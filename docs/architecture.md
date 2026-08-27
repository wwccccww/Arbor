# 架构设计

Arbor 采用 **六边形架构（端口-适配器）** 承载 **DDD 限界上下文**。目标是：换 UI、换数据库、换 LLM 供应商时，领域规则不动。

## 1. 设计目标

- 领域层可单测，不启动 Postgres、不调用 DeepSeek。
- 检索、权限、记忆写入的规则写在领域/应用层，不写在 SQL 或 prompt 字符串里将就。
- 入站适配器（HTTP、CLI、评测运行器）可替换；出站适配器（pgvector、DeepSeek、S3）可替换。
- 任何检索路径必须携带租户与人设边界，缺一则失败。

## 2. 六边形总览

```text
                    ┌─────────────┐
                    │  Web / CLI  │  入站适配器
                    │  FastAPI    │
                    └──────┬──────┘
                           │ 实现入站端口
                           ▼
                    ┌─────────────┐
                    │  应用层     │  用例 / 事务 / 编排
                    │  (use cases)│
                    └──────┬──────┘
                           │ 调用领域 + 出站端口
                           ▼
                    ┌─────────────┐
                    │  领域层     │  实体 / 聚合 / 不变式
                    └─────────────┘
                           ▲
                           │ 出站端口（接口）
              ┌────────────┴────────────┐
              │                         │
      ┌───────┴───────┐         ┌───────┴───────┐
      │ Postgres      │         │ DeepSeek      │
      │ pgvector      │         │ bge-m3        │
      │ S3 / Redis    │         │ Whisper       │
      └───────────────┘         └───────────────┘
           出站适配器

v1 **无领域事件总线**：跨上下文协作在应用层同步编排（见 [ADR-0008](adr/0008-domain-events-deferred.md)），上图领域层不发布运行时事件。
```

**依赖方向：外 → 内。** 领域层零出站 import。适配器依赖端口，不依赖彼此。

## 3. 分层与允许的依赖

| 层 | 职责 | 可以依赖 | 禁止依赖 |
|---|---|---|---|
| `domain` | 实体、值对象、聚合、领域服务、领域事件 | 仅标准库与本层 | FastAPI、ORM、SDK、环境变量 |
| `ports` | 入站/出站接口（Protocol / ABC） | domain | 适配器、框架 |
| `application` | 用例、DTO、权限校验编排、工作单元 | domain、ports | FastAPI 路由、SQL、DeepSeek SDK |
| `adapters.inbound` | HTTP、CLI、eval runner | application、ports、domain DTO | 直接 new 出站客户端（应经组合根） |
| `adapters.outbound` | Postgres、DeepSeek、bge、S3、Whisper | ports、domain | FastAPI 路由、其他出站适配器 |
| `apps/api` 组合根 | 组装依赖、读配置、启动 | 所有适配器 | 把业务规则写在 main.py |

应用层可以知道「需要一段嵌入向量」，但不知道 bge-m3。  
领域层可以规定「跨人设记忆不得合并」，但不知道向量检索。

## 4. 端口清单

### 4.1 入站端口（Driving / Primary）

由 UI、HTTP、评测脚本调用。**v1 实现**：HTTP 与 CLI 直接调用 `application` 用例类；`ports/inbound/` 仅保留薄 Protocol（`ChatPort`、`EvaluationPort`），尚未实现完整入站端口门面。

| 端口（设计） | 用例 | v1 |
|---|---|---|
| `ChatPort` | 发送消息、获取带引用的回复 | Protocol stub；HTTP → `SendMessage` |
| `PersonaAdminPort` | 创建/更新人设、授权 | HTTP → `persona/commands` |
| `MemoryCommandPort` | 导入、确认 Inbox、删除记忆 | HTTP → `memory/*` 用例 |
| `MemoryQueryPort` | 列表记忆、事件树、引用展开 | HTTP → queries / eventgraph |
| `EvaluationPort` | 跑金标、取报告 | Protocol stub；CLI/HTTP → `evaluation/*` |
| `IdentityPort` | 登录、成员管理 | HTTP → `identity/commands` |

一个入站端口对应一组用例，避免 God Service。完整 Port 类可在 v2 收口 HTTP 与 CLI 的重复 DTO 翻译。

### 4.2 出站端口（Driven / Secondary）

由应用层调用，适配器实现。

| 端口 | 实现（v1） | 可替换为 |
|---|---|---|
| `PersonaRepository` | Postgres | 任意 SQL/NoSQL |
| `MemoryRepository` | Postgres | 同上 |
| `EventGraphRepository` | Postgres 邻接表 | Neo4j（仅当多跳成为瓶颈） |
| `ThreadRepository` | Postgres | — |
| `VectorIndex` | pgvector（`postgres/vector.py`） | Qdrant |
| `LLMClient` | DeepSeek Chat | 其他 OpenAI 兼容端点 |
| `ReasoningClient` | DeepSeek Reasoner | 可回退到 `LLMClient` |
| `FaithfulnessScorer` | RAGAS faithfulness 适配器 | 其他 LLM 评委；仅 generation |
| `EmbeddingClient` | bge-m3 | 其他嵌入模型 |
| `ObjectStorage` | `local` / `postgres`（`object_blobs`）/ `s3`（MinIO 或云） | — |
| `SpeechTranscriber` | Whisper | — |
| `VisionDescriber` | 视觉模型 | — |
| `DocumentParser` | Docling / pypdf | — |
| `JobQueue` | Redis ARQ | — |
| `Clock` / `IdGenerator` | 系统时钟 / UUID | 测试替身 |

