"""本地联调用的「网关桩」——在没有启动 springboot 全家桶时，也能跑通前端页面。

背景
----
线上/正常开发时，链路的中间那一段是 springboot 的 bbs-rest：

    vue-ui  ──/api/bbs/ai/**──▶  bbs-rest:7010  ──▶  AI 服务:7861

但 bbs-rest 依赖 ZooKeeper + MySQL + Redis + Mongo 一整套中间件，
只想调前端页面时把它们全拉起来并不划算。这个脚本用标准库起一个**同路径、同信封、
同权限规则**的迷你网关，把请求转发给 AI 服务，于是：

    vue-ui  ──/api/bbs/ai/**──▶  本脚本:7010  ──▶  AI 服务:7861

前端代码一行都不用改（`/api` 由 vue.config.js 代理到 7010）。

权限规则（**必须和 AiBotController 保持一致**，否则联调通过、上线被拒）
------------------------------------------------------------------
- `/kb/sync`、`/kb/sync/status`：仅管理员；
- `/kb/status`：所有人可读，但非管理员会被摘掉 `collection`（向量集合名）。

桩默认把自己当**游客**；要联调管理员视图，请求带上
``X-Dev-Role: admin`` 头即可（前端页面不方便加头，可在浏览器控制台里
直接改 ``$store.state.isManage`` 来切换界面）：

    curl -H "X-Dev-Role: admin" http://127.0.0.1:7010/api/bbs/ai/kb/status

用法::

    python tools/dev_gateway.py            # 监听 7010
    python tools/dev_gateway.py --port 7010

注意：**仅用于本地联调**。它不做真实的登录校验，别拿去部署。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.config import CONFIG  # noqa: E402

# AI 服务地址（与 bbs-rest 的 ai.agent.base-url 保持一致）
AI_BASE = f"http://{CONFIG.get('server.host', '127.0.0.1')}:{CONFIG.get('server.port', 7861)}"

# 浏览器路径 → AI 服务路径。
# 这张表必须与 bbs-rest 的 com.liang.bbs.rest.controller.AiBotController 一一对应，
# 否则前端调通了、正式环境却 404（反之亦然）。
ROUTE_MAP = {
    "/api/bbs/ai/chat": "/agent/chat",
    "/api/bbs/ai/chat/stream": "/agent/chat/stream",
    "/api/bbs/ai/sessions": "/agent/sessions",
    "/api/bbs/ai/health": "/health",
    "/api/bbs/ai/kb/status": "/kb/status",
    "/api/bbs/ai/kb/sync": "/kb/sync/async",
    "/api/bbs/ai/kb/sync/status": "/kb/sync/status",
    "/api/bbs/ai/kb/upload/limits": "/kb/upload/limits",
    "/api/bbs/ai/kb/upload": "/kb/upload",
    "/api/bbs/ai/kb/attachments": "/kb/attachments",
}

# 带路径参数的路径前缀 → AI 服务对应前缀（桩自己拼后半段）
ROUTE_PREFIX_MAP = {
    "/api/bbs/ai/sessions/": "/agent/sessions/",
    "/api/bbs/ai/kb/upload/status/": "/kb/upload/status/",
    "/api/bbs/ai/kb/attachments/": "/kb/attachments/",
}

# 需要透传 SSE 的路径
STREAM_PATHS = {"/api/bbs/ai/chat/stream"}

# 需要透传 multipart 的路径
MULTIPART_PATHS = {"/api/bbs/ai/kb/upload"}

# 仅管理员可用的路径（与 AiBotController.requireAdmin 一一对应）
ADMIN_ONLY_PATHS = {
    "/api/bbs/ai/kb/sync",
    "/api/bbs/ai/kb/sync/status",
    "/api/bbs/ai/kb/upload",
    "/api/bbs/ai/kb/upload/limits",
    "/api/bbs/ai/kb/attachments",
}

# 带路径参数、且要求管理员的前缀（上传进度 / 删除附件）
ADMIN_ONLY_PREFIXES = {
    "/api/bbs/ai/kb/upload/status/": "查看文档入库进度",
    "/api/bbs/ai/kb/attachments/": "删除已上传的文档",
}

# 权限拒绝时给前端看的动作名（与 requireAdmin(...) 的文案保持一致）
ADMIN_ACTIONS = {
    "/api/bbs/ai/kb/sync": "同步知识库",
    "/api/bbs/ai/kb/sync/status": "查看知识库同步状态",
    "/api/bbs/ai/kb/upload": "上传文档到知识库",
    "/api/bbs/ai/kb/upload/limits": "查看文档上传限制",
    "/api/bbs/ai/kb/attachments": "查看已上传的文档",
}

# 非管理员可读、但要摘掉内部字段的路径（与 AiBotController.kbStatus 的脱敏一致）
SANITIZE_FOR_GUEST = {"/api/bbs/ai/kb/status": ["collection"]}

# 联调时用来切换身份：
#   - 请求头 X-Dev-Role: admin（适合 curl / Postman）
#   - Cookie devRole=admin（适合浏览器：控制台执行 document.cookie='devRole=admin;path=/' 后刷新）
DEV_ROLE_HEADER = "X-Dev-Role"
DEV_ROLE_COOKIE = "devRole"

# /about 由 Java 侧就地生成，桩这里给出同样内容的静态版本
ABOUT = {
    "name": "小罗Bot",
    "version": "2.0.0",
    "description": "开罗论坛内置的 AI 搜索引擎助手：多智能体协作 + 多模态 RAG，支持按需联网搜索。",
    "agentEndpoint": "/api/bbs/ai/chat/stream",
    "capabilities": [
        "多智能体协作：调度、论坛检索、联网搜索、多模态理解、答案合成、质量评估",
        "多模态 RAG：文章正文、图片描述、评论、资源、标签统一检索",
        "可选联网搜索：论坛内查不到相关内容时，再获取网络内容作答",
        "多轮对话：会话级上下文与长期记忆",
    ],
    "entryPoints": ["/bot（页面）", "/api/bbs/ai/chat/stream（SSE）", "/api/bbs/ai/chat（JSON）"],
}


def success(data):
    """论坛统一响应信封（与 ResponseResult 一致）。"""
    return {"code": 0, "desc": "成功", "data": data}


def failure(code, desc, data=None):
    return {"code": code, "desc": desc, "data": data}


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # 静音默认的访问日志，改用下面简短的格式
    def log_message(self, fmt, *args):  # noqa: A003
        sys.stderr.write("[stub] %s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------------
    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _ai_path(self, path: str):
        """把浏览器路径映射到 AI 服务路径；未登记的路径返回 None。"""
        if path in ROUTE_MAP:
            return ROUTE_MAP[path]
        for prefix, ai_prefix in ROUTE_PREFIX_MAP.items():
            if path.startswith(prefix):
                return ai_prefix + path[len(prefix):]
        return None

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        self._dispatch("GET")

    def do_POST(self):  # noqa: N802
        self._dispatch("POST")

    def do_DELETE(self):  # noqa: N802
        self._dispatch("DELETE")

    # ------------------------------------------------------------------
    def _is_admin(self) -> bool:
        """联调身份：请求头或 Cookie 里标记 admin 就当管理员，否则按游客。

        浏览器不方便自定义请求头，所以额外支持 Cookie ——
        在控制台执行 ``document.cookie='devRole=admin;path=/'`` 后刷新页面即可看到管理员视图。
        """
        if (self.headers.get(DEV_ROLE_HEADER) or "").strip().lower() == "admin":
            return True
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            key, _, value = part.strip().partition("=")
            if key == DEV_ROLE_COOKIE and value.strip().lower() == "admin":
                return True
        return False

    def _dispatch(self, method: str):
        try:
            self._dispatch_inner(method)
        except Exception as e:  # noqa: BLE001
            # 单个请求出错不要把连接直接掐掉：给个 JSON 错误，方便定位
            sys.stderr.write(f"[stub] 处理 {method} {self.path} 异常：{e}\n")
            try:
                self._json(failure(-1, f"网关桩内部错误：{e}"))
            except Exception:
                pass

    def _dispatch_inner(self, method: str):
        path, _, query = self.path.partition("?")
        if not path.startswith("/api/bbs/ai"):
            self._json(failure(4, f"网关桩只实现了 /api/bbs/ai/**，收到 {path}"), status=404)
            return

        is_admin = self._is_admin()

        # ---- 权限：与 AiBotController.requireAdmin 保持一致 ----
        denied_action = None
        if path in ADMIN_ONLY_PATHS:
            denied_action = ADMIN_ACTIONS.get(path, "执行该操作")
        else:
            for prefix, action in ADMIN_ONLY_PREFIXES.items():
                if path.startswith(prefix):
                    denied_action = action
                    break
        if denied_action and not is_admin:
            # 对应 ResponseCode.URL_ACCESS_REFUSED(1) + requireAdmin 的提示语
            self._json(failure(1, "只有管理员可以" + denied_action))
            return

        # /about 由 Java 侧就地生成，桩这里也本地生成，不打扰 AI 服务
        if path == "/api/bbs/ai/about":
            payload = dict(ABOUT)
            payload["currentUserIsAdmin"] = is_admin
            self._json(success(payload))
            return

        ai_path = self._ai_path(path)
        if ai_path is None:
            self._json(failure(4, f"网关桩未登记该路径：{path}"), status=404)
            return

        # 生产环境里 uploader 由 bbs-rest 从 SSO 上下文注入（知识条目的 author 字段），
        # 桩没有登录态，这里补一个占位值，保证入库记录仍有来源。
        if path == "/api/bbs/ai/kb/upload" and "uploader=" not in query:
            query = (query + "&" if query else "") + "uploader=dev-admin"

        target = f"{AI_BASE}{ai_path}" + (f"?{query}" if query else "")

        if path in STREAM_PATHS:
            self._proxy_stream(method, target, self._read_body())
        elif path in MULTIPART_PATHS:
            # 文件上传：把原始 multipart 体原样转发（含 boundary），不做解析
            self._proxy_raw(method, target, self.headers.get("Content-Type"))
        else:
            self._proxy_json(method, target, self._read_body(),
                             strip_fields=None if is_admin else SANITIZE_FOR_GUEST.get(path))

    def _proxy_json(self, method: str, target: str, body: bytes, strip_fields=None):
        """普通接口：拿到 AI 服务的 JSON，脱敏后再包一层论坛信封。"""
        import httpx

        try:
            with httpx.Client(timeout=300) as client:
                response = client.request(
                    method, target, content=body or None,
                    headers={"Content-Type": "application/json"},
                )
            data = response.json() if response.content else None
        except Exception as e:  # noqa: BLE001
            self._json(failure(-3, f"AI 服务不可用：{e}"), status=200)
            return

        if response.status_code >= 400:
            detail = (data or {}).get("detail") if isinstance(data, dict) else None
            self._json(failure(-1, detail or f"AI 服务返回 {response.status_code}"), status=200)
            return

        # 与 AiBotController.kbStatus 的脱敏逻辑保持一致
        if strip_fields and isinstance(data, dict):
            for field in strip_fields:
                data.pop(field, None)

        self._json(success(data))

    def _proxy_raw(self, method: str, target: str, content_type: str):
        """原样转发请求体（multipart 上传用）——不能解析再拼，否则 boundary 会对不上。"""
        import httpx

        body = self._read_body()
        try:
            with httpx.Client(timeout=900) as client:
                response = client.request(
                    method, target, content=body or None,
                    headers={"Content-Type": content_type or "application/octet-stream"},
                )
            data = response.json() if response.content else None
        except Exception as e:  # noqa: BLE001
            self._json(failure(-3, f"AI 服务不可用：{e}"))
            return

        if response.status_code >= 400:
            detail = (data or {}).get("detail") if isinstance(data, dict) else None
            self._json(failure(-1, detail or f"AI 服务返回 {response.status_code}"))
            return
        self._json(success(data))

    def _proxy_stream(self, method: str, target: str, body: bytes):
        """SSE 接口：边读上游边写下游，保证"打字机"效果。"""
        import httpx

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        # 用 chunked 传输，这样不必事先知道长度
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def write_chunk(payload: bytes):
            if not payload:
                return
            self.wfile.write(b"%X\r\n" % len(payload))
            self.wfile.write(payload)
            self.wfile.write(b"\r\n")
            self.wfile.flush()

        try:
            with httpx.Client(timeout=600) as client:
                with client.stream(
                    method, target, content=body or None,
                    headers={"Content-Type": "application/json",
                             "Accept": "text/event-stream"},
                ) as response:
                    if response.status_code >= 400:
                        write_chunk(
                            ("event: error\ndata: "
                             + json.dumps({"message": f"AI 服务返回 {response.status_code}"},
                                          ensure_ascii=False)
                             + "\n\nevent: end\ndata: {}\n\n").encode("utf-8"))
                    else:
                        for chunk in response.iter_bytes():
                            write_chunk(chunk)
        except Exception as e:  # noqa: BLE001
            try:
                write_chunk(
                    ("event: error\ndata: "
                     + json.dumps({"message": f"AI 服务不可用：{e}"}, ensure_ascii=False)
                     + "\n\nevent: end\ndata: {}\n\n").encode("utf-8"))
            except Exception:
                pass
        finally:
            # 结束 chunked 编码
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="本地联调网关桩（模拟 bbs-rest 的 /api/bbs/ai/**）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7010,
                        help="默认 7010，与 bbs-rest 一致，这样前端 vue.config.js 的代理不用改")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print("=" * 68)
    print("  小罗Bot 本地联调网关桩（仅用于前端调试，不做真实登录校验）")
    print(f"  监听：http://{args.host}:{args.port}/api/bbs/ai/**")
    print(f"  转发：{AI_BASE}")
    print("  身份：默认按游客；加请求头 X-Dev-Role: admin 可模拟管理员")
    print("        仅管理员可用：/kb/sync、/kb/sync/status")
    print("        游客读 /kb/status 会被摘掉 collection（与 bbs-rest 一致）")
    print("  前端：npm run serve 后访问 http://localhost:8082/bot")
    print("=" * 68)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
