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

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.final_publication import (  # noqa: E402
    final_design_guide_publication_is_terminal_no_action_surface,
)
from design_brain.publication import enforce_family_selection_publication_contract  # noqa: E402


def _stale_green_payload() -> dict[str, Any]:
    overview = {
        "all_key_pass": True,
        "any_fail": False,
        "statuses": {"bending": "PASS", "shear": "PASS"},
        "utils": {"bending": 0.12, "shear": 0.98},
        "worst_util": 0.98,
    }
    return {
        "overview": dict(overview),
        "debug_trace": {"overview": dict(overview)},
        "guidance_items": [
            {
                "title_main": "Design is efficient",
                "title": "Design is efficient",
                "headline": "Design is efficient",
                "summary_line": "All checks pass.",
                "selected_family_id": "TARGET_BAND_REACHED",
                "published_family_id": "TARGET_BAND_REACHED",
                "cta_family_id": "TARGET_BAND_REACHED",
                "status": "PASS",
                "guidance_intent": "already_efficient",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "updates": {},
                },
            }
        ],
    }


def _threshold_only_exact_stop_item() -> dict[str, Any]:
    proof = {
        "family": "bending",
        "cleanup_search_exhaustive": True,
        "best_safe_candidate_applied": True,
        "no_second_cta_required": True,
        "executable_target_band_candidate_count": 0,
        "best_safe_final_util": 0.41,
        "failed_check_status": "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
        "failed_check_name": "final accepted bending utilisation threshold",
        "failed_check_demand": "preferred cleanup target",
        "failed_check_util": 0.41,
    }
    return {
        "selected_family_id": "TARGET_BAND_REACHED",
        "published_family_id": "TARGET_BAND_REACHED",
        "cta_family_id": "TARGET_BAND_REACHED",
        "status": "PASS",
        "blocker_reason": "terminal_pass_no_action",
        "exact_stop_proof": {"bending": proof},
        "candidate_search_evidence": dict(proof),
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "blocking_reason": "terminal_pass_no_action",
            "updates": {},
        },
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact = ARTIFACT_DIR / f"target_band_terminal_publication_guard_regression_{stamp}.json"
    report = AUDIT_DIR / f"target_band_terminal_publication_guard_regression_{stamp}.md"
    snapshot["artifact"] = str(artifact)
    snapshot["report"] = str(report)
    artifact.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(
        "\n".join(
            [
                "# Target Band Terminal Publication Guard Regression",
                "",
                f"Result: `{snapshot['status']}`",
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
        ),
        encoding="utf-8",
    )
    return artifact, report


def main() -> int:
    chooser = classify_family_from_raw_flags(
        {
            "bending_overdesigned": True,
            "bending_acceptable": True,
            "shear_within_target_band": True,
            "shear_acceptable": True,
        },
        evidence={
            "bending_utilisation": 0.12,
            "shear_utilisation": 0.98,
            "case_id": "bending_underband_shear_target_cannot_be_target_band_terminal",
        },
    )
    enforced = enforce_family_selection_publication_contract(_stale_green_payload())
    item = dict((enforced.get("guidance_items") or [{}])[0])
    debug = dict(enforced.get("debug_trace") or {})
    threshold_item = _threshold_only_exact_stop_item()
    threshold_terminal = final_design_guide_publication_is_terminal_no_action_surface(
        threshold_item,
        {},
        selected_family="TARGET_BAND_REACHED",
    )

    checks = {
        "chooser_selects_bending_overdesign": chooser.get("selected_family_id") == "BENDING_OVERDESIGN_GOVERNS",
        "chooser_does_not_select_target_band": chooser.get("selected_family_id") != "TARGET_BAND_REACHED",
        "stale_green_reclassified_to_bending_overdesign": debug.get("selected_family_id")
        == "BENDING_OVERDESIGN_GOVERNS",
        "stale_green_not_rebuilt_as_target_band": item.get("selected_family_id") != "TARGET_BAND_REACHED",
        "stale_green_not_pass_terminal": str(item.get("status") or "").upper() != "PASS",
        "stale_green_records_contract_violation": item.get("family_match_violation_reason")
        == "selected_family_id_does_not_match_published_family_id",
        "threshold_only_exact_stop_not_terminal": threshold_terminal is False,
    }
    failures = [key for key, ok in checks.items() if not ok]
    snapshot = {
        "schema": "target_band_terminal_publication_guard_regression.v1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "chooser": chooser,
        "enforced_item": item,
        "enforced_debug": debug,
        "threshold_only_exact_stop_terminal": threshold_terminal,
    }
    artifact, report = _write(snapshot)
    print(f"{snapshot['status']}: {artifact}")
    print(f"REPORT: {report}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