**关键约束：** 向量检索只通过 `VectorIndex`，且方法签名必须包含 `tenant_id` 与 `persona_id`。不允许存在「全局相似度搜索」端口。

```text
# 端口形状（示意，非实现）
search(tenant_id, persona_id, query_vector, k, filters) -> list[MemoryHit]
```

缺租户参数的接口不得合并进主分支。

## 5. 应用层用例（事务边界）

每个用例一个类（或一个函数 + 明确命令对象），只做一件事。

| 用例 | 步骤（编排，不含 SQL） |
|---|---|
| `SendMessage` | 鉴权 → 装载档案与摘要 → 路由事件节点 → 向量检索 → 调 LLM → 抽取候选 → 写入 Inbox → 返回引用 |
| `ConfirmInboxItem` | 鉴权 write_memory → 领域合并规则 → 写档案或事件或记忆 → 失效旧向量 |
| `ImportArtifact` | 鉴权 → 存对象 → 入队解析（`SubmitImportJob` + `JobQueue`） |
| `ProcessImportJob` | 解析/转写/描述 → 切 MemoryItem → 嵌入 → 待确认或按策略直写 |
| `GetEventTree` | 鉴权 read_memory → 读节点与边 → 投影为树 DTO |
| `RunEvaluation` | 装载金标世界 → 只调检索与对话端口 → 算指标 |

`SendMessage` **不得**在适配器里拼 SQL 再调 LLM。拼上下文的策略属于应用层 `ContextCompiler`（检索 → `ContextPolicy` 槽位 → 近期 k 条 + summary → 按模型窗口截断），再委托 `ContextPolicy` 定槽位顺序。

## 6. 检索策略（应用层，不是「一种 RAG 框架」）

默认策略 **`layered_tree`**（`SendMessage.strategy` / `ContextCompiler`）。实现集中在 `application/retrieval.py`，由下列模块协作（检索编排 v2，2026-08）：

| 模块 | 职责 |
|---|---|
| `retrieval_config.py` | `RetrievalConfig` + `ARBOR_RETRIEVAL_*` 环境变量 |
| `event_graph_router.py` | 事件种子打分 + 沿 `temporal` / `caused_by` 边扩展 1～2 跳 |
| `query_planner.py` | 复合问拆子 query（默认 `rules`：`因为` / `后来` / `如果`…） |
| `retrieval_lexical.py` | 词级 lexical、类型权重、MMR、RRF 合并 |
| `context_compiler.py` | 检索 → 槽位 → token 预算；`memory_hits` 带 `id` / `score` |
| `context_injection.py` | 注入 payload 形状、极性冲突软检测 |

一次回答的**槽位顺序**仍固定（与 `ContextPolicy` 一致）：

```text
1. 档案        Persona.profile 规则注入，不靠向量
2. 工具策略    tool_policy（若有）
3. 近期摘要    Thread.summary
4. 近期对话    recent_k 条消息（ContextCompiler）
5. 事件        路由种子 + 图扩展后的 EventNode（title/summary）
6. 记忆片段    hybrid 召回 + rerank 后的 MemoryItem（最多 prompt_k 条）
```

**`layered_tree` 检索编排（单轮请求内）**：

```text
query → [可选] rules 拆子 query
     → 每子 query：事件种子 → 边扩展 → event 下记忆
     → 全局 ANN(pool_k) + 事件 scoped ANN(filters.event_ids) → RRF
     → [可选] 应用层 lexical scan → 再 RRF（ARBOR_RETRIEVAL_HYBRID）
     → 合并池 → 词级 rerank + 类型权重 + MMR → rerank_k
     → ContextCompiler 写入 prompt（memory_hits: {id, text, source, score}）
     → 超 token 时按低分优先 trim 记忆
```

**向量端口**：`VectorIndex.search(..., filters)` 已落地，可选键：

- `event_ids` — 只检索挂在这些事件上的记忆
- `types` — 记忆类型白名单
- `exclude_ids` — 排除已进档案层 / 事件层的 id

仍是 **档案 + 事件树路由 + 向量细节**。不上 GraphRAG、不上独立 TreeRAG 产品。

**可观测**：`SendMessage` 响应含 `retrieval_meta`（`hit_ids`、`sources`、`hit_scores`、`sub_queries`、`per_source_counts`）与 `context_truncation_notes`。详见 [api.md](api.md)。

环境变量见 [local-dev.md](local-dev.md)；评测基线见 [evaluation.md](evaluation.md)。技术决策见 [ADR 0009](adr/0009-retrieval-orchestrator-v2.md)。

