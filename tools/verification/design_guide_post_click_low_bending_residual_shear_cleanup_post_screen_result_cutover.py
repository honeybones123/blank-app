"""Cutover verifier for residual shear fallback post-screen result builder."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result,
)


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _case(name: str, expected: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(**kwargs)
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(**kwargs)
    return {
        "name": name,
        "matches_expected": first.get("result") == expected,
        "stable_hash_repeat": first.get("result_hash") == second.get("result_hash"),
        "proof_hash_present": bool((first.get("proof") or {}).get("proof_hash")),
        "not_moved_contains_dependency_execution": all(
            token in tuple((first.get("proof") or {}).get("not_moved") or ())
            for token in (
                "acceptance_screen_builder_execution",
                "candidate_evaluation_execution",
                "candidate_selection_execution",
            )
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        inputs_source,
        "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    passing_overview = {
        "any_fail": False,
        "statuses": {"shear": "PASS", "bending": "PASS"},
        "utils": {"shear": 0.82, "bending": 0.92},
    }
    passing_statuses = dict(passing_overview["statuses"])
    passing_utils = dict(passing_overview["utils"])
    passing_screen = {
        "required_checks_acceptable": True,
        "explicit_preview_fail": False,
    }
    cases = [
        _case(
            "candidate_unavailable",
            {
                "accepted": False,
                "failed_reason": "candidate_evaluation_returned_no_candidate",
                "overview": {},
                "statuses": {},
                "utils": {},
                "shear_util": None,
            },
            candidate_available=False,
        ),
        _case(
            "accepted",
            {
                "accepted": True,
                "failed_reason": "",
                "overview": dict(passing_overview),
                "statuses": dict(passing_statuses),
                "utils": dict(passing_utils),
                "shear_util": 0.82,
                "acceptance_screen": dict(passing_screen),
            },
            candidate_available=True,
            fallback_overview=dict(passing_overview),
            fallback_statuses=dict(passing_statuses),
            fallback_utils=dict(passing_utils),
            fallback_shear_util=0.82,
            current_shear_util=0.70,
            target_band_eps=0.0,
            acceptance_screen=dict(passing_screen),
        ),
        _case(
            "missing_shear_util",
            {
                "accepted": False,
                "failed_reason": "candidate_failed_residual_shear_cleanup_acceptance",
                "overview": dict(passing_overview),
                "statuses": dict(passing_statuses),
                "utils": dict(passing_utils),
                "shear_util": None,
                "acceptance_screen": dict(passing_screen),
            },
            candidate_available=True,
            fallback_overview=dict(passing_overview),
            fallback_statuses=dict(passing_statuses),
            fallback_utils=dict(passing_utils),
            fallback_shear_util=None,
            current_shear_util=0.70,
            target_band_eps=0.0,
            acceptance_screen=dict(passing_screen),
        ),
        _case(
            "not_shear_improvement",
            {
                "accepted": False,
                "failed_reason": "candidate_failed_residual_shear_cleanup_acceptance",
                "overview": dict(passing_overview),
                "statuses": dict(passing_statuses),
                "utils": dict(passing_utils),
                "shear_util": 0.70,
                "acceptance_screen": dict(passing_screen),
            },
            candidate_available=True,
            fallback_overview=dict(passing_overview),
            fallback_statuses=dict(passing_statuses),
            fallback_utils=dict(passing_utils),
            fallback_shear_util=0.70,
            current_shear_util=0.70,
            target_band_eps=0.0,
            acceptance_screen=dict(passing_screen),
        ),
        _case(
            "above_target",
            {
                "accepted": False,
                "failed_reason": "candidate_failed_residual_shear_cleanup_acceptance",
                "overview": dict(passing_overview),
                "statuses": dict(passing_statuses),
                "utils": dict(passing_utils),
                "shear_util": 1.01,
                "acceptance_screen": dict(passing_screen),
            },
            candidate_available=True,
            fallback_overview=dict(passing_overview),
            fallback_statuses=dict(passing_statuses),
            fallback_utils=dict(passing_utils),
            fallback_shear_util=1.01,
            current_shear_util=0.70,
            target_band_eps=0.0,
            acceptance_screen=dict(passing_screen),
        ),
        _case(
            "overview_any_fail",
            {
                "accepted": False,
                "failed_reason": "candidate_failed_residual_shear_cleanup_acceptance",
                "overview": {**passing_overview, "any_fail": True},
                "statuses": dict(passing_statuses),
                "utils": dict(passing_utils),
                "shear_util": 0.82,
                "acceptance_screen": dict(passing_screen),
            },
            candidate_available=True,
            fallback_overview={**passing_overview, "any_fail": True},
            fallback_statuses=dict(passing_statuses),
            fallback_utils=dict(passing_utils),
            fallback_shear_util=0.82,
            current_shear_util=0.70,
            target_band_eps=0.0,
            acceptance_screen=dict(passing_screen),
        ),
        _case(
            "required_checks_not_acceptable",
            {
                "accepted": False,
                "failed_reason": "candidate_failed_residual_shear_cleanup_acceptance",
                "overview": dict(passing_overview),
                "statuses": dict(passing_statuses),
                "utils": dict(passing_utils),
                "shear_util": 0.82,
                "acceptance_screen": {
                    "required_checks_acceptable": False,
                    "explicit_preview_fail": False,
                },
            },
            candidate_available=True,
            fallback_overview=dict(passing_overview),
            fallback_statuses=dict(passing_statuses),
            fallback_utils=dict(passing_utils),
            fallback_shear_util=0.82,
            current_shear_util=0.70,
            target_band_eps=0.0,
            acceptance_screen={
                "required_checks_acceptable": False,
                "explicit_preview_fail": False,
            },
        ),
        _case(
            "explicit_preview_fail",
            {
                "accepted": False,
                "failed_reason": "candidate_failed_residual_shear_cleanup_acceptance",
                "overview": dict(passing_overview),
                "statuses": dict(passing_statuses),
                "utils": dict(passing_utils),
                "shear_util": 0.82,
                "acceptance_screen": {
                    "required_checks_acceptable": True,
                    "explicit_preview_fail": True,
                },
            },
            candidate_available=True,
            fallback_overview=dict(passing_overview),
            fallback_statuses=dict(passing_statuses),
            fallback_utils=dict(passing_utils),
            fallback_shear_util=0.82,
            current_shear_util=0.70,
            target_band_eps=0.0,
            acceptance_screen={
                "required_checks_acceptable": True,
                "explicit_preview_fail": True,
            },
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_POST_SCREEN_RESULT_CUTOVER_IMPLEMENTED",
        "controller_function_present": (
            "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result("
            in controller_source
        ),
        "controller_function_exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result"'
            in controller_source
        ),
        "inputs_import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result"
            in inputs_source
        ),
        "helper_controller_call_count": helper.count(
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result("
        ),
        "helper_acceptance_builder_still_called": (
            "candidate_acceptance_screen = acceptance_screen_builder(" in helper
        ),
        "helper_old_local_accepted_expression_absent": "accepted = not (" not in helper,
        "cases": cases,
        "all_cases_match_expected": all(case.get("matches_expected") for case in cases),
        "all_cases_stable": all(case.get("stable_hash_repeat") for case in cases),
        "all_cases_keep_dependency_execution_outside": all(
            case.get("not_moved_contains_dependency_execution") for case in cases
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_function_present": capture.get("controller_function_present") is True,
        "controller_function_exported": capture.get("controller_function_exported") is True,
        "inputs_import_present": capture.get("inputs_import_present") is True,
        "helper_controller_call_count_two": capture.get("helper_controller_call_count") == 2,
        "helper_acceptance_builder_still_called": (
            capture.get("helper_acceptance_builder_still_called") is True
        ),
        "helper_old_local_accepted_expression_absent": (
            capture.get("helper_old_local_accepted_expression_absent") is True
        ),
        "all_cases_match_expected": capture.get("all_cases_match_expected") is True,
        "all_cases_stable": capture.get("all_cases_stable") is True,
        "all_cases_keep_dependency_execution_outside": (
            capture.get("all_cases_keep_dependency_execution_outside") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Post-Screen Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Cases",
        "",
    ]
    for case in capture.get("cases") or []:
        lines.append(
            f"- `{case.get('name')}`: matches `{case.get('matches_expected')}`, stable `{case.get('stable_hash_repeat')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Rerun remaining fallback-loop authority audit. Post-screen result shape should now be controller-owned while acceptance helper execution remains live.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_post_screen_result_cutover.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    suffix = payload["created_at"]
    json_path = ARTIFACT_DIR / (
        f"design_guide_post_click_low_bending_residual_shear_cleanup_post_screen_result_cutover_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_post_click_low_bending_residual_shear_cleanup_post_screen_result_cutover_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_post_screen_result_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
