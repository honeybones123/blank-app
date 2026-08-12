# Runtime interaction rerun audit

## Contract

Page-local controls rerender only their owning Streamlit fragment. They do not
own navigation, query parameters, project selection, calculation publication or
another page's state.

An application-level rerun is permitted only for a shell transition:

- navigation to another page;
- creating or resetting a beam workspace;
- opening or closing the first-save project modal;
- authentication or project-context transitions.

## Page ownership matrix

| Page | Local render owner | Engineering authority |
|---|---|---|
| Start | Start page fragment | None |
| Beam Inputs | Unified engineering workspace fragment | Beam Inputs transaction |
| Load Analysis | Load Analysis page fragment | Load Analysis state store |
| Bending | Bending page fragment | Published selected-beam calculation |
| Shear | Shear page fragment | Published selected-beam calculation |
| Creep | Creep page fragment | Published selected-beam calculation |
| Shrinkage | Shrinkage page fragment | Published selected-beam calculation |
| Crack Control | Crack Control page fragment | Published selected-beam calculation |
| Deflection | Deflection page fragment | Published selected-beam calculation |
| Global Save/PDF controls | Header action fragment | Persistence/report command only |

## Interaction rules

- Expanding cards, switching ULS/SLS views and diagram display controls create
  no engineering revision.
- An Inputs engineering widget creates at most one input revision and wakes the
  unified Inputs workspace only.
- Load Analysis widgets update only Load Analysis and never import Beam Inputs
  manual actions.
- Apply remains inside the active Inputs workspace fragment and creates one
  committed input revision.
- Report options and existing-project Save rerender only the header action
  fragment. Opening the first-save project modal remains an intentional shell
  transition.
- Streamlit's automatic fragment rerun is used after page-local widget events;
  page renderers must not call `st.rerun()`.
- Direct application reruns are permanently checked by
  `tests/test_page_rerun_architecture.py`.

## Removed duplicate paths

- Bending and Shear no longer force a second rerun when the ULS/SLS view changes.
- The Design Actions renderer no longer rewrites action-source state or aborts
  the Inputs fragment.
- The unreferenced legacy `apply_auto_design_results` path, including its
  deferred full-page rerun, has been deleted.
