"""文档附件入库：把小罗Bot 页面上传的文件解析成可检索的知识。

支持格式与解析方式
------------------
======================  ==================================================
格式                     解析方式
======================  ==================================================
``.pdf``                PyMuPDF 逐页抽正文（**不需要 GPU/OCR**）
``.txt`` / ``.md``      直接读取
``.json``               读成紧凑文本（对象键值对展开）
``.csv``                csv 模块逐行转成"表头: 值"的可读行
``.docx``               python-docx 抽段落 + 表格
``.png/.jpg/.jpeg/…``   多模态模型生成描述，图片与描述一起向量化
======================  ==================================================

关于扫描件：仓库里 DotsOCR 的权重不存在、也没有起 vLLM 服务，
所以**扫描件 PDF 抽不到文字**。这种情况不静默吞掉，而是明确回报
"该文件可能是扫描件/图片型 PDF，需要先做 OCR"，让用户知道为什么没入库。

与命令行脚本的关系：原先要跑 ``python main.py`` / ``start_knowledge.ps1``
才能把文档入库，现在页面上传即可。两条链路最终都写进同一个集合
``t_knowledge_collection``，只是来源类型不同（``pdf`` vs ``attachment``）。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.config import CONFIG, PROJECT_ROOT
from utils.log_utils import log

# 注意：本模块的**解析部分**刻意不 import milvus_db / forum_ingest，
# 因为那两个模块在导入时就会打开 Milvus Lite（单进程独占锁）。
# 保持解析层"零 Milvus 依赖"，才能在不开服务的情况下单独调解析器
# （`_load_forum_ingest()` 里延迟导入入库相关的东西）。

# 文本类扩展名（读取全文）
_TEXT_EXT = {".txt", ".md", ".markdown"}
# 图片类扩展名（走多模态描述）
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class ParseResult:
    """一个附件的解析结果。"""

    text: str = ""
    images: List[str] = field(default_factory=list)
    # 解析过程中的提示（例如"跳过 3 页无文字页面"），会回给前端展示
    notes: List[str] = field(default_factory=list)
    # 文本总长度（用于判断是否解析到内容）
    ok: bool = True
    error: str = ""


# ---------------------------------------------------------------------------
# 上传落盘
# ---------------------------------------------------------------------------


def store_dir() -> Path:
    path = CONFIG.path("attachment.store_dir", "output/attachments")
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_digest(data: bytes) -> str:
    """内容摘要，用作附件的主键 —— 同一个文件重复上传会覆盖而不是重复入库。"""
    return hashlib.sha1(data).hexdigest()[:16]


def safe_filename(name: str) -> str:
    """去掉路径成分与危险字符，只保留一个安全的基础名。"""
    base = os.path.basename(name or "").strip() or "unnamed"
    base = re.sub(r"[\\/:*?\"<>|\r\n\t]", "_", base)
    return base[:120]


def save_upload(data: bytes, original_name: str) -> Tuple[Path, str, str]:
    """把上传的文件落盘。

    :returns: ``(落盘路径, 内容摘要, 原始文件名)``
    """
    digest = file_digest(data)
    name = safe_filename(original_name)
    target = store_dir() / f"{digest}_{name}"
    if not target.exists():
        target.write_bytes(data)
    else:
        log.info(f"[attachment] 同名同内容文件已存在，直接复用：{target.name}")
    return target, digest, name


def validate_upload(filename: str, size_bytes: int) -> Optional[str]:
    """校验扩展名与大小，返回错误信息（None 表示通过）。"""
    if not CONFIG.get("attachment.enabled", True):
        return "文档上传功能当前未启用"

    ext = Path(filename or "").suffix.lower()
    allowed = [e.lower() for e in (CONFIG.get("attachment.allowed_extensions") or [])]
    if ext not in allowed:
        return f"不支持的文件类型 {ext or '(无扩展名)'}，当前支持：{'、'.join(allowed)}"

    max_bytes = int(CONFIG.get("attachment.max_size_mb", 20)) * 1024 * 1024
    if size_bytes > max_bytes:
        return (f"文件过大：{size_bytes / 1024 / 1024:.1f}MB，"
                f"上限 {CONFIG.get('attachment.max_size_mb', 20)}MB")
    if size_bytes == 0:
        return "文件内容为空"
    return None


# ---------------------------------------------------------------------------
# 各格式解析
# ---------------------------------------------------------------------------


def _parse_pdf(path: Path) -> ParseResult:
    """PyMuPDF 逐页抽正文。扫描件会抽不到文字，这里如实回报。"""
    import pymupdf

    max_pages = int(CONFIG.get("attachment.pdf_max_pages", 200))
    min_chars = int(CONFIG.get("attachment.pdf_min_chars_per_page", 20))

    result = ParseResult()
    pieces: List[str] = []
    empty_pages = 0

    with pymupdf.open(str(path)) as doc:
        total = doc.page_count
        pages = min(total, max_pages)
        if total > max_pages:
            result.notes.append(f"文档共 {total} 页，只解析前 {max_pages} 页")
        for index in range(pages):
            text = (doc.load_page(index).get_text("text") or "").strip()
            if len(text) < min_chars:
                empty_pages += 1
                continue
            pieces.append(f"【第 {index + 1} 页】\n{text}")

    result.text = "\n\n".join(pieces)
    if empty_pages:
        result.notes.append(f"{empty_pages} 页几乎没有文字（可能是图片/扫描页），已跳过")
    if not result.text.strip():
        result.ok = False
        result.error = ("没能从这份 PDF 里提取到文字，它很可能是扫描件或纯图片型 PDF。"
                        "当前环境的 OCR（DotsOCR）未部署，请改用可复制文字的 PDF，"
                        "或先把扫描页转成图片再上传。")
    return result


def _parse_text(path: Path) -> ParseResult:
    return ParseResult(text=path.read_text(encoding="utf-8", errors="ignore"))


def _parse_json(path: Path) -> ParseResult:
    """把 JSON 展开成可读文本，便于按字段名/值检索。"""
    limit = int(CONFIG.get("attachment.json_max_chars", 20000))
    raw = path.read_text(encoding="utf-8", errors="ignore")
    try:
        data = json.loads(raw)
    except Exception as e:
        log.warning(f"[attachment] JSON 解析失败，按纯文本处理：{e}")
        return ParseResult(text=raw[:limit],
                           notes=["JSON 语法有问题，已按纯文本读取"])
    lines: List[str] = []

    def walk(node: Any, prefix: str = "") -> None:
        if len("\n".join(lines)) > limit:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{prefix}[{index}]")
        else:
            lines.append(f"{prefix}: {node}")

    walk(data)
    text = "\n".join(lines)[:limit]
    notes = [f"JSON 已展开为 {len(lines)} 条字段"] if lines else []
    if len("\n".join(lines)) > limit:
        notes.append(f"内容较长，已截断到 {limit} 字")
    return ParseResult(text=text, notes=notes)


def _parse_csv(path: Path) -> ParseResult:
    """逐行转成"列名: 值"的可读文本 —— 直接喂原始 CSV 会让检索命中率很差。"""
    max_rows = int(CONFIG.get("attachment.csv_max_rows", 500))
    raw = path.read_text(encoding="utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(raw))
    try:
        header = next(reader)
    except StopIteration:
        return ParseResult(ok=False, error="CSV 文件是空的")

    lines: List[str] = [f"表格列：{'、'.join(h for h in header if h)}"]
    count = 0
    for row in reader:
        if count >= max_rows:
            break
        pairs = [f"{header[i] or f'列{i + 1}'}: {cell}"
                 for i, cell in enumerate(row) if i < len(header) and str(cell).strip()]
        if pairs:
            lines.append(f"第 {count + 1} 行 —— " + "；".join(pairs))
            count += 1

    notes = []
    if count >= max_rows:
        notes.append(f"只取前 {max_rows} 行")
    notes.append(f"共解析 {count} 行数据")
    return ParseResult(text="\n".join(lines), notes=notes)


def _parse_docx(path: Path) -> ParseResult:
    """python-docx 抽段落与表格。"""
    try:
        import docx
    except ImportError:
        return ParseResult(ok=False, error="服务端缺少 python-docx 依赖，无法解析 .docx")

    document = docx.Document(str(path))
    result = ParseResult()
    pieces: List[str] = []

    for paragraph in document.paragraphs:
        text = (paragraph.text or "").strip()
        if not text:
            continue
        style = (getattr(paragraph.style, "name", "") or "")
        # 标题层级带上 markdown 记号，分块器会把它当成章节标题
        if style.startswith("Heading"):
            level = "".join(ch for ch in style if ch.isdigit()) or "1"
            pieces.append(f"{'#' * min(int(level), 6)} {text}")
        else:
            pieces.append(text)

    for index, table in enumerate(document.tables, 1):
        rows: List[str] = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            pieces.append(f"表格 {index}：\n" + "\n".join(rows))

    result.text = "\n\n".join(pieces)
    if document.tables:
        result.notes.append(f"解析了 {len(document.tables)} 个表格")
    if not result.text.strip():
        result.ok = False
        result.error = "这份 Word 文档里没有可提取的文字（可能内容都在图片里）"
    return result


def _parse_image(path: Path) -> ParseResult:
    """图片：交给多模态模型生成描述，图片本身与描述一起向量化。"""
    from utils.image_utils import describe_image   # 无向量库依赖，解析层可以单独跑

    description = describe_image(str(path), context="")
    result = ParseResult(images=[str(path)])
    result.text = description
    if description:
        result.notes.append("已用多模态模型生成图片描述")
    else:
        result.ok = False
        result.error = "图片理解失败（多模态模型未返回描述），请稍后重试"
    return result


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------


def parse_file(path: Path) -> ParseResult:
    """按扩展名分派到对应的解析器。"""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return _parse_pdf(path)
        if ext in _TEXT_EXT:
            return _parse_text(path)
        if ext == ".json":
            return _parse_json(path)
        if ext == ".csv":
            return _parse_csv(path)
        if ext == ".docx":
            return _parse_docx(path)
        if ext in _IMAGE_EXT:
            return _parse_image(path)
        return ParseResult(ok=False, error=f"没有对应的解析器：{ext}")
    except Exception as e:  # noqa: BLE001
        log.exception(f"[attachment] 解析失败 {path.name}：{e}")
        return ParseResult(ok=False, error=f"解析失败：{e}")


def ingest_attachment(
    path: Path,
    original_name: str,
    uploader: str = "admin",
) -> Dict[str, Any]:
    """解析 + 分块 + 向量化 + 写入知识库，返回可直接回给前端的报告。"""
    # 入库相关的东西延迟导入：见文件顶部说明
    from ingestion.forum_ingest import (
        ForumDocument, KnowledgeChunk, embed_rows, ingest_documents, upsert_rows,
    )
    from milvus_db.collections_operator import knowledge_stats

    ext = path.suffix.lower()
    result = parse_file(path)

    report: Dict[str, Any] = {
        "ok": result.ok,
        "fileName": original_name,
        "fileType": ext,
        "sizeBytes": path.stat().st_size if path.exists() else 0,
        "notes": result.notes,
        "error": result.error,
        "docId": None,
        "chunks": 0,
        "inserted": 0,
        "textLength": len(result.text or ""),
    }
    if not result.ok:
        return report

    doc_id = f"attachment:{file_digest(path.read_bytes())}"
    report["docId"] = doc_id

    # ---------------- 图片附件 ----------------
    # 解析阶段已经让多模态模型生成过描述了，这里**不要再调一次** build_image_chunks
    # （它会重新 describe_image，白白多花一次多模态调用），直接构造图片知识块。
    if ext in _IMAGE_EXT:
        text = f"文件名：{original_name}\n图片描述：{result.text}"
        chunk = KnowledgeChunk(
            doc_id=doc_id,
            chunk_id=f"{doc_id}#img0",
            text=text,
            category="image",
            source_type="attachment",
            title=original_name,
            filename=f"{CONFIG.get('attachment.source_label', '上传文档')}《{original_name}》",
            author=uploader,
            filetype="image",
            image_path=str(path),
            description=result.text,
        )
        inserted = upsert_rows(embed_rows([chunk]))
        report.update({"chunks": 1, "inserted": inserted, "stats": knowledge_stats()})
        return report

    # ---------------- 文本文档 ----------------
    document = ForumDocument(
        doc_id=doc_id,
        source_type="attachment",
        title=original_name,
        content=result.text or "",
        source_url="",                     # 站内没有对应页面，前端不渲染跳转
        author=uploader,
        labels=["上传附件"],
    )
    ingest_report = ingest_documents([document], with_images=False)
    report.update({
        "chunks": ingest_report.get("chunks", 0),
        "inserted": ingest_report.get("inserted", 0),
        "stats": ingest_report.get("stats"),
    })
    return report


def list_attachments(limit: int = 50) -> List[Dict[str, Any]]:
    """列出已入库的附件（从向量库按 source_type 查，而不是扫目录 —— 目录里可能有未入库的残留）。"""
    from milvus_db.collections_operator import KNOWLEDGE_COLLECTION_NAME, client

    try:
        client.load_collection(KNOWLEDGE_COLLECTION_NAME)
        rows = client.query(
            collection_name=KNOWLEDGE_COLLECTION_NAME,
            filter='source_type == "attachment"',
            output_fields=["doc_id", "title", "author", "created_at", "filetype"],
            limit=200,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(f"[attachment] 列出附件失败：{e}")
        return []

    # 同一个附件会有多个块，按 docId 归并
    merged: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        doc_id = row.get("doc_id") or ""
        base_id = doc_id.split("#")[0]
        item = merged.setdefault(base_id, {
            "docId": base_id,
            "title": row.get("title") or "",
            "author": row.get("author") or "",
            "fileType": row.get("filetype") or "",
            "chunks": 0,
        })
        item["chunks"] += 1

    items = sorted(merged.values(), key=lambda x: x["title"])
    return items[:limit]


def delete_attachment(doc_id: str) -> Dict[str, Any]:
    """按附件主键删除其全部知识块（块的主键是 ``<docId>#i``，所以用前缀删）。"""
    from milvus_db.collections_operator import KNOWLEDGE_COLLECTION_NAME, client

    if not doc_id.startswith("attachment:"):
        return {"ok": False, "error": "只能删除通过页面上传的附件"}

    try:
        client.load_collection(KNOWLEDGE_COLLECTION_NAME)
        rows = client.query(
            collection_name=KNOWLEDGE_COLLECTION_NAME,
            filter=f'doc_id like "{doc_id}%"',
            output_fields=["doc_id"],
            limit=1000,
        )
        chunk_ids = [r.get("doc_id") for r in rows if r.get("doc_id")]
        if not chunk_ids:
            return {"ok": False, "error": "没有找到该附件的知识条目"}

        quoted = ", ".join(f'"{c}"' for c in chunk_ids)
        client.delete(collection_name=KNOWLEDGE_COLLECTION_NAME, filter=f"doc_id in [{quoted}]")

        # 顺带删掉落盘的原文件
        digest = doc_id.split(":", 1)[1]
        for f in store_dir().glob(f"{digest}_*"):
            try:
                f.unlink()
            except Exception:  # noqa: BLE001
                pass

        from milvus_db.collections_operator import knowledge_stats
        return {"ok": True, "removed": len(chunk_ids), "stats": knowledge_stats()}
    except Exception as e:  # noqa: BLE001
        log.exception(f"[attachment] 删除附件失败 {doc_id}：{e}")
        return {"ok": False, "error": f"删除失败：{e}"}


__all__ = [
    "ParseResult", "validate_upload", "save_upload", "parse_file",
    "ingest_attachment", "list_attachments", "delete_attachment",
    "safe_filename", "file_digest", "store_dir",
]
