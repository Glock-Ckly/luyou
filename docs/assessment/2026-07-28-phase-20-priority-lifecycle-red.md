# Phase 20 Assessment - Priority and Lifecycle Red Contract

## Scope

- Defined localhost no-token deployment without removing optional Gateway authentication.
- Defined DeepSeek priority reasoning and evidence-based lifecycle boundaries.
- Added Red assertions for explicit unfinished state, priority reason and Task-page color/group markers.

## DDD assessment

Planning owns initial priority and draft/ready mapping. Task owns persisted lifecycle. Verification alone
may authorize completion. HTTP authentication remains a Gateway concern; credentials remain outside all
domain and repository artifacts.

## TDD evidence

The Red tests must fail because `priority_reason`, `completion_state`, completion-group UI and explicit
light search-input colors are not implemented yet.

## Commit

Red contract commit: `ad9bfe1635df408ac40578cdf97bbb3637d47487`.
