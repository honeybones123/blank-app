# V2 Design Brain Architecture and Candidate Recovery Plan

## Objective

Make every Design Brain family the sole owner of its engineering decision,
remove every secondary decision centre, and ensure a failing design produces a
verified repair whenever one exists within the permitted inputs and geometry.

The existing Inputs V2 visual presentation is frozen throughout this work.
Card layout, colours, wording layout, expansion behaviour and Apply-button
placement must remain unchanged unless a separate visual change is approved.

## Governing outcomes

The completed system has:

- one classifier that selects exactly one family;
- one selected `FamilyOwner` that returns the final `FamilyDecision`;
- no status, target-band, blocker or CTA decisions outside that owner;
- a neutral candidate seed identical to the current canonical design;
- one shared evidence-only validation gateway;
- complete family-owned ladders with recorded stage evidence;
- consistent private `0.60 × ULS` serviceability assessment when SLS inputs
  are absent;
- full one-row and practical multi-row reinforcement evaluation; and
- no Apply button for blocked or terminal outcomes, and exactly one Apply
  button for the exact verified proposal.

## Stage 1 — Freeze and characterise current behaviour

Before changing architecture:

1. Record representative fixtures for every family.
2. Include passing, failing, overdesigned, zero-demand, locked, minimum-steel,
   ductility, reinforcement-fit, serviceability and geometry cases.
3. Capture current card screenshots as visual baselines.
4. Record family selection, candidate, result, reason, status, colour and CTA.
5. Add regression fixtures for every recently reproduced missing-Apply case.

Acceptance:

- every family has at least one entry fixture;
- every failing family has a repairable and a genuinely blocked fixture;
- visual baselines exist before behavioural changes begin; and
- V1/Runtime remains untouched.

## Stage 2 — Introduce a neutral candidate factory

Replace the fixture proposal used as a general seed with a neutral factory that
copies the current canonical design exactly.

Rules:

- no automatic extra bottom bar;
- no geometry, reinforcement, action, material, support or SLS mutation;
- each family explicitly applies only its permitted changes;
- complete-proposal boundary checks reject hidden mutations.

Acceptance:

- neutral seed payload equals the current canonical payload;
- generating a seed creates no revision and no displayed change;
- every existing family uses the neutral seed; and
- architecture searches reject the fixture mutation factory outside tests.

## Stage 3 — Build one evidence-only candidate validation gateway

Create one typed gateway that accepts the current design, proposed design and
explicit row arrangement, then returns structured evidence without deciding a
family outcome.

Evidence must include:

- canonical input validation;
- reinforcement fit, cover, clear spacing, row gap, layering and congestion;
- bending capacity, minimum tensile reinforcement and ductility;
- shear strength, web crushing, transverse-reinforcement requirement, minimum
  shear reinforcement, link contribution and spacing;
- geometry and detailing checks;
- explicit-SLS crack control and deflection; and
- provisional crack control, bar spacing and deflection when SLS is absent.

The provisional serviceability calculation uses the configurable `0.60` factor
on the relevant ULS action effect. It is internal evidence only and must not be
written to inputs, widgets, summaries, saved projects, reports or exports.

Acceptance:

- every family calls the same gateway;
- the gateway contains no family identifiers, ranking, status, blocker or CTA;
- current and proposed hashes remain authoritative;
- real SLS inputs replace the proxy immediately; and
- numerical ULS results remain unchanged.

## Stage 4 — Define typed search evidence and exact-stop proof

Replace silent candidate skipping with structured records:

```text
CandidateEvidence
  candidate_id
  stage_id
  proposed_changes
  row_counts
  calculated_checks
  accepted_by_mandatory_checks
  rejection_codes
  elapsed_time
```

Each ladder stage records:

- candidates attempted;
- candidates calculated;
- candidates passing mandatory checks;
- precise rejection counts and reasons;
- whether the stage was completely searched; and
- whether a search bound or user lock stopped it.

Exact stop requires evidence that every contract-required stage actually ran.
A terminal reason string alone is insufficient.

Acceptance:

- no `if not evaluation.usable: continue` path loses rejection evidence;
- every blocked decision identifies a verified blocker;
- exact-stop tests fail when any declared stage is missing; and
- diagnostics can explain why every candidate was rejected.

## Stage 5 — Move final decision authority into each family

Each selected family must return the final `FamilyDecision`, including:

- family;
- final status;
- exact candidate or no candidate;
- current and proposed authoritative results;
- target-band or safe-repair conclusion;
- exact-stop evidence;
- typed blocker;
- changed fields;
- engineering advice data; and
- presentation-neutral CTA intent.

Remove from the orchestrator:

- candidate acceptance recomputation;
- target-band recomputation;
- exact-stop resolution;
- terminal-family conversion;
- blocker selection;
- status selection; and
- Apply eligibility selection.

The orchestrator may calculate the current result, classify once, delegate once
and return the owner's decision unchanged.

Acceptance:

