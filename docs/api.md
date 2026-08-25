# HTTP 接口

入站适配器：`apps/api`（FastAPI）。路径与错误码以本文和 [openapi.yaml](openapi.yaml) 为准。Router 只做 HTTP ↔ 命令/查询对象，业务在应用层。

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
| 403 | `FORBIDDEN_WORKSPACE` `FORBIDDEN_CHAT` `FORBIDDEN_MEMORY_READ` `FORBIDDEN_MEMORY_WRITE` |
| 404 | `NOT_FOUND` |
| 409 | `CONFLICT_INBOX_STATE` `PERSONA_TENANT_MISMATCH` |
| 422 | 请求体 schema |
| 429 | `RATE_LIMITED` |
| 503 | `UPSTREAM_UNAVAILABLE`（DeepSeek 不可用） |

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
  "personality": { "traits": ["冷静"] },
  "taboos": ["香菜"],
  "relationships": [{ "name": "用户", "kind": "partner" }]
}
```

### `GET /v1/personas/{persona_id}`

无 `read_memory` 时返回最小档案（display_name、one_liner），不返回 taboos/relationships 细节。有人设 `admin` 时额外返回 `grants`（与 PUT 同形：`user_id` + `capabilities`）；无 admin 时不带该键。

### `PATCH /v1/personas/{persona_id}`

改档案。需要人设 `admin`。

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

聊天附件只挂在用户消息上，不解析进 Inbox，不直写 Memory。需要 `chat`。GET 历史只回 `filename`；下载走 `GET /v1/threads/{thread_id}/attachments/{filename}`。

响应：

```json
{
  "message_id": "…",
  "role": "assistant",
  "text": "……",
  "citations": [
    { "memory_id": "…", "event_id": "…", "preview": "去年十一月在…" }
  ],
  "inbox_created": 1
}
```

检索顺序由应用层固定：档案 → 摘要 → 事件树 → 向量。响应不返回原始向量。

## 6. 记忆与导入

### `GET /v1/personas/{persona_id}/memories`

Query：`type`、`event_id`、`status`（默认 `active`）、`limit`（1–100，默认 50）、`offset`。需要 `read_memory`。无权限 404。响应含 `items` 与过滤后、分页前的 `total`。每条含 `id`、`text`、`type`、`status`、`event_id`。

### `POST /v1/personas/{persona_id}/imports`

`multipart/form-data`：file + 可选 `hint`。需要 `write_memory`。  
立即返回 `job_id` 与 `status`。配置了 `REDIS_URL` 时任务为真异步（`pending` → worker 解析后进 Inbox）；未配置时在 API 进程内同步完成（`completed`）。不直写 Memory。

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
附件来自该事件上 active 的 `image_caption` / `file_chunk` / `transcript`；其余类型留在 `memories`。

## 8. 评测

### `POST /v1/eval/runs`

```json
{ "strategy": "layered_tree", "suite_version": "v1", "mode": "retrieval" }
```

`mode`：`retrieval`（默认）或 `generation`。`generation` 会跑引用子集检查；若配置了 `FaithfulnessScorer` 再写 `ragas_faithfulness`。空间 Admin。演示模式可打到夹具租户。

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

## 9. 审计

### `GET /v1/audit-logs`

Owner/Admin。过滤 action、persona_id、时间。

## 10. 版本与兼容

- 破坏性变更走 `/v2`，不静默改 v1 语义。
- OpenAPI 是契约；未写入的字段响应端不应依赖。
- 文件上传大小限制由组合根配置，默认 32MB（导入与聊天附件）。超限 400 `VALIDATION_ERROR`，对象存储不留文件。
- `/v1` 按 `Authorization` 头限流，组合根默认每个令牌在 60 秒窗口内最多 120 次；超限 429 `RATE_LIMITED`。无 Bearer 的请求共用 `anon` 配额。`/docs` 与 `/openapi.json` 不计。
