# ADR-005: One Route-and-Execute Use Case

## Context

The repository currently has two diverging flows: MultiModelOrchestrator and TaskDispatcher. The dashboard uses Dispatcher while existing E2E tests use Orchestrator.

## Decision

Create one RouteAndExecuteUseCase and make HTTP, CLI, reliability demo and tests call it. Keep compatibility wrappers only during migration.

## Consequences

- Tests verify the production path.
- Retry/fallback behavior cannot diverge between UI and CLI.
- Duplicate orchestration logic can be removed after migration.

