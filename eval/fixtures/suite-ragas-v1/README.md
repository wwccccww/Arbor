# suite-ragas-v1

默认规模评测集。由 `python3 eval/generate_testset.py --backend ragas --size 30` 生成：先离线合成 `ragas_compat`，再把官方 `TestsetGenerator` 对齐到 `memory_id` 的题目合并进来。对不上 ID 的官方题**不会**进入本目录。

## 本轮官方 RAGAS

见 [MANIFEST.json](MANIFEST.json)：

| 项 | 值 |
|---|---|
| 官方原始条数 `official_ragas_raw` | 30 |
| 对齐成功 `official_ragas_aligned` | 30 |
| 丢弃未对齐 `official_ragas_discarded_unaligned` | 0 |
| 含隔离负例 `isolation_negatives_kept` | 是（`n_isolation_cases` = 30） |
| 离线 compat | 377 |
| 默认套件合计 | **407** |
| LLM / embedding | DeepSeek Chat / `FakeEmbeddings(size=384)`（DeepSeek 无 embedding 接口） |

## 简历可用数字

- **407** 条样本（离线 377 + 官方对齐 30，丢弃 0）
- **2** 租户 × **3** 人设 / **33** 条源记忆
- **30** 条人设 / 租户隔离负例（官方生成器不会覆盖）
- **97.8%** 绑定 `expected_memory_ids` 或 `refuse`

可写进简历的一句：

> 构建 407 条记忆评测集：377 条按 RAGAS 单跳 / 多跳 / 条件问离线合成，另 30 条由官方 TestsetGenerator（DeepSeek Chat）出题并全部对齐到 memory_id；保留 30 条人设与租户隔离负例。不要把 377 或 407 全部说成「官方 RAGAS 自动出题」。

说明：compat 里 simple/reasoning 等含问法改写（同一金标多种问法），用来测检索鲁棒。官方 30 条是 `single_hop` / `multi_hop` synthesizer 产物。

## 与 suite-v1 / suite-ragas-official 的关系

| 套件 | 用途 |
|---|---|
| `suite-v1` | P0 烟雾，13 题 |
| `suite-ragas-v1` | 默认规模回归（本目录） |
| `suite-ragas-official` | 仅官方对齐成功的子集，对照用 |

## 文件

| 文件 | 内容 |
|---|---|
| `knowledge_graph.json` | 人设、记忆、事件源 |
| `cases.json` | Arbor 评测用例 |
| `ragas_eval.jsonl` | RAGAS 评分用 `user_input/reference/reference_contexts` |
| `MANIFEST.json` | 分布与官方对齐统计 |

打分时：retrieval 仍看 ID；generation 的 faithfulness 见 [docs/ragas.md](../../../docs/ragas.md)，`contexts` 必须是本轮注入文本。
