# eval/

Arbor 记忆评测。说明见 [docs/evaluation.md](../docs/evaluation.md) 与 [docs/ragas.md](../docs/ragas.md)。

```text
fixtures/suite-v1/         P0 烟雾金标（13 题）
fixtures/suite-ragas-v1/   规模集（RAGAS 分布，当前 377 条）
generate_testset.py        重新合成规模集
baselines/                 对比表快照
```

```text
python3 eval/check_llm_env.py
python3 eval/generate_testset.py
# 官方 RAGAS（进程里要有 DEEPSEEK_API_KEY，并已 pip install -r eval/requirements-eval.txt）
python3 eval/generate_testset.py --backend ragas --size 10
```

Cloud Agent：在环境 Secrets 填写 `DEEPSEEK_API_KEY` 后必须 **新开一轮 Agent**，Key 才会进入进程。不要写入 git。
本机可复制 `.env.example` 为 `.env`。

