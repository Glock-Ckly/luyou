# PromptPackage Contract

## Required sections

Every Markdown and JSON representation contains these 24 ordered sections:

1. Original Goal
2. Current Subtask
3. Why This Subtask Exists
4. Dependency Inputs
5. Project Context Summary
6. Applicable AGENTS Instructions
7. Relevant Specs and ADRs
8. DDD Bounded Context
9. Owned Invariants
10. Explicit Non-goals
11. Allowed Read Paths
12. Allowed Write Paths
13. Forbidden Paths
14. Allowed Commands
15. Forbidden Commands
16. Execution Budget
17. TDD Red/Green Workflow
18. Acceptance Criteria
19. Required Artifacts
20. Verification Commands
21. Return JSON Schema
22. Human-readable Report Format
23. Template Version
24. Content Hash

## Deterministic compilation

Backend-owned security fields are authoritative. Planner enrichment may add context, risks or proposed
subtasks but may not widen paths, commands, permissions, budgets or Acceptance Criteria. Missing
criteria produce a draft and WAITING_APPROVAL, never an assumed success condition.

Normalize strings to UTF-8 LF, sort object keys, preserve declared list order, remove volatile values
and serialize compact JSON. Compute `content_hash` as lowercase SHA-256 over canonical JSON with the
Content Hash value omitted. Insert that hash into JSON and Markdown. Equal normalized inputs and
template versions must produce byte-identical representations and hashes.

## Context and security

When over budget retain specifications, AGENTS instructions, DDD boundaries, relevant signatures,
tests and acceptance evidence before prose or unrelated files. Exclude API keys, tokens, full `.env`,
credential files, unrelated logs and personal data. Both representations must be reloadable and
semantically equivalent. Artifact paths are defined by the Artifact Store specification.
