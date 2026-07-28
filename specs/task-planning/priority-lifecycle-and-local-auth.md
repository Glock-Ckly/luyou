# Priority, Lifecycle and Local Authentication Contract

## Local authentication mode

- The localhost demo listens on `127.0.0.1` and may run with an empty `MODEL_ROUTER_API_TOKEN`.
- Bearer authentication remains available when `MODEL_ROUTER_API_TOKEN` is configured.
- A non-loopback deployment must configure authentication and explicit origin/work-directory boundaries.
- Provider credentials remain environment-only and must never be committed as defaults, examples or fixtures.

## DeepSeek priority analysis

DeepSeek assigns `low`, `medium`, `high` or `urgent` and must provide `priority_reason` based on explicit
urgency, dependency blocking, security impact, blast radius, deadlines and recovery cost. The backend
validates both fields and compiles the reason into the deterministic Markdown plan.

## Lifecycle truth

- Every newly analyzed Task has `completion_state=unfinished`.
- `needs_clarification=true` maps to `draft`; otherwise it maps to `ready`.
- DeepSeek cannot assign `running`, `validating`, `completed`, `failed` or `cancelled` during analysis.
- Only execution and verification evidence may transition a persisted Task toward `completed`.
- The UI groups persisted states as unfinished, completed or terminated without rewriting domain status.

## UI correction

Task-page search inputs use explicit light foreground, background and placeholder colors so global dark
form styles cannot leak into the light workbench. Completion grouping and priority reasoning are visible
in the analysis preview and Task catalog.
