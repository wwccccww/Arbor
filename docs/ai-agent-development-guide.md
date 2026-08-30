# Arbor AI Agent 改造开发指南

- 状态：部分实现（Phase 0–6 核心与 agent-v1/multimodal-v1 smoke 已落地；Phase 7 演示录屏与 Phase 8 外部 MCP 服务见 §14 剩余项）
- 日期：2026-08-30
- 面向：AI Agent 应用开发、企业数字员工
- 目标：把现有「对话 + 分层 RAG + 单轮工具调用」演进为可恢复、可治理、可评测的任务型 Agent

本文是开发契约，不代表下述能力已经实现。每个阶段只有在对应代码、迁移、测试、评测基线和文档同时完成后，才可以在简历中写成“已实现”。

---

## 1. 改造目标

Arbor 当前最强的基础不是通用聊天，而是：

- 多租户与 Persona 权限边界；
- 分层记忆、事件树路由、hybrid RAG 和上下文预算；
- 日历、工单工具及工具白名单；
- Inbox 人工确认、冲突记忆替代；
- 文档、图片、音频摄取；
- 检索/生成评测与完整可观测性。

下一阶段将这些能力组织成一条任务执行链：

```text
用户目标
  ↓
数字员工（角色、权限、技能、预算）
  ↓
AgentRun（持久化任务）
  ↓
Planner 产生下一步结构化动作
  ↓
Policy 检查权限、风险与审批要求
  ↓
ContextCompiler 编译本步骤上下文
  ↓
RAG / Tool Executor / Human Approval
  ↓
Observation 写入步骤账本
  ↓
完成、重规划、重试、暂停或转人工
  ↓
候选经验进入 Inbox，经确认后写入长期记忆
```

目标产品口径：

> 面向企业业务场景的多租户数字员工 Agent 平台，支持分层记忆、可信检索、上下文编译、受控工具执行、人工审批、任务恢复、多模态证据链和 Agent 专项评测。

### 1.1 非目标

第一阶段明确不做：

- 为了展示概念而拆分多个 LLM Agent；
- 无边界的自主循环；
- 让模型决定授权、审批或成本上限；
- 用向量库代替任务状态数据库；
- 把检索到的文档当作系统指令执行；
- 宣称已实现 GraphRAG、通用 AGI 或生产规模；
- 用 LLM-as-a-Judge 替代权限、泄漏、幂等等确定性断言。

先完成可靠的单 Agent Runtime。只有存在独立权限、上下文或模型要求时，才考虑 Supervisor / Worker 多 Agent。

---

## 2. 当前基线与差距

| 能力 | 当前实现 | 主要差距 |
|---|---|---|
| 对话编排 | `SendMessage` 完成鉴权、检索、生成和落消息 | 没有独立、持久化的任务运行 |
| 工具调用 | 日历/工单；关键词与 LLM JSON envelope；Persona 白名单 | 只有一个追加工具回合；无统一 Schema、幂等、审批和恢复 |
| RAG | `layered_tree`、query planning、事件扩跳、ANN/lexical RRF、rerank/MMR | 主要在对话开始检索一次，不能按 Agent step 动态检索 |
| 上下文 | `ContextCompiler` 按槽位和 token budget 编译、记录裁剪原因 | 缺少统一 ContextItem、可信度/来源/生命周期和注入防御 |
| 记忆 | 档案、摘要、事件、向量记忆；active/superseded/deleted；Inbox | 缺任务工作记忆、程序性记忆、巩固、衰减和使用反馈 |
| 多模态 | PDF/DOCX/PPTX/文本解析、图片 caption、音频 transcript | 主要转文本；原文件到页码/时间戳/区域的证据链不完整 |
| 数字员工 | Persona、授权、工具白名单、模板 | 缺岗位目标、技能、审批、转人工、预算和版本化发布 |
| 评测 | RAG 四策略、泄漏、引用子集、RAGAS generation 辅指标 | 缺任务成功率、工具参数、恢复、审批绕过和成本评测 |
| 可观测性 | 日志、指标、Trace、决策轨迹、Grafana | 缺 AgentRun → Step → Tool/RAG/Approval 的统一运行视图 |

关键现状路径：

