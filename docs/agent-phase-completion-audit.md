# Agent Phase 0–8 完成度审计

对照 `docs/ai-agent-development-guide.md` §14 与 §16.1。状态：**核心交付已落地**；本表记录可复现证据路径。

仍需补齐的演示证据包（P2），按 [Agent 生产化补强开发指南](agent-production-hardening-guide.md) 执行；**P0–P2 核心 gap 已补齐**（agent-security 11 场景、Planner 测试、观测 span/指标、OpenAPI/api.md、Grafana Agent 面板等），见下表。

## 横切 invariant

| 要求 | 证据 |
|------|------|
| SendMessage 兼容 | `tests/unit/application/test_agent_compat_chat.py`；`ARBOR_AGENT_COMPAT_CHAT=1` → `max_steps=1` |
| 租户隔离 P0 | `tests/unit/application/test_agent_tenant_isolation.py`；`tests/contract/postgres/test_agent_tenant_isolation.py`；`tests/contract/postgres/test_membership_isolation.py` |
| 检索基线不回退 | CI `eval_cli --suite v1 --backend postgres`；`tests/eval/test_retrieval_baseline_gate.py`（memory 轨门禁） |
| 每阶段迁移/测试/基线 | 见下表各行 |

## Phase 0：场景契约与基线

| 交付 | 证据 |
|------|------|
| agent-v1 冻结场景 | `eval/fixtures/agent-v1/cases.json` |
| Given-When-Then 样例 | `tests/examples/agent.yaml` + `tests/unit/domain/test_agent_examples.py` |
| ADR Runtime / 工具副作用 / 上下文可信 | `docs/adr/0010-agent-runtime.md`、`0011-agent-tool-side-effects.md` |
| 阻断合并指标 | CI `agent-smoke` job；`eval/baselines/*-smoke.json` |

## Phase 1：持久化 Runtime

| 交付 | 证据 |
|------|------|
| AgentRun/Step + PG 迁移 | `src/arbor/domain/agent/`；`migrations/0014_agent_runtime.py`、`0015_agent_rls.py` |
| Start/Advance/Get/Cancel/Resume | `application/agent/*`；HTTP `register_agent.py` |
| ARQ worker | `adapters/outbound/arq/agent_runner.py` |
| SendMessage 兼容路径 | `application/agent/compat_chat.py` |
| 验收：预算/恢复/租户 | `tests/unit/domain/test_agent_run.py`；`test_agent_concurrent_advance.py`；agent-v1 `worker-resume` case |

## Phase 2：Tool Registry / 幂等 / 审批

| 交付 | 证据 |
|------|------|
| Registry + Executor | `application/agent/tool_executor.py`、`application/tools/registry.py` |
| 重复送达幂等 | agent-v1 `duplicate-delivery-idempotent`；`EvalTicketTool` |
| 审批 API/UI | `register_agent.py` approvals；`AgentRunsPage.tsx` |
| 验收 | `tests/unit/application/test_tool_idempotency.py`；agent-v1 `forbidden-tool`、`ticket-timeout-retry` |

## Phase 3：Step RAG / 上下文 v2

| 交付 | 证据 |
|------|------|
| StepRetrieval + manifest | `application/agent/step_retrieval.py`、`context_engine.py` |
| 二次检索 | agent-v1 `second-retrieve-after-tool` |
| 可信边界 | ADR 0011；`detect_untrusted_instructions`；`test_context_engine_untrusted.py` |
| RAG 不回退 | `test_retrieval_baseline_gate.py`；CI postgres eval_cli |

## Phase 4：Agent Memory

| 交付 | 证据 |
|------|------|
| memory_class / 有效期 / 衰减 | `application/memory/validity.py`、`decay.py`；PG `test_memory_class_contract.py` |
| consolidation / 删除传播 | `consolidate_episodes.py`；memory-v1 smoke |
| Memory Eval 全指标 | `memory_runner.py`；**15 cases**；`memory_write_precision`、`memory_helpfulness_rate`、`conflict_injection_rate` |

