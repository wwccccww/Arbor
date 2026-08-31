# 0011 · Agent 工具副作用与上下文可信边界

- 状态：已采纳（Phase 2–3 落地）
- 日期：2026-08-30

## 决策

1. **工具副作用**：所有写操作经 `ToolExecutor`，绑定 `agent_run_id` / `agent_step_id` 与幂等键；超时按 `retry_policy` 重试，不重复外部副作用。
2. **审批**：高风险工具先进入 `WAITING_APPROVAL`；未批准、拒绝或过期不得执行适配器。
3. **上下文可信**：RAG 候选经 `ContextCompiler` / `compile_context_items` 编译；外部文档默认 `trust_level=untrusted`，检测注入模式仅影响风险与观测，不静默删业务文本。
4. **证据引用**：Planner / 回答只能引用 manifest 中已注入的 `selected_item_ids`。

## 后果

- MCP 与 HTTP 工具共享 Registry 与 Policy，不得绕过审批。
- Agent Eval 单独度量越权、审批绕过与重复副作用，不替代检索泄漏门禁。
