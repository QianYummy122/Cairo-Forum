"""调度智能体（Supervisor）：小罗Bot 多智能体架构的"大脑"。

它做两件事：

1. **规划（LLM）**：把用户问题变成一份执行计划，例如
   ``["vision", "forum", "web", "compose"]``；
2. **路由（规则 + 自适应）**：按计划把控制权交给下一个智能体，并根据上游结论
   动态调整计划 —— 例如"论坛内容不足 + 用户开了联网"就插入 ``web``，
   "评估不通过"就再补一次 ``web`` 或回到 ``compose`` 重写。

之所以"LLM 规划 + 规则路由"混合：计划让协作过程可解释、可展示，
规则路由保证不会因为模型的一次误判而漏掉关键步骤（例如忘了联网兜底），
同时天然带次数上限，不会出现智能体互相踢皮球死循环。
"""
from __future__ import annotations

from typing import Any, Dict, List

from agent.events import agent_done, agent_start, emit, trace_entry
from agent.llm_utils import ask_json
from agent.prompts import SUPERVISOR_PLAN_PROMPT
from agent.state import BotState
from utils.config import CONFIG
from utils.log_utils import log

# 计划中允许出现的智能体与规范顺序
_VALID_AGENTS = ["vision", "forum", "web", "compose"]
_ORDER = {name: index for index, name in enumerate(_VALID_AGENTS)}


def _normalize_plan(raw: Any, state: BotState) -> List[str]:
    """把模型给的计划规整成合法、有序、不重复的计划。"""
    plan: List[str] = []
    if isinstance(raw, dict):
        raw = raw.get("plan")
    if isinstance(raw, list):
        for item in raw:
            name = str(item).strip().lower()
            if name in _VALID_AGENTS and name not in plan:
                plan.append(name)
    if not plan:
        plan = _default_plan(state)
    # 规范化顺序
    plan.sort(key=lambda n: _ORDER.get(n, 99))
    # compose 必须存在且放最后
    if "compose" in plan:
        plan.remove("compose")
    plan.append("compose")
    # 图片步骤只在真的有图片时保留
    if "vision" in plan and not state.get("image"):
        plan.remove("vision")
    return plan


def _default_plan(state: BotState) -> List[str]:
    """模型不可用时的默认计划。"""
    plan: List[str] = []
    if state.get("image"):
        plan.append("vision")
    plan.append("forum")
    if state.get("web_search_enabled"):
        plan.append("web")
    return plan


def supervisor_node(state: BotState) -> Dict[str, Any]:
    """调度智能体节点：生成本轮执行计划。

    规划只做一次。后续每次回到调度智能体时直接沿用已有计划，
    由 :func:`route_next` 依据各智能体的最新结论决定下一步 ——
    这样既保留了"LLM 规划"的可解释性，又不会为每一步都付一次规划调用。
    """
    existing_plan = list(state.get("plan") or [])
    already_planned = (state.get("agent_status") or {}).get("supervisor") == "done"

    question = state.get("question") or ""
    enabled_web = bool(state.get("web_search_enabled"))
    has_image = bool(state.get("image"))

    if already_planned and existing_plan:
        # 沿用计划：不再调用大模型，只累加交接次数（防死循环）
        return {
            "handoffs": int(state.get("handoffs") or 0) + 1,
            "trace": [trace_entry("supervisor", "dispatch",
                                  f"沿用计划：{' → '.join(existing_plan)}")],
        }

    agent_start("supervisor", "正在分析问题并安排智能体分工")

    hints = [
        f"用户问题：{question or '（只上传了图片）'}",
        f"用户上传了图片：{'是' if has_image else '否'}",
        f"用户开启了联网搜索：{'是' if enabled_web else '否'}",
    ]
    raw = ask_json(SUPERVISOR_PLAN_PROMPT, "\n".join(hints))
    plan = _normalize_plan(raw, state)
    reason = ""
    if isinstance(raw, dict):
        reason = str(raw.get("reason") or "").strip()

    # ---- 自适应：评估智能体已经指出"缺外部信息" → 计划里补上 web ----
    if state.get("web_needed_by_evaluator") and enabled_web and "web" not in plan:
        plan.insert(len(plan) - 1, "web")
        reason = (reason + "；" if reason else "") + "质量评估建议补充联网搜索"

    detail = f"计划：{' → '.join(plan)}" + (f"（{reason}）" if reason else "")
    agent_done("supervisor", detail)
    emit("plan", {"plan": plan, "reason": reason})

    return {
        "plan": plan,
        "handoffs": int(state.get("handoffs") or 0) + 1,
        "agent_status": {"supervisor": "done"},
        "trace": [trace_entry("supervisor", "plan", detail, plan=plan)],
    }