## Phase 5：多模态证据链

| 交付 | 证据 |
|------|------|
| Artifact/Segment/Lineage | `application/multimodal/`；`migrations/0016_*` |
| 分层评测 perception/retrieval/generation/agent | `multimodal-v1` 5 cases |
| 对象删除失效 | `InvalidateArtifactsForObjectUri`；`test_invalidate_artifacts.py` |

## Phase 6：Agent Eval / 观测

| 交付 | 证据 |
|------|------|
| agent-v1 runner + baseline | `agent_runner.py`；`eval_cli --mode agent`；`eval/baselines/agent-v1-smoke.json` |
| §11.3 四轨演进基线 | `agent_evolution.py`；`eval/baselines/agent-evolution-v1.json`；`test_agent_evolution.py`；Checkup 四轨表 |
| 步骤树 UI | `step_tree.py`；`AgentStepTree.tsx` |
| 延迟/成本 + eval_runs 入库 | `advance_run.py` metadata；`StartAgentEvalRun` → `eval_runs`；`test_start_agent_eval.py` |
| Run → Tempo trace | `start_run`/`advance_run` `request_id`/`trace_id`；`cancel_run._run_dict`；`AgentRunsPage` Tempo/Loki 链接 |
| 演示录屏 | `docs/demo/recordings/agent-production-demo.mp4` + 离线 demo-v1（13 步） |

## Phase 7：数字员工治理

| 交付 | 证据 |
|------|------|
| 三模板 + 版本固定 | `employee_templates.py`；`test_employee_templates.py`；`test_start_run_pins_employee_definition_version`；`test_employee_definition_version_pinning.py` |
| 岗位评测门禁 | `POST /v1/personas/{id}/employee-eval`；`StartEmployeeEvalRun`；`test_start_employee_eval.py`；`AgentRunsPage` 按钮 |
| Run/Approval/Eval UI | `AgentRunsPage.tsx`、`Checkup.tsx`（基线表 + Agent 对比） |
| 演示脚本 | `docs/demo-script.md` |

## Phase 8：MCP

| 交付 | 证据 |
|------|------|
| JSON-RPC + HTTP 传输 | `adapters/outbound/mcp/` |
| 外部 HTTP E2E | `tests/integration/test_mcp_external_http_e2e.py` |
| Registry 注册 | `test_mcp_stub.py`；agent smoke MCP transport |

## §16.1 检查清单（摘要）

| 条件 | Agent 域覆盖 |
|------|----------------|
| 领域模型 | `domain/agent/*` |
| 端口 + 适配器 | inmemory + postgres `agent.py` |
| 迁移 + RLS | 0014/0015 |
| HTTP 契约 | `register_agent.py`、`openapi` |
| 测试 | unit + contract + eval smoke |
| 冻结场景 + baseline | `eval/fixtures/*`、`eval/baselines/*` |
| 指标/trace | `advance_run` spans；`metadata.metrics`；Grafana/Tempo 链接 Debug 页 |
| 演示 | demo-script + 录屏 |

## §16.1 逐能力完成定义（10 项）

每项能力须同时满足：领域模型、端口+适配器、迁移+租户隔离、HTTP/OpenAPI、测试、冻结场景+baseline、日志指标 trace、安全/TTL/删除、演示路径、文档同步。

