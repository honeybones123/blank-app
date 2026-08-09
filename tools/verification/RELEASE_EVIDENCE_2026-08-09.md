# Runtime super-audit release evidence — 2026-08-09

## Decision

`RELEASE-ELIGIBLE — EXPLICIT UPLOAD APPROVAL REQUIRED`

All current-source automated, AppTest and real-browser gates pass. SA-011 and
the composite SA-012 release gate are `VERIFIED`. Nothing has been uploaded to
GitHub; publication still requires the user's explicit approval.

## Current source

- Branch: `main`
- Latest verified source commit: `189b9bb` (`Use one authority for the design section slider`)
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
| Responsive/browser matrix | 360x800, 430x932, 800x360, 768x1024, 1024x768, 1440x900; PASS |
| Cold/warm Apply scroll retention | 1866 px before and after both operations; PASS |
| 2D/3D UI-state isolation | Input/result revisions, actions and geometry unchanged; PASS |

The 211-control sweep covers all nine routes in isolated AppTest sessions: 39
enabled buttons, 60 enabled number inputs, 60 selectboxes, 8 non-navigation
radios, 8 checkboxes, 11 toggles, 9 text inputs, 9 route-navigation radios,
and 7 intentionally disabled number inputs.

## Real-browser evidence

The local current-source application was exercised in the Codex in-app browser
at narrow-phone, large-phone, phone-landscape, tablet, tablet-landscape and
desktop sizes. Document width and the Streamlit main region stayed contained at
all six sizes, including an open 300 px sidebar at 1024x768. Mobile and desktop
screenshots were visually inspected.

In the cold mobile case, Enter committed `Mu=200`; Apply preserved the live
field and authoritative action at 200, changed depth 300 to 400 mm, advanced
input/result revision 2 to 3, and left main scroll at exactly 1866 px. The warm
case committed `Mu=300`, changed depth 400 to 500 mm, advanced revision 4 to 5,
and again left scroll at 1866 px. Navigation through Load Analysis and back
preserved revision 5, `Mu=300`, `D=500` and `TARGET_BAND_REACHED`.

Switching the 3D display with the control leaves the authoritative input and
result revisions, action, depth and governing family unchanged. All 25 visible
application buttons in the 360 px session had at least a 44 px hit height.
Browser logs contained informational component binding messages only, with no
warning or error entries.

The browser sweep found and drove two root fixes: responsive CSS formerly ran
only during cached Python module import, and summary/tooltip children could
widen tablet content. CSS now emits once per Streamlit run, tables scroll only
inside their owned detail container, and tooltip placement is bounded below the
responsive breakpoint. A separate static contract locks these lifecycle and
containment rules.

## Upload rule

The technical release gate is satisfied. Do not upload until the evidence
checkpoint is committed, the worktree is clean, and the user explicitly
approves the upload.
