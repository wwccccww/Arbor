# ADR 0007：RAGAS 只评本轮注入文本上的生成忠实度

- 状态：已采纳
- 日期：2026-08-20

## 上下文

需要评估「回答有没有超出这次给模型看的记忆」。RAGAS 面向文档问答，LLM 当评委，不稳定、不适合作隔离与召回的主指标。引用 id 子集检查管不住未标注的胡话。

## 决策

- 检索、隔离、superseded、感知槽位：不用 RAGAS。
- generation 模式增加 `FaithfulnessScorer` 出站端口；默认实现为 RAGAS faithfulness。
- `contexts` 必须等于本轮注入的档案 + 摘要 + 事件 + MemoryItem 正文。
- 引用检查 `citations ⊆ injected_ids` 仍为代码 P0。
- 评委模型不得默认与 DeepSeek 生成器相同。
- CI 不跑 RAGAS；软门槛 faithfulness ≥ 0.8，仅 `answer`/`cite` 题。

## 后果

- 体检演示仍以 retrieval 红绿为主，可不展示 RAGAS。
- 多模态只评「有没有超出 caption/转写」，不评原图是否认对。
