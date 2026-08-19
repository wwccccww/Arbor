# ADR 0003：DeepSeek 作为生成层，bge-m3 作为嵌入层

- 状态：已采纳
- 日期：2026-08-19

## 上下文

需要便宜、中文较好的对话模型，以及可靠的中文嵌入。DeepSeek 提供 OpenAI 兼容 Chat/Reasoner，不提供本项目应绑定的嵌入主路径。

## 决策

- `LLMClient` → DeepSeek `deepseek-chat`（日常对话）。
- `ReasoningClient` → `deepseek-reasoner`（抽取、冲突建议、评测打分），可回退 Chat。
- `EmbeddingClient` → bge-m3。图/语音先转描述或转写再嵌入。
- 应用层只依赖端口；模型名放组合根配置。

## 后果

- 换对话模型改适配器配置即可。
- 换嵌入模型需重建向量列并重跑评测基线。
- 禁止在领域层出现 `deepseek` 或 `bge` 字样。
