"""小罗Bot 多智能体工作流的装配。

拓扑（Supervisor 模式）::

                    ┌──────────────┐
        START ─────▶│   prepare    │  清空上一轮遗留的调度状态（见下）
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │  supervisor  │◀──────────────┐
                    │  调度智能体   │               │
                    └──────┬───────┘               │
                           │ route_next()          │
        ┌──────────┬───────┼────────┬──────────┐   │
        ▼          ▼       ▼        ▼          ▼   │
     vision     forum    web    compose    evaluate│
   多模态理解  论坛检索  联网搜索  答案合成   质量评估 │
        │          │       │        │          │   │
        └──────────┴───────┴────────┴──────────┘   │
                           │                        │
                           └── rewrite（重写/补联网）┘
                                    │
                                    ▼
                                   END

与旧版单智能体工作流的区别：
- 旧版是"一条固定流水线"，节点顺序写死；
- 新版由 **调度智能体动态编排**：先规划、再按上游结论自适应调整
  （论坛不足→联网、评估不过→补搜或重写），每个智能体职责单一、可独立观测。

**关于 prepare 节点**：图带 checkpointer，``messages`` 会按会话累积（多轮对话靠它），
但 ``plan`` / ``agent_status`` / ``citations`` 这些**单轮字段**如果不清零，
第二轮会看到"计划里所有步骤都已完成"从而直接结束 —— 表现为用户追问时
原样返回上一轮的答案。所以每轮都先过 prepare 清场。
"""
from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uuid
import time
from typing import Any, Dict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph

from agent.composer import composer_node
from agent.evaluator import evaluator_node
from agent.forum_agent import forum_agent_node
from agent.state import BotState
from agent.supervisor import rewrite_node, route_after_agent, route_next, supervisor_node
from agent.vision_agent import vision_agent_node
from agent.web_agent import web_agent_node
from utils.config import CONFIG
from utils.log_utils import log

# 每个进程一个内存检查点（多轮会话靠 thread_id 区分）
_CHECKPOINTER = InMemorySaver()
_COMPILED = None


def prepare_node(state: BotState) -> Dict[str, Any]:
    """每轮问答的入口节点：把**单轮字段**清零，保留会话级字段。

    列表类字段返回 ``None`` 即表示重置（见 :mod:`agent.state` 的 ``_add_list``）；
    ``agent_status`` 同理（``_merge_dicts`` 收到 ``None`` 会清空）。
    ``messages`` 不动，多轮上下文照旧累积。
    """
    return {
        # 调度
        "plan": None,
        "agent_status": None,
        "trace": None,
        "handoffs": 0,
        # 多模态
        "vision_note": "",
        "image_kb_hits": None,
        # 论坛检索
        "forum_queries": None,
        "forum_hits": None,
        "forum_relevance": 0.0,
        "forum_sufficient": False,
        "forum_reason": "",
        "memory_hits": None,
        # 联网
        "web_queries": None,
        "web_results": None,
        "web_used": False,
        "force_web": False,
        # 输出
        "draft_answer": "",
        "answer": "",
        "answer_score": 0.0,
        "evaluate_reason": "",
        "citations": None,
        "images": None,
        "used_web_search": False,
        "need_rewrite": False,
        "web_needed_by_evaluator": False,
        "rewrite_count": 0,
        "error": None,
        "started_at": time.time(),
    }


def build_agent_graph(enable_evaluator: bool = True):
    """构建并编译多智能体图。"""
    builder = StateGraph(BotState)

    # ---- 节点（每个节点就是一个智能体）----
    builder.add_node("prepare", prepare_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("vision", vision_agent_node)
    builder.add_node("forum", forum_agent_node)
    builder.add_node("web", web_agent_node)
    builder.add_node("compose", composer_node)
    builder.add_node("evaluate", evaluator_node)
    builder.add_node("rewrite", rewrite_node)

    # ---- 入口：先清场，再交给调度智能体 ----
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "supervisor")

    # ---- 调度智能体动态派发 ----
    routing_map = {
        "vision": "vision",
        "forum": "forum",
        "web": "web",
        "compose": "compose",
        "evaluate": "evaluate",
        "rewrite": "rewrite",
        "__end__": END,
    }
    if not enable_evaluator:
        # 关闭评估时，把 evaluate 也当成终点，避免空转
        routing_map["evaluate"] = END
    builder.add_conditional_edges("supervisor", route_next, routing_map)

    # ---- 每个智能体执行完，由 route_after_agent 决定回调度台 / 重写 / 结束 ----
    after_map = {
        "supervisor": "supervisor",
        "rewrite": "rewrite",
        "__end__": END,
    }
    for name in ("vision", "forum", "web", "compose", "evaluate", "rewrite"):
        builder.add_conditional_edges(name, route_after_agent, after_map)

    return builder.compile(checkpointer=_CHECKPOINTER)


def get_agent_graph():
    """进程内单例（编译一次，多请求复用）。"""
    global _COMPILED
    if _COMPILED is None:
        enable_evaluator = CONFIG.get("agent.enable_evaluator", True)
        log.info(f"[agent] 构建多智能体图（质量评估={'开启' if enable_evaluator else '关闭'}）")
        _COMPILED = build_agent_graph(enable_evaluator=enable_evaluator)
    return _COMPILED


def build_session(user: str = None, session_id: str = None) -> tuple:
    """返回 ``(graph, config)``，config 中带用户与会话标识。"""
    graph = get_agent_graph()
    config = {
        "configurable": {
            "thread_id": session_id or str(uuid.uuid4()),
            "user_name": user or CONFIG.get("workflow.user_name", "guest"),
        }
    }
    return graph, config


def draw_graph(path: str = None) -> str:
    """把图渲染成 Mermaid PNG（便于文档展示）。"""
    graph = get_agent_graph()
    path = path or os.path.join(PROJECT_ROOT, "项目文档", "agent_graph.png")
    png = graph.get_graph().draw_mermaid_png()
    with open(path, "wb") as f:
        f.write(png)
    return path


__all__ = ["build_agent_graph", "get_agent_graph", "build_session", "draw_graph", "prepare_node"]


if __name__ == "__main__":
    print(draw_graph())
