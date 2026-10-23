"""prepare 节点：每轮问答的入口，把**单轮字段**清零、保留会话级字段。

为什么必须有它：图带 checkpointer，``messages`` 会按 ``thread_id`` 累积（多轮对话靠它），
但 ``plan`` / ``agent_status`` / ``citations`` 这些**单轮字段**如果不清零，第二轮会看到
"计划里所有步骤都已完成"从而直接结束 —— 表现为用户追问时原样返回上一轮的答案。

列表类字段返回 ``None`` 即表示重置（见 :mod:`agent.state` 的 ``_add_list``）；
``agent_status`` 同理（``_merge_dicts`` 收到 ``None`` 会清空）。
``messages`` 不动，多轮上下文照旧累积。
"""
from __future__ import annotations

import time
from typing import Any, Dict

from agent.state import BotState


def prepare_node(state: BotState) -> Dict[str, Any]:
    """每轮问答的入口节点：清空上一轮遗留的调度状态。"""
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


__all__ = ["prepare_node"]
