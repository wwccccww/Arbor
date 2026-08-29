# 可观测性设计

本文是 Arbor 可观测能力的实现契约。目标不是把用户文本和模型原始思考塞进监控系统，而是让开发、运维和受权管理员分别能回答：

1. 服务是否可用、错误或延迟在哪里；
2. 某次请求经过了哪些系统步骤；
3. 一次 RAG 回答使用了哪些证据，为什么出现裁剪、冲突或失败；
4. 导入、Inbox、记忆和评测质量是否发生退化。

本文的设计适用于 API 进程和 ARQ worker。领域层不得依赖 Prometheus、OpenTelemetry、Grafana、Loki 或任何具体 SDK。

## 1. 范围与非目标

### 1.1 范围

- HTTP 请求、依赖调用、RAG、LLM/Reasoner、工具调用、导入任务、Inbox 和记忆状态迁移；
- Prometheus 指标、Loki JSON 日志、Tempo OpenTelemetry trace；
- 受限的、可查询的 `decision_trace`，用于解释一轮对话的系统决策；
- 健康检查、Grafana dashboards 与告警规则。

### 1.2 非目标

- 不将完整 prompt、用户原文、完整记忆文本、附件二进制、API key 或 Authorization header 写入日志、指标或 trace；
- 不将 `request_id`、thread/message/persona UUID 等高基数值作为 Prometheus label；
- 不默认采集或展示模型 raw CoT / `reasoning_content`；
- 不以 Grafana 代替审计日志、业务数据库或在线权限校验。

## 2. 分层与数据去向

```text
Arbor API / ARQ Worker
  ├── Prometheus metrics ───────→ Prometheus ─→ Grafana Dashboard / Alert
  ├── JSON structured logs ─────→ Loki ───────→ Grafana Explore
  ├── OpenTelemetry spans ──────→ Tempo ──────→ Grafana Trace
  └── decision traces ──────────→ Postgres/S3 → Arbor Debug API / UI
```

| 数据 | 主载体 | 查询入口 | 用途 |
|---|---|---|---|
| QPS、错误率、P95、token、队列数 | Prometheus | Grafana dashboard | 趋势与告警 |
| 单请求步骤、依赖耗时、异常上下文 | Tempo | Grafana trace view | 链路排障 |
| 请求与状态迁移事件、错误详情 | Loki | Grafana Explore | 按 ID 定位 |
| 检索依据、裁剪和结构化 reasoner 结果 | `decision_traces` | Arbor Debug 页 | 回答解释 |
| `audit_logs`、`eval_runs` | Postgres | 现有 Audit/Checkup、Grafana 聚合 | 业务与质量 |

## 3. 隐私、安全与基数规则

### 3.1 可以采集

- 模型、策略、parser、工具名等枚举；
- 请求/步骤的状态、耗时、重试次数、HTTP 状态类别；
- token 数、字节数、候选数、命中数、裁剪数；
- 记忆、事件、会话、任务的 ID（仅日志、trace attribute 或受限调试记录）；
- 输入文本的长度或不可逆 hash。

### 3.2 禁止采集

- API key、Bearer token、Cookie、Authorization header；
- 上传附件原文或二进制；
- 默认路径下的完整 prompt、用户消息、记忆文本、模型输出；
- 未经显式采样授权的 raw CoT / `reasoning_content`。

### 3.3 Prometheus label 规则

允许：`route`、`method`、`status_class`、`strategy`、`model`、`operation`、`parser`、`source`、`result`、`reason`。

禁止：`request_id`、tenant/persona/thread/message/job ID、完整错误信息、文本 hash、时间戳。它们会持续产生新时序并导致 Prometheus 高基数故障。

tenant/persona/thread ID 可作为 Loki JSON 字段、Tempo span attribute 或 `decision_trace` 字段。访问这些数据的 Grafana 角色必须受限。

## 4. 请求上下文与关联

新增 `arbor.observability.context`，通过 `contextvars` 保存当前上下文：

```python
@dataclass(frozen=True)
class RequestContext:
    request_id: str
    trace_id: str | None = None
    tenant_id: str | None = None
    persona_id: str | None = None
    thread_id: str | None = None
    actor_id: str | None = None
```

FastAPI middleware 的职责：

1. 信任格式正确的入站 `X-Request-Id`，否则生成新的 ULID；
2. 创建根 trace/span，并将上下文放入 `contextvars`；
3. 在每个成功或失败响应加 `X-Request-Id`；
4. 将该 ID 写入错误响应体，替代错误处理器临时生成的独立 ID；
5. 记录 HTTP 时长、端点模板、状态类别与异常类别；
6. 将 `request_id` 写入异步任务 payload；ARQ worker 取出后创建子 trace。

