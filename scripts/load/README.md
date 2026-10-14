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

## 5. 导入队列积压（手工）

```bash
# REDIS_URL + arbor-worker 启用后，连续上传 N 个小 PDF，看 Grafana：
# arbor_import_jobs_total、pending 任务、import.process duration
```

## 6. 如何读结果

| 场景 | 主要看 | 典型瓶颈 |
|------|--------|----------|
| k6-me + Postgres | `http_req_duration` p95、0% 5xx | 连接池、RLS checkout |
| k6-chat scripted | p95、失败率 | 检索 + 上下文编译（仍无真 LLM） |
| 真 DeepSeek | 勿用 k6 高 VU | 供应商 RPM / 超时 |

**不要** 把 k6 数字写成「线上 QPS」；结论模板：

> Scripted 路径下 `/v1/me` p95 ≈ X ms（Y VU）；聊天 p95 ≈ Z ms；未测真 LLM 吞吐。
