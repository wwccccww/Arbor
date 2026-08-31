# 公开基准结果（简历口径）

> 私有冻结评测证明回归稳定；公开基准证明在第三方任务上仍可复现。  
> **Fake Planner smoke** 与 **真实 LLM nightly** 分轨报告，禁止混报。

## 双栏对比（2026-08-31 · smoke · Fake Planner）

| 维度 | 私有冻结评测 | 公开基准 smoke |
|---|---|---|
| 任务 / 工具调用 | agent-ablation-v1 完整轨 task 100% | BFCL function_match **1.00**，argument_match **1.00**（12 cases） |
| 安全 | agent-security-v1 P0=0（11 cases） | AgentDojo attack_success **0.00**，data_leak **0.00**（5 cases） |
| 多跳检索 | suite-v1 layered_tree Recall@5 100% | MultiHop supporting_recall **1.00**，answer_em **1.00**（5 cases） |

## 公开基准明细

| 基准 | 套件 | Planner | Cases | 关键指标 |
|---|---|---|---:|---|
| BFCL | `public-bfcl-smoke` | fake | 12 | function_match=1.0, argument_match=1.0, executable=1.0 |
| AgentDojo | `public-agentdojo-smoke` | fake | 5 | utility=1.0, attack_success=0.0, unauthorized=0.0 |
| MultiHop-RAG | `public-multihop-smoke` | fake | 5 | supporting_recall=1.0, answer_em=1.0, faithfulness=1.0 |

## 复现命令

```bash
python3 scripts/fetch_public_benchmarks.py --benchmark all --only smoke
python3 -m pytest tests/eval/public -q
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-smoke --mode agent
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-agentdojo-smoke --mode agent
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-multihop-smoke --mode agent
```

Nightly（需 `DEEPSEEK_API_KEY`）归档至 `eval/public/runs/`。

## 简历表述（可用）

> 接入 BFCL / AgentDojo / MultiHop-RAG 公开基准 smoke 子集，CI 报告工具调用准确率、攻击防御率与多跳检索指标；私有 `eval/fixtures/*` 用于回归，公开基准用于外部可比。

## 不要写

> RAG/Agent 全面超越 SOTA（除非完整官方榜 + 注明协议与模型）。
