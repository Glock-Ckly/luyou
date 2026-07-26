# Execution Task CRUD Specification

## Goal

Provide the first persistent domain slice of the AI Task Execution Platform. Users can create, browse, inspect, update and delete structured execution tasks before later phases attach planning, prompt generation, routing, execution and validation.

## Aggregate

ExecutionTask owns:

- task_id
- title
- description
- task_type
- status
- priority
- technology_stack
- scope
- acceptance_criteria
- tags
- version
- created_at
- updated_at

## Invariants

- Title and description are required.
- Task type must use a supported domain value.
- Status must use draft, ready, running, validating, completed, failed or cancelled.
- Priority must use low, medium, high or urgent.
- Acceptance criteria and tags are normalized non-empty strings.
- HTTP collection fields (`technology_stack`, `acceptance_criteria`, `tags`) must be JSON arrays.
- Domain collection inputs may be lists, tuples or sets; strings, bytes and mappings are invalid collections.
- Version increases after every update.
- A supplied update version must be a JSON integer and must equal the persisted version. Malformed
  strings, fractional numbers and booleans are validation errors, not server errors.
- Running or validating tasks cannot be deleted.
- Status updates must follow the ExecutionTask transition matrix below.
- Repository and HTTP adapters cannot make routing decisions.

## Status transitions

The transition guard applies when updating an existing task. Terminal statuses have no outgoing
transitions.

| Current | Allowed next statuses |
|---|---|
| draft | ready, cancelled |
| ready | running, draft, cancelled |
| running | validating, failed, cancelled |
| validating | completed, failed, running |
| completed | none |
| failed | ready, cancelled |
| cancelled | none |

## API contract

- GET /api/tasks lists tasks and supports status, task_type and search filters.
- POST /api/tasks creates a task and returns HTTP 201.
- GET /api/tasks/<task_id> returns one task or normalized 404.
- PUT /api/tasks/<task_id> replaces editable task fields and checks version when supplied.
- DELETE /api/tasks/<task_id> removes a deletable task and returns HTTP 204.
- Malformed versions and collection shapes return HTTP 400 with `invalid_task`.
- Deleting an unknown task returns HTTP 404 with `task_not_found`.
- Deleting a running or validating task returns HTTP 409 with `task_conflict` and preserves the row.

## Persistence

Use a TaskRepository port. The MVP adapter uses SQLite at MODEL_ROUTER_DB_PATH or .runtime/model-router.db. Runtime data must not be committed.

Deletion is atomic at the repository boundary. The adapter executes one conditional `DELETE` that
excludes protected statuses, then uses `rowcount` and a same-transaction existence lookup to
distinguish not found from a lifecycle conflict. The application layer must not perform a separate
read-then-delete lifecycle check.

## UI contract

The task workbench uses a nested marketplace pattern rather than copying Taobao branding:

- Top utility bar and global search.
- Left category and status navigation.
- Center task cards/table with filters and CRUD actions.
- Right contextual panel for statistics, execution pipeline and selected-task details.
- Create/edit drawer or modal without navigating away.
- Responsive collapse for smaller screens.

## Acceptance criteria

1. CRUD operations persist after repository re-instantiation.
2. Invalid input returns normalized errors without SQLite details.
3. Running and validating tasks cannot be deleted.
4. Search and filters are deterministic.
5. The Dashboard can create, edit, view and delete tasks without page reload.
6. Existing routing, Provider and reliability APIs remain compatible.
