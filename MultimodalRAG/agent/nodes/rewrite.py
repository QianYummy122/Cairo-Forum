"""rewrite 节点：补救准备，决定"补联网"还是"重写"，并把对应步骤置回待执行。

它**不是智能体**：不产出内容、没有提示词、不调用大模型，只修改调度字段
（``plan`` / ``agent_status`` / ``need_rewrite`` / ``rewrite_count``）。
轨迹仍记在 ``supervisor`` 名下，因为前端"思考过程"里没有独立的"重写"角色。

为什么需要单独一个节点：LangGraph 的节点不能反向修改"已完成"的步骤，所以要有一个
节点专门去"撤销"已完成标记（改回 ``pending``）、清零 ``need_rewrite``、累加
``rewrite_count``，再交回 supervisor 重新路由。这样既有自适应的重试，又不会死循环。

预算判断必须复用 :func:`agent.routing._web_available` —— 它和
:func:`agent.routing.route_next` / :func:`agent.routing.route_after_agent` 是同一套规则，
各算各的就会出现"路由放行、节点拒绝"的分裂。
"""
from __future__ import annotations

from typing import Any, Dict

from agent.events import emit, trace_entry
from agent.routing import _web_available
from agent.state import BotState
from utils.log_utils import log


def rewrite_node(state: BotState) -> Dict[str, Any]:
    """补救准备节点：把要重做的步骤重置为 ``pending``，并清零 ``need_rewrite``。"""
    status = dict(state.get("agent_status") or {})
    rewrite_count = int(state.get("rewrite_count") or 0)

    if _web_available(state):
        action = "补充联网搜索"
        status["web"] = "pending"
        # 补搜会带来新材料，答案必须重新合成 —— 只重置 web/evaluate 的话，
        # 评估打分的还是补搜之前那条旧答案，这次搜索就白花了。
        status["compose"] = "pending"
        status["evaluate"] = "pending"
        plan = list(state.get("plan") or [])
        if "web" not in plan:
            plan.insert(max(len(plan) - 1, 0), "web")
        detail = f"质量评估未通过（{state.get('evaluate_reason') or '需要外部信息'}），改为补充联网搜索后重写回答"
        update: Dict[str, Any] = {
            "agent_status": status,
            "plan": plan,
            "need_rewrite": False,
            "force_web": True,
            "web_needed_by_evaluator": False,
            "trace": [trace_entry("supervisor", "replan", detail)],
        }
    else:
        action = "重写回答"
        status["compose"] = "pending"
        status["evaluate"] = "pending"
        rewrite_count += 1
        detail = f"质量评估未通过（{state.get('evaluate_reason') or '不够切题'}），让答案合成智能体重写一次"
        update = {
            "agent_status": status,
            "need_rewrite": False,
            "rewrite_count": rewrite_count,
            "trace": [trace_entry("supervisor", "rewrite", detail)],
        }

    log.info(f"[rewrite] {action}")
    emit("plan", {"plan": list(update.get("plan") or state.get("plan") or []),
                  "reason": detail})
    return update


__all__ = ["rewrite_node"]