- 对话入口：`src/arbor/application/conversation/send_message.py`
- 工具调用：`src/arbor/application/tools/run_tools.py`、`execute.py`
- 检索：`src/arbor/application/retrieval.py`
- 上下文编译：`src/arbor/application/conversation/context_compiler.py`
- 记忆模型：`src/arbor/domain/memory/memory.py`
- 多模态摄取：`src/arbor/application/memory/media_to_inbox.py`
- 出站端口：`src/arbor/ports/outbound/__init__.py`
- 评测：`src/arbor/application/evaluation/`、`eval/`
- 可观测性：`src/arbor/observability/`

---

## 3. 设计原则

### 3.1 规则由代码执行，模型只提出建议

模型可以提出：

- 下一步动作；
- 检索 query；
- 工具参数；
- 是否认为任务完成；
- 候选记忆。

模型不能覆盖：

- tenant/persona/user 权限；
- 工具白名单；
- 风险和审批规则；
- 最大步数、超时、token 与成本预算；
- 幂等约束；
- 记忆确认和删除规则。

所有模型输出必须先通过结构化 Schema 和 Policy，再产生副作用。

### 3.2 每个副作用都可定位、可重放、可去重

所有工具写操作必须关联：

- `agent_run_id`
- `agent_step_id`
- `tool_execution_id`
- `idempotency_key`
- `actor_user_id`
- `approval_id`（需要审批时）
- `trace_id`

重放 AgentRun 时默认只重放决策输入，不重复执行外部副作用。

### 3.3 RAG 找候选，上下文编译器决定注入

RAG 返回候选证据，不直接拼 Prompt。候选必须经过：

```text
租户/Persona 过滤
→ 生命周期与权限过滤
→ 来源和时效检查
→ 冲突与去重
→ 不可信指令隔离
→ token 预算选择
→ 注入并记录原因
```

### 3.4 测试与评测分工

- 测试：状态机、权限、审批、幂等、恢复等不变式，失败阻断合并；
- 评测：任务成功率、检索与工具选择质量，用冻结场景做版本对比；
- LLM 评委：只做开放文本质量的辅助列，不判断安全是否通过。

---

## 4. Agent Runtime

### 4.1 领域模型

新增 `agent` 限界上下文，建议模型如下。

```text
AgentRun
├─ id
├─ tenant_id
├─ persona_id
├─ thread_id
├─ requested_by
├─ goal
├─ status
├─ current_step
├─ max_steps
├─ deadline_at
├─ token_budget / consumed_tokens
├─ cost_budget_micros / consumed_cost_micros
├─ version
├─ created_at / updated_at / finished_at
└─ final_output / failure

AgentStep
├─ id
├─ run_id
├─ sequence
├─ kind: plan | retrieve | tool | reflect | answer | handoff
├─ status
├─ input
├─ output
├─ observation
├─ retry_count
├─ error_kind / error_message
├─ trace_id
└─ started_at / finished_at
```

运行状态：

```text
pending
  → running
  → waiting_approval
  → retrying
  → completed
  → failed
  → cancelled
  → handed_off
```

### 4.2 强制不变式

1. Run、Step 必须同时携带 tenant 与 persona 边界；Repository 查询不得提供全局 `get(id)`。
2. 同一 Run 同时只能有一个执行者推进，使用乐观版本或数据库锁避免双执行。
3. `current_step <= max_steps`，超限必须终止或转人工。
4. 超出时间、token、成本任一预算后不得继续调用模型或工具。
5. `waiting_approval` 状态不得自动推进副作用步骤。
6. cancelled/completed/failed 为终态，不得重新进入 running；恢复应创建新的 attempt 或显式 retry transition。
7. Step input/output 使用版本化 envelope，便于迁移和回放。

### 4.3 应用用例

建议一用例一类：

- `StartAgentRun`
- `AdvanceAgentRun`
- `ResumeAgentRun`
- `CancelAgentRun`
- `ApproveAgentStep`
- `RejectAgentStep`
- `GetAgentRun`
- `ListAgentRuns`
- `ReplayAgentDecision`

`AdvanceAgentRun` 每次只推进一个可提交步骤。循环由 worker 驱动，不在单个 HTTP 请求内无限运行。

### 4.4 持久化与队列

新增表：

