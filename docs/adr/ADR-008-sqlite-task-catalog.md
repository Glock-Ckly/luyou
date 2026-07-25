# ADR-008: SQLite Task Catalog for the Execution Platform MVP

## Context

The new execution-platform checklist requires persistent Task entities and CRUD behavior. The current router has no database-backed application state. Introducing a distributed database before the aggregate and contract stabilize would add infrastructure without domain evidence.

## Decision

Define ExecutionTask as a domain aggregate behind a TaskRepository port. Use SQLite as the first adapter and keep runtime files under .runtime. Expose CRUD through the existing HTTP Gateway while keeping validation and state rules in the application/domain layers.

Use a nested marketplace-style workbench for information density: global search, category navigation, task collection and contextual details. Do not copy Taobao logos, assets or trade dress.

## Consequences

- CRUD behavior is durable and testable with standard-library dependencies.
- A later PostgreSQL adapter can replace SQLite without changing domain behavior.
- Multi-instance writes are deferred.
- The UI can evolve toward Task Plan, Prompt, Execution and Validation sub-resources without another navigation rewrite.
