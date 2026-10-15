"""文档解析引擎调度：OCR（DotsOCR）开关 + 纯 PyMuPDF 兜底。

总开关是 ``config.yml`` 里的 ``ocr.enabled``：

===========  ================================================================
``true``     你已经把 OCR 配好了（权重放到 ``ocr.hf_model_path``，
             或者 vLLM 已起在 ``ocr.ip:ocr.port``）。PDF 里**没有文字层的页**
             （扫描页/图片型页）会渲染成图交给 DotsOCR 识别。
``false``    纯 PyMuPDF 处理：只读 PDF 自带的文字层。扫描件抽不到字，
             如实回报"需要 OCR"，不静默吞掉、也不假装成功。
===========  ================================================================

两条通路都用这里：

- 页面上传附件 → ``ingestion/attachment_ingest._parse_pdf()``
- Gradio 文档知识库构建 → ``main.py`` → ``do_parse()`` / ``pymupdf_pdf_to_markdown_dir()``

**逐页判断，不是二选一**：能抽到文字层的页一律用 PyMuPDF（原文照搬、最快、
不占显存），只有抽不到文字的页才交给 OCR。这样开不开 OCR 都不影响文字型 PDF。

本模块刻意把 ``dots_ocr`` / ``torch`` / ``pymupdf`` 的 import 全部放在函数内部：
``ocr.enabled=false`` 时，没装 torch、没下权重的机器也能正常跑完整个流程。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from utils.config import CONFIG
from utils.log_utils import log

# 渲染出来的页面位图与 DotsOCR 产物落盘根目录（相对项目根目录）
_OCR_PAGES_SUBDIR = "ocr_pages"

__all__ = [
    "ocr_enabled", "ocr_status", "get_ocr_parser", "reset_ocr_parser",
    "ocr_image", "ocr_pdf_pages",
    "pymupdf_pdf_pages", "pymupdf_pdf_to_markdown_dir",
]


# ---------------------------------------------------------------------------
# 开关与状态
# ---------------------------------------------------------------------------


def ocr_enabled() -> bool:
    """OCR 总开关：``config.yml → ocr.enabled``（缺省 false）。"""
    return bool(CONFIG.get("ocr.enabled", False))


def ocr_status() -> Dict[str, Any]:
    """OCR 现状快照：日志、Gradio 界面提示、排查配置时用。

    刻意**不**接进对外接口：这里会带上本地权重路径与内网地址，不适合下发给前端。
    不加载任何模型，纯读配置。
    """
    use_hf = bool(CONFIG.get("ocr.use_hf", False))
    return {
        "enabled": ocr_enabled(),
        "engine": ("huggingface" if use_hf else "vllm") if ocr_enabled() else "pymupdf",
        "modelName": CONFIG.get("ocr.model_name", "dots_ocr"),
        "endpoint": (f"http://{CONFIG.get('ocr.ip', 'localhost')}:{CONFIG.get('ocr.port', 6006)}/v1"
                     if not use_hf else None),
        "modelPath": (str(_hf_model_path()) if use_hf else None),
        "prompt": CONFIG.get("ocr.prompt", "prompt_layout_all_en"),
        "dpi": int(CONFIG.get("ocr.dpi", 120)),
    }


def _hf_model_path() -> Path:
    """本地权重目录（相对路径按项目根目录解析）。"""
    from utils.config import PROJECT_ROOT

    raw = Path(str(CONFIG.get("ocr.hf_model_path", "weights/DotsOCR")))
    return raw if raw.is_absolute() else (PROJECT_ROOT / raw)


# ---------------------------------------------------------------------------
# DotsOCR 调用（懒加载 + 单例）
# ---------------------------------------------------------------------------

_parser: Any = None
_parser_error: Optional[str] = None


def reset_ocr_parser() -> None:
    """丢掉缓存的解析器（补好权重后不想重启服务时用）。"""
    global _parser, _parser_error
    _parser = None
    _parser_error = None


def get_ocr_parser():
    """构造并缓存 ``DotsOCRParser``。

    HF 模式下这一步会真的把权重读进显存，所以只做一次；
    构造失败的原因（权重不存在、缺 torch 等）会被缓存下来，避免每页都重试一遍。
    """
    global _parser, _parser_error

    if _parser is not None:
        return _parser
    if _parser_error:
        raise RuntimeError(_parser_error)

    try:
        from dots_ocr.parser import DotsOCRParser

        _parser = DotsOCRParser()
    except Exception as e:  # noqa: BLE001
        status = ocr_status()
        if status["engine"] == "huggingface":
            hint = (f"本地权重加载失败（ocr.hf_model_path = {status['modelPath']}）。"
                    f"请确认权重已放好、且已按 requirements.txt 装好 "
                    f"transformers / torch / qwen-vl-utils，然后重启本服务。")
        else:
            hint = (f"连接 {status['endpoint']} 的 vLLM 服务失败。"
                    f"请确认 vLLM 已启动、且 model_name 与 ocr.model_name 一致，然后重启本服务。")
        _parser_error = f"OCR 已启用（ocr.enabled=true）但不可用：{hint} 原始错误：{e}"
        log.error(f"[ocr] {_parser_error}")
        raise RuntimeError(_parser_error) from e

    log.info(f"[ocr] DotsOCR 解析器就绪：{ocr_status()}")
    return _parser


def _ocr_work_dir(tag: Optional[str]) -> Path:
    """OCR 中间产物目录：``output/ocr_pages/<tag>/``。"""
    safe = "".join(ch for ch in str(tag or "tmp") if ch.isalnum() or ch in "-_.") or "tmp"
    path = CONFIG.path("paths.output_dir") / _OCR_PAGES_SUBDIR / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def ocr_image(image_path, out_dir=None, tag: Optional[str] = None,
              parser=None) -> str:
    """把一张图片交给 DotsOCR，返回识别出的 Markdown（失败时抛异常）。"""
    parser = parser or get_ocr_parser()
    prompt = CONFIG.get("ocr.prompt", "prompt_layout_all_en")
    image_path = Path(image_path)
    work_dir = Path(out_dir) if out_dir else _ocr_work_dir(tag)
    work_dir.mkdir(parents=True, exist_ok=True)
    name = tag or image_path.stem

    # fitz_preprocess=False：图已经是我们自己按 ocr.dpi 渲染好的，不必再经 fitz 重采样
    results = parser.parse_image(str(image_path), name, prompt, str(work_dir),
                                 fitz_preprocess=False)
    if not results:
        return ""

    md_path = (results[0] or {}).get("md_content_path")
    if not md_path or not os.path.exists(md_path):
        return ""
    return Path(md_path).read_text(encoding="utf-8", errors="ignore")


def _render_pdf_page(doc, index: int, png_path: Path, dpi: int) -> None:
    """用 PyMuPDF 把某一页渲染成 PNG —— 这是 DotsOCR 的输入（它看不见 PDF）。"""
    import pymupdf

    page = doc[index]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False)
    # 与 dots_ocr/utils/doc_utils.py 同样的保险：过大就退回 fitz 默认 72 DPI
    if pix.width > 4500 or pix.height > 4500:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0), alpha=False)
    pix.save(str(png_path))


def ocr_pdf_pages(pdf_path, pages: Optional[Iterable[int]] = None,
                  tag: Optional[str] = None) -> Dict[int, str]:
    """把 PDF 的指定页渲染成图后交给 DotsOCR，返回 ``{页索引(0基): markdown}``。

    调用方负责决定哪些页需要 OCR（通常是"PyMuPDF 抽不到文字"的那些页）。
    单页识别失败不会中断整体：记一条日志后跳过该页。
    """
    import pymupdf

    parser = get_ocr_parser()
    dpi = int(CONFIG.get("ocr.dpi", 120))
    work_dir = _ocr_work_dir(tag)
    out: Dict[int, str] = {}

    with pymupdf.open(str(pdf_path)) as doc:
        indices = list(range(doc.page_count)) if pages is None else sorted(set(int(p) for p in pages))
        for index in indices:
            if index < 0 or index >= doc.page_count:
                continue
            png_path = work_dir / f"page_{index}.png"
            try:
                _render_pdf_page(doc, index, png_path, dpi)
                md = ocr_image(png_path, out_dir=work_dir, tag=f"page_{index}", parser=parser)
            except Exception as e:  # noqa: BLE001
                log.warning(f"[ocr] 第 {index + 1} 页识别失败，已跳过：{e}")
                continue
            if md and md.strip():
                out[index] = md
            else:
                log.warning(f"[ocr] 第 {index + 1} 页没有识别出内容")
    return out


# ---------------------------------------------------------------------------
# 纯 PyMuPDF（不依赖任何模型）
# ---------------------------------------------------------------------------


def pymupdf_pdf_pages(pdf_path, max_pages: Optional[int] = None,
                      min_chars: int = 0) -> tuple:
    """逐页读 PDF **自带的文字层**。

    :returns: ``(总页数, {页索引(0基): 文字})``，少于 ``min_chars`` 的页不放进字典。
    """
    import pymupdf

    out: Dict[int, str] = {}
    with pymupdf.open(str(pdf_path)) as doc:
        total = doc.page_count
        limit = total if max_pages is None else min(total, int(max_pages))
        for index in range(limit):
            text = (doc.load_page(index).get_text("text") or "").strip()
            if len(text) >= max(int(min_chars), 0):
                out[index] = text
    return total, out


def pymupdf_pdf_to_markdown_dir(pdf_path, out_dir, stem: Optional[str] = None,
                                max_pages: Optional[int] = None) -> Dict[str, Any]:
    """纯 PyMuPDF 把 PDF 写成 ``<stem>_page_N.md`` 目录。

    产物与 DotsOCR 的 ``do_parse()`` **同构**（同样的文件名规则），
    所以 ``ingestion.forum_ingest.sync_pdf_markdown()`` 能原样接着入库。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or Path(pdf_path).stem

    total, pages = pymupdf_pdf_pages(pdf_path, max_pages=max_pages, min_chars=1)
    for index in sorted(pages):
        target = out_dir / f"{stem}_page_{index}.md"
        target.write_text(pages[index], encoding="utf-8")

    written = len(pages)
    report: Dict[str, Any] = {
        "ok": written > 0,
        "total": total,
        "written": written,
        "skipped": max(total - written, 0),
        "engine": "pymupdf",
        "error": "",
    }
    if not written:
        report["error"] = (f"这份 PDF 的 {total} 页都没有文字层，很可能是扫描件/纯图片型 PDF。"
                           f"纯 PyMuPDF 抽不到文字，请在 config.yml 里把 ocr.enabled 改成 true "
                           f"并配好 DotsOCR 权重，或改用可复制文字的 PDF。")
    return report
