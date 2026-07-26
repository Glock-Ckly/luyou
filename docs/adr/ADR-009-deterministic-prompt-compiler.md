# ADR-009: Deterministic Prompt Compiler with Optional Planner Enrichment

## 背景

自由模型可补充计划，但不能可靠维护文件、命令、预算和验收安全边界。不可重建的提示词也无法审计。

## 决策

由后端确定性编译 PromptPackage 的 JSON、Markdown、模板版本与 SHA-256。Planner 只能补充建议，不能扩大后端边界。

## 后果

相同输入可复现且可测试，安全策略不依赖模型服从。代价是模板演进需要版本管理，开放式灵活性低于自由拼接。
