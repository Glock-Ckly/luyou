# DeepSeek Task Analysis Contract

## Goal

Convert one user Goal and an optional Scope into a validated Task preview, measurable acceptance
criteria, optional subtasks, model recommendations and a deterministic Markdown checklist. Analysis is
preview-only: it does not create, route or execute a Task.

## Bounded context

Planning owns `TaskAnalysis`, subtask design, technology recommendations and checklist compilation.
Task owns persisted Task fields and lifecycle. Routing owns executable route decisions. Provider owns
DeepSeek transport only. Verification later decides success.

## Request

`POST /api/tasks/analyze`

```json
{"goal": "non-empty string", "scope": "optional string"}
```

Goal length is 10-20000 characters. Scope may be absent or empty and cannot override server security
boundaries. The endpoint uses existing authentication and rate limiting.

## Analysis response

Required fields:

- `analysis_id`: deterministic `analysis_` plus SHA-256 prefix.
- `goal_summary`, `suggested_title`, `description`.
- `task_type`: existing ExecutionTask task type.
- `complexity`: T0-T4.
- `priority`: low, medium, high or urgent.
- `technology_stack`: 1-12 non-empty technologies. Languages are open vocabulary.
- `scope`: optional normalized text.
- `acceptance_criteria`: 1-20 measurable criterion objects.
- `coverage_target_percent`: integer 60-100.
- `tags`: 1-12 unique normalized tags.
- `split_recommended`, `subtasks`: 0 or 2-12 validated subtasks.
- `needs_clarification`, `clarification_questions`.
- `recommended_models`: primary and fallback recommendations from the supplied catalog only.
- `planner_model`, `reasoning`, `checklist_markdown`, `content_hash`.

Each acceptance criterion contains `category`, `criterion`, `target_percent` and `verification`. Expected
categories include functional, boundary, error, security, performance, compatibility and regression
when relevant. Percentages express explicit pass thresholds, not fabricated execution evidence.

Each subtask contains `title`, `description`, `task_type`, `complexity`, `technology_stack`,
`acceptance_criteria`, `recommended_model`, `fallback_models` and `binding_mode`. Subtasks have distinct
goals and do not exceed the parent scope.

## Status mapping

DeepSeek does not assign lifecycle status directly. Application code maps `needs_clarification=true`
to `draft`; otherwise the preview status is `ready`. The user may edit non-security Task fields before
confirmation.

## Model recommendation

The prompt receives a backend-produced model capability catalog. Every recommended model must occur in
that catalog. A recommendation includes reason, strengths, limitations and binding mode. Codex/Cursor
recommendations remain EXECUTOR_MANAGED unless execution evidence can prove another mode.

## Markdown compiler

Backend code, not DeepSeek free text, compiles sections in this order: Goal, Summary, Classification,
Technology Stack, Scope, Acceptance Criteria, Subtasks, Model Allocation, Risks, Confirmation Checklist.
Canonical JSON uses sorted keys and UTF-8; `content_hash` is lowercase SHA-256 over canonical analysis
data excluding generated IDs, Markdown and hash. Equal normalized input produces equal IDs and Markdown.

## Confirmation and artifacts

`POST /api/tasks/from-analysis` accepts a validated analysis object. It creates one parent Task and
writes `.runtime/task-plans/<task_id>.md` through `TaskPlanArtifactPort`. A failed Artifact write is
compensated by deleting the new Task. Existing manual `POST /api/tasks` remains compatible.

`GET /api/tasks/<task_id>/plan.md` returns `text/markdown; charset=utf-8`, or normalized 404 when absent.
Clients never choose Artifact paths.

## Errors

- Invalid request: 400 `invalid_task_analysis`.
- Missing or invalid DeepSeek configuration: 503 `task_planner_unavailable`.
- Provider/parse/schema failure: 502 `task_analysis_failed`.
- Missing plan: 404 `task_plan_not_found`.
- Internal errors use existing safe error normalization and never include keys, prompts or raw responses.

## Non-goals

- Analysis does not execute tasks or prove model binding.
- It does not create ExecutionJob, VerificationReport or cost settlement.
- It does not enumerate every programming language in code.
- It does not allow LLM output to change workdir, command, credential or approval policy.
