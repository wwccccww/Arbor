# Agent Phase 0–8 完成度审计

对照 `docs/ai-agent-development-guide.md` §14 与 §16.1。状态：**核心交付已落地**；本表记录可复现证据路径。

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
| 审批 API/UI | `register_agent.py` approvals；`AgentRunsPage.tsx` |
| 验收 | `tests/unit/application/test_tool_idempotency.py`；agent-v1 `forbidden-tool`、`ticket-timeout-retry` |

## Phase 3：Step RAG / 上下文 v2

| 交付 | 证据 |
|------|------|
| StepRetrieval + manifest | `application/agent/step_retrieval.py`、`context_engine.py` |
| 二次检索 | agent-v1 `second-retrieve-after-tool` |
| 可信边界 | ADR 0011；`detect_untrusted_instructions` |
| RAG 不回退 | `test_retrieval_baseline_gate.py`；CI postgres eval_cli |

## Phase 4：Agent Memory

| 交付 | 证据 |
|------|------|
| memory_class / 有效期 / 衰减 | `application/memory/validity.py`、`decay.py`；PG `test_memory_class_contract.py` |
| consolidation / 删除传播 | `consolidate_episodes.py`；memory-v1 smoke |
| Memory Eval 全指标 | `memory_runner.py`；9 cases；`memory_write_precision`、`memory_helpfulness_rate`、`conflict_injection_rate` |

## Phase 5：多模态证据链

| 交付 | 证据 |
|------|------|
| Artifact/Segment/Lineage | `application/multimodal/`；`migrations/0016_*` |
| 分层评测 perception/retrieval/generation/agent | `multimodal-v1` 5 cases |
| 对象删除失效 | `InvalidateArtifactsForObjectUri`；`test_invalidate_artifacts.py` |

## Phase 6：Agent Eval / 观测

| 交付 | 证据 |
|------|------|
| agent-v1 runner + baseline | `agent_runner.py`；`eval/baselines/agent-v1-smoke.json` |
| 步骤树 UI | `step_tree.py`；`AgentStepTree.tsx` |
| 延迟/成本 + eval_runs 入库 | `advance_run.py` metadata；`StartAgentEvalRun` → `eval_runs`；`test_start_agent_eval.py` |
| Run → Tempo trace | `start_run`/`advance_run` `request_id`/`trace_id`；`cancel_run._run_dict`；`AgentRunsPage` Tempo/Loki 链接 |
| 演示录屏 | `artifacts/agent-eval-fault-injection-demo.mp4` |

## Phase 7：数字员工治理

| 交付 | 证据 |
|------|------|
| 三模板 + 版本固定 | `employee_templates.py`；`test_employee_templates.py`；`test_start_run_pins_employee_definition_version` |
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

## 仍依赖外部环境验证的项

- Nightly 真实模型轨（`ARBOR_JUDGE_API_KEY` / DeepSeek）
- 生产 Tempo 从 Agent Run trace_id 端到端（本地 observability job `continue-on-error`）
- 全量多 Agent（Phase 8 明确为可选，当前未拆分）
