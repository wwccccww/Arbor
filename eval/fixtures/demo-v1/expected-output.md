# Agent 生产化演示 — 预期输出

与 `eval/fixtures/demo-v1/manifest.json` 十二步对应。离线验证：`python3 -m pytest tests/eval/test_demo_v1_smoke.py -q`

| 步骤 | 预期 |
|------|------|
| 上传图片与语音 | multimodal-v1 perception 层通过；PDF 页码=3，音频 time_start_ms=1200 |
| 页码/时间戳证据 | segment-retrieval-hit 可检索到带 page_number 的片段 |
| 固定岗位版本 Run | agent-v1 retrieve-only-handoff 完成；Run 绑定 employee_definition_version |
| 首次检索 | retrieve 步骤 output 含 hit_ids |
| 工具新实体 | ticket.create 返回 ticket_id/title |
| 二次检索 | second-retrieve-after-tool 在工具后再次 retrieve |
| 高风险审批 | ticket-with-approval 进入 waiting_approval 后批准完成 |
| 工具超时 | ticket-timeout-retry 首次超时、重试后 completed |
| 幂等恢复 | duplicate-delivery-idempotent + worker-resume 均 ok |
| Run 完成引用 | final_output 含 text；step_tree 含 answer 节点 |
| 经验 Inbox | ExtractRunMemory 产生 episodic 候选，status=pending |
| Tempo trace | CI `test_tempo_trace_search_by_agent_run_request_id` 可搜到 request_id |

## 关联 baseline

- `eval/baselines/demo-v1-smoke.json` — 十二步 step_pass_rate=1.0
- `eval/baselines/agent-v1-smoke.json` — task_success_rate=1.0，P0 安全=0
- `eval/baselines/agent-ablation-v1.json` — 四轨消融
- `eval/baselines/agent-security-v1-smoke.json` — 6/6 安全场景
- `eval/baselines/memory-v1-smoke.json` — 15 cases gate_pass_rate=1.0
- `eval/baselines/multimodal-v1-smoke.json` — layer_pass_rate=1.0
