# Structural App Architecture

Source of truth, solver flow, and patch guardrails.

This app uses a layered architecture. Do not collapse layers. Do not bypass layers.
Do not let UI presentation become engineering truth.

## 1. Layered Information Flow

### Layer 1 - Widget Layer

Purpose:
- User-facing controls only.
- Examples: `inputs_*`, `bending_*`, `shear_*`, `crack_*`, `defl_*` widget keys.

Rules:
- Widgets are not canonical truth.
- Widgets must not directly own solver state.
- Widgets may be stale or transient during edits.

### Layer 2 - Sync / Contract Layer

Purpose:
- Controlled mapping between widgets and shared canonical state.
- Examples: `TAB_KEYS`, `get_sync_callbacks()`, `hydrate_active_page_widgets_from_shared()`.

Rules:
- This layer protects architecture.
- Page code must not freely write shared state outside the established contract.
- Widget-to-shared synchronization must stay explicit and reversible.

### Layer 3 - Shared Canonical State Layer

Purpose:
- Single source of truth for the current beam/app state.
- Examples: `SHARED_DEFAULTS` values, canonical geometry, actions, reo, shear settings.

Rules:
- This is the app's main truth store.
- All pages must converge back to this state.
- Do not create competing state brains.

### Layer 4 - Derived / Resolved State Layer

Purpose:
- Expand canonical state into engineering-ready resolved state.
- Examples: resolved design actions, row-model resolution, legacy mirror rebuilding,
  effective depths, canonical pack rebuilds, normalized final shear truth.

Rules:
- Purely derived from canonical state.
- Must not invent independent truth.
- Must not mutate architecture casually.

### Layer 5 - Domain Solver / Check Layer

Purpose:
- Engineering calculations for bending, shear, crack, deflection, torsion, and supporting checks.

Rules:
- Solvers read resolved/canonical state.
- Solvers return status, util, reason, and details.
- Solvers do not own UI or session architecture.

### Layer 6 - Truth / Publication Layer

Purpose:
- Normalize domain outputs into publishable app truth.
- Examples: summary packs, governing result selection, final published shear truth,
  and PASS / FAIL / INFO / INVALID meaning.

Rules:
- One canonical published truth per check family.
- No contradictory UI truths for the same engineering state.
- Guidance must read from this layer, not bypass it.

### Layer 7 - Guidance / Recommendation Layer

Purpose:
- Decide what the next move is.
- Examples: Design Guide items, rescue vs optimise logic, candidate generation,
  family selection, ranking, pending recommendation creation.

Rules:
- Guidance reads published truth.
- Guidance does not rewrite engineering truth.
- Rescue and optimise are separate modes.
- A blocked/non-compliant candidate must not be treated as a valid one-click action.

### Layer 8 - Commit / Apply / Audit Layer

Purpose:
- Turn a recommendation into an actual state change safely.
- Examples: pending recommendation, one-click apply, commit preview,
  post-commit validation, rollback.

Rules:
- Preview truth and committed truth must align.
- Invalid candidates must be blocked before commit where possible.
- Post-commit audit remains the last safety net, not the primary selection filter.

### Layer 9 - Presentation Layer

Purpose:
- Show the user what the app knows.
- Examples: summary tables, Design Guide cards, banners, button labels,
  advisory vs actionable states.

Rules:
- Presentation must reflect solver/commit truth honestly.
- UI must never overstate what one-click can actually do.
- A blocked candidate must not be presented like a normal executable action.

## 2. Core Principles

- Shared state is the source of truth.
- Widgets are inputs, not truth.
- Derived state must be rebuilt from canonical state.
- Solvers read truth but do not own UI.
- Guidance reads published truth but does not invent it.
- Commit/audit decides whether a recommendation is actually safe.
- Presentation reflects commit eligibility honestly.

The app should follow this chain:

```text
Widgets
-> Sync contract
-> Shared canonical state
-> Derived/resolved state
-> Domain checks
-> Published truth
-> Guidance/recommendation
-> Commit/audit
-> Presentation
```

Not:

```text
Widgets
-> solver
-> UI
```

## 3. Mode Separation

### Underdesign / Rescue Mode

Purpose:
- Fix failing designs.

Rules:
- Candidates must clear current FAILs to be valid one-click rescue actions.
- A preview-failing rescue candidate must not be presented as executable.

### Overdesign / Optimise Mode

Purpose:
- Reduce excess design while keeping compliance.

Rules:
- Only runs on all-pass / eligible states.
- Must not be mixed with rescue logic.
- Local cleanup must not be mislabeled as overall governing optimisation.

Do not merge rescue and optimise flows.

## 4. UI Honesty Rules

1. If a candidate is commit-eligible, show the normal actionable CTA.
2. If a candidate is blocked, keep the explanatory banner/message, render it as advisory/blocked,
   and do not present it as a normal runnable one-click action.
3. If a card is visible but not actionable, UI must not imply the user can execute it directly.
4. Presentation must not be stronger than solver truth.

## 5. Patch Guardrails

When patching:
- Use the smallest possible patch.
- Touch the fewest functions possible.
- Do not do opportunistic cleanup.
- Do not do broad refactors.
- Do not rename for style.
- Do not move code unless explicitly required.
- Preserve debug and audit hooks.
- Preserve the session-state contract.

Do not change unless explicitly required:
- Shared/widget key mapping model.
- Pending recommendation propagation model.
- Commit audit model.
- Publish/finalize flow.
- Solver family ranking.
- Rescue vs optimise separation.
- Engineering formulas.

## 6. Required Patch Workflow

Before patching, identify:
- Exact functions to inspect.
- Exact architectural layer involved.
- Exact minimal patch surface.
- Contracts that must remain untouched.

After patching, report:
- Exact functions changed.
- Exact logic changed.
- Why this is the smallest safe patch.
- Architectural contracts preserved.
- What was explicitly not changed.
- Verification checklist.

## 7. App-Specific Safety Rule

Do not let a recommendation look more executable than it really is.

That means:
- Blocked preview-failing candidates must not look like normal one-click actions.
- Guidance must not outrun commit truth.
- Presentation must not outrun guidance truth.
- UI polish must not come at the cost of architectural drift.

This app is near-finished. Behave like a maintainer protecting architecture, not a code improver chasing elegance.
