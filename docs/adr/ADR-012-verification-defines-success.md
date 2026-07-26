# ADR-012: Verification Defines Success

## 背景

模型可能错误声称测试已通过或文件已修改。执行器退出成功也不能证明验收标准、范围和安全扫描全部通过。

## 决策

只有独立 VerificationReport PASS 才允许 Job 进入 SUCCEEDED。模型自评不作证据，命令、Artifact、范围与敏感信息检查必须可追溯。

## 后果

成功语义可审计并支持受限修复。代价是运行环境必须提供安全命令执行与 Artifact 读取，纯文本任务也需要结构化验证策略。
