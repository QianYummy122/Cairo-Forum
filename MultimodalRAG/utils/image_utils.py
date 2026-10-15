"""图片理解：把一张图片交给多模态模型，生成一段**可被检索到**的中文描述。

为什么单独成模块
----------------
原先这个函数放在 ``ingestion/forum_ingest.py`` 里，而那个模块在导入时就会打开
Milvus Lite（单进程独占锁）。结果是"只想解析一个文件"也必须先占住向量库，
解析层没法单独测试、也没法在别的场景复用。

这里刻意**不依赖任何向量库**，只有多模态模型客户端；``forum_ingest`` 再把它转出去，
老代码的 ``from ingestion.forum_ingest import describe_image`` 依旧可用。
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from my_llm import multiModal_llm
from utils.embeddings_utils import normalize_image
from utils.log_utils import log

# 图片描述生成提示词：结合前后文，让描述能被文字检索命中
IMAGE_PROMPT_WITH_CONTEXT = """你是多模态知识库的图片理解模块。请根据下面的上下文和图片内容，生成一段便于全文检索的中文描述。

上下文：
{context}

要求：
1. 描述图片里"看得见"的内容（类型、主体、关键文字/代码/表格要点）；
2. 如果图片是流程图/架构图/表格，请说明它表达的流程或数据结构；
3. **图中出现的文字请原样摘录**（报错信息、编号、字段名尤其重要）；
4. 长度不超过 300 个汉字，不要输出 Markdown 标题，不要臆造图中没有的信息。"""

IMAGE_PROMPT_PLAIN = """请用不超过 300 个汉字描述这张图片的内容，重点说明其中可被检索到的关键信息（文字、代码、表格、流程）。"""


def describe_image(image: str, context: str = "") -> str:
    """用多模态大模型给图片生成一段可检索的中文描述。

    :param image:   ``data:image/...;base64,...``、http(s) 图片地址，或本地文件路径
    :param context: 前后文（例如所在文档的正文摘要），用于提升描述的相关性
    :returns:       描述文本；失败时返回空串（调用方自己决定怎么兜底）
    """
    if image.startswith("data:image"):
        api_image = image
    else:
        api_image = normalize_image(image)[0]
    if not api_image:
        return ""

    prompt = IMAGE_PROMPT_WITH_CONTEXT.format(context=context[:800]) if context else IMAGE_PROMPT_PLAIN
    try:
        response = multiModal_llm.invoke([
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": api_image}},
            ])
        ])
        return str(response.content or "").strip()
    except Exception as e:  # noqa: BLE001
        log.warning(f"[image] 图片描述生成失败 {str(image)[:60]}：{e}")
        return ""


__all__ = ["describe_image", "IMAGE_PROMPT_WITH_CONTEXT", "IMAGE_PROMPT_PLAIN"]
