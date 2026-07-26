# ADR-010: Persistent ExecutionJob Instead of Blocking HTTP

## 背景

仓库修改、模型调用和验证可能超过 HTTP 生命周期；进程重启后仅靠请求内状态无法恢复或审计。

## 决策

执行使用持久化 ExecutionJob。创建返回 202 和查询链接，Worker 通过租约推进状态。现有同步 `/api/route` 保持兼容但只代表路由结果。

## 后果

任务可查询、恢复和取消，queued 与 success 被区分。代价是需要 Job Repository、幂等、租约、轮询和后续事件通知能力。