- an identity test proves the orchestrator returns the owner's exact decision;
- static checks reject decision logic outside family owners;
- presentation consumes only `FamilyDecision`; and
- Apply executes only the decision's exact candidate.

## Stage 6 — Standardise and complete every failing-family ladder

Every failing family follows the same structural sequence while retaining its
own permitted changes and engineering priorities:

1. repair with reinforcement at current geometry;
2. test every practical one-row and multi-row arrangement;
3. make local permitted geometry changes;
4. coordinate width, depth and reinforcement changes;
5. expand toward canonical geometry limits when local searches fail;
6. validate every candidate through the shared gateway;
7. rank verified repairs deterministically; and
8. prove exact stop only after complete required-stage evidence.

Family-specific work:

- `BENDING_FAIL_GOVERNS`: remove artificial width/depth expansion limits and
  separate mandatory repair from optional ratio optimisation.
- `SHEAR_FAIL_GOVERNS`: coordinate links, width, depth and longitudinal steel
  for every failing utilisation, not only utilisation above `2.0`.
- `BENDING_AND_SHEAR_FAIL_GOVERN`: evaluate explicit row arrangements and
  expand beyond the current `+100 mm` width window when required.
- `BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS`: implement an actual coordinated
  bending repair plus shear cleanup ladder.
- `SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS`: implement an actual coordinated shear
  repair plus bending optimisation ladder.
- `SERVICEABILITY_GOVERNS`: retain its family-specific serviceability ranking
  while using the shared gateway.
- `GEOMETRY_DETAILING_GOVERNS`: preserve reinforcement initially, repair
  geometry first, and coordinate reinforcement only in an explicit later
  stage.

Acceptance:

- every repairable failing fixture produces one verified Apply candidate;
- multi-row solutions are found where a one-row arrangement cannot fit;
- unlocked geometry is searched to the contract boundary before blocking;
- locked geometry reports the exact lock; and
- preferred reinforcement ratios cannot block a mandatory compliant repair.

## Stage 7 — Standardise overdesign and zero-demand families

Overdesign is optimisation, not failure repair. Each family must:

1. reduce unnecessary reinforcement at current geometry;
2. remove unnecessary layers;
3. reduce geometry and redesign reinforcement where permitted;
4. preserve other active checks;
5. use the shared validation gateway; and
6. return PASS only after target band or a verified exact stopping condition.

Zero ULS demand remains an active cleanup condition when reinforcement exists.
Its utilisation may remain `0.00`; improvement is proven by safe material
reduction, not by utilisation movement.

Acceptance:

- bending overdesign, shear overdesign and combined overdesign each produce
  Apply when a safe reduction exists;
- zero-demand reinforcement cleanup is supported;
- a compliant but unresolved overdesign search cannot silently become PASS;
  and
- retained designs include exact stopping evidence.

## Stage 8 — Align terminal, colour and CTA contracts

Final presentation-neutral states are:

- `ACTION`: verified proposal exists; exactly one Apply CTA;
- `PASS`: current design is in target band or has a verified exact stop; no CTA;
- `BLOCKED`: current design fails or optimisation is unresolved and no verified
  proposal exists; no CTA;
- `INPUT_REQUIRED`: mandatory engineering input is absent; no CTA; and
- `PROVISIONAL`: provisional serviceability evidence is clearly identified
  internally and in the agreed non-numerical notice.

Colour remains derived only from the final decision:

- green for PASS;
- blue for ACTION/overdesign cleanup;
- red for failing BLOCKED outcomes; and
- neutral white/grey for no design actions.

Acceptance:

- no UI code derives colour or CTA from utilisation;
- blocked decisions never enable Apply;
- ACTION always provides Apply; and
- target-band and verified exact-stop decisions are green.

## Stage 9 — Mechanical enforcement, performance and completion report

Add repository checks that fail when:

- decision logic appears outside family owners;
- a family does not own all required contract elements;
- declared and executed ladder stages differ;
- a proposal changes an unowned field;
- a candidate is evaluated without explicit row counts;
- proxy serviceability is skipped by any family;
- rejection evidence is discarded;
- exact stop lacks full stage evidence; or
- presentation independently decides engineering state.

Performance requirements:

- cache repeated calculations by canonical candidate hash;
- stop individual stages only on contract-defined proof;
- keep Fast mode bounded but permit escalation for unresolved failing cases;
- report candidate count, cache hits and elapsed time; and
- demonstrate no material regression for already-balanced designs.

Completion requires:

- full unit, contract, architecture and browser suites passing;
- repairable failure matrix passing for every failing family;
- exact-stop matrix passing for every legitimate blocker;
- current visual regression baselines unchanged;
- V1/Runtime git status unchanged; and
- a final audit proving one classifier and one selected decision owner.

## Delivery rule

Implement one stage at a time. After each stage:

1. identify the contract changed;
2. list affected and expected-unaffected families;
3. run focused tests for both groups;
4. run architecture checks;
5. record performance impact; and
6. stop if the change creates another decision centre or changes presentation.

