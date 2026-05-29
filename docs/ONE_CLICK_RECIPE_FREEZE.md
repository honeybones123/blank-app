# One-Click Recipe Freeze

This document freezes the common base beam and the six clean-start reproduction recipes used for one-click optimisation verification.

Core rule:
- Every recipe begins from a clean app run or a fresh harness import.
- The base beam is immutable unless the recipe explicitly lists a change.

## Frozen Base Beam

- Clean-start required: yes
- Base beam rule: immutable reference input for all recipes unless the recipe explicitly changes a value
- Target band: `0.88` to `0.95`
- Objective / mode: `balanced`
- Design action source: `Manual design actions (inputs below)` / `actions_mode = manual`
- Section type: `RECT`
- Support context: `Simply supported`, `Single span`
- Geometry:
  - `b = 300 mm`
  - `bw = 300 mm`
  - `D = 400 mm`
  - `bf = 600 mm`
  - `tf = 120 mm`
  - `bf_bot = 600 mm`
  - `tf_bot = 120 mm`
- Materials:
  - `fc = 40 MPa`
  - `fsy = 500 MPa`
  - `phi_bend = 0.85`
  - `phi_shear = 0.75`
- Longitudinal reinforcement:
  - Top: `2N10`
  - Bottom: `4N16`
  - Row spacing: top `200 mm`, bottom `200 mm`
- Shear reinforcement:
  - `lig_d = N10`
  - `lig_legs = 2`
  - `s_lig = 150 mm`
- Other toggles:
  - `shear_auto_design = false`
  - `shear_optimize_reinforcement = false`
  - `shear_zone_enabled = true`
  - `loads_edit_mode = ULS`
- Frozen design actions:
  - `Mu = 100 kNm`
  - `Vu = 180 kN`
  - `Nu = 0`

This frozen base beam evaluates to:
- `bending util = 0.912009041065849`
- `shear util = 0.9167006518180297`
- all key checks `PASS`

## Recipe 1 — Bending Overdesigned, Mild

- Recipe name: `R1_bending_over_mild`
- Purpose: verify bending-only overdesign optimisation returns toward the target band from a clean start
- Clean-start required: yes
- Base beam: frozen base beam above
- Target band: `0.88` to `0.95`
- Objective / mode: `balanced`
- Design action source: `Manual design actions (inputs below)`
- Section type: `RECT`
- Geometry: frozen base geometry
- Materials: frozen base materials
- Longitudinal reinforcement: change bottom from `4N16` to `5N16`
- Shear reinforcement: frozen base shear reinforcement
- Other toggles: frozen base toggles
- Recipe change from base: `bot1_count = 5`
- Expected starting condition: bending overdesign governs; shear remains passing and non-governing
- Expected optimisation direction: reduce excess bending capacity toward the target band
- Acceptable stop condition: only a real minimum geometry / bar layout / constructability lower bound
- Must not happen: shear optimises instead of bending; stale final value; target-band success without final recompute

## Recipe 2 — Bending Overdesigned, Moderate

- Recipe name: `R2_bending_over_moderate`
- Purpose: verify the same bending-only overdesign path works farther from the target band
- Clean-start required: yes
- Base beam: frozen base beam above
- Target band: `0.88` to `0.95`
- Objective / mode: `balanced`
- Design action source: `Manual design actions (inputs below)`
- Section type: `RECT`
- Geometry: frozen base geometry
- Materials: frozen base materials
- Longitudinal reinforcement: change bottom bar diameter from `N16` to `N20`
- Shear reinforcement: frozen base shear reinforcement
- Other toggles: frozen base toggles
- Recipe change from base: `db_bot_1 = 20`
- Expected starting condition: bending overdesign governs more strongly than Recipe 1
- Expected optimisation direction: reduce excess bending capacity toward the target band
- Acceptable stop condition: only a real lower-bound geometry/detailing limit
- Must not happen: wrong-domain optimisation; stale governing util; silent fake success

## Recipe 3 — Bending Overdesigned, Strong

