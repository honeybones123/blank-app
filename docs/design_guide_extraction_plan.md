# Design Guide Separation Plan

Goal: separate the Design Guide page, Design Brain logic, and verification
runners from `inputs_page.py` without changing formulas, solver truth, or
verification expectations during the extraction.

## Current Boundaries

- `design_brain/` owns extracted decision logic.
- `design_guidance_engine.py` is a compatibility wrapper into `design_brain.engine`.
- `tools/verification/runners/` owns verification runners.
- `inputs_page.py` still owns most Streamlit Design Guide orchestration and rendering.
- `design_guide_page.py` now owns the page mounting boundary for the Design Guide
  placeholder, final panel, and debug-sidebar entrypoint.

## Staged Extraction

1. Page Mount Boundary
   - Keep behavior unchanged.
   - Route placeholder, final panel mounting, and debug-sidebar entrypoints through
     `design_guide_page.py`.
   - Leave solver, summary truth, and recommendation contracts untouched.

2. Page Rendering Boundary
   - Move pure visual card rendering helpers out of `inputs_page.py`.
   - Keep callbacks injected from `inputs_page.py` until the controller boundary is stable.
   - Verify rendered CTA state and executor-backed payload still match.

3. Controller Boundary
   - Move Design Guide state orchestration into a controller module.
   - Inputs should pass current state, callbacks, and containers; the controller should
     return the render contract and side effects explicitly.
   - Preserve trace fields used by verifiers.

4. Contract Boundary
   - Keep recommendation/result and executor payload construction in one contract layer.
   - Avoid duplicating button action logic between UI and verifier helpers.
   - Verify `apply_resolved_candidate` contract truth against rendered CTA truth.

5. Verification Boundary
   - Keep production app code free of verifier-only logic.
   - Verifiers should consume browser behavior, public contracts, and artifacts.
   - Shared assertion helpers can live under `tools/verification/helpers/`.

## Non-Goals During Extraction

- Do not change engineering formulas.
- Do not change summary truth policy.
- Do not change target-band expectations.
- Do not rewrite verification ladders unless UI tokens or public contracts actually change.
