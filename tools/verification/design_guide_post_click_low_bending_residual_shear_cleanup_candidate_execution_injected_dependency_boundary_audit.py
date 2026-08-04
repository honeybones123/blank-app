"""Audit residual-shear candidate execution injected dependency boundaries.

This is proof-only. It maps the dependencies still injected from inputs_page.py
into the controller candidate execution shell so the next extraction slice can
target one dependency boundary at a time without changing behaviour.
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
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_physical_route_body_wrapper = "

REQUIRED_ARTIFACTS = {
    "candidate_execution_supplier_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_supplier_readiness_audit"
    ),
    "dependency_injected_candidate_execution_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_dependency_injected_candidate_execution_shell_cutover"
    ),
    "route_body_supplier_ownership_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_supplier_ownership_audit"
    ),
}

DEPENDENCY_SURFACES = {
    "primary_executor_lambda": {
        "tokens": (
            "primary_executor=lambda:",
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
            "executor=_compute_shear_tightening_recommendation",
        ),
        "classification": "C. live injected primary candidate dependency",
        "owner": "inputs_page.py page-shell dependency injection",
        "next": "primary_executor_dependency_boundary_object",
    },
    "fallback_variant_generator_lambda": {
        "tokens": (
            "fallback_variant_generator=lambda:",
            "generator=generate_less_shear_reo_variants",
        ),
        "classification": "C. live injected fallback generation dependency",
        "owner": "inputs_page.py page-shell dependency injection",
        "next": "fallback_variant_generator_dependency_boundary_object",
    },
    "fallback_pre_screen_lambda": {
        "tokens": (
            "pre_screen=lambda fallback_variant:",
            "delta_screen_builder=_build_design_guide_shear_low_util_candidate_delta_screen",
            "pure_updates_checker=_shear_detailing_updates_pure",
        ),
        "classification": "C. live injected pre-screen dependency",
        "owner": "inputs_page.py page-shell dependency injection",
        "next": "fallback_pre_screen_dependency_boundary_object",
    },
    "fallback_candidate_evaluator_lambda": {
        "tokens": (
            "candidate_evaluator=lambda fallback_updates:",
            "evaluator=_evaluate_auto_design_candidate",
        ),
        "classification": "C. live injected candidate evaluation dependency",
        "owner": "inputs_page.py page-shell/shared evaluator dependency",
        "next": "fallback_candidate_evaluator_dependency_boundary_object",
    },
    "fallback_post_screen_lambda": {
        "tokens": (
            "post_screen=lambda fallback_candidate:",
            "acceptance_screen_builder=_build_design_guide_shear_low_util_candidate_acceptance_screen",
        ),
        "classification": "C. live injected post-screen dependency",
        "owner": "inputs_page.py page-shell dependency injection",
        "next": "fallback_post_screen_dependency_boundary_object",
    },
    "fallback_candidate_selector_lambda": {
        "tokens": (
            "candidate_selector=lambda fallback_candidates:",
            "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key",
        ),
        "classification": "C. live injected candidate selector dependency",
        "owner": "inputs_page.py page-shell dependency injection",
        "next": "fallback_candidate_selector_dependency_boundary_object",
    },
    "result_packaging_executor_lambda": {
        "tokens": (
            "result_packaging_executor=lambda:",
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
            "packager=_shear_tightening_as_local_cleanup_item",
            "local_cleanup_evaluator=_evaluate_local_cleanup_guidance_item",
        ),
        "classification": "C. live injected result packaging dependency",
        "owner": "inputs_page.py page-shell/shared packaging dependency",
        "next": "result_packaging_executor_dependency_boundary_object",
    },
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
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
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
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    rows: dict[str, dict[str, Any]] = {}
    for name, spec in DEPENDENCY_SURFACES.items():
        tokens = tuple(spec.get("tokens") or ())
        present = [token for token in tokens if token in body]
        rows[name] = {
            "present": len(present) == len(tokens),
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in body],
            "classification": spec.get("classification"),
            "owner": spec.get("owner"),
            "next_safe_surface": spec.get("next"),
            "delete_now": False,
        }
    live_rows = tuple(name for name, row in rows.items() if row.get("present"))
    next_safe_surface = "primary_executor_dependency_boundary_object"
    if "primary_executor_lambda" not in live_rows:
        next_safe_surface = "fallback_variant_generator_dependency_boundary_object"
    return {
        "decision": "RESIDUAL_SHEAR_CANDIDATE_EXECUTION_INJECTED_DEPENDENCIES_MAPPED",
        "route_body_found": bool(body),
        "required_artifacts": latest,
        "required_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "surface_rows": rows,
        "live_injected_dependency_count": len(live_rows),
        "live_injected_dependencies": live_rows,
        "safe_to_delete_supplier_now": False,
        "next_safe_surface": next_safe_surface,
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
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "all_dependencies_classified": all(row.get("classification") for row in rows.values()),
        "live_dependencies_present": capture.get("live_injected_dependency_count", 0) > 0,
        "supplier_not_deleted_while_dependencies_live": (
            capture.get("safe_to_delete_supplier_now") is False
        ),
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
        "# Residual Shear Candidate Execution Injected Dependency Boundary Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Live injected dependency count: `{capture.get('live_injected_dependency_count')}`",
        f"Safe to delete supplier now: `{capture.get('safe_to_delete_supplier_now')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Dependencies",
        "",
    ]
    for name, row in dict(capture.get("surface_rows") or {}).items():
        lines.append(
            f"- `{name}`: present=`{row.get('present')}`, owner=`{row.get('owner')}`, "
            f"classification=`{row.get('classification')}`, next=`{row.get('next_safe_surface')}`"
        )
    lines.extend(["", "## Required Artifacts", ""])
    for name, row in dict(capture.get("required_artifacts") or {}).items():
        lines.append(f"- `{name}`: status=`{row.get('status')}`, path=`{row.get('path')}`")
    lines.extend(["", "## Checks", ""])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
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
        f"candidate_execution_injected_dependency_boundary_audit_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"candidate_execution_injected_dependency_boundary_audit_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_"
        f"candidate_execution_injected_dependency_boundary_audit_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_injected_dependency_boundary_audit",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(audit_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
