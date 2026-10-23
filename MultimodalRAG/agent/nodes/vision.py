"""多模态理解智能体：先把用户上传的图片"读懂"，再交给下游智能体。

只有用户上传了图片才会执行；产出的 ``vision_note`` 会被
论坛检索智能体（并进检索式）和答案合成智能体（写进回答）共同使用。
"""
from __future__ import annotations

from typing import Any, Dict

from agent.events import agent_done, agent_start, trace_entry
from agent.llm_utils import ask_multimodal
from agent.prompts import VISION_PROMPT
from agent.state import BotState
from utils.log_utils import log


def vision_node(state: BotState) -> Dict[str, Any]:
    """多模态理解智能体节点。"""
    image = state.get("image")
    question = state.get("question") or ""

    if not image:
        agent_done("vision", "本轮没有图片输入，跳过")
        return {
            "agent_status": {"vision": "skipped"},
            "trace": [trace_entry("vision", "skip", "本轮没有图片输入")],
        }

    emit = agent_start("vision", "正在理解你上传的图片")
    user_text = (f"用户的问题：{question}" if question
                 else "用户只上传了图片，没有附带文字问题。")

    note = ask_multimodal(VISION_PROMPT, user_text, image)
    if not note:
        note = "（图片理解失败，请结合用户文字问题作答）"
        log.warning("[vision] 图片理解返回空")

    detail = note.replace("\n", " ")[:120]
    agent_done("vision", f"图片理解完成：{detail}", emit)
    return {
        "vision_note": note,
        "agent_status": {"vision": "done"},
        "trace": [trace_entry("vision", "understand", detail)],
    }


__all__ = ["vision_node"]
