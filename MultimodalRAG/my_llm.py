"""项目用到的所有大模型 / 客户端实例（配置统一来自 config.yml）。"""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from zhipuai import ZhipuAI

from utils.config import CONFIG


def _build_chat(section: str) -> ChatOpenAI:
    """根据配置段构建 ChatOpenAI，temperature 为 null 时使用模型默认值。"""
    kwargs = {
        "model": CONFIG.get(f"{section}.model"),
        "api_key": CONFIG.get(f"{section}.api_key"),
        "base_url": CONFIG.get(f"{section}.base_url"),
    }
    temperature = CONFIG.get(f"{section}.temperature")
    if temperature is not None:
        kwargs["temperature"] = temperature
    return ChatOpenAI(**kwargs)


# 通用对话 / RAGAS 评估模型（OpenAI 兼容接口）
llm = _build_chat("llm.openai")

# 多模态大模型（图片描述生成、多模态对话）
multiModal_llm = _build_chat("llm.multimodal")

# 文本向量嵌入模型
embedding = OpenAIEmbeddings(
    api_key=CONFIG.get("llm.embedding.api_key"),
    base_url=CONFIG.get("llm.embedding.base_url"),
    model=CONFIG.get("llm.embedding.model"),
    dimensions=CONFIG.get("llm.embedding.dimensions"),
    check_embedding_ctx_length=CONFIG.get("llm.embedding.check_embedding_ctx_length"),
)

# 智谱 AI 客户端（网络搜索工具）
zhipuai_client = ZhipuAI(api_key=CONFIG.get("llm.zhipu.api_key"))
