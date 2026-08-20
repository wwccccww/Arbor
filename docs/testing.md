# 测试与质量保障

本文覆盖单元测试、契约测试、API 测试、架构测试、CI 门禁，以及与 [评测设计](evaluation.md) 的分工。实现代码时按此目录与用例清单落地，而不是事后补测。

**评测 ≠ 测试。**  
测试保证规则与隔离在每次提交仍然成立；评测比较记忆策略好不好。CI 默认跑测试 + 无 LLM 的隔离/Recall 夹具；带 DeepSeek 的生成评测不进 PR 必跑。

## 1. 原则

1. **测端口以内的规则，不测供应商。** 领域与应用层用 Fake 端口；Postgres/pgvector 用契约测；DeepSeek 默认不进 CI。
2. **隔离是断言，不是示例。** 跨租户命中、跨人设命中、无权限记忆进 prompt，任一失败即红。
3. **替身实现端口，不 mock 领域对象。** 禁止 `MagicMock(Persona)` 来绕开不变式。
4. **测试走与生产相同的用例入口。** 应用层测试调用 `SendMessage` 等，不直接调仓储绕过授权。
5. **金标绑定 ID。** 不绑定某次 embedding 的绝对距离。

## 2. 金字塔与分层

```text
        ┌─────────────┐
        │  评测金标    │  策略对比，可夜间跑 LLM
        └──────▲──────┘
        ┌──────┴──────┐
        │  API / 前端  │  OpenAPI、错误码、关键页面
        └──────▲──────┘
        ┌──────┴──────┐
        │ 适配器契约   │  真实 Postgres + pgvector
        └──────▲──────┘
        ┌──────┴──────┐
        │ 应用层用例   │  Fake 仓储 / Fake LLM / 内存向量
        └──────▲──────┘
        ┌──────┴──────┐
        │ 领域单测     │  无 I/O，最快、最多
        └─────────────┘
        ┌─────────────┐
        │ 架构测试     │  import 方向，与金字塔正交
        └─────────────┘
```

| 层 | 工具 | I/O | CI |
|---|---|---|---|
| 领域 | pytest | 无 | 必跑 |
| 应用 | pytest + fakes | 无 | 必跑 |
| 架构边界 | import-linter / 自定义 AST | 无 | 必跑 |
| 出站契约 | pytest + testcontainers/compose | Postgres | 必跑 |
| HTTP | pytest + httpx ASGI | 测试库 | 必跑 |
| 前端 | vitest + Testing Library | 无 | 必跑（有 UI 之后） |
| eval 隔离/Recall | eval runner + 夹具向量 | Postgres 或内存索引 | 必跑 |
| eval 生成质量 | DeepSeek | 外网 | 夜间 / 手动，PR 不强制 |

## 3. 目录（实现时）

```text
tests/
  examples/                      # Given-When-Then 样例（先于 pytest）
  fixtures/mini-world.yaml       # 契约/应用最小世界
  conftest.py
  fakes/                         # 出站端口的内存实现，供应用层单测
    repositories.py
    llm.py
    embedding.py
    vector_index.py
    storage.py
    clock.py
  unit/
    domain/
      test_authorization.py
      test_memory_supersede.py
      test_event_edge_isolation.py
      test_thread_persona_binding.py
      test_context_policy.py
    application/
      test_send_message.py
      test_confirm_inbox.py
      test_reasoner_parse.py
      test_persona_threads.py
      test_import_artifact.py
      test_get_event_tree.py
  architecture/
    test_import_rules.py         # 或 import-linter 配置
  contract/
    postgres/
      test_memory_tenant_filter.py
      test_vector_search_isolation.py
      test_event_edge_check.py
      test_thread_messages.py
  api/
    test_auth.py
    test_persona_grants.py
    test_chat_citations.py
    test_forbidden_codes.py
    test_inbox.py
    test_event_tree.py
    test_personas_threads.py
    test_imports.py
    test_openapi_smoke.py
apps/web/src/**/*.test.ts(x)
eval/
  fixtures/suite-v1/
  runner.py                      # 入站 CLI，转发 arbor-eval；只跑检索，不调 DeepSeek
```

生产代码 **不得** import `tests.*`。Fake 若被演示模式复用，再提升为 `src/arbor/adapters/outbound/inmemory/`。

## 4. 测试替身