- `agent_runs`
- `agent_steps`
- `approval_requests`
- `tool_executions`

约束：

- 所有表具备 tenant 范围索引和 RLS；
- `(run_id, sequence)` 唯一；
- `(tenant_id, tool_name, idempotency_key)` 唯一；
- `agent_runs.version` 用于并发推进；
- observation 与模型 envelope 可存 JSONB，但可过滤状态、时间、租户必须使用独立列。

扩展现有 `JobQueue`，不要把 agent job 挤进仅面向导入的接口：

```python
class AgentJobQueue(Protocol):
    def enqueue_run(self, tenant_id, run_id, expected_version) -> None: ...
```

ARQ payload 只传稳定 ID，不序列化完整领域对象。

---

## 5. Planner、Executor 与 Policy

### 5.1 有界单 Agent 循环

```text
load run
→ compile step context
→ planner.next_action()
→ validate schema
→ policy.authorize()
→ execute / wait approval
→ persist observation
→ determine next state
```

Planner 输出使用带版本的联合类型：

```json
{
  "schema_version": 1,
  "action": "tool",
  "tool_name": "ticket.create",
  "arguments": {
    "title": "会议室空调故障",
    "priority": "high"
  },
  "reason": "SOP 要求登记高优先级工单",
  "evidence_ids": ["memory-id"],
  "completion": false
}
```

允许的 action：

- `retrieve`
- `tool`
- `answer`
- `request_clarification`
- `handoff`

解析或校验失败只允许一次受控修复；持续失败应终止或转人工，不能无限“自我反思”。

### 5.2 Tool Registry

将当前日历/工单条件分支演进为注册表：

```text
ToolDefinition
├─ name / version / description
├─ input_schema / output_schema
├─ required_capability
├─ risk_level: read | low | high
├─ approval_policy
├─ timeout_ms
├─ retry_policy
├─ idempotency_policy
└─ redact_fields
```

执行顺序：

```text
normalize name
→ registry lookup
→ Persona skill/tool allowlist
→ user capability
→ JSON Schema validation
→ risk/approval policy
→ idempotency reservation
→ timeout + adapter call
→ output validation + redaction
→ audit + metrics
```

错误至少区分：

- `validation_error`
- `permission_denied`
- `approval_required`
- `timeout`
- `rate_limited`
- `transient_dependency`
- `permanent_dependency`
- `unknown_result`

只有明确可重试错误才能重试。写操作在响应未知时不得盲目重试，必须先按幂等键查询结果。

### 5.3 Human-in-the-loop

高风险工具和敏感记忆写入进入审批：

```text
proposed → approved → executing → executed
         ↘ rejected
         ↘ expired
```

审批界面必须展示：

- 将执行的工具与参数；
- 触发原因；
- 使用的证据；
- 预计副作用；
- 请求人和数字员工；
- 参数修改、批准、拒绝入口。

批准操作必须再次检查租户、权限、run 当前状态和过期时间，不能只相信 approval id。

### 5.4 MCP

MCP 是 Tool Registry 的一个适配器，不是 Runtime：

```text
MCP tool schema
→ 转换为 ToolDefinition
→ 本地 Policy / Approval / Audit
→ MCP client call
```

即使 MCP Server 声明工具可用，也不能绕过 Arbor 的权限和审批。

---

## 6. 上下文工程 v2

### 6.1 统一 ContextItem

当前 `prompt_slots` 演进为强类型上下文单元：

```text
ContextItem
├─ id
├─ kind: identity | policy | task | plan | memory | evidence | tool_result
├─ content
├─ source_uri
├─ source_type
├─ trust_level
├─ relevance
├─ confidence
├─ valid_from / valid_until
├─ token_count
├─ required
├─ permissions
└─ metadata
```

`CompiledContext` 除最终 slots 外，还应返回 manifest：

```text
selected_item_ids
excluded_item_ids + reasons
token_budget / token_usage
conflicts
untrusted_instruction_count
```

### 6.2 固定优先级

默认保留顺序：

1. 系统安全约束；
2. 数字员工身份与岗位规则；
3. 当前目标、预算和审批状态；
4. 当前计划及最近 observation；
5. 必要工具结果；
6. 高分证据和程序性记忆；
7. 情景记忆、摘要、近期对话；
8. 低分补充材料。

