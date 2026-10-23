"""条件边（routing）：决定"下一个该谁上场"以及"补救预算还剩多少"。

这些函数**不是图上的节点**，而是节点之间连线上的判定逻辑（LangGraph 的 conditional
edge）。它们都不调用大模型、不需要提示词，只读 ``BotState`` 和配置：

- :func:`route_next` —— ``supervisor`` 之后：按计划派活 / 进质量评估 / 进补救 / 结束；
- :func:`route_after_agent` —— 每个智能体之后：回调度台 / 去补救 / 直接结束；
- :func:`_web_available` / :func:`_rewrite_available` —— 补救预算判定。

**为什么预算判定放在这里、而不是各节点自己算**：``route_next``、``route_after_agent``
和 :func:`agent.nodes.rewrite.rewrite_node` 必须用同一套判断，否则会出现"路由说预算还在、
节点说预算没了"的分裂（历史上就因为同一个表达式抄了两份，其中一份永远为真）。
"""
from __future__ import annotations

from agent.state import BotState
from utils.config import CONFIG
from utils.log_utils import log


def _web_available(state: BotState) -> bool:
    """本轮还能不能（再）联网搜索一次？

    三个条件同时成立才可以：

    1. 用户开了联网；
    2. 搜索词额度没用完 —— 预算就是 ``agent.max_web_queries``，
       按"已经实际执行过的查询条数"扣减（:mod:`agent.nodes.web` 每执行一条查询
       就往 ``web_queries`` 里追加一条）；
    3. 质量评估认为这份回答的短板是**缺外部信息**（``web_needed_by_evaluator``，
       正是评估提示词里 ``need_web`` 的定义）。没有这条，一个只是"没写来源"
       的回答也会去补搜一次，白花一次搜索 + 一次合成。

    注意这里**不能**再叠加 ``not web_used``：那个字段的语义是"本轮到底用没用过网"
    （质量评估和前端展示都依赖它），一次"搜了但没结果"的失败尝试同样会把它置真。
    拿它当预算门，就等于"联网最多进一次"，第一次空手而归后就再也没有换词重搜的机会，
    ``nodes/web.py`` 里 ``limit - already`` 的额度扣减也随之变成死代码。
    """
    if not state.get("web_search_enabled"):
        return False
    if not state.get("web_needed_by_evaluator"):
        return False
    used = int(len(state.get("web_queries") or []))
    limit = int(CONFIG.get("agent.max_web_queries", 2) or 0)
    return used < limit


def _rewrite_available(state: BotState) -> bool:
    """评估不通过时，还有没有"补救"的余地？

    两条补救路径，都有明确上限，避免智能体互相踢皮球：
    1. 补联网搜索 —— 用户开了联网 + 评估指出缺外部信息 + 搜索词额度没用完（默认 2 条）；
    2. 让答案合成智能体重写 —— 只允许一次。
    """
    if _web_available(state):
        return True
    return int(state.get("rewrite_count") or 0) < 1


def route_next(state: BotState) -> str:
    """调度路由：决定下一个该谁上场（或结束）。

    返回 ``__end__`` 时图结束；返回 ``rewrite`` 时进入补救准备节点。
    """
    plan = list(state.get("plan") or [])
    if not plan:
        return "compose"

    status = state.get("agent_status") or {}
    max_handoffs = CONFIG.get("agent.max_handoffs", 6)

    # 防死循环：交接次数过多直接收尾
    if int(state.get("handoffs") or 0) > max_handoffs:
        log.warning("[routing] 超过最大交接次数，直接结束")
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
        log.info("[routing] 补救预算已用尽，按现有结果输出")

    return "__end__"


def route_after_agent(state: BotState) -> str:
    """每个智能体执行完之后的路由：回调度台 / 去补救 / 直接结束。

    存在的意义是"收尾不再多问一次大模型"：计划里所有步骤都做完、
    质量评估也通过时，直接结束，省掉一次没有信息增量的规划调用。

    注意：补救分支必须和 :func:`route_next` 用同一个预算判断
    （``_rewrite_available``）。否则评估连续判不通过时会绕开预算反复重写 ——
    表现为一次提问里答案合成智能体被调用三四次，又慢又费 token。
    """
    if state.get("need_rewrite") and _rewrite_available(state):
        return "rewrite"

    # 评估不通过但补救预算已用尽：直接收尾，省掉一次没有信息增量的调度
    # （否则还要多绕一次 supervisor 才由 route_next 走到同一个 __end__）。
    if state.get("need_rewrite"):
        log.info("[routing] 补救预算已用尽，按现有结果输出")
        return "__end__"

    plan = list(state.get("plan") or [])
    status = state.get("agent_status") or {}
    evaluate_enabled = CONFIG.get("agent.enable_evaluator", True)

    steps_done = all(status.get(name) in ("done", "skipped") for name in plan) if plan else True
    evaluate_done = (not evaluate_enabled) or status.get("evaluate") in ("done", "skipped")

    if steps_done and evaluate_done and not state.get("need_rewrite"):
        return "__end__"
    return "supervisor"


__all__ = ["route_next", "route_after_agent", "_rewrite_available", "_web_available"]
