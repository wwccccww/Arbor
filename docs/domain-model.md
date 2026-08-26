# 领域模型

本文定义 Arbor 的限界上下文、聚合、值对象、不变式与领域事件。实现必须落在 `src/arbor/domain`，不依赖框架。

## 1. 统一语言

| 词 | 含义 | 不是 |
|---|---|---|
| Tenant | 工作空间，数据硬边界 | 用户账号 |
| Member | 空间内的人及其角色 | 人设授权 |
| Persona | 数字人，记忆与会话的属主 | 一次聊天窗口 |
| Profile | 结构化身份（名、性格、禁忌、关系） | 向量切片 |
| Thread | 绑定单一 Persona 的会话 | 租户级群聊 |
| MemoryItem | 一条记忆，有类型与生命周期 | Prompt 里的一段话 |
| InboxItem | 待确认的抽取结果 | 已生效记忆 |
| EventNode | 经历节点 | 向量检索命中 |
| EventEdge | 节点关系（时间后继、因果、涉及人物） | GraphRAG 社区 |
| Citation | 回复对 MemoryItem / EventNode 的引用 | 模型自述「根据记忆」 |
| Grant | 某成员对人设的四项能力 | 空间角色 |

## 2. 限界上下文

### 2.1 Identity Access（身份与访问）

**聚合**

- `Tenant`：id、名称、状态
- `User`：id、主体标识
- `Membership`：`(tenant_id, user_id, role)`，role ∈ {owner, admin, member}

**不变式**

- 每个 Tenant 至少一名 owner。
- 删除 Tenant 是显式用例，不级联「静默清空别人的记忆」而不留审计。

**对外提供**

- `TenantId`、`UserId`、`Role`
- 判定：`can_admin_workspace(user, tenant)`

### 2.2 Persona（人设）

**聚合根 `Persona`**

- `PersonaId`
- `TenantId`（创建后不可迁徙）
- `skin`：companion | employee（仅模板/文案，不改变内核）
- `Profile`（值对象或实体，随聚合提交）
- `ToolPolicy`
- `Grants`：`Grant(user_id, capabilities[])`

**`Profile` 字段（v1）**

- display_name、one_liner、personality、taboos、relationships、locale

**不变式**

- Persona 不能更换 `tenant_id`。
- 改 Profile 立即生效，不写入向量充当「最高优先级身份」。
- 无 `admin` grant 且非空间 Admin/Owner 不得改 Profile / Grants / ToolPolicy。
- `capabilities` ⊆ {chat, read_memory, write_memory, admin}。

**领域服务 `AuthorizationPolicy`**

```text
can_chat / can_read_memory / can_write_memory / can_admin_persona
空间 Admin/Owner 默认具备人设 admin（可在实现中定为策略，但必须单测）。
```

### 2.3 Memory（记忆）

记忆是独立上下文：数量大，不能塞进 Persona 聚合一起加载。

**聚合根 `MemoryItem`**

- `MemoryId`
- `TenantId` + `PersonaId`（必填）
- `ThreadId`（可选）
- `EventId`（可选，挂到树上）
- `type`：fact | episode_summary | file_chunk | image_caption | transcript
- `text`、`importance`、`source`
- `status`：active | superseded | deleted
- `supersedes`：指向被覆盖的 MemoryId（可选）

**聚合根 `InboxItem`**

- 抽取候选：proposed fact / event / conflict
- 与现有 Profile 或 Memory 的冲突说明
- 状态：pending | confirmed | dismissed

**不变式**

- 创建 MemoryItem 必须同时有 TenantId 与 PersonaId。
- `superseded` 记忆不得再进入检索集（由仓储端口保证，领域规定 status）。
- 冲突不得在无用户确认时自动改 Profile。
- 同一 Persona 下，新 fact 确认后，与其矛盾的旧 fact 必须标 `superseded`。

**领域服务 `ConflictDetector`**

- 输入：候选 fact + 当前 Profile + 活跃 facts
- 输出：无冲突 | 冲突（双方摘要）
- 不调用 LLM；LLM 抽取放在应用层，检测规则可先用结构化字段（如 `taboo`、`residence`）匹配，复杂自然语言冲突由应用层用 ReasoningClient **建议**，仍经 Inbox。

### 2.4 Event Graph（事件图）

**聚合根 `EventNode`**（v1 不以整棵树为单一聚合，避免每次对话加载全图）

