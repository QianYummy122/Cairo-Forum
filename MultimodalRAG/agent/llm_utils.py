"""智能体用到的大模型调用小工具：稳健的 JSON 解析与文本流式。"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from my_llm import llm, multiModal_llm
from utils.log_utils import log

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json(text: str) -> Optional[Any]:
    """从模型输出里尽力抽出 JSON（容忍围栏、前后废话、单引号）。"""
    if not text:
        return None
    candidates: List[str] = []

    raw = text.strip()
    candidates.append(raw)

    fenced = _JSON_FENCE_RE.search(raw)
    if fenced:
        candidates.append(fenced.group(1).strip())

    # 截取第一个 { 或 [ 到最后一个 } 或 ]
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = raw.find(opener), raw.rfind(closer)
        if start != -1 and end > start:
            candidates.append(raw[start:end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            # 常见问题：中文引号 / 尾随逗号
            fixed = (candidate
                     .replace("“", '"').replace("”", '"')
                     .replace("‘", "'").replace("’", "'"))
            fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
            try:
                return json.loads(fixed)
            except Exception:
                continue
    log.warning(f"extract_json 失败，原始输出前 200 字：{raw[:200]}")
    return None


def ask(system: str, user: str, temperature: float = 0.2, model=None) -> str:
    """一次同步对话调用，返回纯文本。"""
    target = model or llm
    try:
        response = target.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return str(response.content or "").strip()
    except Exception as e:
        log.exception(f"LLM 调用失败：{e}")
        return ""


def ask_json(system: str, user: str, temperature: float = 0.1, model=None) -> Optional[Any]:
    """一次对话调用 + JSON 解析。"""
    return extract_json(ask(system, user, temperature=temperature, model=model))


def ask_multimodal(system: str, text: str, image: str, model=None) -> str:
    """带图片的一次调用。``image`` 是 data URI 或 http(s) URL。"""
    target = model or multiModal_llm
    content = [{"type": "text", "text": text}]
    if image:
        content.append({"type": "image_url", "image_url": {"url": image}})
    try:
        response = target.invoke([SystemMessage(content=system), HumanMessage(content=content)])
        return str(response.content or "").strip()
    except Exception as e:
        log.exception(f"多模态 LLM 调用失败：{e}")
        return ""


def stream_answer(messages: List[BaseMessage]):
    """流式生成回答，逐段 yield 文本（供答案合成智能体使用）。"""
    try:
        for chunk in llm.stream(messages):
            piece = getattr(chunk, "content", "")
            if piece:
                yield piece
    except Exception as e:
        log.exception(f"流式生成失败：{e}")
        yield f"\n\n> ⚠️ 生成回答时出错：{e}"


def trim_history(messages: List[BaseMessage], window: int) -> List[BaseMessage]:
    """只保留最近 ``window`` 条历史消息，控制上下文长度。"""
    if not messages:
        return []
    return messages[-window:] if window and len(messages) > window else list(messages)


def history_for_composer(messages: List[BaseMessage], window: int) -> List[BaseMessage]:
    """给答案合成智能体准备历史上下文：**只保留用户问过的话**。

    为什么要把 AI 的历史回答丢掉：合成智能体拿到的是完整的 messages（含自己前几轮的长回答），
    模型很容易把上一轮的答案当成"还没写完的内容"续写或合并进来。实测出现过
    问 Flink 的回答里混进上一轮的论坛标签清单、问图片的回答里混进 Flink 对比，
    评估智能体也直接把这类内容判为"答非所问的凑数内容"。

    只保留用户提问既能解决指代（"这些标签里哪个最多"这类追问仍然接得上），
    又不会把旧答案带进新答案。真正需要复用旧答案时，走的是"长期记忆检索"那条路
    （见 ``agent/forum_agent.py`` 的 memory_hits），而不是靠对话历史硬塞。
    """
    users_only = [m for m in messages if isinstance(m, HumanMessage)]
    return sanitize_history(trim_history(users_only, window))


def sanitize_history(messages: List[BaseMessage],
                     image_placeholder: str = "（用户上传了一张图片）") -> List[BaseMessage]:
    """把历史消息里的图片块换成纯文本占位符，再交给**纯文本模型**。

    为什么必须做：轮次里的用户消息是多模态结构（``[{"type":"text"},{"type":"image_url"}]``）。
    答案合成智能体用的是纯文本对话模型（DeepSeek），OpenAI 兼容层无法表达图片块，
    会把它降级成一个奇怪的文本占位符，最终**出现在回答正文里**——
    实际表现就是回答里多出一行 ``![图片](image)`` 这种坏掉的 Markdown 图片。

    图片内容本身不会丢：多模态理解智能体已经把结论写进了 ``vision_note``，
    并作为材料交给合成智能体了，这里只需要占位说明"历史里有一张图"。

    统一返回纯文本消息，避免任何模型侧的隐式转换。
    """
    sanitized: List[BaseMessage] = []
    for message in messages:
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            sanitized.append(message)
            continue

        texts: List[str] = []
        has_image = False
        for part in content:
            if not isinstance(part, dict):
                texts.append(str(part))
                continue
            kind = part.get("type")
            if kind == "text":
                texts.append(part.get("text") or "")
            elif kind == "image_url":
                has_image = True
        if has_image:
            texts.append(image_placeholder)

        merged = "\n".join(t for t in texts if t)
        try:
            sanitized.append(message.model_copy(update={"content": merged}))
        except Exception:
            # 极端情况下退化成 HumanMessage，保证不因为清洗而中断问答
            sanitized.append(HumanMessage(content=merged))
    return sanitized


__all__ = [
    "extract_json", "ask", "ask_json", "ask_multimodal",
    "stream_answer", "trim_history", "sanitize_history",
]
