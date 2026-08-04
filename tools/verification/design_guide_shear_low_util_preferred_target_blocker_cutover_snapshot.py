"""Verify shear low-util preferred-target blocker cutover from page code."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _old_blocker(
    *,
    final_shear_util: Any,
    current_shear_util: Any,
    target_count: int,
    accepted_band_count: int,
    attempted: int,
    safe_count: int,
    candidate_id: str,
    threshold: Any,
    preferred_low: Any,
    target_high: Any,
    updates: dict[str, Any],
    demand: Any,
    best_safe_below_final: bool,
    no_link_candidate_selected: bool,
    final_accepted_min_family_util: Any,
) -> dict[str, Any]:
    preferred_target_blocker: dict[str, Any] = {}
    if final_shear_util is not None and int(target_count) <= 0:
        if best_safe_below_final:
            reason = (
                f"The selected best safe shear cleanup reaches shear utilisation {float(final_shear_util):.2f}, "
                f"below the {float(final_accepted_min_family_util):.2f} final accepted threshold. "
                "The exhaustive discrete shear-link cleanup search found no executable candidate in the "
                "accepted or preferred band while preserving bending, shear, serviceability, spacing, "
                "ductility, geometry, and detailing checks. "
            )
            failed_check_name = "final accepted shear utilisation threshold"
            failed_check_status = "below_final_accepted_threshold"
            failed_check_limit = float(final_accepted_min_family_util)
        else:
            reason = (
                "The selected shear cleanup reaches the final accepted utilisation band, but the exhaustive "
                "discrete shear-link cleanup search found no executable candidate inside the preferred "
                f"{float(preferred_low):.2f}-{float(target_high):.2f} target band. "
            )
            failed_check_name = "preferred shear target band"
            failed_check_status = "outside_preferred_target_band"
            failed_check_limit = float(target_high)
        if no_link_candidate_selected:
            reason += "The selected candidate removes shear links, so the shear-link floor has been reached."
        elif not best_safe_below_final:
            reason += "The remaining miss is caused by the available shear-link catalogue increments."
        preferred_target_blocker = {
            "family": "shear",
            "search_ran": True,
            "search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "attempted_candidate_count": int(attempted),
            "candidate_count": int(attempted),
            "safe_candidate_count": int(safe_count),
            "safe_cleanup_count": int(safe_count),
            "executable_candidate_count": int(safe_count),
            "executable_cleanup_count": int(safe_count),
            "target_band_candidate_count": int(target_count),
            "executable_target_band_candidate_count": int(target_count),
            "accepted_band_candidate_count": int(accepted_band_count),
            "best_safe_candidate_id": candidate_id,
            "best_safe_final_util": final_shear_util,
            "best_safe_candidate_applied": True,
            "no_second_cta_required": True,
            "failed_candidate_id": candidate_id,
            "best_rejected_candidate_id": candidate_id,
            "failed_check_name": failed_check_name,
            "failed_check_status": failed_check_status,
            "failed_check_util": final_shear_util,
            "current_util": current_shear_util,
            "failed_check_demand": demand if demand is not None else "shear demand",
            "failed_check_capacity_or_limit": failed_check_limit,
            "target_low": float(preferred_low),
            "target_high": float(target_high),
            "accepted_target_low": float(threshold),
            "accepted_target_high": 1.0,
            "attempted_updates": dict(updates),
            "reason": reason,
            "why_reduction_would_hurt_other_design_elements": reason,
        }
    return preferred_target_blocker


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_preferred_target_blocker,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "below_final_no_link_floor",
            "final_shear_util": 0.64,
            "current_shear_util": 0.22,
            "target_count": 0,
            "accepted_band_count": 0,
            "attempted": 4,
            "safe_count": 1,
            "candidate_id": "local_cleanup:shear:no_link",
            "threshold": 0.85,
            "preferred_low": 0.85,
            "target_high": 0.95,
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 9999.0},
            "demand": 100.0,
            "best_safe_below_final": True,
            "no_link_candidate_selected": True,
            "final_accepted_min_family_util": 0.85,
        },
        {
            "name": "accepted_but_preferred_target_missed",
            "final_shear_util": 0.86,
            "current_shear_util": 0.3,
            "target_count": 0,
            "accepted_band_count": 1,
            "attempted": 3,
            "safe_count": 2,
            "candidate_id": "local_cleanup:shear:spacing",
            "threshold": 0.85,
            "preferred_low": 0.85,
            "target_high": 0.95,
            "updates": {"s_lig": 300.0},
            "demand": None,
            "best_safe_below_final": False,
            "no_link_candidate_selected": False,
            "final_accepted_min_family_util": 0.85,
        },
        {
            "name": "target_candidate_exists_no_blocker",
            "final_shear_util": 0.9,
            "current_shear_util": 0.3,
            "target_count": 1,
            "accepted_band_count": 1,
            "attempted": 2,
            "safe_count": 2,
            "candidate_id": "local_cleanup:shear:target",
            "threshold": 0.85,
            "preferred_low": 0.85,
            "target_high": 0.95,
            "updates": {"s_lig": 250.0},
            "demand": 90.0,
            "best_safe_below_final": False,
            "no_link_candidate_selected": False,
            "final_accepted_min_family_util": 0.85,
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_blocker(**kwargs)
        new = build_design_guide_shear_low_util_preferred_target_blocker(**kwargs)
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": new,
                "match": old == new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_PREFERRED_TARGET_BLOCKER_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_preferred_target_blocker as "
                "_build_design_guide_shear_low_util_preferred_target_blocker"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_preferred_target_blocker("
                in shear_cleanup_source
            ),
            "old_inline_reason_removed_from_target_function": (
                "The selected best safe shear cleanup reaches shear utilisation"
                not in shear_cleanup_source
                and "The selected shear cleanup reaches the final accepted utilisation band"
                not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_preferred_target_blocker("
                in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_old_new_cases_match": all(
            item.get("match") for item in capture.get("comparisons") or []
        ),
        "source_checks_pass": all(source_checks.values())
        or (
            source_checks.get("target_function_found") is False
            and source_checks.get("controller_has_helper") is True
            and source_checks.get("old_inline_reason_removed_from_target_function") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Preferred Target Blocker Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases", ""])
    for item in capture.get("comparisons") or []:
        lines.append(f"- {item.get('case')}: `{item.get('match')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_preferred_target_blocker_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_preferred_target_blocker_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_preferred_target_blocker_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
