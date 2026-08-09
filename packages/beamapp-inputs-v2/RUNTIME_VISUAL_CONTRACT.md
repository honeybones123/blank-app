# Runtime Inputs visual contract

This is the code-derived visual contract for the isolated V2 lab. The Runtime
application is read-only; these values are extracted from its page shell,
Inputs page styles, widget coordinators, and reference captures.

## Desktop shell

- Streamlit layout: `wide`
- Canvas: white
- Base font size: `14px`
- Main content max width: `1180px`
- Main block padding: `2rem` top, `2.25rem` left/right, `2rem` bottom
- H1: `2rem`, line-height `1.15`
- H2: `1.45rem`
- H3: `1.1rem`

## First editable state

- Geometry and materials appear before reinforcement.
- The diagram occupies the right-hand column of the geometry area.
- Bottom Reinforcement, Top Reinforcement, and Shear are sibling columns below
  the horizontal divider.
- Default editable fixture: `250 x 300 mm`, span `2000 mm`, steel `500 MPa`,
  concrete `40 MPa`, bottom `3-N10`, top `2-N10`, shear off.

## State matrix

The parity gate must capture both desktop and agreed narrow viewports for:

1. default landing state;
2. default editable state;
3. expanded sections;
4. bottom count mode;
5. bottom spacing mode;
6. one-row and two-row reinforcement;
7. validation state;
8. updating/error state.

An image is not approved solely because it exists. Each state requires the
same widget values, viewport, browser, and explicit diff approval.

## Ownership rule

These values are presentation concerns only. They must be implemented in V2
presentation tokens/components and must not be imported into domain,
application, engineering, or infrastructure code.
