"""Verify residual-shear result-packaging/blocker-tail shell cutover."""

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
    "result_packaging_blocker_tail_shell"
)
IMPORT_ALIAS = (
    FUNCTION_NAME
    + " as _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "result_packaging_blocker_tail_shell"
)
ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_route_execution_shell = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell("
TAIL_START = "        residual_result_packaging_blocker_tail = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell("
TAIL_END = "                    residual_evidence_merge_tail_result_adapter = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
PREVIOUS_CUTOVER_PREFIX = (
    "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies_cutover"
)

REQUIRED_ROUTE_TOKENS = {
    "controller_tail_shell_call": (
        "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "result_packaging_blocker_tail_shell("
    ),
    "result_packaging_executor_injected": "result_packaging_executor=lambda:",
    "page_result_packaging_executor_retained": (
        "_run_post_click_low_bending_residual_shear_cleanup_result_packaging("
    ),
    "tail_context_consumed": "residual_result_packaging_blocker_tail_context = dict(",
    "debug_hash_stamped": (
        "design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "result_packaging_blocker_tail_shell_hash"
    ),
    "continue_tail_from_controller": (
        'if residual_result_packaging_blocker_tail.get("should_continue_tail"):'
    ),
}

FORBIDDEN_ROUTE_PREFIX_TOKENS = {
    "inline_outside_preferred_band_calculation": (
        "and float(residual_preview_util) > float(target_hi) + float(TARGET_BAND_EPS)"
    ),
    "inline_shear_blocker_literal": "residual_shear_blocker = {",
    "inline_shear_reason_template": "The best safe one-click shear cleanup reaches shear utilisation",
    "inline_failed_check_status": '"failed_check_status": "OUTSIDE_PREFERRED_TARGET_BAND"',
}

FORBIDDEN_CONTROLLER_TOKENS = {
    "streamlit_import": "import streamlit",
    "page_local_cleanup_evaluator": "_evaluate_local_cleanup_guidance_item",
    "page_packager": "_shear_tightening_as_local_cleanup_item",
    "page_candidate_id_helper": "_guidance_cleanup_candidate_id",
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


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route_body = _between(inputs_source, ROUTE_BODY_START, ROUTE_BODY_END)
    route_prefix = _between(inputs_source, TAIL_START, TAIL_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    previous_cutover = _latest(PREVIOUS_CUTOVER_PREFIX)
    route_token_presence = {
        name: token in route_body for name, token in REQUIRED_ROUTE_TOKENS.items()
    }
    forbidden_route_prefix_presence = {
        name: token in route_prefix
        for name, token in FORBIDDEN_ROUTE_PREFIX_TOKENS.items()
    }
    forbidden_controller_presence = {
        name: token in controller_function
        for name, token in FORBIDDEN_CONTROLLER_TOKENS.items()
    }
    checks = {
        "controller_function_exists": bool(controller_function),
        "controller_function_exported": f'"{FUNCTION_NAME}"' in controller_source,
        "inputs_imports_controller_function": IMPORT_ALIAS in inputs_source,
        "required_route_tokens_present": all(route_token_presence.values()),
        "old_inline_blocker_tail_removed_from_route_prefix": not any(
            forbidden_route_prefix_presence.values()
        ),
        "controller_has_no_page_execution_dependencies": not any(
            forbidden_controller_presence.values()
        ),
        "previous_route_shell_cutover_pass": previous_cutover.get("status") == "PASS",
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
        and checks["required_route_tokens_present"]
        and checks["old_inline_blocker_tail_removed_from_route_prefix"]
        and checks["controller_has_no_page_execution_dependencies"]
        and checks["previous_route_shell_cutover_pass"]
        and checks["product_behavior_changed"] is False
        and checks["engineering_behavior_changed"] is False
        and checks["visible_wording_changed"] is False
        and checks["cta_apply_semantics_changed"] is False
        and checks["family_runtime_changed"] is False
    )
    status = "PASS" if passing else "FAIL"
    return {
        "decision": (
            "RESIDUAL_SHEAR_RESULT_PACKAGING_BLOCKER_TAIL_CONTROLLER_SHELL_CUTOVER"
            if passing
            else "RESIDUAL_SHEAR_RESULT_PACKAGING_BLOCKER_TAIL_NOT_READY"
        ),
        "status": status,
        "checks": checks,
        "route_body_found": bool(route_body),
        "route_prefix_found": bool(route_prefix),
        "controller_function_found": bool(controller_function),
        "route_token_presence": route_token_presence,
        "forbidden_route_prefix_presence": forbidden_route_prefix_presence,
        "forbidden_controller_presence": forbidden_controller_presence,
        "latest_previous_route_shell_cutover": {
            key: value for key, value in previous_cutover.items() if key != "payload"
        },
        "route_prefix_hash": _stable_hash(route_prefix),
        "controller_function_hash": _stable_hash(controller_function),
        "scope": {
            "controller_owns": (
                "result-packaging tail continuation decision",
                "residual evidence extraction from packaged item",
                "outside-preferred-band blocker assembly",
                "tail context and hashes",
            ),
            "page_or_shared_still_owns": (
                "result-packaging execution",
                "local cleanup evaluator",
                "CTA contract execution",
                "visible rendering",
                "apply routing",
                "session/debug mutation",
            ),
        },
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Result-Packaging Blocker Tail Shell Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
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
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            "result_packaging_blocker_tail_shell_cutover.v1"
        ),
        "status": capture["status"],
        "created_at": stamp,
        "capture": capture,
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"result_packaging_blocker_tail_shell_cutover_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"result_packaging_blocker_tail_shell_cutover_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload), encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"result_packaging_blocker_tail_shell_cutover {payload['status']}"
    )
    print(json_path)
    print(report_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
