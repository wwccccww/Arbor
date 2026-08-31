# Arbor Agent 生产化补强开发指南

- 状态：待实施
- 适用分支：`cursor/agent-impl-d39e` 及其后续分支
- 上游契约：[AI Agent 改造开发指南](ai-agent-development-guide.md)
- 当前证据：[Phase 0–8 完成度审计](agent-phase-completion-audit.md)
- 目标：将已经落地的 Agent 核心能力，从“确定性演示与 smoke 可用”推进到“证据可信、契约完整、可部署验证、可写入简历”

> 本文不是新增功能愿望清单。每个工作包都必须同时交付代码、迁移、测试、评测基线、可观测性和文档证据。

---

## 1. 当前基线与真实边界

当前已经具备：

- 持久化 `AgentRun` / `AgentStep` 状态机；
- PostgreSQL Repository、RLS、ARQ 异步推进与恢复；
- Tool Registry、审批、幂等和重试；
- Step RAG、Context Manifest 与二次检索；
- Memory、Multimodal、Agent 三类确定性评测；
- 数字员工模板、版本固定和岗位评测入口；
- MCP JSON-RPC / HTTP 工具适配；
- Agent Run 步骤树和 Tempo / Loki 跳转。

当前不能对外声称：

- 真实 LLM 已完成稳定自主规划；
- 四轨 `12.5% → 100%` 是公平消融或生产效果；
- 数字员工定义已经完整持久化；
- Working / Procedural Memory 已具备完整生命周期；
- Tempo 已通过生产环境验收；
- 已实现 Multi-Agent；
- 已完成原生多模态推理或生产 OCR / ASR 质量验收。

---

## 2. 开发优先级

| 顺序 | 工作包 | 直接解决的问题 | 完成后可获得的简历证据 |
|---|---|---|---|
| P0-1 | 公平四轨 Agent Eval | 当前四轨案例集合不同，数字不可宣传 | 同场景消融、可信 X/Y/Z |
| P0-2 | 可插拔真实 LLM Planner | 当前主要由 `ScriptedPlanner` 驱动 | 真实模型规划、结构化降级 |
| P0-3 | 数字员工 PostgreSQL 持久化 | 当前运行时使用内存定义仓库 | 版本化发布治理、RLS |
| P1-1 | 场景集与安全门禁补齐 | 注入、目标变更等只在局部测试 | 完整 Agent 安全回归集 |
| P1-2 | OpenAPI 与 API 契约闭环 | 当前 Agent API 多为路径级描述 | 可验证接口契约 |
| P1-3 | 可观测性强门禁 | Tempo job 非阻断，指标不完整 | 端到端运行证据 |
| P1-4 | 记忆生命周期补强 | Working / Procedural Memory 偏弱 | 四类记忆的准确表述 |
| P2 | 演示与简历证据包 | 录屏与可复现材料不足 | 可展示 Demo 与证据索引 |

除非出现明确的独立权限、上下文隔离或模型策略需求，暂不开发 Multi-Agent。

---

## 3. 工作包 P0-1：公平四轨 Agent Eval

### 3.1 目标

使用**同一组冻结场景**完成以下消融：

1. 单轮 tool calling；
2. bounded Agent loop；
3. bounded loop + Step RAG；
4. bounded loop + Step RAG + recovery / HITL。

不同轨道只能切换能力开关，不得改变案例集合、初始世界、模型、预算、评判规则或随机种子。

### 3.2 设计要求

新增：

```text
AgentEvalVariant
├─ id
├─ max_steps
├─ step_rag_enabled
├─ recovery_enabled
├─ approval_enabled
└─ planner_version
```

建议文件：

```text
src/arbor/application/evaluation/agent_variants.py
eval/fixtures/agent-ablation-v1/cases.json
eval/baselines/agent-ablation-v1.json
tests/eval/test_agent_ablation.py
```

要求：

- Runner 必须逐轨执行同一批 `case_id`；
- 对不支持某能力的轨道，应记为失败或 handoff，不得删除案例；
- baseline 写入 fixture 版本、variant、planner、模型、预算和生成时间；
- 禁止把 Fake Planner 指标描述为真实模型效果；
- CI 必须检查 P0 安全指标均为 0；
- Task Success Rate 只允许同案例集合横向比较。

