"""论坛检索智能体：小罗Bot 的多模态 RAG 主力。

职责
----
1. **查询改写**：把口语化的问题改写成 1~3 条检索式（同义词/中英文/子问题）。
2. **多模态检索**：对每一条检索式调用 :class:`KnowledgeRetriever`，
   文本走 BM25+稠密混合检索，图片走稠密检索，图文共用一个向量空间。
3. **去重与排序**：按 ``(sourceType, docId, text)`` 去重，保留分数最高的一批。
4. **可用性判定**：用大模型判断"这些片段到底能不能回答问题"，
   这是 :attr:`BotState.forum_sufficient` 的**主判据**；
   稠密余弦相似度（``forum_relevance``）作为兜底判据。
5. **产出引用**：把命中整理成 ``citations``，供答案合成智能体写"来源说明"。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from agent.events import agent_done, agent_start, emit, trace_entry
from agent.llm_utils import ask_json
from agent.prompts import FORUM_JUDGE_PROMPT, FORUM_QUERY_PROMPT
from agent.state import BotState
from milvus_db.forum_retriever import get_memory_retriever, get_retriever
from utils.config import CONFIG, PROJECT_ROOT
from utils.log_utils import log

# 命中片段带给大模型的最大条数与单条最大长度
_MAX_CONTEXT_HITS = 5
_MAX_HIT_CHARS = 900


def public_image_url(path: str) -> str:
    """把图片地址转成前端可直接渲染的 URL。

    - http(s) / data URI：原样返回（论坛图片本身就是外链）；
    - 项目内的本地文件（PDF 解析产物）：转成后端静态目录 ``/static/...``；
    - 其它情况返回空串。
    """
    if not path:
        return ""
    if path.startswith(("http://", "https://", "data:image")):
        return path
    try:
        abs_path = os.path.abspath(path)
        rel = os.path.relpath(abs_path, str(PROJECT_ROOT)).replace(os.sep, "/")
        if rel.startswith(".."):
            return ""
        return f"/static/{rel}"
    except Exception:
        return ""


def _context_block(hits: List[Dict[str, Any]]) -> str:
    """把命中片段拼成给大模型看的材料块。"""
    pieces: List[str] = []
    for index, hit in enumerate(hits[:_MAX_CONTEXT_HITS], 1):
        header = f"[片段{index}] 来源：{hit.get('sourceLabel')}《{hit.get('title')}》"
        if hit.get("author"):
            header += f" 作者：{hit['author']}"
        if hit.get("labels"):
            header += f" 标签：{hit['labels']}"
        body = (hit.get("text") or "")[:_MAX_HIT_CHARS]
        pieces.append(f"{header}\n{body}")
    return "\n\n".join(pieces) if pieces else "（知识库中没有检索到任何内容）"


def _dedupe(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同一段内容可能被多条检索式命中，去重并保留分数最高的一条。"""
    best: Dict[str, Dict[str, Any]] = {}
    for hit in hits:
        key = f"{hit.get('sourceType')}|{hit.get('title')}|{(hit.get('text') or '')[:80]}"
        if key not in best or hit.get("score", 0) > best[key].get("score", 0):
            best[key] = hit
    return sorted(best.values(), key=lambda h: h.get("score", 0), reverse=True)


def _judge(question: str, hits: List[Dict[str, Any]], relevance: float) -> Dict[str, Any]:
    """大模型判定论坛内容是否足以回答问题。"""
    threshold = CONFIG.get("agent.forum_relevance_threshold", 0.70)
    min_hits = CONFIG.get("agent.forum_min_hits", 1)

    # 先做机械判定：一条都没命中，或者相似度连底线都不到，直接判"不行"
    if len(hits) < min_hits:
        return {"sufficient": False, "score": relevance, "reason": "论坛知识库没有检索到任何内容"}

    verdict = ask_json(
        FORUM_JUDGE_PROMPT,
        f"用户问题：{question}\n\n检索到的片段：\n{_context_block(hits)}",
    )
    if isinstance(verdict, dict) and "sufficient" in verdict:
        score = float(verdict.get("score") or 0.0)
        sufficient = bool(verdict.get("sufficient")) and score >= 0.4
        return {
            "sufficient": sufficient,
            "score": score,
            "reason": str(verdict.get("reason") or "").strip() or "由大模型判定",
        }

    # 大模型判定不可用 → 回退到余弦相似度阈值
    sufficient = relevance >= threshold
    return {
        "sufficient": sufficient,
        "score": relevance,
        "reason": f"大模型判定不可用，按向量相似度 {relevance:.3f} 与阈值 {threshold} 比较",
    }


