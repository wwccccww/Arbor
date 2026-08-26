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

首页黄条要同时满足才算「真实性能」：

- **DeepSeek 对话已接通** — `.env` 的 `DEEPSEEK_API_KEY`
- **嵌入 bge-m3** — `.env` 的 `EMBEDDING_API_KEY`（推荐 [SiliconFlow](https://cloud.siliconflow.cn)，默认模型 `BAAI/bge-m3`）
- 可选 **Postgres 持久化** — 取消注释 `DATABASE_URL` 并先起 docker compose

只填 DeepSeek、不填嵌入密钥时，对话是真的，但检索仍是 64 维哈希，记不住语义相近的话。

未填密钥时黄条为「脚本回复」/「哈希夹具」，页面仍能点，但不是真实模型。

关掉这个窗口即停止服务。默认用内存库，关进程后数据丢失。要持久化，先起 Postgres，再在 `.env` 取消注释 `DATABASE_URL`：

```powershell
docker compose -f infra/compose/postgres.yml up -d
```

然后重新运行 `scripts/run.ps1`。

## 导入异步队列（Redis + ARQ，可选）

默认不设 `REDIS_URL` 时，导入在 API 进程内**同步**完成（`POST` 返回 `status: completed`）。大文件或希望 API 快速返回时，可启用真异步：

1. 启动 Redis：

```bash
docker compose -f infra/compose/redis.yml up -d
```

2. `.env` 中配置：

```text
REDIS_URL=redis://127.0.0.1:6379/0
```

3. 安装 worker 依赖并**另开终端**跑 worker：

```bash
python3 -m pip install -e ".[api,postgres,worker]"
arbor-worker
```

4. 启动 API（`scripts/run.sh` 或 uvicorn）。`GET /v1/me` 的 `runtime.job_queue` 应为 `redis`。

此时 `POST /imports` 返回 `status: pending`；工作台会轮询 `GET /v1/imports/{job_id}` 直到 `completed` 或 `failed`。解析仍只进 Inbox，不直写记忆。

显式强制同步（即使配了 Redis）：`ARBOR_JOB_QUEUE=sync`。

## 多模态解析（文档 / 语音 / 图片，可选）

导入与聊天附件（在具备 `write_memory` 时）会经 `MediaToInbox` 解析为待确认 Inbox，**不直写 Memory**。纯文本 `.txt` 导入在有 DeepSeek reasoner 时仍走「抽取事实」短路；PDF/DOCX/PPTX、图片、音频走多模态适配器。

安装可选依赖：

```bash
python3 -m pip install -e ".[api,documents,speech,worker]"
```

| 类型 | 扩展名示例 | Inbox `memory_type` | 依赖 |
|---|---|---|---|
| 纯文本 / Markdown | `.txt` `.md` | `file_chunk`（或 reasoner 抽取 `fact`） | 内置 |
| 文档 | `.pdf` `.docx` `.pptx` | `file_chunk` | `documents`（pypdf、python-docx、python-pptx） |
| 图片 | `.png` `.jpg` `.webp` | `image_caption` | `DEEPSEEK_API_KEY`（视觉描述 API） |
| 音频 | `.mp3` `.wav` `.m4a` | `transcript` | `speech`（faster-whisper） |

未装对应依赖时，适配器会降级为 stub（空块或占位），任务仍可能 `completed` 但 `chunks_parsed=0`。工作台导入面板会显示 `parser` 与块数（`GET /v1/imports/{job_id}`）。

聊天里带附件且有人设 `write_memory` 时，附件同样解析进 Inbox（不走 reasoner 抽取，保留 `file_chunk` / `transcript` / `image_caption`）。助手回复仍用用户文字；若配置了视觉描述，检索上下文会附带图片摘要（`vision_enrich`）。

Redis 异步导入时，**worker 进程也需安装相同 extras**（`arbor-worker` 与 API 同一套 `pip install`）。

## 对象存储（上传与聊天附件）

导入文件、聊天附件不进 Postgres 业务表，由 `ObjectStorage` 出站端口保存。通过 `.env` 的 `ARBOR_OBJECT_STORE` 选择后端（详见 `.env.example`）：

| 值 | 存哪 | 何时用 |
|---|---|---|
| `local`（默认） | `ARBOR_DATA_DIR/objects`（默认仓库下 `.arbor-data`） | 本机开发、单机部署 |
| `postgres` | 表 `object_blobs` | 希望附件和库一起备份、不单独管目录 |
| `s3` | S3 兼容桶（MinIO / 云 OSS） | 多实例 API、生产对象存储 |

`GET /v1/me` 的 `runtime.object_store` 会显示当前后端：`local` / `postgres` / `s3`。

### 本地 MinIO（免费 S3 兼容，可选）

MinIO 是开源对象存储，API 与 AWS S3 兼容。仓库提供 Docker 配置，**不需要云账号、不需要付费**，只在本机跑容器。

1. 启动 MinIO（会创建 bucket `arbor`）：

```bash
docker compose -f infra/compose/minio.yml up -d
```

控制台（可选）：http://127.0.0.1:9001 ，账号 `arbor` / 密码 `arbor-secret`。

2. 安装 S3 依赖（`boto3`）：

```bash
python3 -m pip install -e ".[api,postgres,s3]"
```

3. 在 `.env` 中配置（与 `infra/compose/minio.yml` 默认账号一致）：

```text
ARBOR_OBJECT_STORE=s3
ARBOR_S3_ENDPOINT=http://127.0.0.1:9000
ARBOR_S3_BUCKET=arbor
ARBOR_S3_ACCESS_KEY=arbor
ARBOR_S3_SECRET_KEY=arbor-secret
ARBOR_S3_PREFIX=arbor/
```

4. 若使用 Postgres 持久化，仍建议保留 `DATABASE_URL`；对象存储与数据库是两套：库管结构化数据，MinIO 管文件字节。

5. 重新运行 `./scripts/run.sh`，确认 `runtime.object_store` 为 `s3`。

不用 MinIO 时保持默认即可，无需改 `ARBOR_OBJECT_STORE`。

**镜像拉取失败**（`not found`）：`minio/minio` 与 `minio/mc` 是**两个独立镜像**，同名 `RELEASE.*` 标签不一定两边都有。仓库 `infra/compose/minio.yml` 当前为：

- `minio/minio:RELEASE.2025-04-22T22-12-26Z`
- `minio/mc:RELEASE.2025-04-16T18-13-26Z`

可先单独拉取确认：

```bash
docker pull minio/minio:RELEASE.2025-04-22T22-12-26Z
docker pull minio/mc:RELEASE.2025-04-16T18-13-26Z
```

若仍失败，多为无法访问 Docker Hub（国内可配置镜像加速），或 compose 里标签已过期。可暂时把两个服务的 `image` 改为 `latest` 再 `up -d`，或改用 `ARBOR_OBJECT_STORE=local` 不必起 MinIO。

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

打开工作台先到登录页。预填：

| 邮箱 | 密码 | 角色 |
|---|---|---|
| `demo-a@arbor.eval` | `arbor-owner` | 空间 owner |
| `member-a@arbor.eval` | `arbor-member` | 仅对话 |
| `demo-b@arbor.eval` | `arbor-owner` | 租户 B owner |

登出在首页顶栏。会话存在浏览器 `localStorage`。

接口仍接受静态令牌（测试用）：

| 项 | 值 |
|---|---|
| Bearer 令牌 | `token-a` |
| 租户 ID | `0a000000-0000-4000-a000-000000000001`（演示租户 A） |
| 用户邮箱 | `demo-a@arbor.eval`（首页通过 `GET /v1/me` 显示） |

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
| 问「讨厌什么」答不上来 / 检索很差 | 未设置 `EMBEDDING_API_KEY`，检索仍是哈希。到 https://cloud.siliconflow.cn 创建密钥写入 `.env` |
| `connection timeout expired` / 连不上 Postgres | `.env` 里有 `DATABASE_URL` 但本机没起数据库。用记事本打开 `.env`，把 `DATABASE_URL=` 那一行删掉或前面加 `#`。不要 Postgres 也能跑（内存库）。要持久化再执行 `docker compose -f infra/compose/postgres.yml up -d` |
| 端口被占用 | 换端口时需同时改 API 启动参数与 `vite.config.ts` 中的 proxy 目标 |

## 相关文档

- [HTTP 接口](api.md) — 路径与错误码
- [测试与质量](testing.md) — pytest 分层与 CI
- [apps/web/README.md](../apps/web/README.md) — 前端入站适配器说明
