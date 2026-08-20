# ADR 0006：评测是产品能力，金标先于 runner

- 状态：已采纳
- 日期：2026-08-19

## 上下文

测试保证过滤与不变式。若没有冻结的题目和策略对比表，检索改动无法证明「加上树更好」，记忆体检页也没有东西可演示。

## 决策

- 评测以 `eval/fixtures/suite-v1` 为唯一 v1 金标，题目绑定稳定 ID。
- 分 `retrieval` / `generation` 两模式；CI 与面试默认 retrieval。
- 默认策略 `layered_tree` 的跨租户泄漏必须为 0。
- 先入库世界与题目，runner 实现后再填 `eval/baselines`。
- 改简单题刷分必须升 suite 版本。

## 后果

- 体检页演示不依赖现场调用 DeepSeek。
- 换嵌入模型只重建向量，不改题。
