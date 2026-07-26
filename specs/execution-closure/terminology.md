# Execution Closure Terminology

This table is the authoritative copy of section 8 in the governing execution checklist.

| 术语 | 严格含义 | 允许的下一步 | 明确**不**代表 |
|---|---|---|---|
| `previewed` | 已生成 Plan / Prompt / RouteDecision，未调用任何模型或执行器 | approve → ready | 不代表已路由执行 |
| `routed` | 已产出 RouteDecision（选定候选模型） | dispatch | **不**代表已执行 |
| `queued` | 已投递到队列（Cursor 等），等待外部处理 | claim | **不**代表已开始、更不代表完成 |
| `dispatched` | 已交给执行器，执行器已接收 | running | 不代表已产出结果 |
| `running` | 执行器正在工作，有活跃 attempt | verifying / failed | 不代表有结果 |
| `answered` | 模型返回了文本 | verifying | **不**代表内容正确、**不**代表仓库被改 |
| `executed` | 执行器完成且返回 ExecutionReceipt | verifying | **不**代表结果正确 |
| `verified` | VerificationReport.status == PASS，7 个必要条件全满足 | delivered | — |
| `repairing` | 验证失败且在上限内进行第 N 次修复 | running / failed | 不代表将会成功 |
| `delivered` | 已产出 DeliveryReport 与全部 Artifact，可下载 | — | 不代表已 commit/push 到用户仓库 |
| `dispatch_success` | 投递动作本身成功 | — | **不**等于 `job_success` |
| `job_success` | Job 状态为 `SUCCEEDED`（含 verified） | — | — |
| `ENFORCED` | 可从 argv/config/响应**证明**用了指定模型 | — | 只写进 Prompt **不算** |
| `VERIFIED_FALLBACK` | 用了白名单内替代模型且有 `fallback_reason` | — | 不代表用了首选模型 |
| `EXECUTOR_MANAGED` | 执行器自管模型，系统不掌握 | — | **不得**对外显示为强制绑定 |

API、领域枚举、UI 文案和审计报告必须引用这些含义，不得把 routed、queued、answered 或
executed 映射为 completed。状态机的英文大写枚举与上述事件/事实术语属于不同层次。
