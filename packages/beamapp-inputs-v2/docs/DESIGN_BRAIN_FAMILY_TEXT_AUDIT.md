# Design Brain Family Text and Formatting Audit

**Updated:** 9 August 2026
**Scope:** isolated Inputs V2 only; V1/Runtime remains read-only.
**Visual rule:** preserve the current card shell, spacing, expansion, button layout and red/blue/green system.

## Result

All Design Brain families now publish through one presentation-neutral
`FamilyDecision`, one engineering-advice formatter and one card renderer. The
family owns the engineering purpose, required checks and blocker wording;
presentation owns only layout and styling.

| Area | Result | Mechanical proof |
|---|---|---|
| Card shell and expansion | Pass | One shared card renderer and frozen visual-contract tests. |
| Status colour | Pass | Derived only from the final typed decision: green PASS, blue ACTION/overdesign, red failing BLOCKED, neutral no-action state. |
| Apply button | Pass | Displayed only for `ACTION` with the exact verified proposal; blocked and terminal outcomes cannot expose Apply. |
| Visible headings | Pass | Family-owned engineering titles; internal family identifiers remain diagnostic only. |
| Change wording | Pass | Structured geometry, longitudinal reinforcement, ligature and row changes are converted to natural engineering wording. |
| Reinforcement notation | Pass | Bar notation uses uppercase `N`, such as `4-N24`; companion count, diameter and row data are retained. |
| Engineering explanation | Pass | Direction and family purpose drive the explanation; the formatter does not invent engineering intent. |
| Blocker wording | Pass | Typed, family-owned sentences replace raw reason codes; geometry locks identify the exact locked dimension. |
| Required checks | Pass | Current and proposed checks are selected from authoritative calculation results according to each family contract. |
| Clause metadata | Pass with safe fallback | Clauses are calculation-owned and propagated unchanged; missing metadata remains explicitly unavailable rather than guessed. |
| Reference section | Pass | The compact card omits the former repeated `References:` paragraph while retaining structured metadata in the decision contract. |
| Current/proposed parity | Pass | Both sides carry their own authoritative check objects and clause references. |
| Terminal and no-action states | Pass | Target band, exact stop, locked repair and no-design-action outcomes have explicit typed projections. |

## Family contract coverage

Every family has a golden text/detail contract covering its visible titles,
engineering purpose, required check groups, blocker mapping, status colour and
CTA projection:

- geometry and detailing;
- serviceability;
- combined failure and combined overdesign;
- bending failure, bending overdesign and bending-failure/shear-cleanup;
- shear failure, shear overdesign and shear-failure/bending-optimisation;
- target band reached;
- exact stop proven; and
- locked no repair.

Mixed families own coordinated wording and do not reuse a single-domain final
message. All families use the same formatting structure:

1. current verified engineering state;
2. assessed or proposed revision;
3. assessed result;
4. concise engineering reason; and
5. a specific blocker sentence only when Apply is unavailable.

## Safety invariants

- A formatter cannot change status, family, blocker, colour or Apply intent.
- A blocked proposal is never presented as a final recommendation.
- A raw internal family identifier or rejection code is not visible advice.
- Clause numbers are not selected by the formatter, family, orchestrator or UI.
- The private 0.60 ULS proxy may support candidate detailing checks but is not
  shown as a supplied SLS action and is never persisted.
- User geometry locks are preserved by the neutral candidate and enforced at
  the single shared Apply/evaluation boundary.

## Verification

The audit is enforced by:

- `tests/test_design_brain_text_contracts.py`;
- `tests/test_design_brain_decision.py`;
- `tests/test_architecture.py`;
- `tests/test_runtime_visual_contract.py`;
- `tools/architecture_check.py`; and
- `tools/design_brain_completion_audit.py`.

At this update, the complete offline acceptance gate reports **332 passed and
7 intentionally skipped lab-control tests**, the architecture checker passes,
all 13 family recovery/terminal fixtures pass, and the protected V1 Runtime
status is unchanged.

Pixel-reference capture approval remains a separate visual gate. It does not
change or weaken the text and decision contracts above.
