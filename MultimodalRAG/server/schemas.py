"""小罗Bot HTTP 服务的请求/响应模型。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """一轮对话请求。"""

    question: str = Field("", description="用户问题（纯文本）")
    image: Optional[str] = Field(
        None,
        description="图片：data URI / http(s) URL / 服务器可读的本地路径，三者皆可",
    )
    sessionId: Optional[str] = Field(None, description="会话 id；不传则新建会话")
    userId: Optional[str] = Field(None, description="论坛用户 id（由 bbs-rest 网关透传）")
    userName: Optional[str] = Field(None, description="论坛用户名（由 bbs-rest 网关透传）")
    webSearchEnabled: bool = Field(False, description="是否启用联网搜索")


class ChatResponse(BaseModel):
    """非流式对话响应。"""

    sessionId: str
    answer: str
    usedWebSearch: bool = False
    webSearchEnabled: bool = False
    forumSufficient: bool = False
    forumRelevance: float = 0.0
    answerScore: float = 0.0
    citations: List[Dict[str, Any]] = []
    images: List[str] = []
    plan: List[str] = []
    trace: List[Dict[str, Any]] = []
    elapsedMs: int = 0
    error: Optional[str] = None


class KnowledgeStatus(BaseModel):
    """知识库与数据源状态。"""

    collection: str
    total: int
    bySourceType: Dict[str, int] = {}
    sources: List[Dict[str, Any]] = []
    # 读取是否成功。false 表示"统计拿不到"，此时 total=0 不代表知识库真的是空的
    ok: bool = True
    error: str = ""


class SyncRequest(BaseModel):
    """知识库同步请求。"""

    source: Optional[str] = Field(
        None, description="数据源：springboot-rest / mysql / local-snapshot，不传则自动探测")
    withImages: bool = Field(True, description="是否抓取并理解图片（多模态入库）")
    sourceTypes: Optional[List[str]] = Field(
        None, description="只同步指定来源类型，如 ['article']")


class SyncResponse(BaseModel):
    ok: bool
    source: Optional[str] = None
    documents: int = 0
    chunks: int = 0
    embedded: int = 0
    inserted: int = 0
    error: Optional[str] = None


class SessionItem(BaseModel):
    sessionId: str
    user: str = "guest"
    title: str = ""
    turns: int = 0
    createdAt: float = 0
    updatedAt: float = 0


class HealthResponse(BaseModel):
    status: str
    botName: str
    version: str
    llm: Dict[str, Any]
    knowledge: Dict[str, Any]
    forum: Dict[str, Any]


class AttachmentItem(BaseModel):
    """已入库的文档附件。"""

    docId: str
    title: str = ""
    author: str = ""
    fileType: str = ""
    chunks: int = 0


class UploadAccepted(BaseModel):
    """上传被接受（解析与向量化在后台进行）。"""

    accepted: bool
    taskId: Optional[str] = None
    fileName: str = ""
    sizeBytes: int = 0
    reason: Optional[str] = None


class UploadStatus(BaseModel):
    """上传任务的进度。"""

    taskId: str
    fileName: str = ""
    state: str = "pending"          # pending / parsing / embedding / done / failed
    running: bool = True
    progressText: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class UploadLimits(BaseModel):
    """把服务端限制回给前端，避免前端再写一份规则导致不一致。"""

    enabled: bool
    adminOnly: bool
    maxSizeMb: int
    allowedExtensions: List[str]
    sourceLabel: str = ""


__all__ = [
    "ChatRequest", "ChatResponse", "KnowledgeStatus",
    "SyncRequest", "SyncResponse", "SessionItem", "HealthResponse",
    "AttachmentItem", "UploadAccepted", "UploadStatus", "UploadLimits",
]
