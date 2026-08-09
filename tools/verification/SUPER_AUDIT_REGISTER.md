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
| SA-004 | Concrete and reinforcement strengths | Approved material policy plus independently checked material-property fixtures. Unsupported values must be rejected before calculation with a user-facing validation state. | Independent + contract verified | Supported-grade matrix; unsupported values; saved-session migration; all calculation-family smoke cases; no uncaught exception. | VERIFIED |
| SA-005 | Empty widget labels | WCAG/Streamlit accessibility contract: every interactive widget has a stable non-empty accessible label, whether visibly shown or collapsed. | Contract verified | Automated widget inventory across all routes reports zero empty labels. | VERIFIED |
| SA-006 | Packaged Design Brain architecture | Approved composition: Design Brain is installed inside Runtime and reached through the application port, without absolute paths, `sys.path` mutation, or UI imports of internal family pipelines. | Contract verified | Architecture check; clean-install contract; import-boundary checks; revised non-obsolete architecture test. | VERIFIED |
| SA-007 | Engineering/state verifiers | A verifier must reject deliberately corrupted capacity, utilisation, mandatory-check, clause, revision, hash, and Apply-candidate evidence. | Mutation verified | One positive control and required negative mutations for each verifier; demonstrated false-result rejection. | VERIFIED |
| SA-008 | Independent engineering fixtures | AS 3600 clause/equation derivation or separately reviewed calculation, not production output copied into expectations. | Independently verified | Bending, shear, crack, deflection, minimum reinforcement, geometry/detailing, combined, overdesign, and serviceability fixtures with tolerances and review status. | VERIFIED |
| SA-009 | Design Brain family corpus | Explicit family predicates evaluated from authoritative checks; historical recipe names are regression evidence only. | Independent or review required | All 90 live recipes classified as confirmed, alias, invalid fixture, genuine defect, or review required; valid cases match reviewed predicates. | VERIFIED |
| SA-010 | Streamlit compatibility | Supported Streamlit API behaviour and unchanged approved UI/state contracts. | Contract verified | Deprecated `use_container_width` and component HTML usages migrated in isolated slices; route, control, fragment, and layout regressions pass after each slice. | VERIFIED |
| SA-011 | Desktop/mobile behaviour | Approved UI behaviour observed in a real browser: no Apply scroll jump, overflow, unusable touch target, or navigation failure. | Contract verified | Narrow phone, large phone, tablet, and desktop journeys; cold/warm Apply; portrait/landscape; keyboard; screenshots and console evidence. | VERIFIED |
| SA-012 | Final release gate | This register plus the approved release criteria; no item may be silently excluded. | Composite | All objective items verified; engineering review items explicitly resolved/accepted; 1,000+ stateful fuzz operations; all routes and controls; clean worktree; final evidence report. | VERIFIED |

## Known super-audit evidence baseline

- Current Design Brain package suite: 363 passed and 7 explicitly skipped.
- Architecture check: 82 Python files passed.
- Exhaustive Runtime control sweep: all 211 discoverable controls across all
  nine routes were inventoried in isolated AppTest sessions. All 39 enabled
  buttons, 60 enabled number inputs, 60 selectboxes, 8 non-navigation radios,
  8 checkboxes, 11 toggles and 9 text inputs executed without an application
  exception. The 9 navigation radios were exercised through route traversal,
  and all 7 intentionally disabled number inputs were separately inventoried.
- Stateful Runtime fuzz gate: 50/50 sequences and 1,000/1,000 operations pass
  across geometry, materials, longitudinal and shear reinforcement, manual and
  Load Analysis actions, serviceability, locks, UI state and navigation. Every
  operation rebuilds Runtime's real engineering snapshot and packaged Design
  Brain result while checking authority hashes, revisions and finite outputs.
- Live family corpus: all 90 cases are now predicate-classified: 40 exact
  matches, 30 documented legacy aliases, 10 valid states mislabeled as pure
  bending failure despite active low-utilisation shear, and 10 invalid
  three-leg shear fixtures. No difference is treated as a Design Brain defect
  merely because its historical label differs.
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
- SA-004 Runtime contract passes all eight supported concrete grades with the
  modeled 500 MPa reinforcement grade, rejects f'c = 41 MPa and fsy = 400,
  501 and 600 MPa before calculation,
  clears stale result authority, renders the exact validation reason, recovers
  after correction, and translates unsupported saved-state inputs through the
  same typed boundary without silent material conversion. Standard review
  confirms the eight concrete grades and 500 MPa reinforcement. The model
  lacks the product properties required to verify 600 MPa, and no approved
  basis was found for legacy 400 MPa, so both now use the established explicit
  saved-session validation path. SA-004 is `VERIFIED`.
- SA-005 automated AppTest inventory passes every route with zero empty labels
  across buttons, number inputs, selectors, radios, checkboxes, toggles, text
  inputs/areas, multiselects, date/time inputs, and sliders. Collapsed widgets
  retain the same visible row text as their accessible label.
- SA-006 package suite passes 363 tests with 7 explicit skips; the 81-file
  architecture check passes; the installed-package contract now proves source
  manifest equality with Runtime's owned package; and a fresh temporary venv
  installs that local package and calculates a revision/hash-matched Runtime
  result without an external checkout or source-path mutation.
