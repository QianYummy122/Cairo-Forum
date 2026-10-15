"""
小罗Bot 的 RAG 系统离线评估脚本
用法：python evaluate_full.py

评估对象是**小罗Bot 实际使用的检索器**（统一多模态知识库 + 混合检索），
所以这里跑的分数能直接反映线上问答的检索质量。

想让评估更有意义：先把论坛内容同步进知识库（.\\start_kb_sync.ps1），
再把下面的测试集改成你论坛里真实存在的话题。
"""
import asyncio
import json
from typing import Dict, List

from ragas import SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    ContextRelevance,
    ResponseRelevancy,
    Faithfulness,
    LLMContextPrecisionWithoutReference,
    ContextRecall,
    AnswerCorrectness,
    AnswerSimilarity,
)

from evaluate.evaluate_self import RAGEvaluator
from milvus_db.forum_retriever import get_retriever
from my_llm import llm, embedding
from utils.config import CONFIG


# ============ 测试集（请按你的论坛内容调整） ============
# 前两条是"论坛里应该能查到"的（标签/资源导航），
# 第三条是"论坛里查不到"的（用于验证联网兜底那条分支的必要性）。
TEST_CASES = [
    {
        "question": "论坛里有哪些标签？",
        "reference": "论坛标签包括公告、推荐、优化、插件、Java、Docker、Kubernetes、Markdown 等。",
    },
    {
        "question": "论坛的资源导航里有哪些设计素材网站？",
        "reference": "资源导航里包含 everypixel、Kaboom Pics、colorhub、mixkit、coverr 等图片/视频素材站。",
    },
    {
        "question": "论坛里有没有介绍开罗论坛定位的文章？",
        "reference": "目前站内没有专门说明论坛定位的文章。",
    },
]
# ================================================


async def evaluate_single(test_case: Dict, retriever, rag_evaluator) -> Dict:
    """评估单个测试用例"""
    question = test_case["question"]
    reference = test_case.get("reference", "")

    # 1. 检索（与小罗Bot 线上走的是同一个检索器）
    result = retriever.search(query=question)
    contexts = result["hits"]

    if not contexts:
        return {
            "question": question,
            "error": "检索结果为空",
            "relevance": result.get("relevance", 0.0),
            "context_relevance": 0,
            "response_relevancy": 0,
            "faithfulness": 0,
            "context_precision": 0,
            "context_recall": 0,
            "answer_correctness": 0,
        }

    # 2. 让 LLM 生成回答
    from langchain_core.prompts import ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages([
        ("system", "根据上下文回答问题，如果上下文中没有答案就说不知道。"),
        ("user", f"问题：{question}\n\n上下文：\n" + "\n".join([c.get("text", "") for c in contexts])),
    ])
    chain = prompt | llm
    answer = chain.invoke({}).content

    # 3. 计算各项指标
    sample = SingleTurnSample(
        user_input=question,
        retrieved_contexts=[c.get("text", "") for c in contexts],
        response=answer,
        reference=reference,
    )

    scores = {
        "question": question,
        "relevance": round(float(result.get("relevance") or 0.0), 4),
        "context_relevance": await rag_evaluator.evaluate_context(question, [c.get("text", "") for c in contexts]),
        "response_relevancy": await rag_evaluator.evaluate_answer(question, contexts, answer),
        "faithfulness": await rag_evaluator.scorers["faithfulness"].single_turn_ascore(sample) if "faithfulness" in rag_evaluator.scorers else None,
        "context_precision": await rag_evaluator.scorers["context_precision"].single_turn_ascore(sample) if "context_precision" in rag_evaluator.scorers else None,
        "context_recall": await rag_evaluator.scorers["context_recall"].single_turn_ascore(sample) if "context_recall" in rag_evaluator.scorers else None,
        "answer_correctness": await rag_evaluator.scorers["answer_correctness"].single_turn_ascore(sample) if "answer_correctness" in rag_evaluator.scorers else None,
        "retrieved_count": len(contexts),
    }

    return scores


class FullRAGEvaluator(RAGEvaluator):
    """完整 RAG 评估器，继承 RAGEvaluator 的 evaluate_context 和 evaluate_answer 方法"""

    def __init__(self):
        self.llm_wrapper = LangchainLLMWrapper(llm)
        self.emb_wrapper = LangchainEmbeddingsWrapper(embedding)
        super().__init__(self.llm_wrapper, self.emb_wrapper)
        self.scorers = {
            "faithfulness": Faithfulness(llm=self.llm_wrapper),
            "context_precision": LLMContextPrecisionWithoutReference(llm=self.llm_wrapper),
            "context_recall": ContextRecall(llm=self.llm_wrapper),
            "answer_correctness": AnswerCorrectness(
                llm=self.llm_wrapper,
                answer_similarity=AnswerSimilarity(
                    embeddings=self.emb_wrapper,
                ),
            ),
        }
        # 小罗Bot 实际使用的统一知识库检索器（论坛 + 文档）
        self.retriever = get_retriever()

    async def run_all(self, test_cases: List[Dict]) -> List[Dict]:
        """运行全部测试"""
        results = []
        for i, tc in enumerate(test_cases, 1):
            print(f"[{i}/{len(test_cases)}] 测试: {tc['question']}")
            result = await evaluate_single(tc, self.retriever, self)
            results.append(result)
            # 打印单项结果
            for k, v in result.items():
                if k not in ["question", "error"] and v is not None:
                    print(f"    {k}: {v:.3f}" if isinstance(v, float) else f"    {k}: {v}")
            print()
        return results

    def print_summary(self, results: List[Dict]):
        """打印汇总统计"""
        print("\n" + "=" * 60)
        print(" 评估汇总")
        print("=" * 60)

        metrics = ["relevance", "context_relevance", "response_relevancy", "faithfulness",
                   "context_precision", "context_recall", "answer_correctness"]

        for metric in metrics:
            values = [r[metric] for r in results if r.get(metric) is not None]
            if values:
                avg = sum(values) / len(values)
                print(f"  {metric:25s}: 平均 {avg:.3f}  (测试 {len(values)} 条)")

        print(f"\n  总测试数: {len(results)}")
        print(f"  检索成功: {sum(1 for r in results if 'error' not in r)}")
        print(f"  检索失败: {sum(1 for r in results if 'error' in r)}")
        print("=" * 60)


async def main():
    evaluator = FullRAGEvaluator()
    results = await evaluator.run_all(TEST_CASES)
    evaluator.print_summary(results)

    # 保存结果
    output_file = CONFIG.path("evaluate.output_file", "evaluation_results.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到 {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
