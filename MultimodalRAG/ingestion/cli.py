"""知识库同步命令行入口。

用法::

    # 自动探测数据源（springboot 网关 → MySQL → 本地快照）并全量同步
    python -m ingestion.cli sync

    # 只用某个数据源
    python -m ingestion.cli sync --source mysql
    python -m ingestion.cli sync --source local-snapshot

    # 只同步文章（不同步评论/资源/标签）
    python -m ingestion.cli sync --types article

    # 不抓图片（跳过图片理解与多模态向量化，速度快很多）
    python -m ingestion.cli sync --no-images

    # 查看数据源与知识库状态
    python -m ingestion.cli status

    # 把 PDF 解析产物（output/<名字>/*.md）并入知识库
    python -m ingestion.cli sync-pdf --dir output/xxx --name xxx.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# 保证可以直接 python -m ingestion.cli 运行
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ingestion.forum_ingest import sync_forum, sync_pdf_markdown  # noqa: E402
from ingestion.forum_source import build_sources  # noqa: E402
from milvus_db.collections_operator import knowledge_stats  # noqa: E402


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_status(_args) -> int:
    _print({
        "sources": [
            {"name": s.name, "available": s.available(),
             "detail": getattr(s, "base_url", getattr(s, "database", "")) if hasattr(s, "base_url") or hasattr(s, "database") else ""}
            for s in build_sources()
        ],
        "knowledge": knowledge_stats(),
    })
    return 0


def cmd_sync(args) -> int:
    report = sync_forum(
        prefer=args.source,
        with_images=not args.no_images,
        source_types=args.types.split(",") if args.types else None,
    )
    _print(report)
    return 0 if report.get("ok") else 1


def cmd_sync_pdf(args) -> int:
    _print(sync_pdf_markdown(args.dir, args.name, with_images=not args.no_images))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ingestion.cli", description="小罗Bot 知识库同步工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="查看数据源与知识库状态")
    p_status.set_defaults(func=cmd_status)

    p_sync = sub.add_parser("sync", help="同步论坛内容到知识库")
    p_sync.add_argument("--source", default=None,
                        choices=["springboot-rest", "mysql", "local-snapshot"],
                        help="指定数据源（默认自动探测）")
    p_sync.add_argument("--types", default=None,
                        help="只同步指定来源类型，逗号分隔，如 article,comment")
    p_sync.add_argument("--no-images", action="store_true", help="跳过图片理解与多模态向量化")
    p_sync.set_defaults(func=cmd_sync)

    p_pdf = sub.add_parser("sync-pdf", help="把 PDF 解析产物并入知识库")
    p_pdf.add_argument("--dir", required=True, help="Markdown 目录，如 output/xxx")
    p_pdf.add_argument("--name", required=True, help="原始文件名，用于来源展示")
    p_pdf.add_argument("--no-images", action="store_true", help="跳过图片入库")
    p_pdf.set_defaults(func=cmd_sync_pdf)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
