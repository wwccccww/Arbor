# Arbor（人格树）

多租户人设工作台：每个人设拥有独立档案、记忆与事件树。对话和多模态资料会沉淀为可导航的经历，检索始终限制在租户与人设边界内。

虚拟女友（陪伴）与数字员工是同一套内核上的两张皮肤，不是两个产品。

> 当前仓库以**架构与设计文档**为主。实现必须遵循六边形架构（端口-适配器）与 DDD 分层，领域层不得依赖框架、数据库或模型供应商。

## 它解决什么

多数 Chat 套壳把身份塞进 prompt 或纯 RAG。结果是人设会漂、记忆会串、无法解释「为什么记得」。

Arbor 把记忆分成三层，并由事件树作为叙事视图：

1. **档案**：姓名、性格、禁忌、关系——结构化，每次必带，不走向量。
2. **情景摘要**：当前会话的滚动压缩。
3. **RAG**：久远细节与导入资料——在 `tenant_id + persona_id` 过滤之后再近邻检索。

LLM 使用 DeepSeek；嵌入使用 bge-m3；向量与业务数据同库（PostgreSQL + pgvector）。

## 产品形态

三栏工作台：

- 左：人设资产（档案、关系、知识库、工具权限、成员授权）
- 中：多模态对话；回复可追溯到记忆与事件节点
- 右：关键事件树 / 时间轴（同一数据的两种视图）

另有：记忆确认收件箱、导入向导、记忆体检（召回 / 隔离 / 冲突）。

详细说明见 [docs/product-design.md](docs/product-design.md)。

## 架构原则

- **六边形**：领域在内，适配器在外；依赖只指向圆心。
- **DDD**：按限界上下文拆分（身份、人设、记忆、事件图、会话、评测）。
- **低耦合**：换 DeepSeek、换对象存储、换 Web 框架，不改领域模型。
- **硬隔离**：没有 `tenant_id + persona_id` 的检索视为缺陷，而不是优化项。

见 [docs/architecture.md](docs/architecture.md)。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + TypeScript + Vite + React Flow |
| 后端 | Python 3.12 + FastAPI（仅作为入站适配器） |
| 主库 / 向量 | PostgreSQL 16 + pgvector（`infra/compose/postgres.yml`） |
| 队列 | Redis + ARQ |
| 对象存储 | S3 兼容 |
| 对话 / 抽取 | DeepSeek `deepseek-chat` / `deepseek-reasoner` |
| 嵌入 | bge-m3 |
| 语音 / 文档 | Whisper、Docling 或 pypdf |

## 文档索引

| 文档 | 内容 |
|---|---|
| [docs/README.md](docs/README.md) | 文档导航与阅读顺序 |
| [docs/product-design.md](docs/product-design.md) | 产品形态、页面、权限、非目标 |
| [docs/architecture.md](docs/architecture.md) | 六边形架构、分层、依赖规则 |
| [docs/domain-model.md](docs/domain-model.md) | 限界上下文、聚合、领域事件 |
| [docs/data-model.md](docs/data-model.md) | 表结构与检索约束 |
| [docs/api.md](docs/api.md) | 接口说明（人类可读） |
| [docs/openapi.yaml](docs/openapi.yaml) | OpenAPI 3.1 |
| [docs/testing.md](docs/testing.md) | 单元 / 契约 / API / 架构测试与 CI |
| [docs/testing-examples.md](docs/testing-examples.md) | 如何先写测试样例（YAML） |
| [docs/evaluation.md](docs/evaluation.md) | 评测怎么办：体检页、金标、门槛、工作流 |
| [docs/ragas.md](docs/ragas.md) | RAGAS 打分契约 + 评估集生成 |
| [docs/adr](docs/adr) | 架构决策记录 |

## 目标目录（实现时）

```text
apps/web                     # 入站适配器：工作台 UI
apps/api                     # 组合根 + FastAPI
src/arbor/domain             # 领域模型（零基础设施依赖）
src/arbor/application        # 用例编排
src/arbor/ports              # 入站 / 出站端口（接口）
src/arbor/adapters           # FastAPI、Postgres、DeepSeek、bge、S3…
tests/                       # 单测、契约测、API、架构边界
eval/                        # suite-v1 金标、arbor-eval runner、四策略基线
infra/compose                # Postgres + Redis
docs/
```

领域层禁止出现：FastAPI、SQLAlchemy、httpx、DeepSeek SDK、React。

## 许可

尚未指定许可证。
