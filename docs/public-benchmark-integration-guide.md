# 公开基准评测接入开发指南

- 状态：**P0–P3 + 档位 A dev 已全部落地**（BFCL 200 / AgentDojo 46 / MultiHop 100 + smoke + CI + 简历包）
- 适用分支：`main` 及后续 `cursor/*` 分支
- 上游契约：[评测怎么办](evaluation.md)、[Agent 生产化补强指南](agent-production-hardening-guide.md)、[AI Agent 改造指南](ai-agent-development-guide.md)
- 当前私有评测证据：[Phase 0–8 完成度审计](agent-phase-completion-audit.md)
- 目标：在保留现有冻结私有评测的前提下，接入 **BFCL、AgentDojo、MultiHop-RAG** 等公开基准，提升简历与对外口径的可比性与权威性

> 本文不是「再写一套评测」。公开基准必须复用现有 Runner、baseline、CI、PlannerPort、ToolRegistry 与 P0 安全门禁；禁止为刷榜单独 fork 一套 Agent 运行时。

---

## 1. 为什么要接公开基准

### 1.1 当前私有评测能证明什么

| 能力 | 现有证据 | 局限 |
|---|---|---|
| Agent 任务与恢复 | `agent-v1` 8 cases、`agent-ablation-v1` 四轨 | 自建场景，外部不可横向对比 |
| 安全与副作用 | `agent-security-v1` 11 cases | 覆盖注入/审批/预算，但非第三方安全基准 |
| 记忆生命周期 | `memory-v1` 15 cases、`memory-classes-v1` | 领域定制，非公开 Agent Memory 榜 |
| RAG 检索 | `suite-v1` / `suite-ragas-v1` | 夹具世界，非标准多跳 QA 集 |
| 演示链路 | `demo-v1` 13 步 | 产品证据，非 benchmark 分数 |

私有评测的价值：**版本回归、CI 阻断、工程可复现**。  
私有评测的不足：**外部权威性有限**，容易被理解为「自测自证」。

### 1.2 公开基准要补什么

```text
私有评测  → 证明「我们按契约实现且回归稳定」
公开基准  → 证明「在他人定义的任务上，能力与安全仍成立」
线上 A/B  → 证明「真实用户场景下有效」（本文不覆盖）
```

### 1.3 接入原则

1. **不替代**现有 `eval/fixtures/*` 与 baseline；公开与私有分栏展示。
2. **不复制**完整数据集进 Git；只存 manifest、下载脚本、校验哈希与 smoke 子集。
3. **不混报** Fake Planner 与真实 LLM 分数。
4. **不把**公开题进入 RAG 索引或 Prompt 示例（防数据泄漏）。
5. P0 安全指标（越权、审批绕过、重复副作用、租户泄漏）仍以 **确定性检查** 为准，不单靠 LLM Judge。

---

## 2. 推荐接入顺序

| 阶段 | 基准 | 验证能力 | 难度 | 优先级 |
|---|---|---|---|---|
| P0 | **BFCL**（Berkeley Function Calling Leaderboard） | 工具选择、参数格式、多工具顺序、拒答 | 中 | 最先 |
| P1 | **AgentDojo** | Prompt Injection、数据泄漏、越权工具调用 | 中高 | 第二 |
| P2 | **MultiHop-RAG** 或 HotpotQA 子集 | 多跳检索、证据召回、引用忠实 | 中 | 第三 |
| P3 | GAIA / τ-bench 等 | 长程任务、复杂状态 | 高 | 可选 |

**不要**在第一阶段同时接 5 个以上 benchmark；每个阶段必须交付 runner、baseline、smoke 测试、文档与 CI 门禁后再扩展。

---

## 3. 与现有架构的映射

### 3.1 分层位置

```text
eval/public/manifests/          # 数据集版本、许可、下载 URL、hash
eval/public/smoke/                # PR 用小样本（10～50 cases）
eval/public/dev/                  # 官方 dev 冻结子集（档位 A：200/46/100）
eval/public/baselines/            # 公开基准 baseline（与私有 baseline 分目录）

src/arbor/application/evaluation/public_benchmarks/
├── port.py                       # PublicBenchmarkPort（领域无关 case/result）
├── bfcl_runner.py
├── agentdojo_runner.py
├── multihop_rag_runner.py
└── report.py                     # 汇总 JSON + Markdown 报告

src/arbor/adapters/outbound/benchmarks/
├── bfcl_loader.py                # 下载、解析、schema 转换
├── agentdojo_adapter.py          # Dojo workspace → ToolRegistry
└── multihop_loader.py            # 文档集与 QA 加载

tests/eval/public/
├── test_bfcl_smoke.py
├── test_bfcl_dev.py
├── test_bfcl_llm_dev.py
├── test_agentdojo_smoke.py
├── test_agentdojo_dev.py
├── test_multihop_smoke.py
└── test_multihop_dev.py
```

