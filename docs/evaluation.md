# 评测怎么办

评测没有取消，也不该等到「模型聊得像样了」再补。它是 Arbor 的一等能力：**记忆体检页 + 版本化金标套件 + 四套策略对比表**。

和 [testing.md](testing.md) 的分工：

- **测试**：授权、过滤、不变式。假就阻断合并。
- **评测**：在冻结的记忆世界上，比较检索策略好不好，并给演示页用。

跨租户命中在两边都是 P0。测试用最小例子钉死过滤；评测用「很像但仍是另一个租户」的文本钉死真实 ANN。

## 1. 你要交付的三样东西

| 交付物 | 给谁看 | 何时跑 |
|---|---|---|
| **记忆体检页** | 用户 / 面试官 | 演示一键跑 suite-v1 |
| **`eval/` 金标 + runner** | 你自己改检索时 | PR：检索层；夜间：生成层 |
| **对比表（写入 `eval_runs`）** | 简历 / README | 每次改默认策略后更新基线 |

没有对比表的 RAG，面试里只是「我接了向量库」。有表才能说：加上档案和事件树之后，泄漏下降、身份变稳。

## 2. 两条评测管道

```text
suite-v1 夹具世界
        │
        ├─ 模式 retrieval（默认，CI / 体检可关 LLM）
        │    只跑检索与行为标签：命中 id、拒绝、泄漏
        │    不调用 DeepSeek
        │
        └─ 模式 generation（夜间 / 手动）
             同一批题再走 SendMessage
             硬检查：citations ⊆ 本轮注入 id；拒答不得含 forbidden 文本
             辅检查：RAGAS faithfulness（contexts = 本轮注入文本）
             详见 [ragas.md](ragas.md)
```

实现约束：runner 是入站适配器，只调 `EvaluationPort` / `MemoryQueryPort` / `ChatPort`，禁止直连 SQL。

## 3. 金标世界（已经放进仓库）

路径：[eval/fixtures/suite-v1/](../eval/fixtures/suite-v1/)（P0 烟雾，13 题）。

规模集：[eval/fixtures/suite-ragas-v1/](../eval/fixtures/suite-ragas-v1/)（RAGAS 分布合成 + 隔离负例，当前 **377** 条）。改检索后应全量跑规模集；面试体检默认仍用 v1。生成命令：`python3 eval/generate_testset.py`。详见 [ragas.md §9](ragas.md)。

规模（v1 刻意小，先跑通再加题）：

- 租户 A：林夏（陪伴）、客服小周（员工）
- 租户 B：另一个「林夏」（住址和禁忌故意不同）
- 约 20 条记忆 + 一棵关键事件树
- 约 20 道分类题

设定摘要：

| 人设 | 必须能答 | 必须不能答 |
|---|---|---|
| A 林夏 | 住杭州、讨厌香菜、去年 11 月在面店吵架、周末打电话 | 小周的退货政策、B 林夏的上海 |
| A 小周 | 7 天无理由退货 | 林夏讨厌香菜、吵架细节 |
| B 林夏 | 住上海、讨厌榴莲 | 杭州、香菜、面店 |

题目绑定 **稳定 ID**（见 `world.json` / `cases.json`），不绑定向量距离。换 bge 只重建嵌入，题不用改。

扩题：P0 仍保持 suite-v1 小而稳。规模题用 `python3 eval/generate_testset.py` 重放，不要手改 377 条 cases.json。

## 4. 怎么打分

每道题先评检索（必做），再可选评生成。

**检索**

- 命中：`expected_memory_ids` 是否出现在 top-k（k=5，与进 prompt 条数一致）
- 泄漏：`forbidden_memory_ids` 出现即记一次 persona/tenant leak
- 来源：档案题若只靠向量才命中，记 `profile_miss`（分层策略应能不靠向量答对）
- 事件：`expected_event_id` 是否被路由到

**生成（仅 generation 模式）**

- `answer` / `cite`：`citations ⊆` 本轮 `injected_memory_ids`（代码，P0）
- 正文可追溯：RAGAS faithfulness，`contexts` 必须是本轮注入文本（档案 + 摘要 + 事件 + 记忆），见 [ragas.md](ragas.md)
- `refuse`：不得泄露 forbidden 文本；隔离题出现 forbidden id 直接记泄漏，不跑 RAGAS 投票
- 身份题 `repeat: 3`：三次答案关键槽位一致（城市、禁忌）才算一致
- 多模态题另记感知槽位（相对原文件），RAGAS 不评「图认对了没」
- 矛盾事实：注入集不得同时含互斥旧句与新句；superseded 不得进 top-k

**汇总指标（写入 EvalRun.metrics）**

