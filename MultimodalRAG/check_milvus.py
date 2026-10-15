"""查看小罗Bot 知识库里的数据。

用法：
    python check_milvus.py             # 看统一知识库（论坛 + 文档）
    python check_milvus.py --all       # 三个集合都看
    python check_milvus.py --type article   # 只看论坛文章
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from milvus_db.collections_operator import (
    COLLECTION_NAME, CONTEXT_COLLECTION_NAME, KNOWLEDGE_COLLECTION_NAME,
    client, ensure_collections, knowledge_stats,
)

KNOWLEDGE_FIELDS = ["text", "category", "source_type", "title", "filename",
                    "source_url", "author", "image_path"]


def show_collection(collection_name: str, output_fields, limit: int, filter_expr: str = ""):
    """打印一个集合的基本信息和若干条记录。"""
    existing = client.list_collections()
    if collection_name not in existing:
        print(f"\n集合 '{collection_name}' 不存在。")
        return

    info = client.describe_collection(collection_name)
    print(f"\n{'=' * 70}")
    print(f"集合：{info['collection_name']}")
    print(f"字段：{[f['name'] for f in info['fields']]}")

    client.load_collection(collection_name)
    results = client.query(
        collection_name=collection_name,
        filter=filter_expr,
        output_fields=output_fields,
        limit=limit,
    )
    print(f"（显示前 {len(results)} 条，filter={filter_expr or '无'}）\n")
    for i, doc in enumerate(results, 1):
        print(f"--- 记录 #{i} ---")
        for field in output_fields:
            value = doc.get(field)
            if value in (None, ""):
                continue
            text = str(value)
            if len(text) > 110:
                text = text[:110] + "…"
            print(f"  {field:12}：{text}")
        print()


def main():
    parser = argparse.ArgumentParser(description="查看小罗Bot 知识库")
    parser.add_argument("--all", action="store_true", help="查看全部三个集合")
    parser.add_argument("--type", default=None,
                        help="只看某种来源：article/comment/resource/label/snapshot/pdf")
    parser.add_argument("--limit", type=int, default=20, help="每个集合显示条数")
    args = parser.parse_args()

    ensure_collections()

    stats = knowledge_stats()
    print("=" * 70)
    print(f"小罗Bot 知识库总览（{KNOWLEDGE_COLLECTION_NAME}）")
    print("=" * 70)
    print(f"  总条目：{stats['total']}")
    for key, value in (stats.get("bySourceType") or {}).items():
        print(f"    - {key:10}：{value}")

    filter_expr = f'source_type == "{args.type}"' if args.type else ""
    show_collection(KNOWLEDGE_COLLECTION_NAME, KNOWLEDGE_FIELDS, args.limit, filter_expr)

    if args.all:
        show_collection(COLLECTION_NAME, ["text", "category", "filename", "title"], args.limit)
        show_collection(CONTEXT_COLLECTION_NAME, ["context_text", "user", "message_type"], args.limit)


if __name__ == "__main__":
    main()