### 3.3 指标

- Task Success Rate；
- Recovery Rate；
- Unauthorized Action Rate；
- Approval Bypass Rate；
- Duplicate Side-effect Rate；
- Tenant Leak Rate；
- Average / p95 Steps；
- Average / p95 Latency；
- Token / Cost per Successful Run；
- Human Handoff Rate。

### 3.4 验收

```bash
python3 -m pytest tests/eval/test_agent_ablation.py -q
python3 -m arbor.adapters.inbound.cli.eval_cli \
  --suite agent-ablation-v1 --mode agent --strategy all
```

验收条件：

- 四轨 `case_id` 集合完全相同；
- 相同固定种子重复执行结果一致；
- P0 安全指标为 0；
- baseline 与现场重跑结果一致；
- Checkup 页面显示每轨样本数和环境标签；
- 原 `agent-evolution-v1` 标记为历史/非公平基线，不再用于简历数字。

---

## 4. 工作包 P0-2：可插拔真实 LLM Planner

### 4.1 目标

保留 `ScriptedPlanner` 作为 PR 确定性测试实现，新增真实模型 Planner，但不得让模型绕过 Policy、Approval、Budget 或 ContextCompiler。

### 4.2 端口

```python
class PlannerPort(Protocol):
    def next_action(
        self,
        *,
        goal: str,
        steps: list[dict],
        context_manifest: dict,
        tool_schemas: list[dict],
        budget: dict,
    ) -> PlannerAction: ...
```

实现：

- `ScriptedPlanner`：Fake / PR smoke；
- `LLMPlanner`：真实模型；
- `FallbackPlanner`：格式错误或依赖失败时 handoff / safe answer。

### 4.3 安全要求

- 模型输出必须通过 JSON Schema 和 `validate_planner_action`；
- 工具名和参数由 Tool Registry 再次校验；
- 引用只能来自当前 Step 注入的 evidence；
- 超预算、连续无效动作、循环动作必须终止；
- Prompt、原文和工具参数不得写入指标标签；
- Planner metadata 必须记录 provider、model、prompt version、schema version；
- 不记录思维链；只记录结构化动作、理由摘要和证据 ID。

### 4.4 测试

- 合法 retrieve / tool / answer / handoff；
- 非法 JSON；
- 未知 action；
- 未授权工具；
- 伪造 evidence ID；
- 重复动作循环；
- Provider timeout / 429 / 5xx；
- Token / Cost / Step budget；
- 恶意证据试图覆盖系统规则。

### 4.5 Nightly

新增真实 Agent 轨：

```text
nightly-agent-llm
├─ 固定 agent-ablation-v1
├─ 固定模型和 Prompt 版本
├─ 写独立 baseline
├─ 不覆盖 Fake Planner baseline
└─ 缺少密钥时明确 skip
```

验收后简历才可使用“真实 LLM Planner”。

---

## 5. 工作包 P0-3：数字员工定义持久化

### 5.1 目标

将 `InMemoryEmployeeDefinitions` 降为测试适配器，实现 PostgreSQL 版本化定义仓库和发布门禁。

### 5.2 端口

```python
class EmployeeDefinitionRepository(Protocol):
    def create_draft(...): ...
    def get(...): ...
    def list_versions(...): ...
    def publish(...): ...
    def archive(...): ...
```

### 5.3 数据规则

- 主键必须包含 tenant / persona / version；
- 同租户同 Persona 只能有一个 active published version；
- published 版本不可原地修改；
- 发布新版本不改变运行中 Run；
- AgentRun 保存 definition version 和必要的不可变策略快照；
- 删除 Persona 时按明确策略归档定义；
- 所有读写使用 RLS 和应用层 tenant filter 双保险。

### 5.4 发布流程

```text
create draft
→ validate schema
→ run employee evaluation suite
→ require gate_passed
→ workspace admin publish
→ audit log
→ new AgentRun picks new version
```

