# Arbor（人格树）

多租户人设工作台：每个人设拥有独立档案、记忆与事件树。对话和多模态资料会沉淀为可导航的经历，检索始终限制在租户与人设边界内。

虚拟女友（陪伴）与数字员工是同一套内核上的两张皮肤，不是两个产品。

## 当前实现状态（2026-08）

| 模块 | 状态 |
|---|---|
| 工作台 UI（三栏、体检、审计） | 已实现 |
| 分层记忆 + 事件树 + Inbox | 已实现 |
| Postgres + pgvector 持久化 | 已实现（核心表、会话、向量） |
| 上传 / 聊天附件 | `local` 本地盘 / `postgres` 表 / `s3`（MinIO 或云 OSS） |
| 登录会话 | 演示 token + Postgres `auth_sessions` 表 |
| 导入任务 / 评测运行 | Postgres 表 + 内存回退 |
| 人设创建模板 | 伴侣 / 导师 / 客服 / 面试官 |
| 首页头像 + 聊天导入初稿 | 头像字段；首页独立导入 + Inbox bootstrap |
| 人设轻量体检 API | `POST /v1/personas/{id}/eval/runs` |
| tool_policy 注入 prompt | `ContextPolicy` 槽位 |
| tool_policy 注入 + 执行 | 关键词触发 + LLM `tool_calls`（`ARBOR_TOOL_MODE`） |
| 飞书日历 | OAuth + 查日程；工作台可连接飞书 |
| 工单 HTTP | `ARBOR_TICKET_API_URL` 登记真实工单 |
| Postgres 连接池 | `psycopg-pool` + 每请求 checkout |
| HTTP 评测路由拆分 | `adapters/inbound/http/register_eval.py` |
| 体检冻结世界 API | `POST /v1/eval/seed-world` + 体检页按钮 |
| 导入 reasoner 抽取 | 有 DeepSeek 时走 reasoner，否则原文进 Inbox |
| Redis ARQ（导入异步） | 已实现；`REDIS_URL` + `arbor-worker` |
| 多模态文档 | pypdf/docx/pptx；可选 Docling；`.doc` 经 LibreOffice 转换 |

实现遵循六边形架构（端口-适配器）与 DDD 分层；组合根在 `apps/api/factory.py`，领域层不依赖框架与供应商 SDK。

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
| 队列 | Redis + ARQ（导入任务；可选 `infra/compose/redis.yml` + `arbor-worker`） |
| 对象存储 | 本地盘 / Postgres `object_blobs` / S3（MinIO） |
| 对话 / 抽取 | DeepSeek `deepseek-chat` / `deepseek-reasoner` |
| 嵌入 | bge-m3 |
| 语音 / 文档 | Whisper、Docling 或 pypdf |

## 本地运行

真实对话请填 `.env` 里的 `DEEPSEEK_API_KEY`，然后一条命令启动（页面和 API 都在 8000 端口）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run.ps1
```

```bash
./scripts/run.sh
```

打开 http://127.0.0.1:8000 。首页黄条需同时有「DeepSeek 对话已接通」和「嵌入 bge-m3」才是真实对话 + 真实检索。嵌入密钥见 `.env.example` 的 `EMBEDDING_API_KEY`。

持久化（推荐）：在 `.env` 启用 `DATABASE_URL` 并启动 Postgres：

```bash
docker compose -f infra/compose/postgres.yml up -d
```

上传与附件默认写入仓库根目录下的 `.arbor-data/`（可用 `ARBOR_DATA_DIR` 覆盖）。细节见 [docs/local-dev.md](docs/local-dev.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [docs/README.md](docs/README.md) | 文档导航与阅读顺序 |
| [docs/local-dev.md](docs/local-dev.md) | 本地安装、启动、演示身份 |
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
apps/api                     # 组合根（factory.py）+ FastAPI 入口
src/arbor/domain             # 领域模型（零基础设施依赖）
src/arbor/application        # 用例编排（含 evaluation、storage/object_gc）
src/arbor/ports              # 入站薄 Protocol + 出站端口
src/arbor/adapters/inbound/http  # register_* HTTP 路由
src/arbor/adapters           # Postgres、DeepSeek、bge、S3、multimodal…
tests/                       # 单测、契约测、API、架构边界
eval/                        # suite-v1 金标、arbor-eval runner、四策略基线
infra/compose                # Postgres + Redis
docs/
```

领域层禁止出现：FastAPI、SQLAlchemy、httpx、DeepSeek SDK、React。

## 许可

MIT License — 见 [LICENSE](LICENSE)。
