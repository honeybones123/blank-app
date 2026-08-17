# Beam Application Architecture Contract

This contract defines the target architecture for the canonical Runtime app. A phase is complete only when its implementation and verifiers satisfy this contract without a legacy fallback.

## 1. Non-negotiable user behaviour

- A widget edit is reflected automatically; the user never presses a refresh button.
- Widgets remain usable while dependent work runs.
- Summary and calculation loading affects only the summary/calculation region.
- Design Brain loading affects only the Design Brain region.
- A result is never presented as current unless its revision and engineering hash match the latest committed inputs.
- Inputs persist across Beam pages for the same Streamlit session and browser workspace.
- Restart persistence uses mutable storage outside Runtime.
- Apply is atomic, revision-checked, and followed automatically by a fresh calculation and Design Brain publication.

## 2. Ownership layers

### Presentation shell

`inputs_page.py` owns route order and rendering composition only. It may construct page context and invoke the engineering-workspace entry point. It does not own action-source transaction ordering, calculate engineering results, classify a governing family, build recommendations, decide publication truth, or mutate a Design Brain result.

The Inputs page is composed in this order:

1. page setup and committed widget projection;
2. static page title owned by the shell;
3. one authoritative engineering workspace transaction;
4. page tail and diagnostics.

The authoritative engineering workspace owns the revision-consistent composition of summary/calculation, workspace controls, Design Brain, engineering inputs and diagrams. These regions may have stable presentation-local child fragments, but they must consume the same committed snapshot/revision and may not create competing calculation, publication or Apply authorities.

A child fragment may rerender a display-local region without advancing engineering identity. Splitting presentation for responsiveness is allowed; splitting the authoritative engineering transaction into independently publishing sibling authorities is forbidden.

Action-source switching is an application transaction. The page shell may invoke it, but the pointer -> projection -> reconciliation -> commit ordering belongs to an application service and cannot be reimplemented in `inputs_page.py`.

### Application services

Application services coordinate explicit typed values and stores. They may depend on domain modules and ports. They do not depend on page modules. Presentation-aware application boundaries may receive an explicit rendering adapter only where the boundary itself is a user interaction transaction; they cannot calculate engineering results or own page layout.

Required storage boundaries are:

- `InputSnapshotStore`: committed engineering inputs and input revision;
- `EngineeringResultStore`: calculation result, engineering hash, input revision, and status;
- `PublicationStore`: immutable Design Brain publication identity and revision;
- `RecommendationStore`: fingerprinted recommendation cache entries;
- `ApplyTransactionStore`: queued, validated, committed, or rejected Apply transaction.

The existing names may remain during migration only when a verifier proves the same single ownership. Competing authoritative stores are forbidden.

### Domain and calculation modules

Calculations receive an explicit immutable input snapshot and return an explicit result. They do not import Streamlit, read `st.session_state`, render UI, or choose Design Brain presentation.

### Design Brain

Design Brain receives an explicit engineering snapshot/result and returns typed pipeline outputs. It does not import page modules or read `st.session_state`.

The concrete V2 implementation is supplied by the installed
`beamapp-inputs-v2` distribution. Runtime may depend only on the neutral
application contracts and its adapter; it must not locate a V2 checkout,
insert a V2 source directory into `sys.path`, or select a legacy Design Brain.

The only allowed pipeline order is:

1. snapshot validation;
2. engineering calculation/result intake;
3. governing-state classification;
4. family dispatch;
5. candidate generation;
6. candidate evaluation;
7. candidate selection;
8. publication construction;
9. Apply-command construction.

Each stage has an explicit input and output contract. Render, cache, and session concerns cannot change a stage decision.

## 3. Session-state rule

`st.session_state` remains the session-scoped storage adapter so pages remember the same Beam inputs. It is not the application API.

- Page callbacks may write widget keys and call one application command.
- Stores accept a `MutableMapping` and own their namespaced keys.
- Calculation and Design Brain functions receive explicit objects, never `st.session_state`.
- Cross-page reads go through the same stores or a typed read model.
- Compatibility keys are projections from one authority and cannot become a second authority.

This preserves cross-page memory while making business logic independently testable.

## 4. One revision protocol

Every committed engineering edit belongs to one monotonic `input_revision`.

- `input_revision` advances once when the stable committed-input hash changes.
- Display-only widgets do not advance it.
- `calculation_revision` is publishable only when it equals `input_revision` and its engineering hash matches the committed snapshot.
- `design_revision` is publishable only when it equals the current successful `calculation_revision` and carries the same engineering hash.
- `publication_revision` identifies the published Design Brain result and cannot exceed `design_revision`.
- An Apply command includes its expected `input_revision`, `publication_revision`, engineering hash, publication authority hash, and candidate identity.
- Apply rejects a mismatched expectation without mutating engineering inputs.
- Successful Apply commits one new input revision and invalidates dependent results once.

Revision status is one of `empty`, `pending`, `ready`, `failed`, or `superseded`. Completion for a superseded revision is ignored and cannot replace a newer result.

