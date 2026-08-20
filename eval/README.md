# eval/

Arbor 记忆评测。说明见 [docs/evaluation.md](../docs/evaluation.md) 与 [docs/ragas.md](../docs/ragas.md)。

```text
fixtures/suite-v1/         P0 烟雾金标（13 题）
fixtures/suite-ragas-v1/   规模集（RAGAS 分布，当前 377 条）
generate_testset.py        重新合成规模集
baselines/                 对比表快照
```

```text
python3 eval/generate_testset.py
# 有 Key 且 ragas 可导入时
DEEPSEEK_API_KEY=... python3 eval/generate_testset.py --backend ragas --size 50

# 实现 runner 之后
arbor-eval --suite v1 --mode retrieval --strategy layered_tree
arbor-eval --suite ragas-v1 --mode retrieval --strategy all
arbor-eval --suite ragas-v1 --mode generation --strategy layered_tree
```
