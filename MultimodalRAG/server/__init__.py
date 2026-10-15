"""小罗Bot 的 HTTP 服务包（FastAPI）。

启动：``python -m server.app``（默认 127.0.0.1:7861）
"""
from server.app import app  # noqa: F401

__all__ = ["app"]