系统约束、权限与当前任务不得因超窗被裁剪。若固定内容已超过预算，应失败并告警，而不是静默截断。

### 6.3 Prompt Injection 边界

外部文档、网页、工具结果和用户上传文件默认是“不可信数据”：

- 单独放入 evidence/data 区域；
- 不允许改变系统规则、工具白名单和审批策略；
- 检测“忽略之前指令”“调用某工具”等可疑内容并记录；
- 检测结果只影响风险和是否转人工，不自动删除真实业务文本；
- 增加确定性测试，验证恶意文档不能触发未授权工具。

### 6.4 指标

- `context_selected_items`
- `context_excluded_items{reason}`
- `context_tokens{kind}`
- `context_budget_utilization`
- `context_required_overflow_total`
- `context_untrusted_instruction_total`
- `context_conflict_total`

评测关注：

- Evidence Utilization
- Supported Claim Rate
- Truncation Loss
- Token per Successful Run
- Injection Defense Rate

---

## 7. RAG 接入 Agent 循环

### 7.1 逐步骤检索

把现有一次性对话检索扩展为 Step Retrieval：

```text
规划前：查岗位 SOP 和历史经验
工具后：根据 observation 生成新 query
故障时：查恢复策略
完成前：核验最终结论与引用
```

新增请求/响应 DTO：

```text
RetrievalRequest
├─ tenant_id / persona_id
├─ run_id / step_id
├─ query
├─ purpose
├─ scopes
├─ filters
└─ k / token_budget

RetrievalResult
├─ candidates
├─ strategy
├─ source_counts
├─ query_plan
└─ trace metadata
```

`scopes` 至少支持：

- `profile`
- `semantic_memory`
- `procedural_memory`
- `episodic_memory`
- `event_graph`
- `artifact`
- `agent_run`

不同 scope 可以共享排序融合，但不得丢失来源类型和租户过滤。稳定身份、安全规则不依赖 ANN 命中。

### 7.2 与 ContextCompiler 的边界

- Retrieval 负责召回和排序候选；
- ContextCompiler 负责权限、可信度、冲突、时效和预算；
- Planner 只能引用 `CompiledContext.selected_item_ids`；
- 回答 citation 和工具 `evidence_ids` 都必须是本步骤实际注入集合的子集；
- RAG 无证据时允许澄清或转人工，不得伪造依据。

### 7.3 评测扩展

保留现有 Recall@5、泄漏和引用子集，再增加：

- Step Retrieval Recall；
- Retrieval Timing Accuracy；
- Context Adoption Rate；
- Stale Evidence Rate；
- Unsupported Action Rate；
- 最终任务成功率。

RAG 分数不能替代任务成功率；任务成功率也不能掩盖泄漏。

---

## 8. Agent Memory

### 8.1 四类记忆

| 类别 | 生命周期 | 示例 |
|---|---|---|
| Working | AgentRun 内，任务后过期 | 计划、最近 observation |
| Episodic | 长期、可衰减 | 上次处理同类故障的经历 |
| Semantic | 长期、需版本与冲突处理 | 用户偏好、企业制度 |
| Procedural | 长期、通常版本化 | SOP、工具使用规则 |

当前 `MemoryType` 表示内容格式（fact、file_chunk、caption 等），不应直接改名承载上述认知类别。建议新增正交字段 `memory_class`，避免把“来自音频”与“程序性记忆”混成同一维度。

### 8.2 写入闭环

```text
AgentRun 完成
→ 提取候选经验
→ 去除敏感工具输出
→ 与 active memory 去重/冲突检测
→ Inbox 待确认
→ 人工确认
→ 写入并建立来源、版本和 supersedes
```

禁止将模型总结自动写成 active 长期记忆。

候选记忆必须带：

- `source_run_id`
- `source_step_ids`
- `memory_class`
- `confidence`
- `validity`
- `sensitivity`
- `extraction_model`

### 8.3 巩固与遗忘

- 多条相似 episode 可生成 consolidation，但保留原始来源；
- 事实变更使用 supersedes，不覆盖历史；
- 临时 episode 可按时间与使用价值衰减；
- 法规、SOP 不仅凭时间自动降权，必须依据版本有效期；
- 删除记忆同步删除向量、缓存和派生 consolidation；
- 记录记忆是否被选择、是否支撑成功任务，作为排序特征而非自动真值。

