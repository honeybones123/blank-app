# Page reference sidebar audit

The active runtime page registry in `app.py` contains nine pages. Each page is
covered by one entry in `PAGE_REFERENCE_BUILDERS` and renders the shared
`Glossary of terms` and `Current page values` expanders.

| Page | Glossary | Current values | Base item count |
| --- | --- | --- | ---: |
| Start | PASS | PASS | 0 |
| Beam Inputs | PASS | PASS | 303 |
| Load Analysis | PASS | PASS | 20 + active load rows |
| Bending | PASS | PASS | 44 |
| Shear | PASS | PASS | 47 |
| Creep | PASS | PASS | 24 |
| Shrinkage | PASS | PASS | 20 |
| Crack Control | PASS | PASS | 49 |
| Deflection | PASS | PASS | 39 |

Start intentionally has zero engineering inputs and displays the required
empty-state message. Load Analysis adds entries for the active point/UDL,
span, support, and section-selection rows to its base definitions.

Value sources are page-owned read models:

- Beam Inputs uses the active `InputSnapshotStore` snapshot.
- Load Analysis uses its `LoadAnalysisStateStore` draft plus the already
  resolved local action values.
- Bending and Shear use their page/check snapshots and resolved result fields.
- Creep, Shrinkage, Crack Control, and Deflection use their typed page/check
  values and already-published dependent values.

The reference adapters do not call engineering solvers, write session state,
create widgets, or publish calculations.
