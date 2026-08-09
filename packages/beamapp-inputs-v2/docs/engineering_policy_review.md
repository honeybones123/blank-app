# Engineering Policy Review

This record separates AS 3600 requirements, independently checked physical
invariants and application design policies. A policy is not presented as code
compliance merely because it is useful to candidate search.

| Topic | Current authority | Status | Required follow-up |
|---|---|---|---|
| Concrete strength grades | AS 3600:2018(+A1) Clause 3.1.1.1 lists 20, 25, 32, 40, 50, 65, 80 and 100 MPa. | Confirmed | Retain the exact grade set and rejection boundary. |
| 500 MPa reinforcement | Table 3.2.1 explicitly identifies 500 MPa reinforcement grades and ductility classes. | Confirmed | The eventual material model should also carry product/ductility class. |
| 600 MPa reinforcement | Clause 1.1.2(d) and Table 3.2.1 notes permit higher grades subject to additional characteristic properties. | Conditional | Do not describe 600 MPa as verified without product-property evidence. |
| 400 MPa reinforcement | Not established by the reviewed AS 3600:2018(+A1) grade table. It remains a Runtime compatibility policy. | Review required | Obtain an approved product/legacy design basis or remove through an explicit saved-session migration. |
| Depth/width ratio <= 2 | Application constructability and search policy. | Confirmed as app policy only | Keep clause metadata blank and never label this ratio as AS 3600 compliance. |
| 20 mm clear fit spacing | Application constructability policy used by the arrangement evaluator. | Confirmed as app policy only | Keep separate from code-mandated aggregate/bar-spacing checks until aggregate size is modelled. |
| Specified concrete cover | The model has cover but no exposure classification or required durability cover. | Not checked | Preserve the entered value but never publish a durability `PASS` until those inputs and checks exist. |

## Release implications

- SA-004 remains open for the 400 MPa policy decision and conditional 600 MPa
  product evidence.
- Geometry and reinforcement-fit fixtures may independently prove physical
  arithmetic and application-policy behaviour without claiming AS 3600 status.
- Durability cover is informational only in the current result contract.
