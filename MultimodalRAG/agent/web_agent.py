"""联网搜索智能体：论坛里查不到时的外部信息通道。

开关语义（对应用户需求"能选择启用联网搜索"）
--------------------------------------------
- 只有 ``state["web_search_enabled"]`` 为真时才会真正联网；
- 关闭时本节点直接"跳过"，并在轨迹里说明原因，
  前端能明确看到"未启用联网搜索"而不是"搜了但没结果"；
- 开启时：先由大模型把问题改写成搜索词 → 智谱 ``web_search`` →
  再由大模型把结果整理成可供合成的材料。
"""
from __future__ import annotations

from typing import Any, Dict, List

from agent.events import agent_done, agent_skip, agent_start, emit, trace_entry
from agent.llm_utils import ask, ask_json
from agent.prompts import FORUM_NAME, WEB_QUERY_PROMPT, WEB_SUMMARY_PROMPT
from agent.state import BotState
from my_llm import zhipuai_client
from utils.config import CONFIG
from utils.log_utils import log


def _rewrite_queries(question: str, vision_note: str = "") -> List[str]:
    """把问题改写成 1~2 条搜索关键词。"""
    seed = f"{question}\n{vision_note[:300]}".strip() if vision_note else question
    planned = ask_json(WEB_QUERY_PROMPT, f"用户问题：{seed}")
    queries: List[str] = []
    if isinstance(planned, list):
        queries = [str(q).strip() for q in planned if str(q).strip()]
    if not queries:
        # 兜底：直接用原问题，并去掉论坛限定词（站内信息网上查不到）
        fallback = question.replace(FORUM_NAME, "").replace("开罗论坛", "").strip()
        queries = [fallback or question]
    return queries[: CONFIG.get("agent.max_web_queries", 2)]


def _search_once(query: str) -> List[Dict[str, Any]]:
    """调用智谱 web_search，返回结构化结果。"""
    try:
        response = zhipuai_client.web_search.web_search(
            search_engine=CONFIG.get("web_search.search_engine", "search_pro"),
            search_query=query,
        )
    except Exception as e:
        log.warning(f"[web] 搜索失败 '{query}'：{e}")
        return []

    results: List[Dict[str, Any]] = []
    max_len = CONFIG.get("web_search.snippet_max_length", 1200)
    for item in (getattr(response, "search_result", None) or [])[: CONFIG.get("web_search.max_results", 8)]:
        title = getattr(item, "title", "") or ""
        link = getattr(item, "link", "") or ""
        content = (getattr(item, "content", "") or "")[:max_len]
        if not content:
            continue
        results.append({
            "title": title,
            "url": link,
            "snippet": content,
            "query": query,
            "site": getattr(item, "media", "") or "",
            "publishDate": str(getattr(item, "publish_date", "") or ""),
        })
    return results


def _summarize(question: str, results: List[Dict[str, Any]]) -> str:
    """把搜索结果整理成材料（带 [网页N] 角标）。"""
    blocks = []
    for index, item in enumerate(results, 1):
        blocks.append(
            f"[网页{index}] 标题：{item['title']}\n"
            f"链接：{item['url']}\n"
            f"摘要：{item['snippet']}"
        )
    material = "\n\n".join(blocks)
    summary = ask(WEB_SUMMARY_PROMPT, f"用户问题：{question}\n\n搜索结果：\n{material}")
    return summary or material


def web_agent_node(state: BotState) -> Dict[str, Any]:
    """联网搜索智能体节点。"""
    question = state.get("question") or ""
    enabled = bool(state.get("web_search_enabled"))
    already = int(len(state.get("web_queries") or []))
    limit = CONFIG.get("agent.max_web_queries", 2)

    # ---------- 开关关闭 ----------
    if not enabled:
        agent_skip("web", "用户未启用联网搜索，跳过")
        return {
            "agent_status": {"web": "skipped"},
            "trace": [trace_entry("web", "skip", "用户未启用联网搜索，论坛内容作为唯一来源")],
        }

    # ---------- 论坛内容已经够用 ----------
    # 联网搜索是"论坛查不到时"的兜底通道（对应用户需求 6），
    # 只有质量评估明确要求补外部信息时才强行联网。
    if state.get("forum_sufficient") and not state.get("force_web"):
        agent_skip("web", "论坛知识库已能回答该问题，无需联网")
        return {
            "agent_status": {"web": "skipped"},
            "trace": [trace_entry("web", "skip", "论坛知识库命中充分，未触发联网兜底")],
        }

    # ---------- 次数用尽 ----------
    if already >= limit:
        agent_skip("web", f"本轮联网检索已达上限 {limit} 次")
        return {
            "agent_status": {"web": "skipped"},
            "trace": [trace_entry("web", "skip", f"联网检索次数已达上限 {limit}")],
        }

    reason = state.get("forum_reason") or state.get("evaluate_reason") or ""
    agent_start("web", f"论坛内容不足，开始联网搜索（{reason}）" if reason else "开始联网搜索")

    # ---------- 1. 改写搜索词 ----------
    queries = _rewrite_queries(question, state.get("vision_note") or "")
    # 若论坛检索式里有非中文关键词，允许把它们并入搜索词提升召回
    log.info(f"[web] 搜索词：{queries}")

    # ---------- 2. 搜索 ----------
    results: List[Dict[str, Any]] = []
    executed: List[str] = []
    for query in queries[: max(1, limit - already)]:
        found = _search_once(query)
        executed.append(query)
        results.extend(found)
        if found:
            break  # 已经有结果就不再继续消耗配额

    if not results:
        detail = "联网搜索没有返回可用结果"
        agent_done("web", detail, {"count": 0})
        return {
            "web_queries": executed,
            "web_used": True,
            "used_web_search": True,
            "agent_status": {"web": "done"},
            "trace": [trace_entry("web", "search", f"搜索词 {executed}；未返回结果")],
        }

    # ---------- 3. 整理材料 ----------
    summary = _summarize(question, results)
    citations = [{
        "type": "web",
        "sourceLabel": "联网搜索",
        "title": item["title"] or item["url"],
        "url": item["url"],
        "site": item.get("site") or "",
        "snippet": item["snippet"][:180],
        "publishDate": item.get("publishDate") or "",
    } for item in results[: CONFIG.get("web_search.max_results", 8)]]

    # 材料存进 web_results 的 text 字段，供合成智能体统一消费
    material = [{
        "title": "联网搜索整理结果",
        "url": results[0]["url"],
        "snippet": summary,
        "query": " / ".join(executed),
    }]

    detail = f"联网搜索到 {len(results)} 条结果（搜索词：{' / '.join(executed)}）"
    agent_done("web", detail, {"count": len(results)})
    emit("sources", {"web": citations})

    return {
        "web_queries": executed,
        "web_results": material,
        "web_used": True,
        "used_web_search": True,
        "citations": citations,
        "agent_status": {"web": "done"},
        "trace": [trace_entry("web", "search", detail)],
    }


__all__ = ["web_agent_node"]
