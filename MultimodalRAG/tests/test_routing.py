"""routing 路由 / 联网预算的回归测试。

不需要大模型、向量库或网络：把 ``agent/__init__.py``（会拉起 graph、session、milvus）、
``agent.llm_utils``、``agent.nodes.forum``（会拉起 Milvus 检索器）和 ``my_llm``
换成桩，只驱动 :mod:`agent.routing` 的条件边 + :mod:`agent.nodes.rewrite` 的补救节点
（外加 :mod:`agent.nodes.supervisor` 的规划节点，用桩代替大模型返回）。

覆盖的行为（都是曾经出过问题或容易被改坏的地方）：

- 联网预算按"实际执行过的搜索词条数"扣减，而不是 ``web_used`` 布尔量 ——
  否则一次"搜了但没结果"就把预算永久用光（见 ``agent.routing._web_available``）；
- 补搜之后必须重新合成答案，否则评估打分的还是补搜前的旧答案；
- 只有"评估指出缺外部信息"时才补搜，纯文风问题直接重写，不浪费搜索；
- 各种最坏路径都能收敛，且不会撞上 ``agent.max_handoffs``。

运行::

    .venv\\Scripts\\python.exe tests\\test_routing.py
    # 装了 pytest 也可以：pytest tests/test_routing.py
"""
from __future__ import annotations

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _install_stubs() -> None:
    """在导入 agent 子模块之前装好桩，避免拉起真实的大模型客户端与向量库。"""
    pkg = types.ModuleType("agent")
    pkg.__path__ = [os.path.join(ROOT, "agent")]
    sys.modules["agent"] = pkg

    llm_utils = types.ModuleType("agent.llm_utils")
    llm_utils.ask_json = lambda *a, **k: {"plan": ["forum", "compose"], "reason": "stub"}
    llm_utils.ask = lambda *a, **k: ""
    llm_utils.history_for_composer = lambda messages, window: []
    sys.modules["agent.llm_utils"] = llm_utils

    # 论坛节点在导入时就会拉起 Milvus 检索器；compose 只需要它的排版函数
    forum_node_mod = types.ModuleType("agent.nodes.forum")
    forum_node_mod.context_block_for_llm = lambda hits: ""
    sys.modules["agent.nodes.forum"] = forum_node_mod

    my_llm = types.ModuleType("my_llm")
    my_llm.llm = types.SimpleNamespace(stream=lambda messages: iter(()))
    my_llm.multiModal_llm = my_llm.llm
    my_llm.embedding = None
    my_llm.zhipuai_client = types.SimpleNamespace()
    sys.modules["my_llm"] = my_llm


_install_stubs()

from agent import routing as rt  # noqa: E402
from agent.nodes import compose as compose_mod  # noqa: E402
from agent.nodes import rewrite as rewrite_node_mod  # noqa: E402
from agent.nodes import supervisor as sup  # noqa: E402
from utils.config import CONFIG  # noqa: E402

LIMIT = int(CONFIG.get("agent.max_web_queries", 2))
MAX_HANDOFFS = int(CONFIG.get("agent.max_handoffs", 6))

# 列表类字段：模拟 LangGraph 的 _add_list reducer（累加，None 表示清零）
LIST_FIELDS = {"web_queries", "web_results", "citations", "trace", "forum_queries",
               "forum_hits", "images", "image_kb_hits", "memory_hits"}


def _defaults() -> dict:
    return {
        "question": "Flink 有界流和无界流有什么区别",
        "web_search_enabled": True,
        "image": None,
        "plan": [],
        "agent_status": {},
        "trace": [],
        "handoffs": 0,
        "web_queries": [],
        "web_results": [],
        "web_used": False,
        "force_web": False,
        "rewrite_count": 0,
        "need_rewrite": False,
        "web_needed_by_evaluator": False,
        "evaluate_reason": "",
        "forum_sufficient": False,
        "citations": [],
        "answer": "",
    }


def _merge(state: dict, update: dict) -> None:
    """模拟 LangGraph 的 reducer 语义（``_add_list`` / ``_merge_dicts``）。"""
    for key, value in update.items():
        if key in LIST_FIELDS:
            state[key] = [] if value is None else list(state.get(key) or []) + list(value)
        elif key == "agent_status":
            if value is None:
                state[key] = {}
            else:
                merged = dict(state.get(key) or {})
                merged.update(value)
                state[key] = merged
        else:
            state[key] = value


def _drive(plan, queries_per_run, *, image=False, web_enabled=True, need_web=True):
    """按 :func:`agent.graph.build_agent_graph` 的拓扑手工跑一遍单轮问答。

    真实的 web/compose/evaluate 节点用等价的桩替代：web 照真实实现那样把执行过的
    查询追加进 ``web_queries`` 并置 ``web_used=True``；evaluate 永远判不合格。
    """
    sup.ask_json = lambda *a, **k: {"plan": list(plan), "reason": "stub"}

    state = _defaults()
    state["web_search_enabled"] = web_enabled
    if image:
        state["image"] = "data:image/png;base64,iVBORw0KGgo="
    _merge(state, sup.supervisor_node(state))

    seq, composes, web_runs = [], 0, 0
    for _ in range(80):
        nxt = rt.route_next(state)
        if nxt == "__end__":
            return seq, state, web_runs, composes
        seq.append(nxt)

        if nxt == "web":
            web_runs += 1
            already = len(state["web_queries"])
            assert already < LIMIT, f"预算已用尽却仍被派给联网（已用 {already} 条）"
            take = min(queries_per_run(state), LIMIT - already)
            _merge(state, {
                "web_queries": [f"q{already + i}" for i in range(take)],
                "web_used": True,
                "agent_status": {"web": "done"},
            })
        elif nxt == "compose":
            composes += 1
            _merge(state, {"agent_status": {"compose": "done"}, "answer": f"答案v{composes}"})
        elif nxt == "evaluate":
            _merge(state, {
                "agent_status": {"evaluate": "done"},
                "need_rewrite": True,
                "web_needed_by_evaluator": need_web,
                "evaluate_reason": "缺少外部信息" if need_web else "没写清楚来源",
            })
        elif nxt in ("forum", "vision"):
            _merge(state, {"agent_status": {nxt: "done"}})
        else:  # pragma: no cover - 防拓扑写错
            raise AssertionError(f"未知节点 {nxt}")

        after = rt.route_after_agent(state)
        if after == "__end__":
            return seq, state, web_runs, composes
        if after == "rewrite":
            _merge(state, rewrite_node_mod.rewrite_node(state))
            after = rt.route_after_agent(state)
            if after == "__end__":
                return seq, state, web_runs, composes
        assert after == "supervisor", f"意外的路由 {after}"
        _merge(state, sup.supervisor_node(state))
        assert state["handoffs"] <= MAX_HANDOFFS, (
            f"交接 {state['handoffs']} 次超过 max_handoffs={MAX_HANDOFFS}（最坏路径会提前收尾）"
        )

    raise AssertionError("没有收敛，疑似死循环")


