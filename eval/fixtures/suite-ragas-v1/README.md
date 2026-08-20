# suite-ragas-v1

规模评测集。由 `python3 eval/generate_testset.py` 生成。

## 简历可用数字（当前产物）

见 [MANIFEST.json](MANIFEST.json)：

- **377** 条样本（**374** 条不重复问句）
- **2** 租户 × **3** 人设
- **33** 条源记忆（32 条 active）
- **97.6%** 绑定 `expected_memory_ids` 或 `refuse`（不是开放闲聊）
- RAGAS 演化：simple 231 / reasoning 42 / multi_context 36 / conditional 30
- Arbor 负例：isolation 30 / irrelevant 8（官方 TestsetGenerator 不会从单库文档长出跨租户泄漏题）

可写进简历的一句：

> 构建 377 条记忆评测集（RAGAS 单跳 / 多跳 / 条件问分布 + 人设与租户隔离负例），覆盖 2 租户 3 人设、33 条源记忆，97.6% 样本绑定 memory_id。

说明：其中 simple/reasoning 等含 **问法改写**（同一金标 3 种问法），用来测检索鲁棒，不是 377 条互不相关的事实。独立参考答案约 64 条。

## 与 suite-v1 的关系

| 套件 | 用途 |
|---|---|
| `suite-v1` | P0 烟雾，13 题，面试体检默认 |
| `suite-ragas-v1` | 规模回归与简历数字，改检索后全量跑 |

## 生成方式

当前默认 `--backend ragas_compat`：按 RAGAS 的 simple / reasoning / multi_context / conditional 从知识图谱离线合成，并强制写入 Arbor 的 actor / memory_id / forbidden。

本环境 **没有 DEEPSEEK/OPENAI Key**，且安装的 ragas 0.3 与 langchain 1.x 无法 import，因此 **没有调用官方 TestsetGenerator 出题**。有 Key 后：

```text
DEEPSEEK_API_KEY=... python3 eval/generate_testset.py --backend ragas --size 50
```

LLM 产出会对齐到 `memory_id` 再合并；对齐失败的题不得进入默认套件。

## 文件

| 文件 | 内容 |
|---|---|
| `knowledge_graph.json` | 人设、记忆、事件源 |
| `cases.json` | Arbor 评测用例 |
| `ragas_eval.jsonl` | RAGAS 评分用 `user_input/reference/reference_contexts` |
| `MANIFEST.json` | 分布统计 |

打分时：retrieval 仍看 ID；generation 的 faithfulness 见 [docs/ragas.md](../../../docs/ragas.md)，`contexts` 必须是本轮注入文本，不是本文件的 `reference_contexts` 整包。
