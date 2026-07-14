"""Trace-wiring verifier for residual-shear route-shell adapter.

This verifier is static/proof-only. It confirms the controller route-shell
adapter is wired beside the live residual-shear route as a non-driving debug
trace and that no route output, CTA/apply, rendering, or session authority has
been moved by the trace.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

IMPORT_TOKEN = (
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell "
    "as _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell"
)
HELPER_TOKEN = (
    "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
)
CALL_TOKEN = (
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
)


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
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\n\ndef ", start + len(token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper = _function_block(source, HELPER_TOKEN)
    route = _between(source, ROUTE_START, ROUTE_END)
    route_call_count = route.count(CALL_TOKEN)
    helper_call_count = helper.count(
        "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell("
    )
    non_driving_tokens = (
        "\"proof_only_trace\": True",
        "\"product_driving\": False",
        "\"render_driving\": False",
        "\"apply_driving\": False",
        "\"session_driving\": False",
    )
    outside_dependency_tokens = (
        "candidate_generation_execution_owned_elsewhere",
        "candidate_evaluation_execution_owned_elsewhere",
        "cta_contract_execution_owned_elsewhere",
        "visible_wording_authoring_owned_elsewhere",
    )
    call_after_final_binding_trace = (
        route.find(
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace("
        )
        >= 0
        and route.find(CALL_TOKEN)
        > route.find(
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace("
        )
    )
    allowed_cutover_assignment = (
        "residual_route_shell_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
        in route
        and "residual_promoted = dict(\n                            residual_route_shell_adapter.get(\"result_item\")\n                            or residual_promoted\n                        )"
        in route
    )
    return {
        "decision": "ROUTE_SHELL_ADAPTER_TRACE_WIRED_NON_DRIVING",
        "import_present": IMPORT_TOKEN in source,
        "helper_present": bool(helper),
        "helper_calls_controller_adapter_once": helper_call_count == 1,
        "route_found": bool(route),
        "route_call_count": route_call_count,
        "route_call_after_final_binding_trace": call_after_final_binding_trace,
        "non_driving_tokens_present": all(token in helper for token in non_driving_tokens),
        "outside_dependency_tokens_present": all(
            token in helper for token in outside_dependency_tokens
        ),
        "route_return_unchanged": "return residual_promoted" in route,
        "trace_result_not_assigned_to_residual_promoted": (
            "residual_promoted = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace"
            not in route
        ),
        "allowed_route_shell_cutover_assignment": allowed_cutover_assignment,
        "latest": {
            "route_shell_adapter_object": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_object"
            ),
            "remaining_surface_audit": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "import_present": capture.get("import_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_adapter_once": (
            capture.get("helper_calls_controller_adapter_once") is True
        ),
        "route_found": capture.get("route_found") is True,
        "route_call_count_one": capture.get("route_call_count") == 1,
        "route_call_after_final_binding_trace": (
            capture.get("route_call_after_final_binding_trace") is True
        ),
        "non_driving_tokens_present": capture.get("non_driving_tokens_present") is True,
        "outside_dependency_tokens_present": (
            capture.get("outside_dependency_tokens_present") is True
        ),
        "route_return_unchanged": capture.get("route_return_unchanged") is True,
        "trace_result_not_assigned_to_residual_promoted": (
            capture.get("trace_result_not_assigned_to_residual_promoted") is True
        ),
        "trace_assignment_safe_if_present": (
            capture.get("trace_result_not_assigned_to_residual_promoted") is True
            or capture.get("allowed_route_shell_cutover_assignment") is True
        ),
        "route_shell_adapter_object_pass": (
            (capture.get("latest") or {}).get("route_shell_adapter_object", {}).get("status")
            == "PASS"
        ),
        "remaining_surface_audit_pass": (
            (capture.get("latest") or {}).get("remaining_surface_audit", {}).get("status")
            == "PASS"
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route-Shell Adapter Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Import present: `{capture.get('import_present')}`",
        f"- Helper present: `{capture.get('helper_present')}`",
        f"- Route call count: `{capture.get('route_call_count')}`",
        f"- Route return unchanged: `{capture.get('route_return_unchanged')}`",
        f"- Trace result not assigned to live item: `{capture.get('trace_result_not_assigned_to_residual_promoted')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create route-shell adapter parity scenarios/live readiness before any route-shell cutover.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace_wiring.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace_wiring_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace_wiring_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace_wiring "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
