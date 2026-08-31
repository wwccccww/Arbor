# 004 — Agent 生产化补强证据索引

面向 **Java 后端 / AI 应用 / Agent** 岗位。对外粘贴项目经历仍用 [003-polished-external-copy.md](003-polished-external-copy.md)；本文件为 **可复现证据链**，供面试演示与 CI 对照。

## 一键命令

| 用途 | 命令 |
|------|------|
| 本地工作台 | `./scripts/run.sh` |
| Agent 演示 + 证据链 | `./scripts/demo-agent.sh` |
| 十三步离线验证 | `python3 -m pytest tests/eval/test_demo_v1_smoke.py -q` |

## 评测与 baseline（离线、Fake Planner）

| 能力 | Fixture | Baseline | 测试 |
|------|---------|----------|------|
| Agent 任务 smoke | `eval/fixtures/agent-v1/` | `agent-v1-smoke.json` | `test_agent_smoke.py` |
| 公平四轨消融 | `agent-ablation-v1/` | `agent-ablation-v1.json` | `test_agent_ablation.py` |
| 安全场景 | `agent-security-v1/` | `agent-security-v1-smoke.json` | `test_agent_security_smoke.py` |
| 记忆生命周期 | `memory-v1/`（15 cases） | `memory-v1-smoke.json` | `test_memory_smoke.py` |
| 多模态证据 | `multimodal-v1/` | `multimodal-v1-smoke.json` | `test_multimodal_smoke.py` |
| **演示证据链** | `demo-v1/manifest.json`（13 步含 e2e-agent-chain） | `demo-v1-smoke.json` | `test_demo_v1_smoke.py` |

## P0 指标口径（均为 0 才过 gate）

- `unauthorized_action_rate`
- `approval_bypass_rate`
- `duplicate_side_effect_rate`
- `tenant_leak_rate`

## 架构交付物

- PlannerPort + LLMPlanner：`src/arbor/ports/outbound/planner.py`
- 数字员工 PG：`src/arbor/adapters/outbound/postgres/employee.py`
- OpenAPI 契约：`docs/openapi.yaml` + `scripts/validate_openapi_fastapi.py`
- 观测阻断 CI：`observability-integration` job（Loki/Tempo）

## 演示录屏

- 脚本：`docs/demo-script.md` §Agent 生产化演示
- 文件：`docs/demo/recordings/agent-production-demo.mp4`（demo-v1 + Agent API 契约 pytest 录屏）

## 建议简历补充句（补强完成后）

> 构建可插拔 LLM Planner 与同场景四轨 Agent 消融评测，通过结构化动作校验、Step RAG、断点恢复和 HITL 提升任务成功率，并以版本化 baseline 约束安全、延迟和成本回归。

量化注明：agent-v1 / demo-v1、Fake Planner、7–15 case、离线 CI、P0 定义见上表。
