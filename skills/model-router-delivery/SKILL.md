---
name: model-router-delivery
description: Enforce an evidence-based Specification, DDD, Contract, TDD, implementation, secondary assessment, commit, and push workflow for AI model router changes. Use when adding router features, changing domain policy, delivering a checklist phase, preparing a release, or auditing whether a claimed phase is actually complete.
---

# Model Router Delivery

Apply one reversible delivery phase at a time. Never mix unrelated production changes in the same phase.

## Workflow

1. Read the governing checklist, specifications, ADRs, current assessments and repository instructions.
2. State the bounded context, invariant, acceptance evidence and explicit non-goals.
3. Update a specification or ADR before code when behavior or boundaries change.
4. Add a focused failing test and record the red evidence.
5. Implement the smallest change that satisfies the contract without crossing domain boundaries.
6. Refactor only while all focused tests remain green.
7. Run scripts/assess_phase.py from the repository root.
8. Perform a secondary assessment against references/phase-assessment-template.md.
9. Commit and push the logical phase immediately. Record the implementation hash in a follow-up assessment commit.

## Hard Gates

- Do not weaken an assertion to make a test pass.
- Do not put routing decisions in Gateway or Provider adapters.
- Do not expose credentials, full sensitive prompts or raw exceptions.
- Do not claim deferred infrastructure as complete.
- Stop before commit if deterministic tests, contract tests, dashboard checks or diff validation fail.
- Distinguish deterministic CI evidence from online model evaluation.

## Resources

- Run scripts/assess_phase.py for repeatable deterministic gates.
- Read references/phase-assessment-template.md before writing each phase assessment.
