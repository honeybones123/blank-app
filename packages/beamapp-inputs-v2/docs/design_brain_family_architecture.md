# V2 Design Brain Family Architecture Contract

## Governing rule

The family sorter may classify the current engineering state. It must not
design, rank, accept, block, format, or apply a proposal. Once classified,
exactly one `FamilyOwner` and its immutable `FamilyContract` govern the run.

Every active family owns:

- an executable entry condition;
- a deterministic ordered ladder;
- permitted and prohibited changes;
- mandatory engineering checks;
- the improvement acceptance policy;
- deterministic candidate ranking;
- exact-stop proof requirements;
- blocker reason codes and engineering wording;
- the final proposal status and presentation-neutral CTA intent.

Terminal outcomes (`TARGET_BAND_REACHED`, `EXACT_STOP_PROVEN`, and
`LOCKED_NO_REPAIR`) also have explicit contracts. They retain the current
design and cannot start a repair ladder.

## Non-negotiable single-decision-centre contract

There is exactly one classifier and exactly one decision owner for each run.

- The classifier may select one family and nothing more.
- The selected `FamilyOwner` owns the complete engineering decision.
- No orchestrator, service, formatter, renderer, Apply handler, shared policy,
  or compatibility wrapper may accept, reject, reclassify, soften, promote, or
  replace the selected family's decision.
- Shared code may calculate facts and enforce universal safety invariants. It
  must return evidence to the family and must not turn that evidence into a
  family status, terminal outcome, blocker, colour, or CTA.
- A family decision may not be passed through a second target-band test,
  improvement test, exact-stop test, or CTA resolver after the family returns
  it.

The only permitted decision flow is:

```text
classifier selects one family
        -> selected FamilyOwner evaluates its complete contract
        -> selected FamilyOwner returns one final FamilyDecision
        -> orchestrator passes that decision through unchanged
        -> presentation renders it unchanged
        -> Apply executes the exact authorised candidate
```

The following are forbidden second decision centres:

- an orchestrator recomputing `accepted`, target-band state, terminal state,
  status, colour, blocker, or CTA;
- a shared service selecting a family-specific stopping reason;
- a formatter inferring whether a proposal is safe or applyable;
- a page enabling or suppressing Apply from utilisation values;
- a compatibility wrapper changing a `FamilyDecision`;
- a generic policy overriding the selected family's final decision;
- a terminal-family conversion performed outside the selected family owner.

## Mandatory family ownership

Every non-terminal family must own, in executable form:

1. entry conditions;
2. ordered engineering ladder and actual stage execution;
3. permitted changes;
4. prohibited changes;
5. mandatory authoritative checks;
6. candidate improvement test;
7. deterministic candidate ranking;
8. exact-stop proof;
9. typed blocker code and engineering wording;
10. final status;
11. final proposal;
12. presentation-neutral CTA intent.

Declaring a ladder stage in metadata is not evidence that the stage ran. Each
stage must record its own attempted candidates, valid candidates, rejection
reasons, and completion state. Exact stop is valid only when this recorded
evidence proves that every required stage actually completed.

Mixed families must implement their own coordinated ladders. A mixed family
must not satisfy its contract by delegating to a bending-only or shear-only
pipeline when its declared stages also require cleanup or optimisation of the
other domain.

## Neutral candidate and universal validation contract

Every family candidate starts as an unchanged copy of the current canonical
design. Candidate factories must not contain automatic engineering mutations.
In particular, a shared seed must never add a bar, change a diameter, introduce
ligatures, change geometry, or alter loads.

Each family may change only fields permitted by its own contract. All proposed
changes, including hidden or unchanged companion values, must be compared with
the current canonical design before evaluation.

Every candidate then passes through one shared validation gateway. The gateway
may calculate and return evidence for:

- bending and shear resistance;
- ductility and minimum reinforcement;
- reinforcement fit, cover, clear spacing, layering and congestion;
- geometry and detailing limits;
- explicit-SLS crack control and deflection; and
- provisional crack control, bar spacing and deflection when SLS actions are
  absent.

When SLS actions are absent, candidate validation must privately use the
configured provisional serviceability proxy, initially `0.60` times the
relevant ULS action effect. This rule applies to candidates from every family.
The proxy is evaluation evidence only. It must never be written into canonical
inputs, widget state, summary cards, saved projects, reports, or exported load
data. Genuine SLS actions replace the proxy immediately.

The validation gateway returns facts such as calculated checks, compliance,
fit results and rejection evidence. It does not choose a family, rank a family
ladder, declare exact stop, select visible wording, or decide Apply.

## Change-control rule

No Design Brain change is complete merely because existing tests pass. Every
change to classification, candidate generation, evaluation, ranking, stopping,
status, or Apply must state:

- the family contract being changed;
- expected affected families;
- expected unaffected families;
- the decision owner before and after the change;
- the exact new or changed evidence;
- tests proving affected behaviour; and
- tests proving unaffected families did not change.

A change must be rejected if it creates another place that can decide family,
acceptance, terminal state, blocker, status, colour, or CTA.

## Dependency and decision flow