`request_id` 用于人工检索，OTEL `trace_id` 用于分布式追踪；二者都应存在，但不用互相替代。

## 5. 应用层端口

应用层通过小端口表达观测事件，而不是直接导入观测 SDK：

```python
class ObservabilityPort(Protocol):
    def event(self, name: str, **fields: object) -> None: ...

    @contextmanager
    def span(self, name: str, **fields: object) -> Iterator[SpanHandle]: ...

    def increment(self, name: str, value: float = 1, **labels: str) -> None: ...

    def observe(self, name: str, value: float, **labels: str) -> None: ...
```

实现：

- `NoopObservability`：默认与领域单测；
- `InMemoryObservability`：应用层单测断言事件、指标与 span；
- `ProductionObservability`：组合 JSON logger、Prometheus 与 OTEL adapter。

将该端口作为可选依赖注入 `SendMessage`、`ContextCompiler`、`MediaToInbox`、`RunImportJob` 等用例。实体和值对象不接触该端口。

## 6. 事件、span 与指标

### 6.1 HTTP 与依赖

| 事件/span | 位置 | 字段 |
|---|---|---|
| `http.request` | FastAPI middleware | route、method、status_class、duration_ms |
| `dependency.call` | DB/Redis/S3/HTTP adapter | dependency、operation、result、duration_ms、retry_count |
| `rate_limit.rejected` | 限流 middleware | scope、result |

### 6.2 对话、RAG 与模型

| 事件/span | 位置 | 字段 |
|---|---|---|
| `conversation.send` | `SendMessage` | stream、result、duration_ms、inbox_created |
| `rag.retrieve` | 检索编排 | strategy、candidate_count、hit_count、各来源数量 |
| `rag.rerank` | rerank 步骤 | input_count、output_count、duration_ms |
| `rag.compile_context` | `ContextCompiler` | token_budget、token_estimate、injected_count、trim_count |
| `llm.chat` | `DeepSeekChatLLM` | model、stream、input/output tokens、TTFT、duration_ms、result |
| `llm.extract` | `DeepSeekReasoner.extract` | model、result_kind、parse_result、duration_ms |
| `llm.summarize` | `DeepSeekReasoner.summarize` | model、duration_ms、result |
| `tool.call` | 工具 adapter | tool、result、duration_ms、error_kind |

`DeepSeekChatLLM` 与 `DeepSeekReasoner` 只记录上游 HTTP 状态类别，不记录 request/response body。若供应商返回 usage，应记录 token 数；未返回则记录 `null`，不自行伪造。

### 6.3 导入与记忆生命周期

| 事件/span | 位置 | 字段 |
|---|---|---|
| `import.submitted` | `SubmitImportJob` | media_kind、size_bucket、execution_mode |
| `import.process` | `RunImportJob` | parser、chunk_count、result、duration_ms |
| `inbox.created` | `MediaToInbox` / 对话抽取 | kind、conflict、count |
| `inbox.transition` | Confirm/Dismiss Inbox | from_status、to_status、kind、age_seconds |
| `memory.transition` | 写入/替换/删除 | from_status、to_status、type、source |

状态是持久化业务事实，日志只写转换；不要重复记录“任务仍在运行”的心跳噪声。

### 6.4 Prometheus 指标

所有指标必须 `arbor_` 前缀。

```text
arbor_http_requests_total{route,method,status_class}
arbor_http_request_duration_seconds_bucket{route,method}

arbor_chat_requests_total{stream,result}
arbor_chat_duration_seconds_bucket{model,result}
arbor_rag_retrieval_duration_seconds_bucket{strategy}
arbor_rag_context_duration_seconds_bucket
arbor_rag_hits_total{source}
arbor_rag_empty_retrieval_total{strategy}
arbor_rag_context_trimmed_total{reason}

arbor_llm_requests_total{operation,model,result}
arbor_llm_duration_seconds_bucket{operation,model}
arbor_llm_input_tokens_total{operation,model}
arbor_llm_output_tokens_total{operation,model}
arbor_llm_first_token_duration_seconds_bucket{model}
arbor_llm_upstream_errors_total{operation,status_class}

arbor_import_jobs_total{parser,status}
arbor_import_job_duration_seconds_bucket{parser,status}
arbor_import_jobs_in_progress
arbor_inbox_transitions_total{kind,from_status,to_status}
arbor_inbox_pending
arbor_memory_transitions_total{from_status,to_status,type}

arbor_rate_limit_rejections_total
arbor_dependency_up{dependency}
arbor_eval_metric{suite,strategy,metric_name}
```

