"""小罗Bot 的 HTTP 服务（FastAPI）。

它在整条链路中的位置::

    vue-ui  ──/api/bbs/ai/**──▶  springboot bbs-rest（网关，统一信封 + 登录校验）
                                        │  HTTP 反向代理
                                        ▼
                              本服务（127.0.0.1:7861，仅监听本机）
                                        │
                                        ▼
                          多智能体图 + Milvus 多模态知识库

也就是说：**浏览器永远只跟 bbs-rest 打交道**，本服务是"AI 能力服务"，
只对内提供接口。这样做的好处：

- 前端不用处理跨域（dev 由 vue.config.js 的 ``/api`` 代理，生产同源）；
- 统一走论坛的 ``{code, desc, data}`` 响应信封与登录态（``UserContextUtils``）；
- AI 服务的地址、端口、超时都收敛在 bbs-rest 的配置里，便于部署与限流。

启动::

    python -m server.app          # 或 .\\start_bot.ps1
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from typing import Any, Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent.events import sse_comment
from agent.session import (
    chat_once, list_sessions, reset_session, session_info, sse_encode, stream_chat,
)
from ingestion.attachment_ingest import (
    delete_attachment, ingest_attachment, list_attachments, save_upload, validate_upload,
)
from ingestion.forum_ingest import sync_forum
from ingestion.forum_source import source_status
from milvus_db.collections_operator import knowledge_stats
from server.schemas import (
    AttachmentItem, ChatRequest, ChatResponse, HealthResponse, KnowledgeStatus,
    SessionItem, SyncRequest, SyncResponse, UploadAccepted, UploadLimits, UploadStatus,
)
from utils.config import CONFIG
from utils.log_utils import log

VERSION = "2.0.0"

app = FastAPI(
    title="小罗Bot · AI搜索引擎 Agent 服务",
    description="开罗论坛内置 AI 搜索引擎：多智能体 + 多模态 RAG + 可选联网搜索",
    version=VERSION,
)

# 正常走 bbs-rest 网关时其实用不到 CORS；这里放开是为了方便直接用
# 浏览器/Postman 调试本服务（前端页面依旧只访问 /api/bbs/ai/**）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG.get("server.cors_origins", ["*"]) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 把 output/ 下的图片暴露成 /static/**，让前端能直接渲染 PDF 解析出的图
_OUTPUT_DIR = CONFIG.path("paths.output_dir")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/output", StaticFiles(directory=str(_OUTPUT_DIR)), name="output")


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, summary="服务与依赖健康检查")
async def health() -> HealthResponse:
    llm_ok = True
    llm_error = ""
    try:
        from my_llm import llm

        llm.invoke("ping")
    except Exception as e:  # noqa: BLE001
        llm_ok, llm_error = False, str(e)[:200]

    try:
        stats = knowledge_stats()
    except Exception as e:  # noqa: BLE001
        stats = {"collection": "", "total": 0, "error": str(e)[:200]}

    try:
        sources = source_status()
    except Exception as e:  # noqa: BLE001
        sources = [{"error": str(e)[:200]}]

    return HealthResponse(
        status="ok" if llm_ok else "degraded",
        botName=CONFIG.get("app.bot_name", "小罗Bot"),
        version=VERSION,
        llm={"ok": llm_ok, "model": CONFIG.get("llm.openai.model"), "error": llm_error},
        knowledge={"ok": True, **stats},
        forum={"baseUrl": CONFIG.get("forum.base_url"), "sources": sources},
    )


# ---------------------------------------------------------------------------
# 对话
# ---------------------------------------------------------------------------


def _user_of(req: ChatRequest) -> str:
    """把网关透传的用户信息归一成一个用户名（未登录 -> guest）。"""
    return (req.userName or "").strip() or "guest"


@app.post("/agent/chat", response_model=ChatResponse, summary="对话（非流式）")
async def agent_chat(req: ChatRequest) -> ChatResponse:
    if not (req.question or "").strip() and not req.image:
        raise HTTPException(status_code=400, detail="请输入问题，或者上传一张图片")
    try:
        result = await chat_once(
            question=req.question,
            image=req.image,
            session_id=req.sessionId,
            user=_user_of(req),
            web_search_enabled=req.webSearchEnabled,
        )
    except Exception as e:  # noqa: BLE001
        log.exception(f"[server] /agent/chat 失败：{e}")
        raise HTTPException(status_code=500, detail=f"智能体执行失败：{e}") from e
    return ChatResponse(**{k: v for k, v in result.items() if k in ChatResponse.model_fields})


@app.post("/agent/chat/stream", summary="对话（SSE 流式）")
async def agent_chat_stream(req: ChatRequest):
    """以 SSE 推送智能体协作过程与回答增量。

    事件类型：``meta`` / ``plan`` / ``agent`` / ``sources`` / ``delta`` / ``done`` / ``error``。
    """
    if not (req.question or "").strip() and not req.image:
        raise HTTPException(status_code=400, detail="请输入问题，或者上传一张图片")

    user = _user_of(req)

    async def event_source():
        # 先发一个注释帧，让代理立刻建立流，避免浏览器等待首字节超时
        yield sse_comment("小罗Bot stream opened")
        try:
            async for event in stream_chat(
                question=req.question,
                image=req.image,
                session_id=req.sessionId,
                user=user,
                user_id=req.userId,
                web_search_enabled=req.webSearchEnabled,
            ):
                yield sse_encode(event)
        except asyncio.CancelledError:  # 客户端断开
            log.info("[server] SSE 客户端断开连接")
            raise
        except Exception as e:  # noqa: BLE001
            log.exception(f"[server] SSE 流异常：{e}")
            yield sse_encode({"event": "error", "data": {"message": f"服务异常：{e}"}})
        finally:
            # 显式结束事件，前端据此关闭连接
            yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 关掉 nginx 缓冲，保证逐字下发
        },
    )


# ---------------------------------------------------------------------------
# 会话
# ---------------------------------------------------------------------------


@app.get("/agent/sessions", response_model=List[SessionItem], summary="会话列表")
async def sessions(userName: str = Query(None, description="只看某个用户的会话")):
    return [SessionItem(**item) for item in list_sessions(userName)]


@app.get("/agent/sessions/{session_id}", summary="会话详情")
async def session_detail(session_id: str):
    info = session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="会话不存在")
    return info


@app.delete("/agent/sessions/{session_id}", summary="清理会话")
async def session_delete(session_id: str):
    return {"removed": reset_session(session_id)}


# ---------------------------------------------------------------------------
# 知识库
# ---------------------------------------------------------------------------


@app.get("/kb/status", response_model=KnowledgeStatus, summary="知识库与数据源状态")
async def kb_status() -> KnowledgeStatus:
    stats = knowledge_stats()
    return KnowledgeStatus(
        collection=stats.get("collection", ""),
        total=int(stats.get("total") or 0),
        bySourceType=stats.get("bySourceType") or {},
        sources=source_status(),
        # 把读取是否成功透出去：页面据此区分"知识库是空的"与"统计读不到"
        ok=bool(stats.get("ok", True)),
        error=str(stats.get("error") or ""),
    )


@app.post("/kb/sync", response_model=SyncResponse, summary="同步论坛内容到知识库")
async def kb_sync(req: SyncRequest) -> SyncResponse:
    """同步是耗时操作（要调嵌入接口），默认同步执行；数据量大时请用 /kb/sync/async。"""
    started = time.time()
    report = await asyncio.to_thread(
        sync_forum, req.source, req.withImages, req.sourceTypes,
    )
    report["elapsedMs"] = int((time.time() - started) * 1000)
    log.info(f"[server] 知识库同步完成：{report}")
    return SyncResponse(**{k: v for k, v in report.items() if k in SyncResponse.model_fields})


# 后台同步任务状态（简单内存记录）
_SYNC_STATE: Dict[str, Any] = {"running": False, "startedAt": 0, "result": None, "error": None}


def _run_sync(source: str, with_images: bool, source_types: List[str]) -> None:
    _SYNC_STATE.update({"running": True, "startedAt": time.time(), "result": None, "error": None})
    try:
        _SYNC_STATE["result"] = sync_forum(source, with_images, source_types)
    except Exception as e:  # noqa: BLE001
        log.exception(f"[server] 后台同步失败：{e}")
        _SYNC_STATE["error"] = str(e)
    finally:
        _SYNC_STATE["running"] = False


@app.post("/kb/sync/async", summary="异步同步（立即返回，后台执行）")
async def kb_sync_async(req: SyncRequest, background: BackgroundTasks):
    if _SYNC_STATE["running"]:
        return {"accepted": False, "reason": "已有同步任务在执行"}
    background.add_task(_run_sync, req.source, req.withImages, req.sourceTypes)
    return {"accepted": True}


@app.get("/kb/sync/status", summary="异步同步进度")
async def kb_sync_status():
    return _SYNC_STATE


# ---------------------------------------------------------------------------
# 文档附件上传
# ---------------------------------------------------------------------------
# 目标：把"要跑 python main.py 才能加文档"变成"页面上直接上传"。
# 上传后立刻返回 taskId，解析与向量化在后台线程跑（PDF/Word 解析 + 批量嵌入可能几十秒），
# 前端轮询 /kb/upload/status/{taskId} 拿进度，避免把 HTTP 连接挂死。

# 上传任务表：taskId → 进度
_UPLOAD_TASKS: Dict[str, Dict[str, Any]] = {}
_MAX_TASKS = 200


def _new_task(task_id: str, file_name: str, size: int) -> Dict[str, Any]:
    task = {
        "taskId": task_id,
        "fileName": file_name,
        "sizeBytes": size,
        "state": "pending",
        "running": True,
        "progressText": "已接收文件，排队中…",
        "result": None,
        "error": None,
        "createdAt": time.time(),
    }
    _UPLOAD_TASKS[task_id] = task
    # 只保留最近的任务，防止内存无限增长
    if len(_UPLOAD_TASKS) > _MAX_TASKS:
        for key, _ in sorted(_UPLOAD_TASKS.items(), key=lambda kv: kv[1]["createdAt"])[
                : len(_UPLOAD_TASKS) - _MAX_TASKS]:
            _UPLOAD_TASKS.pop(key, None)
    return task


def _run_upload_task(task_id: str, path, original_name: str, uploader: str) -> None:
    """后台执行：解析 → 分块 → 向量化 → 入库。"""
    task = _UPLOAD_TASKS.get(task_id)
    if task is None:
        return
    try:
        task.update({"state": "parsing", "progressText": "正在解析文件内容…"})
        # ingest_attachment 内部已经合并了"解析 + 入库"两步，
        # 这里在调用前后改状态，让前端至少能看到阶段变化
        task.update({"state": "embedding", "progressText": "正在向量化并写入知识库…"})
        report = ingest_attachment(path, original_name, uploader)
        if report.get("ok"):
            task.update({
                "state": "done",
                "progressText": f"入库完成：{report.get('inserted', 0)} 条知识",
                "result": report,
            })
        else:
            task.update({
                "state": "failed",
                "progressText": report.get("error") or "解析失败",
                "error": report.get("error") or "解析失败",
                "result": report,
            })
    except Exception as e:  # noqa: BLE001
        log.exception(f"[server] 附件入库失败 {original_name}：{e}")
        task.update({"state": "failed", "error": str(e), "progressText": f"入库失败：{e}"})
    finally:
        task["running"] = False


@app.get("/kb/upload/limits", response_model=UploadLimits, summary="上传限制（供前端展示与校验）")
async def kb_upload_limits() -> UploadLimits:
    return UploadLimits(
        enabled=bool(CONFIG.get("attachment.enabled", True)),
        adminOnly=bool(CONFIG.get("attachment.admin_only", True)),
        maxSizeMb=int(CONFIG.get("attachment.max_size_mb", 20)),
        allowedExtensions=list(CONFIG.get("attachment.allowed_extensions") or []),
        sourceLabel=str(CONFIG.get("attachment.source_label", "上传文档")),
    )


@app.post("/kb/upload", response_model=UploadAccepted, summary="上传文档附件并入库（异步）")
async def kb_upload(background: BackgroundTasks,
                    file: UploadFile = File(..., description="要入库的文档"),
                    uploader: str = Query("admin", description="上传者用户名，用于溯源")):
    if not CONFIG.get("attachment.enabled", True):
        return UploadAccepted(accepted=False, reason="文档上传功能当前未启用")

    original_name = file.filename or "unnamed"
    data = await file.read()
    error = validate_upload(original_name, len(data))
    if error:
        return UploadAccepted(accepted=False, fileName=original_name,
                              sizeBytes=len(data), reason=error)

    path, _digest, safe_name = save_upload(data, original_name)
    task_id = uuid.uuid4().hex
    _new_task(task_id, safe_name, len(data))
    background.add_task(_run_upload_task, task_id, path, safe_name, uploader)
    log.info(f"[server] 收到附件上传：{safe_name}（{len(data)} 字节），taskId={task_id}")
    return UploadAccepted(accepted=True, taskId=task_id,
                          fileName=safe_name, sizeBytes=len(data))


@app.get("/kb/upload/status/{task_id}", response_model=UploadStatus, summary="上传任务进度")
async def kb_upload_status(task_id: str) -> UploadStatus:
    task = _UPLOAD_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="上传任务不存在或已过期")
    return UploadStatus(**{k: v for k, v in task.items() if k in UploadStatus.model_fields})


@app.get("/kb/attachments", response_model=List[AttachmentItem], summary="已入库的文档附件")
async def kb_attachments() -> List[AttachmentItem]:
    return [AttachmentItem(**item) for item in list_attachments()]


@app.delete("/kb/attachments/{doc_id:path}", summary="删除某个附件及其知识条目")
async def kb_attachment_delete(doc_id: str):
    result = delete_attachment(doc_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "删除失败")
    return result


# ---------------------------------------------------------------------------
# 异常统一处理
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # noqa: ANN001
    log.exception(f"[server] 未处理异常：{exc}")
    return JSONResponse(status_code=500, content={"detail": f"服务内部错误：{exc}"})


@app.on_event("startup")
async def on_startup() -> None:
    bot_name = CONFIG.get("app.bot_name", "小罗Bot")
    log.info("=" * 68)
    log.info(f"  {bot_name} · AI搜索引擎 Agent 服务已启动  v{VERSION}")
    log.info(f"  监听：http://{CONFIG.get('server.host')}:{CONFIG.get('server.port')}")
    log.info(f"  论坛网关：{CONFIG.get('forum.base_url')}")
    log.info(f"  联网搜索：默认{'开启' if CONFIG.get('web_search.enabled_by_default') else '关闭'}（由前端开关控制）")
    log.info("=" * 68)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """退出前把向量库落盘。

    为什么要这么做：Milvus Lite 是嵌入式实现，写入先进 WAL 再合并成 parquet。
    如果进程被**强杀**（任务管理器结束进程、kill -9），正在写的 WAL 会损坏，
    下次打开时 Milvus 丢弃这段 WAL，极端情况下整个集合会查询为 0 条
    （parquet 里的数据其实还在，但要重新入库才能恢复）。

    正常按一次 Ctrl+C 会走到这里，从而安全落盘。
    页面上的"停止服务"请用 Ctrl+C，不要直接强杀进程。
    """
    try:
        from milvus_db.collections_operator import flush_knowledge

        if flush_knowledge():
            log.info("[小罗Bot] 向量库已安全落盘")
        else:
            log.warning("[小罗Bot] 向量库落盘失败，请检查 milvus_local.db")
    except Exception as e:  # noqa: BLE001
        log.warning(f"[小罗Bot] 退出时落盘跳过：{e}")
    log.info("[小罗Bot] 服务已停止")


def main() -> None:
    """命令行启动入口：python -m server.app"""
    import uvicorn

    host = CONFIG.get("server.host", "127.0.0.1")
    port = int(CONFIG.get("server.port", 7861))
    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        reload=False,
        log_level=str(CONFIG.get("logging.level", "info")).lower(),
    )


if __name__ == "__main__":
    main()
