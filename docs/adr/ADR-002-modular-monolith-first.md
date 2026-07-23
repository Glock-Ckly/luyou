# ADR-002: Modular Monolith Before Service Split

## Decision

Implement Gateway, Application, Routing, Execution and Provider boundaries inside one deployable process first.

## Why

The current scale does not justify distributed operational complexity. Stable ports and contracts are prerequisites for a safe split.

## Future impact

Gateway and Routing may become independent services without changing domain behavior.

