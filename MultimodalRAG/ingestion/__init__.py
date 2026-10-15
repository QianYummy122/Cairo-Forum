"""小罗Bot 的知识库接入包。

- :mod:`ingestion.forum_source` —— 论坛内容数据源（对接 springboot 网关 / MySQL / 本地快照）
- :mod:`ingestion.forum_ingest` —— 分块、多模态向量化、增量写入 Milvus
"""
from ingestion.forum_source import (  # noqa: F401
    ForumDocument, MysqlForumSource, RestForumSource, LocalSnapshotSource,
    build_sources, pick_source, source_status,
)
from ingestion.forum_ingest import (  # noqa: F401
    chunk_text, ingest_documents, sync_forum, sync_pdf_markdown,
)

__all__ = [
    "ForumDocument", "RestForumSource", "MysqlForumSource", "LocalSnapshotSource",
    "build_sources", "pick_source", "source_status",
    "chunk_text", "ingest_documents", "sync_forum", "sync_pdf_markdown",
]
