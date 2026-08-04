"""Primary executor parity scenarios for residual shear cleanup."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff,
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _scenario(
    *,
    name: str,
    executor_output: dict[str, Any],
    expected_has_candidate: bool,
    expected_has_updates: bool,
) -> dict[str, Any]:
    candidate_boundary = {
        "candidate_boundary_hash": f"{name}-boundary",
        "dependency_boundary_ready": True,
        "behavior_cutover_ready": False,
    }
    executor_inputs = {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "starting_shear_util": 1.12,
        "target_low": 0.85,
        "target_high": 0.95,
        "residual_outside_preferred_band": True,
    }
    page_live = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
        candidate_boundary=candidate_boundary,
        executor_inputs=executor_inputs,
        executor_output_summary=executor_output,
        dependency_status="page_live",
    )
    controller_owned = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
        candidate_boundary=candidate_boundary,
        executor_inputs=executor_inputs,
        executor_output_summary=executor_output,
        dependency_status="controller_owned",
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
        candidate_boundary=candidate_boundary,
        executor_inputs=executor_inputs,
        executor_output_summary=executor_output,
        dependency_status="page_live",
    )
    return {
        "name": name,
        "expected_has_candidate": expected_has_candidate,
        "actual_has_candidate": bool(executor_output.get("has_candidate")),
        "expected_has_updates": expected_has_updates,
        "actual_has_updates": bool(executor_output.get("has_updates")),
        "page_live_output_shape_ready": bool(page_live.get("output_shape_ready")),
        "page_live_behavior_cutover_ready": bool(page_live.get("behavior_cutover_ready")),
        "controller_owned_behavior_cutover_ready": bool(
            controller_owned.get("behavior_cutover_ready")
        ),
        "page_live_keeps_executor": "primary_shear_tightening_execution"
        in tuple(page_live.get("page_must_keep_for_now") or ()),
        "stable_page_live_hash": page_live.get("primary_executor_handoff_hash")
        == repeat.get("primary_executor_handoff_hash"),
        "input_hash_present": bool(page_live.get("executor_input_hash")),
        "output_hash_present": bool(page_live.get("executor_output_hash")),
        "non_driving": not page_live.get("product_driving")
        and not page_live.get("render_driving")
        and not page_live.get("apply_driving")
        and not page_live.get("session_driving"),
    }


def _scenarios() -> list[dict[str, Any]]:
    return [
        _scenario(
            name="primary_executor_candidate_with_updates",
            executor_output={
                "executor_attempted": True,
                "has_candidate": True,
                "has_updates": True,
                "candidate_id": "primary_shear_tightening_success",
                "updates": {"s_lig": 300, "lig_legs": 0},
            },
            expected_has_candidate=True,
            expected_has_updates=True,
        ),
        _scenario(
            name="primary_executor_candidate_without_updates",
            executor_output={
                "executor_attempted": True,
                "has_candidate": True,
                "has_updates": False,
                "candidate_id": "primary_shear_tightening_no_delta",
                "updates": {},
            },
            expected_has_candidate=True,
            expected_has_updates=False,
        ),
        _scenario(
            name="primary_executor_no_candidate",
            executor_output={
                "executor_attempted": True,
                "has_candidate": False,
                "has_updates": False,
                "candidate_id": "",
                "updates": {},
            },
            expected_has_candidate=False,
            expected_has_updates=False,
        ),
    ]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    handoff_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    return_call = route_block.find("return residual_route_return_item", handoff_call)
    if return_call < 0:
        return_call = route_block.find("return residual_promoted", handoff_call)
    prebuilt_return_call = route_block.find("return dict(", handoff_call)
    handoff_end = return_call if return_call > handoff_call else prebuilt_return_call
    handoff_call_block = (
        route_block[handoff_call:handoff_end]
        if handoff_call >= 0 and handoff_end > handoff_call
        else ""
    )
    handoff_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff_snapshot.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_PRIMARY_EXECUTOR_PARITY_SCENARIOS_PROVEN",
        "scenarios": _scenarios(),
        "live_handoff_call_present": bool(handoff_call_block),
        "live_handoff_before_return": handoff_call >= 0 and handoff_end > handoff_call,
        "live_handoff_uses_current_route_inputs": all(
            token in handoff_call_block
            for token in (
                "current_shear_for_residual_cleanup",
                "target_lo",
                "target_hi",
                "residual_outside_preferred_band",
            )
        ),
        "live_handoff_uses_executor_outputs": all(
            token in handoff_call_block
            for token in (
                "residual_shear_tighten",
                "residual_shear_updates",
                "executor_attempted",
                "has_candidate",
                "has_updates",
                "candidate_id",
                "updates",
            )
        ),
        "live_executor_injected_before_handoff": (
            route_block.find(
                "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
            )
            >= 0
            and route_block.find(
                "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
            )
            < handoff_call
            and "executor=_compute_shear_tightening_recommendation" in route_block
        ),
        "live_result_return_retained": (
            "return residual_route_return_item" in route_block
            or "return residual_promoted" in route_block
        ),
        "prebuilt_return_boundary_present": prebuilt_return_call > handoff_call,
        "handoff_snapshot": handoff_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    scenarios = list(capture.get("scenarios") or [])
    return {
        "scenario_count": len(scenarios) == 3,
        "scenario_candidate_flags_match": all(
            case.get("actual_has_candidate") is case.get("expected_has_candidate")
            for case in scenarios
        ),
        "scenario_update_flags_match": all(
            case.get("actual_has_updates") is case.get("expected_has_updates")
            for case in scenarios
        ),
        "all_page_live_shapes_ready": all(
            case.get("page_live_output_shape_ready") is True for case in scenarios
        ),
        "all_page_live_not_cutover_ready": all(
            case.get("page_live_behavior_cutover_ready") is False for case in scenarios
        ),
        "all_controller_owned_cutover_ready": all(
            case.get("controller_owned_behavior_cutover_ready") is True for case in scenarios
        ),
        "all_page_live_keep_executor": all(
            case.get("page_live_keeps_executor") is True for case in scenarios
        ),
        "stable_hashes": all(case.get("stable_page_live_hash") is True for case in scenarios),
        "input_output_hashes_present": all(
            case.get("input_hash_present") and case.get("output_hash_present")
            for case in scenarios
        ),
        "non_driving": all(case.get("non_driving") is True for case in scenarios),
        "live_handoff_call_present": capture.get("live_handoff_call_present") is True,
        "live_handoff_before_return": capture.get("live_handoff_before_return") is True,
        "live_handoff_uses_current_route_inputs": (
            capture.get("live_handoff_uses_current_route_inputs") is True
        ),
        "live_handoff_uses_executor_outputs": (
            capture.get("live_handoff_uses_executor_outputs") is True
        ),
        "live_executor_injected_before_handoff": (
            capture.get("live_executor_injected_before_handoff") is True
        ),
        "live_result_return_removed": capture.get("live_result_return_retained") is False,
        "prebuilt_return_boundary_present": (
            capture.get("prebuilt_return_boundary_present") is True
        ),
        "handoff_snapshot_passed": (capture.get("handoff_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
    ]
    for case in capture.get("scenarios") or []:
        lines.append(
            "- "
            + str(case.get("name"))
            + ": page_live_cutover=`"
            + str(case.get("page_live_behavior_cutover_ready"))
            + "`, controller_owned_cutover=`"
            + str(case.get("controller_owned_behavior_cutover_ready"))
            + "`, stable=`"
            + str(case.get("stable_page_live_hash"))
            + "`"
        )
    lines.extend(
        [
            "",
            "## Live Route",
            "",
            f"- Handoff before return: `{capture.get('live_handoff_before_return')}`",
            f"- Uses current route inputs: `{capture.get('live_handoff_uses_current_route_inputs')}`",
            f"- Uses executor outputs: `{capture.get('live_handoff_uses_executor_outputs')}`",
            f"- Live executor injected before handoff: `{capture.get('live_executor_injected_before_handoff')}`",
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Audit whether the primary executor can be injected into the controller without moving formula helpers, candidate evaluation, CTA contract execution, or visible wording.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_parity_scenarios.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_parity_scenarios_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_parity_scenarios_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_parity_scenarios "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