| 端口 | Fake 行为 |
|---|---|
| `*Repository` | dict 存储，按 tenant/persona 过滤 |
| `VectorIndex` | 余弦/欧氏于内存向量，**仍强制 tenant+persona** |
| `LLMClient` | 返回脚本化文本；可记录收到的 prompt 供断言 |
| `ReasoningClient` | 返回固定 JSON 抽取结果 |
| `EmbeddingClient` | 对夹具文本返回预计算向量，未知文本返回零向量并失败（避免假绿） |
| `ObjectStorage` | 本地临时目录 |
| `JobQueue` | 同步立即执行 |
| `Clock` | 固定时间 |
| `FaithfulnessScorer` | 测试里返回固定 1.0 或跳过；禁止在 unit 测试调真 RAGAS |

`LLMClient` Fake 必须把「注入的 memory_ids」记录下来，供「无 read_memory 不得出现禁忌」断言使用。这是应用层测试的核心探针，比检查回复文案重要。

## 5. 必须存在的用例（P0 清单）

实现对应代码时，下列名字应能在 pytest 里找到。缺一项视为文档未落地。  
可加载样例见 [testing-examples.md](testing-examples.md) 与 `tests/examples/*.yaml`。

### 5.1 领域

| 测试 | 断言 |
|---|---|
| 人设不能改 `tenant_id` | 抛领域异常 |
| 无 `chat` 不能追加消息 | 拒绝 |
| 无 `read_memory` 的 ContextPolicy 不含禁忌/关系 | 槽位只有最小 Profile |
| Thread 不能换 Persona | 拒绝 |
| Citation 引用其他人设 MemoryId | 拒绝 |
| 确认冲突 fact 后旧 fact 为 `superseded` | status 变更 |
| 未确认不得改 Profile | Inbox 外无副作用 |
| EventEdge 跨 persona | 拒绝 |
| Tenant 至少一名 owner | 删光 owner 失败 |

### 5.2 应用层（Fake 端口）

| 测试 | 断言 |
|---|---|
| `SendMessage` 组装顺序 | prompt 槽位：档案 → 摘要 → 事件 → 向量命中 |
| 无 `read_memory` 仍可 chat | LLM 入参无 MemoryItem 正文 |
| 模型返回未注入的 memory_id | citations 丢弃 |
| 抽取结果进 Inbox 不直写 Memory | 仓储无新 active item |
| `ConfirmInboxItem` 后可检索 | 内存 VectorIndex 命中 |
| 导入无 `write_memory` | 失败，对象存储不留文件（或事务回滚） |
| 两个 Persona 的 Fake 向量互不命中 | 即使用相同向量 |

### 5.3 适配器契约（真实 Postgres）

| 测试 | 断言 |
|---|---|
| 写入租户 A 的记忆，用租户 B 搜相同向量 | 0 行 |
| `status=superseded` 不出现在 search | 0 行 |
| 缺 `tenant_id` 调用仓储/向量方法 | 类型/校验错误，禁止有重载 |
| 跨人设插入 event_edge | DB 或仓储失败 |
| 删除 MemoryItem 后 ANN 不命中 | 0 行 |

### 5.4 HTTP

| 测试 | 断言 |
|---|---|
| 无 Bearer | 401 `UNAUTHENTICATED` |
| Member 无人设 grant 访问记忆 | 404 或 403，不泄露存在性（与 api.md 一致） |
| `PUT grants` 后原 chat 用户 403 | 收权生效 |
| 对话响应 citations ⊆ 实际注入 id | |
| `X-Tenant-Id` 与资源不符 | 404 |
| OpenAPI 里的错误体含 `code` | |
| 抽取进 Inbox，确认后待办清空 | HTTP `inbox_created` + confirm |
| 无 `write_memory` 看 Inbox | 404 或 403，不泄露存在性 |
| 事件树不串人设 | 林夏树不含小周节点 |
| 无 `read_memory` 看事件树 | 404 或 403，不泄露存在性 |
| 确认并 `mark_key_event` | 树上多一个关键节点 |
| 事件卡需要 `read_memory` | 无权限或跨租户 404 |
| Owner 列出人设、Member 仅已授权 | 列表不串无权的人设 |
| 无 `read_memory` 看人设 | 最小档案，无禁忌 |
| 创建会话后能拉历史 | POST thread → POST message → GET messages |
| 导入需要 `write_memory` | 无权限 404/403；成功后能查 job |

### 5.5 架构

| 测试 | 断言 |
|---|---|
| `domain` 不 import `adapters` / `fastapi` / `sqlalchemy` | |
| `application` 不 import `adapters` | |
| `adapters.outbound.deepseek` 不 import `postgres` | |
| `VectorIndex.search` 签名含 `tenant_id` 与 `persona_id` | 反射检查端口 Protocol |

