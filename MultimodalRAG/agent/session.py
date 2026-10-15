"""小罗Bot 的运行时：把"一次提问"跑成一条事件流。

对外只暴露一个异步生成器 :func:`stream_chat`，它负责：

1. 构造/复用会话（LangGraph ``thread_id``），维持多轮上下文；
2. 组装 :class:`BotState` 初值（问题、图片、联网开关、用户）；
3. 驱动多智能体图，把 ``custom`` 流里的事件原样转发；
4. 兜底处理异常（任何一步炸了都要给前端一个 event: error，而不是断流）；
5. 结束后把本轮问答写入长期记忆（Milvus 上下文集合），供后续追问复用。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.messages import HumanMessage

from agent.events import AGENT_LABELS, emit, sse_comment, sse_format
from agent.graph import get_agent_graph
from agent.state import BotState
from utils.config import CONFIG
from utils.log_utils import log

# 会话表：thread_id → 元信息（用于 /session/{id} 查询与清理）
_SESSIONS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------


def _touch_session(session_id: str, user: str, question: str) -> Dict[str, Any]:
    now = time.time()
    info = _SESSIONS.get(session_id)
    if info is None:
        info = {"sessionId": session_id, "user": user, "createdAt": now,
                "updatedAt": now, "turns": 0, "title": question[:30]}
        _SESSIONS[session_id] = info
    info["updatedAt"] = now
    info["turns"] = int(info.get("turns") or 0) + 1
    if not info.get("title") and question:
        info["title"] = question[:30]
    # 超过上限时清掉最旧的会话
    max_sessions = CONFIG.get("server.max_sessions", 500)
    if len(_SESSIONS) > max_sessions:
        oldest = sorted(_SESSIONS.items(), key=lambda kv: kv[1]["updatedAt"])[: len(_SESSIONS) - max_sessions]
        for key, _ in oldest:
            _SESSIONS.pop(key, None)
    return info


def session_info(session_id: str) -> Optional[Dict[str, Any]]:
    return _SESSIONS.get(session_id)


def list_sessions(user: str = None) -> List[Dict[str, Any]]:
    items = list(_SESSIONS.values())
    if user:
        items = [i for i in items if i.get("user") == user]
    return sorted(items, key=lambda i: i["updatedAt"], reverse=True)


def reset_session(session_id: str) -> bool:
    return _SESSIONS.pop(session_id, None) is not None


# ---------------------------------------------------------------------------
# 输入整理
# ---------------------------------------------------------------------------


def normalize_image(image: Optional[str]) -> Optional[str]:
    """把前端传来的图片统一成多模态模型能直接吃的形式。

    支持三种输入：
    - 已经是 ``data:image/...;base64,...``（前端用 FileReader 读出来的）；
    - ``http(s)://`` 图片地址；
    - 后端可读的本地文件路径（会转成 data URI）。
    """
    if not image:
        return None
    image = image.strip()
    if image.startswith("data:image") or image.startswith(("http://", "https://")):
        return image
    import os

    if os.path.isfile(image):
        from utils.embeddings_utils import image_to_base64

        data_uri, _ = image_to_base64(image)
        return data_uri or None
    log.warning(f"[session] 无法识别的图片输入：{image[:80]}")
    return None


def _initial_state(
    question: str,
    image: Optional[str],
    session_id: str,
    user: str,
    user_id: Optional[str],
    web_search_enabled: bool,
) -> Dict[str, Any]:
    """构造本轮状态初值。

    只放**输入类**字段：``messages`` 里只追加本轮用户消息（历史轮次由 LangGraph 的
    checkpointer 按 ``thread_id`` 叠加），其余单轮字段由图的 ``prepare`` 入口节点统一清零。

    这样划分的好处：多轮上下文"记在图上"，不会因为手写历史而出现重复或错序；
    而调度状态又不会跨轮残留（否则追问时智能体会以为"计划都做完了"直接返回旧答案）。
    """
    content: List[Dict[str, Any]] = []
    if question:
        content.append({"type": "text", "text": question})
    if image:
        content.append({"type": "image_url", "image_url": {"url": image}})

    return {
        "messages": [HumanMessage(content=content or [{"type": "text", "text": question or "（空提问）"}])],
        "question": question,
        "image": image,
        "user": user,
        "user_id": user_id,
        "session_id": session_id,
        "web_search_enabled": web_search_enabled,
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


async def stream_chat(
    question: str = "",
    image: Optional[str] = None,
    session_id: Optional[str] = None,
    user: str = "guest",
    user_id: Optional[str] = None,
    web_search_enabled: bool = False,
) -> AsyncIterator[Dict[str, Any]]:
    """跑一轮问答，逐个 yield 事件字典（由调用方负责编码成 SSE / JSON）。

    事件类型见 :mod:`agent.events`。
    """
    started = time.time()
    session_id = session_id or str(uuid.uuid4())
    _touch_session(session_id, user, question)
    graph = get_agent_graph()
    config = {"configurable": {"thread_id": session_id, "user_name": user}}

    question = (question or "").strip()
    image = normalize_image(image)

    # 首帧：让前端立刻知道会话 id 和智能体清单，便于渲染"思考过程"骨架
    yield {"event": "meta", "data": {
        "sessionId": session_id,
        "botName": CONFIG.get("app.bot_name", "小罗Bot"),
        "agents": AGENT_LABELS,
        "webSearchEnabled": bool(web_search_enabled),
    }}

    if not question and not image:
        yield {"event": "error", "data": {"message": "请输入问题，或者上传一张图片。"}}
        return

    state = _initial_state(question, image, session_id, user, user_id, web_search_enabled)
    answer = ""
    final_values: Dict[str, Any] = {}

    try:
        async for mode, chunk in graph.astream(
            state, config, stream_mode=["custom", "values"],
        ):
            if mode == "custom":
                # 节点里 emit() 出来的事件
                if isinstance(chunk, dict) and chunk.get("event"):
                    if chunk["event"] == "delta":
                        answer += str((chunk.get("data") or {}).get("text") or "")
                    yield {"event": chunk["event"], "data": chunk.get("data") or {}}
            elif mode == "values":
                final_values = chunk if isinstance(chunk, dict) else final_values
    except Exception as e:  # noqa: BLE001 - 任何异常都要变成可读的错误事件
        log.exception(f"[session] 问答失败：{e}")
        yield {"event": "error", "data": {
            "message": f"智能体执行出错：{e}",
            "sessionId": session_id,
        }}
        return

    final_answer = (final_values.get("answer") or answer or "").strip()
    elapsed = int((time.time() - started) * 1000)

    yield {"event": "done", "data": {
        "sessionId": session_id,
        "answer": final_answer,
        "usedWebSearch": bool(final_values.get("web_used")),
        "webSearchEnabled": bool(web_search_enabled),
        "forumSufficient": bool(final_values.get("forum_sufficient")),
        "forumRelevance": round(float(final_values.get("forum_relevance") or 0.0), 4),
        "answerScore": round(float(final_values.get("answer_score") or 0.0), 4),
        "citations": final_values.get("citations") or [],
        "images": final_values.get("images") or [],
        "plan": final_values.get("plan") or [],
        "trace": final_values.get("trace") or [],
        "elapsedMs": elapsed,
        "user": user,
    }}

    # 写入长期记忆（失败不影响本轮结果）
    if final_answer:
        try:
            asyncio.create_task(_save_memory(final_answer, user))
        except Exception as e:
            log.warning(f"[session] 长期记忆写入调度失败：{e}")


async def _save_memory(answer: str, user: str) -> None:
    from graph.save_context import get_milvus_writer

    try:
        await get_milvus_writer().async_insert(context_text=answer, user=user, message_type="AIMessage")
    except Exception as e:
        log.warning(f"[session] 长期记忆写入失败：{e}")


async def chat_once(
    question: str = "",
    image: Optional[str] = None,
    session_id: Optional[str] = None,
    user: str = "guest",
    web_search_enabled: bool = False,
) -> Dict[str, Any]:
    """非流式版本：内部跑完整个事件流，返回最终 done 结果（给 /agent/chat 用）。"""
    result: Dict[str, Any] = {"answer": "", "sessionId": session_id or str(uuid.uuid4())}
    async for event in stream_chat(question, image, session_id, user,
                                   web_search_enabled=web_search_enabled):
        if event["event"] == "done":
            result = event["data"]
        elif event["event"] == "error":
            result["error"] = event["data"].get("message")
    return result


def sse_encode(event: Dict[str, Any]) -> str:
    """把事件字典编码成 SSE 帧。"""
    return sse_format(event["event"], event["data"])


__all__ = [
    "stream_chat", "chat_once", "sse_encode", "sse_comment",
    "session_info", "list_sessions", "reset_session", "normalize_image",
]
