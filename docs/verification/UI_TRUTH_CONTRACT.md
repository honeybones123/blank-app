# UI Truth Contract

This contract defines the acceptance surface for user-visible Design Guide and
summary verification.

## Final Truth Surface

- The visible browser UI is the final acceptance surface for user-facing truth.
- Hidden DOM, debug payloads, session state, shared state, engine state, or
  internal verifier probes are supporting evidence only. They are not sufficient
  proof when they disagree with what the browser visibly renders.
- Stale, default, hidden, off-route, or transitional UI must not be counted as
  passing evidence.

## Cross-Surface Agreement

- Summary tables, calculation rows, Design Guide cards, CTA state, and browser
  proof artifacts must agree for the current visible design state.
- A green or PASS Design Guide state must not coexist with any visible detailed
  FAIL row for the same current design.
- A red or active-fail detailed state must remain visible as a failure until the
  visible current design has actually changed and the detailed checks agree.
- Where focused browser recipes are used, the requested recipe must equal the
  applied recipe before any browser-visible proof is accepted.

## Action And CTA Truth

- An executable or enabled CTA must have an executor-backed candidate whose
  preview and contract pass the relevant checks for the current visible state.
- A CTA that is not executable must be both visually and contractually disabled.
- A visible CTA must not be treated as valid because internal state suggests a
  candidate exists; the visible card, button contract, and executor-backed
  payload must align.

## Browser Proof Requirements

- Browser proof is required for user-visible truth claims that involve visible
  summaries, detailed check rows, Design Guide cards, CTAs, or page navigation.
- Final ghost, empty, stale, faded, and wrong-page checks must run after the page
  exits transitional render states before a visible pass is accepted.
- If browser-visible truth and internal state disagree, classify the result as a
  state publication, render, or verifier-readiness issue until the mismatch is
  resolved.

## Failure Classification

- Product-visible contradictions take priority over internal-state explanations.
- Verifier artifacts must distinguish product issues from verifier-readiness,
  page-render, stale-state/publication, browser-readiness, and
  orchestration/runtime issues.
- A passing artifact must record the visible proof fields needed to show that the
  browser UI, detailed rows, summary, Design Guide, and action contract were
  evaluated against the same current state.
