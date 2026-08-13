# Production Readiness Audit — 13 August 2026

## Release scope

StructuralBase reinforced-concrete beam Runtime, installed V2 calculation and
Design Brain package, direct Render deployment, and the public
`structuralbase.com/beam` embed.

## Requirement evidence

| Requirement | Authoritative evidence | Result |
|---|---|---|
| AS 3600 engineering equations | `as3600-equation-audit.md`; 90 focused bending, multi-row, shear, ligature, crack, deflection, creep and shrinkage tests | Pass |
| One calculation owner and deployment parity | Adapter parity fixtures, vendored-package identity check and clean-installed-package CI step | Pass |
| Family-owned Design Brain decisions | Architecture checker plus `design_brain_completion_audit.py` covering all 23 outcomes | Pass |
| No stale Apply or duplicate Apply authority | Apply boundary contracts, action-source tests and live local/Render/embed Apply runs | Pass |
| Manual versus Load Analysis action ownership | Absence-only migration tests and live source-toggle round trips | Pass |
| Fragment/page rerun architecture | 97 focused interaction, ownership, summary, diagram and rerun tests | Pass |
| Cold and warm behaviour | Fresh public session, warmed public session, direct Render and local Apply tests | Pass |
| Public deployment parity | Public iframe resolves to the verified Render service and forwards `page`, `cid` and `fresh` session identity | Pass |
| Page navigation and exception safety | Every public beam page opened in a fresh embedded session without a Runtime exception | Pass |
| Repository release suite | 593 passed, 7 intentional production-surface skips | Pass |
| GitHub release gate | Architecture, all V2 tests, family audit, calculation parity, Apply and clean install passed for `d822784` | Pass |

## Live regression values

- Load Analysis with `g = 10`, `q = 5`, `L = 2 m` published `Mu* = 9.75 kNm` and `V* = 19.50 kN`.
- Load Analysis with `g = 12`, `q = 4`, `L = 2 m` published `Mu* = 10.20 kNm` and `V* = 20.4 kN`.
- Enabling the source selector projected the same ULS/SLS action set into Beam Inputs.
- Disabling it restored the four preserved manual action widgets to zero and cleared derived summary actions.
- A fresh embedded `Mu* = 200 kNm` recommendation applied depth `400 mm`; both values remained unchanged after two later settle intervals.
- No `stale_apply`, traceback, import error or continuing Design Brain update was present.

## Intentional skips

The seven skipped tests cover lab-only downloads, persistence controls, batch
fixtures and detailed controls intentionally absent from the production
V1-parity surface. They do not represent unverified engineering calculations
or disabled production release gates.

## Release invariant

A future release fails if any of the following occurs:

- presentation or page code calculates or replaces an engineering result;
- a Design Brain decision is selected, reranked or replaced outside its family;
- Apply uses a candidate from a different input revision;
- Load Analysis values overwrite preserved manual actions;
- the public shell embeds a different Runtime or drops the session identity;
- local, direct Render and embedded behaviour cannot be reproduced from the
  same committed input sequence;
- the full suite, architecture checker, 23-family audit, parity, Apply or clean
  install gate is not green.

At the recorded commit and deployment state, no critical or high-severity
defect is known in the audited release scope.
