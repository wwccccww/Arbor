# HTTP 接口

入站适配器：`src/arbor/adapters/inbound/http/`（`register_*.py` 注册路由）。组合根：`apps/api/factory.py`。路径与错误码以本文和 [openapi.yaml](openapi.yaml) 为准。Router 只做 HTTP ↔ 命令/查询对象，业务在应用层。

生产入口 `create_app_from_env()`：有 `DEEPSEEK_API_KEY` 时用 DeepSeek Chat + Reasoner，否则 ScriptedLLM / ScriptedReasoner。单测调用 `create_app()` 始终用假适配器，即使环境里有密钥。抽取进 Inbox，确认后才写记忆。

基路径：`/v1`  
认证：`Authorization: Bearer <access_token>`  
租户：`X-Tenant-Id: <uuid>`（除登录、列出自己加入的空间外，均必填）

## 1. 约定

### 1.1 错误

```json
{
  "error": {
    "code": "FORBIDDEN_MEMORY_READ",
    "message": "当前授权不能读取该人设记忆",
    "request_id": "01J…"
  }
}
```

`request_id` 为每次错误单独生成的 ULID，不再写死。

| HTTP | code 示例 |
|---|---|
| 400 | `VALIDATION_ERROR` |
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN_WORKSPACE` `FORBIDDEN_CHAT` `FORBIDDEN_MEMORY_READ` `FORBIDDEN_MEMORY_WRITE` `FORBIDDEN_PLAN_SCRIPT` |
| 404 | `NOT_FOUND` |
| 409 | `CONFLICT_INBOX_STATE` `PERSONA_TENANT_MISMATCH` |
| 422 | 请求体 schema |
| 429 | `RATE_LIMITED` |
| 503 | `UPSTREAM_UNAVAILABLE`（DeepSeek 不可用） |

Agent / 数字员工专用错误码（HTTP 400/403/404/409）：

| code | 含义 |
|---|---|
| `FORBIDDEN_PLAN_SCRIPT` | 生产环境禁止 `plan_script`（测试需 `ARBOR_ALLOW_PLAN_SCRIPT=1`） |
| `FORBIDDEN_TOOL` | 工具未注册或岗位策略不允许 |
| `APPROVAL_EXPIRED` | 审批已过期，副作用不得执行 |
| `AGENT_RUN_TERMINAL` | Run 已终态，不可继续推进 |
| `AGENT_VERSION_CONFLICT` | 并发推进版本冲突 |
| `EMPLOYEE_EVAL_GATE` | 岗位评测未通过，不可发布定义 |
| `WORKING_MEMORY_CAPACITY` | Run 级 Working Memory 条目达上限 |

跨租户或跨人设「猜 UUID」一律 404，不暴露存在性（实现可对无权资源返回 404）。

### 1.2 引用

助手消息的 `citations` 只允许包含本次上下文实际注入的 id。模型幻觉出的 id 由应用层丢弃。HTTP 对话响应把引用写成 `{memory_id, event_id, preview}`；评测内部仍用 id 列表做子集检查。

## 2. 身份

### `POST /v1/auth/login`

```json
{ "email": "demo-a@arbor.eval", "password": "arbor-owner" }
```

```json
{ "access_token": "…", "refresh_token": "…", "user": { "id": "…", "email": "…" } }
```

演示账号：`demo-a@arbor.eval` / `arbor-owner`（owner），`member-a@arbor.eval` / `arbor-member`（仅 CHAT）。旧静态令牌 `token-a` / `token-member` 仍可用。

### `POST /v1/auth/refresh`

```json
{ "refresh_token": "…" }
```

刷新会轮换 access / refresh。旧 access 立即失效。

### `POST /v1/auth/logout`

```json
{ "refresh_token": "…" }
```

作废该 refresh。前端清本地会话即可视为登出。

### `GET /v1/me`

当前用户、加入的 tenants，以及运行时：

```json
{
  "user": { "id": "…", "email": "demo-a@arbor.eval" },
  "tenants": [{ "id": "…", "name": "演示租户A", "role": "owner" }],
  "runtime": { "llm": "deepseek", "store": "memory", "embed": "bge-m3" }
}
```

`runtime.llm` 为 `deepseek` 或 `scripted`；`runtime.store` 为 `postgres` 或 `memory`；`runtime.embed` 为 `fixture` 或 `bge-m3`（及其他 HTTP 嵌入模型名）。

### 飞书日历（可选）

配置 `ARBOR_FEISHU_APP_ID`、`ARBOR_FEISHU_APP_SECRET` 后启用（`ARBOR_CALENDAR_BACKEND=auto` 默认会自动选飞书）。

| 方法 | 说明 |
|------|------|
| `GET /v1/me/feishu/status` | 是否已绑定飞书日历 |
| `GET /v1/me/feishu/connect` | 返回 `authorize_url`，浏览器打开完成 OAuth |
| `DELETE /v1/me/feishu/disconnect` | 解除绑定 |
| `GET /v1/auth/feishu/callback` | OAuth 回调（飞书重定向，无需手动调） |

### 工单 HTTP（可选）

`ARBOR_TICKET_API_URL` 配置后，`ticket` 工具会向该 URL `POST` JSON：`tenant_id`、`user_id`、`title`、`description`、`source=arbor-chat`。可选 `ARBOR_TICKET_API_KEY` 作为 Bearer。

### 工单工具 API（工作台 UI）

`POST /v1/personas/{persona_id}/tools/ticket`

需人设 `tool_policy.allowed_tools` 包含 `ticket`，且调用方对该人设有 `chat` 授权。

```json
{ "title": "面店空调故障", "description": "制冷不足，请安排检修" }
```

响应（stub 或 HTTP 后端）示例：

```json
{
  "tool": "ticket",
  "status": "ok",
  "ticket_id": "stub-ticket-001",
  "title": "面店空调故障",
  "note": "演示工单已登记（stub），未连接真实工单系统"
}
```

错误：`403 FORBIDDEN_TOOL`（未授权工具）、`403 FORBIDDEN_CHAT`（无对话权限）。

聊天响应 `POST /v1/threads/{thread_id}/messages` 与消息列表在助手消息上可带 `tool_results`（与关键词/LLM 工具执行结果同形）。

### 日历工具 API（工作台 UI）

`POST /v1/personas/{persona_id}/tools/calendar`

需人设 `tool_policy.allowed_tools` 包含 `calendar`，且调用方对该人设有 `chat` 授权。飞书真实日程需用户先绑定飞书日历。

```json
{ "query_text": "这周有什么安排" }
```

### 人设列表统计

`GET /v1/personas?include_stats=true`

在列表项上附加 `stats`：`memory_count`（需 `read_memory`）、`thread_count` / `last_interaction` / `last_interaction_at`（需 `chat`）。

### 工具调用模式

`ARBOR_TOOL_MODE`：

- `keywords`：仅用户消息关键词触发工具
- `llm`：仅模型 JSON 中 `tool_calls` 触发
- `both`（默认）：关键词预执行 + 模型可追加 `tool_calls`

飞书环境变量：`ARBOR_FEISHU_APP_ID`、`ARBOR_FEISHU_APP_SECRET`、`ARBOR_FEISHU_REDIRECT_URI`、`ARBOR_CALENDAR_BACKEND`、`ARBOR_WEB_URL`。

## 3. 工作空间

### `GET /v1/tenants`

当前用户的空间列表。

### `POST /v1/tenants`

```json
{ "name": "私人空间" }
```

创建者成为 owner。

### `DELETE /v1/tenants/{tenant_id}`

仅 Owner。空间里还有人设时拒绝（本刀不级联删记忆）。空空间删除后不再出现在列表里。

### `GET /v1/tenants/{tenant_id}/members`

### `POST /v1/tenants/{tenant_id}/members`

```json
{ "email": "c@d.com", "role": "member" }
```

Owner/Admin。

### `PATCH /v1/tenants/{tenant_id}/members/{user_id}`

```json
{ "role": "admin" }
```

## 4. 人设

### `GET /v1/personas`

当前租户下，调用者可见的人设（Owner/Admin 全量；Member 仅有 grant 的）。

### `POST /v1/personas`

```json
{
  "skin": "companion",
  "display_name": "林夏",
  "one_liner": "住在杭州的陪伴助手",
  "avatar": "🌿",
  "personality": { "traits": ["冷静"] },
  "taboos": ["香菜"],
  "relationships": [{ "name": "用户", "kind": "partner" }]
}
```

### `GET /v1/personas/{persona_id}`

无 `read_memory` 时返回最小档案（display_name、one_liner），不返回 taboos/relationships 细节。有人设 `admin` 时额外返回 `grants`（与 PUT 同形：`user_id` + `capabilities`）；无 admin 时不带该键。

### `PATCH /v1/personas/{persona_id}`

改档案。需要人设 `admin`。可更新 `tool_policy`（`allowed_tools`、`notes`）与 `avatar`（emoji 或单字）。

### `PUT /v1/personas/{persona_id}/grants`

```json
{
  "grants": [
    { "user_id": "…", "capabilities": ["chat", "read_memory"] }
  ]
}
```

全量覆盖该人设授权（更安全，避免增量补丁漏收权）。

## 5. 会话与对话

### `POST /v1/personas/{persona_id}/threads`

创建会话。需要 `chat`。

### `GET /v1/personas/{persona_id}/threads`

### `GET /v1/threads/{thread_id}/messages`

需要 `chat`。Query：`limit`（1–100，默认 50）、`offset`。响应含 `items` 与分页前的 `total`。无权限或跨租户 404。

### `GET /v1/threads/{thread_id}/attachments/{filename}`

需要 `chat`。返回本会话里已存储的文件字节。只认消息上带 `uri` 的 multipart 附件；JSON 只带 filename、未存文件的 404。无权限或跨租户 404。不写 Memory。

### `POST /v1/threads/{thread_id}/export`

需要 `chat`。返回会话 JSON（消息正文 + 引用 id），写一条脱敏审计 `thread.export`（只记 `message_count`，不写对话正文）。不改 Memory。无权限或跨租户 404。

### `POST /v1/threads/{thread_id}/messages`

发送用户消息。`multipart/form-data` 可带 `text` + `file`（文件进对象存储）；或 JSON：

```json
{
  "text": "我们上次为什么吵架？",
  "attachments": []
}
```

聊天附件在具备 `write_memory` 时会解析进 Inbox（`file_chunk` / `transcript` / `image_caption`），不直写 Memory；仅 `chat` 权限时附件只挂在消息上。需要 `chat`。GET 历史只回 `filename`；下载走 `GET /v1/threads/{thread_id}/attachments/{filename}`。配置了视觉描述时，检索与 LLM 上下文会附带图片摘要，消息正文仍为用户输入的文字。

可选查询参数 `?stream=true`：以 SSE 流式返回助手回复分片，末包为完整 JSON（含 `citations`）。

响应：

```json
{
  "message_id": "…",
  "role": "assistant",
  "text": "……",
  "citations": [
    { "memory_id": "…", "event_id": "…", "preview": "去年十一月在…" }
  ],
  "injected_memory_ids": ["…"],
  "context_token_budget": 12000,
  "context_token_estimate": 4200,
  "context_truncation_notes": [],
  "retrieval_meta": {
    "strategy": "layered_tree",
    "hit_ids": ["…"],
    "sources": { "…": "vector" },
    "hit_scores": { "…": 0.82 },
    "sub_queries": [{ "query": "…", "intent": "episode" }],
    "per_source_counts": { "profile": 3, "event_tree": 2, "vector": 8 }
  },
  "inbox_created": 1
}
```

`retrieval_meta` 供调试与体检页展示本轮检索来源；不向客户端返回向量。注入进 LLM 的 `memory_hits` 为 `{id, text, source?, score?}` 列表（在 `prompt_slots` 内，流式与非流式路径一致）。

检索编排见 [architecture.md §6](architecture.md)；顺序仍为：档案 → 摘要 → 近期对话 → 事件树路由（含边扩展）→ hybrid 向量 → rerank → 组装上下文。

## 6. 记忆与导入

### `GET /v1/personas/{persona_id}/memories`

Query：`type`、`event_id`、`status`（默认 `active`）、`limit`（1–100，默认 50）、`offset`。需要 `read_memory`。无权限 404。响应含 `items` 与过滤后、分页前的 `total`。每条含 `id`、`text`、`type`、`status`、`event_id`。

### `DELETE /v1/personas/{persona_id}/memories/{memory_id}`

软删除一条记忆并移除向量索引。需要 persona 的 `admin` 能力；无权限 403 `FORBIDDEN_MEMORY_WRITE`，不存在 404。成功 204。

### `POST /v1/personas/{persona_id}/imports`

`multipart/form-data`：file + 可选 `hint`。需要 `write_memory`。  
立即返回 `job_id` 与 `status`。配置了 `REDIS_URL` 时任务为真异步（`pending` → worker 解析后进 Inbox）；未配置时在 API 进程内同步完成（`completed`）。不直写 Memory。

完成后的任务含 `parser`（如 `plain_text`、`pypdf`、`reasoner`、`faster_whisper`）、`media_kind`（`text` / `document` / `image` / `audio`）、`chunks_parsed` 与 `inbox_created`。

### `GET /v1/imports/{job_id}`

任务状态：`pending` / `running` / `completed` / `failed`；失败时含 `error`。

### `GET /v1/personas/{persona_id}/inbox`

待确认抽取。需要 `write_memory` 或 `admin`。

### `POST /v1/inbox/{inbox_id}/confirm`

```json
{ "mark_key_event": true }
```

已确认或已忽略的条目再操作返回 409 `CONFLICT_INBOX_STATE`。未知 id 仍是 404。

### `POST /v1/inbox/{inbox_id}/dismiss`

### `POST /v1/personas/{persona_id}/inbox/bootstrap`

将待确认 Inbox 批量落成记忆：启发式补全档案（`one_liner`、禁忌），并为事件类条目创建关键事件节点。需要 `write_memory`。响应：

```json
{
  "profile_updated": true,
  "events_created": 2,
  "memories_created": 8,
  "inbox_processed": 8
}
```

创建向导或首页「从聊天导入」在 `imports` 完成后应调用本接口。

## 7. 事件树

### `GET /v1/personas/{persona_id}/events/tree`

Query：`view=tree|timeline`、`key_only=true`。

```json
{
  "nodes": [
    {
      "id": "…",
      "title": "第一次见面",
      "happened_at": "2024-11-02T00:00:00Z",
      "type": "milestone",
      "importance": 5,
      "summary": "…",
      "confidence": 0.92,
      "memory_ids": ["…"]
    }
  ],
  "edges": [
    { "from_id": "…", "to_id": "…", "kind": "temporal" }
  ]
}
```

### `GET /v1/events/{event_id}`

事件卡：节点 + 附件 + 相关记忆预览。需要 `read_memory`。无权限 404。  
响应含 `confidence`、`participants`、`causal_in`、`causal_out`、`verbatim`（原话类记忆）与 `attachments`。

## 8. Agent Runtime 与数字员工

需要 `chat`；审批列表与岗位治理需要空间 Admin（`token-a` / owner）。

### `POST /v1/personas/{persona_id}/agent-runs`

创建 Agent Run。`202` 返回 `{ id, status, version }`。测试环境可通过 `plan_script` 注入确定性步骤（需 `ARBOR_ALLOW_PLAN_SCRIPT=1`；生产返回 403 `FORBIDDEN_PLAN_SCRIPT`）。

### `GET /v1/agent-runs/{run_id}`

Run 详情 + 步骤树 + 可选 lineage。无 Chat 权限 403；跨成员 403。

### `GET /v1/personas/{persona_id}/agent-runs`

列出 persona 下最近 Run（`items[]`）。

### `GET /v1/agent-runs/{run_id}/steps`

步骤列表 `{ run_id, steps[] }`。

### `POST /v1/agent-runs/{run_id}/resume`

恢复非终态 Run（如 `waiting_approval`）。终态 Run 返回 400 `AGENT_RUN_TERMINAL`。

### `POST /v1/agent-runs/{run_id}/cancel`

取消 Run；已终态则返回当前状态。

### `GET /v1/approvals`

待审批队列（Admin）。`items[]` 含 `id`、`run_id`、`tool_name`、`status`。

### `POST /v1/approvals/{approval_id}/approve`

可选 body：`{ "modified_arguments": {…} }`。过期审批 400 `APPROVAL_EXPIRED`。

### `POST /v1/approvals/{approval_id}/reject`

拒绝审批并终止 Run 工具步骤。

### `POST /v1/agent-eval/runs`

空间 Admin 触发 workspace 级 agent-v1 smoke；返回评测报告摘要。

### `GET /v1/employee-templates`

岗位模板列表（需登录）。

### `GET /v1/personas/{persona_id}/employee-definition`

当前发布版或指定 `?version=` 的定义。

### `GET /v1/personas/{persona_id}/employee-definitions`

版本历史 `items[]`（含 `release_status`、`eval_gate_passed`）。

### `POST /v1/personas/{persona_id}/employee-definitions`

Admin 创建 draft 定义（`201`）。body 含 `version`、`role`、`evaluation_suite`、`tool_policy` 等。

### `POST /v1/personas/{persona_id}/employee-eval`

Admin 跑岗位绑定评测套件；Query 可选 `version`。响应含 `gate_passed`、`task_success_rate`、`p0_security`。

### `POST /v1/personas/{persona_id}/employee-definitions/{version}/publish`

评测门禁通过后发布；未通过 400 `EMPLOYEE_EVAL_GATE`。

### `POST /v1/personas/{persona_id}/memories/{memory_id}/publish`

Admin 发布 procedural draft（supersede 同版本旧条目）。非 draft 或非 procedural 返回 400。

### `DELETE /v1/personas/{persona_id}`

Admin 软删除 persona 并归档 employee definitions。响应 `{ deleted, employee_definitions_archived }`。

### Chat SSE（`POST /v1/threads/{thread_id}/messages?stream=true`）

`text/event-stream` 事件：

- `{ "type": "delta", "text": "…" }`
- `{ "type": "done", … }`（含 `message_id`、`citations`、`inbox_created`）
- `{ "type": "error", "error": { "code", "message" } }`

## 9. 评测

### `POST /v1/personas/{persona_id}/eval/runs`

单人设轻量体检：从该人设档案与关键事件自动生成 5～8 道检索题（不跑 suite-v1 隐私题）。需要空间 Admin 或对该人设的 `admin`。

```json
{ "strategy": "layered_tree" }
```

响应 `202`：`{ "id": "…" }`。结果写入 `eval_runs`，与全局评测共用 `GET /v1/eval/runs/{run_id}`。

### `POST /v1/eval/seed-world`

装载 suite-v1 冻结演示世界（租户 A/B、林夏/小周等）。仅空间 Admin。会清空演示租户下的人设与记忆后重载夹具。响应含 `persona_count`、`memory_count`。

### `POST /v1/eval/runs`

```json
{ "strategy": "layered_tree", "suite_version": "v1", "mode": "retrieval" }
```

`mode`：`retrieval`（默认）或 `generation`。`generation` 会跑引用子集检查；若配置了 `FaithfulnessScorer` 再写 `ragas_faithfulness`。空间 Admin。演示模式可打到夹具租户。

### `GET /v1/eval/runs`

列出本租户最近评测运行（空间 Admin）。查询参数 `limit`（默认 10，最大 50）。返回 `items[]`：`id`、`strategy`、`suite_version`、`mode`、`metrics`、`p0_tenant_leak_zero`（不含逐题 `cases`，详情见单条 GET）。

### `GET /v1/eval/runs/{run_id}`

```json
{
  "metrics": {
    "identity_consistency": 1.0,
    "recall_at_5": 0.82,
    "persona_leak_rate": 0.0,
    "tenant_leak_count": 0,
    "citation_subset_rate": 1.0,
    "ragas_faithfulness": 0.86
  }
}
```

`tenant_leak_count` 必须为 0，否则该策略不得标为默认。`ragas_faithfulness` 仅 generation 有值；检索 run 可省略。接线见 [ragas.md](ragas.md)。

## 10. 审计

### `GET /v1/audit-logs`

Owner/Admin。过滤 action、persona_id、时间。

## 11. 版本与兼容

- 破坏性变更走 `/v2`，不静默改 v1 语义。
- OpenAPI 是契约；未写入的字段响应端不应依赖。
- 文件上传大小限制由组合根配置，默认 32MB（导入与聊天附件）。超限 400 `VALIDATION_ERROR`，对象存储不留文件。
- `/v1` 按 `Authorization` 头限流，组合根默认每个令牌在 60 秒窗口内最多 120 次；超限 429 `RATE_LIMITED`。无 Bearer 的请求共用 `anon` 配额。`/docs` 与 `/openapi.json` 不计。
