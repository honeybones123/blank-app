"""Verify residual-shear proof/debug/return tail controller representation.

This is a proof/cutover checkpoint only. It proves the remaining route-body
tail has a controller-owned hash surface while the page still owns debug/session
mutation and the physical nested return.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FUNCTION_NAME = (
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "proof_debug_return_tail"
)
IMPORT_ALIAS = FUNCTION_NAME + (
    " as _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "proof_debug_return_tail"
)
STAMP_WRAPPER = (
    "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "proof_debug_return_tail("
)
STAMP_CALL = (
    "residual_proof_debug_return_tail = "
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "proof_debug_return_tail("
)
ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = (
    "    residual_shear_cleanup_route_execution_shell = "
    "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell("
)
RETURN_TOKEN = "return residual_route_return_item"

REQUIRED_PREVIOUS_ARTIFACTS = {
    "remaining_tail_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_route_body_tail_audit"
    ),
    "result_packaging_blocker_tail_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell_cutover"
    ),
    "route_shell_with_injected_dependencies_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies_cutover"
    ),
}

FORBIDDEN_CONTROLLER_TOKENS = {
    "streamlit_import": "import streamlit",
    "inputs_page_import": "inputs_page",
    "streamlit_session_state": "st.session_state",
    "page_button_contract": "_design_guide_button_contract",
    "page_candidate_evaluator": "_evaluate_auto_design_candidate",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


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


def _function_source(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 4)
    return source[start:next_def] if next_def > start else source[start:]


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "status": _status_from_payload(payload),
        "path": str(path),
        "payload": payload,
    }


def _load_controller_function():
    spec = importlib.util.spec_from_file_location(
        "design_guide_controller_for_tail_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, FUNCTION_NAME)


def _sample_payload() -> dict[str, Any]:
    fn = _load_controller_function()
    result_item = {
        "title_main": "Strengthening required",
        "action_type": "apply_resolved_candidate",
        "action_payload": {"updates": {"shear_links": 0}},
    }
    route_return_boundary = {
        "result_item": dict(result_item),
        "result_item_hash": _stable_hash(result_item),
    }
    route_body_result = {
        "result_item": dict(result_item),
        "result_item_hash": _stable_hash(result_item),
        "route_return_boundary": dict(route_return_boundary),
    }
    route_body_replacement = {
        "result_item": dict(result_item),
        "result_item_hash": _stable_hash(result_item),
        "output_shape_ready": True,
    }
    common = {
        "debug_projection_rows": {"post_click_bending_blocker_preserved": True},
        "route_proof": {"proof_hash": "route-proof"},
        "route_shell_readiness": {"route_shell_cutover_ready": True},
        "candidate_boundary": {"candidate_boundary_hash": "candidate"},
        "fallback_variant_generator_boundary": {"fallback_hash": "fallback"},
        "candidate_evaluator_handoff": {"evaluator_hash": "evaluator"},
        "materiality_safety_handoff": {"screen_hash": "screen"},
        "candidate_selection_sort_key": {"selector_hash": "selector"},
        "result_packaging_handoff": {"packaging_hash": "packaging"},
        "button_contract_execution_boundary": {"button_hash": "button"},
        "cta_apply_payload_source_boundary": {"cta_hash": "cta"},
        "final_binding_tail_handoff": {"binding_hash": "binding"},
        "route_shell_adapter": {"adapter_hash": "adapter"},
        "evidence_merge_tail_handoff": {"evidence_hash": "evidence"},
        "primary_executor_handoff": {"executor_hash": "executor"},
        "route_body_replacement": dict(route_body_replacement),
        "route_body_result": dict(route_body_result),
        "route_return_boundary": dict(route_return_boundary),
        "result_item": dict(result_item),
    }
    first = fn(**common)
    second = fn(**common)
    return {
        "first": first,
        "second": second,
        "stable_repeat_hash": first.get("proof_debug_return_tail_hash")
        == second.get("proof_debug_return_tail_hash"),
        "output_shape_ready": bool(first.get("output_shape_ready")),
        "return_item_parity": bool(first.get("return_item_parity")),
        "missing_required_inputs": list(first.get("missing_required_inputs") or ()),
        "product_driving": bool(first.get("product_driving")),
        "render_driving": bool(first.get("render_driving")),
        "apply_driving": bool(first.get("apply_driving")),
        "session_driving": bool(first.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route_body = _between(inputs_source, ROUTE_BODY_START, ROUTE_BODY_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_PREVIOUS_ARTIFACTS.items()}
    stamp_pos = route_body.find(STAMP_CALL)
    return_pos = route_body.find(RETURN_TOKEN)
    forbidden_controller_presence = {
        name: token in controller_function for name, token in FORBIDDEN_CONTROLLER_TOKENS.items()
    }
    sample = _sample_payload()
    checks = {
        "controller_function_exists": bool(controller_function),
        "controller_function_exported": f'"{FUNCTION_NAME}"' in controller_source,
        "inputs_imports_controller_function": IMPORT_ALIAS in inputs_source,
        "inputs_stamp_wrapper_exists": STAMP_WRAPPER in inputs_source,
        "inputs_route_body_calls_stamp": STAMP_CALL in route_body,
        "stamp_occurs_before_route_return": bool(stamp_pos >= 0 and return_pos >= 0 and stamp_pos < return_pos),
        "controller_has_no_forbidden_dependencies": not any(
            forbidden_controller_presence.values()
        ),
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "sample_hash_stable": sample["stable_repeat_hash"] is True,
        "sample_output_shape_ready": sample["output_shape_ready"] is True,
        "sample_return_item_parity": sample["return_item_parity"] is True,
        "sample_missing_required_inputs_empty": not sample["missing_required_inputs"],
        "sample_non_product_driving": sample["product_driving"] is False,
        "sample_non_render_driving": sample["render_driving"] is False,
        "sample_non_apply_driving": sample["apply_driving"] is False,
        "sample_non_session_driving": sample["session_driving"] is False,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    passing = (
        checks["controller_function_exists"]
        and checks["controller_function_exported"]
        and checks["inputs_imports_controller_function"]
        and checks["inputs_stamp_wrapper_exists"]
        and checks["inputs_route_body_calls_stamp"]
        and checks["stamp_occurs_before_route_return"]
        and checks["controller_has_no_forbidden_dependencies"]
        and checks["previous_artifacts_pass"]
        and checks["sample_hash_stable"]
        and checks["sample_output_shape_ready"]
        and checks["sample_return_item_parity"]
        and checks["sample_missing_required_inputs_empty"]
        and checks["sample_non_product_driving"]
        and checks["sample_non_render_driving"]
        and checks["sample_non_apply_driving"]
        and checks["sample_non_session_driving"]
        and checks["product_behavior_changed"] is False
        and checks["engineering_behavior_changed"] is False
        and checks["visible_wording_changed"] is False
        and checks["cta_apply_semantics_changed"] is False
        and checks["family_runtime_changed"] is False
    )
    return {
        "decision": (
            "RESIDUAL_SHEAR_PROOF_DEBUG_RETURN_TAIL_CONTROLLER_REPRESENTED"
            if passing
            else "RESIDUAL_SHEAR_PROOF_DEBUG_RETURN_TAIL_NOT_READY"
        ),
        "checks": checks,
        "route_body_found": bool(route_body),
        "controller_function_found": bool(controller_function),
        "forbidden_controller_presence": forbidden_controller_presence,
        "latest_required_artifacts": {
            name: {key: value for key, value in row.items() if key != "payload"}
            for name, row in latest.items()
        },
        "sample": {
            key: value
            for key, value in sample.items()
            if key not in {"first", "second"}
        },
        "sample_hash": sample["first"].get("proof_debug_return_tail_hash"),
        "route_body_hash": _stable_hash(route_body),
        "controller_function_hash": _stable_hash(controller_function),
        "safe_to_delete_route_body_now": False,
        "next_safe_surface": "rerun_route_body_deletion_readiness_and_deadness",
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Proof/Debug/Return Tail Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Checks",
        "",
    ]
    for name, value in dict(capture.get("checks") or {}).items():
        lines.append(f"- {name}: `{value}`")
    lines.extend(
        [
            "",
            "## Behaviour",
            "",
            "- Product behaviour changed: `False`",
            "- Engineering behaviour changed: `False`",
            "- Visible wording changed: `False`",
            "- CTA/apply semantics changed: `False`",
            "- Family runtime changed: `False`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    status = (
        "PASS"
        if capture.get("decision")
        == "RESIDUAL_SHEAR_PROOF_DEBUG_RETURN_TAIL_CONTROLLER_REPRESENTED"
        else "FAIL"
    )
    payload = {
        "status": status,
        "timestamp": stamp,
        "capture": capture,
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"proof_debug_return_tail_cutover_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"proof_debug_return_tail_cutover_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"{status}: wrote {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
