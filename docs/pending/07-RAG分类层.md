# RAG 分类层（搁置）

## 设计原文

`multi-llm-router-design.md` 提及 brentsWorks 三层门控：关键词 + **RAG** + LLM。

## 决策（已实施）

**明确不做 RAG 层** — 需 Pinecone 等向量库，个人工作流过重。

当前为两级：**L1 关键词 + L2 DeepSeek**。

## 若未来重启

- 需：embedding 服务、任务样本库、检索 top-k 再喂 L2
- 评估：在 `l2_eval_samples.json` 上对比准确率提升是否 worth 运维成本

## 状态

**搁置**，不列入近期里程碑。