- SA-007 mutation certification passes positive controls and rejects deliberate
  corruption of bending capacity, independently derived utilisation, mandatory
  check presence, AS 3600 clause metadata, input revision, engineering and
  publication hashes, and both Apply candidate identity and its exact update
  map. The production Apply boundary was strengthened so a copied candidate ID
  cannot authorize altered updates, and the authoritative-result store lock was
  updated to exercise the current neutral contract and coordinator API.
- SA-008 now includes a visually reviewed, standard-derived rectangular
  flexure fixture citing AS 3600:2018(+A1) Clauses 3.1.1.3, 8.1.3 and 8.1.6.1
  and Table 2.2.2. It independently verifies effective depth, steel area,
  stress-block factors, neutral axis, ductility ratio, reduction factor,
  nominal/design moment and minimum tensile steel. This exposed and corrected
  the former minimum-steel exponent/coefficient error. A second derivation now
  verifies the simplified unreinforced-shear branch, including effective shear
  depth, concrete contribution, reduced capacity and the web-crushing ceiling,
  against Clauses 8.2.1.9, 8.2.3.1, 8.2.3.3 and 8.2.4.1. A continuous-beam
  deflection fixture independently verifies effective inertia, the conservative
  end-span coefficient, short-term deflection and the Clause 8.5.3.2 sustained
  multiplier; it corrected the generic `Continuous` route's former silent
  simply-supported fallback. Crack-control fixtures now independently verify
  Table 8.6.2.2 and the Clause 8.6.2.3 effective tension area, mean tensile
  strength, strain difference, maximum spacing and width. Direct width is no
  longer claimed when its close-bar-spacing precondition is false. The
  geometry/detailing fixture independently verifies usable width, clear
  spacing, reinforcement centroid and effective depth. It also prevents the
  app-policy `D/b <= 2` rule and specified cover from being misreported as
  AS 3600 compliance. Finally, independently calculated strength and
  serviceability ratios drive combined-failure, overdesign and deflection-
  governed family predicates without relying on historical recipe labels.
  All named fixture categories now have direct evidence, so SA-008 is
  `VERIFIED`.
- SA-009's executable corpus contract rebuilds every frozen live state through
  Runtime's engineering snapshot boundary, recalculates it with the packaged
  Design Brain, independently derives the governing family from authoritative
  checks, and requires exact agreement with the production classifier. All 90
  cases are accounted for with no unclassified difference, so SA-009 is
  `VERIFIED`.
- SA-010 uses Streamlit 1.61.1 or newer and contains no deprecated
  `use_container_width`, `components.html`, or experimental query-parameter
  calls. The shared trusted-iframe boundary preserves the former fixed-height
  and no-scroll behavior, including zero-size script hooks through a validated
  one-pixel host. The compatibility contract, every-route widget inventory,
  363-test package suite, verifier mutations, and 90-case family corpus all
  pass without a Streamlit deprecation warning. SA-010 is `VERIFIED`.
- The final control rerun exposed keyed widgets that supplied both a session
  value and an explicit Streamlit default. The shared single-authority pattern
  now seeds session state once and omits the competing `value`/`index`
  argument for Load Analysis number rows, the active-beam selector, crack
  exposure and the calculated-actions toggle. Static compatibility checks and
  the focused Load Analysis, Apply and accessibility contracts pass without
  the duplicate-default warning; the 211-control contract also passes after
  the repair.
- Design Brain Apply is now browser-certified against the original cold
  `Mu=200, Vu=0` case and a warm `Mu=300` case. The action edit and Apply each
  create one authoritative revision; result revisions match, the visible
  action remains unchanged, and the accepted candidates update depth from
  300 to 400 mm and then 400 to 500 mm. The Streamlit main scroll position
  remained exactly 1866 px before and after both Apply operations.
- The 2D/3D display preference is owned by UI state. Mouse and rerun journeys
  leave the authoritative input revision, result revision, action, geometry
  and governing family unchanged; the static display-state contract rejects
  reintroduction into the beam-project parameter boundary.
- SA-011 passed real-browser journeys at 360x800, 430x932, 800x360, 768x1024,
  1024x768 and 1440x900. Document and Streamlit-main widths matched at every
  viewport, including 1024x768 with the 300 px sidebar open. Twenty-five
  visible application buttons in the 360 px session had a 44 px minimum hit
  height. Mobile and desktop screenshots were visually inspected, Enter-key
  action commits passed, cross-page Load Analysis return preserved revision 5,
  `Mu=300` and `D=500`, and browser logs contained no warning or error entries.
- Responsive CSS is emitted at the per-run Streamlit lifecycle boundary rather
  than module import, so independent later sessions receive the same phone
  ergonomics as the first. Expanded summary tables now scroll inside their
  owned container, and hidden tooltip geometry cannot widen tablet content.
- The exhaustive final control rerun exposed one remaining keyed-slider
  duplicate-default warning. The Design-page section slider now follows the
  established session-owned default pattern, its mutation-sensitive static
  contract passes, and a second complete 211-control sweep passes without the
  warning.
- SA-012's deterministic 50-sequence, 1,000-operation Runtime fuzz contract
  (seed 20260809), 363-test package suite, 82-file architecture check, clean
  install, all-route accessibility inventory and complete control sweep all
  pass on the final source. The composite release gate is `VERIFIED`.

## Release rule

The Runtime is eligible for upload only when SA-012 is satisfied and the user
explicitly approves the upload. `REVIEW_REQUIRED` may be resolved only by
documented engineering approval or independent evidence; changing expected
outputs to match current production results is not verification.
