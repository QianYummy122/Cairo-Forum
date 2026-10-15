"""命令行问答入口（调试用）。

用法::

    # 单轮提问
    python -m agent.cli "论坛里有哪些标签"

    # 开启联网搜索
    python -m agent.cli "Apache Flink 有界流和无界流有什么区别" --web

    # 交互式多轮
    python -m agent.cli --interactive --web

    # 指定用户（影响长期记忆与引用）
    python -m agent.cli "你好" --user ZS
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.session import stream_chat  # noqa: E402


async def ask(question: str, web: bool, user: str, session_id: str = None) -> None:
    """跑一轮，把事件流打印成人能看懂的过程。"""
    print(f"\n👤 用户：{question}")
    print("-" * 72)
    async for event in stream_chat(question, session_id=session_id, user=user,
                                   web_search_enabled=web):
        kind = event["event"]
        data = event["data"]

        if kind == "meta":
            print(f"🆔 会话：{data['sessionId']}")
        elif kind == "plan":
            print(f"🧭 计划：{' → '.join(data.get('plan') or [])}")
        elif kind == "agent":
            icon = {"start": "▶", "done": "✔", "skipped": "⏭"}.get(data.get("status"), "•")
            if data.get("status") == "start":
                print(f"\n{icon} [{data.get('label')}] {data.get('detail') or ''}")
            else:
                print(f"{icon} [{data.get('label')}] {data.get('detail') or ''}")
        elif kind == "sources":
            for key in ("forum", "web"):
                for item in data.get(key) or []:
                    print(f"   🔗 {key}: {item.get('title')} {item.get('url') or ''}")
        elif kind == "delta":
            sys.stdout.write(data.get("text") or "")
            sys.stdout.flush()
        elif kind == "done":
            print("\n" + "-" * 72)
            print(f"📊 论坛命中充分={data.get('forumSufficient')} "
                  f"相似度={data.get('forumRelevance')} "
                  f"用了联网={data.get('usedWebSearch')} "
                  f"评分={data.get('answerScore')} "
                  f"耗时={data.get('elapsedMs')}ms")
            if not data.get("answer"):
                print("⚠️  未生成回答")
        elif kind == "error":
            print(f"\n❌ {data.get('message')}")


async def interactive(web: bool, user: str) -> None:
    session_id = None
    print("小罗Bot 交互模式（exit / quit 退出）")
    while True:
        try:
            question = input("\n👤 你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"exit", "quit", "退出"}:
            break
        if not question:
            continue
        await ask(question, web, user, session_id)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="agent.cli", description="小罗Bot 命令行问答")
    parser.add_argument("question", nargs="?", help="要问的问题")
    parser.add_argument("--web", action="store_true", help="启用联网搜索")
    parser.add_argument("--user", default="guest", help="用户名（默认 guest）")
    parser.add_argument("--session", default=None, help="会话 id（用于接着上一轮聊）")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式多轮对话")
    args = parser.parse_args(argv)

    if args.interactive or not args.question:
        asyncio.run(interactive(args.web, args.user))
        return 0

    asyncio.run(ask(args.question, args.web, args.user, args.session))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
