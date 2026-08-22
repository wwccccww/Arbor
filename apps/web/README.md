# Arbor 工作台

入站适配器：只调用 `/v1`，不内嵌检索、不直连数据库。

完整本地启动说明见 [docs/local-dev.md](../../docs/local-dev.md)。

## 快速启动

**前置：** Python 3.11+、Node.js 18+；在仓库根目录执行 `pip install -e ".[api]" uvicorn`。

```bash
# 终端 1 — 仓库根目录
python3 -m uvicorn apps.api.main:create_app_from_env --factory --port 8000

# 终端 2
cd apps/web
npm install
npm run dev
```

浏览器打开 **http://localhost:5173**。演示令牌为 `token-a`（owner），无需登录。

开发时 Vite 把 `/v1` 代理到 `http://127.0.0.1:8000`。

## 测试

```bash
npm test
```
