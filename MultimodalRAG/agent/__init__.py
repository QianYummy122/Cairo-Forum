"""小罗Bot 多智能体核心包。

架构总览::

    agent/graph.py        多智能体图装配（Supervisor 模式）
    agent/routing.py      条件边：路由 + 联网/重写预算判定（不调用大模型）
    agent/nodes/          图上的 8 个节点，一节点一个文件
        prepare.py         每轮开头清空单轮状态
        supervisor.py      调度智能体：只做"规划"（调用大模型产出计划）
        vision.py          多模态理解智能体：图片 → 可检索信息
        forum.py           论坛检索智能体：多模态 RAG
        web.py             联网搜索智能体：可开关的外部信息通道
        compose.py         答案合成智能体：流式产出带引用的回答
        evaluate.py        质量评估智能体：规则 + 模型双层把关
        rewrite.py         补救准备：把要重做的步骤置为待执行
    agent/session.py      运行时：会话管理 + 事件流
    agent/prompts.py      全部提示词（人设与各智能体角色）
    agent/state.py        共享状态（智能体之间的通信总线）
    agent/events.py       事件协议（推给前端）
    agent/llm_utils.py    稳健的 JSON 解析 / 流式 / 多模态调用
    agent/cli.py          命令行问答（调试用）
"""
from agent.graph import build_agent_graph, build_session, get_agent_graph  # noqa: F401
from agent.session import chat_once, stream_chat  # noqa: F401
from agent.state import BotState  # noqa: F401

__all__ = [
    "BotState", "build_agent_graph", "get_agent_graph", "build_session",
    "stream_chat", "chat_once",
]
