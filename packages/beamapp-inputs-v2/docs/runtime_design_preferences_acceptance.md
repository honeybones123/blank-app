# Runtime Family-Owned Design Preferences Acceptance

Date: 2026-08-10  
Branch: `agent/runtime-design-preferences`

## Scope

- Changed only `packages/beamapp-inputs-v2`.
- No presentation modules were changed.
- The frozen standalone V2 archive was not changed.
- The existing Design Brain card, colour and Apply presentation contracts remain unchanged.

## Architecture evidence

- One immutable `DesignPreferenceProfile` supplies passive configuration only.
- `FamilyRunContext` binds current inputs, current calculations, preferences and search budgets to the selected family.
- Mandatory rejection occurs before preference ranking.
- Hard congestion codes and soft buildability scores are recorded separately.
- Near-limit treatment is available only through explicit family-owned rules.
- Candidate ranking requires a selected `FamilyContract`; there is no unbound fallback.
- `CandidateEvidence` is factual audit evidence and has no selection method.
- Preference profile identity and version are preserved in internal search evidence.

## Verification

- Full Runtime suite: `355 passed, 7 skipped`.
- Architecture checker: passed across 83 Python files.
- Family completion audit: all 23 cases passed.
- Calculation shadow parity: passed.
- Apply and visual-contract tests: passed as part of the full suite.
- Acceptance gate: passed isolation, tests, architecture, parity and family audit.
- Clean wheel installation: `beamapp-inputs-v2 0.1.0` imported from the clean environment's `site-packages`.

## Performance evidence

Measured against the unchanged pre-feature `HEAD` using
`tools/design_preferences_benchmark.py`.

| Case | Version | Median | p95 | Worst | Generated | Cache hits | Full evaluations |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ordinary non-triggered | Baseline | 0.444 ms | 1.118 ms | 1.142 ms | 0 | 0 | 0 |
| Ordinary non-triggered | Updated | 0.381 ms | 0.606 ms | 0.934 ms | 0 | 0 | 0 |
| Triggered Fast | Baseline | 284.640 ms | 290.620 ms | 290.620 ms | 1,158 | 13 | 1,022 |
| Triggered Fast | Updated | 280.946 ms | 291.657 ms | 291.657 ms | 1,158 | 13 | 1,022 |

The ordinary median improved by about 14.2% with zero additional evaluations.
The triggered median improved by about 1.3%. Triggered p95 and worst-case time
were about 0.4% higher in this sample, while candidate generation and full
evaluation counts remained exactly bounded at their baseline values.
