# suite-ragas-official

官方 `ragas.testset.TestsetGenerator`（ragas 0.2.15）对齐成功的子集，对照用。

默认规模集在 `../suite-ragas-v1/`：离线 compat **加上** 这些对齐成功的官方题；未对齐的官方题不会进入默认套件。隔离 / 跨租户负例只存在于 `suite-ragas-v1`。

本轮：`--size 100`，原始 100、对齐 100、丢弃 0（single-hop 50 / multi-hop 50）。人设：林夏 A 54、客服小周 34、租户 B 林夏 12。LLM 为 DeepSeek Chat；embedding 为 `FakeEmbeddings`（DeepSeek 无 embedding 接口）。

```text
python3 eval/generate_testset.py --backend ragas --size 100
```