## 5. Automatic scoped execution

Widget callbacks commit or classify the edit and request the smallest affected presentation rerun that preserves the authoritative engineering transaction.

- Display-local edit: rerun only its widget/diagram/card fragment when that fragment has no engineering authority.
- Engineering edit: commit `input_revision`; the authoritative workspace refreshes the matching calculation and Design Brain publication automatically.
- Design-policy edit: reuse a matching calculation when legal and refresh Design Brain automatically.
- Apply: validate and commit atomically, then follow the engineering-edit path.

Polling or background execution may be used only when freshness contracts remain explicit, but the browser must never require a manual refresh. The shell must not recompute the authoritative transaction merely because an unrelated expander opened, collapsed, or changed display mode.

## 6. Freshness and failure presentation

- A pending region shows a region-local loading state for the latest revision.
- Old values are not labelled or styled as current.
- A failed latest calculation shows its error in the summary/calculation region and blocks Design Brain publication for that revision.
- A failed latest Design Brain run shows its error only in the Design Brain region.
- The last successful object may remain stored for audit or recovery, but the UI must not publish it as the latest result.
- Page navigation never changes revision identity.

## 7. Family contract

All 15 registered governing families use the same dispatch and pipeline interfaces. Every family provides:

- classification evidence it accepts;
- an ordered strategy ladder;
- typed candidate generation;
- typed evaluation evidence;
- deterministic selection or a typed no-valid-candidate outcome;
- publication and Apply data through the common builders.

Family-specific policy belongs within the family contract/runtime. Page-owned decisions, registry side doors, and legacy fallback publications are forbidden.

## 8. Dependency direction

Allowed engineering direction is:

`page shell -> application services -> domain/design_brain/calculations -> pure contracts`

Presentation components may depend on pure presentation helpers and read models, but they cannot become engineering authorities. Adapters may implement inward-facing ports. Reverse engineering imports are forbidden. In particular:

- report helpers cannot import page modules;
- Design Brain registry modules cannot import a family module that imports the registry;
- evidence and optimisation modules cannot mutually import each other;
- domain modules cannot import Streamlit or `inputs_page.py`;
- calculation-card performance policy cannot import calculation or Design Brain mutation services.

Relevant strongly connected components must be zero at final acceptance.

## 9. Performance and cache correctness

- Cache identity derives from immutable typed inputs, not the whole session mapping.
- Pure calculation cache and Design Brain cache are separate.
- Invalidations name their owner and affected revision.
- An unchanged engineering hash performs zero calculation and zero Design Brain compute.
- Cache reuse is permitted only when revision/hash contracts prove freshness.
- Performance work follows measured section timings and may not weaken freshness checks.

### 9.1 Calculation-page presentation freeze

Performance optimisation may change **when** an existing calculation-page body is constructed, but has no authority to change **what** the user sees. For Bending, Shear, Creep, Shrinkage, Crack Control and Deflection:

- the visible control set, control type, order and location remain unchanged;
- headings, labels, help, equations, calculation-box text and explanations remain unchanged;
- cards, tabs, expanders, diagrams, icons, colours, borders, spacing, typography, dimensions and responsive formatting remain unchanged;
- light closed card bodies may remain mounted so expansion is browser-only;
- expensive diagram-bearing card bodies may remain lazy so their figures are constructed only when opened;
- opening or closing a presentation-only card must never advance input revision, recalculate engineering results, refresh Design Brain or publish a new authoritative result;
- deferred work may display only the existing loading treatment and cannot expose a new shell, placeholder or stale result;
- a shared presentation renderer may choose eager versus lazy execution, but it cannot alter engineering state, publish results, own navigation or change the visible contract;
- UI or formatting changes require a separately authorised product change and cannot be justified or bundled as a performance optimisation.

Acceptance requires like-for-like cold and warm measurements plus unchanged visual/formatting, calculation, state-retention and Apply contracts.

The calculation-page performance target is strict: every measured cold page open must complete in less than 1.0 second. A median below 1.0 second does not pass when any required cold run exceeds the limit. The target cannot be met by removing, hiding, renaming, restyling, reordering or omitting visible content, or by substituting a lighter presentation. Before and after runs must render the same page, controls, expanded/collapsed defaults, summaries, diagrams, calculation boxes, wording and formatting from the same engineering snapshot.

## 10. Root-cause completion gate

No symptom-only patch counts toward architecture completion. Each closed issue must include:

1. reproduction evidence;
2. one named primary root cause;
3. the owning layer;
4. a boundary-level fix;
5. a regression verifier;
6. proof that the obsolete or competing path is absent.

If two narrow fixes fail, stop and classify the root cause before another change.

## 11. Final acceptance

The architecture is rated 10/10 only when compile, unit, store, all-family, Apply, navigation, repeated-edit, browser visual, performance, stale-result, drift, and dependency-cycle gates pass together, and no gate relies on `Copy (3)` or generated files inside Runtime.