- Recipe name: `R3_bending_over_strong`
- Purpose: stress test bending-only overdesign behaviour at a clearly excessive bending-capacity level
- Clean-start required: yes
- Base beam: frozen base beam above
- Target band: `0.88` to `0.95`
- Objective / mode: `balanced`
- Design action source: `Manual design actions (inputs below)`
- Section type: `RECT`
- Geometry: frozen base geometry
- Materials: frozen base materials
- Longitudinal reinforcement: change bottom bar diameter from `N16` to `N24`
- Shear reinforcement: frozen base shear reinforcement
- Other toggles: frozen base toggles
- Recipe change from base: `db_bot_1 = 24`
- Expected starting condition: strong bending overdesign governs; this is the largest bending overdesign case
- Expected optimisation direction: still optimise the bending domain back toward the target band
- Acceptable stop condition: only a real minimum geometry / spacing / cover / constructability limit
- Must not happen: fake target-band success; wrong-domain optimisation; nondeterministic clean-start outcome

## Recipe 4 — Shear Overdesigned Family

- Recipe name: `R4_shear_over_family`
- Purpose: verify shear-only overdesign optimisation works from mild to strong excess shear capacity
- Clean-start required: yes
- Base beam: frozen base beam above
- Target band: `0.88` to `0.95`
- Objective / mode: `balanced`
- Design action source: `Manual design actions (inputs below)`
- Section type: `RECT`
- Geometry: frozen base geometry
- Materials: frozen base materials
- Longitudinal reinforcement: frozen base longitudinal reinforcement
- Shear reinforcement: start from frozen base and apply exactly one of these subcase changes
- Other toggles: frozen base toggles
- Recipe change from base:
  - `R4A_shear_over_mild`: `s_lig = 125 mm`
  - `R4B_shear_over_moderate`: `s_lig = 100 mm`
  - `R4C_shear_over_strong`: `s_lig = 75 mm`
- Expected starting condition: shear overdesign governs; bending remains passing and non-governing
- Expected optimisation direction: reduce excess shear capacity toward the target band using true post-commit shear truth
- Acceptable stop condition: only minimum shear reinforcement / minimum permitted detailing / minimum spacing-leg arrangement limits
- Must not happen: bending optimises instead of shear; stale shear truth after commit; target-band success without post-commit recompute

## Recipe 5 — Combined Underdesign

- Recipe name: `R5_combined_underdesign`
- Purpose: verify combined bending + shear underdesign is solved as a combined problem, not by stale single-domain truth
- Clean-start required: yes
- Base beam: frozen base beam above
- Target band: `0.88` to `0.95`
- Objective / mode: `balanced`
- Design action source: `Manual design actions (inputs below)`
- Section type: `RECT`
- Geometry: frozen base geometry
- Materials: frozen base materials
- Longitudinal reinforcement: reduce bottom from `4N16` to `3N16`
- Shear reinforcement: relax spacing from `150 mm` to `200 mm`
- Other toggles: frozen base toggles
- Recipe change from base: `bot1_count = 3`, `s_lig = 200 mm`
- Expected starting condition: combined underdesign with both bending and shear materially part of the governing picture
- Expected optimisation direction: recompute both domains and land the final governing utilisation inside the target band
- Acceptable stop condition: none unless a genuine enforced bound makes target unreachable
- Must not happen: bending fixed while shear stays stale; shear fixed while bending stays stale; stale single-domain final util; preview/commit mismatch

## Recipe 6 — Overdesign Verification Trio

- Recipe name: `R6_overdesign_verification_trio`
- Purpose: final overdesign verification across isolated and combined cases after the recipes are frozen
- Clean-start required: yes
- Base beam: frozen base beam above
- Target band: `0.88` to `0.95`
- Objective / mode: `balanced`
- Design action source: `Manual design actions (inputs below)`
- Section type: `RECT`
- Geometry: frozen base geometry
- Materials: frozen base materials
- Longitudinal reinforcement / shear reinforcement: apply exactly one subcase below
- Other toggles: frozen base toggles
- Recipe change from base:
  - `R6A_bending_over_verify`: `db_bot_1 = 20`
  - `R6B_shear_over_verify`: `s_lig = 100 mm`
  - `R6C_both_over_verify`: `bot1_count = 5`, `s_lig = 125 mm`
- Expected starting condition:
  - `R6A`: bending controls overdesign
  - `R6B`: shear controls overdesign
  - `R6C`: both bending and shear are overdesigned
- Expected optimisation direction: reduce excess conservatism without solving the wrong domain
- Acceptable stop condition: only a real minimum geometry or minimum shear-detailing bound
- Must not happen: wrong-domain optimisation; fake target-band success; stale recommendation/card state; commit truth differing from preview truth
