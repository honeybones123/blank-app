# Runtime–V2 Integration Boundary

## Implemented status

Runtime consumes Inputs V2 as its sole Design Brain implementation through
Runtime-owned contracts, `DesignBrainPort`, and an installed
`beamapp-inputs-v2` distribution. Runtime does not locate a development checkout,
mutate `sys.path`, or select a legacy Design Brain implementation with a feature
flag.

V2 remains independent of Runtime internals: it owns calculation and Design
Brain decision behavior, while Runtime owns application composition, adaptation,
revision/hash coherence checks, and publication into the UI.

## Reproducibility contract

The clean-install contract must remain green for every boundary change. It:

1. creates a temporary Python environment;
2. builds and installs the current V2 checkout as a distribution;
3. starts the Runtime-owned adapter contract without access to V2's source-tree
   layout; and
4. verifies package version, source identity, revision/hash coherence, candidate
   adaptation, and Apply safety.

Runtime pins the supported distribution version and hashes the installed package
source. A clean checkout must therefore fail clearly when V2 is absent, has the
wrong version, or does not match the expected installed source.

## Remaining migration gates

Installed-package integration does not by itself complete the broader migration.
The following gates remain tracked in `V2_INTEGRATION_READINESS.md` and
`ACCEPTANCE_STATUS.md`:

- numerical parity for each calculation family as `legacy_snapshot` modules are
  replaced;
- complete family-ladder and serviceability/crack-control evidence;
- browser and visual regression coverage across supported beam workflows;
- incremental decomposition of Runtime page/shared-helper monoliths; and
- removal of obsolete rollback-era code only after equivalent behavior is
  covered by executable contracts.

## Recovery

A broken V2 release is recovered by reinstalling the last verified
`beamapp-inputs-v2` distribution and rerunning the clean-install contract. There
is no Runtime feature flag that silently changes decision authority back to a
legacy implementation.