| 能力 | 领域 | 端口/适配器 | 迁移/RLS | HTTP/OpenAPI | 测试 | 场景/baseline | 观测 | 安全/删除 | 演示 | 文档 |
|------|------|-------------|----------|--------------|------|---------------|------|-----------|------|------|
| Agent Runtime | `domain/agent/run.py` `step.py` | inmemory + `postgres/agent.py` | 0014/0015 | `register_agent.py` | unit + contract + agent-v1 | `agent-v1` + smoke baseline | spans + Tempo 集成测 | 租户隔离 PG 契约 | demo-script | ADR 0010 |
| Tool/审批 | `tool_executor.py` `approval.py` | tool_executions PG | 0014 | approvals API | idempotency + agent-v1 | forbidden-tool case | executor metrics | 审批绕过率=0 | 故障注入录屏 | ADR 0011 |
| Step RAG/上下文 | `step_retrieval.py` `context_engine.py` | vector + memory repos | memory RLS | manifest in run metadata | second-retrieve case | RAG baseline gate | context manifest UI | injection 检测 | — | ADR 0011 |
| Agent Memory | `memory_class` `validity` `decay` | memory PG | memory migrations | memory HTTP | memory-v1 15 cases | memory-smoke baseline | — | 删除传播 invalidate | — | guide §9 |
| 多模态证据链 | `application/multimodal/` | artifacts PG | 0016/0017 | artifact routes | multimodal-v1 5层 | multimodal-smoke | lineage UI | 对象删除失效 | — | guide §9.5 |
| Agent Eval | `agent_runner.py` | eval_runs repo | eval_runs table | `/agent-eval/runs` | `test_start_agent_eval` | `agent-v1-smoke.json` | eval_runs metrics | P0 安全指标 | 录屏 | Checkup 对比表 |
| 数字员工 | `employee.py` templates | inmemory templates | employee_definitions | employee-definition + employee-eval | templates + pinning + employee eval | evaluation_suite 门禁 | AgentRunsPage | 岗位评测 gate | AgentRunsPage | guide §10 |
| MCP | `adapters/outbound/mcp/` | jsonrpc + http transport | — | tools via MCP | `test_mcp_external_http_e2e` | agent smoke MCP | — | — | — | guide §8 |

## 仍依赖外部环境验证的项

- Nightly 真实模型轨（`ARBOR_JUDGE_API_KEY` / DeepSeek）— `nightly.yml` generation-llm job
- Nightly Agent smoke（Fake Planner）— `nightly.yml` agent-smoke job
- 生产 Tempo Agent Run 端到端 — `test_tempo_trace_search_by_agent_run_request_id`（CI `observability-integration` 阻断 job）

## 生产化补强 P0–P1（agent-production-hardening-guide）

| 工作包 | 证据 |
|--------|------|
| P0-1 公平四轨消融 | `agent_ablation.py`；`eval/fixtures/agent-ablation-v1/`；`eval/baselines/agent-ablation-v1.json`；`test_agent_ablation.py` |
| P0-2 PlannerPort | `ports/outbound/planner.py`；`LLMPlanner`/`FallbackPlanner`；`test_planner_port.py` |
| P0-3 数字员工 PG | `postgres/employee.py`；`employee_commands.py`；`test_pg_employee_definition.py` |
| P1-1 安全场景 | `agent_security_runner.py`（P0 指标非硬编码）；`agent-security-v1` 11 cases + category 元数据 + baseline |
| P1-2 OpenAPI/契约 | `docs/openapi.yaml` + `docs/api.md` §8；`test_agent_contracts.py`（含 reject 成功/403） |
| P1-3 观测强门禁 | `observability-integration` job 等待 Loki/Tempo + `OBSERVABILITY_INTEGRATION_REQUIRED`；`arbor_tool_call_total` |
| P1-4 四类记忆 | `eval/fixtures/memory-classes-v1/` 四类独立 fixture + `test_memory_classes_smoke.py` |
| P0-3 PG 持久化 HTTP | `test_postgres_agent_run_survives_app_restart` |
| P0-2 LLM baseline 结构 | `test_agent_ablation_llm_baseline.py`；nightly 写入 `task_success_rate` |
| P2 演示证据 | demo-v1 13 步 + `test_agent_contracts.py`；录屏为 CLI/pytest 片段（非 §10.1 完整 UI 流程） |
