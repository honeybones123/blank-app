# Design Guide Staged Verification Workflow

This workflow keeps verification proportional to the change. Start with the smallest proof that can catch the bug, then escalate only after the focused behaviour is green.

## Do Not Touch

- formulas
- solver maths
- target bands
- recommendation ranking, unless the task is explicitly a ranking/preference change
- Design Guide hard invariants
- existing verifier assertions
- golden matrix expectations
- previous-fixed expectations

## Stage 0 - Compile

Always run this first after code or verifier edits:

```powershell
python -m py_compile app.py inputs_page.py design_guidance_engine.py state_and_helpers.py tools/browser_live_design_guide_fuzz_verifier.py tools/run_design_guide_previous_fixes_gate.py tools/run_design_guide_golden_matrix.py tools/run_design_guide_fuzz_regression_gate.py tools/verification/check_regression_contracts.py
```

Stop on compile failure. Do not run browser checks until compile is clean.

For shared Design Brain candidate contract or alias-map changes, also run the
non-runtime structural preflight:

```powershell
python tools/verification/shared_candidate_contract_structure_check.py
```

This structural checker may fail only on shared candidate contract or alias-map
shape problems, such as invalid JSON, missing required alias-map sections,
malformed mapping rows, invalid enum values, or missing required mapping entries.
It must not inspect saved verification artifacts, run browser checks, load the
product runtime, or fail on semantic alias coverage gaps.

The optional alias coverage companion remains warning-only:

```powershell
python tools/verification/shared_candidate_alias_coverage_probe.py
```

The alias coverage probe may report `missing`, `ambiguous`, or
`high_risk_mismatch` findings, but those findings must not fail gates yet.
Saved-artifact coverage gaps, semantic split fields such as `safe`,
`executor_backed`, `preview`, `evidence`, and `apply_payload_ref`, and
exact-stop/blocker proof mappings remain non-failing until explicitly promoted
in a later phase.

## Fix Protection Rule

Every product, UI, verifier, evidence, or publication fix must prove two things:

1. The immediate issue is fixed.
2. The same failure mode cannot silently return.

A fix is not complete until:

- `py_compile` passes.
- The exact failing replay or case passes, or progresses past the original failure.
- The old failure mode is explicitly protected by a replay, gate, or verifier assertion.
- Any new failure is classified separately and is not mixed into the original fix.
- Artifact paths are reported.

Do not treat "the error disappeared once" as enough. The fix must be locked into recurring verification.

## Mandatory Verifier Impact Discipline

No product, UI, Design Guide, optimisation, repair, publication, contract,
selector, test-id, or evidence change is complete until verifier impact is
reviewed.

For every phase, record one of:

1. Verifier updated.
2. Verifier confirmed still valid.
3. Verifier update deferred with explicit reason and blocking status.

This rule exists because Phase 6.8 intentionally hid the raw lower Design Guide
details section from normal UI, while the previous-fixed verifier still required
`design-guide-details`. That stale verifier/layout contract expectation caused
the next previous-fixed run to fail `35/35` even though the product behaviour was
intentional.

### Verifier Impact Checklist

For every change, answer:

1. Did visible UI change?
   - If yes, update or confirm layout verifier selectors and visibility assertions.
2. Did any test ID, selector, CSS hook, or DOM structure change?
   - If yes, update or confirm verifier selectors.
3. Did any normal-user debug/details visibility change?
   - If yes, update or confirm verifier expectations for visible or hidden debug content.
4. Did Design Guide card/status/CTA behaviour change?
   - If yes, update or confirm the Design Guide outcome verifier.
5. Did publication priority/order change?
   - If yes, update or confirm stale-blocker and `ACTION`/`PASS`/`BLOCKED` assertions.
6. Did repair or optimisation behaviour change?
   - If yes, update or confirm repair/optimisation expectation ladders.
7. Did candidate aliases, candidate fields, or result payload shape change?
   - If yes, update or confirm the alias map, alias coverage probe, and shared candidate preflight.
8. Did a machine-readable contract change?
   - If yes, update or confirm the structural checker and all loaders/probes that consume it.
9. Did formulas, solver maths, or engineering checks change?
   - If yes, update or confirm formula, golden, and verifier expectations.
10. Did no verifier change appear necessary?
    - Record why the existing verifier still proves the new behaviour.

### Standard Phase Closeout

Every phase report must include:

- Verifier Impact:
  - Product/UI behaviour changed: YES / NO
  - Verifier updated: YES / NO / NOT REQUIRED
  - Reason:
  - Focused verifier run:
  - Broader verifier required before release: YES / NO
  - Drift risk remaining:

For confirmed product bugs, also run the regression-contract meta-verifier:

