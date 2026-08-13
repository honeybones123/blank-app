# AS 3600 equation audit

This record covers numerical implementation only. Calculation-card labels,
wording, layout, colours, and formatting are outside the equation correction
scope and were not changed.

## Verified corrections

| Area | AS 3600 source | Previous numerical behaviour | Corrected behaviour | Independent evidence |
|---|---|---|---|---|
| Flexural ductility | 8.1.5 | Any calculated `ku > 0.36` was treated as a mandatory failure. | Additional requirements are triggered only when both `ku > 0.36` and `M* > 0.8 phiMuo`; a triggered section passes only when all conditional requirements are verified. | Boundary tests at 0.80 and 0.8001 demand ratios plus verified/unverified conditional cases. |
| Direct crack width | 8.6.2.3 | Effective tension area used cover-based limits without the cracked neutral-axis depth. | Effective tension-zone height uses `min(2.5(D-d), (D-kd)/3, D/2)` from the calculated cracked-section neutral axis. | Independent hand-equation tests for the tension area and crack-width terms. |
| General-method shear strain | 8.2.4.2.2 | The longitudinal strain expression could use a moment term below the clause minimum. | The moment contribution is bounded by `M* >= (abs(V*)-Pv)dv` before calculating longitudinal strain. | Independent zero-moment/high-shear hand calculation of the bounded term, strain, `kv`, and angle. |
| Combined shear-torsion strain | 8.2.4.2.3 | The flexural term was added outside the shear-torsion resultant and the torsion term used `0.97T`. | The complete `(M*/dv + V* - Pv)` term is inside the resultant, the torsion term uses `0.9T`, and the clause minimum resultant is enforced. | Independent hand calculation covers the resultant, minimum bound, numerator and longitudinal strain. |
| Closed-link torsion geometry | 8.2.3.4 and 8.2.5.6 | `Aoh` and `uh` used a hard-coded cover and deducted it only once from each overall dimension. | The centre-line dimensions deduct twice the actual `(side cover + half link diameter)` from the section dimensions. | Independent 300 x 500 mm section check with 35 mm cover and N12 links verifies `Aoh` and `uh`. |
| Shrinkage reference data | Table 3.1.7.2 | Multiple copied table cells differed from the standard and the table was described as drying shrinkage. | The reference table exactly records typical final **total design** shrinkage after 30 years. | Tests cover representative cells across strength and environment extremes. |
| Drying shrinkage | 3.1.7.2(4)-(5) | Total final table shrinkage was used as the drying component and autogenous strain was then added, causing double counting. | Drying shrinkage is calculated as `k1*k4*(0.9-0.005f'c)*800e-6`; autogenous shrinkage is added once. | Independent equation test at 40 MPa in a temperate environment. |
| Creep/shrinkage size factors | 3.1.7.2 and 3.1.8.3 | Hypothetical thickness was rounded to a table column before evaluating `k1`, `k2`, and `k5`. | Time-dependent equations use the actual `th = 2Ag/ue`; rounding remains only for reference-table lookup. | Non-tabulated geometry test proves authoritative factors use the raw thickness. |
| Deflection modulus and flanged width | 8.5.3.1 | The authoritative serviceability path fixed `Ec` at 30,000 MPa and treated every section as rectangular for the simplified `Ief` equations. | Deflection uses the current engineering modulus and the applicable compression-face and web widths for rectangular, T, and I sections. | Independent mechanics test plus authoritative modulus-scaling and flanged-section tests. |
| Deflection boundary condition | 8.5.3.1 calculation model | The allowed `Continuous` input was absent from the coefficient map and silently used the simply-supported coefficient `5/384`. | `Continuous` resolves to the existing interior-span coefficient `1.5/384`; every supported end-condition alias resolves deterministically. | Independent `wL^4/(EcIef)` checks cover simply supported, continuous end/interior, fixed-ended, fixed-pinned, pinned-fixed and cantilever cases. |
| Crack-control modulus propagation | 8.6.2.3 calculation model | The cracked-section stress and direct crack-width calculation fixed `Ec` at 30,000 MPa even when the engineering snapshot supplied another modulus. | Both calculations use the immutable snapshot's concrete modulus. | Independent transformed-section hand calculation at 25,000 MPa verifies the published outer-steel stress. |
| Minimum flexural strength | 8.1.6.1 | The deemed reinforcement equation used `0.4 f'ct.f b d/fsy` for every shape; minimum nominal strength used a rectangular section modulus and was compared with `phiMuo`. | The deemed reinforcement route uses the clause `alpha_b(D/d)^2(f'ct.f/fsy)bwd` expression, including web-in-tension T and flange-in-tension I coefficients. The direct route uses the actual gross section modulus and compares `(Muo)min` with nominal `Muo`. | Independent rectangular and I-section reinforcement equations, T-section section-modulus, and nominal-strength comparison tests. |

## Verification status

- Focused boundary-condition deflection suite: 21 passed.
- Complete Design Brain package suite after the equation corrections:
  436 passed, 7 skipped.
- The complete package and Runtime suites must be rerun after all equation
  areas have been audited.

## Presentation observations

Presentation issues, if found, must be recorded separately and must not be
fixed as part of equation work. No calculation-box presentation change is
included in the corrections above.

- The existing row labelled as minimum tensile reinforcement can pass through
  the clause's direct nominal-strength route even when the deemed
  reinforcement inequality alone is not satisfied. The wording may therefore
  be incomplete, but it has deliberately not been changed in this equation
  audit.

## Remaining equation audit

- Continue clause-by-clause review of any engineering method newly exposed by
  future Runtime inputs. The currently exposed rectangular, T and I bending,
  shear/torsion, crack-control, creep, shrinkage and deflection inputs now have
  independent equation coverage and Runtime propagation evidence.
