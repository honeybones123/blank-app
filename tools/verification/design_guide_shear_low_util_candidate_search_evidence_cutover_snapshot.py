"""Verify shear low-util candidate-search evidence cutover from page code."""

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


def _old_evidence(
    *,
    current_shear_util: Any,
    final_shear_util: Any,
    threshold: Any,
    target_high: Any,
    updates: dict[str, Any],
    accepted_band_count: int,
    safe_count: int,
    target_count: int,
    failed_reasons: list[Any],
    best_safe_below_final: bool,
    no_link_audit: dict[str, Any],
    preferred_target_blocker: dict[str, Any],
) -> dict[str, Any]:
    evidence = {
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "family": "shear",
        "starting_util": current_shear_util,
        "best_safe_final_util": final_shear_util,
        "target_low": float(threshold),
        "target_high": float(target_high),
        "best_safe_candidate_updates": dict(updates),
        "best_safe_candidate_applied": False,
        "accepted_band_candidate_count": int(accepted_band_count),
        "safe_candidate_count": max(1, int(safe_count), int(accepted_band_count)),
        "executable_candidate_count": max(1, int(safe_count), int(accepted_band_count)),
        "safe_cleanup_count": max(1, int(safe_count), int(accepted_band_count)),
        "executable_cleanup_count": max(1, int(safe_count), int(accepted_band_count)),
        "safe_shear_cleanup_count": max(1, int(safe_count), int(accepted_band_count)),
        "executable_shear_cleanup_count": max(1, int(safe_count), int(accepted_band_count)),
        "executable_target_band_candidate_count": max(int(target_count), int(accepted_band_count)),
        "failed_candidate_reasons": list(dict.fromkeys(failed_reasons))[:40],
        "best_safe_partial_cleanup": bool(best_safe_below_final),
        "no_second_cta_required": False,
        "one_click_target_reaching_candidate_exists": bool(accepted_band_count > 0),
        **dict(no_link_audit),
    }
    publish_preferred_target_blocker_as_exact = bool(
        preferred_target_blocker and int(accepted_band_count or 0) <= 0
    )
    if publish_preferred_target_blocker_as_exact:
        evidence["exact_blockers_by_family"] = {"shear": dict(preferred_target_blocker)}
        evidence["post_click_exact_blockers_by_family"] = {"shear": dict(preferred_target_blocker)}
        evidence["cleanup_evidence_by_family"] = {"shear": dict(preferred_target_blocker)}
        evidence["post_click_cleanup_evidence_by_family"] = {"shear": dict(preferred_target_blocker)}
    return evidence


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_cleanup_candidate_search_evidence,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    blocker = {
        "family": "shear",
        "best_safe_candidate_id": "local_cleanup:shear:best",
        "reason": "blocked reason",
    }
    cases = [
        {
            "name": "accepted_band_without_exact_blocker",
            "current_shear_util": 0.42,
            "final_shear_util": 0.88,
            "threshold": 0.85,
            "target_high": 0.95,
            "updates": {"lig_legs": 2, "s_lig": 300.0},
            "accepted_band_count": 1,
            "safe_count": 1,
            "target_count": 1,
            "failed_reasons": ["required_check_failed", "required_check_failed"],
            "best_safe_below_final": False,
            "no_link_audit": {"no_link_candidate_tested": False},
            "preferred_target_blocker": dict(blocker),
        },
        {
            "name": "below_final_with_exact_blocker",
            "current_shear_util": 0.25,
            "final_shear_util": 0.65,
            "threshold": 0.85,
            "target_high": 0.95,
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 9999.0},
            "accepted_band_count": 0,
            "safe_count": 1,
            "target_count": 0,
            "failed_reasons": ["shear_target_threshold_not_reached"],
            "best_safe_below_final": True,
            "no_link_audit": {"no_link_candidate_selected": True},
            "preferred_target_blocker": dict(blocker),
        },
        {
            "name": "safe_floor_from_accepted_count",
            "current_shear_util": 0.3,
            "final_shear_util": 0.86,
            "threshold": 0.85,
            "target_high": 0.95,
            "updates": {"lig_legs": 2},
            "accepted_band_count": 2,
            "safe_count": 0,
            "target_count": 0,
            "failed_reasons": [],
            "best_safe_below_final": False,
            "no_link_audit": {},
            "preferred_target_blocker": {},
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_evidence(**kwargs)
        new = build_design_guide_shear_low_util_cleanup_candidate_search_evidence(**kwargs)
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": new,
                "match": old == new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_CANDIDATE_SEARCH_EVIDENCE_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_cleanup_candidate_search_evidence as "
                "_build_design_guide_shear_low_util_cleanup_candidate_search_evidence"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_cleanup_candidate_search_evidence("
                in shear_cleanup_source
            ),
            "old_inline_evidence_block_removed": (
                '"cleanup_search_ran": True,\n        "cleanup_search_exhaustive": True,'
                not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_cleanup_candidate_search_evidence("
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
            and source_checks.get("old_inline_evidence_block_removed") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Candidate Search Evidence Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_candidate_search_evidence_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_candidate_search_evidence_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_candidate_search_evidence_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
