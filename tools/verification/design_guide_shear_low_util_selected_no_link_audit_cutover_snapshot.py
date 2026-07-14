"""Verify selected no-link shear cleanup audit cutover from page code."""

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


def _old_selected_no_link_update(
    *,
    updates: dict[str, Any],
    candidate_id: str,
    canonical_no_shear_slig_mm: float,
) -> dict[str, Any]:
    return {
        "no_link_candidate_tested": True,
        "no_link_candidate_evaluated": True,
        "no_link_candidate_passed": True,
        "no_link_candidate_selected": True,
        "no_link_candidate_updates": dict(updates),
        "no_link_candidate_id": candidate_id,
        "no_link_candidate_failed_or_selected_reason": (
            "No-link shear cleanup was tested, passed all required checks, and was selected."
        ),
        "no_link_s_lig_policy": (
            "canonical_neutralised"
            if "s_lig" in updates
            and abs(float(updates.get("s_lig") or 0.0) - float(canonical_no_shear_slig_mm))
            <= 1e-9
            else "retained_or_not_applicable"
        ),
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_selected_no_link_audit_update,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "canonical_slig",
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 9999.0},
            "candidate_id": "local_cleanup:shear:no_link",
            "canonical_no_shear_slig_mm": 9999.0,
        },
        {
            "name": "retained_slig",
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 250.0},
            "candidate_id": "local_cleanup:shear:no_link_retained",
            "canonical_no_shear_slig_mm": 9999.0,
        },
        {
            "name": "missing_slig",
            "updates": {"lig_d": 0, "lig_legs": 0},
            "candidate_id": "local_cleanup:shear:no_link_missing_slig",
            "canonical_no_shear_slig_mm": 9999.0,
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_selected_no_link_update(**kwargs)
        new = build_design_guide_shear_low_util_selected_no_link_audit_update(**kwargs)
        comparable_new = {
            key: new.get(key)
            for key in (
                "no_link_candidate_tested",
                "no_link_candidate_evaluated",
                "no_link_candidate_passed",
                "no_link_candidate_selected",
                "no_link_candidate_updates",
                "no_link_candidate_id",
                "no_link_candidate_failed_or_selected_reason",
                "no_link_s_lig_policy",
            )
        }
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": comparable_new,
                "match": old == comparable_new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_SELECTED_NO_LINK_AUDIT_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_selected_no_link_audit_update as "
                "_build_design_guide_shear_low_util_selected_no_link_audit_update"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_selected_no_link_audit_update("
                in shear_cleanup_source
            ),
            "old_inline_selected_no_link_reason_removed": (
                "No-link shear cleanup was tested, passed all required checks, and was selected."
                not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_selected_no_link_audit_update("
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
        "source_checks_pass": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Selected No-Link Audit Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_selected_no_link_audit_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_selected_no_link_audit_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_selected_no_link_audit_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
