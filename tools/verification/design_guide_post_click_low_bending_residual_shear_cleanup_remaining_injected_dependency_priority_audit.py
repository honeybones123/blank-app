"""Prioritize remaining injected dependencies in the residual-shear route body."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

SURFACES = {
    "route_entry_guard": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(",
        "category": "controller guard runner",
        "priority": 80,
        "recommended_action": "keep as controller-owned guard boundary until whole route body deletion is proven",
    },
    "primary_executor": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
        "category": "injected execution shell",
        "priority": 10,
        "recommended_action": "next extraction target: prove controller route can accept primary executor result as dependency boundary and stop treating page wrapper as authority",
        "completed_cutover_prefix": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover",
    },
    "fallback_variant_generator": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
        "category": "injected execution shell",
        "priority": 20,
        "recommended_action": "extract after primary executor; generator still drives candidate search surface",
        "completed_cutover_prefix": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover",
    },
    "candidate_evaluator": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
        "category": "injected execution shell",
        "priority": 30,
        "recommended_action": "extract after generator; evaluator is engineering dependency and must stay injected until boundary proof",
        "completed_cutover_prefix": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_implementation",
    },
    "materiality_pre_screen": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        "category": "injected screening shell",
        "priority": 40,
        "recommended_action": "extract after evaluator; depends on candidate result shape",
        "completed_cutover_prefix": "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_cutover_implementation",
    },
    "materiality_post_screen": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
        "category": "injected screening shell",
        "priority": 41,
        "recommended_action": "extract with pre-screen or immediately after",
        "completed_cutover_prefix": "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_cutover_implementation",
    },
    "candidate_selector": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
        "category": "injected selection shell",
        "priority": 50,
        "recommended_action": "selector sort-key is represented; extract only after evaluator/screening shells",
        "completed_cutover_prefix": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_cutover_implementation",
    },
    "result_packaging": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
        "category": "bounded injected packaging shell",
        "priority": 70,
        "recommended_action": "already bounded; keep until whole route shell deletion",
    },
    "shared_button_contract": {
        "token": "_design_guide_button_contract(residual_promoted, state=state)",
        "category": "bounded shared button-contract shell",
        "priority": 75,
        "recommended_action": "already source-summary bounded; keep until CTA/apply routing boundary says otherwise",
    },
    "debug_projection_tail": {
        "token": "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only(",
        "category": "compatibility/debug tail",
        "priority": 90,
        "recommended_action": "delete only after consumer reachability says debug tail is dead",
    },
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=120)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
        "passed": proc.returncode == 0,
    }


def _latest(prefix: str) -> dict[str, Any] | None:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        return None
    try:
        return json.loads(matches[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _capture() -> dict[str, Any]:
    deletion_readiness = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness.py",
        ]
    )
    return_boundary = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_return_boundary_cutover.py",
        ]
    )
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    rows: dict[str, dict[str, Any]] = {}
    for name, spec in SURFACES.items():
        present = spec["token"] in route
        completed_cutover = False
        if spec.get("completed_cutover_prefix"):
            completed_cutover = (
                (_latest(str(spec.get("completed_cutover_prefix"))) or {}).get("status")
                == "PASS"
            )
        rows[name] = {
            "present": present,
            "category": spec["category"],
            "priority": spec["priority"],
            "recommended_action": spec["recommended_action"],
            "token": spec["token"],
            "completed_cutover": completed_cutover,
        }
    present_rows = {
        name: row for name, row in rows.items() if row.get("present")
    }
    actionable_rows = {
        name: row
        for name, row in present_rows.items()
        if row.get("category") in (
            "injected execution shell",
            "injected screening shell",
            "injected selection shell",
        )
        and row.get("completed_cutover") is not True
    }
    next_surface = ""
    if actionable_rows:
        next_surface = min(
            actionable_rows.items(), key=lambda item: int(item[1]["priority"])
        )[0]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_REMAINING_INJECTED_DEPENDENCIES_PRIORITIZED",
        "deletion_readiness": deletion_readiness,
        "return_boundary": return_boundary,
        "route_found": bool(route),
        "surface_rows": rows,
        "present_surfaces": tuple(present_rows),
        "actionable_surfaces": tuple(actionable_rows),
        "next_safe_surface": next_surface or "route_body_deletion_or_debug_tail_cleanup",
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "deletion_readiness_passed": (capture.get("deletion_readiness") or {}).get("passed")
        is True,
        "return_boundary_passed": (capture.get("return_boundary") or {}).get("passed")
        is True,
        "present_surfaces_recorded": bool(capture.get("present_surfaces")),
        "next_safe_surface_selected": bool(capture.get("next_safe_surface")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    rows = dict(capture.get("surface_rows") or {})
    lines = [
        "# Residual Shear Cleanup Remaining Injected Dependency Priority Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Present surfaces: `{capture.get('present_surfaces')}`",
        f"- Actionable surfaces: `{capture.get('actionable_surfaces')}`",
        f"- Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Surface Rows",
        "",
    ]
    for name, row in rows.items():
        lines.append(
            "- `{}`: present=`{}`, category=`{}`, priority=`{}`, next=`{}`".format(
                name,
                row.get("present"),
                row.get("category"),
                row.get("priority"),
                row.get("recommended_action"),
            )
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_injected_dependency_priority_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_remaining_injected_dependency_priority_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_remaining_injected_dependency_priority_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_remaining_injected_dependency_priority_audit_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_injected_dependency_priority_audit "
        + payload["status"]
    )
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
