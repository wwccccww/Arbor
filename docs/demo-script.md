# 五分钟产品演示脚本

面向对外展示与本地彩排。账号与样例文件与 E2E 一致。

## 准备

- 启动：`./scripts/run.sh` 或 `powershell -File scripts/run.ps1`
- 打开 http://127.0.0.1:8000
- 登录：`demo-a@arbor.eval` / `arbor-owner`
- （可选）`.env` 配置 `DEEPSEEK_API_KEY` 获得真实对话；无密钥时使用脚本回复，演示路径仍可用

## 步骤（约 5 分钟）

| 分钟 | 动作 | 预期 |
|------|------|------|
| 0:00 | 工作空间 → 打开 **林夏** | 三栏工作台，右侧默认 **传记目录** |
| 0:30 | 左侧「授权与导入」→ **导入** `sample-chat.txt`（可 [下载样例](/demo/sample-chat.txt)） | 导入完成，收件箱有条目 |
| 1:00 | 收件箱 → **一键写入记忆并建树** | 收件箱清空；传记目录出现新节点 |
| 1:30 | 对话输入：「我们上次为什么吵架？」 | 回复提及香菜/面馆；下方有 **依据** 链接 |
| 2:00 | 点击 **依据** | 右侧高亮 **面店争吵** 节点 |
| 2:30 | 返回 → 打开 **客服小周**，同问一句 | 回复「没有找到…」或不含面馆细节 |
| 3:30 | 工作空间 → **记忆体检** → suite-v1 检索 | **跨租户泄漏** 为 0 |
| 4:30 | （可选）suite-v1 **生成评测** | 引用子集 1.0；RAGAS 需 `ARBOR_JUDGE_API_KEY` |
| 4:45 | 记忆体检 → **Agent Eval（agent-v1）** | 任务成功率 1.0；越权/审批绕过/重复副作用均为 0 |
| 5:00 | 工作台 → **Agent 任务** | 可查看 Run 步骤与审批队列 |

## Agent 故障注入彩排（约 3 分钟）

本地无需 Redis，smoke 使用 Fake Planner / Fake Tool：

```bash
# agent-v1：审批、越权、超时重试、worker 恢复（7 cases）
python3 -m pytest tests/eval/test_agent_smoke.py -q

# memory-v1：过期 / superseded / 删除 / consolidation（4 gates）
python3 -m pytest tests/eval/test_memory_smoke.py -q

# multimodal-v1：页码 / 时间戳 / lineage（3 layers）
python3 -m pytest tests/eval/test_multimodal_smoke.py -q
```

UI 路径：

1. **记忆体检** → **Agent Eval（agent-v1）** → 确认 P0 安全指标为 0
2. **Agent 任务** → 创建 Run → 在待审批中批准/拒绝 → 展开 **上下文 manifest** 与 **多模态证据链**

## 窄屏提示

宽度 &lt; 900px 时，导入/Inbox 在 **「授权与导入」** Tab；有待处理收件箱时会自动切到该 Tab。

## 自动化

- `apps/web/e2e/demo-path.spec.ts` — 导入 → bootstrap → 传记可见
- `apps/web/e2e/demo-closure.spec.ts` — 吵架引用 + 人设隔离

```bash
cd apps/web && npm run test:e2e
```

## CI / Nightly

仓库 Secrets 与 bge 基线说明见 [nightly-ci.md](nightly-ci.md)。
