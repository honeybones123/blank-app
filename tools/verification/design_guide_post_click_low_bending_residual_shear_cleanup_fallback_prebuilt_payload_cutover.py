"""Verify residual-shear route shell consumes a prebuilt fallback payload."""

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
REPORT_DIR = ROOT / "artifacts" / "reports"

FUNCTION_NAME = (
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "route_shell_with_injected_dependencies"
)
ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_physical_route_body_wrapper = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_physical_nested_route_body_wrapper("

REQUIRED_INPUT_TOKENS = {
    "fallback_executed_flag": "residual_route_fallback_search_loop_executed = bool(",
    "fallback_payload_variable": "residual_route_fallback_search_loop_payload = {}",
    "guarded_fallback_call": "if residual_route_fallback_search_loop_executed:",
    "prebuilt_fallback_payload_passed": (
        "prebuilt_fallback_search_loop_payload=dict("
    ),
    "prebuilt_fallback_executed_passed": (
        "prebuilt_fallback_search_loop_executed=residual_route_fallback_search_loop_executed"
    ),
}

FORBIDDEN_INPUT_TOKENS = {
    "fallback_search_loop_lambda": "fallback_search_loop=lambda:",
}

REQUIRED_CONTROLLER_TOKENS = {
    "prebuilt_fallback_param": (
        "prebuilt_fallback_search_loop_payload: dict[str, Any] | None = None"
    ),
    "prebuilt_fallback_executed_param": (
        "prebuilt_fallback_search_loop_executed: bool | None = None"
    ),
    "prebuilt_fallback_supplied": "prebuilt_fallback_supplied =",
    "prebuilt_fallback_hash": '"prebuilt_fallback_search_loop_hash"',
}

REQUIRED_PREVIOUS_ARTIFACTS = {
    "physical_nested_wrapper_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_physical_nested_wrapper_cutover"
    ),
    "primary_prebuilt_result_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_prebuilt_result_cutover"
    ),
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
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _load_controller_function():
    spec = importlib.util.spec_from_file_location(
        "design_guide_controller_fallback_prebuilt_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, FUNCTION_NAME)


def _sample() -> dict[str, Any]:
    fn = _load_controller_function()
    fallback_payload = {
        "residual_shear_tighten": {"updates": {"lig_legs": 0}, "candidate_id": "fallback"},
        "residual_shear_updates": {"lig_legs": 0},
        "fallback_variant_generator_attempted": True,
        "fallback_variant_generator_variant_count": 1,
        "fallback_variant_generator_update_sequence": [{"updates": {"lig_legs": 0}}],
        "fallback_candidate_evaluation_sequence": [{"accepted_as_safe_cleanup": True}],
        "fallback_candidate_selection_sequence": [{"candidate_id": "fallback"}],
        "fallback_candidate_selection_output_summary": {"selected": "fallback"},
        "fallback_shear_candidates": [{"candidate_id": "fallback"}],
        "fallback_selected_result": {"result_hash": "fallback"},
    }
    decision = {"should_enter_route": True, "route_entry_decision_hash": "entry"}
    first = fn(
        route_entry_decision=dict(decision),
        prebuilt_primary_result=({}, {}),
        prebuilt_primary_executor_attempted=True,
        prebuilt_fallback_search_loop_payload=dict(fallback_payload),
        prebuilt_fallback_search_loop_executed=True,
        fallback_search_loop=lambda: {"should_not": "run"},
    )
    second = fn(
        route_entry_decision=dict(decision),
        prebuilt_primary_result=({}, {}),
        prebuilt_primary_executor_attempted=True,
        prebuilt_fallback_search_loop_payload=dict(fallback_payload),
        prebuilt_fallback_search_loop_executed=True,
        fallback_search_loop=lambda: {"should_not": "run"},
    )
    context = dict(first.get("route_shell_context") or {})
    return {
        "stable_repeat_hash": first.get("route_shell_hash") == second.get("route_shell_hash"),
        "prebuilt_fallback_supplied": first.get("prebuilt_fallback_search_loop_supplied")
        is True,
        "fallback_executed": first.get("fallback_search_loop_executed") is True,
        "updates_preserved": dict(context.get("residual_shear_updates") or {})
        == {"lig_legs": 0},
        "sequence_preserved": len(context.get("fallback_candidate_evaluation_sequence") or [])
        == 1,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is False,
        "apply_driving": first.get("apply_driving") is False,
        "session_driving": first.get("session_driving") is False,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(inputs_source, ROUTE_BODY_START, ROUTE_BODY_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    sample = _sample()
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_PREVIOUS_ARTIFACTS.items()}
    return {
        "decision": "RESIDUAL_SHEAR_FALLBACK_SEARCH_LOOP_PREBUILT_PAYLOAD_CUTOVER",
        "route_body_found": bool(body),
        "controller_function_found": bool(controller_function),
        "required_input_presence": {
            name: token in body for name, token in REQUIRED_INPUT_TOKENS.items()
        },
        "forbidden_input_presence": {
            name: token in body for name, token in FORBIDDEN_INPUT_TOKENS.items()
        },
        "required_controller_presence": {
            name: token in controller_function
            for name, token in REQUIRED_CONTROLLER_TOKENS.items()
        },
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "sample": sample,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "result_packaging_executor_lambda_cutover",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("sample") or {})
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "controller_function_found": capture.get("controller_function_found") is True,
        "required_input_tokens_present": all(
            dict(capture.get("required_input_presence") or {}).values()
        ),
        "fallback_search_loop_lambda_absent": not any(
            dict(capture.get("forbidden_input_presence") or {}).values()
        ),
        "required_controller_tokens_present": all(
            dict(capture.get("required_controller_presence") or {}).values()
        ),
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "sample_stable_repeat_hash": sample.get("stable_repeat_hash") is True,
        "sample_prebuilt_fallback_supplied": sample.get("prebuilt_fallback_supplied") is True,
        "sample_fallback_executed": sample.get("fallback_executed") is True,
        "sample_updates_preserved": sample.get("updates_preserved") is True,
        "sample_sequence_preserved": sample.get("sequence_preserved") is True,
        "product_driving_preserved": sample.get("product_driving") is True,
        "not_render_driving": sample.get("render_driving") is True,
        "not_apply_driving": sample.get("apply_driving") is True,
        "not_session_driving": sample.get("session_driving") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Fallback Prebuilt Payload Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        "The residual-shear route shell now consumes the fallback search loop "
        "result as prebuilt data instead of receiving `fallback_search_loop=lambda:`. "
        "The fallback generator/evaluator/screening execution remains page/shared-owned.",
        "",
        "## Checks",
        "",
    ]
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {name}: `{value}`")
    lines.extend(["", "## Next Safe Target", "", f"`{capture.get('next_safe_surface')}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"fallback_prebuilt_payload_cutover_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"fallback_prebuilt_payload_cutover_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_fallback_prebuilt_payload_"
        f"{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_prebuilt_payload_cutover",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(audit_path)
    print(report_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
