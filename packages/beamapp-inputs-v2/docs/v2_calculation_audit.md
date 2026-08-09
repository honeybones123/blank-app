# V2 Calculation Audit

This matrix compares the Runtime summary/check contract with the current V2
authoritative calculation result. It is an audit record, not a substitute for
the calculation contract.

| Runtime check | V2 owner | V2 output currently available | Summary row | Action |
|---|---|---|---|---|
| Positive bending | `legacy_snapshot_calculator.bending` | `phi_Mu_kNm`, `M_star_kNm`, `util`, `status` | Partial | Add exact row contract and status |
| Minimum tensile reinforcement | bending calculation | `Ast_tension_mm2`; `Ast_min_mm2` placeholder | Partial | Copy Runtime `As,min` calculation |
| Minimum design capacity requirement | bending calculation | `minimum_capacity_knm` placeholder | Partial | Copy Runtime `Mcr`/minimum-capacity calculation |
| Ductility limit | `ductility` family | `ku`, `limit`, `util`, `status` | Partial | Propagate exact row values |
| Service bending moment | bending/serviceability boundary | `service_moment_knm` | Partial | Preserve explicit SLS-only semantics |
| Sectional shear capacity | `shear` family | `V_eq`, `phi_Vu`, `Vuc_kN`, `Vus_kN`, `Vu_total_kN`, `shear_ok` | Partial | Add exact Runtime row mapping |
| Torsion cracking check | `shear` family | `Tcr_kNm`, torsion fields | Missing | Add explicit check result/status |
| Web-crushing strength | `shear` family | `Vu_max_kN`, `web_ok` | Partial | Add exact row mapping/status |
| Design creep coefficient | `creep_shrinkage` | Only `k3_age_loading` | Missing | Add authoritative creep result |
| Final creep coefficient | `creep_shrinkage` | Missing | Missing | Copy Runtime final coefficient calculation |
| Creep strain | `creep_shrinkage` | Missing | Missing | Copy Runtime strain calculation |
| Autogenous shrinkage | `creep_shrinkage` | Missing | Missing | Add explicit shrinkage family result |
| Drying shrinkage | `creep_shrinkage` | Missing | Missing | Add explicit shrinkage family result |
| Total shrinkage | `creep_shrinkage` | Missing | Missing | Add explicit total result |
| Governing crack-control outcome | `crack_control` | `status`, `width_mm`, `limit_mm`, `util` | Partial | Add governing outcome row |
| Table-based crack control check | `crack_control` | Missing table stress/result fields | Missing | Propagate table method result/status |
| Direct crack width check | `crack_control` | Width only; no direct sub-result | Partial | Add direct-width result/status |
| Total deflection (short + long-term) | `serviceability` | `deflection_mm`, `deflection_util`, `status` | Partial | Add exact Runtime row |
| Short-term deflection (total load) | `serviceability` | `short_term_deflection_mm` | Partial | Add row status and limit |
| Additional long-term deflection | `serviceability` | `long_term_deflection_mm` | Partial | Add row status and limit |
| Reinforcement fit/congestion | `reinforcement_fit` | accepted, congestion, layers, reasons | Not shown | Add detailing check section where applicable |

## Required completion gates

1. No placeholder numeric result may be presented as a calculated check.
2. Each Runtime row must have one V2 calculation owner and typed output.
3. Current and proposed results must carry the same row-level checks independently.
4. Summary cards may only display values returned by the authoritative result.
5. Missing or not-run checks must display `INFO`/`NOT RUN`, never `PASS`.
6. Every row needs a focused contract/parity test against a Runtime fixture.