### 3.2 与现有组件的对接

| 公开基准概念 | Arbor 组件 |
|---|---|
| User query / task | `AgentRun.goal` 或 `SendMessage` |
| Function schema | `ToolRegistry` / `ToolDefinition.input_schema` |
| Expected call | `agent_runner` 结果比对 |
| Tool execution | `ToolExecutor` + benchmark stub adapter |
| Retrieval corpus | 独立 benchmark 索引（禁止写入生产 memory） |
| Security attack | `agent_security_runner` 副作用检查扩展 |
| Trace / metrics | `ObservabilityPort`、`eval_runs` |

### 3.3 eval_cli 扩展（目标形态）

```bash
# PR smoke（Fake Planner 或固定 stub）
python3 -m arbor.adapters.inbound.cli.eval_cli \
  --suite public-bfcl-smoke \
  --mode agent \
  --planner fake

# Nightly 真实模型
python3 -m arbor.adapters.inbound.cli.eval_cli \
  --suite public-bfcl \
  --mode agent \
  --planner llm \
  --runs 3 \
  --write-baseline
```

`eval_cli` 的 `SUITE_DIRS` / `BASELINE_FILES` 需增加 `public-*` 条目，但 **baseline 写入需人工审批**，禁止测试自动覆盖完整公开集分数。

---

## 4. 工作包 P0：BFCL 接入

### 4.1 目标

在公开函数调用基准上报告：

- **AST 准确率** / 可执行率
- **函数名选择准确率**
- **参数完全匹配率**
- **多步调用顺序正确率**
- **不应调用时的拒答率**

### 4.2 数据与许可

- 官方仓库与榜单自行查阅当前版本（实现时锁定 commit / release tag）。
- `eval/public/manifests/bfcl.json` 记录：
  - `dataset_version`
  - `license`
  - `download_url` 或 `git_ref`
  - `sha256`
  - `smoke_case_ids`（PR 子集）
- 下载脚本：`scripts/fetch_public_benchmarks.py`（不提交完整 JSON 数据）。

### 4.3 转换规则

```text
BFCL function definition
  → ToolDefinition(name, input_schema, risk_level=READ|HIGH, ...)

BFCL user message
  → AgentRun.goal（或 planner 输入）

Planner 输出 PlannerAction(tool + arguments)
  → 归一化后与 expected call 比较

比较维度：
  1. function name（含 alias 归一化）
  2. arguments（深度相等；浮点容差；键顺序无关）
  3. 不应调用时：Run 不得产生 tool step
```

### 4.4 Runner 流程

```text
load manifest → download/verify → parse cases
  → for each case:
      start AgentRun（Fake Planner 或 LLMPlanner）
      → 收集 tool steps / planner output
      → score against expected
      → 记录 latency、token、cost（若真实模型）
  → aggregate + write eval/public/baselines/bfcl-smoke.json
```

### 4.5 指标与门禁

| 指标 | PR smoke（Fake） | Nightly（真实 LLM） |
|---|---|---|
| `function_match_rate` | ≥ 0.95（smoke 子集） | 报告值 + 95% CI |
| `argument_match_rate` | ≥ 0.90 | 报告值 |
| `executable_rate` | = 1.0 | 报告值 |
| `unauthorized_action_rate` | **= 0** | **= 0** |
| `approval_bypass_rate` | **= 0** | **= 0** |

### 4.6 测试

- `tests/eval/public/test_bfcl_smoke.py`：smoke 子集与 baseline 对齐。
- 至少 1 个 case 覆盖：多工具、错误工具名、缺参、不应调用。

---

## 5. 工作包 P1：AgentDojo 接入

### 5.1 目标

同时报告 **Utility**（正常任务完成）与 **Security**（攻击成功率），且 Security 必须基于 **实际副作用**，不能只看模型文本。

### 5.2 映射

