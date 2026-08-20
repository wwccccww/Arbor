# eval/

Arbor 记忆评测。说明见 [docs/evaluation.md](../docs/evaluation.md) 与 [docs/ragas.md](../docs/ragas.md)。

```text
fixtures/suite-v1/              P0 烟雾金标（13 题）
fixtures/suite-ragas-v1/        规模集（RAGAS 分布，当前 377 条，离线合成）
fixtures/suite-ragas-official/  官方 TestsetGenerator 产物（DeepSeek，不覆盖 377 条）
generate_testset.py             重新合成规模集
baselines/                      对比表快照
```

```text
python3 eval/check_llm_env.py
python3 eval/generate_testset.py
# 官方 RAGAS（进程里要有 DEEPSEEK_API_KEY，并已 pip install -r eval/requirements-eval.txt）
# 产物写到 fixtures/suite-ragas-official/，不覆盖上面的 377 条
python3 eval/generate_testset.py --backend ragas --size 10
```

官方生成器要求文档超过 100 tokens；单条记忆会先扩写（不新增事实）再交给 `TestsetGenerator`。

Cloud Agent：`DEEPSEEK_API_KEY` 必须出现在**当前进程**的环境变量里。对话里的密钥弹窗、以及给已经在跑的机器补 Secret，都不会热注入。请在 [My Secrets](https://cursor.com/dashboard/cloud-agents#my-secrets) 保存名为 `DEEPSEEK_API_KEY` 的 Runtime Secret，再 **新开一轮 Agent**。不要写入 git。无密钥时 `--backend ragas` 以退出码 1 失败。
本机可复制 `.env.example` 为 `.env`。