### 5.5 验收

- PostgreSQL migration / repository / RLS 契约测试；
- 跨租户读写返回 P0 失败；
- 未通过岗位评测无法发布；
- v1 Run 在 v2 发布后仍使用 v1；
- API 重启后定义仍存在；
- UI 可查看版本、评测结果和发布状态。

---

## 6. 工作包 P1-1：冻结场景与安全门禁

在 `agent-v1` 或新版本中补齐：

| 场景 | 关键断言 |
|---|---|
| 用户中途修改目标 | 产生新版本/事件；旧目标不会继续执行副作用 |
| 恶意文档要求调用工具 | 工具权限不扩大；记录 untrusted 指标 |
| 冲突或过期制度 | 不进入 Context Manifest |
| 多模态定位 | action / answer 可回溯到页码、时间戳或区域 |
| 审批过期 | 外部适配器调用次数为 0 |
| Worker 并发重复消费 | Run 仅推进一次 |
| Token / Cost / Step 耗尽 | 立即终止并记录 failure kind |
| 原始对象删除 | 派生 evidence 和引用均失效 |

新增场景必须同步：

1. fixture；
2. Fake 端口；
3. runner 断言；
4. baseline；
5. CI gate；
6. 审计文档。

---

## 7. 工作包 P1-2：OpenAPI 与 HTTP 契约

补齐以下 Schema：

- `AgentRunCreateRequest`；
- `AgentRunSummary` / `AgentRunDetail`；
- `AgentStep` / `AgentStepTree`；
- `ApprovalRequest` / `ApprovalDecision`；
- `EmployeeDefinitionDraft` / `EmployeeDefinitionVersion`；
- `EmployeeEvalReport`；
- `AgentEvalRun`；
- SSE `done` / `error` 事件；
- 通用错误体和 `request_id`。

规则：

- OpenAPI 先于路由实现更新；
- FastAPI 实际 schema 与 `docs/openapi.yaml` 做 CI diff；
- 每个公开路径至少一个成功和一个权限失败 API 测试；
- 关键错误码写入 `docs/api.md`；
- `plan_script` 只允许测试/管理员环境，不作为生产公共输入。

---

## 8. 工作包 P1-3：可观测性强门禁

### 8.1 Trace

```text
agent.run
├─ agent.step{kind=retrieve}
│  ├─ rag.retrieve
│  └─ rag.compile_context
├─ agent.step{kind=tool}
│  ├─ policy.check
│  ├─ approval.wait
│  └─ tool.call / mcp.call
└─ agent.step{kind=answer}
   └─ planner.call
```

### 8.2 指标

- run success / failed / handoff；
- p50 / p95 run latency；
- steps / tokens / cost per success；
- tool retry / timeout / idempotent hit；
- approval wait / reject / expire；
- selected / excluded context items；
- required context overflow；
- untrusted instruction；
- MCP latency / error；
- memory candidate / confirm / reject / conflict；
- artifact invalidation。

### 8.3 安全

指标标签禁止包含：

- Prompt、记忆原文和工具参数；
- 用户输入；
- 对象 URI；
- 可逆 tenant / user 标识。

内容型 trace 按采样、加密、TTL 与删除传播策略保存。

### 8.4 验收

- Loki / Tempo / Prometheus 集成 job 改为阻断；
- 测试从一个 Run ID 找到完整步骤树；
- 删除请求后加密内容不可再读取；
- Grafana Dashboard 包含 P0、安全、效率和依赖四组面板。

---

## 9. 工作包 P1-4：四类记忆生命周期

### Working Memory

- 仅属于 Run / Step；
- 有容量和 TTL；
- Run 完成后清理；
- 只有候选摘要可进入 Inbox。

### Episodic Memory

- 来源 Run / Step；
- 衰减、冲突、consolidation；
- 删除可传播到派生项。

### Semantic Memory

- 来源、版本、有效期；
- superseded / expired 不可进入上下文；
- 支持稳定 ID 与兼容迁移。

### Procedural Memory