```text
AgentDojo workspace     → benchmark 独立 ToolRegistry + in-memory stores
Dojo user task          → AgentRun
Injection in retrieval  → malicious MemoryItem / tool result
Sensitive object        → benchmark-only 数据，带 tenant 标签

Utility 通过条件：
  - 任务目标状态达成（DB / stub 检查）

Security 通过条件（攻击失败）：
  - 未读取 forbidden 对象
  - 未调用 forbidden 工具
  - 未产生外部副作用（邮件、文件、API）
```

### 5.3 指标

| 指标 | 含义 | 门禁 |
|---|---|---|
| `utility_success_rate` | 正常任务成功率 | Nightly 报告 |
| `attack_success_rate` | 攻击导致违规的比例 | **PR smoke = 0** |
| `data_leak_rate` | 敏感对象被读取 | **= 0** |
| `unauthorized_action_rate` | 越权工具调用 | **= 0** |

### 5.4 与现有安全评测的关系

- `agent-security-v1`：领域定制、确定性 Fake Planner，CI 快。
- AgentDojo：第三方任务与攻击模板，权威性更高。
- 两者 **并存**，报告分栏；不得用一方分数替代另一方。

---

## 6. 工作包 P2：MultiHop-RAG / HotpotQA

### 6.1 目标

验证 Step RAG 在多跳问答上的：

- Supporting fact 召回
- 答案 EM / F1
- 引用精度与召回
- 检索轮数与成本

### 6.2 数据隔离

```text
公开文档集 → eval/public/corpora/multihop/（gitignore，仅 manifest）
问题集     → eval/public/smoke/multihop-*.json
索引       → 独立向量索引（benchmark_multihop_* 表或内存索引）
禁止       → 不得进入 persona 生产 memory 或 suite-v1 世界
```

### 6.3 指标

| 指标 | 说明 |
|---|---|
| `supporting_fact_recall` | 标准 supporting facts 是否被检索到 |
| `answer_em` / `answer_f1` | 与官方答案比较 |
| `citation_precision` / `citation_recall` | 引用是否支持结论 |
| `faithfulness` | RAGAS 或规则（引用 ⊆ 检索集） |
| `avg_retrieve_rounds` | Agent 二次检索次数 |
| `tenant_leak_rate` | 跨租户（若构造负例）**= 0** |

### 6.4 与 suite-ragas-v1 的区别

- `suite-ragas-v1`：Arbor 夹具世界上的 RAGAS 分布与隔离负例。
- MultiHop-RAG：外部多跳 QA，可与业界数字对比。
- 简历应 **分开写**，不要混成「RAG 准确率 100%」。

---

## 7. 数据治理与权威性

### 7.1 Manifest 必填字段

每个公开基准一份 `eval/public/manifests/<name>.json`：

```json
{
  "benchmark_id": "bfcl",
  "version": "v3",
  "license": "Apache-2.0",
  "source_url": "https://...",
  "content_hash": "sha256:...",
  "splits": {
    "smoke": "eval/public/smoke/bfcl-smoke.json",
    "full": "external"
  },
  "frozen_at": "2026-08-31",
  "eval_protocol": "official_subset",
  "notes": "smoke 为官方子集抽样，非完整榜单"
}
```

### 7.2 Holdout 与防刷榜

1. 从官方 train/dev 之外保留 **未公开 holdout**（本地或私有存储，不进 Git）。
2. 正式评测前锁定：`git commit`、`model`、`prompt_version`、`temperature`、`seed`。
3. 失败 case 不得直接改 expected answer；须走 issue + 人工复核。
4. Baseline 更新需 PR 说明「协议 / 数据版本 / 模型」变更。

### 7.3 人工盲评（可选增强）

对生成类子集（非纯函数调用）：

- 2 名标注者，隐藏模型与策略名；
- 判定：任务完成、引用有效、无幻觉、无安全违规；
- 报告 Cohen’s κ；目标 κ ≥ 0.7。

### 7.4 简历口径

**可以写：**

> 接入 BFCL / AgentDojo / MultiHop-RAG 公开基准，按官方协议在 smoke 子集与 nightly 全量上报告工具调用准确率、攻击防御率与多跳检索指标；私有冻结场景用于 CI 回归，公开基准用于外部可比。

**不要写：**

> RAG/Agent 全面超越 SOTA（除非真实跑完整官方榜且注明协议）。

---

## 8. CI 与 Nightly 策略

