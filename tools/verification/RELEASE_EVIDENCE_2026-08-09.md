# Runtime super-audit release evidence — 2026-08-09

## Decision

`NOT RELEASE-ELIGIBLE`

All current-source automated and AppTest gates pass. The real-browser gate
SA-011 remains `BLOCKED_ENVIRONMENT`, so the composite SA-012 release gate
remains `OPEN`. Nothing has been uploaded to GitHub.

## Current source

- Branch: `main`
- Latest verified commit: `c57a9fb` (`Use one authority for keyed widget defaults`)
- Worktree at evidence collection: clean

## Passing evidence

| Gate | Current result |
|---|---|
| Packaged Design Brain suite | 363 passed, 7 explicitly skipped |
| Architecture boundary | 82 Python files passed |
| Installed-package identity | PASS |
| Fresh temporary-environment install | PASS |
| Engineering/state verifier mutations | PASS |
| Family predicate corpus | 90/90 accounted for and passing |
| Streamlit compatibility | PASS |
| Accessibility inventory | All nine routes; zero empty widget labels |
| Inputs Apply revision/rerun | PASS |
| Load Analysis publication/round-trip | PASS |
| Shared Design Actions | PASS |
| Authoritative result-store lock | PASS |
| Material validation/recovery | PASS |
| Bending diagram composition | PASS |
| Beam-summary policy | PASS |
| Longitudinal-row policy | PASS |
| Stateful Runtime fuzz | 1,000/1,000 operations; 50/50 sequences; seed 20260809 |
| Exhaustive Runtime controls | 211/211 inventoried and handled; process exit 0 |

The 211-control sweep covers all nine routes in isolated AppTest sessions: 39
enabled buttons, 60 enabled number inputs, 60 selectboxes, 8 non-navigation
radios, 8 checkboxes, 11 toggles, 9 text inputs, 9 route-navigation radios,
and 7 intentionally disabled number inputs.

## Unresolved required evidence

SA-011 requires real-browser journeys at narrow-phone, large-phone, tablet and
desktop widths, including portrait/landscape, keyboard behaviour, cold/warm
Apply, navigation, scroll-position retention, overflow, touch targets,
screenshots and console inspection.

The in-app browser backend returned an empty browser list on both availability
checks. AppTest cannot prove browser scroll or physical viewport behaviour, so
no substitute evidence has been used and SA-011 remains unresolved.

## Upload rule

Do not upload until SA-011 passes, SA-012 is changed to `VERIFIED`, the final
worktree is clean, and the user explicitly approves the upload.
