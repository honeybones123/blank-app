# Design Guide Verification

All active Design Guide verification runners now live under `tools/verification`.
Root-level scripts in `tools/` are compatibility wrappers only.

## Runners

Run from the repository root.

| Runner | Purpose | Command |
| --- | --- | --- |
| `real_user_design_guide_ladder.py` | Browser-live Design Guide card, CTA, click, post-click, payload-binding, and active-failure checks. | `python tools/verification/runners/real_user_design_guide_ladder.py` |
| `local_cleanup_apply_effectiveness_ladder.py` | Focused one-click local-cleanup effectiveness and post-click accepted-state checks. | `python tools/verification/runners/local_cleanup_apply_effectiveness_ladder.py` |
| `recommendation_contract_ladder.py` | Browser-live recommendation contract and apply-path binding checks. | `python tools/verification/runners/recommendation_contract_ladder.py` |
| `optimisation_expectation_ladder.py` | Optimisation expectation checks for target-band, overdesign, and unnecessary strengthening. | `python tools/verification/runners/optimisation_expectation_ladder.py` |
| `shear_overdesign_ladder.py` | Focused shear-overdesign diagnostic and freeze-blocking optimisation-gap checks. | `python tools/verification/runners/shear_overdesign_ladder.py` |
| `summary_truth_ladder.py` | Summary/status truth checks, including false pass/fail and target-band wording. | `python tools/verification/runners/summary_truth_ladder.py` |
| `matrix_chooser_verifier.py` | Required browser-live matrix chooser gate for active-failure/serviceability/terminal matrix cases. | `python tools/verification/runners/matrix_chooser_verifier.py` |
| `golden_matrix_runner.py` | Mandatory deterministic 14-case Design Guide golden matrix gate. | `python tools/run_design_guide_golden_matrix.py --port 9301` |
| `super_verification.py` | Freeze gate wrapper. Runs the required child gates and writes split super artifacts. | `python tools/verification/runners/super_verification.py` |
| `verification_quick_gate.py` | Tiered workflow runner for focused, local, and freeze verification loops. | `python tools/verification/runners/verification_quick_gate.py --tier local` |

## Helpers

| Helper | Purpose |
| --- | --- |
| `helpers/browser_helpers.py` | Shared browser/session helpers used by browser-live ladders. |
| `helpers/browser_one_click_regression.py` | Shared one-click tracer and browser helpers retained for compatibility. |
| `helpers/overdesign_assertions.py` | Shared unresolved material-overdesign verifier assertion. |
| `helpers/artifact_helpers.py` | Small artifact directory helpers. |
| `helpers/truth_assertions.py` | Shared simple status/truth predicates. |

## Recipes

`recipes/one_click_recipe_defs.py` contains shared browser recipe/state definitions.

## Artifacts

New verifier artifacts are written under:

- `artifacts/verification/latest/`
- `artifacts/verification/latest/super_verification_runs/<timestamp>/`

Old generated outputs have been moved under:

- `artifacts/verification/history/`
- `artifacts/verification/archived/`

## Staged Design Guide Workflow

The staged workflow lives in:

```text
tools/verification/VERIFICATION_WORKFLOW.md
```

After a patch, start with compile and the exact focused replay/case that proves
the behaviour. Do not run previous-fixed, golden, or fuzz-regression before the
focused proof unless the user explicitly asks for a broad investigation.

The fixed replay gate is:

```powershell
python tools/run_design_guide_previous_fixes_gate.py --port 9301
```

The golden matrix gate is:

```powershell
python tools/run_design_guide_golden_matrix.py --port 9301
```

## Mandatory Freeze Gates

Before trusting a GREEN/freeze result, run:

```powershell
python tools/verification/runners/verification_quick_gate.py --tier freeze
```

The underlying super runner is:

```powershell
python tools/verification/runners/super_verification.py
```

Super verification first runs the previous fixed groups gate and the golden
matrix gate. It also treats `matrix_chooser_verifier.py` as a required child
gate. GREEN/freeze cannot pass unless those gates pass in browser-live mode.

The old commands still work through wrappers, for example:

```powershell
python tools/browser_real_user_design_guide_ladder.py --help
python tools/super_verification.py --help
```
