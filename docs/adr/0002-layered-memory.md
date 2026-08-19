# ADR 0002：分层记忆，而不是单一 RAG 框架

- 状态：已采纳
- 日期：2026-08-19

## 上下文

人设身份需要稳定、可编辑、可审计。纯向量检索会把旧设定与相似闲聊一并召回。GraphRAG / RAPTOR 面向大语料全局问题，不是「这个人上周答应了什么」。

## 决策

- 身份走结构化 Profile。
- 近期走 Thread summary。
- 细节走 pgvector，强制 `tenant_id + persona_id`。
- 关键经历走 EventNode 树，作为路由与展示，不引入 GraphRAG 流水线。
- 向量与业务数据同库（PostgreSQL + pgvector），降低双库过滤遗漏。

## 后果

- 检索实现是应用层策略 + `VectorIndex` 端口，而不是领域概念「RAG」。
- 因果多跳不足时，只增加 `EventEdge` 种类与 1～2 跳查询，再评估是否需要图数据库。
- 评测必须包含隔离与身份一致，而不仅是 Recall。