def _assert_recompose_after_web(seq) -> None:
    for index, node in enumerate(seq[:-1]):
        if node == "web":
            assert seq[index + 1] == "compose", (
                f"联网之后没有重新合成答案，新材料进不了回答：{' → '.join(seq)}"
            )


def test_web_available_uses_query_count_not_web_used():
    """核心回归：``web_used`` 是"用过没有"，不是"还能不能再用"。"""
    cases = [
        ({"web_search_enabled": True, "web_needed_by_evaluator": True,
          "web_queries": [], "web_used": False}, True, "首次联网"),
        ({"web_search_enabled": True, "web_needed_by_evaluator": True,
          "web_queries": ["a"], "web_used": True}, True,
         "搜过 1 条、额度还剩 → 必须允许换词重搜"),
        ({"web_search_enabled": True, "web_needed_by_evaluator": True,
          "web_queries": ["a", "b"], "web_used": True}, False, "额度用完"),
        ({"web_search_enabled": True, "web_needed_by_evaluator": False,
          "web_queries": [], "web_used": False}, False, "评估没要外部信息"),
        ({"web_search_enabled": False, "web_needed_by_evaluator": True,
          "web_queries": [], "web_used": False}, False, "用户没开联网"),
    ]
    for state, expected, label in cases:
        assert rt._web_available(state) is expected, f"_web_available 判断错误：{label}"


def test_failed_search_retries_with_new_query_and_recomposes():
    """首轮只搜 1 条 -> 评估要外部信息 -> 换词再搜 1 条，每轮都重新合成。"""
    seq, state, web_runs, composes = _drive(
        ["forum", "compose"], queries_per_run=lambda s: 1)

    assert web_runs == LIMIT, f"应当补搜到额度用完，实际联网 {web_runs} 次"
    assert len(state["web_queries"]) == LIMIT
    assert len(set(state["web_queries"])) == LIMIT, "重搜没有换词"
    assert composes == 4, f"合成 {composes} 次（首答 1 + 两次补搜 2 + 重写 1 = 4）"
    _assert_recompose_after_web(seq)


def test_first_run_can_exhaust_budget():
    """首轮就试了两条词（都没结果）→ 不允许再补搜，只重写一次。"""
    seq, state, web_runs, composes = _drive(
        ["forum", "compose"], queries_per_run=lambda s: 2)

    assert web_runs == 1, f"额度已被首轮吃掉，不应再联网（实际 {web_runs} 次）"
    assert len(state["web_queries"]) == LIMIT
    assert composes == 3, f"合成 {composes} 次（首答 1 + 补搜 1 + 重写 1 = 3）"
    _assert_recompose_after_web(seq)


def test_vision_worst_case_fits_handoff_limit():
    seq, state, web_runs, composes = _drive(
        ["vision", "forum", "web", "compose"],
        queries_per_run=lambda s: 1, image=True)

    assert web_runs == LIMIT
    assert composes == 3, f"合成 {composes} 次（首答 1 + 补搜 1 + 重写 1 = 3）"
    assert state["handoffs"] <= MAX_HANDOFFS
    _assert_recompose_after_web(seq)


def test_no_web_when_user_disabled_search():
    seq, state, web_runs, composes = _drive(
        ["forum", "web", "compose"], queries_per_run=lambda s: 1, web_enabled=False)

    assert web_runs == 0 and state["web_queries"] == []
    assert composes == 2, "未开联网时只允许重写一次"


def test_stylistic_failure_does_not_trigger_search():
    """评估只说"没写清楚"、没要外部信息 → 直接重写，不浪费一次搜索。"""
    seq, state, web_runs, composes = _drive(
        ["forum", "compose"], queries_per_run=lambda s: 1, need_web=False)

    assert web_runs == 0, f"不该联网（实际 {web_runs} 次）"
    assert composes == 2, "首答 + 一次重写"
    assert "evaluate" in seq


def test_recompose_receives_previous_critique():
    """补搜后的重写（rewrite_count 还是 0）也要把评估意见带进提示词。"""
    state = _defaults()
    state["evaluate_reason"] = "答案没有引用联网材料"
    prompt = compose_mod._system_prompt(state)
    assert "答案没有引用联网材料" in prompt

    # 首次合成（还没有评估意见）不应带上"上一轮不合格"的补充要求
    fresh = _defaults()
    assert compose_mod._system_prompt(fresh) == compose_mod.COMPOSER_PROMPT


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"[FAIL] {name}: {exc}")
        else:
            print(f"[ok] {name}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
