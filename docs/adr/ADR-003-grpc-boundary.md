# ADR-003: Define gRPC at the Gateway/Router Boundary

## Decision

Use HTTP externally. Introduce gRPC only when Gateway and Router become independently deployable. Maintain a proto contract in the repository before the split.

## Current status

Deferred until the modular use case and provider contract are stable. The dashboard must not claim live gRPC before implementation.

