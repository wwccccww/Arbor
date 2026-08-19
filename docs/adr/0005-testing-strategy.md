# ADR 0005：测试与评测分离，隔离测试阻断合并

- 状态：已采纳
- 日期：2026-08-19

## 上下文

记忆产品容易只做「开一场聊天看看」。那样测不到租户过滤、权限进 prompt、supersede。评测集又偏慢、偏依赖模型，不适合当唯一 CI。

## 决策

- 金字塔按六边形分层：领域/应用用 Fake 端口；Postgres 做契约测；HTTP 对 OpenAPI；import 方向做架构测试。
- 跨租户 / 跨人设 / 无权限记忆进上下文，作为 P0 pytest，失败即不可合并。
- 评测金标（Recall、身份一致、策略对比）与测试分家；PR 只强制无 LLM 的夹具隔离与 Recall。
- 默认 CI 不调用 DeepSeek。

## 后果

- 实现必须先提供端口 Fake 与 `Clock`/`IdGenerator`。
- 不能用 mock 领域对象绕过不变式。
- 详细清单见 `docs/testing.md`。
