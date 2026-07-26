# Artifact Store Contract

## Roots and naming

Execution packages live under `artifacts/execution-packages/<job_id>/`; results live under
`artifacts/execution-results/<job_id>/`. Names use `<artifact_type>-<sequence>-<sha256-prefix>.<ext>`.
Metadata records `artifact_id`, `job_id`, `attempt_id`, type, media type, byte length, SHA-256,
created_at, producer and relative path.

## Path safety

The Port accepts identifiers and relative logical names, never arbitrary absolute destinations.
Adapters resolve the candidate, require it to remain under the configured root, reject `..`, absolute
paths, drive changes, symlink escape and reserved device names, and write through a temporary file plus
atomic rename. Reads repeat containment checks and verify hash when requested.

## Retention

PromptPackage, receipts, verification reports and delivery reports are retained with the Job. Temporary
stdout/stderr details may expire after 30 days; summaries and hashes remain. Failed secret scans are
quarantined and not downloadable. Deletion is policy-driven, auditable and idempotent.

Runtime artifact contents are gitignored by default. Ports preserve replacement by S3-compatible or
database-backed adapters without exposing storage paths to domain objects.
