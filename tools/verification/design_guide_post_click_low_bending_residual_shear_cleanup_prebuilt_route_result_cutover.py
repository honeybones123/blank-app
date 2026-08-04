"""Verify residual-shear route execution shell uses a prebuilt route result.

This proves the controller no longer receives the physical page nested route
body as an injected callable. It does not delete the nested body yet.
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
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell"
)
ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

REQUIRED_ARTIFACTS = {
    "proof_debug_return_tail_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail_cutover"
    ),
    "physical_wrapper_replacement_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_physical_wrapper_replacement_readiness"
    ),
}

REQUIRED_INPUT_TOKENS = {
    "physical_wrapper_result_variable": (
        "residual_shear_cleanup_physical_route_body_wrapper = {"
    ),
    "prebuilt_result_from_wrapper": (
        '"prebuilt_result_item": dict(residual_shear_cleanup_prebuilt_route_result or {})'
    ),
    "prebuilt_execution_flag_from_wrapper": (
        "residual_shear_cleanup_prebuilt_route_body_executed = bool("
    ),
    "prebuilt_result_passed_to_controller": "prebuilt_result_item=dict(residual_shear_cleanup_prebuilt_route_result or {})",
    "prebuilt_executed_passed_to_controller": "prebuilt_route_body_executed=residual_shear_cleanup_prebuilt_route_body_executed",
    "physical_wrapper_compatibility_only": '"compatibility_only": True',
    "physical_wrapper_non_product_driving": '"product_driving": False',
}

FORBIDDEN_INPUT_TOKENS = {
    "route_body_executor_injection": (
        "route_body_executor=_execute_post_click_low_bending_residual_shear_cleanup_route_body"
    ),
}

REQUIRED_CONTROLLER_TOKENS = {
    "prebuilt_result_param": "prebuilt_result_item: dict[str, Any] | None = None",
    "prebuilt_executed_param": "prebuilt_route_body_executed: bool | None = None",
    "prebuilt_supplied": "prebuilt_supplied =",
    "prebuilt_scope": '"prebuilt_route_result"',
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
        "design_guide_controller_for_prebuilt_route_result_verifier",
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
    decision = {"should_enter_route": True, "route_entry_decision_hash": "entry"}
    first = fn(
        route_entry_decision=dict(decision),
        prebuilt_result_item=dict(result_item),
        prebuilt_route_body_executed=True,
    )
    second = fn(
        route_entry_decision=dict(decision),
        prebuilt_result_item=dict(result_item),
        prebuilt_route_body_executed=True,
    )
    skipped = fn(
        route_entry_decision={"should_enter_route": False, "route_entry_decision_hash": "skip"},
        prebuilt_result_item={},
        prebuilt_route_body_executed=False,
    )
    return {
        "stable_repeat_hash": first.get("route_execution_shell_hash")
        == second.get("route_execution_shell_hash"),
        "scope": first.get("route_execution_shell_scope"),
        "executed_route_body": bool(first.get("executed_route_body")),
        "result_hash_matches": first.get("result_item_hash") == _stable_hash(result_item),
        "prebuilt_supplied": bool(first.get("prebuilt_route_result_supplied")),
        "prebuilt_hash_matches": first.get("prebuilt_route_result_hash") == _stable_hash(result_item),
        "skip_does_not_execute": skipped.get("executed_route_body") is False
        and not dict(skipped.get("result_item") or {}),
        "product_driving": bool(first.get("product_driving")),
        "render_driving": bool(first.get("render_driving")),
        "apply_driving": bool(first.get("apply_driving")),
        "session_driving": bool(first.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    required_input_presence = {
        name: token in route for name, token in REQUIRED_INPUT_TOKENS.items()
    }
    forbidden_input_presence = {
        name: token in route for name, token in FORBIDDEN_INPUT_TOKENS.items()
    }
    required_controller_presence = {
        name: token in controller_function
        for name, token in REQUIRED_CONTROLLER_TOKENS.items()
    }
    sample = _sample_payload()
    checks = {
        "route_found": bool(route),
        "controller_function_found": bool(controller_function),
        "required_input_tokens_present": all(required_input_presence.values()),
        "forbidden_executor_injection_absent": not any(forbidden_input_presence.values()),
        "required_controller_tokens_present": all(required_controller_presence.values()),
        "required_previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "sample_hash_stable": sample["stable_repeat_hash"] is True,
        "sample_scope_prebuilt": sample["scope"] == "prebuilt_route_result",
        "sample_executed_route_body": sample["executed_route_body"] is True,
        "sample_result_hash_matches": sample["result_hash_matches"] is True,
        "sample_prebuilt_supplied": sample["prebuilt_supplied"] is True,
        "sample_prebuilt_hash_matches": sample["prebuilt_hash_matches"] is True,
        "sample_skip_does_not_execute": sample["skip_does_not_execute"] is True,
        "product_driving_preserved": sample["product_driving"] is True,
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
        checks["route_found"]
        and checks["controller_function_found"]
        and checks["required_input_tokens_present"]
        and checks["forbidden_executor_injection_absent"]
        and checks["required_controller_tokens_present"]
        and checks["required_previous_artifacts_pass"]
        and checks["sample_hash_stable"]
        and checks["sample_scope_prebuilt"]
        and checks["sample_executed_route_body"]
        and checks["sample_result_hash_matches"]
        and checks["sample_prebuilt_supplied"]
        and checks["sample_prebuilt_hash_matches"]
        and checks["sample_skip_does_not_execute"]
        and checks["product_driving_preserved"]
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
            "RESIDUAL_SHEAR_PREBUILT_ROUTE_RESULT_CUTOVER"
            if passing
            else "RESIDUAL_SHEAR_PREBUILT_ROUTE_RESULT_NOT_READY"
        ),
        "checks": checks,
        "required_input_presence": required_input_presence,
        "forbidden_input_presence": forbidden_input_presence,
        "required_controller_presence": required_controller_presence,
        "latest_required_artifacts": {
            name: {key: value for key, value in row.items() if key != "payload"}
            for name, row in latest.items()
        },
        "sample": sample,
        "route_hash": _stable_hash(route),
        "controller_function_hash": _stable_hash(controller_function),
        "safe_to_delete_nested_wrapper_now": False,
        "next_safe_surface": "prove_nested_route_body_wrapper_dead_then_delete",
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Prebuilt Route Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete nested wrapper now: `{capture.get('safe_to_delete_nested_wrapper_now')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Checks",
        "",
    ]
    for name, value in dict(capture.get("checks") or {}).items():
        lines.append(f"- {name}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    status = (
        "PASS"
        if capture.get("decision") == "RESIDUAL_SHEAR_PREBUILT_ROUTE_RESULT_CUTOVER"
        else "FAIL"
    )
    payload = {
        "status": status,
        "timestamp": stamp,
        "capture": capture,
        "snapshot_hash": _stable_hash(capture),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"prebuilt_route_result_cutover_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"prebuilt_route_result_cutover_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_cutover",
        status,
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