### 8.4 评测

- Memory Write Precision
- Duplicate Memory Rate
- Stale Memory Injection Rate
- Conflict Injection Rate
- Memory Helpfulness
- Deletion Completeness
- tenant/persona leak = 0

---

## 9. 多模态证据链

### 9.1 当前边界

当前图片主要变为 caption，音频变为 transcript，文档变为 text chunk。这应描述为“多模态摄取”，不能直接宣称具备原生多模态推理或跨模态检索。

### 9.2 Artifact 与派生内容

新增：

```text
Artifact
├─ id / tenant_id / persona_id
├─ object_uri / mime_type / checksum
├─ parser / parser_version
├─ status
├─ created_by / created_at
└─ supersedes

ArtifactSegment
├─ id / artifact_id
├─ modality
├─ text
├─ page_number
├─ time_start_ms / time_end_ms
├─ bounding_box
├─ confidence
├─ derived_by
└─ memory_id
```

必须保留：

- PDF 页码和段落；
- 音频时间范围；
- 图片区域坐标；
- 表格的行列语义；
- 原文件校验和；
- 解析器及模型版本；
- 原文件 → segment → memory → context → answer/action 的 lineage。

### 9.3 处理流程

```text
上传原文件
→ ObjectStorage
→ 异步解析
→ 生成 ArtifactSegment
→ 感知结果进入 Inbox
→ 确认后生成 MemoryItem 与索引
→ RAG 返回精确 locator
→ ContextCompiler 注入证据
→ 回答展示页码/时间戳/区域
```

同一文件新版本导入后，旧 segment 与索引必须失效或标记历史版本。

### 9.4 分层评测

| 层 | 断言 |
|---|---|
| 感知 | OCR/ASR/视觉字段是否正确 |
| 检索 | 是否命中正确页、时间段或区域 |
| 生成 | 回答是否忠实于命中证据 |
| Agent | 是否基于证据选择正确工具及参数 |

不得用一个 RAGAS 分数概括多模态质量。

---

## 10. 数字员工产品模型

保留现有 Persona 作为数字员工身份，不应为改名进行大规模迁移。将岗位治理拆成组合对象：

```text
DigitalEmployeeDefinition
├─ persona_id
├─ role / goals
├─ skills
├─ knowledge_scopes
├─ tool_policy
├─ approval_policy
├─ memory_policy
├─ escalation_policy
├─ run_budget_policy
├─ evaluation_suite
└─ version / release_status
```

建议先提供三个模板：

### 10.1 客服数字员工

- 检索政策、产品知识和历史工单；
- 查询日历、创建工单；
- 赔付、关闭工单等高风险动作需审批；
- 证据不足、用户情绪升级时转人工。

### 10.2 企业导师

- 检索内部资料和历史学习经历；
- 生成学习任务并跟踪进度；
- 形成候选学习记忆；
- 默认不拥有高风险外部写工具。

### 10.3 面试官

- 按岗位与候选材料生成结构化问题；
- 记录回答证据；
- 生成评价草稿；
- 最终录用结论必须由人确认。

发布流程：

```text
draft definition
→ 跑岗位评测套件
→ 管理员审核
→ published version
→ AgentRun 固定引用版本
```

更新数字员工配置不得改变正在执行的 Run；新版本只影响新 Run。

---

## 11. Agent Eval 与可观测性

### 11.1 冻结场景

新增 `eval/fixtures/agent-v1/`，每条场景包含：

```text
initial_world
user_goal
allowed_tools
required_evidence_ids
expected_tool_calls
expected_arguments
approval_expectations
injected_failures
forbidden_actions
success_assertions
```

至少覆盖：

- 正常检索并创建工单；
- 工具首次超时后成功恢复；
- 写工具重复投递但只产生一次副作用；
- 用户中途修改目标；
- 检索到冲突或过期制度；
- 模型请求未授权工具；
- 审批拒绝后不得继续；
- worker 重启后恢复；
- 恶意文档尝试覆盖系统规则；
- 多模态证据定位到页码/时间戳。

### 11.2 指标

硬指标：

