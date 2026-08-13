# V2 Calculation Ownership Audit

This document records the current calculation ownership boundary. It replaces
the obsolete pre-migration gap list that described placeholders and missing
outputs which no longer exist.

The installed Runtime-owned V2 calculator is authoritative. Presentation code
may format its typed results, but it may not calculate, substitute, infer or
upgrade a check status.

| Engineering area | Authoritative owner | Published evidence |
|---|---|---|
| Positive bending, minimum tensile reinforcement, minimum design capacity and ductility | `engineering_calculator.py` bending and ductility packs | `phi_Mu_kNm`, `Ast_tension_mm2`, `Ast_min_mm2`, `minimum_capacity_knm`, `ku`, conditional Clause 8.1.5 result |
| Rectangular, T and I compression blocks and multi-row reinforcement | bending-capacity component plus row geometry | Shape-specific equilibrium, compression-steel strain compatibility and effective depth |
| Shear, torsion, web crushing and transverse reinforcement | shear-capacity and shear-detailing components | `V_eq`, `phi_Vu`, `Vuc_kN`, `Vus_kN`, `Vu_max_kN`, torsion and detailing results |
| Table and direct crack control | `crack_control.py` | Table stress, outer-steel stress, direct crack width, limits, utilisations and independent statuses |
| Short- and long-term deflection | serviceability component | `short_term_deflection_mm`, `long_term_deflection_mm`, total deflection, limit, utilisation and status |
| Creep | time-dependent concrete component | Notional thickness, age factors, final creep coefficient and current creep result |
| Autogenous, drying and total shrinkage | time-dependent concrete component | Component strains, total strain and microstrain publication |
| Reinforcement fit and congestion | reinforcement-fit component | Accepted state, hard fit failures, row/layer arrangement and congestion evidence |

## Mandatory publication contract

1. No placeholder numeric result may be presented as a calculated check.
2. Every visible check has one authoritative calculation owner and typed output.
3. Current and proposed designs are evaluated independently through the same calculator.
4. Summary cards display only authoritative result values.
5. Missing or not-run checks display `INFO`/`NOT RUN`, never `PASS`.
6. Design Brain families consume the same ULS/SLS calculation result used by the pages.
7. The 0.60 ULS serviceability proxy is provisional internal evidence only; it is never persisted or published as a user SLS action.

## Current verification evidence

- `docs/verification/as3600-equation-audit.md` records the clause-level equation corrections and independent hand-equation coverage.
- `tests/test_authoritative_check_packs.py` proves Runtime row ownership and status publication.
- Component tests independently cover bending, multi-row depth, shear, ligature geometry, crack control, deflection, creep and shrinkage.
- Calculation-parity fixtures prove the installed Runtime adapter and packaged calculator return the same results.
- The clean-installed-package gate proves deployment does not fall back to a different calculator.
- The focused engineering audit on 13 August 2026 passed 90 tests.
- The complete Runtime/V2 GitHub gate for commit `dcec08c` passed architecture, all package tests, the 23-family audit, calculation parity, Apply authority and clean installation.

Any new engineering method or visible check must update this ownership record
and add independent equation and Runtime-propagation tests before release.
