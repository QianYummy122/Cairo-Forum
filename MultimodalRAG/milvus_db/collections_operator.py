"""Milvus 集合定义与创建（配置来自 config.yml -> milvus）。

三个集合各司其职：

===============================  ==========================================
集合                              用途
===============================  ==========================================
``t_knowledge_collection``       ★ 小罗Bot 的统一多模态知识库：
                                 论坛文章/评论/资源/标签 + PDF 文档解析结果，
                                 文本与图片共用同一个 1024 维向量空间。
``t_doc_collection``             旧版 PDF 知识库（保留兼容历史数据）。
``t_context_collection``         长期记忆：小罗Bot 的历史回答，用于多轮复用。
===============================  ==========================================
"""
from pymilvus import MilvusClient, DataType, Function, FunctionType

from utils.config import CONFIG

# 集合名称
COLLECTION_NAME = CONFIG.get("milvus.doc_collection")
KNOWLEDGE_COLLECTION_NAME = CONFIG.get("milvus.knowledge_collection", "t_knowledge_collection")
CONTEXT_COLLECTION_NAME = CONFIG.get("milvus.context_collection")

# 向量维度
DIM = CONFIG.get("milvus.dim")

# 本地 Milvus Lite，数据文件路径来自配置
_MILVUS_DB_PATH = str(CONFIG.path("milvus.db_path"))

client = MilvusClient(uri=_MILVUS_DB_PATH)


def _analyzer_params() -> dict:
    """中文分词配置。"""
    return {
        "tokenizer": CONFIG.get("milvus.tokenizer", "jieba"),
        "filter": [CONFIG.get("milvus.analyzer_filter", "cnalphanumonly")],
    }


def _bm25_index_params() -> dict:
    """稀疏向量（BM25）索引参数。"""
    sparse = CONFIG.section("milvus.sparse_index")
    return {
        "inverted_index_algo": sparse.get("inverted_index_algo", "DAAT_MAXSCORE"),
        # 词频 (TF) 饱和度：越大高频词贡献越线性
        "bm25_k1": sparse.get("bm25_k1", 1.2),
        # 文档长度归一化强度：越大对长文档惩罚越强
        "bm25_b": sparse.get("bm25_b", 0.75),
    }