```text
BeamInputs + EngineeringResult
        -> family classifier
        -> one FamilyOwner
        -> its ordered ladder
        -> shared candidate evaluator/calculator
        -> family improvement + ranking + exact-stop policies
        -> FamilyDecision
        -> presentation view model
        -> explicit Apply command (when authorised)
```

The shared search engine may evaluate calculations and reusable candidate
mechanics. It may not select a family or invent a final CTA. The orchestrator
may calculate, classify, delegate, enforce cross-family invariants, and return
the decision. It may not call a concrete ladder directly.

## Collaborator ownership

`DesignBrainService` is the composition facade, not the owner of every search
policy. Current focused collaborators are:

- `candidate_ranking.py`: shared safety-first and bending-specific evidence
  ordering;
- `ratio_policy.py`: reinforcement-ratio trigger and blocker policy;
- `serviceability_pipeline.py`: serviceability candidate generation,
  evaluation, and selection;
- `combined_overdesign_pipeline.py`: combined low-demand cleanup;
- `bending_repair_policy.py`: primary bending, low-demand cleanup, and bounded
  proportion-balancing search-space ordering;
- `bending_proportion_pipeline.py`: trigger-based, calculator-backed section
  proportion evaluation and metrics;
- `bending_failure_pipeline.py`: primary bending repair evaluation and final
  verification;
- `bending_overdesign_policy.py`, `bending_overdesign_selection.py`, and
  `bending_overdesign_pipeline.py`: bounded bending-cleanup generation,
  selection, and calculator-backed orchestration;
- `shear_repair_policy.py`: deterministic shear repair search-space ordering;
  and
- `shear_failure_pipeline.py`: calculator-backed shear repair evaluation and
  selection;
- `shear_overdesign_pipeline.py`: link-density and zero-demand cleanup; and
- `combined_failure_pipeline.py`: atomic bending-and-shear failure repair.

The facade binds the active `FamilyContract`, supplies calculation/evaluation
ports, and delegates. Collaborators must remain independent of Streamlit,
session state, and Runtime modules.

## Mechanical enforcement

### Family-owned preference contract

`DesignPreferenceProfile` is immutable project configuration. It supplies
standard sizes, dimension increments, soft-buildability values and the selected
optimisation mode. It cannot classify a family, generate an unrequested move,
evaluate compliance, rank globally, publish advice or authorise Apply.

The classifier selects one owner. That owner receives a typed
`FamilyRunContext`, runs its ordered ladder, rejects hard failures, and uses its
own `RankingPolicy` to compare only passing candidates. Hard congestion (fit,
cover, clear spacing, row spacing, anchorage or a declared constructability
limit) is mandatory rejection evidence. Soft congestion is recorded separately
and may only affect family-owned ranking.

Near-limit treatment is opt-in per family and per check. Each `NearLimitRule`
declares the check, direction, threshold and comparison method. No default
near-limit rule is inferred. Preferred `As/(bd)` bands remain proportion-
balancing diagnostics unless a calculation contract explicitly promotes a
ratio to a mandatory requirement.

`SearchProfile` remains the sole owner of Fast/Detailed evaluation budgets.
Every decision records the preference profile identity/version, generated
candidates, cache hits, full evaluations and elapsed time for reproducibility.
Normal cards do not display this diagnostic provenance.

- Every `DesignFamily` must exist in `FAMILY_CONTRACTS`.
- Every non-terminal family must have a unique owner and ladder entry point.
- A proposal is rejected if any changed field is outside the family boundary,
  including hidden action, material, support, or serviceability changes.
- Exact stop requires all declared ladder stages to be recorded as completed.
- Ranking contract binding is scoped to one ladder execution and restored
  afterwards, preventing family-policy leakage.
- Apply is authorised only for a verified proposal whose source revision and
  hash still match the canonical inputs.
- UI styling and wording consume typed decision data and do not select
  engineering outcomes.
- Static architecture checks reject target-band, acceptance, terminal-family,
  blocker, status, colour, and CTA decisions outside family owners.
- The orchestrator test proves the returned `FamilyDecision` is the exact
  decision returned by the selected owner, without recomputation.
- Every family has a no-candidate test that proves the precise rejection
  evidence and CTA intent.
- Every family has an Apply test proving that a verified candidate produces
  exactly one authorised CTA and that a blocked or terminal decision produces
  none.
- Every family has a proxy-serviceability test proving that missing SLS actions
  trigger private `0.60`-proxy crack, spacing and deflection evidence without
  changing visible or persisted inputs.
- Every mixed family has tests proving all declared domains and ladder stages
  actually execute.
- Exact-stop tests verify recorded stage evidence; reason codes alone are
  insufficient.
- A neutral-seed test proves that creating a candidate without family changes
  produces a proposal identical to the current canonical design.

These rules are covered by `tests/test_architecture.py`, family/service tests,
orchestrator contract tests, text-contract tests, and the repository
architecture checker.

## Presentation freeze

This repair does not alter the Streamlit page structure, component styles,
card colours, expand/collapse behaviour, or Apply-button layout. Presentation
changes require a separate visual contract and approval.
