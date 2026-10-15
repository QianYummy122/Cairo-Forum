"""智能体事件协议：把"多智能体在干什么"实时推给前端。

前端（vue-ui 的「小罗Bot」页面）通过 SSE 收到的事件序列形如::

    event: meta      {"sessionId": "...", "agents": [...]}
    event: agent     {"agent": "supervisor", "status": "start", "label": "调度智能体"}
    event: plan      {"plan": ["forum", "web", "compose"]}
    event: agent     {"agent": "forum", "status": "start", ...}
    event: sources   {"forum": [ {...} ], "web": []}
    event: agent     {"agent": "forum", "status": "done", "detail": "论坛命中 3 条"}
    event: delta     {"text": "## 结论\n"}
    event: done      {"answer": "...", "usedWebSearch": true, "citations": [...]}
    event: error     {"message": "..."}

节点内部通过 LangGraph 的 ``get_stream_writer()`` 把事件写进 ``stream_mode="custom"``
流；在命令行/非流式场景下 writer 不可用，则退化为静默丢弃，不影响主流程。
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

# 智能体展示名（前端"思考过程"面板用）
AGENT_LABELS: Dict[str, str] = {
    "supervisor": "调度智能体",
    "vision": "多模态理解智能体",
    "forum": "论坛检索智能体",
    "web": "联网搜索智能体",
    "compose": "答案合成智能体",
    "evaluate": "质量评估智能体",
}

# SSE 事件名白名单
EVENT_TYPES = (
    "meta", "plan", "agent", "sources", "delta", "done", "error", "warning",
)


def _writer():
    """拿到当前节点所属图的自定义流 writer；不在图上下文中时返回 None。"""
    try:
        from langgraph.config import get_stream_writer

        return get_stream_writer()
    except Exception:
        return None


def emit(event: str, payload: Dict[str, Any], writer=None) -> Dict[str, Any]:
    """发出一个事件。

    返回事件本身（便于测试与同步逻辑复用）；``writer`` 为 None 时自动获取，
    拿不到就只返回不发送。
    """
    packet = {"event": event, "data": payload, "ts": int(time.time() * 1000)}
    sink = writer if writer is not None else _writer()
    if sink is not None:
        try:
            sink(packet)
        except Exception:
            # 推流失败不能影响答题主流程
            pass
    return packet


def agent_start(agent: str, detail: str = "", writer=None) -> Dict[str, Any]:
    return emit("agent", {
        "agent": agent,
        "label": AGENT_LABELS.get(agent, agent),
        "status": "start",
        "detail": detail,
    }, writer)


def agent_done(agent: str, detail: str = "", extra: Dict[str, Any] = None, writer=None) -> Dict[str, Any]:
    payload = {
        "agent": agent,
        "label": AGENT_LABELS.get(agent, agent),
        "status": "done",
        "detail": detail,
    }
    if extra:
        payload.update(extra)
    return emit("agent", payload, writer)


def agent_skip(agent: str, detail: str = "", writer=None) -> Dict[str, Any]:
    return emit("agent", {
        "agent": agent,
        "label": AGENT_LABELS.get(agent, agent),
        "status": "skipped",
        "detail": detail,
    }, writer)


def trace_entry(agent: str, action: str, detail: str = "", **extra) -> Dict[str, Any]:
    """构造一条写进 ``BotState.trace`` 的协作轨迹（持久化在状态里）。"""
    entry = {
        "agent": agent,
        "label": AGENT_LABELS.get(agent, agent),
        "action": action,
        "detail": detail,
        "ts": int(time.time() * 1000),
    }
    if extra:
        entry.update(extra)
    return entry


def sse_format(event: str, data: Any) -> str:
    """把事件编码成 SSE 帧（``event:`` + ``data:``）。"""
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    # SSE 以空行分隔消息；data 中的换行必须逐行加 data: 前缀
    lines = "".join(f"data: {line}\n" for line in data.split("\n"))
    return f"event: {event}\n{lines}\n"


def sse_comment(text: str) -> str:
    """SSE 注释帧，用作心跳保活（代理不会因为长时间无数据断开）。"""
    return f": {text}\n\n"


__all__ = [
    "AGENT_LABELS", "EVENT_TYPES",
    "emit", "agent_start", "agent_done", "agent_skip", "trace_entry",
    "sse_format", "sse_comment",
]
