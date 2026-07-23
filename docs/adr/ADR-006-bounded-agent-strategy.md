# ADR-006: Bounded Agent Strategy

## Context

The checklists request Agent usage, but reliability must not depend on an unconstrained autonomous planner.

## Decision

Use bounded engineering role prompts with explicit write scopes. Keep deterministic routing and fallback in domain services. Defer runtime autonomous routing agents until step, cost, timeout and permission controls are implemented.

## Consequences

- Agent failure cannot block the base router.
- Review responsibility can remain independent.
- Runtime Agent Decision remains partial rather than falsely complete.
