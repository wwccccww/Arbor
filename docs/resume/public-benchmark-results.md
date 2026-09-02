# 公开基准结果（简历口径）

> 私有冻结评测证明回归稳定；公开基准证明在第三方任务上仍可复现。  
> **Fake Planner** 与 **真实 LLM** 分轨报告，禁止混报。

## 双栏对比（2026-08-31 · 路线 B）

| 维度 | 私有冻结评测 | 公开基准 |
|---|---|---|
| 任务 / 工具调用 | agent-ablation-v1 完整轨 task 100% | BFCL 官方 dev **200 题** · LLM task **0.915** / function **0.985** |
| Agent 工具链 | agent-v1 smoke 100% | AgentDojo workspace **46 题** · LLM utility **0.225** / attack **0.00** |
| 多跳检索 | suite-v1 Recall@5 100% | MultiHop dev **100 题** · LLM supporting_recall **0.721** / answer_em **0.65** |
| 安全 | agent-security-v1 P0=0 | AgentDojo injection attack_success **0.00**；MultiHop tenant_leak **0.00** |

## 公开基准明细

| 基准 | 套件 | 数据来源 | Planner | Cases | 关键指标 |
|---|---|---|---|---:|---|
| BFCL | `public-bfcl-smoke` | 自建 smoke | fake | 12 | function/argument 1.0 |
| BFCL | `public-bfcl-dev` | **官方 HF v3 冻结子集** | fake | **200** | task 1.0（回归基线） |
| BFCL | `public-bfcl-dev-llm` | **同上官方 dev** | **DeepSeek LLM (bfcl-fc-v6)** | **200** | task **0.915**, function **0.985**, argument **0.915** |
| AgentDojo | `public-agentdojo-smoke` | 自建 smoke | fake | 5 | utility 1.0, attack 0.0 |
| AgentDojo | `public-agentdojo-dev` | **官方 v1.2 workspace** | fake | **46** | utility 1.0, attack 0.0 |
| AgentDojo | `public-agentdojo-dev-llm` | **同上官方 dev** | **DeepSeek LLM** | **46** | utility **0.225**, attack **0.0** |
| MultiHop-RAG | `public-multihop-smoke` | 自建 smoke | fake | 5 | supporting_recall 1.0 |
| MultiHop-RAG | `public-multihop-dev` | **官方 HF 分层抽样** | fake | **100** | supporting_recall 1.0 |
| MultiHop-RAG | `public-multihop-dev-llm` | **同上官方 dev** | **DeepSeek RAG+LLM (v6)** | **100** | recall **0.721**, answer_em **0.65**, tenant_leak **0.0** |
| RAGAS 官方 | `ragas-official-v1` | **TestsetGenerator 对齐 100 条** | **DeepSeek + SF Qwen2.5-14B judge + bge-m3** | **100** | faithfulness **88.0%**, context_recall **72.7%**, answer_correctness **56.6%**, citation **1.0**, leak **0**（2026-09-01） |

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

# Nightly LLM（DeepSeek，dev 子集）
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl-dev-llm --mode agent --planner llm
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-agentdojo-dev-llm --mode agent --planner llm
python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-multihop-dev-llm --mode agent --planner llm

# Nightly RAGAS 官方 100（DeepSeek + ARBOR_JUDGE_API_KEY + bge）
pip install -r eval/requirements-eval.txt
python3 -m arbor.adapters.inbound.cli.eval_cli --suite ragas-official-v1 --mode generation --embed bge --write-baseline
```

## 简历表述（推荐）

> 接入 **BFCL / AgentDojo / MultiHop-RAG / RAGAS official** 四套公开/半公开 dev 冻结子集；CI Fake Planner 回归 + Nightly DeepSeek 分轨：**BFCL task 91.5%**、**AgentDojo utility 22.5% / attack 0%**、**MultiHop answer_em 65% / recall 72.1%**、**RAGAS official faithfulness 88.0% / answer_correctness 56.6%**（2026-09-01，dev 子集非完整榜单；RAGAS judge=SiliconFlow Qwen2.5-14B）。

## 局限（务必如实）

- BFCL 200 / MultiHop 100 / AgentDojo 46 均为**官方全集的子采样**。
- BFCL / AgentDojo LLM 使用 Arbor 多轮规划器，**非**官方 leaderboard 完整协议。
- MultiHop LLM 使用 fixture 嵌入 + layered_tree 检索，**非**生产 embedding 或官方 HotpotQA 协议。

## 不要写

> BFCL / AgentDojo / MultiHop 榜单 SOTA 或全面超越官方 baseline。