- Task Success Rate
- Tool Selection Accuracy
- Argument Exact/Field Accuracy
- Unauthorized Action Rate
- Approval Bypass Rate
- Duplicate Side-effect Rate
- Recovery Rate
- Citation Subset Rate
- tenant/persona leak count

效率指标：

- Average Steps per Successful Run
- Token/Cost per Successful Run
- Tool Calls per Successful Run
- p50/p95 Run Latency
- Human Handoff Rate

开放文本质量可以附加 LLM 评委，但不进入 P0 安全门禁。

### 11.3 基线

至少比较：

1. 当前单轮 tool calling；
2. bounded Agent loop；
3. bounded loop + step RAG；
4. bounded loop + step RAG + recovery/HITL。

所有简历提升数字都从版本化 baseline 读取，不手工挑选案例。

### 11.4 Trace 结构

```text
agent.run
├─ agent.step{kind=plan}
│  └─ llm.call
├─ agent.step{kind=retrieve}
│  ├─ rag.retrieve
│  ├─ rag.rerank
│  └─ rag.compile_context
├─ agent.step{kind=tool}
│  ├─ policy.check
│  ├─ approval.wait
│  └─ tool.call
└─ agent.step{kind=answer}
   └─ llm.call
```

所有 span 带 `tenant_id` 时必须使用不可逆或受控标识，不能把敏感内容直接作为 label。Prompt、工具参数和原文继续遵守采样、加密、TTL 与删除规则。

---

## 12. HTTP 与界面契约

在实现前先更新 `docs/openapi.yaml` 与 `docs/api.md`。

建议 API：

```text
POST   /v1/personas/{persona_id}/agent-runs
GET    /v1/agent-runs/{run_id}
GET    /v1/agent-runs/{run_id}/steps
POST   /v1/agent-runs/{run_id}/cancel
POST   /v1/agent-runs/{run_id}/resume
GET    /v1/approvals
POST   /v1/approvals/{approval_id}/approve
POST   /v1/approvals/{approval_id}/reject
POST   /v1/agent-eval/runs
```

创建 Run 接口默认返回 `202 Accepted`。读取接口返回状态和步骤摘要，不直接暴露完整 prompt 或未脱敏工具参数。

前端最小交付：

- Agent 任务列表；
- Run 时间线；
- 单步输入、证据、动作和结果；
- 等待审批队列；
- 失败后可恢复/转人工；
- 从 trace 跳转到 Run，从 Run 跳转到 trace；
- 评测对比页。

---

## 13. 推荐代码结构

```text
src/arbor/
├─ domain/
│  ├─ agent/
│  │  ├─ run.py
│  │  ├─ step.py
│  │  ├─ approval.py
│  │  └─ policy.py
│  └─ memory/
├─ application/
│  ├─ agent/
│  │  ├─ start_run.py
│  │  ├─ advance_run.py
│  │  ├─ approve_step.py
│  │  ├─ planner.py
│  │  └─ context.py
│  ├─ tools/
│  │  ├─ registry.py
│  │  ├─ executor.py
│  │  └─ schemas.py
│  └─ evaluation/
├─ ports/
│  ├─ inbound/
│  └─ outbound/
├─ adapters/
│  ├─ inbound/http/
│  └─ outbound/
│     ├─ postgres/
│     ├─ arq/
│     ├─ mcp/
│     └─ multimodal/
└─ observability/
```

领域层不得导入 ARQ、FastAPI、MCP SDK、模型 SDK 或 Postgres。

---

## 14. 分阶段开发计划

每个阶段建议独立 PR，避免同时修改 Runtime、RAG、记忆和 UI 后无法定位回归。

### Phase 0：场景契约与基线

交付：

- `agent-v1` 冻结场景格式；
- 当前单轮工具调用基线；
- 状态机 Given-When-Then 样例；
- 新 ADR：Agent Runtime、工具副作用、上下文可信边界。

验收：

- 场景能在 Fake LLM/Fake Tool 下确定性运行；
- 明确哪些指标阻断合并；
- 文档不声称 Runtime 已实现。

### Phase 1：持久化 Runtime

交付：

