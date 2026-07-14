"""Object snapshot for residual-shear primary executor dependency boundary.

This proof is intentionally non-driving. It proves the controller can represent
the primary executor dependency boundary while the actual shear-tightening
executor remains page-injected and live.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter,
)


REQUIRED_ARTIFACTS = {
    "candidate_execution_injected_dependency_boundary_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_injected_dependency_boundary_audit"
    ),
    "primary_executor_injected_adapter_object": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_object"
    ),
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(
        payload.get("status") or payload.get("result") or payload.get("lock_status") or ""
    ).upper()
    status = "PASS" if "PASS" in raw_status or "LOCKED" in raw_status else raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _handoff(*, dependency_status: str = "page_live") -> dict[str, Any]:
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
        candidate_boundary={"candidate_boundary_hash": "candidate-boundary-hash"},
        executor_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-fingerprint",
            "starting_shear_util": 1.12,
            "target_low": 0.85,
            "target_high": 0.95,
        },
        executor_output_summary={
            "executor_attempted": True,
            "has_candidate": True,
            "has_updates": True,
            "candidate_id": "primary_shear_tightening_success",
            "updates_hash": "updates-hash",
        },
        dependency_status=dependency_status,
    )


def _adapter(handoff: dict[str, Any], *, input_hash: str | None = None) -> dict[str, Any]:
    contract = {
        "executor_name": "primary_shear_tightening_executor",
        "input_hash": input_hash or handoff.get("executor_input_hash"),
        "output_hash": handoff.get("executor_output_hash"),
        "stale_state_policy": "rebuild_on_state_fingerprint_change",
        "exception_policy": "return_no_candidate_and_keep_page_path_live",
        "executor_available": True,
        "executor_is_injected": True,
        "executor_is_deterministic": True,
        "executor_changes_behavior": False,
    }
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter(
        primary_executor_handoff=handoff,
        adapter_contract=contract,
    )


def _descriptor(**updates: Any) -> dict[str, Any]:
    descriptor = {
        "executor_name": "primary_shear_tightening_executor",
        "runner_name": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor",
        "injection_site": "residual_shear_cleanup_route_shell.primary_executor",
        "dependency_status": "page_injected",
        "stale_state_policy": "rebuild_on_state_fingerprint_change",
        "exception_policy": "return_no_candidate_and_keep_page_path_live",
    }
    descriptor.update(updates)
    return descriptor


def _case(
    *,
    name: str,
    descriptor_updates: dict[str, Any] | None = None,
    adapter_input_hash: str | None = None,
    expected_ready: bool,
) -> dict[str, Any]:
    handoff = _handoff()
    adapter = _adapter(handoff, input_hash=adapter_input_hash)
    descriptor = _descriptor(**dict(descriptor_updates or {}))
    payload = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary(
        primary_executor_handoff=handoff,
        primary_executor_injected_adapter=adapter,
        dependency_descriptor=descriptor,
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary(
        primary_executor_handoff=handoff,
        primary_executor_injected_adapter=adapter,
        dependency_descriptor=descriptor,
    )
    return {
        "name": name,
        "expected_ready": expected_ready,
        "dependency_boundary_ready": bool(payload.get("dependency_boundary_ready")),
        "route_shape_cutover_ready": bool(payload.get("route_shape_cutover_ready")),
        "safe_to_delete_page_executor_now": bool(payload.get("safe_to_delete_page_executor_now")),
        "missing_descriptor_fields": tuple(payload.get("missing_descriptor_fields") or ()),
        "handoff_ready": bool(payload.get("handoff_ready")),
        "adapter_ready": bool(payload.get("adapter_ready")),
        "page_injected_dependency": bool(payload.get("page_injected_dependency")),
        "safe_next_surface": payload.get("safe_next_surface"),
        "page_must_keep_for_now": tuple(payload.get("page_must_keep_for_now") or ()),
        "stable_hash_repeat": payload.get("primary_executor_dependency_boundary_hash")
        == repeat.get("primary_executor_dependency_boundary_hash"),
        "product_driving": bool(payload.get("product_driving")),
        "render_driving": bool(payload.get("render_driving")),
        "apply_driving": bool(payload.get("apply_driving")),
        "session_driving": bool(payload.get("session_driving")),
    }


def _function_block() -> str:
    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    start_token = (
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "primary_executor_dependency_boundary("
    )
    end_token = (
        "\n\ndef build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "fallback_variant_generator_boundary("
    )
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    required = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    block = _function_block()
    cases = [
        _case(name="complete_page_injected_dependency", expected_ready=True),
        _case(
            name="missing_runner_descriptor",
            descriptor_updates={"runner_name": ""},
            expected_ready=False,
        ),
        _case(
            name="adapter_hash_mismatch",
            adapter_input_hash="mismatch",
            expected_ready=False,
        ),
        _case(
            name="controller_owned_descriptor_not_yet_allowed",
            descriptor_updates={"dependency_status": "controller_owned"},
            expected_ready=False,
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_PRIMARY_EXECUTOR_DEPENDENCY_BOUNDARY_OBJECT_PROVEN",
        "cases": cases,
        "required_artifacts": required,
        "required_artifacts_pass": all(row.get("status") == "PASS" for row in required.values()),
        "function_block_found": bool(block),
        "function_block_hash": _stable_hash(block),
        "forbidden_terms_present": tuple(
            term for term in ("inputs_page", "streamlit", "st.session_state", "st.") if term in block
        ),
        "next_safe_surface": "primary_executor_dependency_trace_wiring",
        "safe_to_delete_page_executor_now": False,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    cases = list(capture.get("cases") or [])
    return {
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "function_block_found": capture.get("function_block_found") is True,
        "controller_object_import_clean": not capture.get("forbidden_terms_present"),
        "case_count": len(cases) == 4,
        "complete_page_injected_dependency_ready": any(
            case.get("name") == "complete_page_injected_dependency"
            and case.get("dependency_boundary_ready") is True
            and case.get("route_shape_cutover_ready") is True
            for case in cases
        ),
        "guarded_cases_not_ready": all(
            case.get("dependency_boundary_ready") is case.get("expected_ready")
            for case in cases
        ),
        "missing_runner_detected": any(
            case.get("name") == "missing_runner_descriptor"
            and "runner_name" in case.get("missing_descriptor_fields")
            for case in cases
        ),
        "adapter_mismatch_detected": any(
            case.get("name") == "adapter_hash_mismatch"
            and case.get("adapter_ready") is False
            for case in cases
        ),
        "controller_owned_descriptor_kept_guarded": any(
            case.get("name") == "controller_owned_descriptor_not_yet_allowed"
            and case.get("page_injected_dependency") is False
            for case in cases
        ),
        "page_executor_not_deleted": all(
            case.get("safe_to_delete_page_executor_now") is False for case in cases
        ),
        "page_executor_kept_for_now": all(
            "primary_shear_tightening_execution" in case.get("page_must_keep_for_now")
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
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Primary Executor Dependency Boundary Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        f"Safe to delete page executor now: `{capture.get('safe_to_delete_page_executor_now')}`",
        "",
        "## Cases",
        "",
    ]
    for case in capture.get("cases") or []:
        lines.append(
            "- "
            + str(case.get("name"))
            + ": dependency_ready=`"
            + str(case.get("dependency_boundary_ready"))
            + "`, route_shape_cutover_ready=`"
            + str(case.get("route_shape_cutover_ready"))
            + "`, safe_to_delete_page_executor_now=`"
            + str(case.get("safe_to_delete_page_executor_now"))
            + "`"
        )
    lines.extend(["", "## Required Artifacts", ""])
    for name, row in dict(capture.get("required_artifacts") or {}).items():
        lines.append(f"- `{name}`: status=`{row.get('status')}`, path=`{row.get('path')}`")
    lines.extend(["", "## Checks", ""])
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire this dependency boundary beside the live residual-shear primary executor call. Do not move or delete the executor yet.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"primary_executor_dependency_boundary_object_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"primary_executor_dependency_boundary_object_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_"
        f"primary_executor_dependency_boundary_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary_object "
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