Gauge 的采集必须有明确来源：`arbor_inbox_pending`、队列积压和依赖健康从仓储/队列连接读出；不要通过日志反推。

## 7. 日志与 trace 格式

日志输出 JSON 到 stdout，由 Grafana Alloy/Promtail 采集到 Loki：

```json
{
  "timestamp": "2026-08-29T05:10:00Z",
  "level": "INFO",
  "service": "arbor-api",
  "event": "llm.completed",
  "request_id": "01J...",
  "trace_id": "...",
  "tenant_id_hash": "sha256:...",
  "persona_id": "...",
  "thread_id": "...",
  "model": "deepseek-chat",
  "duration_ms": 824,
  "input_tokens": 3200,
  "output_tokens": 481,
  "result": "success"
}
```

Loki stream label 只使用低基数的 `service`、`environment`、`level`、`component`。其余字段始终是 JSON 内容字段。

Tempo trace 采用：

```text
HTTP POST /v1/threads/{thread_id}/messages
 ├─ auth.authorize
 ├─ rag.retrieve
 │   ├─ event_tree.route
 │   ├─ vector.search
 │   └─ rerank
 ├─ rag.compile_context
 ├─ llm.chat
 ├─ inbox.extract
 └─ postgres.persist_message
```

span attribute 只存模型、策略、数量、状态和耗时。`request_id` 是允许的 span attribute，但不是 metric label。

## 8. decision trace 与模型过程

现有对话响应已提供 `retrieval_meta`、`context_truncation_notes` 与 `injected_memory_ids`。新增 `decision_trace` 将这些安全摘要统一为可审计的解释轨迹：

```json
{
  "retrieval": {
    "strategy": "layered_tree",
    "sub_queries": [{"intent": "episode", "query_hash": "sha256:..."}],
    "candidate_count": 18,
    "selected_count": 8,
    "per_source_counts": {"profile": 2, "event_tree": 2, "vector": 4}
  },
  "context": {
    "token_budget": 12000,
    "token_estimate": 11850,
    "injected_memory_ids": ["..."],
    "truncation_notes": ["trim_vector_low_score:2"]
  },
  "reasoner": {
    "called": true,
    "operation": "extract",
    "result_kind": "conflict",
    "conflicts_with": "..."
  },
  "generation": {
    "model": "deepseek-chat",
    "latency_ms": 824,
    "input_tokens": 3200,
    "output_tokens": 481,
    "citation_ids": ["..."]
  }
}
```

这不是模型 CoT。它是可验证的系统决策：检索了什么、注入了什么、裁剪了什么、调用了什么模型、生成了什么引用。

建议新增 `decision_traces`：

```text
id, request_id, tenant_id, persona_id, thread_id, message_id,
trace_version, summary_json, created_at, expires_at,
encrypted_payload_uri NULL
```

- `summary_json` 永远只含安全摘要；
- `GET /v1/debug/requests/{request_id}` 仅 Owner/Admin + Debug 权限可访问；
- 聊天页以折叠的“处理过程”展示安全字段；
- `expires_at` 支持默认清理策略；
- Grafana 从 Loki/Tempo 使用 request ID 链接到 Debug 页面。

如未来确实需要内容级调试，必须同时满足：显式 tenant 开关、采样规则、加密对象存储、严格 RBAC、访问审计、TTL、删除支持。`reasoning_content` 不进入 Prometheus、常规 Loki 日志或 Tempo attribute。

## 9. 健康检查

| Endpoint | 语义 | 返回 |
|---|---|---|
| `GET /health` | 进程存活；不检查外部依赖 | 200 |
| `GET /ready` | 当前部署配置要求的 DB、Redis、对象存储等依赖可用 | 200 或 503 |

`/ready` 必须返回每个依赖的名称与安全状态，不返回连接串、密钥或上游响应体。LLM/embedding 默认仅检查配置和轻量连接条件，不能让每次 readiness probe 产生昂贵模型调用。

## 10. Grafana dashboard 与告警

### 10.1 Service Overview

- HTTP QPS、活跃请求、P50/P95/P99；
- 4xx/5xx、429、readiness；
- Postgres/Redis/S3/DeepSeek/embedding 依赖状态；
- 容器 CPU、内存、磁盘与 worker 重启。

