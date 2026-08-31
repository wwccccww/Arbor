# 公开基准结果（简历口径）

> 私有冻结评测证明回归稳定；公开基准证明在第三方任务上仍可复现。  
> **Fake Planner** 与 **真实 LLM** 分轨报告，禁止混报。

## 双栏对比（2026-08-31 · 档位 A）

| 维度 | 私有冻结评测 | 公开基准 |
|---|---|---|
| 任务 / 工具调用 | agent-ablation-v1 完整轨 task 100% | BFCL 官方 dev **200 题** · LLM task **0.64** / function **0.94** |
| 安全 | agent-security-v1 P0=0 | AgentDojo workspace **46 题** attack_success **0.00** |
| 多跳检索 | suite-v1 Recall@5 100% | MultiHop 官方 dev **100 题** supporting_recall **1.00** |

## 公开基准明细

| 基准 | 套件 | 数据来源 | Planner | Cases | 关键指标 |
|---|---|---|---|---:|---|
| BFCL | `public-bfcl-smoke` | 自建 smoke | fake | 12 | function/argument 1.0 |
| BFCL | `public-bfcl-dev` | **官方 HF v3 冻结子集** | fake | **200** | task 1.0（回归基线） |
| BFCL | `public-bfcl-dev-llm` | **同上官方 dev** | **DeepSeek LLM** | **200** | task **0.64**, function **0.94**, argument **0.66** |
| AgentDojo | `public-agentdojo-smoke` | 自建 smoke | fake | 5 | utility 1.0, attack 0.0 |
| AgentDojo | `public-agentdojo-dev` | **官方 v1.2 workspace** | fake | **46** | utility 1.0, attack 0.0 |
| MultiHop-RAG | `public-multihop-smoke` | 自建 smoke | fake | 5 | supporting_recall 1.0 |
| MultiHop-RAG | `public-multihop-dev` | **官方 HF 分层抽样** | fake | **100** | supporting_recall 1.0 |

### BFCL 官方 dev 组成（200 题）

| 类别 | 题数 | 说明 |
|---|---:|---|
| simple | 73 | `BFCL_v3_simple.json` 前 73 题 |
| multiple | 55 | 多函数选择 |
| parallel | 36 | 并行多调用 |
| irrelevance | 36 | 不应调用工具 |

### AgentDojo 官方 workspace dev（46 题）

| 类别 | 题数 | 说明 |
|---|---:|---|
| utility | 40 | 官方 workspace 全部 user_task |
| security | 6 | 官方 injection_task 0–5 |

### MultiHop 官方 dev（100 题）

| 类别 | 题数 |
|---|---:|
| inference_query | 30 |
| comparison_query | 30 |
| temporal_query | 25 |
| null_query | 15 |

## 复现命令

```bash
python3 scripts/fetch_public_benchmarks.py --benchmark all --only smoke
python3 scripts/build_bfcl_dev_subset.py
python3 scripts/build_agentdojo_dev_subset.py
python3 scripts/build_multihop_dev_subset.py

python3 -m pytest tests/eval/public -q -m "not llm"
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-dev --mode agent
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-agentdojo-dev --mode agent
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-multihop-dev --mode agent

# Nightly LLM（BFCL 200 题）
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-dev-llm --mode agent --planner llm
```

## 简历表述（推荐）

> 接入 **BFCL 官方 v3 dev（200 题）**、**AgentDojo workspace（46 题）**、**MultiHop-RAG dev（100 题）** 三套第三方冻结子集；CI 用 Fake Planner 做 100% 回归，Nightly DeepSeek 报告 BFCL task **64%** / function_match **94%**（2026-08-31，**dev 子集非完整榜单**）。

## 局限（务必如实）

- BFCL 200 / MultiHop 100 / AgentDojo 46 均为**官方全集的子采样**。
- BFCL LLM 使用 Arbor 多轮规划器，**非**官方 leaderboard 完整协议。
- MultiHop dev 当前为 fake plan_script 回归，**非**真实 RAG 检索+生成 LLM 分数。

## 不要写

> BFCL / AgentDojo / MultiHop 榜单 SOTA 或全面超越官方 baseline。