## 7. 限界上下文与六边形的关系

每个限界上下文内部都是一个小六边形（自己的应用服务与仓储端口），通过 **显式 ID** 和 **领域事件** 协作，禁止跨上下文直接改对方聚合。

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Identity    │     │ Persona     │     │ Memory      │
│ Access      │────▶│             │◀────│             │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │ Conversation│────▶│ Event Graph │
                    └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Evaluation  │  支持子域，只读生产记忆
                    └─────────────┘
```

上下文细节见 [domain-model.md](domain-model.md)。

## 8. 目标代码目录

```text
apps/
  api/                         # 组合根：factory.py、main.py
  web/                         # React 工作台
src/arbor/
  domain/
    identity/
    persona/
    memory/
    eventgraph/
    conversation/
    audit/
    shared/                    # TenantId, PersonaId 等值对象
  application/
    identity/
    persona/
    memory/
    eventgraph/
    conversation/
      context_compiler.py
      context_injection.py
      …
    evaluation/                # 评测支持子域（无 domain/evaluation 聚合）
    audit/
    retrieval.py               # retrieve() 编排入口
    retrieval_config.py
    retrieval_lexical.py
    event_graph_router.py
    query_planner.py
    storage/                   # object_gc 等出站协调
  ports/
    inbound/                   # v1 薄 Protocol
    outbound/                  # 仓储、向量、LLM、ObjectStorage…
  adapters/
    inbound/
      http/                    # register_auth|tenants|personas|threads|audit|eval|feishu
      cli/                     # eval_cli
      eval_runner.py
    outbound/
      postgres/                # 业务表、vector、pool、RLS、migrations
      deepseek/
      embedding.py
      ragas_scorer.py
      s3.py / localfs.py / object_storage.py
      multimodal/
      arq/
      inmemory.py              # 演示与单测替身
eval/
infra/compose/
docs/
```

**导入规则（`tests/architecture/test_import_rules.py` 守护，等同 import-linter 目标）：**

```text
domain            不得 import arbor.adapters / arbor.application / 第三方框架
ports             仅可 import domain
application       仅可 import domain, ports
adapters.inbound  可 import application, ports
adapters.outbound 可 import ports, domain
apps.api          可 import 一切（仅组合根）
```

禁止 `adapters.outbound.deepseek` import `adapters.outbound.postgres`。需要协作时走应用层。

## 9. 请求生命周期

```text
HTTP 请求
  → 入站适配器：鉴权解析、TenantId 注入、请求校验
  → 入站端口用例
  → 领域不变式
  → 出站端口：仓储 / 向量 / LLM
  → 应用层同步编排（v1 无领域事件总线，见 ADR-0008）
  → HTTP 响应 DTO（引用 memory_ids，不把 ORM 对象漏出去）
```

ORM 模型止于 `adapters/outbound/postgres`。领域实体与 ORM 双向翻译只发生在仓储适配器。

## 10. 前端的位置

`apps/web` 是 **入站适配器**，不是第二个后端。它：

- 只调用 HTTP API
- 不内嵌检索逻辑、不直连数据库
- 事件树是投影，不是另一份数据

若未来做桌面端或小程序，再增加一个入站适配器，复用同一套应用层。

## 11. 测试金字塔（与分层对齐）

完整清单、目录、CI 与 P0 用例见 [testing.md](testing.md)。评测策略对比见 [evaluation.md](evaluation.md)。二者不可互相替代。

| 测试 | 测什么 | 替身 |
|---|---|---|
| 领域单测 | 不变式、冲突合并、授权判定 | 无 |
| 应用层单测 | 用例编排、检索顺序、Inbox 流程 | 内存仓储 + Fake LLM |
| 适配器契约测 | Postgres 过滤、向量查询带租户 | 测试库 |
| 架构测试 | import 方向、检索签名含租户 | 无 |
| API 契约 | OpenAPI 路径与错误码 | 测试容器 |
| 评测金标 | Recall / 泄漏 / 身份一致 | 夹具；生成质量才用真实 LLM |

领域测试失败 = 业务规则坏了。契约测试失败 = 过滤漏了。评测失败 = 记忆策略坏了。不要用「再调一次大模型」掩盖。

## 12. 安全与隔离（架构级）

1. 所有出站查询端口带 `tenant_id`。
2. 人设记忆查询额外带 `persona_id`。
3. 应用层在调用 LLM 前再滤一遍：无 `read_memory` 则上下文不含记忆。
4. Prompt 中只放 MemoryId 已授权集合；模型返回的 id 若不在集合内，引用丢弃。
5. 跨租户命中是 **P0 事故**，不是 RAG 调参问题。

## 13. 明确拒绝的架构

- 在 Router 里写业务 + 直接调 DeepSeek
- LangChain / LlamaIndex 作为领域模型
- 领域实体继承 SQLAlchemy Model
- 全局向量集合（没有租户列）
- Conversation 上下文直接 import Memory 的 ORM
- 为简历引入 GraphRAG 流水线（社区检测、多层摘要）作为 v1 底座
