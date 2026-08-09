# Inputs V2 acceptance status

This file is the living evidence register for the Modular Rebuild Plan. V2 is
now the sole Design Brain implementation composed by Runtime through an
installed-package adapter. Runtime owns that adapter; V2 remains independent
of Runtime modules.

## Verified

- [x] Standalone Streamlit process and isolated source tree.
- [x] Immutable canonical input/result models with source revision and hash.
- [x] One validated application command boundary for input mutation.
- [x] Fixture calculation with revision-aware publication.
- [x] In-memory and versioned JSON repository contracts.
- [x] Typed diagram view model and component-owned rendering.
- [x] Typed report/export request and artifact boundary with stale-request
      rejection (fixture exporter only; production formats remain pending).
- [x] Typed batch-design boundary preserving per-beam revisions (UI and
      production calculation integration remain pending).
- [x] Domain, engineering, layer-direction, Runtime-reference, and CSS checks.
- [x] AppTest widget edit, atomic validation, default values, and diagram update.
- [x] Performance and stale Design Brain proposal tests.
- [x] Browser smoke test on a separate localhost port.
- [x] Isolated session save/load and revision-tagged fixture report download;
      no Runtime persistence or report implementation is used.
- [x] Single production-engineering adapter seam with revision-tagged result
      rejection; the approved Runtime formula implementation remains pending.
- [x] Deterministic Design Brain proposal producer and canonical, stale-safe
      apply test; production recommendation source remains pending.
- [x] Isolated Design Brain fixture proposal is exposed through a typed UI
      action and AppTest; production Design Brain remains pending.
- [x] Versioned JSON persistence is exposed as an explicitly isolated lab
      action; production persistence and navigation remain pending.
- [x] Canonical revision/hash input snapshots are downloadable as typed JSON
      evidence from the isolated lab; production export formats remain pending.
- [x] The isolated fixture report boundary now exposes HTML, CSV, and a valid
      deterministic one-page PDF evidence download with revision-tagged
      stale-request protection; production report parity remains pending.
- [x] Successful fixture calculations expose a revision-tagged completion
      state in the page without replacing non-destructive validation errors.
- [x] Presentation calculation requests now pass through the application
      `CalculationCoordinator`; the page does not call the engineering
      calculator directly.
- [x] Batch calculation requests use an application-owned fixture boundary;
      the page does not construct engineering calculators directly.
- [x] Persistence and fixture report construction are behind application-owned
      lab-service seams; the Streamlit entry point has no direct infrastructure
      imports.
- [x] The architecture checker mechanically rejects summary-table code, which
      is outside the approved V1 visual contract.
- [x] V2 builds as the `beamapp-inputs-v2` distribution and Runtime consumes
      it through normal package discovery without an absolute checkout path or
      `sys.path` mutation.
- [x] A clean-install Runtime integration contract builds V2 into a temporary
      environment and proves revision/hash/source-manifest coherence.

## Pending evidence

- [ ] Capture current Runtime reference PNGs for every manifest state and
      viewport. Default and expanded desktop captures now exist; remaining
      states/viewports are still pending.
- [ ] Capture matching V2 PNGs and run the agreed image-diff threshold.
- [ ] Approve/document intentional visual differences, if any.
- [ ] Replace fixture calculation through one parity-tested engineering adapter.
- [ ] Add isolated persistence and full navigation/per-beam browser coverage.
- [ ] Reproduce batch design, save/load, engineering updates, and all current
      report/PDF/export actions behind V2 ports and typed view models.
- [ ] Add the remaining family-by-family visual slices and acceptance evidence.
- [x] Prepare (but do not apply) the integration proposal and rollback
      procedure template; applying it remains approval-gated.

The proposal and rollback template are prepared in
`outputs/INPUTS_V2_INTEGRATION_PROPOSAL.md`; the acceptance prerequisites and
owner approval are still pending.

## Current integration state

V2 is authoritative for Runtime Design Brain and calculation publication
through Runtime-owned neutral contracts and adapters. The repositories remain
separate and V2 is installed into Runtime's Python environment. Visual parity,
remaining family coverage, and replacement of legacy snapshot calculations are
still migration gates; they no longer imply that V2 is unused by Runtime.

## Change rule

Runtime/V2 boundary changes require the clean-install contract plus V2's
architecture and test suites. Calculation-family replacement additionally
requires numerical parity and browser evidence before legacy deletion.
