# Routing Policy Specification

## Inputs

- TaskType
- ComplexityTier T0-T4
- BudgetRatio 0.0-1.0
- Provider availability
- Optional model constraints

## Output

RoutingDecision contains primary model, ordered fallbacks, executor, floor, tier, cost level and budget zone.

## Invariants

- Candidate models are unique and ordered.
- Budget degradation never crosses the task floor.
- Critical tasks do not degrade below their configured floor.
- Unavailable providers are skipped before execution.
- Routing never calls a provider adapter.
- Unknown task/complexity values normalize to safe defaults.

