# 002 · 可写入简历的技术点清单

- 日期：2026-08-28
- 取代：无（001 的前置盘点，不替代 001 成稿）
- 面向：Java 后端、AI 应用开发
- 口径：数字员工工作台

本文件只列「仓库里已经落地、面试能讲清楚」的点。★ 优先写进项目条目；▲ 投 AI 岗再加重；· 口述备用，正文不必占行。

---

## 1. 架构与领域建模（Java 后端主卖点）

- ★ 六边形架构（端口-适配器）：领域在内，HTTP / Postgres / LLM / S3 在外，依赖只指向圆心
- ★ DDD 限界上下文：Identity、Persona、Memory、Event Graph、Conversation、Audit；评测为只读支持子域
- ★ 领域层零框架依赖（无 FastAPI / ORM / 供应商 SDK）；换模型或存储只改出站适配器
- ★ 应用层一用例一类（`SendMessage`、`ConfirmInboxItem`、`ImportArtifact` 等），事务边界清晰
- ★ 组合根组装依赖（`apps/api/factory.py`），Router 只做 HTTP ↔ 命令
- ★ 架构测试锁死 import 方向（对标 Java ArchUnit）
- · 值对象 ID（TenantId / PersonaId 等）；跨上下文只传 ID，不互相改聚合
- · ADR 记录关键决策（分层记忆、租户授权、检索编排 v2、评测与测试分离）
- · 领域事件总线未做（应用层同步编排）；不要写成 EventBus / CQRS 已落地

## 2. 多租户、授权、安全

- ★ 租户硬隔离：人设作用域查询必须同时带 `tenant_id + persona_id`；缺一视为缺陷
- ★ 空间三角色 owner / admin / member + 人设四权 chat / read_memory / write_memory / admin
- ★ 无 `read_memory` 的记忆不得进入模型上下文（领域服务判定，不是前端隐藏）
- ★ Postgres RLS 作为第二道隔离门；跨租户命中是 P0
- ★ 审计：改人设、导入、确认记忆、导出对话落审计表
- · 登录 / 刷新轮换 / 登出；access 刷新后旧令牌立即失效
- · 跨租户猜 UUID 返回 404，不暴露资源存在性
- · 错误码契约（403 分 FORBIDDEN_CHAT / FORBIDDEN_MEMORY_READ 等）+ 每次请求 ULID
- · 限流、CORS、可关闭演示 token、强制租户成员校验
- · 引用必须属于本线程人设；模型幻觉出的 memory id 若不在本轮注入集则丢弃

## 3. 数据与基础设施

- ★ PostgreSQL 16 + pgvector：业务与向量同库，降低双库过滤遗漏
- ★ Alembic 迁移（含 pgvector、消息附件、审计、RLS、tsvector、头像等）
- ★ 连接池：`psycopg-pool`，每请求 checkout（对标 HikariCP）
- ★ 对象存储可切换：本地盘 / Postgres `object_blobs` / S3（MinIO 或云 OSS）
- ★ Redis + ARQ 异步导入任务（`arbor-worker`）；无 Redis 时同步回退
- · 对象 GC / 孤儿 blob 清理
- · tsvector 全文检索列，供 lexical hybrid
- · ORM 止于出站适配器，领域实体与表结构双向翻译只发生在仓储

## 4. HTTP / 用例能力（可写成「后端功能面」）

- · REST `/v1` + OpenAPI 3.1，文档先于实现
- · 工作空间与成员 CRUD、人设 CRUD、授权替换
- · 会话：创建线程、分页消息、流式 SSE、附件、导出会话
- · 记忆列表 / 删除、导入任务查询、Inbox 确认/忽略/批量 bootstrap
- · 事件树与事件卡查询
- · 评测运行、冻结金标世界、审计日志
- · 人设级工具：工单登记、飞书日历查询

## 5. 检索与上下文（AI 应用主卖点）

- ★ 分层记忆：档案（结构化、不走向量）→ 工具策略 → 会话摘要 → 近期对话 → 事件树路由 → RAG 片段
- ★ 默认策略 `layered_tree`，另有 `summary_only` / `vector_only` / `layered` 做对照
- ★ 检索编排 v2：复合问拆子 query → 事件种子 + 因果/时序边 1～2 跳 → 全局 ANN 与 scoped ANN 做 RRF → lexical hybrid 再 RRF → 词级 rerank + 类型权重 + MMR
- ★ `VectorIndex.search` 签名强制租户/人设；filters 支持 `event_ids` / `types` / `exclude_ids`
- ★ `ContextPolicy` 定槽位；`ContextCompiler` 按 token 预算裁剪，超窗按低分优先删记忆
- ★ 可观测：`retrieval_meta`（hit ids、来源、分数、子 query、分源计数）与截断说明
- ▲ 不把 RAG 写成领域概念；不上 GraphRAG / 独立 TreeRAG 产品
- · 记忆生命周期：active / superseded / deleted；矛盾事实确认后旧记忆不可再检索
- · 切块 `max_chars` + overlap 可配置