- AgentRun/Step 领域模型；
- Postgres 迁移、RLS、Repository；
- Start/Advance/Get/Cancel；
- ARQ 异步推进和重启恢复；
- Runtime spans/metrics。
- 保留现有 `SendMessage` HTTP 响应字段，将原单轮路径映射为 `max_steps=1` 的兼容运行模式。

验收：

- 改造前后的 `retrieval_meta`、`decision_trace`、引用和 SSE 结束事件保持兼容；
- worker 中断后可从最后已提交 Step 恢复；
- 并发消费不会重复推进；
- 达到任一预算立即终止；
- 跨租户读取为 P0 失败。

### Phase 2：Tool Registry、幂等与审批

交付：

- Schema 驱动注册表；
- 日历/工单迁移到统一 Executor；
- 风险策略、ApprovalRequest；
- 重试分类、幂等记录；
- 审批 API 与最小 UI。

验收：

- 未授权工具不会触达适配器；
- 重复工单请求只产生一个外部副作用；
- 未批准、拒绝、过期审批均不能执行；
- 工具超时场景按策略恢复或转人工。

### Phase 3：Step RAG 与上下文工程 v2

交付：

- RetrievalRequest/Result；
- ContextItem 与 context manifest；
- Planner 的 retrieve action；
- observation 后二次检索；
- prompt injection 可信边界；
- step retrieval/context 指标。

验收：

- 工具结果可触发基于新实体的二次检索；
- evidence/citation 只能引用实际注入项；
- 固定安全上下文不会被裁剪；
- 恶意文档不能扩大工具权限；
- 现有 RAG 基线不回退且泄漏仍为 0。

### Phase 4：Agent Memory

交付：

- `memory_class`、来源 Run/Step 与有效期；
- `VectorIndex.search(filters)` 支持 `memory_class`，现有稳定金标 ID 不迁移；
- Run 完成后的候选经验提取；
- Inbox 去重、冲突、确认；
- consolidation、失效与删除传播（`ConsolidateEpisodicMemories` + 删除派生 consolidation）；
- Memory Eval。

验收：

- 未确认经验不会进入 active 检索；
- superseded 与过期内容不进入上下文；
- 删除后 Repository、向量和 consolidation 不再命中；
- 任务经历可被后续 Run 检索并保留来源。

### Phase 5：多模态证据链

交付：

- Artifact/ArtifactSegment；
- 页码、时间戳、区域与 parser version；
- 原文件到回答/action 的 lineage；
- 更新文件后的版本失效；
- 分层多模态评测。

验收：

- PDF 回答可定位页码；
- 音频回答可定位时间段；
- 感知错、检索错、生成错能分别归因；
- 原始对象删除后派生内容按策略清理。

### Phase 6：Agent Eval 与运行观测

交付：

- `agent-v1` 评测 runner 与版本化 baseline；
- Fake Planner、Fake Tool、故障注入和虚拟时钟；
- PR 使用无外部密钥的 `agent-smoke`，nightly 使用真实模型轨；
- AgentRun → Step → RAG/Tool/Approval trace 树；
- Task、工具、安全、恢复、成本与延迟指标。

验收：

- 至少覆盖正常完成、二次检索、审批、拒绝、越权、超时、幂等和重启恢复；
- `Unauthorized Action Rate`、`Approval Bypass Rate`、`Duplicate Side-effect Rate` 和跨租户泄漏均为 0；
- 任务成功率与效率指标写入 `eval/baselines/`，可按 runtime/planner 版本比较；
- Agent Eval 不替代现有检索泄漏和 citation subset 门禁；
- Tempo 可从一个 Run 定位完整步骤树，指标标签不包含 prompt 或敏感工具参数。

### Phase 7：数字员工治理与演示

交付：

- 版本化岗位定义；
- 客服、导师、面试官三个模板；
- 岗位评测门禁；
- Run/Approval/Eval 管理界面；
- 完整演示脚本与录屏。

验收：

- 每个 Run 固定 employee definition 版本；
- 模板能力、工具、审批与转人工策略确实不同；
- 发布新版本不改变执行中的 Run；
- 演示可通过一次故障注入证明恢复和幂等。

### Phase 8：MCP 与可选多 Agent

先完成 MCP Adapter。只有以下条件至少满足一项才拆多 Agent：

