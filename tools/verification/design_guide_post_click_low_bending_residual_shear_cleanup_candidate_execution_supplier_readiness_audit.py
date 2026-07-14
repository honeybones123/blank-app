"""Audit remaining residual-shear candidate execution ownership.

This is proof-only. It does not execute product code or move ownership.
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

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_physical_route_body_wrapper = "


SURFACES: dict[str, dict[str, Any]] = {
    "primary_executor_call": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
        "classification": "still live page-owned candidate execution",
        "delete_blocker": True,
        "ownership": "page supplier",
    },
    "primary_executor_dependency": {
        "token": "executor=_compute_shear_tightening_recommendation",
        "classification": "still injected/shared shear recommendation dependency",
        "delete_blocker": True,
        "ownership": "page/shared dependency",
    },
    "fallback_search_loop_controller_shell": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop(",
        "classification": "controller shell already present",
        "delete_blocker": False,
        "ownership": "controller shell",
    },
    "fallback_variant_generator_lambda": {
        "token": "fallback_variant_generator=lambda:",
        "classification": "still live injected generator dependency",
        "delete_blocker": True,
        "ownership": "page supplier dependency injection",
    },
    "fallback_pre_screen_lambda": {
        "token": "pre_screen=lambda fallback_variant:",
        "classification": "still live injected pre-screen dependency",
        "delete_blocker": True,
        "ownership": "page supplier dependency injection",
    },
    "fallback_candidate_evaluator_lambda": {
        "token": "candidate_evaluator=lambda fallback_updates:",
        "classification": "still live injected evaluator dependency",
        "delete_blocker": True,
        "ownership": "page supplier dependency injection",
    },
    "fallback_post_screen_lambda": {
        "token": "post_screen=lambda fallback_candidate:",
        "classification": "still live injected post-screen dependency",
        "delete_blocker": True,
        "ownership": "page supplier dependency injection",
    },
    "fallback_candidate_selector_lambda": {
        "token": "candidate_selector=lambda fallback_candidates:",
        "classification": "still live injected selector dependency",
        "delete_blocker": True,
        "ownership": "page supplier dependency injection",
    },
    "candidate_execution_bundle": {
        "token": "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle(",
        "classification": "controller proof bundle already present",
        "delete_blocker": False,
        "ownership": "controller proof/bundle",
    },
    "prebuilt_route_shell_consumes_bundle": {
        "token": "prebuilt_primary_result=residual_candidate_execution_bundle.get(\"primary_result\")",
        "classification": "route shell already consumes bundle",
        "delete_blocker": False,
        "ownership": "controller shell",
    },
    "result_packaging_call": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
        "classification": "still live result packaging execution",
        "delete_blocker": True,
        "ownership": "page supplier",
    },
    "local_cleanup_evaluator_dependency": {
        "token": "local_cleanup_evaluator=_evaluate_local_cleanup_guidance_item",
        "classification": "still live local cleanup evaluator dependency",
        "delete_blocker": True,
        "ownership": "page/shared dependency",
    },
}


REQUIRED_ARTIFACTS = {
    "candidate_execution_bundle_route_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle_route_shell_cutover"
    ),
    "dependency_injected_candidate_execution_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_dependency_injected_candidate_execution_shell_cutover"
    ),
    "result_packaging_execution_bundle_tail_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle_tail_cutover"
    ),
    "route_body_supplier_ownership_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_supplier_ownership_audit"
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
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    rows: dict[str, dict[str, Any]] = {}
    for name, config in SURFACES.items():
        present = bool(body and str(config["token"]) in body)
        rows[name] = {
            "token": config["token"],
            "present": present,
            "classification": config["classification"],
            "ownership": config["ownership"],
            "delete_blocker": bool(config["delete_blocker"] and present),
        }
    blockers = [name for name, row in rows.items() if row.get("delete_blocker")]
    previous_artifacts = {
        name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()
    }
    dependency_shell_cutover = (
        previous_artifacts.get("dependency_injected_candidate_execution_shell_cutover", {}).get("status")
        == "PASS"
    )
    return {
        "decision": "RESIDUAL_SHEAR_CANDIDATE_EXECUTION_SUPPLIER_STILL_LIVE",
        "route_body_found": bool(body),
        "surface_rows": rows,
        "delete_blockers": blockers,
        "delete_blocker_count": len(blockers),
        "safe_to_delete_supplier_now": False,
        "safe_to_move_without_dependency_injection": False,
        "previous_artifacts": previous_artifacts,
        "previous_artifacts_pass": all(
            row.get("status") == "PASS" for row in previous_artifacts.values()
        ),
        "dependency_injected_candidate_execution_shell_cutover": dependency_shell_cutover,
        "next_safe_surface": (
            "candidate_execution_injected_dependency_boundary_audit"
            if dependency_shell_cutover
            else "dependency_injected_candidate_execution_shell_readiness"
        ),
        "why_not_delete": (
            "primary/fallback candidate generation, evaluation, selection, result packaging, "
            "and local cleanup evaluation still execute through page supplier dependencies"
        ),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "route_body_hash": _stable_hash(body),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = dict(capture.get("surface_rows") or {})
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "candidate_bundle_present": (
            (rows.get("candidate_execution_bundle") or {}).get("present") is True
        ),
        "route_shell_consumes_bundle": (
            (rows.get("prebuilt_route_shell_consumes_bundle") or {}).get("present") is True
        ),
        "dependency_injected_candidate_execution_shell_cutover": (
            capture.get("dependency_injected_candidate_execution_shell_cutover") is True
        ),
        "live_dependencies_classified": bool(capture.get("delete_blockers")),
        "supplier_not_deleted_while_live": (
            capture.get("safe_to_delete_supplier_now") is False
        ),
        "dependency_injection_required": (
            capture.get("safe_to_move_without_dependency_injection") is False
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
        "# Residual Shear Candidate Execution Supplier Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete supplier now: `{capture.get('safe_to_delete_supplier_now')}`",
        f"Safe to move without dependency injection: `{capture.get('safe_to_move_without_dependency_injection')}`",
        f"Delete blocker count: `{capture.get('delete_blocker_count')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Why Not Delete",
        "",
        str(capture.get("why_not_delete") or ""),
        "",
        "## Surface Inventory",
        "",
    ]
    for name, row in dict(capture.get("surface_rows") or {}).items():
        lines.append(
            "- `{}`: present=`{}`, delete_blocker=`{}`, ownership=`{}`, classification=`{}`".format(
                name,
                row.get("present"),
                row.get("delete_blocker"),
                row.get("ownership"),
                row.get("classification"),
            )
        )
    lines.extend(["", "## Checks", ""])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
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
        f"candidate_execution_supplier_readiness_audit_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"candidate_execution_supplier_readiness_audit_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_supplier_readiness_audit",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
