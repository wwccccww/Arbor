# 公开基准结果（简历口径）

> 私有冻结评测证明回归稳定；公开基准证明在第三方任务上仍可复现。  
> **Fake Planner** 与 **真实 LLM** 分轨报告，禁止混报。

## 双栏对比（2026-08-31）

| 维度 | 私有冻结评测 | 公开基准 |
|---|---|---|
| 任务 / 工具调用 | agent-ablation-v1 完整轨 task 100% | BFCL 官方 dev 55 题 · LLM function_match **0.86** |
| 安全 | agent-security-v1 P0=0 | AgentDojo smoke attack_success **0.00** |
| 多跳检索 | suite-v1 Recall@5 100% | MultiHop smoke supporting_recall **1.00**（5 题 smoke） |

## 公开基准明细

| 基准 | 套件 | 数据来源 | Planner | Cases | 关键指标 |
|---|---|---|---|---:|---|
| BFCL | `public-bfcl-smoke` | 自建 smoke | fake | 12 | function/argument 1.0 |
| BFCL | `public-bfcl-dev` | **官方 HF v3 冻结子集** | fake | 55 | task 1.0（回归基线） |
| BFCL | `public-bfcl-dev-llm` | **同上官方 dev** | **DeepSeek LLM** | 55 | task **0.55**, function **0.86**, argument **0.60** |
| AgentDojo | `public-agentdojo-smoke` | 自建 smoke | fake | 5 | utility 1.0, attack 0.0 |
| MultiHop-RAG | `public-multihop-smoke` | 自建 smoke | fake | 5 | supporting_recall 1.0 |

### BFCL 官方 dev 组成

| 类别 | 题数 | 说明 |
|---|---:|---|
| simple | 20 | `BFCL_v3_simple.json` 前 20 题 + 官方 ground truth |
| multiple | 15 | 多函数选择 |
| parallel | 10 | 并行多调用（当前 Agent 单轮 LLM 规划器限制，LLM 分较低） |
| irrelevance | 10 | 不应调用工具 |

## 复现命令

```bash
# 校验 smoke + 官方 dev 文件
python3 scripts/fetch_public_benchmarks.py --benchmark bfcl --only smoke

# 从 HuggingFace 重建 dev（可选）
python3 scripts/build_bfcl_dev_subset.py

# CI：fake dev 回归
python3 -m pytest tests/eval/public/test_bfcl_dev.py -q
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-dev --mode agent

# Nightly：真实 LLM（需 DEEPSEEK_API_KEY）
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-dev-llm --mode agent --planner llm
```

## 简历表述（推荐）

> 接入 Berkeley Function Calling Leaderboard **官方 v3 dev 子集（55 题，HuggingFace 源）**，CI 用 Fake Planner 做 100% 回归；Nightly 用 DeepSeek 报告 function_match **86%** / argument_match **60%**（2026-08-31）。并行 AgentDojo / MultiHop smoke 用于安全与多跳能力分栏。

## 局限（务必如实）

- dev 55 题是官方全集的子采样，**不是完整 BFCL 榜单**。
- LLM 评测为 **顺序单工具调用** 规划器，parallel/multiple 类题目分低于 simple/irrelevance。
- AgentDojo / MultiHop 仍为 smoke，待接官方 dev 扩展。

## 不要写

> BFCL 榜单 SOTA / 全面超越官方 baseline（除非跑完整官方协议 + 注明模型与版本）。
