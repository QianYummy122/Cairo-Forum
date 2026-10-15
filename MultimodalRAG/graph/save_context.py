"""长期记忆（对话上下文）的异步写入。

集合 ``t_context_collection`` 存的是小罗Bot 过去的回答，用于跨会话找回
"我之前问过什么、当时是怎么答的"。

**重要**：这里的向量必须和检索时用同一个嵌入模型（``multimodal-embedding-v1``，
见 ``utils/embeddings_utils.embed_texts``）。原实现用 ``text-embedding-v4`` 写入、
却用多模态模型检索，两个向量空间不可比，稠密那一路其实是失效的 —— 这里一并修掉。
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from pymilvus import MilvusClient

from milvus_db.collections_operator import client, CONTEXT_COLLECTION_NAME
from utils.embeddings_utils import embed_texts
from utils.log_utils import log

# 全局线程池用于异步操作
thread_pool = ThreadPoolExecutor(max_workers=5)  # 创建一个线程池


class OptimizedMilvusAsyncWriter:
    def __init__(self,
                 client: MilvusClient,
                 collection_name: str = CONTEXT_COLLECTION_NAME):

        self.client = client
        self.collection_name = collection_name

    def _get_dense_vector(self, text: str):
        """生成稠密向量（与检索端共用多模态嵌入空间）"""
        try:
            vectors = embed_texts([text], batch_size=1)
            return vectors[0] if vectors else None
        except Exception as e:
            log.exception(f"向量生成失败: {e}")
            return None

    def _sync_insert(self, data: Dict[str, Any]):
        """同步插入数据到Milvus"""
        if not data.get("context_dense"):
            log.warning("长期记忆跳过写入：向量为空")
            return
        try:
            result = self.client.insert(collection_name=self.collection_name, data=data)
            log.info(f"[Milvus] 成功插入 {result['insert_count']} 条记录。IDs 示例: {result['ids'][:5]}")
        except Exception as e:
            log.exception(f"插入数据到Milvus失败: {e}")

    async def async_insert(self, context_text: str, user: str, message_type: str = "AIMessage"):
        """异步插入数据"""
        data = {
            "context_text": context_text,
            "user": user,
            "timestamp": int(time.time() * 1000),  # 毫秒时间戳
            "message_type": message_type,
            "context_dense": self._get_dense_vector(context_text),
        }

        log.info(f"准备异步插入数据 - 用户：{user}, 类型：{message_type}, 文本长度：{len(context_text)}")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(thread_pool, self._sync_insert, data)


# 全局写入器实例（单例模式）
_milvus_writer_instance = None

def get_milvus_writer() -> OptimizedMilvusAsyncWriter:
    """获取全局Milvus写入器实例（单例）"""
    global _milvus_writer_instance
    if _milvus_writer_instance is None:
        _milvus_writer_instance = OptimizedMilvusAsyncWriter(
            client=client,
            collection_name=CONTEXT_COLLECTION_NAME
        )
    return _milvus_writer_instance