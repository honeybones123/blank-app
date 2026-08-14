# Calculation-page compact inputs migration plan

## Scope

Replace the large input rails on these calculation pages only:

- Bending
- Shear
- Creep
- Shrinkage
- Crack Control
- Deflection

Do not change Start, Beam Inputs, Load Analysis, engineering equations, result
packs, publication identities, Design Brain ownership, Apply, or calculation-box
content and formatting.

The target presentation is one `Inputs used for this check` panel immediately
before the calculation results. It has compact summary rows, independently
expandable presentation-only rows with no surrounding card shell, edit action,
or source badge. Multiple rows may remain open: enforcing a single-open accordion
must not add session state, callbacks, widget unmounting or engineering reruns.

## Non-negotiable state contract

The migration must preserve the current authoritative mutation path.

1. Summary rows read the current committed engineering projection. They do not
   read a second component-owned engineering dictionary.
2. Expansion is presentation state only. It cannot set `inputs_dirty`, create an
   input revision, calculate, publish, run the Design Brain, or invalidate Apply.
3. Existing editable fields keep the exact widget key, type, constraints,
   help text, and callback.
4. An editable widget is never conditionally unmounted merely because its row is
   collapsed. Widgets remain mounted in the calculation-page fragment, with CSS
   controlling visibility, or are hosted in one permanently mounted edit region.
5. A widget key is rendered exactly once. The old rail and compact component
   cannot coexist on a migrated page.
6. A missing value and a genuine numeric zero remain distinct.
7. Beam Inputs and Load Analysis source selection is displayed but cannot be
   changed by the component unless the existing authorised source-control widget
   is deliberately referenced with its existing key and callback.
8. Page navigation does not copy values through widget state.
9. Expand/collapse is handled as a presentation-only interaction and must not
   request a fragment or page rerun. Engineering execution is never permitted.
10. Every summary is derived from the same committed snapshot/result revision
    displayed by the calculation card below it.

## Shared component contract

Create one presentation package, for example:

```text
engineering_page_sections/compact_check_inputs/
  contract.py
  registry.py
  summaries.py
  renderer.py
  styles.py
```

Suggested types:

```python
@dataclass(frozen=True)
class CheckInputField:
    field_id: str
    label: str
    symbol: str | None
    unit: str | None
    source: InputSource
    value_reader: AuthoritativeValueReader
    required: bool
    editable: bool
    existing_widget_ref: ExistingWidgetRef | None

@dataclass(frozen=True)
class CheckInputCategory:
    category_id: str
    label: str
    ordered_fields: tuple[CheckInputField, ...]
    summary_formatter: SummaryFormatter
    visibility: VisibilityRule

@dataclass(frozen=True)
class CheckInputPanelConfig:
    page_slug: str
    categories: tuple[CheckInputCategory, ...]
    edit_destination: EditDestination
```

`ExistingWidgetRef` is a reference to an existing renderer/key/callback. It is
not permission to construct a replacement widget with a new key.

The shared renderer owns presentation only. Page contracts own which fields are
shown. Existing application services remain the only input/publication owners.

## Page input inventory

### Bending

**Design actions**

- Positive and negative ULS moment
- SLS moment when the SLS check is active
- Axial force
- Prestress action where present
- Action mode/source, read-only in the summary

**Section and material**

- Section shape
- Rectangular width, or flange/web dimensions for T/I sections
- Overall depth and effective-depth evidence
- Span where used by the displayed check
- Concrete strength and steel strength
- Concrete and steel modulus where used by SLS bending
- Top, bottom and side cover

**Longitudinal reinforcement**

- Bottom row-one and row-two count/diameter
- Top row-one and row-two count/diameter
- Bottom and top row gaps
- Calculated provided steel areas as read-only summaries

**Detailing/calculation settings**

- Link diameter where it affects effective depth
- Concrete stress-block model
- Strength factor only where it is an exposed authoritative setting

Do not put diagram-state, selected-sign view, open-check state, or navigation
state in the input panel.

### Shear

**Design actions**

- ULS shear
- Torsion
- Axial force
- Associated bending moment used by the shear model
- Prestress action/effects where enabled
- SLS/ULS display mode only where it genuinely changes the check input

**Section and material**

- Section shape and rectangular/T/I dimensions
- Overall depth and effective-depth evidence
- Span and support/system mode where consumed
- Concrete and steel strengths
- Top, bottom and side cover

**Longitudinal reinforcement**

- Top and bottom reinforcement arrangements used by the shear calculation
- Row gaps and bar coordinates where the general method consumes them
- Minimum clear-spacing/aggregate-size evidence where detailing depends on it

**Shear reinforcement**

- Link diameter
- Effective legs
- Link spacing
- Any distinct end/mid spacing that is genuinely active
- Auto/manual shear-design status as read-only provenance

**Ducts and prestress voids**

- Number and diameter of ducts
- Duct-location/reduction option
- Show only when present or enabled

**Method settings**

- `k_v` method
- Crack-angle/theta input where user-authoritative
- Shear strength factor where exposed

Do not include visual overlays, diagram mode, expanded MCFT breakdown, tab
selection, or other teaching/display controls.

### Creep

**Section and material**

- Section dimensions used to obtain theoretical thickness
- Concrete strength and modulus
- Member/faces exposed
- Theoretical thickness as calculated, read-only

**Environment**

- Creep environment

**Time and loading**

- Time after loading
- Age at loading
- Sustained stress/action provenance
- Initial concrete stress and stress ratio as calculated, read-only

**Dependent results**

- Authoritative shrinkage/material dependencies only if the creep equation
  actually consumes them; display them read-only.

Do not duplicate derived `k2`-`k6`, creep coefficient, or strain as inputs; these
belong in the calculation results.

