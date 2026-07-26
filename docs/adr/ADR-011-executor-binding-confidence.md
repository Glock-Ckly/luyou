# ADR-011: Executor Capabilities and Binding Confidence

## 背景

Provider、Codex、Cursor 和本地文档执行器能证明的模型与工具能力不同；提示词中的模型名不是实际绑定证据。

## 决策

采用 ENFORCED、VERIFIED_FALLBACK、EXECUTOR_MANAGED 三级绑定，并为四类 Executor 定义独立能力矩阵与统一 Receipt。

## 后果

UI 能准确表达 requested 与 actual model。Codex 当前只能 EXECUTOR_MANAGED；只有 argv/config/响应契约可证明时才能升级，代价是部分路径无法宣称强绑定。