def create_db_collection():
    """创建知识库集合 t_doc_collection。"""
    text_max_length = CONFIG.get("milvus.text_max_length", 6000)
    field_max_length = CONFIG.get("milvus.field_max_length", 1000)

    schema = client.create_schema()
    schema.add_field(field_name='id', datatype=DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(field_name='text', datatype=DataType.VARCHAR, max_length=text_max_length,
                     enable_analyzer=True, analyzer_params=_analyzer_params())
    schema.add_field(field_name='category', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='filename', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='filetype', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='image_path', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='title', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='sparse', datatype=DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(field_name='dense', datatype=DataType.FLOAT_VECTOR, dim=DIM)

    bm25_function = Function(
        name="text_bm25_emb",
        input_field_names=["text"],
        output_field_names=["sparse"],
        function_type=FunctionType.BM25,
    )
    schema.add_function(bm25_function)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="sparse",
        index_name="sparse_inverted_index",
        index_type=CONFIG.get("milvus.sparse_index.index_type", "SPARSE_INVERTED_INDEX"),
        metric_type=CONFIG.get("milvus.sparse_index.metric_type", "BM25"),
        params=_bm25_index_params(),
    )
    index_params.add_index(
        field_name="dense",
        index_name="dense_inverted_index",
        index_type=CONFIG.get("milvus.dense_index.index_type", "AUTOINDEX"),
        metric_type=CONFIG.get("milvus.dense_index.metric_type", "IP"),
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params,
    )


def create_store_collection():
    """创建长期记忆（对话上下文）集合 t_context_collection。"""
    text_max_length = CONFIG.get("milvus.text_max_length", 6000)
    field_max_length = CONFIG.get("milvus.field_max_length", 1000)

    schema = client.create_schema()
    schema.add_field(field_name='id', datatype=DataType.INT64, is_primary=True, auto_id=True)
    # 某一条聊天记录的文本内容
    schema.add_field(field_name='context_text', datatype=DataType.VARCHAR, max_length=text_max_length,
                     enable_analyzer=True, analyzer_params=_analyzer_params())
    # 用户名
    schema.add_field(field_name='user', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='timestamp', datatype=DataType.INT64, nullable=True)
    schema.add_field(field_name='message_type', datatype=DataType.VARCHAR, max_length=100, nullable=True)
    schema.add_field(field_name='context_sparse', datatype=DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(field_name='context_dense', datatype=DataType.FLOAT_VECTOR, dim=DIM)

    bm25_function = Function(
        name="text_bm25_emb",
        input_field_names=["context_text"],
        output_field_names=["context_sparse"],
        function_type=FunctionType.BM25,
    )
    schema.add_function(bm25_function)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="context_sparse",
        index_name="context_sparse_inverted_index",
        index_type=CONFIG.get("milvus.sparse_index.index_type", "SPARSE_INVERTED_INDEX"),
        metric_type=CONFIG.get("milvus.sparse_index.metric_type", "BM25"),
        params=_bm25_index_params(),
    )
    index_params.add_index(
        field_name="context_dense",
        index_name="context_dense_inverted_index",
        index_type=CONFIG.get("milvus.dense_index.index_type", "AUTOINDEX"),
        metric_type=CONFIG.get("milvus.dense_index.metric_type", "IP"),
    )

    client.create_collection(
        collection_name=CONTEXT_COLLECTION_NAME,
        schema=schema,
        index_params=index_params,
    )


def create_knowledge_collection():
    """创建小罗Bot 的统一多模态知识库集合 t_knowledge_collection。

    相比旧的 ``t_doc_collection``，这里为"论坛内容"补齐了必要的业务字段：

    - ``doc_id``     业务主键（如 ``article:43``），支持增量刷新时按来源删除重建；
    - ``source_type``来源类型（article / comment / resource / label / snapshot / pdf）；
    - ``source_url`` 论坛内可跳转路径，回答里作为引用链接给用户；
    - ``labels``     标签（逗号拼接），参与 BM25 稀疏检索，提升"按标签问"的命中率。
    """
    text_max_length = CONFIG.get("milvus.text_max_length", 6000)
    field_max_length = CONFIG.get("milvus.field_max_length", 1000)

    schema = client.create_schema()
    schema.add_field(field_name='id', datatype=DataType.INT64, is_primary=True, auto_id=True)
    # 参与 BM25 稀疏向量化的正文（也是混合检索的文本字段）
    schema.add_field(field_name='text', datatype=DataType.VARCHAR, max_length=text_max_length,
                     enable_analyzer=True, analyzer_params=_analyzer_params())
    # category: text / image —— 决定该条目是文本知识还是图片知识
    schema.add_field(field_name='category', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='doc_id', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='source_type', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='title', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    # 展示与引用用的来源名（如 "文章《Hello》"）
    schema.add_field(field_name='filename', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='source_url', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='author', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='created_at', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='labels', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    schema.add_field(field_name='filetype', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    # 图片条目的原始地址（URL 或本地路径），回答里用 Markdown 图片语法渲染
    schema.add_field(field_name='image_path', datatype=DataType.VARCHAR, max_length=field_max_length, nullable=True)
    # 图片的文本描述（多模态模型生成），同时也是该条目的稀疏检索文本
    schema.add_field(field_name='description', datatype=DataType.VARCHAR,
                     max_length=CONFIG.get("milvus.description_max_length", 2000), nullable=True)
    schema.add_field(field_name='sparse', datatype=DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(field_name='dense', datatype=DataType.FLOAT_VECTOR, dim=DIM)

    bm25_function = Function(
        name="text_bm25_emb",
        input_field_names=["text"],
        output_field_names=["sparse"],
        function_type=FunctionType.BM25,
    )
    schema.add_function(bm25_function)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="sparse",
        index_name="knowledge_sparse_inverted_index",
        index_type=CONFIG.get("milvus.sparse_index.index_type", "SPARSE_INVERTED_INDEX"),
        metric_type=CONFIG.get("milvus.sparse_index.metric_type", "BM25"),
        params=_bm25_index_params(),
    )
    index_params.add_index(
        field_name="dense",
        index_name="knowledge_dense_inverted_index",
        index_type=CONFIG.get("milvus.dense_index.index_type", "AUTOINDEX"),
        metric_type=CONFIG.get("milvus.dense_index.metric_type", "IP"),
    )

    client.create_collection(
        collection_name=KNOWLEDGE_COLLECTION_NAME,
        schema=schema,
        index_params=index_params,
    )


def ensure_collections():
    """确保各个集合都存在，不存在则自动创建。"""
    existing = client.list_collections()
    if KNOWLEDGE_COLLECTION_NAME not in existing:
        print(f"[Milvus] 创建集合: {KNOWLEDGE_COLLECTION_NAME}")
        create_knowledge_collection()
    if COLLECTION_NAME not in existing:
        print(f"[Milvus] 创建集合: {COLLECTION_NAME}")
        create_db_collection()
    if CONTEXT_COLLECTION_NAME not in existing:
        print(f"[Milvus] 创建集合: {CONTEXT_COLLECTION_NAME}")
        create_store_collection()


def drop_knowledge_docs(doc_ids: list) -> int:
    """按 ``doc_id`` 删除知识库条目（增量同步时先删后插），返回删除条数。"""
    if not doc_ids:
        return 0
    quoted = ", ".join(f'"{d}"' for d in doc_ids)
    res = client.delete(collection_name=KNOWLEDGE_COLLECTION_NAME, filter=f"doc_id in [{quoted}]")
    return int(res.get("delete_count", 0)) if isinstance(res, dict) else 0


def flush_knowledge() -> bool:
    """把内存/WAL 里的写入落盘到 parquet。

    **为什么必须调**：Milvus Lite 是嵌入式实现，写入先进 WAL，之后才合并成 parquet。
    如果进程在这中间被强杀（任务管理器结束进程、`kill -9`），WAL 会写坏，
    下次打开时 Milvus 会丢弃这段 WAL —— 实测出现过"manifest 已推进、但快照没被读回"
    导致整个集合查询为 0 条的情况（parquet 里的数据其实还在）。

    写完就 flush 能把"可能丢失的窗口"压到最小。返回是否成功，调用方可以只记日志。
    """
    try:
        client.flush(collection_name=KNOWLEDGE_COLLECTION_NAME)
        return True
    except Exception as e:  # noqa: BLE001
        # flush 失败不影响本次写入的结果，但要留下痕迹
        print(f"[Milvus] flush 失败：{e}")
        return False


def knowledge_stats() -> dict:
    """知识库统计（供 /kb/status 接口与页面展示）。

    **不要在这里静默吞异常**：早先的实现把查询失败也返回成 0 条，
    结果一次 WAL 损坏被伪装成"知识库是空的，一切正常"，
    排查时白绕了一大圈。现在失败会带上 ``ok: false`` 与 ``error``，
    页面据此提示"统计不可用"，而不是显示一个误导性的 0。
    """
    stats: dict = {
        "collection": KNOWLEDGE_COLLECTION_NAME,
        "total": 0,
        "bySourceType": {},
        "ok": True,
        "error": "",
    }
    try:
        client.load_collection(KNOWLEDGE_COLLECTION_NAME)
        total = client.query(collection_name=KNOWLEDGE_COLLECTION_NAME, filter="id >= 0",
                             output_fields=["count(*)"])
        stats["total"] = total[0].get("count(*)") if total else 0
    except Exception as e:  # noqa: BLE001
        stats["ok"] = False
        stats["error"] = f"读取知识库失败：{e}"
        print(f"[Milvus] knowledge_stats 读取失败：{e}")
        return stats

    by_type = {}
    # 顺序与前端「按来源」的展示顺序一致；attachment 是页面上传的文档附件
    for stype in ("article", "comment", "resource", "label", "attachment", "pdf", "snapshot"):
        try:
            rows = client.query(collection_name=KNOWLEDGE_COLLECTION_NAME,
                                filter=f'source_type == "{stype}"',
                                output_fields=["count(*)"])
            by_type[stype] = rows[0].get("count(*)") if rows else 0
        except Exception as e:  # noqa: BLE001
            by_type[stype] = 0
            stats["ok"] = False
            stats["error"] = f"分类统计失败（{stype}）：{e}"
    stats["bySourceType"] = by_type

    # 一个额外的健康信号：集合读得出来、但一条都没有 —— 这通常意味着数据被清空或损坏，
    # 值得在日志里留一条明显的记录（页面也会因此显示 0，不至于让人以为"还没同步"）。
    if stats["total"] == 0:
        print("[Milvus] 注意：知识库当前为 0 条。若是刚重置过可忽略；"
              "否则请检查 milvus_local.db 下的 parquet 是否还在（见 flush_knowledge 的说明）。")
    return stats


# 模块导入时自动确保集合存在
ensure_collections()


if __name__ == '__main__':
    # 查看集合信息
    res = client.describe_collection(collection_name=COLLECTION_NAME)
    print(res)
