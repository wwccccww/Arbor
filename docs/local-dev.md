# 本地运行

在浏览器里体验当前工作台（首页、三栏工作台、体检、审计），需要同时启动 API 与前端开发服务器。

## 前置条件

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | 3.11+ | FastAPI 入站适配器 |
| Node.js | 18+ | Vite + React 工作台 |

**演示最小集不需要：**

- PostgreSQL / Redis — 默认内存库，启动时自动 seed 演示世界（林夏、小周等）
- 登录 — 前端写死演示令牌，无登录页
- `DEEPSEEK_API_KEY` — 未配置时使用内置 ScriptedLLM / ScriptedReasoner

## 安装

在仓库根目录：

```bash
pip install -e ".[api]" uvicorn
```

前端依赖：

```bash
cd apps/web
npm install
```

## 启动

需要两个终端，均从仓库根目录开始。

**终端 1 — API（端口 8000）**

```bash
python3 -m uvicorn apps.api.main:create_app_from_env --factory --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即表示 API 就绪。

**终端 2 — 前端（端口 5173）**

```bash
cd apps/web
npm run dev
```

浏览器打开 **http://localhost:5173**。

开发模式下 Vite 将 `/v1` 代理到 `http://127.0.0.1:8000`（见 `apps/web/vite.config.ts`），无需额外配置 CORS。

## 演示身份

前端默认使用 owner 身份，无需手动填写 Header：

| 项 | 值 |
|---|---|
| Bearer 令牌 | `token-a` |
| 租户 ID | `0a000000-0000-4000-a000-000000000001`（演示租户 A） |
| 用户邮箱 | `demo-a@arbor.eval`（首页通过 `GET /v1/me` 显示） |

后端还内置 `token-member`（仅 CHAT 权限），但前端目前没有切换令牌的 UI。

常用演示人设：

| 名称 | ID |
|---|---|
| 林夏 | `0a000000-0000-4000-a000-000000000010` |
| 客服小周 | `0a000000-0000-4000-a000-000000000011` |

首页点击人设名称进入工作台；也可直接访问 `#/personas/0a000000-0000-4000-a000-000000000010`。

## 页面路由

| 地址 | 页面 |
|---|---|
| `#/` | 首页：空间、人设列表、成员、体检/审计入口 |
| `#/personas/:id` | 三栏工作台 |
| `#/checkup` | 记忆体检（检索评测） |
| `#/audit` | 审计日志 |

## 可选环境变量

```bash
# 真实 DeepSeek 对话与抽取（否则为脚本回复）
export DEEPSEEK_API_KEY=sk-...

# 持久化到 Postgres（需先 docker compose up postgres）
export DATABASE_URL=postgresql://...
```

Postgres 本地栈见 `infra/compose/postgres.yml`：

```bash
docker compose -f infra/compose/postgres.yml up -d
```

演示环境以 in-memory 为主；`DATABASE_URL` 主要用于契约测与持久化验证，日常看 UI 不必配置。

## 验证

```bash
# 前端单测（56 项）
cd apps/web && npm test

# 后端 API 测
pytest tests/api -q
```

快速检查 API 是否存活：

```bash
curl -s http://127.0.0.1:8000/v1/me \
  -H "Authorization: Bearer token-a" \
  -H "X-Tenant-Id: 0a000000-0000-4000-a000-000000000001"
```

应返回 `demo-a@arbor.eval` 与租户列表。

## 常见问题

| 现象 | 处理 |
|---|---|
| 首页空白或网络错误 | 确认 API 终端仍在 8000 端口运行 |
| `ModuleNotFoundError: fastapi` | 执行 `pip install -e ".[api]" uvicorn` |
| `uvicorn: command not found` | 使用 `python3 -m uvicorn ...` |
| 对话回复很「模板化」 | 未设置 `DEEPSEEK_API_KEY` 时为预期行为 |
| 端口被占用 | 换端口时需同时改 API 启动参数与 `vite.config.ts` 中的 proxy 目标 |

## 相关文档

- [HTTP 接口](api.md) — 路径与错误码
- [测试与质量](testing.md) — pytest 分层与 CI
- [apps/web/README.md](../apps/web/README.md) — 前端入站适配器说明