def forum_node(state: BotState) -> Dict[str, Any]:
    """论坛检索智能体节点。"""
    question = state.get("question") or ""
    image = state.get("image")
    vision_note = state.get("vision_note") or ""
    agent_start("forum", f"在论坛知识库中检索：{question or '（图片检索）'}")

    retriever = get_retriever()
    # 结合多模态理解结论，检索式会更准
    search_seed = question
    if vision_note:
        search_seed = f"{question}\n{vision_note[:400]}".strip()

    # ---------- 1. 查询改写 ----------
    queries: List[str] = []
    if search_seed:
        planned = ask_json(
            FORUM_QUERY_PROMPT,
            f"用户问题：{search_seed}",
        )
        if isinstance(planned, list):
            queries = [str(q).strip() for q in planned if str(q).strip()][:3]
        if not queries:
            queries = [question or search_seed[:60]]
    log.info(f"[forum] 改写后的检索式：{queries}")

    # ---------- 2. 多模态检索 ----------
    all_hits: List[Dict[str, Any]] = []
    best_relevance = 0.0

    for query in queries:
        result = retriever.search(query=query)
        all_hits.extend(result["hits"])
        best_relevance = max(best_relevance, float(result.get("relevance") or 0.0))

    # 用户上传了图片 → 再按图片检索一次（Any-to-Any 检索）
    if image:
        try:
            result = retriever.search(image=image)
            all_hits.extend(result["hits"])
            best_relevance = max(best_relevance, float(result.get("relevance") or 0.0))
        except Exception as e:
            log.warning(f"[forum] 图片检索失败：{e}")

    hits = _dedupe([h for h in all_hits if h.get("text") or h.get("imagePath")])
    hits = hits[: CONFIG.get("retrieval.agent_top_k", 5)]

    # ---------- 2.5 长期记忆：找回该用户过去的高相似回答 ----------
    # 记忆不是"论坛的公共知识"，所以它只作为补充材料，
    # 既不参与"论坛里到底有没有"的判定，也不产生引用。
    memory_hits: List[Dict[str, Any]] = []
    try:
        memory_hits = get_memory_retriever().search(question, state.get("user") or "")
        if memory_hits:
            log.info(f"[forum] 命中 {len(memory_hits)} 条历史记忆")
    except Exception as e:
        log.warning(f"[forum] 长期记忆检索跳过：{e}")

    # ---------- 3. 判定 ----------
    verdict = _judge(question or "（用户上传了一张图片）", hits, best_relevance)
    sufficient = verdict["sufficient"]

    # ---------- 4. 产出引用与图片 ----------
    citations: List[Dict[str, Any]] = []
    images: List[str] = []
    for hit in hits:
        citations.append({
            "type": "forum",
            "sourceLabel": hit.get("sourceLabel"),
            "sourceType": hit.get("sourceType"),
            "title": hit.get("title"),
            "url": hit.get("sourceUrl") or "",
            "author": hit.get("author") or "",
            "createdAt": hit.get("createdAt") or "",
            "snippet": (hit.get("text") or "")[:180],
            "score": round(float(hit.get("score") or 0.0), 4),
        })
        if hit.get("imagePath"):
            url = public_image_url(hit["imagePath"])
            if url and url not in images:
                images.append(url)

    detail = (f"命中 {len(hits)} 条论坛内容（相似度 {best_relevance:.2f}），"
              f"{'可以回答' if sufficient else '不足以回答'}"
              + (f"；另有 {len(memory_hits)} 条历史记忆" if memory_hits else ""))
    agent_done("forum", detail, {"sufficient": sufficient, "hitCount": len(hits)})

    if hits:
        emit("sources", {"forum": citations})

    return {
        "forum_queries": queries,
        "forum_hits": hits,
        "forum_relevance": best_relevance,
        "forum_sufficient": sufficient,
        "forum_reason": verdict.get("reason", ""),
        "memory_hits": memory_hits,
        "citations": citations,
        "images": images,
        "agent_status": {"forum": "done"},
        "trace": [trace_entry(
            "forum", "retrieve",
            f"检索式 {queries}；命中 {len(hits)} 条；判定：{verdict.get('reason', '')}",
            relevance=round(best_relevance, 4), sufficient=sufficient,
            memory=len(memory_hits),
        )],
    }


__all__ = ["forum_node", "public_image_url", "context_block_for_llm"]

# 给答案合成智能体用的材料拼装（避免在 composer 里重复实现）
context_block_for_llm = _context_block
