# Inputs V2 integration proposal

Status: **not approved — proposal only**

This proposal is the final handoff shape for the isolated Inputs V2 lab. It
does not authorize edits to the Beamapp Runtime.

## Preconditions

Integration may be considered only after the acceptance report shows no open
visual, behavioral, engineering, persistence/report, or isolation gates and
the owner gives explicit written approval.

Required evidence:

- approved Runtime and V2 reference captures for every manifest state and
  viewport;
- old-versus-V2 production calculation parity fixtures;
- production persistence, report/PDF, export, navigation, and per-beam tests;
- Design Brain proposals applied only through the canonical command boundary;
- unchanged Runtime git status and protected-path audit before and after the
  proposed patch.

## Narrow integration patch

1. Add the approved V2 package and its declared entry point.
2. Add one Runtime navigation route that can select V2 explicitly.
3. Keep the existing Inputs route unchanged behind a feature flag.
4. Route persistence, engineering, reports, and exports through the tested
   V2 ports; do not share Runtime session-state dictionaries.
5. Run the complete acceptance suite in an isolated process and port.

No broad stylesheet, alias, widget, or calculation copy is permitted in this
patch.

## Rollback

Disable the V2 feature flag and restore the previous Inputs route. Remove only
the V2 route registration and package reference; do not delete Runtime data,
snapshots, projects, or configuration. Re-run the Runtime smoke suite and
verify the protected-path hash report is unchanged.

## Approval record

- Owner: ____________________
- Date: _____________________
- Acceptance report: _____________________
- Approved integration commit: _____________________
- Rollback rehearsal result: _____________________

