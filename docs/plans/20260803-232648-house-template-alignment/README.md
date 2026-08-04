# House Template Alignment

Align xqueue with the house reference architecture for agentic Python
multichannel applications, at the four edges where it currently diverges:
configuration, workspace identity, dependency weight, and declared
architecture artifacts.

Source of the rules:
`~/projects/_kb-docs/stepping-stones/templates/agentic-python-multichannel-app`
(`README`, `REFERENCE-STRUCTURE`, `CHANNELS`,
`CONVENTIONS-AND-GUARDRAILS`, `COMPOSITION-AND-EXTENSIONS`,
`WORKSPACES-AND-CONFIGURATION`, `ADOPTION`, `PLANE-MAP`) plus
`MODULE-ISOLATION.md`.

## Outcome

xqueue satisfies the template's Definition of Done for every item that
applies to a CLI-plus-SDK product, and each newly declared boundary is
backed by a gate rather than by prose.

Of the template's sixteen Definition-of-Done items, xqueue already meets
seven. This plan closes four. The remaining five — FastAPI, the web
client, the separately named remote client, plane failure drills, and
extension points — are not applicable to a CLI-plus-SDK single-machine
tool and are excluded by decision, not by omission.

## Architecture Decision

This is an alignment plan, not a re-architecture. The capability core is
already what the template asks for: typed actions own the use cases and
their transactions, one composition root wires them, a context-managed
`Xqueue` facade groups them by capability, the CLI holds all presentation,
and the dependency graph is enforced mechanically.

The divergences are all at the process edge — how the application decides
which workspace it operates on, how it composes settings, what it forces
an embedder to install, and which architecture facts it has written down.
Those are the four things this plan changes. No capability module changes
shape, and no action signature changes.

## Fixed Decisions

1. No re-layout to `src/xqueue/capabilities/<name>/`. Capabilities at the
   package top level with a sibling `xqueue_cli` package is an accepted
   deviation from the reference tree. The template itself says to adapt
   names to the domain and not to keep generic packages merely because
   they appear in the diagram. Moving 95 modules for directory cosmetics
   would spend the entire budget of this plan on nothing.
2. The machine-wide home instance stays the default scope. xqueue is a
   single-machine queue whose controller supervises pools across
   projects; a project workspace is additive, not a replacement.
3. XCFG is adopted behind exactly one app-owned adapter. `xcfg` types and
   exceptions never appear in an xqueue public signature or error
   contract.
4. Existing flat environment variables keep working unchanged.
5. The CLI's dependencies become an extra. `xq` stays a declared console
   script and fails with an actionable hint, not an `ImportError`
   traceback, when the extra is absent.
6. A declared artifact without a gate is not done. The plane map and the
   channel parity matrix each ship with a test that fails when the code
   and the document disagree.
7. Superseded claims in prior plan records are annotated in place with a
   pointer, never edited away.

## Explicit Non-Goals

- no FastAPI or REST channel;
- no web application or generated TypeScript client;
- no extension tiers of any kind — there is no second implementation of
  any seam and no optional heavy dependency to isolate;
- no split into several distributions;
- no physical plane separation, no second process, no deployment change;
- no alternate database or broker backend; and
- no change to job execution, leasing, retry, timeout, or cancellation
  semantics.

## Documents

1. [`01-evidence-and-current-state.md`](01-evidence-and-current-state.md)
   — what conforms today, what does not, with file evidence.
2. [`02-target-architecture.md`](02-target-architecture.md) — the target
   shape of each of the four edges.
3. [`03-migration-stones.md`](03-migration-stones.md) — six
   dependency-ordered stones with deltas and done-signals.
4. [`04-verification-and-rollback.md`](04-verification-and-rollback.md) —
   gate composition, new test lanes, risks, and rollback per stone.
5. [`05-beads-execution-map.md`](05-beads-execution-map.md) — the epic and
   task breakdown to create on approval.
6. `PLANE-MAP.md` — moved to [`docs/dev/plane-map.md`](../../dev/plane-map.md)
   when Stone 1 landed, together with its gate.
7. [`STONE-LOG.md`](STONE-LOG.md) — decisions and verification evidence.

## Review Gate

This plan is not implemented until the user approves it. On approval,
create the Beads epic and Stone 0 task before any tracked change, exactly
as the capability/SDK refactor did.

The predecessor plan is
`docs/plans/20260803-182325-capability-sdk-refactor/`, closed with all
twenty of its review findings resolved. This plan starts from that tree.
