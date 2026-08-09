# Current Inputs page parity audit

Read-only audit of the Runtime Inputs implementation. This is a scope ledger,
not an import or integration permission.

## Present in V2 slice

- Geometry: width, depth, span, section presentation choice
- Materials: concrete and reinforcement strengths
- Actions: bending, torsion, shear, axial
- Supports: left and right support choices
- Bottom/top reinforcement count and spacing modes
- Shear link diameter, legs, and spacing
- Deflection/serviceability controls, time-dependent inputs, and ducts/voids
- 2D section diagram, validation, revision-aware fixture result
- Section-shape control is canonical and revision-tested.
- Isolated save/load, fixture report download, and Design Brain apply action
  are now exercised through typed boundaries and AppTests.
- Runtime-reference default geometry/reinforcement values and vertically
  stacked action/geometry/material control groups are now explicit and tested.

## Still required for full parity

The current open-screen comparison confirms these high-impact visual defects:

- V2 shell/header and navigation do not match the Runtime viewport composition.
- V2-only lab actions and downloads are visible in the primary page flow.
- Control widths, left-column offset, vertical rhythm, and diagram placement
  differ from the Runtime reference.
- Reinforcement family controls do not yet match the Runtime section spacing,
  labels, and three-column geometry.
- Summary table is now required by the current review scope and is rendered as a
  typed, presentation-owned read-only component in the entered workspace.

- Multiple reinforcement rows per top/bottom layer and all row-level layout
  rules.
- Existing 2D and 3D diagram behaviour and all model-shape geometry fields.
- Recommendation panels and Design Guide/Design Brain interaction states.
- Batch design, save/load, active-beam navigation and per-beam isolation.
- Production engineering calculations and old-versus-V2 parity fixtures.
- Real report/PDF/export generation and download behaviour.
- Updating, error, loading, and calculation-completion states.

## Live comparison update (2026-08-04)

The live Runtime reference was verified on port 8501 and the isolated V2 page
on port 8513. The V2 header now exposes the same PDF Report action and the
navigation is represented as separate items with an active Inputs underline.
The comparison still does not pass: V2 lab expanders remain intentionally
available in the isolated workspace, and the entered-workspace geometry,
diagram scale, and reinforcement section rhythm still require pixel-diff
work. This entry records a measured change without treating it as parity.

Each item becomes a vertical slice with a canonical model owner, application
command, typed view model, component, and tests. No item is considered complete
because a placeholder widget exists.

## Measured baseline evidence

The four currently captured pairs have matching pixel dimensions, but a
deterministic Pillow comparison reports a non-empty difference bounding box
covering the viewport for every pair: `desktop--default`,
`desktop--bottom_count_mode`, `desktop--expanded_sections`, and
`narrow--default`. These captures are mismatch evidence, not a parity pass.
