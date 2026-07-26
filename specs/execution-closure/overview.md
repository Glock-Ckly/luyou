# Execution Closure OpenSpec Index

## Purpose

本规格集定义从结构化 Task 到可审计 Delivery 的统一契约：Task -> Specification ->
Project Context -> Plan -> PromptPackage -> RouteDecision -> ExecutionJob -> Execute -> Verify ->
Repair -> Deliver。它约束未来领域实现，不代表这些运行时能力已经完成。

## DDD boundaries

- Task Context 拥有用户目标和验收草案。
- Planning Context 拥有 TaskSpecification、ProjectSnapshot 和 DAG Plan。
- Routing Context 只产出 RouteDecision，不执行任务。
- Execution Context 拥有 Job、Attempt、WorkOrder、Receipt 和状态机。
- Verification Context 独立判断 PASS、可修复失败或最终失败。
- Delivery Context 持有 Artifact 与最终报告；Cost Context 持有预算与实际账目。

Adapters may depend on application services, application services may depend on domain and ports,
and domain specifications never depend on HTTP, SQLite, gRPC or a concrete model Provider.

## Specifications

- [ExecutionJob lifecycle](job-lifecycle.md)
- [PromptPackage contract](prompt-package.md)
- [Model binding and receipt](model-binding.md)
- [Verification contract](verification.md)
- [Artifact store](artifact-store.md)
- [Cost ledger](cost-ledger.md)
- [Terminology](terminology.md)

## gRPC boundary

`proto/model_router.proto` remains a future process boundary under ADR-003. Current Python calls stay
in-process. When a real service split is justified, gRPC transports DTOs for route preview, job
submission and job query; it must not move domain invariants into generated messages or handlers.

## Compatibility

Existing synchronous `/api/route` remains a route/simulation capability. Future job creation returns
202 and a Job identifier. `/api/specs` is unchanged in this documentation-only phase; HTTP exposure of
this index belongs to the later execution gateway phase.
