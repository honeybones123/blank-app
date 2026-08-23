# Calculation-page module contract

This contract records the page architecture proven by Creep, Shrinkage,
Crack Control, and Deflection. It is a refactoring boundary, not a new
engineering model. A conforming extraction must preserve the rendered page,
widget identities, session behaviour, authoritative publications, reports,
and numerical results.

## Ownership model

Each calculation page has one owner for each responsibility:

1. **Composition shell**
   - The route-facing module owns profiling and the single runtime entrypoint.
   - It must not reproduce the page calculation or presentation.
2. **Runtime coordinator**
   - Owns ordered page composition, shared-state reads, widget synchronisation,
     authoritative calculation calls, and result publication.
   - It creates detached snapshots before handing values to presentation.
3. **Immutable page/check snapshots**
   - Contain only the values needed by the receiving renderer.
   - Copy mutable mappings and nested collections before freezing them.
   - Never expose mutable `session_state` or an authoritative publication by
     reference.
4. **Summary owner**
   - Renders the existing summary first, with the same row identifiers,
     columns, click binding, colours, and explainer position.
5. **Compact-input owner**
   - Owns existing widgets and their established keys/callbacks.
   - May request a state update through an injected callback, but does not own
     engineering formulas or publication policy.
6. **Visualisation owner**
   - Receives a frozen diagram snapshot and mounts the established live
     diagram in the established DOM position.
   - Diagram presentation must not become an engineering authority.
7. **Calculation-check owner**
   - Projects a frozen check snapshot into the existing teaching cards.
   - It may use pure display helpers, but does not read `session_state`, write
     results, or independently recalculate authoritative outputs.
8. **Report projection**
   - Is a pure, Streamlit-free conversion from authoritative values into the
     established report input structure.
   - PDF/report generation consumes this projection; reports never scrape the
     page or browser DOM.

## Page-specific boundaries

- **Creep** keeps time-dependent engineering/publication in the runtime and
  passes frozen input, summary, visualisation, and check snapshots to section
  renderers.
- **Shrinkage** keeps AS 3600 and EC2/C766 authority branches explicit. The
  selected method and warnings are preserved in its report projection.
- **Crack Control** keeps separate AS 3600, AS 5100 wall, and C766 input/check
  renderers. Method selection changes presentation and the existing
  authoritative calculation branch; it does not merge the methods into one
  generic teaching solver.
- **Deflection** keeps serviceability publication, support resolution, and
  multi-span calculation ownership outside summary/check/diagram renderers.
  The diagram receives only the resolved governing-span snapshot.

## Non-negotiable invariants

A modularisation is valid only when all of these remain unchanged:

- engineering formulas, tolerances, sign conventions, and result values;
- authoritative state/publication ownership and active-beam identity;
- Design Brain integration and Load Analysis/Beam Inputs ownership;
- widget keys, callbacks, defaults, disabled states, and beam switching;
- summary-first order, headings, spacing, cards, tabs, diagrams, colours,
  collapsed/open behaviour, and responsive geometry;
- report values, method metadata, warnings, and PDF consumer entrypoints;
- intentional lazy/heavy render boundaries, scrolling, and cold/warm timing.

Presentation modules must not use runtime global mutation bridges such as
`bind_runtime(globals())` or `globals().update(...)`. Dependencies are explicit
imports, immutable snapshots, or narrow injected callbacks.

## Safe extraction sequence

For each page:

1. Record desktop and narrow geometry and visible text.
2. Record open/collapsed cards, widgets, keys, interaction behaviour, and
   active-beam switching.
3. Capture authoritative engineering and report fixtures.
4. Measure cold and warm page milestones.
5. Create a dedicated branch.
6. Add immutable page/check/diagram snapshots without changing output.
7. Extract summary, compact inputs, visualisation, checks, and report
   projection one boundary at a time.
8. Leave the runtime as the only state/publication coordinator.
9. Run focused contracts after every boundary.
10. Compare the live browser page at the frozen desktop and narrow viewports.
11. Run engineering/report parity and broader regression suites.
12. Commit, fast-forward main, push, and verify the remote SHA before starting
    the next page.

## Verification gates

Completion requires evidence for all of the following:

- immutable snapshot detachment and nested freezing;
- source-ownership/architecture tests;
- engineering and publication parity;
- report projection and PDF consumer parity;
- desktop and narrow browser geometry parity;
- summary/card/tab/diagram/widget interaction parity;
- active-beam navigation/state survival;
- scroll stability and no duplicate render owner;
- multiple-run cold/warm timing within the agreed tolerance;
- clean remote-main smoke test.

## Shared-helper rule

Do not create a shared abstraction from one page. Extract a helper only after
at least two independently verified pages expose the same stable presentation
boundary. The helper must preserve the existing markup and component keys, and
both source pages must rerun their complete visual and interaction gates after
adoption.

This rule allows the architecture to be repeated without forcing unlike
engineering methods into a premature generic model.
