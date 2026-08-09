# Reinforcement arrangement policy compatibility audit

The shared policy is passive. Family classification, candidate generation,
filtering, ranking, exact-stop proof, publication and Apply remain in the
existing DesignBrainService/orchestrator paths.

| Family | Longitudinal moves | Shear moves | Layers | Acceptance owner | Status |
|---|---|---|---|---|---|
| Bending failure | Existing bending ladder | Only through combined contract | practical row enumeration | bending family | compatible |
| Shear failure | Not a primary repair | Existing diameter/spacing/legs ladder | only when explicitly requested | shear family | compatible |
| Combined failure | coordinated | coordinated | permitted by combined candidate | combined family | compatible |
| Bending overdesign | bar count/diameter and geometry | unchanged | fit utility only | bending cleanup | compatible |
| Shear overdesign | unchanged | spacing/diameter/legs/removal | unchanged | shear cleanup | compatible |
| Serviceability | distribution/count/diameter/layers | unchanged | practical rows | serviceability family | compatible |
| Geometry/detailing | fit-driven arrangements | enclosure checked | permitted where fit requires | geometry family | compatible |
| Locked/no repair, target, exact stop | no new moves | no new moves | no new moves | terminal family | unchanged |

The policy supplies standard preferences, ratio diagnostics and fit metadata;
it cannot select a family result or create an Apply payload. A remaining gap is
that the current V2 UI does not expose manual Row 1/Row 2 editing; Design Brain
proposals can nevertheless store and draw a verified layered arrangement.
