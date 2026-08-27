# Nightly / Weekly CI 与仓库 Secrets

PR 门禁 **不** 依赖下列密钥；仅 nightly / weekly 与本地真模型评测使用。

## 仓库 Secrets（GitHub → Settings → Secrets → Actions）

| Secret | 用途 | 必填 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | generation 评测、`pytest -m llm` | nightly generation 轨 |
| `ARBOR_JUDGE_API_KEY` | RAGAS faithfulness（**不能与** `DEEPSEEK_API_KEY` 相同） | RAGAS 软门槛 |
| `EMBEDDING_API_KEY` 或 `SILICONFLOW_API_KEY` | bge-m3 嵌入 | nightly bge 轨 |

未配置时对应 job 步骤会跳过，不会失败。

## Workflows

| 文件 | 触发 | 内容 |
|------|------|------|
| `.github/workflows/ci.yml` | PR / push | 夹具嵌入检索、unit、web、e2e |
| `.github/workflows/nightly.yml` | 每日 03:00 UTC、`workflow_dispatch` | generation + RAGAS + bge ragas-v1 |
| `.github/workflows/weekly-eval.yml` | 每周一 04:00 UTC、`workflow_dispatch` | main 上 ragas-v1 夹具回归 |

## bge 基线

- 夹具表：`eval/baselines/suite-ragas-v1.json`（PR 门禁）
- 真嵌入表：`eval/baselines/suite-ragas-v1-bge.json`（仅 nightly 写入，**不与夹具混读**）

本地更新 bge 基线：

```bash
export EMBEDDING_API_KEY=...
python3 -m arbor.adapters.inbound.cli.eval_cli \
  --suite ragas-v1 --strategy all --backend postgres --embed bge --write-baseline
# 输出写入 eval/baselines/suite-ragas-v1-bge.json（nightly 脚本）
```

## 本地 generation + RAGAS

```bash
export DEEPSEEK_API_KEY=...
export ARBOR_JUDGE_API_KEY=...   # 独立评委密钥
python3 -m arbor.adapters.inbound.cli.eval_cli --suite v1 --mode generation --strategy layered_tree --backend postgres
```

见 [evaluation.md](evaluation.md)、[ragas.md](ragas.md)。
