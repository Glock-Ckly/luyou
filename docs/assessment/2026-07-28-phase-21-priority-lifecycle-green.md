# Phase 21 Assessment - Priority, Lifecycle and Local Auth Green

## Scope

- Added DeepSeek priority classification with a required, validated `priority_reason`.
- Added deterministic `completion_state=unfinished` for every new analysis.
- Preserved `draft`/`ready` as Planning-owned initial states and persisted Task status as the lifecycle authority.
- Disabled the optional Bearer lock by default for the localhost Demo while retaining token support for shared hosts.
- Fixed the Task search input light colors and added unfinished, completed and terminated visual groups.

## DDD assessment

- Planning owns task interpretation, priority recommendation and initial readiness.
- Task owns persisted lifecycle transitions; the UI derives display groups from persisted Task status.
- Verification remains the only future authority that may prove completion.
- Gateway owns optional Bearer authentication. Provider credentials remain environment-only Adapter concerns.
- No domain object, prompt artifact, browser storage or repository file contains a Provider credential.

## TDD evidence

- Phase 20 Red contract failed before implementation for priority reason, unfinished state and UI markers.
- Full deterministic suite: 82/82 passed.
- Dashboard contract suite: 10/10 passed.
- JavaScript syntax, `git diff --check` and phase assessor passed.
- Provider Adapter boundary and deterministic reliability audits passed.

## Secondary assessment

- Real DeepSeek smoke returned a valid priority, non-empty reason, `unfinished`, safe `draft`/`ready`
  initial status and the expected DeepSeek planner identity.
- Credential-shaped scans of the worktree and Git history found no committed key.
- Playwright at 1440x1000 and 390x844 confirmed white readable search input, three distinct completion
  colors, no search-control overlap and no horizontal overflow.
- Localhost no-token mode removes only the local Demo lock. Shared or non-loopback deployments still
  require a separate high-entropy Router token.
- A new analysis can never claim completed, executed or verified state from user wording alone.

## Checklist status

- Completed: priority classification and explanation, unfinished initial lifecycle, status display groups,
  local no-token configuration, color correction, regression tests and live Planner smoke.
- Partial: child subtasks remain analysis/Markdown data and are not persisted as an ExecutionJob DAG.
- Deferred: automatic model execution, VerificationReport-driven completion and cost settlement.
- Blocked: none.

## Commit

Implementation commit: pending Green commit.
