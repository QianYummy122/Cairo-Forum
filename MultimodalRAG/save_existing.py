"""直接存入知识库（跳过 OCR 解析，使用已解析好的 MD 文件）。

用法：
    python save_existing.py <output 下的子目录名>
若不传参数，则交互式列出并选择目录。

与 ``main.py`` 的"存入知识库"按钮走的是同一条链路
（``ingestion.sync_pdf_markdown``），因此都会写进小罗Bot 的统一知识库。
"""
import os
import sys

from ingestion.forum_ingest import sync_pdf_markdown
from utils.common_utils import get_sorted_md_files
from utils.config import CONFIG

# Markdown 解析产物根目录（来自 config.yml -> paths.output_dir）
BASE_MD_DIR = str(CONFIG.path("paths.output_dir"))


def save_existing_to_knowledge(pdf_dir_name: str, pdf_filename: str):
    """把已解析的 MD 文件存入小罗Bot 统一知识库。

    :param pdf_dir_name: output 下的子目录名
    :param pdf_filename: 原始 PDF 文件名（用于标记来源）
    """
    md_dir = os.path.join(BASE_MD_DIR, pdf_dir_name)
    if not os.path.isdir(md_dir):
        print(f"❌ 目录不存在: {md_dir}")
        return

    md_files = get_sorted_md_files(md_dir)
    print(f" 找到 {len(md_files)} 个 MD 文件")

    result = sync_pdf_markdown(md_dir, pdf_filename)
    if not result.get("ok"):
        print(f"❌ 入库失败：{result.get('error')}")
        return

    stats = result.get("stats") or {}
    print(f"\n✅ 成功入库 {result.get('inserted', 0)} 条知识"
          f"（分块 {result.get('chunks', 0)}，向量化 {result.get('embedded', 0)}）")
    print(f"   当前知识库共 {stats.get('total', 0)} 条：{stats.get('bySourceType')}")


if __name__ == '__main__':
    print(" 已解析的文档目录：")
    images_sub = CONFIG.get("paths.images_subdir", "images")
    dirs = [d for d in os.listdir(BASE_MD_DIR)
            if os.path.isdir(os.path.join(BASE_MD_DIR, d)) and d != images_sub]
    for i, d in enumerate(dirs, 1):
        print(f"  {i}. {d}")

    print()
    target = sys.argv[1] if len(sys.argv) > 1 else input("请输入要存入知识库的目录名：").strip()
    save_existing_to_knowledge(target, f"{target}.pdf")
