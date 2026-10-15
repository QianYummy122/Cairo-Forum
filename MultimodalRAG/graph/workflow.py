"""命令行版小罗Bot 问答入口。

运行：``python graph/workflow.py``

这个文件现在是 ``agent.cli`` 的薄封装，保证老命令仍然可用；
真正的多智能体实现在 ``agent/`` 包，Web 页面（vue-ui 的 /bot）用的也是它。
"""
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.cli import main  # noqa: E402

if __name__ == "__main__":
    # 默认进入交互模式；传参时按单轮提问执行
    raise SystemExit(main(sys.argv[1:] or ["--interactive"]))