### Shrinkage

**Method**

- Selected shrinkage method/standard

**Section and material**

- Section dimensions
- Concrete strength
- Member/faces exposed
- Theoretical thickness as calculated, read-only

**Environment**

- AS 3600 shrinkage environment for the existing method
- Relative humidity for the EC2/CIRIA method
- Cement class for the EC2/CIRIA method

**Time and drying**

- Time since commencement of drying
- End-of-curing/start-of-drying age where required by the method

Method visibility must be contract-driven: hidden method fields remain mounted
only where needed to preserve their established state, but cannot affect the
active calculation until their method is selected.

### Crack Control

**Method**

- Existing AS 3600, AS 5100 wall, or CIRIA C766/EC2 method

**Design actions and dependent values**

- SLS moment/action source
- Service steel stress or authoritative stress result
- Creep coefficient and shrinkage strain where consumed

**Section and material**

- Section shape and active tension-zone dimensions
- Concrete and steel modulus
- Tension-face cover

**Reinforcement**

- Active tension-face bars, diameters, spacing and row gap
- Provided tension steel area as calculated, read-only

**Crack-control parameters**

- Exposure class and characteristic crack-width limit
- Member type and `k1`/`k2` parameters for the selected standard
- Wall base-zone flag for AS 5100 wall checks
- Restraint type for CIRIA C766/EC2

Do not include diagram view or individual calculation-step expansion state.

### Deflection

**Serviceability actions**

- SLS moment and shear
- UDL/point-load values and positions when the selected action model consumes
  them
- Permanent/imposed components and combination factor
- Action source and selected load case as read-only provenance

**Section and material**

- Section shape and rectangular/T/I dimensions
- Span/effective span
- Concrete modulus, effective modulus and creep coefficient

**Reinforcement**

- Bottom and top reinforcement arrangements
- Bottom/top row gaps
- Reinforcement areas/effective depths as calculated, read-only

**Support and limits**

- Support condition
- Deflection limit ratio

**Long-term parameters**

- Sustained stress/action values consumed by the long-term calculation
- Shrinkage/creep dependencies, read-only where derived
- Simplified/custom effective-inertia selection and custom value, if active

Do not include diagram visibility, selected diagram, cache keys or multispan
presentation state.

## Rendering behaviour matching the reference

- Header: `Inputs used for this check` without an additional action button.
- No surrounding white card or source badge; only the compact input rows render.
- Rows contain icon, category label, concise authoritative summary and chevron.
- Rows expand independently. Do not enforce a single-open accordion through
  session state or conditional widget mounting.
- Expanded content uses four columns on desktop, two on tablet and one on mobile.
- Field backgrounds and typography reuse existing StructuralBase tokens.
- Warning state names the missing/invalid field; it never substitutes zero.

For session safety, all editable widget owners remain mounted. The accordion may
hide inactive regions visually, but it must not destroy and recreate the widgets.

## Migration sequence

1. Add an inventory test that records the existing widget key, callback, type,
   constraints and authoritative value source for every field above.
2. Add the typed shared contract and read-only summary renderer.
3. Add an execution probe around calculation, publication and Design Brain calls.
4. Migrate Creep first because it has the smallest editable surface.
5. Verify Creep expansion produces zero engineering executions and that edits use
   existing keys/callbacks.
6. Migrate Shrinkage, including method-specific visibility and state retention.
7. Migrate Bending and verify ULS/SLS action switching, positive/negative bending,
   T/I geometry and two-row reinforcement.
8. Migrate Shear and verify links, ducts, method selection and detailing fields.
9. Migrate Crack Control and verify all three standards/methods independently.
10. Migrate Deflection and verify manual/calculated SLS actions, support type,
    long-term dependencies and multispan state.
11. Remove each page's old large input rail in the same migration change that
    enables its compact renderer.
12. Delete shared legacy rail code only after production callers reach zero.
13. Keep permanent architecture checks prohibiting duplicate widget ownership and
    component-local engineering state.

## Required verification

### State invariants

- Expand/collapse ten times: zero input revisions and identical widget values.
- Switch between every calculation page: no input resets or hydration rollback.
- Change ULS/SLS mode where supported: correct values remain associated with the
  correct mode.
- Toggle Load Analysis actions on Inputs, visit every calculation page, toggle it
  off and confirm manual actions are restored.
- Edit every authorised inline field and prove exactly one existing callback and
  one authoritative mutation occur.
- No page renders the same widget key twice.

### Engineering invariants

- Frozen before/after snapshots produce byte-equivalent authoritative input
  payloads.
- Calculation results and publication identities are identical for unchanged
  inputs.
- Expansion causes zero calculations, zero Design Brain runs and zero publishes.
- Missing inputs display `Not provided` and warning evidence, never numeric zero.
- Source badges match the actual action/input owner.

### Page coverage

- Bending: positive, negative, ULS, SLS, RECT, T and I, one/two rows.
- Shear: no links, 2/3/4/5/6 legs, torsion, ducts, all supported methods.
- Creep: environments, ages, faces exposed and missing sustained loading.
- Shrinkage: each supported method, environment/RH/cement branches.
- Crack: AS 3600, AS 5100 wall and CIRIA C766/EC2.
- Deflection: manual/calculated actions, support types, short/long term and
  multispan.

### UI coverage

- Desktop, tablet and mobile screenshots match the reference hierarchy.
- No horizontal overflow.
- Keyboard control exposes header, `Edit inputs`, every row and every editable
  field with accessible names.
- Existing calculation boxes remain visually and textually unchanged.

## Completion evidence

The migration is complete only when all six calculation pages use the shared
component, old input rails have no callers and are deleted, the state and
engineering invariants pass, and live browser checks prove page switching and
editing preserve authoritative values without full-page reruns.