def _rewrite_available(state: BotState) -> bool:
    """评估不通过时，还有没有"补救"的余地？

    两条补救路径，都有明确上限，避免智能体互相踢皮球：
    1. 补一次联网搜索 —— 仅当用户开了联网、还没搜过、且没超过搜索次数上限；
    2. 让答案合成智能体重写 —— 只允许一次。
    """
    web_available = (
        bool(state.get("web_search_enabled"))
        and not state.get("web_used")
        and int(len(state.get("web_queries") or [])) < CONFIG.get("agent.max_web_queries", 2)
    )
    if web_available:
        return True
    return int(state.get("rewrite_count") or 0) < 1


def route_next(state: BotState) -> str:
    """调度智能体的路由函数：决定下一个该谁上场（或结束）。

    返回 ``__end__`` 时图结束；返回 ``rewrite`` 时进入重写准备节点。
    """
    plan = list(state.get("plan") or [])
    if not plan:
        return "compose"

    status = state.get("agent_status") or {}
    max_handoffs = CONFIG.get("agent.max_handoffs", 6)

    # 防死循环：交接次数过多直接收尾
    if int(state.get("handoffs") or 0) > max_handoffs:
        log.warning("[supervisor] 超过最大交接次数，直接结束")
        return "__end__"

    # 1) 计划里还没做的步骤，按顺序执行
    for name in plan:
        if status.get(name) in (None, "", "pending"):
            if name == "web" and not state.get("web_search_enabled"):
                continue  # 未开启联网，跳过该步骤
            return name

    # 2) 计划已执行完 → 进入质量评估（若启用）
    if CONFIG.get("agent.enable_evaluator", True) and status.get("evaluate") in (None, "", "pending"):
        return "evaluate"

    # 3) 评估不通过 → 在补救预算内补联网或重写一次
    if state.get("need_rewrite"):
        if _rewrite_available(state):
            return "rewrite"
        log.info("[supervisor] 补救预算已用尽，按现有结果输出")

    return "__end__"


def route_after_agent(state: BotState) -> str:
    """每个智能体执行完之后的路由：回调度台 / 去重写 / 直接结束。

    存在的意义是"收尾不再多问一次大模型"：计划里所有步骤都做完、
    质量评估也通过时，直接结束，省掉一次没有信息增量的规划调用。

    注意：重写分支必须和 :func:`route_next` 用同一个预算判断
    （``_rewrite_available``）。否则评估连续判不通过时会绕开预算反复重写 ——
    表现为一次提问里答案合成智能体被调用三四次，又慢又费 token。
    """
    if state.get("need_rewrite") and _rewrite_available(state):
        return "rewrite"

    plan = list(state.get("plan") or [])
    status = state.get("agent_status") or {}
    evaluate_enabled = CONFIG.get("agent.enable_evaluator", True)

    steps_done = all(status.get(name) in ("done", "skipped") for name in plan) if plan else True
    evaluate_done = (not evaluate_enabled) or status.get("evaluate") in ("done", "skipped")

    if steps_done and evaluate_done and not state.get("need_rewrite"):
        return "__end__"
    return "supervisor"


def rewrite_node(state: BotState) -> Dict[str, Any]:
    """重写准备节点：决定"补联网"还是"重写"，并把对应步骤重置为待执行。

    LangGraph 的节点不能反向修改已完成的步骤，所以单独用一个节点来
    "撤销"已完成标记（``pending``）、清零 ``need_rewrite``、累加 ``rewrite_count``，
    再交回 supervisor 重新路由。这样既有自适应的重试，又不会死循环。
    """
    status = dict(state.get("agent_status") or {})
    rewrite_count = int(state.get("rewrite_count") or 0)

    web_available = (
        bool(state.get("web_search_enabled"))
        and not state.get("web_used")
        and int(len(state.get("web_queries") or [])) < CONFIG.get("agent.max_web_queries", 2)
    )
    if web_available:
        action = "补充联网搜索"
        status["web"] = "pending"
        status["evaluate"] = "pending"
        plan = list(state.get("plan") or [])
        if "web" not in plan:
            plan.insert(max(len(plan) - 1, 0), "web")
        detail = f"质量评估未通过（{state.get('evaluate_reason') or '需要外部信息'}），改为补一次联网搜索"
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

    log.info(f"[supervisor] {action}")
    emit("plan", {"plan": list(update.get("plan") or state.get("plan") or []),
                  "reason": detail})
    return update


__all__ = ["supervisor_node", "route_next", "route_after_agent", "rewrite_node",
           "_normalize_plan", "_rewrite_available"]
