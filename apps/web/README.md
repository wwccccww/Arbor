# Arbor 工作台

入站适配器：只调用 `/v1`，不内嵌检索、不直连数据库。

完整本地启动说明见 [docs/local-dev.md](../../docs/local-dev.md)。

## 快速启动

真实可用：仓库根目录填好 `.env` 的 `DEEPSEEK_API_KEY` 后执行 `scripts/run.ps1`（Windows）或 `scripts/run.sh`，打开 **http://127.0.0.1:8000**。

开发热更新仍可用两个终端（PowerShell 请分行，不要写 `&&`）：

```powershell
python -m uvicorn apps.api.main:create_app_from_env --factory --port 8000
```

```powershell
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