### 5.6 评测夹具（无 LLM 也可跑）

见 [evaluation.md](evaluation.md) 与 [ragas.md](ragas.md)。CI 至少跑：跨租户 0 命中、人设泄漏、档案题不依赖向量。RAGAS faithfulness 仅夜间 generation，且不得代替隔离测试。

## 6. 与评测的分工

| | 测试 | 评测 |
|---|---|---|
| 问题 | 「规则有没有被改坏」 | 「这种检索策略好不好」 |
| 数据 | 最小夹具、针对不变式 | 版本化金标世界 suite-v1 |
| 失败 | 红线，阻断合并 | 对比表，默认策略有门槛（租户泄漏=0） |
| LLM | Fake | 可选真实 DeepSeek |

不要用 RAGAS 分数代替 `test_vector_search_isolation`。RAGAS 只允许出现在评测 generation 适配器里，见 [ragas.md](ragas.md)。也不要在单元测试里扫整份金标题（慢、不稳）。

## 7. 前端测试（有 UI 之后）

只测适配器行为，不在浏览器里测检索：

- 无 `read_memory` 时左栏不展示禁忌、树为空态
- 回复区能渲染 citations 并跳到节点
- Inbox 确认/忽略会调对应 API
- 三栏在窄屏不丢右栏入口（可改为抽屉）

E2E（Playwright）只保留 1 条烟雾：登录 → 打开人设 → 发一句 → 看到回复。记忆正确性不靠 E2E。

## 8. CI 门禁

PR 流水线建议分 job，失败信息要对分层：

```text
lint          ruff + mypy + import-linter
unit          tests/unit + tests/architecture
contract      Postgres service + DATABASE_URL → tests/contract/postgres
api           无库时内存组合根；有 DATABASE_URL 时 create_app_from_env 连真库。有 DEEPSEEK_API_KEY 时走 DeepSeek Chat/Reasoner，单测 create_app() 仍用 ScriptedLLM / ScriptedReasoner。
eval-fixture  suite-v1 / ragas-v1 检索（CI 在 pgvector 上跑，泄漏必须为 0）
eval-nightly  pytest -m llm：suite-v1 generation（需 DEEPSEEK_API_KEY）
web           vitest（有前端时）
```

合并条件：上述全绿。  
`tenant_leak_count` 在 eval-fixture 中必须为 0。

覆盖率：领域 + 应用层行覆盖建议 ≥ 80%。适配器不追求数字，靠契约清单。不要为覆盖率测 DeepSeek SDK。

## 9. 静态质量（「之类」里一并做）

| 工具 | 用途 |
|---|---|
| ruff | 格式与 lint |
| mypy | 端口 Protocol 与 ID 类型 |
| import-linter | 依赖方向，见 [architecture.md](architecture.md) §8 |
| pip-audit / npm audit | 依赖（可夜间） |
| OpenAPI 校验 | CI 解析 `docs/openapi.yaml` |

密钥：`.env` 不入库；契约测用本地 Postgres，不用生产 DeepSeek key。

## 10. 明确不测 / 不进 PR

- 真实 DeepSeek 的文风、情商、陪伴「好不好听」
- GraphRAG 论文指标
- 性能压测（有基线后再加，延迟在评测里拆开记即可）
- 截图回归、视觉对比
- 用 mock 掉 `AuthorizationPolicy` 再测聊天（等于没测授权）

## 11. 实现顺序（与测试同步）

1. 领域实体 + 第 5.1 节单测（无数据库）
2. 端口 Protocol + Fake + 第 5.2 节
3. Postgres 适配器 + 第 5.3 节
4. FastAPI 组合根 + 第 5.4 节
5. eval runner + suite-v1 隔离
6. 前端与 vitest

先有红测再写实现。隔离测试必须先于「能聊起来」。

## 12. 失败怎么归因

| 红的是 | 先看 |
|---|---|
| `tests/unit/domain` | 不变式被改 |
| `tests/unit/application` | 用例编排/拼上下文 |
| `tests/architecture` | 有人从领域 import 了框架 |
| `tests/contract` | SQL/索引/过滤漏了 |
| `tests/api` | HTTP 翻译或漏鉴权 |
| eval-fixture 泄漏 | 检索策略或过滤，P0 |
| eval 夜间生成分下降 | 提示词或模型，不回滚隔离测试 |

领域测试失败时禁止用「调大模型就好了」作为修复。
