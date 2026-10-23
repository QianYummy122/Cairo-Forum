"""调度智能体（Supervisor）：把用户问题变成一份执行计划。

它只做**规划**这一件事：问一次大模型"这题该让谁上"，产出 ``plan``，例如
``["vision", "forum", "web", "compose"]``。计划让协作过程可解释、可展示。

"按计划把控制权交给下一个智能体""评估不通过怎么补救"属于**调度策略**，
不调大模型也不需要提示词，因此不在本文件里：条件边在 :mod:`agent.routing`，
补救节点在 :mod:`agent.nodes.rewrite`。

规划只在第一轮做一次：后续每次回到调度台都沿用已有计划，既保留可解释性，
又不会为每一步都付一次规划调用。补救次数由 routing 里的预算规则兜底，
不会出现智能体互相踢皮球死循环。
"""
from __future__ import annotations

from typing import Any, Dict, List

from agent.events import agent_done, agent_start, emit, trace_entry
from agent.llm_utils import ask_json
from agent.prompts import SUPERVISOR_PLAN_PROMPT
from agent.state import BotState

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
    由 :func:`agent.routing.route_next` 依据各智能体的最新结论决定下一步。
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

    # 注意：这里**不能**消费质量评估的结论。规划只在第一轮做一次，
    # 而质量评估在计划执行完之后才跑，所以"评估指出缺外部信息 → 补搜"的
    # 自适应发生在 scheduler.rewrite_node 里。

    detail = f"计划：{' → '.join(plan)}" + (f"（{reason}）" if reason else "")
    agent_done("supervisor", detail)
    emit("plan", {"plan": plan, "reason": reason})

    return {
        "plan": plan,
        "handoffs": int(state.get("handoffs") or 0) + 1,
        "agent_status": {"supervisor": "done"},
        "trace": [trace_entry("supervisor", "plan", detail, plan=plan)],
    }


__all__ = ["supervisor_node", "_normalize_plan", "_default_plan"]
