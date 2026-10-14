# 本地负载 / 并发冒烟

用于 **分层容量意识**：Fake LLM 压 API + 检索，**不是** 真 DeepSeek 极限 QPS。

## 1. 启动被测 API

```bash
chmod +x scripts/load/serve-for-load.sh
./scripts/load/serve-for-load.sh
```

- 无 `DEEPSEEK_API_KEY` → **ScriptedLLM** + **fixture 嵌入**（与 CI 类似）。
- `ARBOR_RATE_LIMIT_PER_WINDOW` 默认 **10000**（避免 k6 被 429 淹没）。
- 要测 **Postgres + 连接池 + RLS**：另终端起 `docker compose -f infra/compose/postgres.yml up -d`，在 `.env` 配置 `DATABASE_URL` 后再跑本脚本。

## 2. 安装 k6

```bash
# Debian/Ubuntu 示例 — 其它系统见 https://grafana.com/docs/k6/latest/set-up/install-k6/
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

## 3. 跑 k6 场景

**场景 A — 只打 auth / 租户头（偏 PG 池 + RLS）**

```bash
k6 run scripts/load/k6-me.js
# 或加重：VUS=50 DURATION=1m k6 run scripts/load/k6-me.js
```

**场景 B — 聊天全路径（检索 + 上下文 + Scripted 回复）**

```bash
k6 run scripts/load/k6-chat-scripted.js
```

环境变量：`BASE_URL`、`TENANT_ID`、`THREAD_ID`、`VUS`、`DURATION`、`DEMO_TOKENS`（逗号分隔，分摊限流配额）。

## 4. pytest 并发正确性（CI 可跑，需 Postgres）

```bash
export DATABASE_URL=postgresql://...
pytest tests/api/test_postgres_concurrent_mixed.py -v
```

与 `test_postgres_app_concurrent_me_with_tenant_header` 互补：混合只读接口、更高并发。

## 5. 导入队列积压（ARQ + Postgres + worker）

API 与 worker **必须共用 `DATABASE_URL`**（job 状态在 PG）；仅内存模式 worker 吃不到 API 写的 job。

```bash
docker compose -f infra/compose/postgres.yml up -d   # 或本地 Postgres
docker compose -f infra/compose/redis.yml up -d
export DATABASE_URL=postgresql://...
export REDIS_URL=redis://127.0.0.1:6379/0

./scripts/load/serve-for-load.sh          # 终端 1（需改为带 PG/Redis 的环境变量）
python3 -m arq arbor.adapters.outbound.arq.worker.WorkerSettings   # 终端 2
./scripts/load/import-backlog-smoke.sh    # 终端 3
```

环境变量：`IMPORT_COUNT`（默认 25）、`BASE_URL`、`PERSONA_ID`。

## 6. 导入队列积压（手工观察 Grafana）

```bash
# REDIS_URL + arbor-worker 启用后，连续上传 N 个小 PDF，看 Grafana：
# arbor_import_jobs_total、pending 任务、import.process duration
```

## 7. 真 bge-m3 + DeepSeek（双 worker 冒烟）

**用途**：验证嵌入/LLM 延迟、导入队列消化，**不是** 压出线上 QPS。

前置：Postgres（含 pgvector）、Redis、`DEEPSEEK_API_KEY`、`EMBEDDING_API_KEY`（或 `SILICONFLOW_API_KEY`）。

```bash
export DATABASE_URL=postgresql://arbor:arbor@127.0.0.1:5432/arbor
export REDIS_URL=redis://127.0.0.1:6379/0
# export DEEPSEEK_API_KEY=...
# export EMBEDDING_API_KEY=...

chmod +x scripts/load/serve-for-load-real.sh scripts/load/run-arq-workers.sh
./scripts/load/serve-for-load-real.sh          # 终端 1
./scripts/load/run-arq-workers.sh                # 终端 2（默认 WORKERS=2）
```

聊天（**低 VU**，120s 超时）：

```bash
VUS=2 DURATION=20s k6 run scripts/load/k6-chat-real.js
```

导入积压（真嵌入会慢，可把 `IMPORT_COUNT` 调小；长跑可加大 poll 上限）：

```bash
IMPORT_COUNT=40 ./scripts/load/import-backlog-smoke.sh
```

`/v1/me` 应显示 `llm: deepseek`、`embed: bge-m3`（或你的 `EMBEDDING_MODEL`）、`store: postgres`、`job_queue: redis`。

## 8. 如何读结果

| 场景 | 主要看 | 典型瓶颈 |
|------|--------|----------|
| k6-me + Postgres | `http_req_duration` p95、0% 5xx | 连接池、RLS checkout |
| k6-chat scripted | p95、失败率 | 检索 + 上下文编译（仍无真 LLM） |
| k6-chat real | 失败率、~0.1 rps 量级 | DeepSeek + bge 串行/排队 |
| 并行导入 + 2 worker | pending/running 快照、completed/s | 嵌入 + 写 PG，≈2× 单 worker 吞吐 |

### 本机一次实测参考（Cloud Agent VM，仅供参考）

| 栈 | 场景 | 吞吐 / 规模 | p95 / 备注 |
|----|------|-------------|------------|
| fixture + 内存 | k6-me 30 VU×30s | ~446 rps | ~50 ms，0% fail |
| fixture + PG | k6-me 800 VU | ~450–550 rps 平台期 | ~2.3 s，0% fail |
| fixture + PG | k6-chat 30–120 VU | ~3–15 rps | 3–35 s（排队） |
| PG + 1 worker | 导入 250 串行 | worker 跟得上 | peak pending ≈0 |
| PG + 2 worker | 导入 120 并行 burst | ~8 completed / 5s | 提交后 pending≈118、running≈2 |
| 真 bge + DeepSeek + 2 worker | 单条聊天 | ~10.7 s/条 | — |
| 真 bge + DeepSeek | k6-chat-real 2–10 VU×20s | ~0.12–0.14 rps | p95 ~20–44 s，17–29% 超时 fail |

**不要** 把 k6 数字写成「线上 QPS」；结论模板：

> Scripted 路径下 `/v1/me` p95 ≈ X ms（Y VU）；聊天 p95 ≈ Z ms。真 LLM 路径仅验证延迟与队列，约 A s/条、并发 B VU 时失败率 C%。