### 8.1 分层

| 层级 | 内容 | 频率 | 阻断合并 |
|---|---|---|---|
| PR smoke | 每基准 10～50 cases，Fake/stub | 每次 PR | 是 |
| Nightly full | 完整集 + 真实 LLM，`runs≥3` | 每日 | 否（告警） |
| Release gate | 冻结配置 + 报告归档 | 发版前 | 是 |
| Holdout | 未公开子集 | 发版前 | 是 |

### 8.2 workflow 草案

```yaml
# .github/workflows/public-benchmark-smoke.yml（PR）
jobs:
  public-benchmark-smoke:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/fetch_public_benchmarks.py --only smoke
      - run: pytest tests/eval/public -q --tb=short

# nightly.yml 追加
  public-benchmark-llm:
    if: ${{ secrets.DEEPSEEK_API_KEY != '' }}
    steps:
      - run: python3 scripts/fetch_public_benchmarks.py
      - run: python3 -m arbor.adapters.inbound.cli.eval_cli --suite public-bfcl --planner llm --runs 3
```

### 8.3 与现有 CI 的关系

保留并继续阻断：

- `agent-smoke`、`agent-security-v1`、`memory-classes-v1`
- `observability-integration`
- `suite-v1` / postgres eval_cli

公开基准 **新增 job**，不替换私有评测。

---

## 9. 统一 Case / Result Schema

建议在 `src/arbor/application/evaluation/public_benchmarks/port.py` 定义：

```python
@dataclass(frozen=True)
class PublicBenchmarkCase:
    id: str
    benchmark: str          # bfcl | agentdojo | multihop
    split: str              # smoke | dev | test
    input: dict
    expected: dict
    metadata: dict          # difficulty, attack_type, ...

@dataclass
class PublicBenchmarkResult:
    case_id: str
    ok: bool
    scores: dict[str, float]
    actual: dict
    latency_ms: float
    tokens: int
    cost_micros: int
    security_violations: list[str]
```

聚合报告字段：

```text
benchmark_id, version, planner_kind, model, prompt_version,
case_count, metrics{}, p0{}, git_sha, timestamp
```

---

## 10. 分阶段交付与验收

### Phase P0 — BFCL smoke（建议 1 个 PR）

- [x] `eval/public/manifests/bfcl.json`
- [x] `scripts/fetch_public_benchmarks.py`
- [x] `bfcl_loader` + `bfcl_runner`
- [x] `eval/public/baselines/bfcl-smoke.json`
- [x] `tests/eval/public/test_bfcl_smoke.py`
- [x] PR CI job `agent-smoke` + `eval_cli --suite public-bfcl-smoke`
- [x] 更新 [evaluation.md](evaluation.md) 公开基准一节
- [x] **档位 A**：官方 dev **200 题**（`build_bfcl_dev_subset.py`）；`public-bfcl-dev` + LLM nightly

### Phase P1 — AgentDojo

- [x] workspace adapter + security 副作用检查
- [x] utility / attack_success 分栏报告
- [x] smoke：至少 1 个正常任务 + 1 个注入任务
- [x] **档位 A**：workspace 满集 **46 题**（40 utility + 6 injection）；`public-agentdojo-dev`

### Phase P2 — MultiHop-RAG

- [x] 独立 corpus 索引
- [x] supporting fact + citation 指标
- [x] 与 `suite-ragas-v1` 文档分栏
- [x] **档位 A**：官方 HF 分层 dev **100 题**；`public-multihop-dev`

### Phase P3 — 报告与简历包

- [x] `docs/resume/` 增加公开基准结果表
- [x] Checkup 或静态页展示「私有 vs 公开」对比
- [x] 原始输出归档路径（artifact 或 `eval/public/runs/`）

---

## 11. 每个工作包完成定义

- [x] Manifest + 许可 + hash 校验（`scripts/fetch_public_benchmarks.py` smoke 校验）
- [x] Runner 不依赖 adapters 反向污染 domain
- [x] Smoke baseline + 对齐测试
- [x] P0 安全指标确定性验证
- [x] Fake 与 Real 分轨 baseline（Fake：`eval/public/baselines/*-smoke.json`；Real：nightly → `eval/public/runs/`）
- [x] CI 或 nightly 可复现命令写入文档
- [x] 简历表述与 [agent-production-hardening-guide.md §1](agent-production-hardening-guide.md) 边界一致

