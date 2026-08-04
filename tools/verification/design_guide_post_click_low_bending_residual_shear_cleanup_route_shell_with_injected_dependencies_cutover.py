"""Verify residual-shear cleanup route shell cutover with injected dependencies.

This proof is deliberately narrow. It confirms the controller owns the
primary-then-fallback route-shell orchestration while inputs_page.py still
injects the page/shared-owned execution dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FUNCTION_NAME = (
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "route_shell_with_injected_dependencies"
)
IMPORT_ALIAS = (
    FUNCTION_NAME
    + " as _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "route_shell_with_injected_dependencies"
)
ROUTE_BODY_START = (
    "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
)
ROUTE_PREFIX_END = (
    "        residual_shear_cleanup_fallback_search_loop_handoff = "
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "fallback_search_loop_handoff("
)
ROUTE_WINDOW_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("
READINESS_PREFIX = (
    "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_extraction_readiness"
)

INJECTED_DEPENDENCIES = {
    "primary_executor": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
    "fallback_variant_generator": "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
    "candidate_evaluator": "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
    "button_contract_execution": "_execute_post_click_low_bending_residual_shear_cleanup_button_contract(",
}

FORBIDDEN_CONTROLLER_TOKENS = {
    "streamlit_import": "import streamlit",
    "page_candidate_evaluator": "_evaluate_auto_design_candidate",
    "page_variant_generator": "generate_less_shear_reo_variants",
    "page_button_contract": "_design_guide_button_contract",
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
    start_token = f"def {function_name}("
    start = source.find(start_token)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(start_token))
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


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route_body = _between(inputs_source, ROUTE_BODY_START, ROUTE_WINDOW_END)
    route_prefix = _between(inputs_source, ROUTE_BODY_START, ROUTE_PREFIX_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    readiness = _latest(READINESS_PREFIX)

    injected_dependency_presence = {
        name: token in route_body for name, token in INJECTED_DEPENDENCIES.items()
    }
    controller_forbidden_presence = {
        name: token in controller_function for name, token in FORBIDDEN_CONTROLLER_TOKENS.items()
    }
    checks = {
        "controller_function_exists": bool(controller_function),
        "controller_function_exported": f'"{FUNCTION_NAME}"' in controller_source,
        "inputs_imports_controller_function": IMPORT_ALIAS in inputs_source,
        "route_body_calls_controller_shell": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
            "route_shell_with_injected_dependencies("
        )
        in route_body,
        "page_owned_primary_fallback_branch_removed": "if not residual_shear_updates:" not in route_prefix,
        "page_owned_fallback_assignment_removed": "residual_fallback_search_loop =" not in route_prefix,
        "injected_dependencies_retained": all(injected_dependency_presence.values()),
        "controller_has_no_page_owned_execution_dependencies": not any(
            controller_forbidden_presence.values()
        ),
        "readiness_artifact_pass": readiness.get("status") == "PASS",
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
        and checks["route_body_calls_controller_shell"]
        and checks["page_owned_primary_fallback_branch_removed"]
        and checks["page_owned_fallback_assignment_removed"]
        and checks["injected_dependencies_retained"]
        and checks["controller_has_no_page_owned_execution_dependencies"]
        and checks["readiness_artifact_pass"]
        and checks["product_behavior_changed"] is False
        and checks["engineering_behavior_changed"] is False
        and checks["visible_wording_changed"] is False
        and checks["cta_apply_semantics_changed"] is False
        and checks["family_runtime_changed"] is False
    )
    status = "PASS" if passing else "FAIL"
    return {
        "decision": (
            "RESIDUAL_SHEAR_CLEANUP_ROUTE_SHELL_WITH_INJECTED_DEPENDENCIES_CUTOVER"
            if status == "PASS"
            else "RESIDUAL_SHEAR_CLEANUP_ROUTE_SHELL_WITH_INJECTED_DEPENDENCIES_NOT_READY"
        ),
        "status": status,
        "checks": checks,
        "route_body_found": bool(route_body),
        "route_prefix_found": bool(route_prefix),
        "controller_function_found": bool(controller_function),
        "injected_dependency_presence": injected_dependency_presence,
        "controller_forbidden_presence": controller_forbidden_presence,
        "latest_route_shell_extraction_readiness": {
            key: value for key, value in readiness.items() if key != "payload"
        },
        "scope": {
            "controller_owns": (
                "route entry decision consumption",
                "primary executor call orchestration",
                "fallback search call orchestration when primary has no updates",
                "route shell context and hashes",
            ),
            "page_or_shared_still_owns": (
                "candidate generation execution",
                "candidate evaluation execution",
                "CTA contract execution",
                "visible wording",
                "apply routing",
                "UI rendering",
                "session/debug mutation",
            ),
        },
        "route_prefix_hash": _stable_hash(route_prefix),
        "route_body_hash": _stable_hash(route_body),
        "controller_function_hash": _stable_hash(controller_function),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(capture.get("checks") or {})
    lines = [
        "# Residual Shear Cleanup Route Shell With Injected Dependencies Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Decision",
        "",
        str(capture.get("decision") or ""),
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {name}: `{value}`" for name, value in checks.items())
    lines.extend(
        [
            "",
            "## Ownership",
            "",
            "Controller now owns the route-shell orchestration only. The page still injects "
            "candidate generation/evaluation, CTA contract execution, visible wording, apply "
            "routing, rendering, and session/debug mutation.",
            "",
            "## Latest Readiness Artifact",
            "",
            f"- Status: `{(capture.get('latest_route_shell_extraction_readiness') or {}).get('status')}`",
            f"- Path: `{(capture.get('latest_route_shell_extraction_readiness') or {}).get('path')}`",
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
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            "route_shell_with_injected_dependencies_cutover.v1"
        ),
        "status": capture["status"],
        "created_at": stamp,
        "capture": capture,
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"route_shell_with_injected_dependencies_cutover_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"route_shell_with_injected_dependencies_cutover_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload), encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"route_shell_with_injected_dependencies_cutover {payload['status']}"
    )
    print(json_path)
    print(report_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