### 10.2 RAG & LLM

- Chat 端到端、retrieval、context、LLM、tool 分段延迟；
- 空召回率、来源命中数、裁剪数；
- 模型上游错误、超时、重试、首 token 时延；
- 输入/输出 token 和估算成本。

### 10.3 Import & Memory Operations

- pending/running/failed 导入任务；
- parser 成功率、耗时与 chunk 数；
- Inbox pending、确认/驳回/冲突率、停留时长；
- Memory 新增、superseded、deleted 趋势。

### 10.4 Quality & Safety

- `EvalRun.metrics`：Recall@5、关键事件命中、身份一致性、RAGAS；
- `tenant_leak_count`、`persona_leak_rate`、citation subset；
- 权限拒绝和敏感操作趋势。

### 10.5 告警

| 告警 | 条件 |
|---|---|
| 服务错误 | 5xx > 1%，持续 5 分钟 |
| 对话变慢 | Chat P95 > 15 秒，持续 10 分钟 |
| 模型依赖故障 | LLM/embedding 失败率 > 2% 或连续超时 |
| 检索退化 | 空召回率相对 7 日基线上升 30% |
| 队列积压 | pending import 连续增长或等待超阈值 |
| 数据隔离 | `tenant_leak_count > 0` |
| 引用越界 | citation 超出注入集次数 > 0 |
| 依赖不可用 | readiness 或 `arbor_dependency_up` 为 0 |

## 11. 部署配置

开发环境在 `infra/compose/observability.yml` 提供 Prometheus、Grafana、Loki、Tempo 和 Alloy。生产环境使用托管等价服务也可，但必须保持指标、日志和 trace 语义不变。

建议环境变量：

```text
OBSERVABILITY_ENABLED=true
OTEL_SERVICE_NAME=arbor-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4318
PROMETHEUS_MULTIPROC_DIR=
LOG_FORMAT=json
DECISION_TRACE_RETENTION_DAYS=30
OBSERVABILITY_CAPTURE_CONTENT=false
```

`OBSERVABILITY_CAPTURE_CONTENT` 默认为 `false`，且不能单独成为保存敏感内容的充分条件；还必须具备 tenant 级明确授权和采样配置。

## 12. 实现顺序与验收

### Phase 1：关联、日志、健康

1. 实现 `RequestContext`、request ID middleware 与统一错误 ID；
2. 实现 `ObservabilityPort`、Noop/InMemory/Production adapter；
3. 覆盖 HTTP、RAG、LLM/Reasoner、导入和 Inbox 状态转换的 JSON 日志；
4. 实现 `/health`、`/ready`；
5. 单测：成功/失败 ID 一致、日志脱敏、异步任务继承 ID、readiness 状态。

### Phase 2：Prometheus 与 Grafana

1. 实现 `/metrics` 和第 6.4 节指标；
2. 增加 Compose 观测栈、数据源 provisioning、dashboard JSON、告警规则；
3. 集成测试：指标暴露、标签白名单、指标计数和依赖 down；
4. 手动验证 Grafana dashboard 可显示 API/worker 数据。

### Phase 3：Trace 与决策视图

1. 接入 OpenTelemetry FastAPI、httpx 和数据库 instrumentation；
2. 添加 RAG、Context、Reasoner、Tool 的手动 spans；
3. 迁移 `decision_traces`，实现 Admin-only Debug API；
4. 在聊天页增加“处理过程”折叠面板；
5. 配置 Grafana 从 request ID 跳转 Tempo、Loki 与 Debug 页面。

### Phase 4：受控内容采样（可选）

仅在前三阶段稳定后实现。验收包括：加密、tenant 隔离、RBAC、访问审计、TTL 清理、内容删除与无内容泄漏回归测试。

## 13. 测试要求

- 单元测试：应用层在无需 Prometheus/OTEL 的条件下验证事件和 `decision_trace`；
- API 测试：`X-Request-Id` 在成功和错误响应中一致，`/health` 与 `/ready` 契约稳定；
- 安全测试：日志、span、metrics 中不含密钥、Authorization、用户正文或 prompt；
- 基数测试：拒绝将 UUID/request ID 传入 metric labels；
- 集成测试：Prometheus scrape、Loki JSON 查询、Tempo trace 的 request ID 关联；
- 回归测试：既有 `retrieval_meta`、审计日志、`EvalRun.metrics` 和 SSE 末包语义不变。
