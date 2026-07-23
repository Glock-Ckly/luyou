# ADR-007: Compose Deployment for MVP

## Context

The demo is a single modular-monolith process with no demonstrated independent scaling pressure.

## Decision

Package one Python service with Docker and Compose, a health check, environment-driven secrets and a reverse-proxy security boundary. Do not introduce Kubernetes for the MVP.

## Consequences

- Local and CI deployment remain understandable.
- Multi-instance quotas and durable metrics require later shared infrastructure.
- Docker image execution must be verified in CI because the current host has no Docker engine.
