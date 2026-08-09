# Runtime Super-Audit Verification Register

This register is the release authority map for the Runtime super-audit repair
goal. A green regression test is not sufficient by itself: every item must
name the independent evidence that defines correct behaviour.

## Repair rules

1. Repair the first incorrect ownership decision or state transition that
   causes a failure. Do not mask its final exception, add permissive keys, or
   weaken a guard merely to turn a test green.
2. Before introducing a new mechanism, locate the established architecture
   used by the closest equivalent operation and reuse its contracts, ports,
   transaction stores, revision rules, and persistence boundary.
3. If an analogous pattern cannot be found, record that fact and justify the
   new boundary before implementation.
4. Prove the failure before the change, then prove the focused contract and
   broad regressions after it.
5. Keep one behavioural repair per checkpoint commit. Do not mix engineering,
   state-management, compatibility, or presentation changes.
6. Never change an expected engineering result solely to match current output.
   Disagreement remains `REVIEW_REQUIRED` until independently resolved.

## Confidence classifications

| Classification | Meaning |
|---|---|
| Independently verified | Compared with a separately derived engineering fixture or external standard calculation. |
| Invariant verified | A state, identity, safety, or mathematical relationship was checked independently of the implementation decision. |
| Contract verified | Behaviour matches an explicitly approved application or UI ownership contract. |
| Regression matched | Behaviour matches historical output only; this is not independent engineering proof. |
| Review required | Available authorities disagree or engineering intent is not yet approved. |
| Untested | Required evidence or execution environment is unavailable. |

## Status vocabulary

`OPEN`, `IN_PROGRESS`, `REVIEW_REQUIRED`, `BLOCKED_ENVIRONMENT`, and `VERIFIED`
are the only accepted statuses. `VERIFIED` requires every item in the named
release evidence column, not merely the absence of an exception.

## Findings and repair evidence

| ID | Scope | Correctness authority | Confidence target | Required release evidence | Current status |
|---|---|---|---|---|---|
| SA-001 | Inputs Design Brain Apply | Approved transaction contract: visible candidate, applied payload, committed input revision, and recalculated result must agree. Apply inside the unified workspace is fragment-scoped; page-level callers retain an app fallback. | Contract + invariant verified | Cold and warm `Mu=200, Vu=0` AppTest; candidate/payload identity; input/result revision equality; fragment/app rerun routing contract; cross-page return. | VERIFIED |
| SA-002 | Load Analysis action publication | Approved ownership contract: Load Analysis actions remain page-local until explicit publication; publication uses the shared Design Actions boundary and must not write calculation outputs through the result-store API. | Contract + invariant verified | Zero/non-zero ULS and SLS cases; toggle on/off; Inputs round-trip; manual-action isolation; cross-beam isolation; no exception. | VERIFIED |
| SA-003 | Bending RECT/T/I diagrams | Presentation contract: every supported section renders; diagram composition must not mutate or redefine authoritative bending calculations. | Contract + invariant verified | RECT, T, and I positive/negative cases; linear/parabolic stress blocks; calculation identity before/after diagram render; fullscreen controls. | VERIFIED |
| SA-004 | Concrete and reinforcement strengths | Approved material policy plus independently checked material-property fixtures. Unsupported values must be rejected before calculation with a user-facing validation state. | Independent + contract verified | Supported-grade matrix; unsupported values; saved-session migration; all calculation-family smoke cases; no uncaught exception. | IN_PROGRESS |
| SA-005 | Empty widget labels | WCAG/Streamlit accessibility contract: every interactive widget has a stable non-empty accessible label, whether visibly shown or collapsed. | Contract verified | Automated widget inventory across all routes reports zero empty labels. | VERIFIED |
| SA-006 | Packaged Design Brain architecture | Approved composition: Design Brain is installed inside Runtime and reached through the application port, without absolute paths, `sys.path` mutation, or UI imports of internal family pipelines. | Contract verified | Architecture check; clean-install contract; import-boundary checks; revised non-obsolete architecture test. | VERIFIED |
| SA-007 | Engineering/state verifiers | A verifier must reject deliberately corrupted capacity, utilisation, mandatory-check, clause, revision, hash, and Apply-candidate evidence. | Mutation verified | One positive control and required negative mutations for each verifier; demonstrated false-result rejection. | OPEN |
| SA-008 | Independent engineering fixtures | AS 3600 clause/equation derivation or separately reviewed calculation, not production output copied into expectations. | Independently verified | Bending, shear, crack, deflection, minimum reinforcement, geometry/detailing, combined, overdesign, and serviceability fixtures with tolerances and review status. | OPEN |
| SA-009 | Design Brain family corpus | Explicit family predicates evaluated from authoritative checks; historical recipe names are regression evidence only. | Independent or review required | All 90 live recipes classified as confirmed, alias, invalid fixture, genuine defect, or review required; valid cases match reviewed predicates. | REVIEW_REQUIRED |
| SA-010 | Streamlit compatibility | Supported Streamlit API behaviour and unchanged approved UI/state contracts. | Contract verified | Deprecated `use_container_width` and component HTML usages migrated in isolated slices; route, control, fragment, and layout regressions pass after each slice. | OPEN |
| SA-011 | Desktop/mobile behaviour | Approved UI behaviour observed in a real browser: no Apply scroll jump, overflow, unusable touch target, or navigation failure. | Contract verified | Narrow phone, large phone, tablet, and desktop journeys; cold/warm Apply; portrait/landscape; keyboard; screenshots and console evidence. | BLOCKED_ENVIRONMENT |
| SA-012 | Final release gate | This register plus the approved release criteria; no item may be silently excluded. | Composite | All objective items verified; engineering review items explicitly resolved/accepted; 1,000+ stateful fuzz operations; all routes and controls; clean worktree; final evidence report. | OPEN |

