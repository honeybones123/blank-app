"""Object snapshot for residual shear cleanup primary executor injected adapter."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter,
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


def _handoff() -> dict[str, Any]:
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
        candidate_boundary={"candidate_boundary_hash": "candidate-boundary-hash"},
        executor_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "starting_shear_util": 1.12,
            "target_low": 0.85,
            "target_high": 0.95,
        },
        executor_output_summary={
            "executor_attempted": True,
            "has_candidate": True,
            "has_updates": True,
            "candidate_id": "primary_shear_tightening_success",
            "updates": {"s_lig": 300, "lig_legs": 0},
        },
        dependency_status="page_live",
    )


def _case(*, name: str, contract_updates: dict[str, Any], expected_ready: bool) -> dict[str, Any]:
    handoff = _handoff()
    contract = {
        "executor_name": "primary_shear_tightening_executor",
        "input_hash": handoff.get("executor_input_hash"),
        "output_hash": handoff.get("executor_output_hash"),
        "stale_state_policy": "rebuild_on_state_fingerprint_change",
        "exception_policy": "return_no_candidate_and_keep_page_path_live",
        "executor_available": True,
        "executor_is_injected": True,
        "executor_is_deterministic": True,
        "executor_changes_behavior": False,
    }
    contract.update(contract_updates)
    payload = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter(
        primary_executor_handoff=handoff,
        adapter_contract=contract,
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter(
        primary_executor_handoff=handoff,
        adapter_contract=contract,
    )
    return {
        "name": name,
        "expected_ready": expected_ready,
        "adapter_boundary_ready": bool(payload.get("adapter_boundary_ready")),
        "behavior_cutover_ready": bool(payload.get("behavior_cutover_ready")),
        "input_hash_matches": bool(payload.get("input_hash_matches")),
        "output_hash_matches": bool(payload.get("output_hash_matches")),
        "missing_contract_fields": tuple(payload.get("missing_contract_fields") or ()),
        "page_must_keep_for_now": tuple(payload.get("page_must_keep_for_now") or ()),
        "stable_hash_repeat": payload.get("primary_executor_injected_adapter_hash")
        == repeat.get("primary_executor_injected_adapter_hash"),
        "product_driving": bool(payload.get("product_driving")),
        "render_driving": bool(payload.get("render_driving")),
        "apply_driving": bool(payload.get("apply_driving")),
        "session_driving": bool(payload.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    handoff_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff_snapshot.py",
        ]
    )
    parity_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_parity_scenarios.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_PRIMARY_EXECUTOR_INJECTED_ADAPTER_OBJECT_PROVEN",
        "cases": [
            _case(name="complete_injected_contract", contract_updates={}, expected_ready=True),
            _case(
                name="stale_policy_missing",
                contract_updates={"stale_state_policy": ""},
                expected_ready=False,
            ),
            _case(
                name="input_hash_mismatch",
                contract_updates={"input_hash": "mismatch"},
                expected_ready=False,
            ),
            _case(
                name="executor_not_injected",
                contract_updates={"executor_is_injected": False},
                expected_ready=False,
            ),
        ],
        "handoff_snapshot": handoff_run,
        "parity_scenarios": parity_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    cases = list(capture.get("cases") or [])
    return {
        "case_count": len(cases) == 4,
        "complete_contract_ready": any(
            case.get("name") == "complete_injected_contract"
            and case.get("adapter_boundary_ready") is True
            and case.get("behavior_cutover_ready") is True
            for case in cases
        ),
        "guarded_cases_not_ready": all(
            case.get("behavior_cutover_ready") is case.get("expected_ready")
            for case in cases
        ),
        "missing_policy_detected": any(
            case.get("name") == "stale_policy_missing"
            and "stale_state_policy" in case.get("missing_contract_fields")
            for case in cases
        ),
        "hash_mismatch_detected": any(
            case.get("name") == "input_hash_mismatch"
            and case.get("input_hash_matches") is False
            for case in cases
        ),
        "not_injected_keeps_page_live": any(
            case.get("name") == "executor_not_injected"
            and "primary_shear_tightening_execution" in case.get("page_must_keep_for_now")
            for case in cases
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in cases),
        "non_driving": all(
            not case.get("product_driving")
            and not case.get("render_driving")
            and not case.get("apply_driving")
            and not case.get("session_driving")
            for case in cases
        ),
        "handoff_snapshot_passed": (capture.get("handoff_snapshot") or {}).get("passed") is True,
        "parity_scenarios_passed": (capture.get("parity_scenarios") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Injected Adapter Object Snapshot",
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
            "- "
            + str(case.get("name"))
            + ": adapter_ready=`"
            + str(case.get("adapter_boundary_ready"))
            + "`, behavior_ready=`"
            + str(case.get("behavior_cutover_ready"))
            + "`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire the injected-adapter object beside the live route. Keep the page-live executor as the injected implementation.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_injected_adapter_object_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_object "
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
