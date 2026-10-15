"""小罗Bot 多智能体工作流的共享状态。

所有智能体（Supervisor / 论坛检索 / 联网搜索 / 多模态理解 / 答案合成 / 质量评估）
都读写同一个 :class:`BotState`，这就是"多智能体协作"的通信总线：
上游智能体把结论写进状态，下游智能体读取并继续加工，整个过程对前端可见
（通过 :mod:`agent.events` 推流）。

状态里有两类字段，处理方式不同：

- **会话级**（``messages``）：由 LangGraph 的 checkpointer 按 ``thread_id`` 累积，
  这是多轮对话"记得上一句"的来源；
- **单轮级**（``plan`` / ``agent_status`` / ``*_hits`` / ``trace`` / ``citations`` …）：
  每轮开始必须清零，否则上一轮的"计划已执行完"会让新一轮直接跳过所有智能体。
  清零由 :func:`agent.graph.prepare_node` 完成，依赖下面支持 ``None`` 语义的 reducer。
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional

from langgraph.graph import MessagesState


def _merge_dicts(left: Dict, right: Dict) -> Dict:
    """并行分支同时写同一个 dict 字段时的合并策略。

    ``right is None`` 表示"重置"（由 :func:`agent.graph.prepare_node` 在每轮开始时发出），
    用于把上一轮遗留的调度状态清干净。
    """
    if right is None:
        return {}
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def _add_list(left: List, right: List) -> List:
    """列表累加，并支持用 ``None`` 重置为空列表。

    为什么需要它：LangGraph 的 checkpointer 会把状态按 ``thread_id`` 持久化下来，
    于是"计划、命中、引用、轨迹"这些**只属于本轮**的字段会跨轮残留 ——
    表现为"用户追问时智能体直接返回上一轮的答案"。
    有了 ``None`` 语义，每轮开头的 prepare 节点就能把本轮字段清零，
    而 ``messages``（对话历史）依旧由 ``add_messages`` 正常累积。
    """
    if right is None:
        return []
    return list(left or []) + list(right or [])


class BotState(MessagesState):
    """小罗Bot 的一次问答所携带的全部状态。"""

    # ---------------- 输入 ----------------
    question: str = ""                     # 本轮用户问题（纯文本）
    image: Optional[str] = None            # 本轮用户上传的图片（data URI 或 URL）
    user: str = "guest"                    # 论坛用户名（未登录为 guest）
    user_id: Optional[str] = None
    session_id: str = ""                   # 会话（LangGraph thread_id）
    web_search_enabled: bool = False       # 用户是否开启了联网搜索

    # ---------------- 调度 ----------------
    # Supervisor 生成的执行计划，例如 ["vision", "forum", "web", "compose"]
    plan: Annotated[List[str], _add_list] = []
    # 每个智能体的执行状态：{"forum": "done", "web": "skipped", ...}
    agent_status: Annotated[Dict[str, str], _merge_dicts] = {}
    # 智能体协作轨迹，前端"思考过程"面板直接渲染
    trace: Annotated[List[Dict[str, Any]], _add_list] = []
    handoffs: int = 0                      # 已完成交接次数（防止死循环）

    # ---------------- 多模态理解 ----------------
    vision_note: str = ""                  # 多模态智能体对用户图片的理解结论
    image_kb_hits: Annotated[List[Dict[str, Any]], _add_list] = []

    # ---------------- 论坛检索（多模态 RAG）----------------
    forum_queries: Annotated[List[str], _add_list] = []
    forum_hits: Annotated[List[Dict[str, Any]], _add_list] = []
    forum_relevance: float = 0.0           # 稠密余弦相似度（论坛里到底有没有相关内容）
    forum_sufficient: bool = False         # 论坛内容是否足以回答
    forum_reason: str = ""                 # 判定理由（给前端展示）
    # 长期记忆命中的历史回答（补充材料，不参与"论坛有没有"的判定）
    memory_hits: Annotated[List[Dict[str, Any]], _add_list] = []

    # ---------------- 联网搜索 ----------------
    web_queries: Annotated[List[str], _add_list] = []
    web_results: Annotated[List[Dict[str, Any]], _add_list] = []
    web_used: bool = False
    # 质量评估判定"必须补一次联网"时置位，强制联网智能体跳过"论坛已足够"的短路
    force_web: bool = False

    # ---------------- 输出 ----------------
    draft_answer: str = ""                 # 合成智能体产出的答案
    answer: str = ""                       # 最终答案
    answer_score: float = 0.0              # 质量评估智能体打分
    evaluate_reason: str = ""
    citations: Annotated[List[Dict[str, Any]], _add_list] = []
    images: Annotated[List[str], _add_list] = []      # 答案中要展示的图片
    used_web_search: bool = False
    need_rewrite: bool = False             # 评估不通过 → 回到合成智能体
    # 质量评估智能体建议"补一次联网搜索"（supervisor 据此插入 web 步骤）
    web_needed_by_evaluator: bool = False
    rewrite_count: int = 0

    # ---------------- 运行时 ----------------
    started_at: float = 0.0
    error: Optional[str] = None


# 计划中的智能体名字（与 supervisor 的路由键一致）
AgentName = Literal[
    "supervisor", "vision", "forum", "web", "compose", "evaluate", "__end__",
]


class InvalidInputError(Exception):
    """自定义异常，用于表示无效输入。"""

    def __init__(self, message: str, error_code: int = 400):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


__all__ = ["BotState", "AgentName", "InvalidInputError"]