## 6. 模型、抽取、工具

- ★ DeepSeek Chat 对话 + Reasoner 抽取/冲突建议；应用层只依赖 `LLMClient` / `ReasoningClient` 端口
- ★ 嵌入 bge-m3（OpenAI 兼容网关）；图/语音先转描述或转写再嵌入
- ★ Inbox：抽取结果待主管确认，冲突不静默覆盖档案
- ★ 人设 `tool_policy` 白名单；关键词触发 与 LLM `tool_calls`（`ARBOR_TOOL_MODE`）
- ▲ 飞书日历 OAuth 查日程；HTTP 工单适配器对接外部工单 API
- · 极性冲突启发式检测 + Reasoner 建议，仍经 Inbox
- · 会话滚动摘要压缩
- · 无密钥时 ScriptedLLM 可走通演示路径（面试可提「可降级」，不必当主点）

## 7. 多模态导入（数字员工知识沉淀）

- ▲ 文档：PDF / DOCX / PPTX / 纯文本；可选 Docling；`.doc` 经 LibreOffice 转换
- ▲ 语音：faster-whisper 转写进 Inbox
- ▲ 图片：视觉模型出 caption 再嵌入
- · 导入：存对象 → 入队解析 → 切 MemoryItem → 嵌入 → Inbox 或策略直写
- · 聊天附件与知识库导入走同一套解析端口

## 8. 评测与质量门禁（两类岗都加分）

- ★ 测试 ≠ 评测：pytest 钉死授权/过滤/不变式；评测比较检索策略
- ★ 测试金字塔：领域单测（无 I/O）→ 应用层 Fake 端口 → Postgres 契约测 → HTTP/OpenAPI → 架构边界
- ★ 跨租户 / 跨人设 / 无权限记忆进 prompt 为 P0，失败阻断合并
- ★ 金标绑定稳定 ID，不绑定某次 embedding 距离
- ★ 四策略对比（规模集 477 题，夹具嵌入）：`layered_tree` Recall@5 ≈ 0.92、身份一致 1.0、跨租户泄漏 0；纯向量 0.70 / 0.63
- ▲ RAGAS faithfulness 只评本轮注入文本；不评隔离、不进 PR 必跑
- · 记忆体检页是产品入口，不是隐藏脚本
- · CI：ruff / mypy（domain+ports）/ OpenAPI 校验 / pytest / `arbor-eval` suite-v1 + ragas-v1
- · Nightly：DeepSeek 生成评测 + 真 bge-m3 检索基线（与夹具表分轨）
- · 前端 Vitest + Playwright 演示路径（Java 岗一句带过）
- · Given-When-Then YAML 样例先于实现

## 9. 前端（入站适配器，Java 岗少写）

- · React + TypeScript + Vite；只调 `/v1`，不内嵌检索、不直连库
- · 三栏工作台：档案/知识库/授权 · 对话与引用 · 事件树/时间轴同源投影（React Flow）
- · Inbox、记忆体检、审计页
- · 数字员工模板：导师 / 客服 / 面试官（简历只写这三类）

## 10. 明确不要写进简历

- 虚拟角色、陪伴、消费向人设产品（统一数字员工）
- 用 Java 实现了本仓库 / 微服务 / K8s / 生产 N 万用户
- 自研 GraphRAG、自训/微调大模型、LangChain 当领域模型
- 领域事件总线、CQRS、独立图数据库（Neo4j 仅为端口可替换说明，未落地）
- 「RAGAS 证明隔离正确」；把夹具嵌入 0.92 说成线上 bge 分数
- 477 题当成大规模语料（实为约 33 条源记忆的问法扩张）

---

## 投递时怎么抽

| 岗位 | 从上面抽 |
|---|---|
| Java 后端 | §1 全 ★ + §2 隔离授权 + §3 同库向量/连接池/迁移/队列 + §8 测试金字塔与 P0 |
| AI 应用 | §5 分层检索 ★ + §6 Inbox/工具 + §7 多模态 + §8 四策略对比与 RAGAS 边界 |
| 一份简历兼顾 | 架构分层一句、租户隔离一句、layered_tree 一句、Inbox 确认一句、评测对比一句 |

下一批成稿从本清单勾选，编号 `003`。
