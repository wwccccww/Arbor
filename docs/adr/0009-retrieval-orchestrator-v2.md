# ADR 0009：检索编排 v2（图扩展 + hybrid + 注入规划）

- 状态：已采纳
- 日期：2026-08-27

## 上下文

v1 检索为「单 query + 全局 ANN + 字符级 rerank」。在规模评测集上复合问、因果链、问法改写类题目 Recall 明显低于档案/时间题；`VectorIndex.search(filters)` 端口未落地；上下文超 token 时按列表尾部删记忆，易丢掉高分片段。

ADR-0002 已规定：分层记忆 + 事件树路由，不引入 GraphRAG 流水线。

## 决策

在 **不改变** `layered_tree` 默认策略与槽位顺序的前提下，增强 `retrieve()` 编排：

1. **事件图**：种子打分后沿 `temporal` / `caused_by` 边扩展 1～2 跳；scoped ANN + 全局 ANN RRF。
2. **Hybrid**：应用层 lexical scan（人设内 active 记忆）与向量结果 RRF；默认开启，可 `ARBOR_RETRIEVAL_HYBRID=off`。
3. **Rerank**：词级 lexical + 向量分 + 记忆类型权重 + MMR 去重。
4. **Query 规划**：默认 `rules` 拆复合问；`off` 关闭；`llm` 在配置 `DEEPSEEK_API_KEY` 时调用 Chat Completions 拆问，失败或无密钥时回退 `rules`。
5. **注入**：`memory_hits` 为 `{id, text, source, score}`；trim 按低分优先；`SendMessage` 返回 `retrieval_meta`。
6. **VectorIndex.filters**：`event_ids`、`types`、`exclude_ids` 在 Postgres / InMemory 落地。
7. **切块**：`ARBOR_CHUNK_MAX_CHARS` / `ARBOR_CHUNK_OVERLAP_CHARS` 可配置 overlap。

**不做**：GraphRAG、跨 persona 合并、PR 门禁绑 RAGAS。Postgres `text_tsv` 已落地（`0010`）；`query_plan=llm` 与 nightly bge 轨见 `eval_cli --embed bge`。

## 后果

- 夹具嵌入 ragas-v1：`layered_tree` Recall@5 约 0.90 → 0.904（泄漏仍为 0）。见 `eval/baselines/suite-ragas-v1.json`。
- 真 bge-m3 行为需 nightly 轨单独 baseline，不与夹具表混读。
- 改检索后须跑 `arbor-eval --suite ragas-v1` 并更新 baseline。

## 参考

- [architecture.md §6](../architecture.md)
- [evaluation.md](../evaluation.md)
- [local-dev.md](../local-dev.md) — `ARBOR_RETRIEVAL_*`
