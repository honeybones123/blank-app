"""Regression: combined active-fail candidates must satisfy longitudinal detailing.

The combined family owns its target-band refinement candidate generation. It
must not publish a candidate that only becomes blocked later by the shared
minimum-bar or 300 mm longitudinal c/c spacing guards.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (  # noqa: E402
    resolve_longitudinal_bar_spacing_rule,
    resolve_minimum_longitudinal_bar_rule,
)
from design_brain.families.combined_bending_shear_fail import (  # noqa: E402
    CombinedBendingShearFailFamily,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _base_state() -> dict:
    return {
        "b": 450.0,
        "bw": 450.0,
        "D": 700.0,
        "cover_side": 40.0,
        "lig_d": 12.0,
        "bot1_count": 2,
        "db_bot_1": 28,
        "bot2_count": 0,
        "db_bot_2": 28,
        "top1_count": 2,
        "db_top_1": 20,
        "top2_count": 0,
        "db_top_2": 0,
    }


def _write(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_longitudinal_spacing_candidate_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_longitudinal_spacing_candidate_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Combined Bending/Shear Longitudinal Candidate Regression",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Invalid Candidates",
                "",
                *(
                    [
                        f"- `{item['candidate_id']}`: min=`{item['minimum_rule'].get('valid')}`, "
                        f"spacing=`{item['spacing_rule'].get('valid')}`, updates=`{item['updates']}`"
                        for item in snapshot["invalid_candidates"]
                    ]
                    or ["- none"]
                ),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    family = CombinedBendingShearFailFamily()
    base = _base_state()
    candidates = family.build_target_band_refinement_candidates(base, limit=24)
    invalid: list[dict] = []
    valid_rows: list[dict] = []
    for candidate in candidates:
        updates = dict(candidate.get("updates") or {})
        minimum_rule = resolve_minimum_longitudinal_bar_rule(base, updates)
        spacing_rule = resolve_longitudinal_bar_spacing_rule(base, updates)
        row = {
            "candidate_id": candidate.get("candidate_id"),
            "updates": updates,
            "minimum_rule": minimum_rule,
            "spacing_rule": spacing_rule,
        }
        if minimum_rule.get("valid") and spacing_rule.get("valid"):
            valid_rows.append(row)
        else:
            invalid.append(row)

    first_updates = dict(candidates[0].get("updates") or {}) if candidates else {}
    checks = {
        "candidates_generated": bool(candidates),
        "all_generated_candidates_pass_minimum_bar_rule": not invalid,
        "all_generated_candidates_pass_longitudinal_spacing_rule": not invalid,
        "first_candidate_bottom_count_adjusted": int(first_updates.get("bot_row_1_bars") or 0) >= 3,
        "first_candidate_top_count_adjusted": int(first_updates.get("top_row_1_bars") or 0) >= 3,
        "first_candidate_has_canonical_top_keys": {"top_row_count", "top_row_1_bars", "top_row_1_dia"} <= set(first_updates),
        "first_candidate_has_canonical_bottom_keys": {"bot_row_count", "bot_row_1_bars", "bot_row_1_dia"} <= set(first_updates),
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_bending_shear_fail_longitudinal_spacing_candidate_regression.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "candidate_count": len(candidates),
        "valid_candidate_count": len(valid_rows),
        "invalid_candidates": invalid,
        "first_candidate_updates": first_updates,
    }
    json_path, report_path = _write(snapshot)
    print(f"combined bending/shear longitudinal candidate regression {snapshot['result']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