```powershell
python tools/verification/check_regression_contracts.py
python tools/verification/run_release_gate_manifest.py
python tools/verification/check_release_gate_manifest.py
python tools/verification/verifier_retirement_deletion_workflow.py
python tools/verification/design_guide_live_bug_registry_contract.py
python tools/verification/shared_bridge_dependency_binding_lock.py
python tools/verification/design_guide_legacy_visible_surface_deletion_lock.py
python tools/verification/design_brain_shared_path_release_lock.py
python tools/verification/design_guide_safe_optimal_blocker_publication_lock.py
python tools/verification/design_brain_family_smooth_operation_lock.py
```

The meta-verifiers must stay green before a product bug is called complete. They
check that the bug has a focused replay, global verifier invariant, permanent
regression-suite entry, named failure classification, never-regress rule, and
no missing late-bound extracted bridge dependency. Live/browser-observed bugs
must also be listed in `design_guide_live_bug_regression_registry.json` and
must have a focused verifier with a latest passing artifact before the app can
be called fully verified.

For each fix, answer this checklist:

1. What exact failure mode was fixed?
   Examples: route/evidence label parsed as numeric bar count; generic CTA without executor-backed payload; visible card family did not match payload family; `current_util` used attempted/rejected util; collapsed card leaked expanded body; summary parser read an expanded detail row instead of the top-level row.
2. What replay or gate now protects it?
   Examples: exact replay path; previous-fixed-groups replay; fuzz-regression replay; golden matrix case; focused layout replay.
3. What verifier assertion protects it?
   Examples: no generic CTA without executor-backed payload; ACTION means executable; blocker invalid if a safe executor-backed candidate exists; summary parser must read the top-level row only; route labels must not be applied as model updates.
4. Did the replay pass or progress past the original failure?
   If it fails on a new issue, report: `Original failure fixed. New failure classification: <classification>.`
5. Was the new failure patched?
   Patch the new failure only when explicitly approved, or when it is clearly inside the same scoped task.

For type-safety and evidence fixes, this invariant is permanent:

- Evidence labels, route labels, explanation labels, and `route_inventory` strings must never be applied as model update values.
- Only recognised model/update keys with valid values may be applied to synthetic state.
- Descriptive strings must remain evidence text only.

These descriptive strings must never be parsed as numeric update values:

- `combined bottom bar count trial`
- `shear links spacing trial`
- `shear links diameter trial`
- `section depth geometry trial`
- `section width geometry trial`

If such a value appears in `attempted_updates` or evidence maps:

- ignore it for synthetic-state application
- preserve it in evidence/explanation text
- do not cast it to `int` or `float`

## Stage 1 - Focused Replay

Run the exact replay or case that proves the changed behaviour. Do not run full gates first.

Examples:

- blocker wording change: run one replay that reaches `Why no further cleanup?`
- summary row UI change: run one focused summary/layout check
- false blocker fix: run the exact false-blocker replay
- button contract fix: run the exact CTA/payload replay

Exact replay command:

```powershell
python tools/browser_live_design_guide_fuzz_verifier.py --replay-case "<path-to-failure_case.json>" --port 9301
```

Optional helper:

```powershell
python tools/verification_quick_gate.py --mode focused --replay "<path-to-failure_case.json>" --port 9301
```

Focused ladder/case command:

```powershell
python tools/verification_quick_gate.py --tier focused --case <CASE_ID> --port 9301
```

Do not escalate until the focused replay passes, unless the user explicitly requests investigation-only broader coverage.

## Stage 2 - Sibling / Root-Cause Replays

If the bug belongs to a known root-cause group, run only sibling replays from that group:

- low-util blocker group
- action-family publication group
- layout/render group
- stale recompute group
- display-util mismatch group

Use exact replays when available. The goal is to prove the shared root cause, not the whole product.

## Stage 3 - Relevant Gate Only

Run the smallest full gate that protects the changed area:

- previous-fixed-groups for old fixed bugs
- golden matrix for canonical matrix behaviour
- fuzz-regression gate for promoted fuzz failures
- layout gate for layout-only changes
- matrix-variant gate for controlled variants, when present

Do not run all gates automatically unless the change touches shared Design Guide publication or render logic.

Commands:

```powershell
python tools/run_design_guide_previous_fixes_gate.py --port 9301
python tools/run_design_guide_golden_matrix.py --port 9301
python tools/run_design_guide_fuzz_regression_gate.py --port 9301
```

## Stage 4 - Full Deterministic Baseline

Only after focused and sibling replays are green, run the deterministic baseline:

```powershell
python tools/run_design_guide_previous_fixes_gate.py --port 9301
python tools/run_design_guide_golden_matrix.py --port 9301
python tools/run_design_guide_fuzz_regression_gate.py --port 9301
```

If any gate fails, stop before fuzz and inspect the first failed replay artifact.

## Stage 5 - Fuzz

Run fuzz only after deterministic gates are green.

Small fuzz first:

