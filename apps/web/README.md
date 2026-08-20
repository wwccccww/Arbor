# Arbor 工作台

入站适配器：只调用 `/v1`，不内嵌检索、不直连数据库。演示令牌是 `token-a`（owner）。

```bash
# 仓库根目录
python3 -m uvicorn apps.api.main:create_app_from_env --factory --port 8000

cd apps/web
npm install
npm test
npm run dev
```

开发时 Vite 把 `/v1` 代理到 `http://127.0.0.1:8000`。