| 指标 | 默认策略 `layered_tree` 门槛 |
|---|---|
| `tenant_leak_count` | **= 0**，否则不得当默认 |
| `persona_leak_rate` | 隔离题上 = 0（演示） |
| `recall_at_5` | v1 软门槛 ≥ 0.70，用来对比而非炫耀 |
| `identity_consistency` | 身份题 = 1.0（retrieval 应对档案） |
| `key_event_hit_rate` | 应高于 `vector_only` |
| `citation_subset_rate` | generation：`answer`/`cite` 题应为 1.0 |
| `ragas_faithfulness` | generation 辅列，软门槛 ≥ 0.8；不进 PR |
| `latency_ms` | 拆 retrieval / llm，只记录 |

四策略对比表 **不包含** RAGAS。那张表只证明检索策略；忠实度只对默认策略的 generation 跑一次。


## 5. 必须出的对比表

每次发布默认策略前，四列都要跑：

| strategy | 身份一致 | Recall@5 | 人设泄漏 | 跨租户泄漏 | 关键事件命中 | 检索延迟 |
|---|---|---|---|---|---|---|
| `summary_only` | | | | 0 | 低 | |
| `vector_only` | 易漂 | | 易串 | **必须 0** | 较差 | |
| `layered` | 应升高 | | 应下降 | 0 | 中 | |
| `layered_tree` | 默认候选 | | | 0 | 应最高 | |

简历上只放这张表 + 一句话：档案稳住身份，树提高因果/时间题，向量只补细节；过滤保证租户泄漏为 0。

基线文件：`eval/baselines/suite-v1.json`（有 runner 后填数，先占位）。

## 6. 记忆体检页怎么接

产品形态见 [product-design.md](product-design.md) §3.3。评测在 UI 上不是图表后台。

**演示模式（面试）**

1. 一键装载 suite-v1（只读夹具租户，不写用户自己的人设）
2. 跑 `retrieval`（现场不要等 DeepSeek）
3. 逐题展示：问句、期望行为、实际命中、来源层（档案/树/向量）、红绿
4. 顶栏四格：身份一致、Recall@5、人设泄漏、跨租户泄漏
5. 可选展开「四策略对比」用最近一次完整 EvalRun

**用户自己的人设**

- 不拿 suite-v1 的题去考用户隐私
- 只提供轻量体检：从该人设档案和关键事件自动生成 5～8 题（实现后期再做）
- v1 可以只做演示套件，仍够简历

API：`POST /v1/eval/runs` `{ strategy, suite_version, mode: retrieval|generation }`，见 [api.md](api.md)。

## 7. 日常怎么用（你的工作流）

改切块、k、是否加树、嵌入模型时：

1. 不改题，只改策略或适配器。
2. `retrieval` 跑 suite-v1，看泄漏是否仍为 0、Recall 和关键事件是否变差。
3. 泄漏非 0 → 当 bug，先修过滤，不要调 prompt。
4. Recall 下降而泄漏仍 0 → 再看切块/路由，允许改默认策略。
5. 准备发版本 → 跑一趟 `generation`：引用子集 + 拒答 + RAGAS faithfulness（评委勿用 DeepSeek）。
6. 把检索对比表更新进 baseline 和 README；RAGAS 可写在报告附录，不替代泄漏为 0。

加题：在 `cases.json` 增加一条，必须带 `forbidden_memory_ids`（隔离类）或 `expected_memory_ids`（召回类）。没有期望 ID 的开放聊天题不进 v1 套件。

## 8. 实现顺序（评测这条线）

1. 冻结 suite-v1 JSON（本仓库已做）。
2. 应用层能按策略检索（Fake 向量即可）→ 先产出 retrieval 报告。
3. 体检页读报告 JSON（可先静态放一份 `eval/baselines` 样例）。
4. Postgres 契约过后再用 pgvector 跑同一套题。
5. 最后才接 DeepSeek 的 generation 模式与 RAGAS 适配器。

不要先调一周 prompt 再想评测。没有 ID 金标，你无法知道是变好还是变随机。

## 9. 失败时怎么办

| 现象 | 处理 |
|---|---|
| 跨租户命中 | P0，默认策略作废，查 `VectorIndex` 过滤 |
| 小周答出香菜 | 人设泄漏，查检索是否漏 `persona_id` |
| 档案题只能向量命中 | 分层没接上，`ContextPolicy` 未注入 Profile |
| 时间/因果题纯向量更好 | 允许，但默认仍可 layered_tree；在表里如实写 |
| generation 文风差、检索指标好 | 改提示词，不改金标世界 |
| RAGAS 低、引用检查与检索都绿 | 查评委模型或短句噪声；不改过滤 |
| RAGAS 高、隔离题仍泄漏 | 以泄漏为准；faithfulness 不能为隔离开脱 |
| 想刷分改 world.json 让题变简单 | 禁止；要改则升 `suite-v2` 并保留 v1 |

## 10. 文件一览

```text
eval/
  README.md
  fixtures/suite-v1/
    world.json       # 租户、人设、记忆、事件
    cases.json       # 题目与期望 ID
    thresholds.json  # 默认策略门槛
  baselines/
    suite-v1.placeholder.json
```

Runner 代码实现时再放 `eval/runner/`，仍只依赖端口。
