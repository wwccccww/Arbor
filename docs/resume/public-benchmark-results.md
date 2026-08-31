# 公开基准结果（简历口径）

> 私有冻结评测证明回归稳定；公开基准证明在第三方任务上仍可复现。  
> **Fake Planner** 与 **真实 LLM** 分轨报告，禁止混报。

## 双栏对比（2026-08-31）

| 维度 | 私有冻结评测 | 公开基准 |
|---|---|---|
| 任务 / 工具调用 | agent-ablation-v1 完整轨 task 100% | BFCL 官方 dev 55 题 · LLM task **0.65** / function **0.94** |
| 安全 | agent-security-v1 P0=0 | AgentDojo 官方 dev attack_success **0.00**（13 题） |
| 多跳检索 | suite-v1 Recall@5 100% | MultiHop smoke supporting_recall **1.00**（5 题 smoke） |

## 公开基准明细

| 基准 | 套件 | 数据来源 | Planner | Cases | 关键指标 |
|---|---|---|---|---:|---|
| BFCL | `public-bfcl-smoke` | 自建 smoke | fake | 12 | function/argument 1.0 |
| BFCL | `public-bfcl-dev` | **官方 HF v3 冻结子集** | fake | 55 | task 1.0（回归基线） |
| BFCL | `public-bfcl-dev-llm` | **同上官方 dev** | **DeepSeek LLM** | 55 | task **0.65**, function **0.94**, argument **0.70** |
| AgentDojo | `public-agentdojo-smoke` | 自建 smoke | fake | 5 | utility 1.0, attack 0.0 |
| AgentDojo | `public-agentdojo-dev` | **官方 v1.2 workspace** | fake | 13 | utility 1.0, attack 0.0 |
| MultiHop-RAG | `public-multihop-smoke` | 自建 smoke | fake | 5 | supporting_recall 1.0 |

### BFCL 官方 dev 组成

| 类别 | 题数 | 说明 |
|---|---:|---|
| simple | 20 | `BFCL_v3_simple.json` 前 20 题 + 官方 ground truth |
| multiple | 15 | 多函数选择 |
| parallel | 10 | 并行多调用（v2 多轮规划器 + 无序匹配，LLM parallel 8/10） |
| irrelevance | 10 | 不应调用工具 |

### AgentDojo 官方 dev 组成

| 类别 | 题数 | 说明 |
|---|---:|---|
| utility | 8 | 官方 workspace user_task ground truth 工具序列 |
| security | 5 | 官方 injection_task（send_email / delete_file / share_file） |

## 复现命令

```bash
# 校验 smoke + 官方 dev 文件
python3 scripts/fetch_public_benchmarks.py --benchmark all --only smoke

# 从官方包重建 AgentDojo dev（需 pip install agentdojo）
python3 scripts/build_agentdojo_dev_subset.py

# 从 HuggingFace 重建 BFCL dev（可选）
python3 scripts/build_bfcl_dev_subset.py

# CI：fake dev 回归
python3 -m pytest tests/eval/public -q -m "not llm"
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-dev --mode agent
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-agentdojo-dev --mode agent

# Nightly：真实 LLM（需 DEEPSEEK_API_KEY）
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-dev-llm --mode agent --planner llm
```

## 简历表述（推荐）

> 接入 Berkeley Function Calling Leaderboard **官方 v3 dev 子集（55 题，HuggingFace 源）**，CI 用 Fake Planner 做 100% 回归；Nightly 用 DeepSeek 多轮工具规划器报告 task **65%** / function_match **94%**（2026-08-31）。并行接入 AgentDojo **官方 workspace dev（13 题）** 与 MultiHop smoke，安全与多跳能力分栏展示。

## 局限（务必如实）

- dev 55 题是官方全集的子采样，**不是完整 BFCL 榜单**。
- BFCL LLM 仍为顺序单工具调用规划器（多轮），未复刻官方 API 批量 parallel 协议。
- AgentDojo dev 为 workspace 子集（8 utility + 5 injection），**不是完整 AgentDojo 榜**。
- MultiHop 仍为 smoke，待接官方 dev 扩展。

## 不要写

> BFCL / AgentDojo 榜单 SOTA / 全面超越官方 baseline（除非跑完整官方协议 + 注明模型与版本）。
