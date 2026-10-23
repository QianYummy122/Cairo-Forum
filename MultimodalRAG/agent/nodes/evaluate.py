"""质量评估智能体：回答发出前的最后一道闸门。

两层评估，兼顾"准"和"稳"：
1. **规则层**（零成本）：来源是否标注、是否出现"材料/上下文"这类内部词汇、
   回答长度是否异常、论坛没命中却声称"论坛里有"……
2. **模型层**：让评估模型判断"切题 / 有据 / 完整"，并给出 ``need_web`` 建议。

评估不通过时，若联网搜索还没用过且用户开启了开关，就回到联网搜索智能体补资料；
否则让合成智能体重写一次（最多一次，避免死循环）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from agent.events import agent_done, trace_entry
from agent.llm_utils import ask_json
from agent.prompts import EVALUATOR_PROMPT, FORUM_NAME
from agent.state import BotState
from utils.config import CONFIG
from utils.log_utils import log

# 不该出现在用户可见回答里的"内部词汇"
_INTERNAL_WORDS = ["材料", "上下文", "片段", "检索结果", "知识库命中", "网页N"]


def _rule_check(state: BotState, answer: str) -> Dict[str, Any]:
    """零成本规则检查，返回扣分项。"""
    problems: List[str] = []

    if len(answer) < 30:
        problems.append("回答过短，可能没有真正作答")
    if any(word in answer for word in _INTERNAL_WORDS):
        problems.append("回答里出现了'材料/上下文'等内部词汇")
    if re.search(r"\{\s*\"?(score|sufficient|plan)\"?\s*:", answer):
        problems.append("回答里混入了 JSON 结构")

    has_forum = bool(state.get("forum_hits"))
    has_web = bool(state.get("web_results"))
    # 论坛没命中、也没联网，回答里不该声称"论坛里有"
    if not has_forum and not has_web:
        if re.search(rf"{FORUM_NAME}(里|中)?(有|存在)(相关)?(文章|内容|帖子)", answer):
            problems.append("论坛并无命中，回答却声称站内有相关内容")

    # 用了联网搜索结果，最好明确说明
    if has_web and not re.search(r"(联网|网络|网上|互联网|搜索)", answer):
        problems.append("使用了联网搜索结果但未说明来源")

    return {"problems": problems, "penalty": min(0.15 * len(problems), 0.6)}


def _model_check(state: BotState, answer: str) -> Dict[str, Any]:
    """让评估模型打分。

    **必须把材料原文一起给它**：评估要判的是"结论有没有依据"，
    如果只告诉它"论坛命中 5 条"，它无法核对回答里的标签名、链接、数字，
    就会把正确答案误判成"疑似编造"，进而触发没必要的重写（白等十几秒 + 多花 token）。
    所以这里把命中片段与联网材料各截一段真实内容附上。

    同理，``forum_sufficient`` 的判定结论也要一并告知：论坛"命中了 5 条但不足以回答"时，
    回答里写"站内没有相关内容"是**正确**的，不告诉它这一点它就会判成自相矛盾。
    """
    lines: List[str] = []

    # 论坛检索的结论（含判定理由）
    forum_hits = state.get("forum_hits") or []
    sufficient = bool(state.get("forum_sufficient"))
    lines.append(
        f"论坛知识库：命中 {len(forum_hits)} 条，检索智能体判定为"
        f"「{'内容足够回答' if sufficient else '不足以回答'}」"
    )
    if state.get("forum_reason"):
        lines.append(f"判定理由：{state['forum_reason']}")
    if not sufficient and forum_hits:
        lines.append("注意：判定为「不足以回答」时，回答里说“站内没有相关内容”是**正确**的表述，"
                     "不算与命中条数矛盾。")

    # 论坛命中原文（截断）。**要和合成智能体看到的一样多**：
    # 合成智能体用的是 ``retrieval.agent_top_k`` 条命中，如果这里只给它看前 4 条，
    # 回答里合法引用了第 5 条时就会被误判成"凭空编造"。
    # 另外必须带上 sourceUrl —— 回答里的引用链接（如 /label/11）直接来自它。
    max_hits = max(int(CONFIG.get("retrieval.agent_top_k", 5)), 5)
    for index, hit in enumerate(forum_hits[:max_hits], 1):
        text = (hit.get("text") or "").replace("\n", " ")[:220]
        url = hit.get("sourceUrl") or ""
        lines.append(
            f"[论坛片段{index}] {hit.get('sourceLabel')}《{hit.get('title')}》"
            + (f"（站内路径 {url}）" if url else "")
            + f"：{text}"
        )

    # 联网材料（截断）
    web_results = state.get("web_results") or []
    if web_results:
        lines.append(f"联网搜索：{len(web_results)} 组整理结果")
        for item in web_results[:1]:
            lines.append("[联网材料] " + (item.get("snippet") or "").replace("\n", " ")[:600])
    else:
        lines.append("联网搜索：0 组")

    if state.get("vision_note"):
        lines.append("图片理解结论：" + state["vision_note"].replace("\n", " ")[:400])

    verdict = ask_json(
        EVALUATOR_PROMPT,
        f"用户问题：{state.get('question') or '（图片提问）'}\n"
        f"是否开启联网搜索：{'是' if state.get('web_search_enabled') else '否'}\n\n"
        f"可用材料：\n" + "\n".join(lines) + "\n\n"
        f"待评估的回答：\n{answer}",
    )
    if isinstance(verdict, dict) and "score" in verdict:
        return {
            "score": float(verdict.get("score") or 0.0),
            "reason": str(verdict.get("reason") or "").strip(),
            "need_web": bool(verdict.get("need_web")),
            "source": "model",
        }
    return {"score": 0.0, "reason": "", "need_web": False, "source": "none"}


def evaluate_node(state: BotState) -> Dict[str, Any]:
    """质量评估智能体节点。"""
    answer = state.get("answer") or state.get("draft_answer") or ""
    threshold = CONFIG.get("agent.answer_score_threshold", 0.55)
    enabled = CONFIG.get("agent.enable_evaluator", True)

    if not enabled:
        agent_done("evaluate", "质量评估已关闭")
        return {
            "answer_score": 1.0,
            "agent_status": {"evaluate": "skipped"},
            "trace": [trace_entry("evaluate", "skip", "配置中已关闭质量评估")],
        }

    rules = _rule_check(state, answer)
    model = _model_check(state, answer)

    # 规则层与模型层共同决定最终分数
    score = max(0.0, model["score"] - rules["penalty"])
    if model["source"] == "none":
        # 模型评分不可用 → 有硬伤就判不通过，否则放行
        score = 0.2 if rules["problems"] else 1.0

    reasons = [r for r in [model.get("reason")] if r] + rules["problems"]
    reason = "；".join(reasons) or "回答质量正常"
    passed = score >= threshold

    # 是否需要联网兜底：模型建议联网 或 论坛没命中但用户开了联网
    need_web = bool(model.get("need_web"))
    if not state.get("web_used") and state.get("web_search_enabled") and not state.get("forum_sufficient"):
        need_web = True

    detail = f"评分 {score:.2f}（阈值 {threshold}）→ {'通过' if passed else '需改进'}：{reason}"
    agent_done("evaluate", detail, {"score": round(score, 4), "pass": passed})

    update: Dict[str, Any] = {
        "answer_score": round(score, 4),
        "evaluate_reason": reason,
        "agent_status": {"evaluate": "done"},
        "trace": [trace_entry("evaluate", "score", detail,
                              score=round(score, 4), pass_=passed, needWeb=need_web)],
    }
    if not passed:
        update["need_rewrite"] = True
    else:
        update["need_rewrite"] = False
    # 把"建议联网"的意图交给 supervisor 处理
    update["web_needed_by_evaluator"] = need_web
    return update


__all__ = ["evaluate_node"]
