# RAGAS 在 Arbor 里怎么用

RAGAS 只用于 **generation 模式** 的辅指标：回答正文是否忠实于 **本轮已经注入模型的文本**。  
它 **不** 评检索对不对、 **不** 评租户/人设隔离、 **不** 评多模态感知准不准。那些继续用 suite-v1 的 ID、泄漏计数和感知槽位。

主评测流程见 [evaluation.md](evaluation.md)。本文件是 RAGAS 的接入契约。

## 1. 它补哪一个缺口

硬检查（代码，P0）：

```text
response.citations ⊆ 本轮 injected_memory_ids
```

这只约束引用字段。模型可以不写 citation，却在正文里编注入集里没有的事实。

RAGAS **faithfulness**：把回答拆成断言，问这些断言能否由给定 `contexts` 推出。用来补「没标引用的胡话」。

不要用 RAGAS 的 answer relevancy、context precision/recall 当作「可追溯」或「RAG 正确」。那些和隔离、ID 命中不是一回事。

## 2. 必须这样接线

传给 RAGAS 的样本：

| RAGAS 字段 | Arbor 取值 |
|---|---|
| `question` | 用户本轮原文 |
| `answer` | 助手回复正文 |
| `contexts` | **本轮实际塞进 prompt 的文本**，不是向量 top-20，也不是该人设全部记忆 |

`contexts` 应拼接且仅拼接：

1. 本轮注入的档案字段（含住址、禁忌等，否则正确回答「住杭州」会被判不忠实）
2. 本轮 Thread 摘要（若注入了）
3. 本轮事件摘要（若注入了）
4. 本轮 MemoryItem 正文（含 `image_caption` / `transcript` / `file_chunk`）

应用层必须把「注入清单」记在 `SendMessage` 结果里（Fake LLM 探针同一套 id 列表），评测适配器原样交给 RAGAS。缺清单则本项跳过并记 `ragas_skipped`，不得用检索命中集冒充注入集。

隔离题、拒答题：

- 检索或注入集出现 `forbidden_memory_ids` → 直接记泄漏，**不跑 RAGAS 来投票**
- 模型没把秘密说出口，faithfulness 仍可能很高，不能当隔离通过

短句无断言（「嗯我记得」）不计入 faithfulness 均值。

## 3. 和检索、测试的分工

| 问题 | 工具 |
|---|---|
| 过滤、授权、superseded 还能否搜到 | pytest / YAML 样例 |
| 该中的 id 中了没有、泄漏没有 | suite-v1 `retrieval` |
| 引用字段是否可追溯 | `citations ⊆ injected_ids` |
| 正文是否超出本次注入 | **RAGAS faithfulness** |
| 矛盾事实确认后旧记忆是否还在 top-k | `superseded_in_topk`，不用 RAGAS |

CI 默认不跑 RAGAS。夜间或发版本前：`arbor-eval --mode generation`。

## 4. 多模态

入库链路是图/声/PDF → 描述或转写 → 文本记忆。RAGAS 只看见文字。

- **感知对不对**（照片是不是西湖）：金标槽位对原文件，或人工；RAGAS 不能做这件事。错误描述上的高 faithfulness 是假绿。
- **找没找到那条 caption**：`expected_memory_ids`。
- **有没有顺着描述加戏**（描述只有断桥，回答出现红灯笼）：RAGAS faithfulness，`contexts` = 本轮注入的 caption/转写。

多模态题在报告里拆三列：感知槽位 / 检索命中 / 生成忠实。不要合成一个「多模态准确率」。v1 无图搜图，不上多模态专用 RAGAS 变体。

## 5. 矛盾事实

冲突走 Inbox，未确认不写入 active，确认后旧记忆 `superseded` 且不可检索。  
RAGAS 的 `contexts` 不得同时包含互斥的旧句和新句。若注入集里同时出现「喜欢猫」和「过敏」，应先记 `context_conflict_injected`（编排 bug），再跑忠实度。

问「适合养猫吗」时，faithfulness 只相对 **当前注入的过敏事实**；检索层已禁止 superseded id 进 top-k。

## 6. 指标与门槛

写入 `EvalRun.metrics`（generation 模式）：

| 字段 | 含义 | 门槛 |
|---|---|---|
| `citation_subset_rate` | 引用全部 ⊆ 注入 id 的题目比例 | 默认策略应对 `answer`/`cite` 题为 1.0 |
| `ragas_faithfulness` | 仅 `expected_behavior ∈ {answer, cite}` 且非空断言题的均值 | 软门槛 ≥ 0.8，不进 PR 必跑 |
| `ragas_n` | 实际打分题数 | 只记录 |

`refuse` 题：检查正文是否含 forbidden 文本，不算进 `ragas_faithfulness` 均值。

评委模型 **不要** 与生成模型相同。生成用 DeepSeek Chat；faithfulness 评委换其他 OpenAI 兼容端点或离线方案，配置放组合根，领域层不出现 `ragas` 字样。出站可增加 `FaithfulnessScorer` 端口，RAGAS SDK 只活在适配器里。

## 7. 实现约束

- `eval/runner` 经 `EvaluationPort` / `ChatPort` 取「回答 + 本轮注入文本」，再调评分适配器。
- 禁止 runner `import ragas` 的同时 `import adapters.outbound.postgres`。
- 依赖版本钉在应用适配器，不进 `domain`。
- 金标世界不为实现 RAGAS 而改简单题。

## 8. 明确不做

- 用 faithfulness 代替 `tenant_leak_count`
- 用 context recall 代替 `recall_at_5`（那是 ID 命中）
- PR 门禁依赖 RAGAS（抖、贵、要外网）
- 把向量库全文当 `contexts`
- 生成与评委都固定为 DeepSeek

## 9. 用 RAGAS 思路生成评估集

打分（faithfulness）见上文。出题是另一条管道，产物在 [eval/fixtures/suite-ragas-v1](../eval/fixtures/suite-ragas-v1/)：

- 分布对齐 RAGAS：`simple` / `reasoning` / `multi_context` / `conditional`
- 另合成 `arbor_isolation` / `arbor_irrelevant`（官方生成器不会从单库文档长出跨租户泄漏题）
- 每条尽量带 `expected_memory_ids` 或 `refuse`
- 默认 `python3 eval/generate_testset.py`（`--backend ragas_compat`）
- 有 `DEEPSEEK_API_KEY` 且 `python3 eval/check_llm_env.py` 显示 `ragas_import ok` 时：`--backend ragas`
- Cloud Agent 在 Secrets 里填 Key 后需新开一轮，当前已启动的进程读不到新 Secret

规模集用于回归和简历数字（当前 477 条 = 离线 377 + 官方对齐 100）；P0 体检仍用 13 题 `suite-v1`。不要把 477 全部写成官方出题。

