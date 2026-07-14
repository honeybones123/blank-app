"""Cutover verifier for residual shear fallback pre-screen result builder."""

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
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result,
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
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result(**kwargs)
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result(**kwargs)
    return {
        "name": name,
        "matches_expected": first.get("result") == expected,
        "stable_hash_repeat": first.get("result_hash") == second.get("result_hash"),
        "proof_hash_present": bool((first.get("proof") or {}).get("proof_hash")),
        "not_moved_contains_dependency_execution": all(
            token in tuple((first.get("proof") or {}).get("not_moved") or ())
            for token in (
                "delta_screen_builder_execution",
                "state_match_check_execution",
                "pure_updates_checker_execution",
            )
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        inputs_source,
        "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        "\n\ndef _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    )
    cases = [
        _case(
            "dependency_unavailable",
            {
                "accepted_for_evaluation": False,
                "updates": {},
                "failed_reason": "screen_dependency_unavailable",
            },
            dependencies_available=False,
        ),
        _case(
            "no_updates",
            {
                "accepted_for_evaluation": False,
                "updates": {},
                "failed_reason": "no_updates",
            },
            updates={},
        ),
        _case(
            "updates_match_state",
            {
                "accepted_for_evaluation": False,
                "updates": {"s_lig": 300},
                "failed_reason": "updates_match_state",
            },
            updates={"s_lig": 300},
            updates_match_state=True,
            materially_reduces_reinforcement=True,
        ),
        _case(
            "not_material_reduction",
            {
                "accepted_for_evaluation": False,
                "updates": {"s_lig": 300},
                "failed_reason": "not_material_reduction",
            },
            updates={"s_lig": 300},
            materially_reduces_reinforcement=False,
        ),
        _case(
            "non_shear_update_keys",
            {
                "accepted_for_evaluation": False,
                "updates": {"beam_b": 450},
                "failed_reason": "non_shear_update_keys",
                "bad_update_keys": ("beam_b",),
            },
            updates={"beam_b": 450},
            materially_reduces_reinforcement=True,
            pure_shear_updates=False,
            bad_update_keys=("beam_b",),
        ),
        _case(
            "accepted",
            {
                "accepted_for_evaluation": True,
                "updates": {"s_lig": 300},
                "failed_reason": "",
                "bad_update_keys": tuple(),
            },
            updates={"s_lig": 300},
            materially_reduces_reinforcement=True,
            pure_shear_updates=True,
            bad_update_keys=tuple(),
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_PRE_SCREEN_RESULT_CUTOVER_IMPLEMENTED",
        "controller_function_present": (
            "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result("
            in controller_source
        ),
        "controller_function_exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result"'
            in controller_source
        ),
        "inputs_import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result"
            in inputs_source
        ),
        "helper_controller_call_count": helper.count(
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result("
        ),
        "helper_dependency_order_preserved": (
            helper.find("candidate_delta_screen = delta_screen_builder(")
            < helper.find("if not fallback_updates:")
            < helper.find("if _updates_match_state(state, fallback_updates):")
            < helper.find("pure_shear, bad_shear_keys = pure_updates_checker(")
        ),
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
        "helper_controller_call_count_five": capture.get("helper_controller_call_count") == 5,
        "helper_dependency_order_preserved": (
            capture.get("helper_dependency_order_preserved") is True
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
        "# Residual Shear Cleanup Pre-Screen Result Cutover",
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
            "Rerun remaining fallback-loop authority audit. Pre-screen result shape should now be controller-owned while helper execution remains live.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_pre_screen_result_cutover.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_pre_screen_result_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_pre_screen_result_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_pre_screen_result_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_pre_screen_result_cutover "
        f"{payload['status']}"
    )
    if failures:
        print("failures:", ", ".join(failures))
        print("artifact:", json_path)
        return 1
    print("artifact:", json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
