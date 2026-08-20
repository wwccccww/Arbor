# eval/

Arbor 记忆评测。说明见 [docs/evaluation.md](../docs/evaluation.md) 与 [docs/ragas.md](../docs/ragas.md)。

```text
fixtures/suite-v1/              P0 烟雾金标（13 题）
fixtures/suite-ragas-v1/        默认规模集（离线 compat + 对齐后的官方题；含隔离负例）
fixtures/suite-ragas-official/  官方 TestsetGenerator 对齐成功的子集（对照用）
generate_testset.py             重新合成规模集
baselines/                      对比表快照
```

```text
# CI / 体检：无 LLM，四策略检索 + 跨租户泄漏必须为 0
arbor-eval --suite v1 --strategy all
python3 eval/runner.py --suite v1 --strategy all --write-baseline

python3 eval/check_llm_env.py
python3 eval/generate_testset.py
# 官方 RAGAS：先写 compat 金标，再把对齐到 memory_id 的官方题合并进 suite-ragas-v1
# 对不上 ID 的题丢弃；隔离负例始终保留
python3 eval/generate_testset.py --backend ragas --size 100
```

`generation` 模式尚未接 DeepSeek，CLI 以退出码 2 拒绝，避免在 PR 里误跑 RAGAS。

suite-v1 检索基线（夹具嵌入，2026-08-20）：

| strategy | 身份一致 | Recall@5 | 人设泄漏 | 跨租户泄漏 | 关键事件 | 档案层漏检 |
|---|---|---|---|---|---|---|
| `summary_only` | 0.0 | 0.0 | 0 | **0** | 0.0 | 3 |
| `vector_only` | 1.0 | 1.0 | 0 | **0** | 1.0 | 3 |
| `layered` | 1.0 | 1.0 | 0 | **0** | 1.0 | **0** |
| `layered_tree` | 1.0 | 1.0 | 0 | **0** | 1.0 | **0** |

v1 只有约 20 条记忆，`vector_only` 也能碰巧召回身份题；分层是否接上档案要看 `profile_miss_count`。过滤保证四列跨租户泄漏都是 0。完整 JSON：`baselines/suite-v1.json`。规模集 477 条仍用 `generate_testset.py` 维护，不进 PR 必跑。

官方生成器要求文档超过 100 tokens；单条记忆会先扩写（不新增事实）再交给 `TestsetGenerator`。

Cloud Agent：`DEEPSEEK_API_KEY` 必须出现在**当前进程**的环境变量里。对话里的密钥弹窗、以及给已经在跑的机器补 Secret，都不会热注入。请在 [My Secrets](https://cursor.com/dashboard/cloud-agents#my-secrets) 保存名为 `DEEPSEEK_API_KEY` 的 Runtime Secret，再 **新开一轮 Agent**。不要写入 git。无密钥时 `--backend ragas` 以退出码 1 失败。
本机可复制 `.env.example` 为 `.env`。

