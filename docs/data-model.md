# 数据模型

持久化只存在于出站适配器 `adapters/outbound/postgres`。本表结构是该适配器的默认实现，**不是领域层**。换库时保持端口语义即可。

所有业务表包含 `tenant_id`。人设作用域表包含 `persona_id`。查询必须同时过滤二者（人设作用域时）。

## 1. ER 概览

```text
tenants ─┬─ memberships ─ users
         └─ personas ─┬─ persona_grants
                      ├─ threads ─ messages
                      ├─ memory_items
                      ├─ inbox_items
                      ├─ event_nodes ─ event_edges
                      ├─ import_jobs
                      └─ audit_logs
```

`memory_items.embedding` 使用 pgvector。不要把向量放到无租户列的独立库，除非 `VectorIndex` 适配器仍强制过滤。

## 2. 表

### tenants

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | TenantId |
| name | text | |
| created_at | timestamptz | |

### users

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| email | citext unique | v1 登录标识 |
| password_hash | text | 可后续换 OAuth |
| created_at | timestamptz | |

### memberships

| 列 | 类型 | 说明 |
|---|---|---|
| tenant_id | uuid fk | |
| user_id | uuid fk | |
| role | text | owner / admin / member |
| pk | (tenant_id, user_id) | |

### personas

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid fk | 不可更新 |
| skin | text | companion / employee |
| display_name | text | Profile |
| one_liner | text | |
| personality | jsonb | |
| taboos | jsonb | |
| relationships | jsonb | |
| tool_policy | jsonb | |
| created_at / updated_at | timestamptz | |

### persona_grants

| 列 | 类型 | 说明 |
|---|---|---|
| persona_id | uuid | |
| tenant_id | uuid | 冗余便于 RLS |
| user_id | uuid | |
| capabilities | text[] | chat, read_memory, write_memory, admin |
| pk | (persona_id, user_id) | |

### threads

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid | |
| persona_id | uuid | 不可更新 |
| summary | text | 滚动摘要 |
| created_at / updated_at | timestamptz | |

### messages

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid | |
| thread_id | uuid | |
| role | text | user / assistant / system |
| content | text | 消息正文 |
| citation_memory_ids | uuid[] | |
| citation_event_ids | uuid[] | |
| attachments | jsonb | `[{filename, uri}]`；聊天附件不进 Memory |
| created_at | timestamptz | |

### memory_items

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid not null | |
| persona_id | uuid not null | |
| thread_id | uuid null | |
| event_id | uuid null | |
| type | text | fact / episode_summary / file_chunk / image_caption / transcript |
| text | text | 可检索正文 |
| importance | smallint | |
| source | jsonb | 导入来源、页码、附件 URI |
| status | text | active / superseded / deleted |
| supersedes | uuid null | |
| embedding | vector | 演示为 `fixture_embed`（64 维）；真实路径为 bge-m3（1024 维）。同一库不要混用两种维数 |
| created_at | timestamptz | |

**索引**

```text
UNIQUE / PK: id
INDEX: (tenant_id, persona_id, status)
INDEX: ivfflat 或 hnsw ON embedding
       -- 查询必须带 tenant_id、persona_id 条件，避免全库 ANN
OPTIONAL: GIN tsvector(text) 用于专名混合检索
```

**查询契约**

```sql
SELECT id, text, event_id, embedding <=> :q AS dist
FROM memory_items
WHERE tenant_id = :tenant
  AND persona_id = :persona
  AND status = 'active'
  -- 可选: event_id = :event
ORDER BY embedding <=> :q
LIMIT :k;
```

禁止无 `tenant_id` 的 ANN。集成测试必须覆盖「两个租户相似文本互不命中」。

### inbox_items

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id / persona_id | uuid | |
| kind | text | fact / event / conflict |
| payload | jsonb | 候选内容 |
| conflict_with | jsonb null | |
| status | text | pending / confirmed / dismissed |
| created_at | timestamptz | |

### event_nodes

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id / persona_id | uuid | |
| title | text | |
| happened_at | timestamptz null | |
| type | text | milestone / promise / conflict / daily / work |
| importance | smallint | 主干阈值 |
| summary | text | |
| confidence | real | |
| created_at | timestamptz | |

### event_edges

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id / persona_id | uuid | 两端必须同人设 |
| from_id / to_id | uuid | |
| kind | text | temporal / caused_by / involves_person |

应用层或数据库 CHECK：from/to 的 persona_id 一致。跨人设插入必须失败。

### import_jobs

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id / persona_id | uuid | |
| object_uri | text | |
| mime | text | |
| status | text | queued / running / completed / failed |
| error | text null | |
| created_at / finished_at | timestamptz | |

### audit_logs

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid | |
| actor_user_id | uuid | |
| action | text | persona.update / memory.import / memory.confirm / thread.export … |
| resource_type / resource_id | text / uuid | |
| payload | jsonb | 脱敏 |
| created_at | timestamptz | |

### eval_runs

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid | 演示租户或评测夹具 |
| suite_version | text | 金标版本 |
| strategy | text | summary_only / vector_only / layered / layered_tree |
| metrics | jsonb | |
| created_at | timestamptz | |

## 3. RLS（可选第二道闸）

应用层过滤是第一道闸。Postgres RLS 建议：

```text
SET app.tenant_id = '<uuid>';
POLICY: tenant_id = current_setting('app.tenant_id')::uuid
```

评测夹具库可关闭 RLS，但生产配置应开启。缺 RLS 不能作为跨租户泄漏的借口。

## 4. 对象存储

原图、音频、PDF 不进 Postgres 业务表。实现上由 `ObjectStorage` 适配器写入本地盘、`object_blobs` 表或 S3 兼容存储；`source.uri` / 消息 `attachments.uri` 保存返回的 key。本地开发可用 `infra/compose/minio.yml` 起 MinIO（见 [local-dev.md](local-dev.md)）。删除 MemoryItem 时由应用层发出站端口删对象（或标记 GC）。

## 5. 迁移原则

- 用 Alembic，迁移文件只放在 `src/arbor/adapters/outbound/postgres/migrations/`，不放领域逻辑。
- API 启动调用 `PostgresSession.migrate()`（`alembic upgrade head`），**不要 DROP**。空库才 seed suite-v1 演示世界。
- `reset()`（删 public schema 再升级）只给契约测和 `arbor-eval` 用。
- 本机：`DATABASE_URL=... alembic upgrade head`
- `embedding` 维度变更视为新列或重建索引，需同步评测基线。
- 禁止在迁移里调用 LLM。