## Known super-audit evidence baseline

- Design Brain package suite: 348 passed, 7 skipped, 1 obsolete packaging
  assertion failed.
- Architecture check: 81 Python files passed.
- Discoverable button sweep: 39/39 passed in isolated AppTest sessions.
- Selector/radio/checkbox/toggle sweep: 85/87 passed. Failures are SA-002
  and SA-003.
- Number-input sweep: 65/67 passed. Failures are covered by SA-004.
- Stateful Runtime fuzz baseline: 25/25 sequences and 300/300 operations
  passed without exception, non-finite engineering actions, or revision drift.
- Live family corpus: 90 cases; 39 label matches, 41 label differences, and
  10 invalid three-leg shear fixtures. These are evidence for SA-009, not 51
  automatically confirmed Design Brain defects.
- Cross-page `Mu=200, Vu=0` round-trip passed through Inputs, Load Analysis,
  Bending, Shear, and back to Inputs.
- SA-002 focused certification passes real AppTest zero/non-zero ULS and SLS
  publication, manual -> design -> manual restoration, Inputs navigation, and
  two-beam source isolation. Calculated extrema remain result-owned; the
  canonical per-beam `actions_mode` owns source selection and the legacy label
  is compatibility-only.
- SA-003 focused certification passes RECT, T, and I sections under positive
  and negative moment with rectangular/linear and parabolic display modes.
  The shared subplot composer preserves its child figure, bending capacity is
  identical before/after display-mode changes, and every rendered Plotly chart
  has the shared fullscreen anchor.
- SA-004 Runtime contract passes all 24 supported concrete/reinforcement grade
  combinations, rejects f'c = 41 MPa and fsy = 501 MPa before calculation,
  clears stale result authority, renders the exact validation reason, recovers
  after correction, and translates unsupported saved-state inputs through the
  same typed boundary. Independent material-property fixture review remains
  outstanding under SA-008, so SA-004 is not yet `VERIFIED`.
- SA-005 automated AppTest inventory passes every route with zero empty labels
  across buttons, number inputs, selectors, radios, checkboxes, toggles, text
  inputs/areas, multiselects, date/time inputs, and sliders. Collapsed widgets
  retain the same visible row text as their accessible label.
- SA-006 package suite passes 349 tests with 7 explicit skips; the 81-file
  architecture check passes; the installed-package contract now proves source
  manifest equality with Runtime's owned package; and a fresh temporary venv
  installs that local package and calculates a revision/hash-matched Runtime
  result without an external checkout or source-path mutation.
- Real-browser mobile/scroll certification was unavailable and remains
  explicitly blocked rather than inferred from AppTest.

## Release rule

The Runtime is eligible for upload only when SA-012 is satisfied and the user
explicitly approves the upload. `REVIEW_REQUIRED` may be resolved only by
documented engineering approval or independent evidence; changing expected
outputs to match current production results is not verification.