- `EventId`、`TenantId`、`PersonaId`
- `title`、`happened_at`、`type`（milestone | promise | conflict | daily | work）
- `importance`（关键事件进主干）
- `summary`、`confidence`
- 可选 `caused_by` 边在 `EventEdge` 中表达

**实体 / 值对象 `EventEdge`**

- `from_id`、`to_id`
- `kind`：temporal | caused_by | involves_person

**不变式**

- 边的两端必须同一 `tenant_id + persona_id`。
- 禁止跨人设连边。
- 关键事件由 importance/type 决定，不由向量相似度决定。

**领域服务 `EventTreeProjector`**

- 将节点与边投影为树/时间轴 DTO（只读）。可放应用层查询端；若含「何为父节点」的规则，则留在领域。

v1 边以时间后继为主，因果边按需增加，**不做社区检测、不做多层 GraphRAG 摘要**。

### 2.5 Conversation（会话）

**聚合根 `Thread`**

- `ThreadId`、`TenantId`、`PersonaId`（不可变）
- `summary`（滚动摘要）
- `messages[]` 或按页仓储；消息含 role、content、citations、created_at

**值对象 `Citation`**

- `memory_id` 和/或 `event_id`
- 必须属于该 Thread 的 Persona

**不变式**

- 一个 Thread 一生只绑定一个 Persona。
- 消息不得引用其他 Persona 的 MemoryId。
- 无 `chat` 授权不得追加消息。

**领域服务 `ContextPolicy`**

- 定义上下文槽位：profile、summary、event_hits、memory_hits 的优先级与条数上限。
- 不执行 I/O。

### 2.6 Evaluation（评测，支持子域）

**聚合根 `EvalRun`**

- 金标世界版本、策略名称、指标快照
- 只读生产记忆或使用夹具数据

不向 Persona 写记忆。不得为了刷分修改金标世界而不记版本。

## 3. 跨上下文协作

禁止直接改对方聚合内部。允许：

- 传递 ID（`PersonaId`、`MemoryId`）
- 发布领域事件，应用层订阅后调用另一上下文用例（**v1 未实现**，见 [ADR-0008](adr/0008-domain-events-deferred.md)）

**领域事件（设计预留，v1 未实现）**

下列事件描述目标协作方式，当前代码由应用层用例 **同步** 完成同等副作用（写仓储、删向量、写审计）。

| 事件 | 何时 | 订阅者（设计） |
|---|---|---|
| `PersonaProfileUpdated` | 档案变更 | Memory：相关 fact 可能冲突入 Inbox |
| `InboxItemConfirmed` | 用户确认 | Memory 写入；Event Graph 可能建节点 |
| `MemorySuperseded` | 冲突覆盖 | VectorIndex 删除或标记不可检索 |
| `ImportJobCompleted` | 解析结束 | 通知；批量 Inbox |
| `MessageReplied` | 对话完成 | 可选异步抽取 |

事件载荷只含 ID 与少量值对象，不含 ORM。

## 4. 授权与记忆进入模型（领域规则）

```text
若 not can_read_memory:
    上下文不得包含 Profile 细节以外的 MemoryItem / EventNode
    （是否包含公开 one_liner 由产品策略决定，默认：无 read_memory 仍可 chat 时只用最小 Profile）
若 not can_chat:
    不得追加 Thread 消息
```

「最小 Profile」= display_name + one_liner，避免无记忆权限时完全无法对话，同时不泄露禁忌与关系。此策略必须单测。

## 5. 聚合图（简化）

```text
Tenant ── Membership ── User
   │
   └── Persona ── Grant
          │
          ├── Thread ── Message ── Citation
          ├── MemoryItem
          ├── InboxItem
          └── EventNode ── EventEdge
```

加载规则：按聚合根 ID 加载，禁止 `select * from memories where tenant_id=?` 在领域服务里当聚合用。列表是查询端，走 Query 端口。

## 6. ID 与多租户

所有业务表/实体带 `TenantId`。Persona 作用域的实体还带 `PersonaId`。  
ID 为 UUID。跨上下文引用只存 ID，不存对方快照（引用展示用查询端 join/投影）。

## 7. 与 RAG 的边界

RAG 不是领域概念。领域只认识 `MemoryItem` 及其 `status`。  
「如何找相关记忆」是应用层 + `VectorIndex` 端口。  
领域规定：**被 superseded 的记忆对检索不可见**；**检索集合的边界是 Persona**。
