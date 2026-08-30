# 0010 · 持久化 Agent Runtime

- 状态：已采纳（Phase 1 落地）
- 日期：2026-08-30

## 决策

引入 `AgentRun` / `AgentStep` 聚合与 Postgres 持久化，由 worker 或同步队列按步推进；`AdvanceAgentRun` 每次只提交一个步骤；终态不可回退为 running。

## 后果

- 对话 `SendMessage` 保持兼容，Agent 走独立 HTTP 路径。
- 并发推进使用乐观版本 `agent_runs.version`。
