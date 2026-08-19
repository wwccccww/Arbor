# eval/

Arbor 记忆评测套件。说明见 [docs/evaluation.md](../docs/evaluation.md)。

当前只有 **suite-v1 金标数据**，没有 runner（等生成代码时再写，且必须走应用端口）。

```text
fixtures/suite-v1/     冻结的记忆世界与题目
baselines/             对比表快照（有结果后再填）
```

跑法（实现后）：

```text
# 检索层，CI / 体检默认
arbor-eval --suite v1 --mode retrieval --strategy layered_tree

# 四策略出表
arbor-eval --suite v1 --mode retrieval --strategy all

# 生成层，夜间
arbor-eval --suite v1 --mode generation --strategy layered_tree
```
