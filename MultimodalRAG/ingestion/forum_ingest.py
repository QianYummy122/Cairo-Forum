"""论坛知识入库：把论坛内容变成小罗Bot 可检索的多模态知识库。

流程（与论文里的 RAG 索引阶段一一对应）::

    ForumDocument（REST/MySQL/本地快照）
        ↓ 1. 清洗 & 分块      chunk_document()
        ↓ 2. 图片理解          describe_image()    ← 多模态 LLM 生成图片描述
        ↓ 3. 统一向量化        embed_rows()        ← 图文同一个 1024 维空间
        ↓ 4. 增量写入          upsert_rows()       ← 按 doc_id 先删后插

第 4 步用 ``doc_id``（如 ``article:43``）做"先删后插"，所以重复执行同步不会产生
重复数据，也天然支持"论坛文章更新后重新同步"。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from langchain_core.messages import HumanMessage

from ingestion.forum_source import ForumDocument, pick_source
from milvus_db.collections_operator import (
    KNOWLEDGE_COLLECTION_NAME, client, drop_knowledge_docs, flush_knowledge,
    knowledge_stats,
)
from my_llm import multiModal_llm
from utils.config import CONFIG, PROJECT_ROOT
from utils.embeddings_utils import (
    embed_image_with_text, embed_texts, normalize_image,
)
from utils.image_utils import (
    IMAGE_PROMPT_PLAIN, IMAGE_PROMPT_WITH_CONTEXT,   # noqa: F401  (兼容旧的模块级引用)
)
from utils.log_utils import log

# 分块时的自然边界
_BLOCK_SEP_RE = re.compile(r"\n\s*\n")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")


@dataclass
class KnowledgeChunk:
    """一条待入库的知识条目（文本块或图片块）。"""

    doc_id: str                 # 业务主键（同一篇文档的多个块共享前缀）
    chunk_id: str               # 块级唯一键 "<doc_id>#<i>"
    text: str                   # 参与 BM25 与稠密向量化的正文
    category: str               # text / image
    source_type: str
    title: str
    filename: str               # 展示用来源名
    source_url: str = ""
    author: str = ""
    created_at: str = ""
    labels: str = ""
    filetype: str = ""
    image_path: str = ""
    description: str = ""
    dense: List[float] = field(default_factory=list)

    def to_row(self) -> Dict[str, Any]:
        """转成 Milvus 集合的字段结构。"""
        return {
            "text": (self.text or "")[:CONFIG.get("milvus.text_max_length", 6000)],
            "category": self.category,
            "doc_id": self.chunk_id[:CONFIG.get("milvus.field_max_length", 1000)],
            "source_type": self.source_type,
            "title": (self.title or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "filename": (self.filename or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "source_url": (self.source_url or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "author": (self.author or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "created_at": (self.created_at or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "labels": (self.labels or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "filetype": (self.filetype or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "image_path": (self.image_path or "")[:CONFIG.get("milvus.field_max_length", 1000)],
            "description": (self.description or "")[:CONFIG.get("milvus.description_max_length", 2000)],
            "dense": self.dense,
        }


# ---------------------------------------------------------------------------
# 1. 分块
# ---------------------------------------------------------------------------


def _split_blocks(text: str) -> List[str]:
    """先按空行切成块，块内再按句子切成不超过 chunk_size 的片段。"""
    return [b.strip() for b in _BLOCK_SEP_RE.split(text or "") if b.strip()]


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[str]:
    """把长文本切成带重叠的片段。

    策略（够用且可解释）：标题行自成一段；其余按空行分段；
    段内超过 ``chunk_size`` 时按中英文句末标点累积切分，并保留 ``chunk_overlap``
    个字符的重叠，避免把一句话的答案切散。
    """
    chunk_size = chunk_size or CONFIG.get("forum.chunk_size", 700)
    chunk_overlap = chunk_overlap or CONFIG.get("forum.chunk_overlap", 80)
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    buffer = ""
    for block in _split_blocks(text):
        # 标题单独成块，方便"按章节问"
        if _HEADING_RE.match(block) and len(block) < 120:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.append(block)
            continue

        if len(buffer) + len(block) + 2 <= chunk_size:
            buffer = f"{buffer}\n\n{block}" if buffer else block
            continue

        if buffer:
            chunks.append(buffer)
        if len(block) <= chunk_size:
            buffer = block
            continue

        # 长段落：按句子累积
        sentences = re.split(r"(?<=[。！？；!?;\.])\s*", block)
        piece = ""
        for sentence in sentences:
            if not sentence:
                continue
            if len(piece) + len(sentence) <= chunk_size:
                piece += sentence
            else:
                if piece:
                    chunks.append(piece)
                # 保留尾部重叠
                piece = (piece[-chunk_overlap:] if chunk_overlap and piece else "") + sentence
        buffer = piece

    if buffer:
        chunks.append(buffer)

    # 收尾：过短的尾块并入前一块，避免产生噪声块
    merged: List[str] = []
    for c in chunks:
        c = c.strip()
        if not c:
            continue
        if merged and len(c) < 30 and len(merged[-1]) + len(c) <= chunk_size:
            merged[-1] = f"{merged[-1]}\n{c}"
        else:
            merged.append(c)
    return merged


def document_to_chunks(doc: ForumDocument) -> List[KnowledgeChunk]:
    """一篇论坛内容 → 若干文本知识块（图片块在 :func:`build_image_chunks` 里处理）。"""
    chunks: List[KnowledgeChunk] = []
    labels = "，".join(doc.labels) if doc.labels else ""
    # 头部元信息拼进第一块，让"谁写的/什么时候写的/属于哪个标签"也能被检索到
    header = f"{doc.display_source}"
    if doc.author:
        header += f"｜作者：{doc.author}"
    if labels:
        header += f"｜标签：{labels}"
    if doc.created_at:
        header += f"｜时间：{doc.created_at}"

    body = doc.content or ""
    pieces = chunk_text(body)
    # 纯图片条目（正文为空、只有图）不生成文本块，交给 build_image_chunks 处理
    if not pieces and not body.strip():
        return []
    if not pieces and doc.title:
        pieces = [doc.title]

    for index, piece in enumerate(pieces):
        text = f"{header}\n{piece}" if index == 0 else f"{doc.title}\n{piece}"
        chunks.append(KnowledgeChunk(
            doc_id=doc.doc_id,
            chunk_id=f"{doc.doc_id}#{index}",
            text=text,
            category="text",
            source_type=doc.source_type,
            title=doc.title,
            filename=doc.display_source,
            source_url=doc.source_url,
            author=doc.author,
            created_at=doc.created_at,
            labels=labels,
            filetype="text",
        ))
    return chunks


# ---------------------------------------------------------------------------
# 2. 图片理解（多模态）
# ---------------------------------------------------------------------------


def describe_image(image: str, context: str = "") -> str:
    """用多模态大模型给图片生成一段可检索的中文描述。

    实现已移到 :mod:`utils.image_utils`（那里不依赖向量库，可单独复用与测试）；
    这里保留同名函数，老的 ``from ingestion.forum_ingest import describe_image`` 不受影响。
    """
    from utils.image_utils import describe_image as _describe

    return _describe(image, context)


def build_image_chunks(doc: ForumDocument, limit: int = None) -> List[KnowledgeChunk]:
    """把正文里的图片转成"图片知识块"：图片 + 描述一起向量化。"""
    limit = limit if limit is not None else CONFIG.get("forum.max_images_per_article", 3)
    chunks: List[KnowledgeChunk] = []
    for index, image in enumerate((doc.images or [])[:limit]):
        # 只处理能真正拿到的图片（URL 可下载 / 本地文件存在）
        if not image.startswith("data:image") and not normalize_image(image)[0]:
            log.info(f"[ingest] 跳过不可用图片：{image[:80]}")
            continue
        description = describe_image(image, context=doc.content[:800] if doc.content else "")
        if not description:
            continue
        chunks.append(KnowledgeChunk(
            doc_id=doc.doc_id,
            chunk_id=f"{doc.doc_id}#img{index}",
            # 图片的稀疏检索文本用描述，稠密向量用"图片+描述"
            text=description,
            category="image",
            source_type=doc.source_type,
            title=doc.title,
            filename=doc.display_source,
            source_url=doc.source_url,
            author=doc.author,
            created_at=doc.created_at,
            labels="，".join(doc.labels) if doc.labels else "",
            filetype="image",
            image_path=image,
            description=description,
        ))
    return chunks


# ---------------------------------------------------------------------------
# 3. 向量化
# ---------------------------------------------------------------------------


def embed_rows(chunks: List[KnowledgeChunk], batch_size: int = 10) -> List[KnowledgeChunk]:
    """给所有知识块补上稠密向量（文本走批量，图片走单条多模态接口）。"""
    text_chunks = [c for c in chunks if c.category == "text"]
    image_chunks = [c for c in chunks if c.category == "image"]

    if text_chunks:
        vectors = embed_texts([c.text for c in text_chunks], batch_size=batch_size)
        for chunk, vector in zip(text_chunks, vectors):
            chunk.dense = vector

    for chunk in image_chunks:
        chunk.dense = embed_image_with_text(chunk.image_path, chunk.description or chunk.text)

    embedded = [c for c in chunks if c.dense]
    skipped = len(chunks) - len(embedded)
    if skipped:
        log.warning(f"[ingest] {skipped} 个知识块向量化失败，已跳过")
    return embedded


def upsert_rows(chunks: List[KnowledgeChunk]) -> int:
    """按 chunk_id 先删后插，实现幂等的增量写入。"""
    if not chunks:
        return 0
    chunk_ids = [c.chunk_id for c in chunks]
    try:
        drop_knowledge_docs(chunk_ids)
    except Exception as e:
        log.warning(f"[ingest] 删除旧块失败（首次入库可忽略）：{e}")
    rows = [c.to_row() for c in chunks]
    res = client.insert(collection_name=KNOWLEDGE_COLLECTION_NAME, data=rows)
    inserted = int(res.get("insert_count", len(rows))) if isinstance(res, dict) else len(rows)
    log.info(f"[ingest] 写入 {inserted} 条知识到 {KNOWLEDGE_COLLECTION_NAME}")

    # 立刻落盘：Milvus Lite 的写入先进 WAL，进程被强杀会写坏 WAL 并丢掉整段写入。
    # 见 collections_operator.flush_knowledge 的说明。
    flush_knowledge()
    return inserted


# ---------------------------------------------------------------------------
# 4. 对外主入口
# ---------------------------------------------------------------------------


def ingest_documents(
    documents: Iterable[ForumDocument],
    with_images: bool = None,
    progress_every: int = 20,
) -> Dict[str, Any]:
    """把一批 :class:`ForumDocument` 分块、向量化并写入知识库。"""
    with_images = CONFIG.get("forum.ingest_images", True) if with_images is None else with_images
    documents = list(documents)

    all_chunks: List[KnowledgeChunk] = []
    for index, doc in enumerate(documents, 1):
        if not (doc.content or doc.images):
            continue
        chunks = document_to_chunks(doc)
        if with_images:
            chunks.extend(build_image_chunks(doc))
        all_chunks.extend(chunks)
        if index % progress_every == 0:
            log.info(f"[ingest] 已分块 {index}/{len(documents)} 篇，累计 {len(all_chunks)} 块")

    embedded = embed_rows(all_chunks)
    inserted = upsert_rows(embedded)

    return {
        "documents": len(documents),
        "chunks": len(all_chunks),
        "embedded": len(embedded),
        "inserted": inserted,
        "stats": knowledge_stats(),
    }


def sync_forum(
    prefer: str = None,
    with_images: bool = None,
    source_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """同步论坛全部内容到知识库（REST 网关优先，MySQL/本地快照兜底）。"""
    source = pick_source(prefer)
    if source is None:
        return {
            "ok": False,
            "error": "没有可用的论坛数据源（springboot 网关未启动、MySQL 不可达、也没有本地快照）",
            "source": None,
        }

    log.info(f"[ingest] 开始从 {source.name} 同步论坛内容 …")
    documents = list(source.fetch())
    if source_types:
        wanted = set(source_types)
        documents = [d for d in documents if d.source_type in wanted]
    log.info(f"[ingest] 拉取到 {len(documents)} 条论坛内容")

    report = ingest_documents(documents, with_images=with_images)
    report["ok"] = True
    report["source"] = source.name
    return report


def documents_to_knowledge(docs: Iterable, source_filename: str) -> List[ForumDocument]:
    """把 ``splitters/splitter_md.py`` 切出来的 LangChain ``Document`` 列表
    转成统一知识条目（保留原项目"标题层级 + 图片独立成块"的四层分块成果）。

    - ``embedding_type == 'text'``  → 正文块，标题层级（Header 1~3）拼成 title；
    - ``embedding_type == 'image'`` → 图片块，``page_content`` 是本地图片路径，
      由图片理解模块补描述后再向量化。
    """
    documents: List[ForumDocument] = []
    for index, doc in enumerate(docs):
        metadata = getattr(doc, "metadata", {}) or {}
        headers = [metadata.get(f"Header {level}") for level in (1, 2, 3)]
        title = " → ".join([h for h in headers if h]) or (source_filename or "文档")
        embedding_type = metadata.get("embedding_type", "text")

        if embedding_type == "image":
            image_path = (getattr(doc, "page_content", "") or "").strip()
            if not image_path:
                continue
            documents.append(ForumDocument(
                doc_id=f"pdf:{source_filename}:img{index}",
                source_type="pdf",
                title=title or source_filename,
                # 图片块的"正文"稍后由多模态模型生成描述
                content="",
                images=[image_path],
            ))
        else:
            text = (getattr(doc, "page_content", "") or "").strip()
            if not text:
                continue
            documents.append(ForumDocument(
                doc_id=f"pdf:{source_filename}:t{index}",
                source_type="pdf",
                title=title or source_filename,
                content=text,
            ))
    return documents


def ingest_split_documents(docs: Iterable, source_filename: str, with_images: bool = True) -> Dict[str, Any]:
    """把 MarkdownDirSplitter 的分块结果写入统一知识库。"""
    documents = documents_to_knowledge(docs, source_filename)
    report = ingest_documents(documents, with_images=with_images)
    # 图片块没有正文，需要单独处理：它们的描述在 build_image_chunks 里生成
    report["ok"] = True
    report["source"] = "pdf-splitter"
    return report


def sync_pdf_markdown(md_dir: str, source_filename: str, with_images: bool = True) -> Dict[str, Any]:
    """把 PDF 解析出的 Markdown 目录也并入统一知识库（复用原项目的四层分块器）。"""
    from pathlib import Path

    md_dir_path = Path(md_dir)
    if not md_dir_path.is_dir():
        return {"ok": False, "error": f"目录不存在：{md_dir}"}

    from milvus_db.collections_operator import KNOWLEDGE_COLLECTION_NAME  # noqa: F401  (文档说明用)
    from splitters.splitter_md import MarkdownDirSplitter

    images_dir = str(CONFIG.path("paths.output_dir") / CONFIG.get("paths.images_subdir", "images"))
    splitter = MarkdownDirSplitter(images_output_dir=images_dir)
    docs = splitter.process_md_dir(str(md_dir_path), source_filename)
    return ingest_split_documents(docs, source_filename, with_images=with_images)


__all__ = [
    "KnowledgeChunk",
    "chunk_text",
    "document_to_chunks",
    "describe_image",
    "build_image_chunks",
    "embed_rows",
    "upsert_rows",
    "ingest_documents",
    "ingest_split_documents",
    "documents_to_knowledge",
    "sync_forum",
    "sync_pdf_markdown",
    "PROJECT_ROOT",
]
