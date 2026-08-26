# ADR 0008：领域事件 v1 延后

## 状态

已接受（2026-08）

## 背景

[domain-model.md](../domain-model.md) 列出了 `PersonaProfileUpdated`、`InboxItemConfirmed`、`MemorySuperseded` 等跨上下文协作事件。六边形架构图也写了「应用层发布领域事件」。

## 决策

**v1 不实现领域事件总线。** 跨上下文协作继续由应用层用例同步编排（直接调仓储 / `VectorIndex` / Inbox）。

文档中的事件表保留为 **设计预留**，不代表当前运行时行为。

## 理由

- v1 用例链路短，同步编排足够，且更易单测。
- 事件订阅、顺序、幂等与失败重放会增加组合根与测试复杂度。
- 记忆隔离与授权已在应用层断言，不依赖事件驱动。

## 后果

- 改 `ConfirmInboxItem` 或 `DeleteMemory` 时，向量失效、审计写入仍在同一用例内完成。
- 若未来引入事件，建议从 `MemorySuperseded` → 向量删除 单链路切入，载荷仅含 ID。
- `domain-model.md` 事件表已标注「预留 / 未实现」。
