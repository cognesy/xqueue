# Beads Execution Map

Create on approval, not before. The predecessor plan's gate was "create
and claim the Beads epic and Stone 0 task before tracked implementation",
and the same rule applies here.

## Epic

```text
bd create "House template alignment: configuration, workspace, packaging, \
declared artifacts" -t epic -p 2
```

Description carries the README's outcome, the four fixed decisions that
constrain execution (no re-layout, home instance stays default, XCFG
behind one adapter, every artifact gets a gate), and a pointer to this
plan directory.

## Tasks

One task per stone, each a child of the epic, in dependency order.

| Task | Type | Pri | Blocked by |
| --- | --- | --- | --- |
| Stone 0 — baseline, XCFG pin, install decision | chore | 1 | — |
| Stone 1 — plane map, parity matrix, parity gate | task | 2 | Stone 0 |
| Stone 2 — CLI dependencies become an extra | task | 2 | Stone 0 |
| Stone 3 — workspace marker, resolver, typed root | feature | 1 | Stone 0 |
| Stone 4 — XCFG adapter and layered precedence | feature | 1 | Stone 3 |
| Stone 5 — guardrails and record | task | 2 | 1, 2, 4 |

Stones 1, 2, and 3 are ready simultaneously once Stone 0 closes.

## Description Skeleton

Every task uses the structure that worked for epic `xqueue-4e8`, because
it is what made those twenty findings independently actionable:

```text
## Purpose
One sentence: what is true afterwards that is not true now.

## Context
File:line evidence from 01-evidence-and-current-state.md, plus the
template text it satisfies, quoted rather than paraphrased.

## Symptoms
What a reader or an operator hits today.

## Expected Outcomes
The observable end state.

## Specification
The concrete changes, named per file.

## Acceptance Criteria
Checkboxes that another agent can evaluate without judgement calls.

## Verification
The exact commands, including the planted-violation check where the
stone adds a gate.

## Cleanup
Stale artifacts to remove; close with
`bd close <id> -r "<what changed and how it was verified>"`.
```

## Operational Notes Carried Forward

These cost time during the previous epic and are recorded so they do not
again:

- never use `bd close --json`; it silently no-ops. Use
  `bd close <id> -r "reason"`.
- `bd list --parent <epic>` hides closed children without `--all`.
- do not run `bd` invocations in parallel; the embedded Dolt backend does
  not tolerate it.

## Reporting

Each stone closes with a STONE-LOG entry carrying Gate, Evidence,
Decision, and Next gate, and the bd close reason summarizes the same
facts. Superseded claims in earlier entries are annotated in place with a
pointer, never edited away.
