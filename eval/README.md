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
python3 eval/check_llm_env.py
python3 eval/generate_testset.py
# 官方 RAGAS：先写 compat 金标，再把对齐到 memory_id 的官方题合并进 suite-ragas-v1
# 对不上 ID 的题丢弃；隔离负例始终保留
python3 eval/generate_testset.py --backend ragas --size 30
```

官方生成器要求文档超过 100 tokens；单条记忆会先扩写（不新增事实）再交给 `TestsetGenerator`。

Cloud Agent：`DEEPSEEK_API_KEY` 必须出现在**当前进程**的环境变量里。对话里的密钥弹窗、以及给已经在跑的机器补 Secret，都不会热注入。请在 [My Secrets](https://cursor.com/dashboard/cloud-agents#my-secrets) 保存名为 `DEEPSEEK_API_KEY` 的 Runtime Secret，再 **新开一轮 Agent**。不要写入 git。无密钥时 `--backend ragas` 以退出码 1 失败。
本机可复制 `.env.example` 为 `.env`。

