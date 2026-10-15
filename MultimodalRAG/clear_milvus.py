"""
Milvus 数据库清理工具
支持选择性清理：小罗Bot 知识库、旧版 PDF 知识库、长期记忆（聊天上下文）、或全部清理
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from milvus_db.collections_operator import (
    COLLECTION_NAME, CONTEXT_COLLECTION_NAME, KNOWLEDGE_COLLECTION_NAME, client,
)

# 菜单选项与集合的映射
MENU_OPTIONS = {
    '1': {'name': '小罗Bot 知识库（论坛+文档）', 'collection': KNOWLEDGE_COLLECTION_NAME},
    '2': {'name': '旧版 PDF 知识库', 'collection': COLLECTION_NAME},
    '3': {'name': '长期记忆（聊天上下文）', 'collection': CONTEXT_COLLECTION_NAME},
    '4': {'name': '全部清理', 'collection': None},
}


def get_collection_count(collection_name: str) -> int:
    """获取集合中的数据条数"""
    try:
        existing = client.list_collections()
        if collection_name not in existing:
            return 0
        client.load_collection(collection_name)
        results = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["id"]
        )
        return len(results)
    except Exception as e:
        print(f"  [警告] 获取集合 '{collection_name}' 数据量失败：{e}")
        return -1


def clear_collection(collection_name: str):
    """清空指定集合的所有数据"""
    try:
        existing = client.list_collections()
        if collection_name not in existing:
            print(f"  集合 '{collection_name}' 不存在，跳过")
            return True

        client.load_collection(collection_name)

        results = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["id"]
        )

        if not results:
            print(f"  集合 '{collection_name}' 已经是空的")
            return True

        ids = [item['id'] for item in results]
        client.delete(
            collection_name=collection_name,
            filter=f"id in {ids}"
        )

        print(f"  已清空集合 '{collection_name}'，删除 {len(ids)} 条记录")
        return True

    except Exception as e:
        print(f"  [错误] 清空集合 '{collection_name}' 失败：{e}")
        return False


def show_status():
    """显示当前各集合的状态"""
    print("\n  当前数据库状态：")
    print("  " + "-" * 45)

    existing = client.list_collections()

    # 知识库
    if COLLECTION_NAME in existing:
        count = get_collection_count(COLLECTION_NAME)
        count_str = f"{count} 条记录" if count >= 0 else "获取失败"
        print(f"  [1] 知识库（文档内容）  : {count_str}")
    else:
        print(f"  [1] 知识库（文档内容）  : 集合不存在")

    # 长期记忆
    if CONTEXT_COLLECTION_NAME in existing:
        count = get_collection_count(CONTEXT_COLLECTION_NAME)
        count_str = f"{count} 条记录" if count >= 0 else "获取失败"
        print(f"  [2] 长期记忆（聊天上下文）: {count_str}")
    else:
        print(f"  [2] 长期记忆（聊天上下文）: 集合不存在")

    print("  [3] 全部清理（知识库 + 长期记忆）")
    print("  " + "-" * 45)


def confirm_action(target_name: str) -> bool:
    """确认用户是否真的要执行清理"""
    confirm = input(f"\n  确认要清理 【{target_name}】 吗？(输入 yes 确认): ").strip().lower()
    return confirm == 'yes'


def execute_clear(choice: str) -> bool:
    """根据用户选择执行清理"""
    option = MENU_OPTIONS.get(choice)
    if not option:
        print("  无效的选择")
        return False

    target_name = option['name']

    if not confirm_action(target_name):
        print("  操作已取消")
        return False

    print("\n  开始清理...")

    if option['collection']:
        # 清理单个集合
        return clear_collection(option['collection'])
    else:
        # 清理全部
        ok1 = clear_collection(COLLECTION_NAME)
        ok2 = clear_collection(CONTEXT_COLLECTION_NAME)
        return ok1 and ok2


def main():
    print("=" * 55)
    print("  Milvus 数据库清理工具")
    print("  支持选择性清理：知识库 / 长期记忆 / 全部")
    print("=" * 55)

    while True:
        show_status()

        print("\n  短期记忆（InMemorySaver）为内存存储，重启即自动清除，无需手动清理。")

        choice = input("\n  请选择要清理的内容 (1/2/3，输入 q 退出): ").strip().lower()

        if choice in ('q', 'quit', 'exit'):
            print("\n  已退出清理工具")
            break

        if choice not in MENU_OPTIONS:
            print("\n  无效输入，请输入 1、2、3 或 q")
            continue

        execute_clear(choice)

        # 清理后显示最新状态
        print("\n  清理完成！")
        show_status()

        again = input("\n  是否继续其他操作？(y/n): ").strip().lower()
        if again != 'y':
            print("\n  已退出清理工具")
            break
        print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
