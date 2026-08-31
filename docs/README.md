# Arbor 文档

按下面顺序阅读，可以从产品形态走到接口契约。

## 本地运行

要在浏览器里看到工作台效果，见 [本地运行](local-dev.md)（安装、**一条命令**启动 API+前端于 8000、演示身份与常见问题）。

## 阅读顺序

1. [产品设计](product-design.md) — 工作台形态、人设、事件树、权限、非目标
2. [架构](architecture.md) — 六边形、端口-适配器、依赖方向、目录
3. [领域模型](domain-model.md) — 限界上下文、聚合、不变式、领域事件
4. [数据模型](data-model.md) — PostgreSQL / pgvector 表与过滤约束
5. [HTTP 接口](api.md) 与 [OpenAPI](openapi.yaml)
6. [测试与质量](testing.md) — 金字塔、P0 清单、Fake 端口、CI 门禁
7. [测试样例](testing-examples.md) — Given-When-Then YAML，先于 pytest
8. [评测](evaluation.md) — 怎么办：体检页、suite-v1 金标、门槛与工作流
9. [五分钟演示脚本](demo-script.md) — 导入 → Inbox → 传记 → 引用 → 体检
10. [Nightly / Weekly CI](nightly-ci.md) — 仓库 Secrets 与 bge 基线
11. [RAGAS](ragas.md) — 仅评本轮注入文本上的生成忠实度
12. [可观测性](observability.md) — 指标、日志、Trace、决策轨迹与 Grafana 实现契约
13. [AI Agent 改造开发指南](ai-agent-development-guide.md) — Runtime、上下文、RAG、记忆、多模态、数字员工与评测路线
14. [Agent 生产化补强开发指南](agent-production-hardening-guide.md) — 真实 Planner、公平消融、持久化、契约、观测与可直接使用的编码提示词
15. [ADR](adr) — 已冻结的技术决策（含 [0009 检索编排 v2](adr/0009-retrieval-orchestrator-v2.md)）
16. [简历材料](resume) — Arbor 项目口径，按 `001` 起递增
17. [求职交付 · Sail](job/sail) — AI Agent 应用岗；主投简历为 [005](job/sail/005/005-改后简历.html)，另有 [003 扫读](job/sail/003/003-改后简历.html) / [004 完整](job/sail/004/004-改后简历.html)

## 文档与代码的关系

文档是实现的边界，不是实现完成后的附录。

- 新增用例：先补应用层用例名与端口，再写适配器。
- 新增外部系统：只允许新增出站适配器，禁止改领域实体去迁就 SDK。
- 新增 HTTP 路径：先改 `openapi.yaml` 与 `api.md`，再实现入站适配器。
- 检索相关改动：必须能在评测集上对比 Recall、泄漏率、跨租户命中（目标为 0）。
- 新增领域规则或端口：先在 `tests/examples/` 补一条 Given-When-Then，再写实现。

## 词汇

| 术语 | 含义 |
|---|---|
| Tenant | 工作空间，多租户硬边界 |
| Persona | 数字人 / 人设，会话与记忆的归属 |
| Thread | 一次对话，绑定且仅绑定一个 Persona |
| MemoryItem | 统一记忆项（事实、摘要、切片、描述、转写） |
| EventNode | 事件树上的节点 |
| Port | 领域/应用向外提出的接口 |
| Adapter | 端口的具体实现（HTTP、Postgres、DeepSeek…） |
| Inbox | 抽取结果待人工确认的收件箱 |
