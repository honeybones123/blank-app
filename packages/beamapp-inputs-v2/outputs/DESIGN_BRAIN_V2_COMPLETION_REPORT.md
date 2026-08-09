# Inputs V2 Design Brain Architecture Recovery — Acceptance Report

**Generated:** 9 August 2026  
**Scope:** isolated `inputs-v2-lab`; V1/Runtime remained read-only.  
**Integration status:** not approved and not attempted.

## Outcome

The V2 Design Brain passes its complete offline acceptance gate. One classifier
selects one family. One `FamilyOwner` owns the ladder, ranking, stopping,
blocker, terminal status and CTA. Every candidate passes through one shared
validation gateway, and Apply executes only the exact typed proposal authorised
by the family decision.

The current Inputs V2 page and Design Brain visual shell were preserved.

## Implemented contracts

- Neutral candidate seeds with no hidden engineering mutation.
- Family-owned entry conditions, ordered stages, permitted changes, mandatory
  checks, improvement policy, ranking, exact-stop evidence, blocker wording,
  final proposal and CTA intent.
- One universal candidate gateway for validation, reinforcement fit, row
  arrangement, lock enforcement and calculation evidence.
- Private 0.60 ULS serviceability proxy when genuine SLS actions are absent;
  the proxy does not enter canonical inputs, summaries, saved data or exports.
- Explicit candidate records, stage counts, rejection codes, cache evidence,
  elapsed time, budget state and stop reasons.
- Practical one-row and two-row reinforcement candidates.
- Zero-shear cleanup that can remove unnecessary ligatures.
- Geometry/reinforcement proportion balancing with configurable bounded Fast
  and Detailed search profiles.
- Monotonic capacity-ceiling stopping for the weaker tail of bending
  reinforcement reductions.
- User width/depth locks preserved by the neutral seed and enforced at the
  universal candidate boundary.
- Calculation-owned clause metadata propagated without family/UI mappings.
- One shared family text contract, advice formatter and card projection.
- A typed `INPUT_REQUIRED` no-load outcome owned by a registered family
  contract. The UI only projects the outcome and contains no second no-load
  engineering decision path.

## Verification evidence

Latest complete offline gate:

- **349 tests passed**;
- **7 tests intentionally skipped**;
- architecture checker passed across **81 Python files**;
- shadow calculation parity report generated;
- **23/23** repair, optimisation, terminal, exact-stop and locked-outcome audit fixtures
  passed; and
- protected V1 Runtime git status was identical before and after the gate.

Representative recovery audit:

| Outcome | Family | Apply | Candidate evaluations |
|---|---|---:|---:|
| No design actions | `INPUT_REQUIRED` | No | 0 |
| Geometry/detailing failure | `GEOMETRY_DETAILING_GOVERNS` | Yes | 803 |
| Combined bending/shear failure | `BENDING_AND_SHEAR_FAIL_GOVERN` | Yes | 32 |
| Bending failure with shear cleanup | `BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS` | Yes | 113 |
| Shear failure with bending optimisation | `SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS` | Yes | 1185 |
| Bending failure | `BENDING_FAIL_GOVERNS` | Yes | 105 |
| Shear failure | `SHEAR_FAIL_GOVERNS` | Yes | 5 |
| Serviceability failure | `SERVICEABILITY_GOVERNS` | Yes | 960 |
| Combined overdesign | `COMBINED_OVERDESIGN` | Yes | 420 |
| Bending overdesign | `BENDING_OVERDESIGN_GOVERNS` | Yes | 1159 |
| Shear overdesign | `SHEAR_OVERDESIGN_GOVERNS` | Yes | 124 |
| Zero-shear ligature cleanup | `SHEAR_OVERDESIGN_GOVERNS` | Yes | 1 |
| Detailed minimum-shear failure below headline capacity | `SHEAR_FAIL_GOVERNS` | Yes | 889 |
| Exhausted compliant shear optimisation | `EXACT_STOP_PROVEN` | No | 5 |
| Exhausted compliant combined optimisation | `EXACT_STOP_PROVEN` | No | 16 |
| Target band | `TARGET_BAND_REACHED` | No | 0 |
| Locked bending failure | `BENDING_FAIL_GOVERNS` | No | 105 |
| Locked geometry/detailing failure | `GEOMETRY_DETAILING_GOVERNS` | No | 0 |
| Locked combined failure | `BENDING_AND_SHEAR_FAIL_GOVERN` | No | 24 |
| Locked bending/shear mixed failure | `BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS` | No | 88 |
| Locked shear/bending mixed failure | `SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS` | No | 91 |
| Locked shear failure | `SHEAR_FAIL_GOVERNS` | No | 91 |
| Locked serviceability failure | `SERVICEABILITY_GOVERNS` | No | 60 |

Performance fixtures prove:

- an already-balanced design runs the terminal path with zero candidate
  evaluations and zero calculation-cache misses;
- the no-load contract completes in approximately **0.64 ms**, with zero
  candidate evaluations and no Apply action;
- a passing bending-overdesign case is retained as a green PASS only after
  every permitted reinforcement and geometry stage completes, with the exact
  checks that rejected useful reductions preserved in the decision evidence;
- the same exact-stop rule is enforced for shear-only and combined overdesign,
  with no candidate or Apply action retained on terminal PASS;
- detailed shear failures below headline utilisation 1.0 enter the selected
  shear repair ladder rather than being reclassified by the pipeline;
- every overdesign ACTION is rejected unless it reduces longitudinal steel,
  transverse steel density or concrete area while preserving all mandatory
  checks;
- triggered Fast search remains below its configured 2500-evaluation budget;
- candidate count, cache hits/misses and elapsed time are published; and
- a configured consecutive-infeasible limit may stop only with recorded
  `monotonic_bending_capacity_ceiling_proven` evidence.

## Remaining boundary

V1 visual matching is not an acceptance requirement for this goal. The current
V2 shell, red/blue/green terminal states, expansion behaviour and Apply control
were preserved, and the live white no-load shell was verified in V2.

Production integration remains a separate approval checkpoint. No V1 module,
project, snapshot, persistence record or configuration was changed.

## Commands

```powershell
.\.venv\Scripts\python.exe tools\v2_acceptance_gate.py
.\.venv\Scripts\python.exe tools\architecture_check.py
.\.venv\Scripts\python.exe tools\design_brain_completion_audit.py
```
