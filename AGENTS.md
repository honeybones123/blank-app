# Repository Instructions

## Inputs Page Decision-Authority Rule

`inputs_page.py` is a Streamlit/page shell only. It may collect user inputs,
render UI, route apply actions, store compatibility/debug/session payloads, and
call Design Brain services. It must not own Design Brain decision authority.

Forbidden decision authority in `inputs_page.py` includes family selection,
family ladder order, candidate generation policy, candidate scoring/ranking,
target-band/exact-stop/no-valid-repair decisions, publication legality, CTA
decision truth, blocker legality, and engineering recommendation selection.

When decision-shaped logic is found in `inputs_page.py`, the required response
is not to preserve it as page logic. Either:

- move the decision into the relevant `design_brain` contract/runtime/service
  and delete the page-owned decision branch, or
- prove it is only render/session/apply/debug shell code and keep it classified
  by verifier.

Do not add or edit decision-shaped logic in `inputs_page.py` without updating
the Design Brain proof/verifier boundary in the same slice.

## Design Guide Fuzz Root-Cause Gate

If a Design Guide fuzz failure is not fixed after two narrow patch attempts, stop patching and create a root-cause classification report before making further changes.

Classify the failure as exactly one primary category:

- candidate_search_failure
- candidate_found_not_selected
- candidate_selected_not_published
- published_payload_stale
- click_apply_noop
- click_apply_but_ui_stale
- blocker_evidence_missing
- verifier_classification_bug
- stale_cache_or_state_source
- render_proof_mismatch

Patch only the identified owner layer after that. Do not keep adding fallback guards across render, proof, payload, cache, or coherence paths until the owner layer is named.

## Calculation-Page Performance UI Freeze

Performance work on Bending, Shear, Creep, Shrinkage, Crack Control and
Deflection is execution-only. It must not change any visible UI or formatting.

Forbidden performance-driven changes include:

- adding, removing, renaming, reordering or relocating visible controls;
- changing headings, labels, help text, equations, calculation-box text or
  explanatory wording;
- changing cards, tabs, expanders, diagrams, icons, colours, borders, spacing,
  typography, widths, heights or responsive layout;
- replacing an existing visible interaction with a different control merely to
  make rendering faster;
- showing stale content as current while deferred work completes.

Permitted changes are limited to measured execution behaviour behind the
existing presentation: lazy computation for already-existing selections,
module import deferral or warm-up, cache reuse with complete identities,
removal of proven-dead execution paths, and fragment scoping that preserves the
rendered output and interaction contract.

Every performance slice must compare the same cold/warm scenario before and
after, retain visual/formatting regression coverage, and pass calculation,
state, Apply and page-architecture gates. If a proposed speed improvement needs
a UI or formatting change, stop and obtain an explicit separate user request;
do not bundle it into performance work.
