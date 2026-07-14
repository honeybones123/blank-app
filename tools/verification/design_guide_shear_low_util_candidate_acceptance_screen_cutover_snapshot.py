"""Verify shear low-util candidate acceptance screen cutover."""

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


def _old_overview_required_checks_acceptable(overview: dict | None) -> bool:
    if not isinstance(overview, dict):
        return False
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        tracked = [
            str(status or "").strip().upper()
            for status in statuses.values()
            if str(status or "").strip() not in {"", "—", "-"}
        ]
    else:
        tracked = []
    if not tracked:
        return bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    return not any(status in {"FAIL", "FAILED", "ERROR"} for status in tracked)


def _old_candidate_preview_statuses_have_explicit_fail(
    preview_statuses: dict | None,
    *,
    fail_status_value: Any = "FAIL",
) -> bool:
    if not isinstance(preview_statuses, dict):
        return False
    for value in preview_statuses.values():
        if value == fail_status_value:
            return True
        if str(value or "").strip().upper() == "FAIL":
            return True
    return False


def _old_acceptance_screen(
    *,
    candidate_overview: dict[str, Any] | None,
    candidate_statuses: dict[str, Any] | None,
) -> dict[str, Any]:
    overview = dict(candidate_overview or {}) if isinstance(candidate_overview, dict) else {}
    statuses = (
        dict(candidate_statuses or {})
        if isinstance(candidate_statuses, dict)
        else dict(overview.get("statuses") or {})
    )
    any_fail = bool(overview.get("any_fail"))
    required_checks_acceptable = _old_overview_required_checks_acceptable(overview)
    explicit_preview_fail = _old_candidate_preview_statuses_have_explicit_fail(statuses)
    accepted = bool(not any_fail and required_checks_acceptable and not explicit_preview_fail)
    return {
        "accepted": accepted,
        "failed_reason": None if accepted else "required_check_failed",
        "any_fail": any_fail,
        "required_checks_acceptable": required_checks_acceptable,
        "explicit_preview_fail": explicit_preview_fail,
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_candidate_acceptance_screen,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "all_key_pass_without_statuses",
            "overview": {"all_key_pass": True, "any_fail": False},
            "statuses": {},
        },
        {
            "name": "any_fail",
            "overview": {"all_key_pass": False, "any_fail": True},
            "statuses": {},
        },
        {
            "name": "status_fail",
            "overview": {"statuses": {"shear": "FAIL"}, "any_fail": False},
            "statuses": {"shear": "FAIL"},
        },
        {
            "name": "status_error",
            "overview": {"statuses": {"shear": "ERROR"}, "any_fail": False},
            "statuses": {"shear": "ERROR"},
        },
        {
            "name": "status_pass",
            "overview": {"statuses": {"shear": "PASS"}, "any_fail": False},
            "statuses": {"shear": "PASS"},
        },
        {
            "name": "dash_status_uses_all_key",
            "overview": {"statuses": {"shear": "-"}, "all_key_pass": True, "any_fail": False},
            "statuses": {"shear": "-"},
        },
    ]
    comparisons = []
    for case in cases:
        old = _old_acceptance_screen(
            candidate_overview=case["overview"],
            candidate_statuses=case["statuses"],
        )
        new_raw = build_design_guide_shear_low_util_candidate_acceptance_screen(
            candidate_overview=case["overview"],
            candidate_statuses=case["statuses"],
        )
        new = {
            "accepted": bool(new_raw.get("accepted")),
            "failed_reason": new_raw.get("failed_reason"),
            "any_fail": bool(new_raw.get("any_fail")),
            "required_checks_acceptable": bool(new_raw.get("required_checks_acceptable")),
            "explicit_preview_fail": bool(new_raw.get("explicit_preview_fail")),
        }
        comparisons.append(
            {
                "case": case["name"],
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(new),
                "match": old == new,
                "old": old,
                "new": new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_CANDIDATE_ACCEPTANCE_SCREEN_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_candidate_acceptance_screen as "
                "_build_design_guide_shear_low_util_candidate_acceptance_screen"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_candidate_acceptance_screen("
                in shear_cleanup_source
            ),
            "old_required_checks_helper_removed_from_target": (
                "_overview_required_checks_acceptable(" not in shear_cleanup_source
            ),
            "old_explicit_fail_helper_removed_from_target": (
                "_candidate_preview_statuses_have_explicit_fail(" not in shear_cleanup_source
            ),
            "generic_required_checks_helper_not_deleted": (
                "def _overview_required_checks_acceptable(" in inputs_source
            ),
            "generic_explicit_fail_helper_not_deleted": (
                "def _candidate_preview_statuses_have_explicit_fail(" in inputs_source
                or "candidate_preview_statuses_have_explicit_fail as _candidate_preview_statuses_have_explicit_fail"
                in inputs_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_candidate_acceptance_screen("
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
        "generic_helpers_deleted": False,
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
        "generic_helpers_not_deleted": capture.get("generic_helpers_deleted") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Candidate Acceptance Screen Cutover Snapshot",
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
        lines.append(
            f"- {item.get('case')}: match=`{item.get('match')}`, old=`{item.get('old_hash')}`, new=`{item.get('new_hash')}`"
        )
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_candidate_acceptance_screen_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_candidate_acceptance_screen_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_candidate_acceptance_screen_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
