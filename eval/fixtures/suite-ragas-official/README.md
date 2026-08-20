# suite-ragas-official

官方 `ragas.testset.TestsetGenerator`（ragas 0.2.15）产物。

- LLM：DeepSeek Chat（`https://api.deepseek.com`）
- Embedding：`FakeEmbeddings(size=384)`（DeepSeek 无 embedding 接口；只用于构图，题目仍由 Chat 生成）
- 本目录 **不是** 默认规模集。377 条离线合成样本在 `../suite-ragas-v1/`。
- 隔离 / 租户泄漏负例仍只存在于 `suite-ragas-v1`（官方生成器不会发明 Arbor 的 refuse 切片）。
- 每条样本都绑定了 `expected_memory_ids`；`reference_contexts` 已收成对应记忆原文，不含扩写包装。

复现：

```text
pip install -r eval/requirements-eval.txt
python3 eval/check_llm_env.py
python3 eval/generate_testset.py --backend ragas --size 50
```

简历上不要把 377 条写成「官方 RAGAS 自动出题」。那一批是 `ragas_compat`。本目录才是官方生成器跑出来的。
