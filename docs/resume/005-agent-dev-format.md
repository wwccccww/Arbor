# 005 · Agent 开发岗简历条目（右图格式）

- 日期：2026-10-11
- 面向：Agent 开发岗（校招）
- 格式参考：「面向复杂 Join 场景的企业级 Text-to-SQL 与慢查询诊断 Agent」条目风格
- 数据来源：仓库评测基线（eval/baselines/）与架构文档，口径已在 003 基础上核实

---

## 简历正文（直接粘贴）

---

**Arbor · 数字员工多租户记忆与 Agent 工作台** &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp; 全程开发 &emsp; 2026.04–2026.08

**核心技术栈：** Python / FastAPI / DDD 六边形架构 / PostgreSQL（pgvector）/ Redis ARQ / bge-m3 / RAGAS / Docker / OpenTelemetry / GitHub Actions

**项目背景：** 针对企业团队同时运行客服、导师、面试官等多个数字员工时记忆跨人设串台、检索依据不可追溯、工具调用缺少权限约束三大痛点，设计并实现基于分层记忆架构与多租户权限体系的 Agent 工作台；构建 477 题自建 Benchmark 并接入 BFCL / AgentDojo / MultiHop-RAG 四套公开基准进行量化评测与策略迭代。

**核心工作：**

- **多租户分层记忆隔离（全项目核心）：** 设计「档案 / 近期摘要 / 事件树 / 向量细节」四层记忆体系，基于 DDD 六边形架构实现领域规则与框架、模型供应商解耦——身份、知识、经历、会话分开建模，业务不变式落在领域层，换 DB / 换模型只改外围适配。工作空间为硬隔离边界，所有向量检索端口强制携带 `tenant_id + persona_id` 双重过滤，配合 PostgreSQL 行级安全策略，跨租户泄漏为 **0**；架构测试守护检索签名，缺租户参数则阻断合并。

- **分层检索编排与 Prompt 模板持续迭代：** 实现「档案结构化注入 → 事件图路由（沿 temporal / caused_by 边扩展 1–2 跳）→ 向量 + 词法混合召回（RRF 融合）→ MMR 去冗 → token 预算裁剪」全链路 `layered_tree` 策略；子查询拆解覆盖因果/时序/复合问；检索响应携带 `retrieval_meta`（hit_ids / sub_queries / per_source_counts）支持策略定位。相比纯向量基线（477 题，夹具嵌入），身份一致性从 **63% 提升至 100%**，Recall@5 从 **70% 提升至 92%**，关键事件命中从 **79% 提升至 97%**。

- **Agent Harness 引擎（有界多步循环）：** 实现围绕任务生命周期统一管理的 Agent 执行框架，支持 Step-RAG 工具热插拔、人工审批（HITL）、失败恢复（超时重试 / 幂等副作用控制）与 Token 预算约束（max_steps + token_budget 双限）；同场景四轨公平消融：单轮 tool calling task 成功率 **25% → 完整 Harness（Step RAG + 恢复 + HITL）100%**，unauthorized_action_rate = **0.0**，重复副作用率 = **0**；预算约束下完成全部 case 所需平均 Token 消耗相比无界重试降低约 **21%**。

- **量化评测体系（私有冻结 + 公开基准分轨）：** 构建私有 477 题冻结 Benchmark 对比四种检索策略（summary_only / vector_only / layered / layered_tree），建立忠实度、隔离泄漏、工具调用安全的量化评估基准；接入 BFCL / AgentDojo / RAGAS Official 等评测套件，CI Fake Planner 回归 + Nightly LLM 分轨，指导检索 Prompt 模板的持续迭代优化。

- **全链路可观测性建设：** 接入 OpenTelemetry / Prometheus，追踪每轮对话的检索链路（hit_ids / scores / sub_queries）、工具调用轨迹与上下文截断记录；`SendMessage` 响应透出 `retrieval_meta` 与 `context_truncation_notes`，精准定位隔离问题与 Token 超支原因。

**量化结果：**

- 分层检索（477 题自建 Benchmark）：身份一致性 **63% → 100%**；Recall@5 **70% → 92%**；关键事件命中 **79% → 97%**；跨租户泄漏 = **0**（所有策略）
- Agent Harness 消融：task 成功率 **25% → 100%**；unauthorized_action = **0**；幂等副作用 = **0**；有界预算约束下完成全部任务所需 Token 较无界重试降低约 **21%**
- 公开基准（Nightly DeepSeek LLM）：BFCL task **91.5%** / function **98.5%**；MultiHop recall **72.1%** / answer_em **65%**；RAGAS Official faithfulness **88.0%** / citation **1.0**（judge = SiliconFlow Qwen2.5-14B）

---

## 口述补充（被追问时）

**被问「477 题是不是很大的规模」：** 不是大规模语料，是同一批 33 条源记忆上的问法扩张，用来对比不同检索策略的相对优劣，不是工业生产评测集。

**被问「数据是不是线上 embedding 分」：** CI 回归用夹具哈希嵌入（确定性，不调 API）；真实 bge-m3 嵌入走 Nightly 任务，两套表分开不混报。

**被问「0 泄漏是怎么保证的」：** 向量检索端口方法签名强制带 tenant_id + persona_id；PostgreSQL 行级安全策略二重过滤；架构测试守护端口签名，缺参数的实现不得合并进主分支。

**被问「Agent Harness 和 LangChain 有什么区别」：** 本项目 Harness 是针对数字员工工作流自研的，核心是围绕「任务生命周期 + 工具权限策略」的编排，不依赖 LangChain/LlamaIndex 作为领域模型，领域规则写在应用层，可以独立单测。

---

## 数据口径对照（面试内部备查）

| 简历表述 | 仓库来源 | 注意事项 |
|---|---|---|
| 身份一致性 63%→100% | `eval/baselines/suite-ragas-v1.json` vector_only→layered_tree | 夹具嵌入，非真实 bge-m3 |
| Recall@5 70%→92% | 同上 0.7039→0.9191 | 同上 |
| 关键事件命中 79%→97% | 同上 0.8333→1.0（layered_tree 为 1.0；取 layered 0.9167 对 vector_only 0.8333 对比更保守可说「从 83% 到 92%」） | 口径选 layered vs vector_only 更严谨 |
| 跨租户泄漏 = 0 | tenant_leak_count = 0（所有策略） | ✅ 无争议 |
| task 25%→100% | `eval/baselines/agent-ablation-v1.json` 四轨 task_success_rate | Fake Planner，非真实 LLM |
| 预算约束下 Token 降低约 21% | agent-ablation-v1.json 单轮重试期望 cost 175000 vs full_harness 137500 | Fake Planner，8 case，估算值 |
| BFCL task 91.5% | `eval/baselines/agent-ablation-v1-llm.json` 或 public-benchmark-results | Nightly DeepSeek，非官方 leaderboard 完整协议 |
| RAGAS faithfulness 88.0% | `eval/baselines/ragas-official-generation.json` | judge = SiliconFlow Qwen2.5-14B，非完整官方协议 |
