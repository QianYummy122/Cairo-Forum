"""小罗Bot 的统一多模态知识库检索器。

与旧版 ``db_retriever.MilvusRetriever``（只面向 PDF 知识库）的区别：

1. **面向论坛**：命中结果自带 ``source_url`` / ``source_type`` / ``author``，
   可以直接在回答里生成"论坛内可点开的引用"；
2. **多模态**：文本用混合检索（BM25 + 稠密向量），图片用稠密检索，
   两者共用一个 1024 维向量空间，所以"用一段文字搜出一张图"是成立的；
3. **可判定"没找到"**：额外提供 :meth:`relevance_probe`，
   用稠密余弦相似度给出"知识库里到底有没有相关内容"的量化判据，
   这是小罗Bot 决定要不要转联网搜索的关键信号之一。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pymilvus import AnnSearchRequest, WeightedRanker

from milvus_db.collections_operator import (
    CONTEXT_COLLECTION_NAME, KNOWLEDGE_COLLECTION_NAME, client,
)
from utils.config import CONFIG
from utils.embeddings_utils import call_dashscope_once, image_to_base64, normalize_image
from utils.log_utils import log

# 检索输出字段（与 t_knowledge_collection 的 schema 对应）
_OUTPUT_FIELDS = [
    "text", "category", "doc_id", "source_type", "title", "filename",
    "source_url", "author", "created_at", "labels", "filetype",
    "image_path", "description",
]

# 论坛内容类型 → 展示名（回答里的"资料来源"）
_SOURCE_LABEL = {
    "article": "论坛文章",
    "comment": "论坛评论",
    "resource": "论坛资源",
    "label": "论坛标签",
    "snapshot": "导入文档",
    "pdf": "解析文档",
    "image": "论坛图片",
}


class KnowledgeRetriever:
    """统一知识库的混合检索器。"""

    def __init__(self, collection_name: str = None):
        self.collection_name = collection_name or KNOWLEDGE_COLLECTION_NAME
        self.top_k = CONFIG.get("retrieval.agent_top_k", 5)
        self.search_limit = CONFIG.get("retrieval.agent_search_limit", 20)
        self.nprobe = CONFIG.get("retrieval.nprobe", 10)
        self.drop_ratio_search = CONFIG.get("retrieval.drop_ratio_search", 0.2)
        self.sparse_weight = CONFIG.get("retrieval.sparse_weight", 1.0)
        self.dense_weight = CONFIG.get("retrieval.dense_weight", 1.0)
        self.dense_metric = CONFIG.get("milvus.dense_index.metric_type", "IP")
        self.sparse_metric = CONFIG.get("milvus.sparse_index.metric_type", "BM25")

    # ------------------------------------------------------------------
    # 嵌入
    # ------------------------------------------------------------------
    def embed_query(self, text: str) -> List[float]:
        """文本 → 向量（图文统一空间）。"""
        ok, vector, status, _ = call_dashscope_once([{"text": text}])
        if not ok:
            log.error(f"KnowledgeRetriever: 查询向量化失败 status={status}")
            return []
        return vector

    def embed_image(self, image: str) -> List[float]:
        """图片（URL / 本地路径 / data URI）→ 向量。"""
        if image.startswith("data:image"):
            api_image = image
        else:
            api_image = normalize_image(image)[0]
        if not api_image:
            log.warning(f"KnowledgeRetriever: 图片无法规范化，跳过 → {str(image)[:80]}")
            return []
        ok, vector, status, _ = call_dashscope_once([{"image": api_image}])
        if not ok:
            log.error(f"KnowledgeRetriever: 图片向量化失败 status={status}")
            return []
        return vector

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    def _load(self) -> None:
        client.load_collection(self.collection_name)

    def hybrid_search(
        self,
        query_text: str,
        query_vector: List[float],
        limit: int = None,
        source_types: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """BM25 稀疏 + 稠密向量的混合检索（WeightedRanker 融合重排）。"""
        limit = limit or self.search_limit
        expr = self._filter_expr(source_types)

        dense_req = AnnSearchRequest(
            [query_vector], "dense",
            {"metric_type": self.dense_metric, "params": {"nprobe": self.nprobe}},
            limit=limit, expr=expr,
        )
        sparse_req = AnnSearchRequest(
            [query_text], "sparse",
            {"metric_type": self.sparse_metric, "params": {"drop_ratio_search": self.drop_ratio_search}},
            limit=limit, expr=expr,
        )
        rerank = WeightedRanker(self.sparse_weight, self.dense_weight)
        res = client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[sparse_req, dense_req],
            ranker=rerank,
            limit=limit,
            output_fields=_OUTPUT_FIELDS,
        )
        return res[0] if res else []

    def dense_search(self, query_vector: List[float], limit: int = None) -> List[Dict[str, Any]]:
        """纯稠密检索（图片查询走这里，因为图片无法参与 BM25）。"""
        limit = limit or self.search_limit
        res = client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            anns_field="dense",
            limit=limit,
            output_fields=_OUTPUT_FIELDS,
            search_params={"metric_type": self.dense_metric, "params": {"nprobe": self.nprobe}},
        )
        return res[0] if res else []

    @staticmethod
    def _filter_expr(source_types: List[str]) -> Optional[str]:
        if not source_types:
            return None
        quoted = ", ".join(f'"{s}"' for s in source_types)
        return f"source_type in [{quoted}]"

    # ------------------------------------------------------------------
    # 相关性判定
    # ------------------------------------------------------------------
    def relevance_probe(self, query_vector: List[float]) -> float:
        """返回知识库中与查询最相似的稠密余弦相似度（0~1，够用即可）。

        向量已 L2 归一化，所以 IP 距离就是余弦相似度。
        该值用于"论坛里到底有没有相关内容"的兜底判定：
        低于 ``agent.forum_relevance_threshold`` 即认为论坛里查不到。
        """
        if not query_vector:
            return 0.0
        try:
            self._load()
            res = self.dense_search(query_vector, limit=1)
        except Exception as e:
            log.warning(f"relevance_probe 失败：{e}")
            return 0.0
        if not res:
            return 0.0
        return float(res[0].get("distance", 0.0))

    # ------------------------------------------------------------------
    # 对外主入口
    # ------------------------------------------------------------------
    def search(
        self,
        query: str = None,
        image: str = None,
        top_k: int = None,
        source_types: List[str] = None,
    ) -> Dict[str, Any]:
        """检索知识库。

        :param query: 文本查询。纯图片查询时可为空。
        :param image: 图片查询（data URI / URL / 本地路径）。
        :param top_k: 最终返回条数。
        :param source_types: 只看某几类来源（如 ``["article"]``）。
        :returns: ``{"hits": [...], "relevance": float, "query": str, "hasImage": bool}``
        """
        top_k = top_k or self.top_k
        hits: List[Dict[str, Any]] = []
        relevance = 0.0

        try:
            self._load()
        except Exception as e:
            log.warning(f"加载集合 {self.collection_name} 失败：{e}")

        if image:
            vector = self.embed_image(image)
            if vector:
                relevance = self.relevance_probe(vector)
                hits = self.dense_search(vector, limit=self.search_limit)
        elif query:
            vector = self.embed_query(query)
            if vector:
                relevance = self.relevance_probe(vector)
                hits = self.hybrid_search(query, vector, source_types=source_types)
        else:
            return {"hits": [], "relevance": 0.0, "query": "", "hasImage": False}

        normalized = [self._to_hit(h) for h in hits]
        # 去掉没有正文、也没有图片的空条目
        normalized = [h for h in normalized if h["text"] or h["imagePath"]]
        return {
            "hits": normalized[:max(top_k, self.top_k)],
            "relevance": relevance,
            "query": query or "",
            "hasImage": bool(image),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _to_hit(raw: Dict[str, Any]) -> Dict[str, Any]:
        """把 Milvus 的原始命中整理成智能体/前端好用的结构。"""
        entity = raw.get("entity", raw) or {}
        source_type = entity.get("source_type") or ""
        category = entity.get("category") or "text"
        image_path = entity.get("image_path") or ""
        # 图片条目的"正文"其实是图片描述
        text = entity.get("text") or entity.get("description") or ""
        return {
            "id": raw.get("id"),
            "score": float(raw.get("distance", 0.0)),
            "text": text,
            "category": category,
            "sourceType": source_type,
            "sourceLabel": _SOURCE_LABEL.get(source_type, "相关内容"),
            "title": entity.get("title") or "",
            "filename": entity.get("filename") or "",
            "sourceUrl": entity.get("source_url") or "",
            "author": entity.get("author") or "",
            "createdAt": entity.get("created_at") or "",
            "labels": entity.get("labels") or "",
            "imagePath": image_path,
        }


class MemoryRetriever:
    """长期记忆检索器：找回该用户过去的高相似回答。

    集合 ``t_context_collection`` 由 :class:`graph.save_context.OptimizedMilvusAsyncWriter`
    写入（AI 的历次回答），这里按 ``user`` 过滤后做混合检索。
    它的作用是让"跨会话"的追问也能接上，例如用户第二天再问
    "上次你说的那个切换方式再讲讲"。

    与知识库检索的区别：记忆是**用户自己的历史**，不是论坛的公共知识，
    因此单独成类、单独标注来源，不参与"论坛里有没有"的判定。
    """

    def __init__(self, collection_name: str = None):
        self.collection_name = collection_name or CONTEXT_COLLECTION_NAME
        self.limit = CONFIG.get("agent.memory_top_k", 3)
        self.nprobe = CONFIG.get("retrieval.nprobe", 10)
        self.drop_ratio_search = CONFIG.get("retrieval.drop_ratio_search", 0.2)

    def search(self, query: str, user: str, threshold: float = None) -> List[Dict[str, Any]]:
        """返回与当前问题高度相关的历史回答（相似度低于阈值的不返回）。"""
        if not query or not user or user == "guest":
            # 访客没有稳定身份，跨会话记忆不可靠，直接不做记忆检索
            return []
        threshold = threshold if threshold is not None else CONFIG.get(
            "agent.memory_relevance_threshold", 0.82)

        vector = get_retriever().embed_query(query)
        if not vector:
            return []

        filter_expr = f'user == "{user}"'
        try:
            client.load_collection(self.collection_name)
            dense_req = AnnSearchRequest(
                [vector], "context_dense",
                {"metric_type": CONFIG.get("milvus.dense_index.metric_type", "IP"),
                 "params": {"nprobe": self.nprobe}},
                limit=self.limit, expr=filter_expr,
            )
            sparse_req = AnnSearchRequest(
                [query], "context_sparse",
                {"metric_type": CONFIG.get("milvus.sparse_index.metric_type", "BM25"),
                 "params": {"drop_ratio_search": self.drop_ratio_search}},
                limit=self.limit, expr=filter_expr,
            )
            res = client.hybrid_search(
                collection_name=self.collection_name,
                reqs=[sparse_req, dense_req],
                ranker=WeightedRanker(1.0, 1.0),
                limit=self.limit,
                output_fields=["context_text", "user", "timestamp"],
            )
            # 用稠密相似度单独判阈值（混合检索的融合分不适合直接比阈值）
            dense_res = client.search(
                collection_name=self.collection_name,
                data=[vector], anns_field="context_dense", limit=1,
                expr=filter_expr,
                output_fields=["context_text"],
                search_params={"metric_type": CONFIG.get("milvus.dense_index.metric_type", "IP"),
                               "params": {"nprobe": self.nprobe}},
            )
        except Exception as e:
            log.warning(f"MemoryRetriever 检索失败：{e}")
            return []

        best = dense_res[0][0].get("distance", 0.0) if dense_res and dense_res[0] else 0.0
        if float(best) < threshold:
            return []

        hits = []
        for raw in (res[0] if res else []):
            entity = raw.get("entity", raw) or {}
            text = entity.get("context_text") or ""
            if text:
                hits.append({
                    "text": text,
                    "score": float(raw.get("distance", 0.0)),
                    "similarity": round(float(best), 4),
                })
        return hits


# 全局单例（检索器无状态，可复用）
_retriever: Optional[KnowledgeRetriever] = None
_memory_retriever: Optional[MemoryRetriever] = None


def get_retriever() -> KnowledgeRetriever:
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeRetriever()
    return _retriever


def get_memory_retriever() -> MemoryRetriever:
    global _memory_retriever
    if _memory_retriever is None:
        _memory_retriever = MemoryRetriever()
    return _memory_retriever


def to_data_uri(image: str) -> str:
    """本地图片 → data URI（供多模态模型直接消费）。"""
    return image_to_base64(image)[0]


if __name__ == "__main__":
    r = get_retriever()
    out = r.search(query="开罗论坛")
    print("relevance =", out["relevance"])
    for h in out["hits"]:
        print("-", h["sourceLabel"], h["title"], "|", h["text"][:60])
