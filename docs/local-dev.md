# 本地运行

推荐用**一条命令**同时拉起 API 和工作台，浏览器打开 **http://127.0.0.1:8000**。不要只开前端（`localhost:5173`），否则会出现 **Bad Gateway**。

## 真实可用（推荐）

前置：Python 3.11+、Node.js 18+。Windows 用 `python`；macOS/Linux 用 `python3`。

1. 到 [DeepSeek 开放平台](https://platform.deepseek.com) 创建 API Key。
2. 仓库根目录复制环境文件并填入密钥（不要提交 `.env`）：

```powershell
copy .env.example .env
notepad .env
```

```bash
cp .env.example .env
```

`.env` 中至少：

```text
DEEPSEEK_API_KEY=sk-你的密钥
```

3. **一条命令启动**（构建前端后，由 API 在 8000 端口一起提供页面和 `/v1`）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run.ps1
```

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

4. 浏览器打开 **http://127.0.0.1:8000**。

首页黄条应显示 **「DeepSeek 对话已接通」**。点开林夏即可真实对话、导入资料、确认记忆。未填密钥时黄条为「脚本回复」，页面仍能点，但对话不是模型生成的。

关掉这个窗口即停止服务。默认用内存库，关进程后数据丢失。要持久化，先起 Postgres，再在 `.env` 取消注释 `DATABASE_URL`：

```powershell
docker compose -f infra/compose/postgres.yml up -d
```

然后重新运行 `scripts/run.ps1`。

## 前置条件

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | 3.11+ | FastAPI 入站适配器 |
| Node.js | 18+ | 构建工作台 |

**演示最小集不需要：** PostgreSQL、登录页。嵌入仍为内置 `fixture_embed`（无独立 embedding API），不影响对话与工作台操作。

## 开发模式（两个终端）

改前端时可用 Vite 热更新。Windows PowerShell 5.x **不支持** `&&`，请分行执行。

两个终端都从仓库根目录开始。

**终端 1 — API（端口 8000）**

```bash
python -m pip install -e ".[api]"
python -m uvicorn apps.api.main:create_app_from_env --factory --port 8000
```

```powershell
python -m pip install -e ".[api]"
python -m uvicorn apps.api.main:create_app_from_env --factory --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即表示 API 就绪。

**终端 2 — 前端（端口 5173）**

```bash
cd apps/web
npm install
npm run dev
```

```powershell
cd apps/web
npm install
npm run dev
```

浏览器打开 **http://localhost:5173**。Vite 将 `/v1` 代理到 `http://127.0.0.1:8000`。

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

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
$env:DATABASE_URL = "postgresql://..."
```

Postgres 本地栈见 `infra/compose/postgres.yml`：

```bash
docker compose -f infra/compose/postgres.yml up -d
```

```powershell
docker compose -f infra/compose/postgres.yml up -d
```

演示环境以 in-memory 为主；`DATABASE_URL` 主要用于契约测与持久化验证，日常看 UI 不必配置。

## 验证

```bash
cd apps/web
npm test

pytest tests/api -q
```

```powershell
cd apps/web
npm test

cd ../..
pytest tests/api -q
```

快速检查 API 是否存活：

```bash
curl -s http://127.0.0.1:8000/v1/me \
  -H "Authorization: Bearer token-a" \
  -H "X-Tenant-Id: 0a000000-0000-4000-a000-000000000001"
```

```powershell
curl.exe -s http://127.0.0.1:8000/v1/me `
  -H "Authorization: Bearer token-a" `
  -H "X-Tenant-Id: 0a000000-0000-4000-a000-000000000001"
```

应返回 `demo-a@arbor.eval` 与租户列表。

## 常见问题

| 现象 | 处理 |
|---|---|
| `标记“&&”不是此版本中的有效语句分隔符` | Windows PowerShell 5.x 不支持 `&&`。改成分行执行，或用 `;`（例如 `cd apps/web; npm install; npm run dev`） |
| 首页空白或网络错误 | 确认 API 终端仍在 8000 端口运行 |
| `ModuleNotFoundError: fastapi` | 执行 `pip install -e ".[api]" uvicorn` |
| `uvicorn: command not found` | 使用 `python -m uvicorn ...` |
| `python3` 找不到 | Windows 上改用 `python` |
| 首页 **Bad Gateway** | 只开了 5173、没开 8000。改用 `scripts/run.ps1` 打开 **http://127.0.0.1:8000**，或把 API 终端拉起来再刷新 |
| `run.ps1` 报「意外的标记」或中文乱码 | 旧脚本编码不兼容 PowerShell 5。`git pull` 后再跑；脚本已改为 UTF-8 BOM |
| 对话回复很「模板化」 | 未设置 `DEEPSEEK_API_KEY` 时为预期行为 |
| 端口被占用 | 换端口时需同时改 API 启动参数与 `vite.config.ts` 中的 proxy 目标 |

## 相关文档

- [HTTP 接口](api.md) — 路径与错误码
- [测试与质量](testing.md) — pytest 分层与 CI
- [apps/web/README.md](../apps/web/README.md) — 前端入站适配器说明