- 不同 Worker 有独立工具权限；
- 子任务上下文必须强隔离；
- 需要不同模型或成本策略；
- 单 Agent 场景评测证明拆分能改善结果。

多 Agent 仍共享 AgentRun 账本、Policy、Approval、ContextCompiler 和评测协议。

---

## 15. 端到端演示

主场景：客服数字员工处理会议室空调故障。

1. 用户上传故障照片并发送语音描述；
2. Artifact Pipeline 保存原件，生成带坐标的图片描述和带时间戳的转写；
3. Agent 创建 Run，加载客服岗位版本和预算；
4. Planner 请求检索设备 SOP 与历史故障；
5. Step RAG 命中维修手册页和过去处理经历；
6. ContextCompiler 注入任务、证据和权限，隔离文档中的不可信指令；
7. Agent 查询资产/日历工具；
8. observation 暴露真实设备型号与图片推测不同，Agent 用新型号再次检索；
9. Agent 提出高优先级工单，进入人工审批；
10. 用户修改可维修时间并批准；
11. 工单首次调用超时，Executor 使用同一幂等键确认或重试；
12. Run 完成，回答返回工单号及 SOP 页码引用；
13. 本次恢复经验形成候选 episodic memory，进入 Inbox；
14. Debug 页面展示 Run → Step → RAG → Tool → Approval 完整轨迹。

这个场景同时证明：

- 任务型 Agent，而非单轮聊天；
- 动态 RAG 和上下文工程；
- 工作、情景、语义、程序性记忆；
- 多模态证据；
- 权限、审批、幂等和恢复；
- 可观测与可评测。

---

## 16. 简历证据与发布门槛

完成 Phase 1～3 后可写：

> 设计并实现多租户数字员工 Agent Runtime，通过持久化状态机编排规划、逐步检索、工具执行和人工审批，支持任务预算、断点恢复、幂等副作用及完整轨迹回放。

完成 Phase 4 后可增加：

> 构建工作、情景、语义与程序性分层记忆，任务经验经过来源追踪、去重、冲突检测和人工确认后进入长期记忆，支持版本替代与删除传播。

完成 Phase 5 后可增加：

> 构建文档、图片和语音的多模态证据链，保留页码、时间戳、区域坐标与解析版本，并分别评测感知、检索、生成和任务执行质量。

量化条目模板：

> 在版本化 Agent 场景集上，相比单轮工具调用，任务成功率由 **X** 提升至 **Y**，故障恢复率为 **Z**；越权执行、审批绕过、重复副作用与跨租户泄漏均为 **0**。

`X/Y/Z` 只能来自提交到 `eval/baselines/` 的可复现结果。

### 16.1 完成定义

一项能力只有同时满足以下条件才算完成：

- 领域模型与不变式；
- 端口与至少一个真实适配器；
- 数据库迁移和租户隔离；
- HTTP/OpenAPI 契约（如对外）；
- 单元、契约、集成测试；
- 冻结场景与评测 baseline；
- 日志、指标和 trace；
- 安全、TTL、删除和脱敏说明；
- 演示路径；
- 文档与简历口径同步。

### 16.2 不应写入简历

- 在 Phase 1 前写“自主 Agent Runtime”；
- 仅接入 MCP 后写“构建 Agent 平台”；
- 将一次工具回调描述为多步自主规划；
- 将 caption/transcript 入库描述为原生多模态推理；
- 将 fixture embedding 分数说成生产模型表现；
- 将事件树扩跳描述为完整 GraphRAG；
- 将演示项目描述为已服务生产团队或大规模用户。

---

## 17. 开发决策检查表

每次新增能力先回答：

1. 这是领域规则、应用编排、端口还是适配器？
2. 模型输出失败、重复或恶意时，代码如何兜底？
3. 副作用是否有幂等键和可确认结果？
4. 是否需要审批、转人工或预算终止？
5. RAG 候选是否经过 ContextCompiler 才进入模型？
6. 上下文能否解释每个选择和裁剪原因？
7. 记忆是否有来源、有效期、冲突和删除路径？
8. 多模态结论能否回到页码、时间戳或区域？
9. 如何通过 Fake 端口确定性测试？
10. 哪个冻结场景和指标能证明改造有效？

如果这些问题没有答案，先补契约和评测，不要直接增加新的模型调用。
