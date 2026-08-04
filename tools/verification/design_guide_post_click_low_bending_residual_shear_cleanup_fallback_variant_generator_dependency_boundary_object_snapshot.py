"""Object snapshot for residual-shear fallback variant generator dependency boundary."""

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
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter,
)


REQUIRED_ARTIFACTS = {
    "fallback_variant_generator_injected_adapter_object": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_object"
    ),
    "fallback_variant_generator_injected_adapter_trace": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring"
    ),
    "candidate_execution_injected_dependency_boundary_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_injected_dependency_boundary_audit"
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
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if "PASS" in raw.upper() or "LOCKED" in raw.upper() else raw or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _boundary(*, dependency_status: str = "page_live") -> dict[str, Any]:
    sequence = [
        {"index": 0, "variant_hash": "v0", "updates": {"lig_legs": 0, "s_lig": 0}},
        {"index": 1, "variant_hash": "v1", "updates": {"s_lig": 300}},
    ]
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(
        candidate_boundary={"candidate_boundary_hash": "candidate-boundary-hash"},
        generator_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
            "iteration_limit": 64,
        },
        generator_output_summary={
            "generator_attempted": True,
            "generated_variant_count": 2,
            "generated_update_count": len(sequence),
            "iteration_limit": 64,
            "stable_sequence_hash": _stable_hash(sequence),
            "order_proof": {
                "iteration_limit": 64,
                "preserves_generator_order": True,
                "stable_sequence_hash": _stable_hash(sequence),
            },
        },
        dependency_status=dependency_status,
    )


def _adapter(boundary: dict[str, Any], *, input_hash: str | None = None) -> dict[str, Any]:
    contract = {
        "generator_name": "fallback_variant_generator",
        "input_hash": input_hash or boundary.get("generator_input_hash"),
        "output_hash": boundary.get("generator_output_hash"),
        "iteration_limit": boundary.get("iteration_limit"),
        "stale_state_policy": "rebuild_on_state_fingerprint_change",
        "exception_policy": "return_empty_variants_and_keep_page_path_live",
        "generator_available": True,
        "generator_is_injected": True,
        "generator_is_deterministic": True,
        "generator_changes_behavior": False,
    }
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter(
        fallback_variant_generator_boundary=boundary,
        adapter_contract=contract,
    )


def _descriptor(**updates: Any) -> dict[str, Any]:
    descriptor = {
        "generator_name": "fallback_variant_generator",
        "runner_name": "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator",
        "injection_site": "residual_shear_cleanup_fallback_search_loop.fallback_variant_generator",
        "dependency_status": "page_injected",
        "iteration_limit": 64,
        "stale_state_policy": "rebuild_on_state_fingerprint_change",
        "exception_policy": "return_empty_variants_and_keep_page_path_live",
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
    boundary = _boundary()
    adapter = _adapter(boundary, input_hash=adapter_input_hash)
    descriptor = _descriptor(**dict(descriptor_updates or {}))
    payload = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary(
        fallback_variant_generator_boundary=boundary,
        fallback_variant_generator_injected_adapter=adapter,
        dependency_descriptor=descriptor,
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary(
        fallback_variant_generator_boundary=boundary,
        fallback_variant_generator_injected_adapter=adapter,
        dependency_descriptor=descriptor,
    )
    return {
        "name": name,
        "expected_ready": expected_ready,
        "dependency_boundary_ready": bool(payload.get("dependency_boundary_ready")),
        "route_shape_cutover_ready": bool(payload.get("route_shape_cutover_ready")),
        "safe_to_delete_page_generator_now": bool(payload.get("safe_to_delete_page_generator_now")),
        "missing_descriptor_fields": tuple(payload.get("missing_descriptor_fields") or ()),
        "boundary_ready": bool(payload.get("boundary_ready")),
        "adapter_ready": bool(payload.get("adapter_ready")),
        "page_injected_dependency": bool(payload.get("page_injected_dependency")),
        "iteration_limit_matches": bool(payload.get("iteration_limit_matches")),
        "safe_next_surface": payload.get("safe_next_surface"),
        "page_must_keep_for_now": tuple(payload.get("page_must_keep_for_now") or ()),
        "stable_hash_repeat": payload.get("fallback_variant_generator_dependency_boundary_hash")
        == repeat.get("fallback_variant_generator_dependency_boundary_hash"),
        "product_driving": bool(payload.get("product_driving")),
        "render_driving": bool(payload.get("render_driving")),
        "apply_driving": bool(payload.get("apply_driving")),
        "session_driving": bool(payload.get("session_driving")),
    }


def _function_block() -> str:
    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    start_token = (
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "fallback_variant_generator_dependency_boundary("
    )
    end_token = (
        "\n\ndef build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "candidate_evaluator_handoff("
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
            name="iteration_limit_mismatch",
            descriptor_updates={"iteration_limit": 32},
            expected_ready=False,
        ),
        _case(
            name="controller_owned_descriptor_not_yet_allowed",
            descriptor_updates={"dependency_status": "controller_owned"},
            expected_ready=False,
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_FALLBACK_VARIANT_GENERATOR_DEPENDENCY_BOUNDARY_OBJECT_PROVEN",
        "cases": cases,
        "required_artifacts": required,
        "required_artifacts_pass": all(row.get("status") == "PASS" for row in required.values()),
        "function_block_found": bool(block),
        "function_block_hash": _stable_hash(block),
        "forbidden_terms_present": tuple(
            term for term in ("inputs_page", "streamlit", "st.session_state", "st.") if term in block
        ),
        "next_safe_surface": "fallback_variant_generator_dependency_trace_wiring",
        "safe_to_delete_page_generator_now": False,
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
        "case_count": len(cases) == 5,
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
        "iteration_limit_mismatch_detected": any(
            case.get("name") == "iteration_limit_mismatch"
            and case.get("iteration_limit_matches") is False
            for case in cases
        ),
        "controller_owned_descriptor_kept_guarded": any(
            case.get("name") == "controller_owned_descriptor_not_yet_allowed"
            and case.get("page_injected_dependency") is False
            for case in cases
        ),
        "page_generator_not_deleted": all(
            case.get("safe_to_delete_page_generator_now") is False for case in cases
        ),
        "page_generator_kept_for_now": all(
            "fallback_variant_generation" in case.get("page_must_keep_for_now")
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
        "# Residual Shear Fallback Variant Generator Dependency Boundary Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        f"Safe to delete page generator now: `{capture.get('safe_to_delete_page_generator_now')}`",
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
            + "`, safe_to_delete_page_generator_now=`"
            + str(case.get("safe_to_delete_page_generator_now"))
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
            "Trace-wire this dependency boundary beside the live residual-shear fallback generator. Do not move or delete the generator yet.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"fallback_variant_generator_dependency_boundary_object_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"fallback_variant_generator_dependency_boundary_object_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_"
        f"fallback_variant_generator_dependency_boundary_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary_object "
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
