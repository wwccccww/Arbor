# ADR 0001：六边形架构 + DDD 分层

- 状态：已采纳
- 日期：2026-08-19

## 上下文

Arbor 同时对接 HTTP、DeepSeek、bge、pgvector、对象存储与评测脚本。若业务写在 FastAPI 路由或 LangChain 链里，换模型或写单测都会拖动整棵树。记忆隔离是安全规则，必须能在无网络下测。

## 决策

采用六边形架构：

- 领域层表达 Persona / Memory / Event 不变式。
- 应用层编排用例。
- 端口定义仓储、LLM、嵌入、存储。
- 适配器实现端口。
- 限界上下文划分见 `docs/domain-model.md`。

## 后果

- 新增供应商 = 新增出站适配器，不改聚合。
- 目录与 import 规则需要 lint 维持。
- 前期比「一个 service.py」多一些样板，换来可测的隔离规则。