```powershell
python tools/browser_live_design_guide_fuzz_verifier.py --max-cases 10 --session-steps 5 --mutations-per-case 4 --headless --port 9301 --no-stop-on-first-failure
```

Then 50-case investigation:

```powershell
python tools/browser_live_design_guide_fuzz_verifier.py --max-cases 50 --session-steps 5 --mutations-per-case 4 --headless --port 9301 --no-stop-on-first-failure
```

Fuzz is investigation unless the deterministic baseline is green.

## Stage 6 - Fully Verified Family Lock

The app is not fully verified unless every Design Brain family has a current
live family lock. This gate runs the family-specific contract, ladder,
10-fuzz/live browser, CTA/apply, target-band/blocker, publication, render, and
shared-lock checks for every supported family.

The universal family lock must also prove logical ladder traversal for every
family. A family lock is not sufficient unless it records:

- contract ladder order
- candidate generation per lane
- candidate rejection reasons
- ranking / selected best candidate proof
- same-click folding where a family can otherwise publish partial cleanup
- terminal result after Apply, or exact-stop/blocker proof
- no live browser red-screen sentinel finding: `Traceback`, `NameError`,
  Streamlit duplicate-key/runtime error, stale primary payload blocker, or
  Design Guide family contract violation card

The same gate must also prove final Design Guide text/formatting authority:

- visible title, badge, colour/tone, summary, blocker explanation, and CTA are
  derived from `FinalDesignGuidePublication`
- formatting is produced by `design_brain.final_design_guide_formatter`
- HTML is rendered by `ui.final_design_guide_card` as render-only output
- no family-specific page fallback may invent visible card text or formatting
- the live card is hash-stamped with publication/display/CTA authority hashes

Run this only after the focused gates, deterministic baseline, and relevant fuzz
checks are green:

```powershell
python tools/verification/shared_bridge_dependency_binding_lock.py
python tools/verification/design_guide_legacy_visible_surface_deletion_lock.py
python tools/verification/design_guide_live_bug_registry_contract.py
python tools/verification/run_release_gate_manifest.py
python tools/verification/check_release_gate_manifest.py
python tools/verification/verifier_retirement_deletion_workflow.py
python tools/verification/design_brain_shared_path_release_lock.py
python tools/verification/design_guide_browser_visual_layout_lock.py
python tools/verification/design_guide_safe_optimal_blocker_publication_lock.py
python tools/verification/design_brain_universal_live_family_lock.py --run-live --port 9301
python tools/verification/design_brain_family_smooth_operation_lock.py
python tools/verification/design_brain_universal_verification_meta_lock.py --enforce
python tools/verification/app_stability_goal_completion_audit.py
```

`app_stability_goal_completion_audit.py` must not report `COMPLETE` unless the
latest universal live family lock artifact has `universal_lock_status=LOCKED`
and the latest universal verification meta-lock artifact has
`meta_lock_status=LOCKED`.
Running `design_brain_universal_live_family_lock.py` without `--run-live` is
inspection-only and must not be used to claim full verification.
Running `design_brain_universal_verification_meta_lock.py` without `--enforce`
is audit-only and must not be used as a release gate.

## Runtime Rules

1. Clear only processes attached to port `9301` before each focused run.
2. If a focused replay hangs for more than 20 minutes, stop and classify it as runtime/readiness unless a visible product contradiction artifact exists.
3. If a full gate hangs, inspect partial artifacts and the active replay before patching.
4. Never treat a timeout as a product failure unless a browser-state artifact captures a visible product contradiction.
5. If a standalone replay passes but the full gate fails on that same replay, classify it as likely readiness/full-sequence issue and rerun once clean before product patching.

## Classification Rules

- Product contradiction: browser state and visible UI prove an impossible or misleading product state.
- Verifier/readiness issue: browser state is missing, app did not settle, probe timed out, or no visible contradiction was captured.
- Stale process issue: a non-test server or old browser/verifier tree was attached to the requested port.
- Full-sequence issue: standalone replay passes but gate sequence fails on the same replay after shared setup or prior cases.

Patch only product code after a fresh artifact captures a visible product contradiction.

## Artifact Expectations

- Focused replay artifacts live under `artifacts/verification/live_fuzz/replay_<timestamp>/`.
- Full gate reports live under `artifacts/verification/`.
- Fuzz-regression reports live under `artifacts/verification/fuzz_regression_gate_<timestamp>.json`.
- Investigation-only reports live under `artifacts/investigation/`.

Report the artifact path, pass/fail count, failure classification, and exact next replay command after each stage.

After every fix, report:

- Files changed
- Exact failure fixed
- Original artifact path
- Exact replay command run
- Result: passed / progressed past original failure / failed same way
- Replay or gate that now protects the failure
- Verifier invariant that now protects it
- New failure classification, if any
- Whether broader gates are still required
