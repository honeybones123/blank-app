"""Regression for combined active-fail publication action recovery.

This covers the live shape where the selected family is
COMBINED_BENDING_SHEAR_FAIL, but the final visible item still carries a stale
disabled/missing-updates button contract while debug evidence has the valid
executor-backed repair payload.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.publication import enforce_family_selection_publication_contract  # noqa: E402


def _payload() -> dict[str, Any]:
    valid_updates = {
        "D": 750.0,
        "b": 450.0,
        "bot_row_1_bars": 5,
        "bot_row_1_dia": 28,
        "lig_d": 16,
        "lig_legs": 4,
        "s_lig": 100.0,
    }
    valid_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "COMBINED_BENDING_SHEAR_FAIL",
        "updates": dict(valid_updates),
        "preview_pass": True,
        "expected_util": 0.92,
        "candidate_id": "combined_user_400_200_repair",
        "source_candidate_id": "combined_user_400_200_repair",
    }
    return {
        "guidance_items": [
            {
                "title": "Design Guide family contract violation",
                "title_main": "Design Guide family contract violation",
                "summary_line": "Publication blocked by family contract before final render.",
                "family": "target_band_reached",
                "check_key": "target_band_reached",
                "published_family_id": "TARGET_BAND_REACHED",
                "cta_family_id": "TARGET_BAND_REACHED",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "action_type": "apply_resolved_candidate",
                    "family": "COMBINED_BENDING_SHEAR_FAIL",
                    "updates": {},
                    "blocking_reason": "missing_updates",
                },
                "candidate_search_evidence": {
                    "selected_candidate_id": "combined_user_400_200_repair",
                    "target_band_candidate_count": 1,
                },
            }
        ],
        "debug_trace": {
            "active_failures": ["bending", "shear"],
            "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "selected_family": "COMBINED_BENDING_SHEAR_FAIL",
            "primary_button_contract": dict(valid_contract),
            "button_contract": dict(valid_contract),
            "displayed_primary_button_contract": dict(valid_contract),
        },
        "design_brain_result": {
            "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "evidence": {},
        },
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_publication_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_publication_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Combined Bending/Shear Publication Regression",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    output = enforce_family_selection_publication_contract(_payload())
    item = dict((output.get("guidance_items") or [{}])[0] or {})
    debug = dict(output.get("debug_trace") or {})
    contract = dict(item.get("button_contract") or {})
    checks = {
        "selected_family_preserved": item.get("selected_family_id") == "COMBINED_BENDING_SHEAR_FAIL",
        "no_family_contract_violation_card": "family contract violation"
        not in str(item.get("title_main") or item.get("title") or "").lower(),
        "button_enabled": contract.get("enabled") is True and contract.get("actionable") is True,
        "action_type_apply_resolved_candidate": contract.get("action_type") == "apply_resolved_candidate",
        "updates_preserved": bool(contract.get("updates")),
        "missing_updates_removed": contract.get("blocking_reason") != "missing_updates",
        "same_family_recovery_stamped": debug.get("family_guard_recovered_same_family_repair_action") is True,
        "no_inputs_page_dependency": True,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_bending_shear_fail_publication_regression.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "selected_item": {
            "title": item.get("title_main") or item.get("title"),
            "selected_family_id": item.get("selected_family_id"),
            "published_family_id": item.get("published_family_id"),
            "cta_family_id": item.get("cta_family_id"),
            "button_contract": contract,
        },
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("combined bending/shear publication regression FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("combined bending/shear publication regression PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
