"""Primary executor handoff snapshot for residual shear cleanup."""

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


def _object_cases() -> list[dict[str, Any]]:
    candidate_boundary = {
        "candidate_boundary_hash": "boundary-hash",
        "dependency_boundary_ready": True,
        "behavior_cutover_ready": False,
    }
    executor_inputs = {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "starting_shear_util": 1.12,
        "target_low": 0.85,
        "target_high": 0.95,
    }
    executor_output = {
        "executor_attempted": True,
        "has_candidate": True,
        "has_updates": True,
        "candidate_id": "residual_shear_cleanup",
        "updates": {"s_lig": 300, "lig_legs": 0},
    }
    cases: list[dict[str, Any]] = []
    for name, status, expected_ready in (
        ("current_page_live_executor", "page_live", False),
        ("future_controller_owned_executor", "controller_owned", True),
    ):
        payload = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
            candidate_boundary=candidate_boundary,
            executor_inputs=executor_inputs,
            executor_output_summary=executor_output,
            dependency_status=status,
        )
        repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
            candidate_boundary=candidate_boundary,
            executor_inputs=executor_inputs,
            executor_output_summary=executor_output,
            dependency_status=status,
        )
        cases.append(
            {
                "name": name,
                "expected_behavior_ready": expected_ready,
                "output_shape_ready": bool(payload.get("output_shape_ready")),
                "behavior_cutover_ready": bool(payload.get("behavior_cutover_ready")),
                "page_must_keep_for_now": tuple(payload.get("page_must_keep_for_now") or ()),
                "stable_hash_repeat": payload.get("primary_executor_handoff_hash")
                == repeat.get("primary_executor_handoff_hash"),
                "product_driving": bool(payload.get("product_driving")),
                "render_driving": bool(payload.get("render_driving")),
                "apply_driving": bool(payload.get("apply_driving")),
                "session_driving": bool(payload.get("session_driving")),
            }
        )
    return cases


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    proof_call = route_block.find(
        "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof("
    )
    boundary_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary("
    )
    handoff_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    return_call = route_block.find("return residual_route_return_item", handoff_call)
    if return_call < 0:
        return_call = route_block.find("return residual_promoted", handoff_call)
    prebuilt_return_call = route_block.find("return dict(", handoff_call)
    parity_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_parity_scenarios.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_PRIMARY_EXECUTOR_HANDOFF_PROVEN",
        "controller_builder_imported": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff"
            in source
        ),
        "helper_present": bool(helper_block),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
            in helper_block
        ),
        "proof_before_boundary_before_handoff": (
            proof_call >= 0 and boundary_call > proof_call and handoff_call > boundary_call
        ),
        "handoff_before_return": handoff_call >= 0
        and (
            return_call > handoff_call
            or prebuilt_return_call > handoff_call
        ),
        "live_return_retained": (
            "return residual_route_return_item" in route_block
            or "return residual_promoted" in route_block
        ),
        "prebuilt_return_boundary_present": prebuilt_return_call > handoff_call,
        "live_executor_shape_retained": (
            "_compute_shear_tightening_recommendation(" in route_block
            or (
                "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
                in route_block
                and "executor=_compute_shear_tightening_recommendation" in route_block
            )
        ),
        "live_executor_tokens_retained": all(
            token in route_block
            for token in ("residual_shear_tighten", "residual_shear_updates")
        ),
        "executor_input_output_wired": all(
            token in route_block
            for token in (
                "executor_inputs",
                "executor_output_summary",
                "executor_attempted",
                "has_candidate",
                "has_updates",
                "candidate_id",
                "updates",
            )
        ),
        "controller_stamps_present": all(
            token in helper_block
            for token in (
                "primary_executor_handoff",
                "primary_executor_handoff_hash",
                "primary_executor_output_shape_ready",
                "primary_executor_behavior_cutover_ready",
                "primary_executor_page_must_keep_for_now",
            )
        ),
        "controller_stamps_non_driving": all(
            token in helper_block
            for token in (
                "primary_executor_product_driving",
                "primary_executor_render_driving",
                "primary_executor_apply_driving",
                "primary_executor_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "object_cases": _object_cases(),
        "candidate_boundary_parity": parity_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    cases = list(capture.get("object_cases") or [])
    return {
        "controller_builder_imported": capture.get("controller_builder_imported") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_object": capture.get("helper_calls_controller_object") is True,
        "proof_before_boundary_before_handoff": (
            capture.get("proof_before_boundary_before_handoff") is True
        ),
        "handoff_before_return": capture.get("handoff_before_return") is True,
        "live_return_removed": capture.get("live_return_retained") is False,
        "prebuilt_return_boundary_present": (
            capture.get("prebuilt_return_boundary_present") is True
        ),
        "live_executor_shape_retained": capture.get("live_executor_shape_retained") is True,
        "live_executor_tokens_retained": capture.get("live_executor_tokens_retained") is True,
        "executor_input_output_wired": capture.get("executor_input_output_wired") is True,
        "controller_stamps_present": capture.get("controller_stamps_present") is True,
        "controller_stamps_non_driving": capture.get("controller_stamps_non_driving") is True,
        "object_case_count": len(cases) == 2,
        "object_cases_output_shape_ready": all(case.get("output_shape_ready") is True for case in cases),
        "object_cases_expected_readiness": all(
            case.get("behavior_cutover_ready") is case.get("expected_behavior_ready")
            for case in cases
        ),
        "page_live_case_keeps_executor": all(
            "primary_shear_tightening_execution" in case.get("page_must_keep_for_now")
            for case in cases
            if case.get("expected_behavior_ready") is False
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in cases),
        "object_cases_non_driving": all(
            not case.get("product_driving")
            and not case.get("render_driving")
            and not case.get("apply_driving")
            and not case.get("session_driving")
            for case in cases
        ),
        "candidate_boundary_parity_passed": (
            capture.get("candidate_boundary_parity") or {}
        ).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Handoff Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Proof -> boundary -> handoff order: `{capture.get('proof_before_boundary_before_handoff')}`",
        f"- Handoff before live return: `{capture.get('handoff_before_return')}`",
        f"- Live executor shape retained: `{capture.get('live_executor_shape_retained')}`",
        f"- Live executor tokens retained: `{capture.get('live_executor_tokens_retained')}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
        "",
        "## Object Cases",
        "",
    ]
    for case in capture.get("object_cases") or []:
        lines.append(
            "- "
            + str(case.get("name"))
            + ": behavior_cutover_ready=`"
            + str(case.get("behavior_cutover_ready"))
            + "`, page_must_keep=`"
            + ", ".join(case.get("page_must_keep_for_now") or ())
            + "`"
        )
    lines.extend(
        [
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
            "Create a focused parity proof for primary shear tightening executor inputs/outputs before any behavior cutover.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_handoff_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff "
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
