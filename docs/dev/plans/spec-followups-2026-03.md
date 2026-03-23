# Spec Follow-Ups: March 2026

## Goal

Capture the remaining post-v1 follow-up work that is still reasonable to do
after the lease-renewal fix, without overstating low-value spec mismatches as
urgent engineering work.

## Review Basis

This plan is based on the completed spec-gap reassessment after the worker
lease-renewal task. That review already narrowed the list to five follow-up
items and ranked them pragmatically:

1. direct-mode controller restart should reload config
2. `jobs list` should support richer filtering and explicit sorting
3. explicit retention tooling should exist for old attempts, events, and log
   files
4. `xq worker` should support direct invocation as an alias to `xq worker run`
5. CLI exit codes may reserve a distinct timeout code where applicable

## Constraints

- Preserve the architecture rule: `apps -> actions -> services`.
- Keep CLI shells slim; do not let app commands call services directly.
- Preserve JSON output contracts unless a task explicitly evolves them.
- Prefer operator value and correctness over strict spec literalism.
- Avoid introducing abstractions that distort the local-first design.

## Task Breakdown

### 1. Controller config reload on restart

This is the most valuable remaining functional gap. The direct controller loop
currently keeps using one config snapshot through restart transitions.

### 2. Richer job inspection filters and sorting

This improves operator and agent ergonomics, especially for delayed and
backlogged work, but it is not a runtime correctness issue.

### 3. Retention and cleanup tooling

This is an operations maturity task. It should remain explicit and
operator-controlled rather than adding silent retention behavior.

### 4. Direct `xq worker` alias

This is mainly CLI/spec parity. It is low risk and low urgency.

### 5. Distinct timeout exit code

This is the lowest-value item. It should only touch the CLI error/exit-code
layer and should avoid inventing artificial timeout failures where the CLI does
not currently surface one.

## Priorities

- P1: controller config reload on restart
- P2: job list filters and sorting
- P3: retention tooling
- P4: direct `xq worker` alias
- P4: timeout exit code

## Risks

- Controller restart changes can affect long-running direct-mode behavior and
  must preserve current worker supervision semantics.
- Filtering/sorting changes can accidentally destabilize JSON output or command
  UX if not kept additive.
- Retention tooling must not silently remove data or conflict with current
  inspectability expectations.
- Low-value parity work should stay small and not sprawl into unrelated CLI
  refactors.

## Open Questions

- Whether retention should land as one command family or as separate targeted
  commands.
- Whether the direct worker alias should remain documentation-only compatible or
  become the preferred visible CLI form.
