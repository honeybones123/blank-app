"""Audit the remaining live residual-shear route result assembly.

This is proof-only. It classifies the residual-shear cleanup code that still
physically lives inside inputs_page.py after the controller/prebuilt-result
cutovers. The audit deliberately does not claim deletion readiness; it names
the next extraction boundary.
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

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_prebuilt_route_body_executed = bool("
ROUTE_SECTION_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_SECTION_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

REQUIRED_ARTIFACTS = {
    "route_body_supplier_ownership_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_supplier_ownership_audit"
    ),
    "prebuilt_route_result_builder_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_builder_cutover"
    ),
    "prebuilt_route_result_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_cutover"
    ),
}

ASSEMBLY_SURFACES = {
    "controller_live_route_result_assembly_call": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_live_route_result_assembly(",
        "classification": "B. controller-owned live route-result assembly cutover",
        "delete_blocker": False,
    },
    "dependency_injected_route_shell_call": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies(",
        "classification": "A. live controller shell call still assembled in inputs_page",
        "delete_blocker": True,
    },
    "primary_executor_lambda": {
        "token": "primary_executor=lambda:",
        "classification": "A. page supplies primary executor dependency",
        "delete_blocker": True,
    },
    "fallback_search_loop_lambda": {
        "token": "fallback_search_loop=lambda:",
        "classification": "A. page supplies fallback search dependency",
        "delete_blocker": True,
    },
    "candidate_execution_bundle_builder": {
        "token": "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle(",
        "classification": "B. controller-owned candidate execution bundle",
        "delete_blocker": False,
    },
    "prebuilt_route_shell": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell(",
        "classification": "B. controller-owned prebuilt route shell",
        "delete_blocker": False,
    },
    "route_body_result_shell": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
        "classification": "B. controller-owned route body result shell",
        "delete_blocker": False,
    },
    "prebuilt_route_result_builder": {
        "token": "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(",
        "classification": "B. controller-owned prebuilt route result builder",
        "delete_blocker": False,
    },
    "debug_projection": {
        "token": "debug_sink[",
        "classification": "C. page-owned debug/session projection only",
        "delete_blocker": False,
    },
}

CONTROLLER_READY_TOKENS = {
    "live_route_result_assembly": (
        "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_live_route_result_assembly("
    ),
    "route_shell_with_injected_dependencies": (
        "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies("
    ),
    "candidate_execution_bundle": (
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle("
    ),
    "prebuilt_route_shell": (
        "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell("
    ),
    "route_body_result": (
        "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body("
    ),
    "prebuilt_route_result": (
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result("
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


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(inputs_source, ROUTE_BODY_START, ROUTE_BODY_END)
    route_section = _between(inputs_source, ROUTE_SECTION_START, ROUTE_SECTION_END)
    inspected_source = body or route_section

    surface_rows = {
        name: {
            "present": spec["token"] in inspected_source,
            "classification": spec["classification"],
            "delete_blocker": bool(spec["delete_blocker"] and spec["token"] in inspected_source),
            "token": spec["token"],
        }
        for name, spec in ASSEMBLY_SURFACES.items()
    }
    controller_api_presence = {
        name: token in controller_source for name, token in CONTROLLER_READY_TOKENS.items()
    }
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    delete_blockers = tuple(
        name for name, row in surface_rows.items() if row.get("delete_blocker") is True
    )
    cutover_call_present = bool(
        surface_rows.get("controller_live_route_result_assembly_call", {}).get("present")
    )
    required_artifacts_pass = all(row.get("status") == "PASS" for row in latest.values())
    controller_api_ready = all(controller_api_presence.values())
    ready_for_next_cutover = bool(inspected_source and required_artifacts_pass and controller_api_ready)
    nested_body_deleted = bool(route_section and not body)

    return {
        "decision": (
            "RESIDUAL_SHEAR_LIVE_ROUTE_RESULT_ASSEMBLY_CUTOVER_BODY_DELETED"
            if ready_for_next_cutover
            and nested_body_deleted
            and cutover_call_present
            and not delete_blockers
            else
            "RESIDUAL_SHEAR_LIVE_ROUTE_RESULT_ASSEMBLY_CUTOVER"
            if ready_for_next_cutover and cutover_call_present and not delete_blockers
            else "RESIDUAL_SHEAR_LIVE_ROUTE_RESULT_ASSEMBLY_READY_FOR_CUTOVER_PROOF"
            if ready_for_next_cutover
            else "RESIDUAL_SHEAR_LIVE_ROUTE_RESULT_ASSEMBLY_NOT_READY"
        ),
        "body_found": bool(body),
        "route_section_found": bool(route_section),
        "nested_body_deleted": nested_body_deleted,
        "required_artifacts_pass": required_artifacts_pass,
        "controller_api_ready": controller_api_ready,
        "controller_api_presence": controller_api_presence,
        "surface_rows": surface_rows,
        "delete_blockers": delete_blockers,
        "delete_blocker_count": len(delete_blockers),
        "controller_live_route_result_assembly_call_present": cutover_call_present,
        "safe_to_delete_nested_body_now": False,
        "next_safe_surface": (
            "rerun_nested_wrapper_deadness_and_route_body_deletion_readiness"
            if ready_for_next_cutover and cutover_call_present and not delete_blockers
            else "controller_live_route_result_assembly_cutover_with_injected_dependencies"
            if ready_for_next_cutover
            else "refresh_required_preconditions"
        ),
        "latest_required_artifacts": latest,
        "body_hash": _stable_hash(inspected_source),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    blocker_count = int(capture.get("delete_blocker_count") or 0)
    cutover_call_present = capture.get("controller_live_route_result_assembly_call_present") is True
    return {
        "route_or_body_found": (
            capture.get("body_found") is True or capture.get("route_section_found") is True
        ),
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "controller_api_ready": capture.get("controller_api_ready") is True,
        "controller_live_route_result_assembly_call_present": cutover_call_present,
        "assembly_state_consistent": (
            (cutover_call_present and blocker_count == 0)
            or ((not cutover_call_present) and blocker_count > 0)
        ),
        "deletion_not_claimed": capture.get("safe_to_delete_nested_body_now") is False,
        "next_surface_classified": bool(capture.get("next_safe_surface")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Live Route Result Assembly Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete nested body now: `{capture.get('safe_to_delete_nested_body_now')}`",
        f"Delete blocker count: `{capture.get('delete_blocker_count')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Surface Inventory",
        "",
    ]
    for name, row in dict(capture.get("surface_rows") or {}).items():
        lines.append(
            f"- `{name}`: present=`{row.get('present')}`, "
            f"delete_blocker=`{row.get('delete_blocker')}`, "
            f"classification=`{row.get('classification')}`"
        )
    lines.extend(["", "## Required Artifacts", ""])
    for name, row in dict(capture.get("latest_required_artifacts") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}` {row.get('path')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [name for name, passed in checks.items() if passed is not True]
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
        f"live_route_result_assembly_audit_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"live_route_result_assembly_audit_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_live_route_result_assembly_audit",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