- SOP 版本和适用范围；
- 审核后发布；
- 不允许 Agent 自动覆盖已发布程序性记忆；
- Run 固定使用版本。

验收必须为每类记忆提供独立 fixture、指标和删除测试，不能只用枚举值证明“已实现四类记忆”。

---

## 10. 工作包 P2：演示与简历证据包

### 10.1 演示流程

1. 上传图片与语音；
2. 展示页码、时间戳或区域证据；
3. 创建固定岗位版本的 Run；
4. 首次检索；
5. 工具返回新实体；
6. 二次检索；
7. 高风险工具进入审批；
8. 首次调用超时；
9. 使用同一幂等键恢复；
10. Run 完成并返回引用；
11. 经验进入 Inbox；
12. Tempo 展示完整 trace。

### 10.2 交付

- `docs/demo-script.md`；
- 3–5 分钟录屏；
- 一键启动命令；
- demo fixture；
- 预期输出；
- 测试和 baseline 链接；
- 简历证据索引。

录屏必须验证后再写入审计表，未入库时不得写“录屏已交付”。

---

## 11. 每个工作包统一完成定义

- [ ] 领域规则和不变式明确；
- [ ] Port 不依赖 Adapter；
- [ ] 至少一个真实 Adapter；
- [ ] Migration、RLS、回滚路径；
- [ ] OpenAPI / HTTP 契约；
- [ ] 单元、契约、集成测试；
- [ ] 同场景可重放 baseline；
- [ ] 日志、指标和 trace；
- [ ] 安全、TTL、删除、脱敏；
- [ ] UI 或 CLI 演示入口；
- [ ] 文档和简历口径同步；
- [ ] PR CI 全绿。

任何一项缺失时，状态写“核心已落地”或“部分实现”，不得写“生产完成”。

---

## 12. 开发提示词

以下提示词可直接交给 Cursor Agent。一次只执行一个工作包，避免跨 Runtime、RAG、Memory、UI 大范围并行修改。

### 12.1 通用实施提示词

```text
你正在 /workspace 的 Arbor 仓库工作。

目标：
实现 docs/agent-production-hardening-guide.md 中的【工作包名称】。

开始前：
1. 阅读 docs/ai-agent-development-guide.md、docs/agent-phase-completion-audit.md 和目标工作包。
2. 检查当前分支、未提交修改和现有测试；不得覆盖用户改动。
3. 先列出指南中每条交付/验收要求及对应证据路径。
4. 遵守六边形架构：domain/application 不得导入 adapters 或框架。

实现要求：
- 不用窄化需求或 Fake-only 实现替代最终目标。
- 新增领域规则先写 Given-When-Then 示例。
- 新增 HTTP 路径先更新 OpenAPI。
- 新增持久化数据必须包含 migration、RLS、Repository contract。
- 新增评测必须使用冻结 fixture 和版本化 baseline。
- P0 指标：tenant leak、unauthorized action、approval bypass、duplicate side effect 必须为 0。
- 指标标签不得包含 Prompt、工具参数、原文或可逆租户标识。

验证：
- 运行目标单元、契约、集成和评测测试。
- 运行 architecture import rules、ruff、mypy、OpenAPI 校验。
- 明确报告未执行或依赖外部服务的验证。

交付：
- 更新 docs/agent-phase-completion-audit.md，但仅记录已有强证据的内容。
- 提交并推送独立 commit。
- 给出变更摘要、测试结果、剩余风险。
```

### 12.2 公平四轨评测提示词

```text
实现 P0-1 公平四轨 Agent Eval。

硬性要求：
- 四轨必须运行完全相同的 case_id 集合。
- 使用 capability flags 做消融，不得按轨道过滤案例。
- 固定初始世界、Planner/模型、Prompt、预算和随机种子。
- 对缺失能力产生正常失败/handoff，不得跳过案例。
- baseline 记录 suite、variant、planner/model、prompt、预算、seed 和 case_count。
- 增加测试，断言四轨 case_id 集合完全一致。
- 原 agent-evolution-v1 标记为 historical，不得作为简历提升数字。
- Checkup 展示样本数、运行环境和 Fake/Real 标签。
```

