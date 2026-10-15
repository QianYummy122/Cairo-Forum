"""答案合成智能体：把所有材料写成一份对用户有用的回答。

它是唯一一个**流式输出**的智能体 —— 生成过程中通过 ``delta`` 事件把增量文本推给前端，
所以用户在页面上看到的是"打字机"效果，而不是等十几秒后一次性刷出整段答案。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agent.events import agent_done, agent_start, emit, trace_entry
from agent.forum_agent import context_block_for_llm
from agent.prompts import (
    COMPOSER_PROMPT, COMPOSER_RETRY_SUFFIX, BOT_NAME, FORUM_NAME,
)
from agent.state import BotState
from agent.llm_utils import history_for_composer
from my_llm import llm
from utils.config import CONFIG
from utils.log_utils import log

# 回答里的图片语法（Markdown 与 HTML 两种），用于剔除模型自己编出来的图片
_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)[^)]*\)")
_HTML_IMG_RE = re.compile(r"<img\b[^>]*?>", re.IGNORECASE)
_HTML_IMG_SRC_RE = re.compile(r'src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def sanitize_answer_images(answer: str, allowed: List[str]) -> str:
    """只保留"确实存在"的图片引用。

    为什么需要：材料为空时，模型仍可能凭"图片"这个词自己编一个
    ``![图片](image)`` 或 ``<img src="...">``，用户看到的就是一个坏图。
    这里把不在 ``allowed``（论坛命中图片 + 用户上传图片）里的图片引用统统删掉，
    宁可不显示图，也不显示坏图。

    另外会顺手清掉模型自造的 base64 图片（几 KB 的 data URI 塞进回答里毫无意义）。
    """
    allowed_set = {a for a in (allowed or []) if a}

    def keep(url: str) -> bool:
        url = (url or "").strip()
        if not url:
            return False
        if url.startswith("data:image"):
            return False          # 模型自造的 base64 图，一律丢掉
        return url in allowed_set

    def md_repl(match: re.Match) -> str:
        return match.group(0) if keep(match.group(1)) else ""

    def html_repl(match: re.Match) -> str:
        src_match = _HTML_IMG_SRC_RE.search(match.group(0))
        src = src_match.group(1) if src_match else ""
        return match.group(0) if keep(src) else ""

    cleaned = _MD_IMG_RE.sub(md_repl, answer or "")
    cleaned = _HTML_IMG_RE.sub(html_repl, cleaned)
    # 删掉图片后可能留下空行，顺手压缩
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _web_block(results: List[Dict[str, Any]]) -> str:
    """联网搜索材料块。"""
    if not results:
        return "（本轮没有联网搜索结果）"
    return "\n\n".join(
        f"[联网材料{index}] {item.get('title') or ''}\n{item.get('snippet') or ''}"
        for index, item in enumerate(results, 1)
    )


def build_materials(state: BotState) -> str:
    """把各智能体的产出拼成给合成模型看的一份材料。"""
    sections: List[str] = []

    if state.get("vision_note"):
        sections.append(f"## 图片理解结论（多模态理解智能体）\n{state['vision_note']}")

    forum_hits = state.get("forum_hits") or []
    if forum_hits:
        sections.append(
            f"## {FORUM_NAME}知识库命中（论坛检索智能体，共 {len(forum_hits)} 条）\n"
            + context_block_for_llm(forum_hits)
        )
    else:
        sections.append(f"## {FORUM_NAME}知识库命中\n（没有命中任何内容）")

    memory_hits = state.get("memory_hits") or []
    if memory_hits:
        pieces = [f"[历史回答{index}] {h.get('text', '')[:600]}"
                  for index, h in enumerate(memory_hits, 1)]
        sections.append(
            "## 与当前提问相关的历史回答（长期记忆）\n"
            "（这是你过去给这位用户的回答，可用来保持前后一致；"
            "如需引用，请说明「参考了之前的回答」）\n" + "\n\n".join(pieces)
        )

    web_results = state.get("web_results") or []
    if web_results:
        sections.append(f"## 联网搜索结果（联网搜索智能体）\n{_web_block(web_results)}")
    elif state.get("web_search_enabled"):
        sections.append("## 联网搜索结果\n（本轮没有联网搜索结果）")
    else:
        sections.append("## 联网搜索结果\n（用户未开启联网搜索，本轮没有外部资料）")

    # 来源索引，方便模型写出可点的引用
    citations = state.get("citations") or []
    if citations:
        lines = []
        for index, c in enumerate(citations, 1):
            if c.get("type") == "forum":
                lines.append(f"- 论坛来源{index}：{c.get('sourceLabel')}《{c.get('title')}》"
                             f"（作者 {c.get('author') or '未知'}）链接 {c.get('url') or '站内'}")
            else:
                lines.append(f"- 网络来源{index}：{c.get('title')} 链接 {c.get('url')}")
        sections.append("## 可用引用清单\n" + "\n".join(lines))

    images = state.get("images") or []
    if images:
        sections.append("## 可展示的图片（Markdown 语法直接引用）\n" + "\n".join(f"- {u}" for u in images))

    return "\n\n".join(sections)


def _system_prompt(state: BotState) -> str:
    prompt = COMPOSER_PROMPT
    if state.get("rewrite_count"):
        prompt += COMPOSER_RETRY_SUFFIX.format(
            reason=state.get("evaluate_reason") or "答案不够切题或缺少依据"
        )
    if not state.get("web_search_enabled"):
        prompt += ("\n\n# 注意\n用户本轮**没有开启联网搜索**："
                   f"如果{FORUM_NAME}知识库里没有相关内容，就如实说明站内暂时没有，"
                   "并给出你基于常识的建议（并注明这部分没有站内依据）。")
    return prompt


def composer_node(state: BotState) -> Dict[str, Any]:
    """答案合成智能体节点（流式）。"""
    question = state.get("question") or ""
    has_image = bool(state.get("image"))
    agent_start("compose", "正在综合论坛与联网材料撰写回答")

    materials = build_materials(state)
    system = SystemMessage(content=_system_prompt(state))

    user_parts = [
        f"# 用户问题\n{question or '（用户只上传了一张图片，请结合图片理解结论作答）'}",
        f"# 可用材料\n{materials}",
    ]
    if has_image:
        user_parts.append("# 提示\n用户上传了图片，图片理解结论已包含在材料中。")
    user_parts.append("请直接输出最终回答（Markdown），不要重复材料原文，不要输出材料标题。")

    messages = [system, *history_for_composer(
        [m for m in (state.get("messages") or []) if not isinstance(m, SystemMessage)],
        CONFIG.get("agent.history_window", 8),
    )]
    # 保证最后一条是本轮问题（历史消息里可能已经带了本轮问题）
    messages.append(HumanMessage(content="\n\n".join(user_parts)))

    buffer: List[str] = []
    pending: List[str] = []          # 攒一小批再推，减少 SSE 帧数量
    flush_at = 8

    def flush() -> None:
        if pending:
            emit("delta", {"text": "".join(pending)})
            pending.clear()

    for piece in llm.stream(messages):
        text = getattr(piece, "content", "") or ""
        if not text:
            continue
        buffer.append(text)
        pending.append(text)
        # 到量、或遇到换行/句末标点就立刻下发，保证打字机节奏自然
        if len(pending) >= flush_at or text[-1] in "\n。！？；：,!?;:":
            flush()
    flush()

    answer = "".join(buffer).strip()
    if not answer:
        answer = (f"抱歉，我这次没能生成有效回答。{FORUM_NAME}知识库里暂时也没有可用内容，"
                  "你可以换个说法再问一次，或者开启联网搜索让我去网上找找。")
        log.warning("[compose] 模型返回空回答")

    # 剔除模型自己编出来的图片引用（材料里没有图时它也常常会写一个坏图）
    answer = sanitize_answer_images(answer, state.get("images") or [])

    detail = f"已生成 {len(answer)} 字的回答"
    agent_done("compose", detail)
    return {
        "draft_answer": answer,
        "answer": answer,
        "agent_status": {"compose": "done"},
        "trace": [trace_entry("compose", "write", detail, length=len(answer))],
    }


__all__ = ["composer_node", "build_materials", "sanitize_answer_images", "BOT_NAME"]
