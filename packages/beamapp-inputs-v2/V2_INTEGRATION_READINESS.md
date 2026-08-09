# Inputs V2 Design Brain — Integration Readiness

## Current production boundary

Runtime composes V2 as its sole Design Brain implementation through
`DesignBrainPort` and the installed `beamapp-inputs-v2` distribution. Runtime
does not locate the V2 checkout or mutate `sys.path`. The remaining gates below
concern parity completion and retirement of legacy calculation snapshots, not
whether V2 is connected.

## Current evidence

- V1 Runtime files remain read-only and are not imported at runtime.
- V2 owns the canonical input model, calculation adapter, candidate model, and Apply boundary.
- V1 family identifiers and priority order have a parity test.
- Copied bending and shear calculations have numerical parity fixtures.
- Combined failure, shear failure, bending failure, geometry/detailing, and overdesign paths are routed through the V2 orchestrator.
- Exact-stop and locked/no-repair outcomes expose evidence payloads.
- The architecture and automated test suites are executable release gates.
- Package installation and Runtime request/result coherence are covered by the
  clean-install integration contract.

## Remaining release gates

These are intentionally not marked complete:

1. Full serviceability calculation parity, including deflection and crack-control results.
2. Complete candidate ladders for every V1 family, including all mixed and terminal branches.
3. Browser proof for every detailed widget, candidate preview, stale Apply rejection, and rapid edits.
4. Pixel comparison of Design Guide cards and summary tables against V1 references.
5. Shadow-mode report comparing V1 and V2 results across normal, boundary, inactive, and invalid fixtures.
6. Versioned package publishing and deployment automation beyond the current
   reproducible two-checkout installation workflow.

Legacy calculation snapshots must not be deleted until their corresponding
family parity gates have authoritative evidence.