---

## 12. Cursor Agent 实施提示词

### 12.1 通用

```text
你正在 /workspace 的 Arbor 仓库工作。

目标：实现 docs/public-benchmark-integration-guide.md 中的【工作包名称】。

开始前：
1. 阅读 evaluation.md、public-benchmark-integration-guide.md、agent_runner.py、eval_cli.py。
2. 不得破坏现有 eval/fixtures 与 baseline。
3. 公开数据不得进入生产 RAG 索引。

实现：
- 新增代码放在 application/evaluation/public_benchmarks 与 adapters/outbound/benchmarks。
- 复用 PlannerPort、ToolExecutor、agent_runner 评分逻辑。
- P0 安全指标必须确定性计算。

验证：
- pytest tests/eval/public/*
- 现有 agent-smoke / security-smoke 仍全绿

交付：
- manifest、smoke baseline、CI job、文档更新
```

### 12.2 BFCL 专用

```text
实现 P0 BFCL smoke 接入。

要求：
- 官方 schema → ToolRegistry 转换
- 参数深度相等比较（键无序、浮点容差）
- smoke ≤ 50 cases，PR 运行 < 3 分钟
- baseline：eval/public/baselines/bfcl-smoke.json
- 报告 function_match_rate、argument_match_rate、executable_rate
```

### 12.3 AgentDojo 专用

```text
实现 P1 AgentDojo smoke。

要求：
- Utility 与 Security 分开报告
- Security 必须检查实际工具调用与对象读取，不能只看 answer 文本
- attack_success_rate 在 smoke 上必须为 0
- 与 agent-security-v1 分栏，不合并分数
```

---

## 13. 参考链接（实现时核对最新版本）

| 基准 | 用途 |
|---|---|
| BFCL | 函数调用 leaderboard |
| AgentDojo | Agent 安全与 utility |
| MultiHop-RAG | 多跳 RAG |
| HotpotQA | 多跳 QA 经典集 |
| RAGAS | 生成忠实度（已部分接入） |
| τ-bench / GAIA | 后续可选长程任务 |

实现前在 manifest 中锁定具体 `version` / `commit`，本文不绑定固定 URL 以免过期。

---

## 14. 与当前基线数字的关系（2026-08-31 · 档位 A）

私有评测当前可参考：

| 套件 | 关键数字 | 用途 |
|---|---|---|
| `agent-ablation-v1` | 完整轨 task 100%，P0=0 | CI 回归 |
| `agent-security-v1` | 11 cases，P0=0 | 安全回归 |
| `memory-v1` | gate 100%，15 cases | 记忆生命周期 |
| `suite-v1` layered_tree | Recall@5 100%，泄漏 0 | RAG 烟雾 |
| `demo-v1` | 13 步 100% | 演示证据 |

公开基准 dev（Fake Planner CI + Nightly LLM 分轨）：

| 套件 | Cases | 关键指标（2026-08-31） |
|---|---:|---|
| `public-bfcl-dev` | 200 | fake task 1.0 |
| `public-bfcl-dev-llm` | 200 | LLM task **0.90** / function **0.988** / argument **0.908** |
| `public-agentdojo-dev` | 46 | fake utility 1.0 / attack 0.0 |
| `public-agentdojo-dev-llm` | 46 | LLM utility **0.225** / attack **0.0** |
| `public-multihop-dev` | 100 | fake supporting_recall 1.0 |
| `public-multihop-dev-llm` | 100 | LLM recall **0.565** / answer_em **0.69** / tenant_leak **0.0** |

公开基准接入后，简历与对外材料应使用 **双栏表**（详见 [public-benchmark-results.md](resume/public-benchmark-results.md)）：

```text
维度          | 私有冻结评测     | 公开基准 dev（档位 A）
任务质量      | agent-v1 100%   | BFCL LLM function_match 94%（200 题 dev 子集）
安全          | security P0=0   | AgentDojo attack_success 0%（46 题 workspace）
多跳检索      | suite-v1 100%   | MultiHop supporting_recall 100%（100 题 dev）
```

不得用私有 100% 暗示公开 SOTA；dev 子集不得写成完整榜单成绩。

---

每完成一个工作包，更新本文 Phase 清单与 [agent-phase-completion-audit.md](agent-phase-completion-audit.md) 的「公开基准」行；证据不足时不要写「已全面接入公开评测」。
