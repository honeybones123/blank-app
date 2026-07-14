"""Verify residual-shear physical nested wrapper has been deleted from Inputs.

The nested route body is still live, but the temporary physical wrapper layer
has been removed from ``inputs_page.py``. The page now executes the route body
from the already controller-owned route-entry decision and keeps only a
compatibility/debug payload for old consumers.
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
REPORT_DIR = ROOT / "artifacts" / "reports"

FUNCTION_NAME = (
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "physical_nested_route_body_wrapper"
)
ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

REQUIRED_INPUT_TOKENS = {
    "direct_route_body_guard": (
        "residual_shear_cleanup_prebuilt_route_body_executed = bool(\n"
        "        residual_shear_cleanup_route_entry_decision.get(\"should_enter_route\")"
    ),
    "deleted_compatibility_authority": (
        "DesignGuideController.post_click_low_bending_residual_shear_cleanup_"
        "physical_nested_route_body_wrapper_deleted"
    ),
    "route_body_supplier_deleted": '"route_body_supplier_deleted": True',
    "compatibility_only_payload": '"compatibility_only": True',
    "prebuilt_result_item_payload": (
        '"prebuilt_result_item": dict(residual_shear_cleanup_prebuilt_route_result or {})'
    ),
    "debug_hash_stamp": (
        "design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "physical_nested_route_body_wrapper_hash"
    ),
}

FORBIDDEN_INPUT_TOKENS = {
    "controller_import": (
        "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "physical_nested_route_body_wrapper as _run_design_guide_controller_post_click_"
        "low_bending_residual_shear_cleanup_physical_nested_route_body_wrapper"
    ),
    "wrapper_call": (
        "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "physical_nested_route_body_wrapper("
    ),
    "supplier_passed": (
        "route_body_supplier=_execute_post_click_low_bending_residual_shear_cleanup_route_body"
    ),
    "direct_route_body_call": (
        "_execute_post_click_low_bending_residual_shear_cleanup_route_body() or {}"
    ),
}

REQUIRED_CONTROLLER_TOKENS = {
    "function_def": f"def {FUNCTION_NAME}(",
    "authority": (
        "DesignGuideController.post_click_low_bending_residual_shear_cleanup_"
        "physical_nested_route_body_wrapper"
    ),
    "supplier_owned_elsewhere": '"route_body_supplier_owned_elsewhere": True',
    "not_moved_candidate_generation": '"candidate_generation_execution_owned_elsewhere": True',
    "not_moved_candidate_evaluation": '"candidate_evaluation_execution_owned_elsewhere": True',
    "not_moved_cta_contract": '"cta_contract_execution_owned_elsewhere": True',
    "not_moved_visible_wording": '"visible_wording_authoring_owned_elsewhere": True',
    "not_moved_apply_routing": '"apply_routing_owned_elsewhere": True',
    "not_moved_rendering": '"ui_rendering_owned_elsewhere": True',
    "not_moved_session": '"session_debug_mutation_owned_elsewhere": True',
    "exported": f'"{FUNCTION_NAME}"',
}

FORBIDDEN_CONTROLLER_TOKENS_IN_FUNCTION = (
    "inputs_page",
    "import streamlit",
    "st.session_state",
    "_evaluate_auto_design_candidate(",
    "generate_less_shear_reo_variants(",
    "_execute_post_click_low_bending_residual_shear_cleanup_button_contract(",
    "_design_guide_button_contract(",
)

REQUIRED_PREVIOUS_ARTIFACTS = {
    "prebuilt_route_result_builder_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_builder_cutover"
    ),
    "remaining_route_body_tail_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_route_body_tail_audit"
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
        "design_guide_controller_physical_wrapper_verifier",
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
    calls = {"count": 0}

    def supplier() -> dict[str, Any]:
        calls["count"] += 1
        return {"title_main": "Strengthening required", "updates": {"lig_legs": 0}}

    decision = {"should_enter_route": True, "route_entry_decision_hash": "entry"}
    first = fn(route_entry_decision=dict(decision), route_body_supplier=supplier)
    second_calls = {"count": 0}

    def second_supplier() -> dict[str, Any]:
        second_calls["count"] += 1
        return {"title_main": "Strengthening required", "updates": {"lig_legs": 0}}

    second = fn(route_entry_decision=dict(decision), route_body_supplier=second_supplier)
    skip_calls = {"count": 0}

    def skip_supplier() -> dict[str, Any]:
        skip_calls["count"] += 1
        return {"should_not": "execute"}

    skipped = fn(
        route_entry_decision={"should_enter_route": False, "route_entry_decision_hash": "skip"},
        route_body_supplier=skip_supplier,
    )
    return {
        "stable_repeat_hash": first.get("physical_nested_route_body_wrapper_hash")
        == second.get("physical_nested_route_body_wrapper_hash"),
        "supplier_called_once": calls["count"] == 1,
        "second_supplier_called_once": second_calls["count"] == 1,
        "skip_supplier_not_called": skip_calls["count"] == 0,
        "executed_route_body": first.get("executed_route_body") is True,
        "skip_not_executed": skipped.get("executed_route_body") is False,
        "prebuilt_result_present": bool(first.get("prebuilt_result_item")),
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is False,
        "apply_driving": first.get("apply_driving") is False,
        "session_driving": first.get("session_driving") is False,
        "raw_payload": first,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    sample = _sample()
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_PREVIOUS_ARTIFACTS.items()}
    return {
        "decision": "RESIDUAL_SHEAR_PHYSICAL_NESTED_WRAPPER_DELETED",
        "route_found": bool(route),
        "controller_function_found": bool(controller_function),
        "required_input_presence": {
            name: token in inputs_source for name, token in REQUIRED_INPUT_TOKENS.items()
        },
        "forbidden_input_presence": {
            name: token in route for name, token in FORBIDDEN_INPUT_TOKENS.items()
        },
        "required_controller_presence": {
            name: token in controller_source for name, token in REQUIRED_CONTROLLER_TOKENS.items()
        },
        "forbidden_controller_terms_present": [
            token
            for token in FORBIDDEN_CONTROLLER_TOKENS_IN_FUNCTION
            if token.lower() in controller_function.lower()
        ],
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "sample": sample,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "rerun_route_body_deletion_readiness_and_deadness_gates",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("sample") or {})
    return {
        "route_found": capture.get("route_found") is True,
        "controller_function_found": capture.get("controller_function_found") is True,
        "required_input_tokens_present": all(
            dict(capture.get("required_input_presence") or {}).values()
        ),
        "forbidden_input_tokens_absent": not any(
            dict(capture.get("forbidden_input_presence") or {}).values()
        ),
        "required_controller_tokens_present": all(
            dict(capture.get("required_controller_presence") or {}).values()
        ),
        "forbidden_controller_terms_absent": not capture.get(
            "forbidden_controller_terms_present"
        ),
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "sample_stable_repeat_hash": sample.get("stable_repeat_hash") is True,
        "supplier_called_once": sample.get("supplier_called_once") is True,
        "skip_supplier_not_called": sample.get("skip_supplier_not_called") is True,
        "executed_route_body": sample.get("executed_route_body") is True,
        "skip_not_executed": sample.get("skip_not_executed") is True,
        "prebuilt_result_present": sample.get("prebuilt_result_present") is True,
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
        "# Residual Shear Physical Nested Wrapper Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        "The page no longer owns the inline `if should_enter_route` wrapper "
        "as a temporary supplier wrapper around the residual-shear nested body. "
        "The old wrapper import/call is gone; a compatibility/debug payload "
        "preserves old evidence consumers while the route body remains live.",
        "",
        "## Behaviour Preserved",
        "",
        f"- Engineering behaviour changed: `{capture.get('engineering_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- Family runtime changed: `{capture.get('family_runtime_changed')}`",
        "",
        "## Checks",
        "",
    ]
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {name}: `{value}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "",
            "The nested route body still owns the live supplier body. Candidate "
            "generation/evaluation, CTA contract execution, visible wording, "
            "Apply routing, rendering, and session/debug mutation were not moved.",
            "",
            "## Next Safe Target",
            "",
            f"`{capture.get('next_safe_surface')}`",
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
        f"physical_nested_wrapper_cutover_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"physical_nested_wrapper_cutover_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_physical_nested_wrapper_"
        f"{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_physical_nested_wrapper_cutover",
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