### 12.3 LLM Planner 提示词

```text
实现 P0-2 可插拔真实 LLM Planner。

保留 ScriptedPlanner 用于 PR smoke；新增 PlannerPort、LLMPlanner、FallbackPlanner。
模型只输出结构化 PlannerAction；所有动作必须继续经过 schema、Policy、Approval、
Tool Registry、ContextCompiler 和 Budget 校验。

必须覆盖：
- invalid JSON/action/tool/evidence；
- timeout/429/5xx；
- 循环动作与预算终止；
- 恶意 evidence；
- provider/model/prompt/schema version metadata；
- nightly 真实 Agent 轨；
- 不记录思维链和敏感原文。
```

### 12.4 数字员工持久化提示词

```text
实现 P0-3 数字员工 PostgreSQL 持久化。

新增 EmployeeDefinitionRepository Port、Postgres Adapter、migration/RLS 和 API。
发布流程必须为 draft → eval gate → admin publish → audit。
published 版本不可原地修改；AgentRun 固定 version + 策略快照。
跨租户读取是 P0；API 重启后数据必须保留。
InMemoryEmployeeDefinitions 只保留为测试 Adapter。
```

### 12.5 安全场景提示词

```text
实现 P1-1 Agent 安全与恢复场景集。

补齐：目标中途变更、恶意文档、冲突/过期制度、多模态定位、审批过期、
并发重复消费、三类预算耗尽、对象删除传播。

每个场景必须包含 initial_world、goal、actions、injected_failures、
expected side effects、P0 assertions，并进入版本化 baseline 和 CI。
不能只写函数级单元测试来替代 Agent 场景级验收。
```

### 12.6 OpenAPI 提示词

```text
实现 P1-2 Agent/Employee OpenAPI 契约闭环。

为所有 AgentRun、Step、Approval、EmployeeDefinition、EmployeeEval、AgentEval、
SSE done/error 定义 request/response/error schemas。
增加 FastAPI 实际 schema 与 docs/openapi.yaml 的 CI 对齐检查。
每个公开端点至少覆盖成功、未认证、跨租户/无权限三类 API 测试。
plan_script 不得作为普通生产调用者可用字段。
```

### 12.7 可观测性提示词

```text
实现 P1-3 Agent 可观测性强门禁。

建立 agent.run 根 span 以及 rag.compile_context、policy.check、approval.wait、
tool.call、mcp.call、planner.call 子 span；补齐成功率、p95 延迟、成本、重试、
审批、上下文、MCP、记忆和 artifact 指标。

将 Loki/Tempo/Prometheus 集成测试改为阻断 CI。
证明从 Run ID 可定位完整 trace，且 labels 不包含 Prompt、工具参数或敏感标识。
```

---

## 13. 建议简历口径

补强完成前，建议使用：

> 设计并实现多租户 Agent Runtime，以持久化 Run/Step 状态机编排逐步检索、工具调用与人工审批，支持任务预算、ARQ 异步恢复和幂等副作用控制；建立 Agent、Memory 与 Multimodal 确定性场景评测并接入 CI。

公平消融和真实 Planner 完成后，才可补充：

> 构建可插拔 LLM Planner 与同场景四轨 Agent 消融评测，通过结构化动作校验、Step RAG、断点恢复和 HITL 提升任务成功率，并以版本化 baseline 约束安全、延迟和成本回归。

量化结果必须注明：

- 数据集名称和版本；
- Fake 还是真实模型；
- 样本数；
- 是否同案例集对比；
- 是否为离线结果；
- P0 指标定义。

---

## 14. 推荐执行顺序

```text
公平四轨 Eval
→ PlannerPort + 真实 LLM Planner
→ 数字员工 PostgreSQL Repository
→ 安全/恢复场景补齐
→ OpenAPI 契约
→ 可观测性阻断门禁
→ 四类记忆生命周期补强
→ 演示录屏与简历证据包
```

每完成一个工作包，重新执行 §11 完成定义，并更新审计状态。不要在证据不足时提前修改指南状态为“生产完成”。
