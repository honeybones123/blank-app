from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

FOCUSED_VERIFIERS = (
    "candidate_evaluation_boundary",
    "design_guide_auto_design_row_layout_filter_service_extraction",
    "design_guide_direct_target_ladder_filter_extraction",
    "design_guide_active_fail_executor_safe_candidate_filter_adapter",
    "design_guide_bottom_reo_recommendation_filter_policy_extraction",
    "bottom_reo_evaluated_candidate_filter_boundary",
    "locked_family_live_wiring_snapshot",
)

REQUIRED_CANDIDATE_EVALUATION_HELPERS = {
    "resolve_auto_design_candidate_row_layout_validity",
    "filter_auto_design_candidates_by_row_layout",
}

REQUIRED_CONTROLLER_HELPERS = {
    "filter_design_guide_controller_direct_target_ladder_candidates",
    "filter_design_guide_controller_active_fail_executor_repair_candidates",
    "resolve_design_guide_controller_bottom_reo_prerank_filter_policy",
    "resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy",
}

FORBIDDEN_IMPORT_ROOTS = {"inputs_page", "streamlit"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"prefix": prefix, "found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"prefix": prefix, "found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "").upper()
    if "PASS" in status or "LOCKED" in status or "COMPLETE" in status:
        normalized = "PASS"
    elif "PARTIAL" in status:
        normalized = "PARTIAL"
    elif "FAIL" in status or "BLOCKED" in status:
        normalized = "FAIL"
    else:
        normalized = status or "UNKNOWN"
    return {"prefix": prefix, "found": True, "status": normalized, "path": str(path)}


def _module_import_roots(source: str) -> set[str]:
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(str(alias.name).split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(str(node.module).split(".", 1)[0])
    return roots


def _function_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return "\n".join(lines[start - 1 : end])
    return ""


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Filtering Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock covers shared filtering plumbing and proof surfaces. Family-specific acceptance and repair intent stay owned by family runtimes.",
        "",
        "## Ownership",
        "",
        "- row-layout candidate filtering: `design_brain.candidate_evaluation`",
        "- direct-target ladder filtering: `DesignGuideController`",
        "- active-fail executor candidate filtering: `DesignGuideController`",
        "- bottom-reo pre-rank and growth filter policy: `DesignGuideController`",
        "- accepted/rejected engineering evidence: family runtimes",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Focused Artifacts", ""])
    for row in snapshot["focused_artifacts"]:
        lines.append(f"- `{row['prefix']}`: `{row['status']}` ({row.get('path') or 'missing'})")
    if snapshot["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {item}" for item in snapshot["failures"])
    lines.extend(["", "## Next", "", "Proceed to the shared `ranking` component if this lock is PASS."])
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    controller_source = _read(CONTROLLER)
    candidate_functions = _function_names(candidate_source)
    controller_functions = _function_names(controller_source)
    candidate_import_roots = _module_import_roots(candidate_source)
    controller_import_roots = _module_import_roots(controller_source)
    selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")
    bottom_reo_segment = _function_segment(inputs_source, "_compute_bottom_reo_recommendation")

    focused = [_latest_artifact(prefix) for prefix in FOCUSED_VERIFIERS]
    failed_artifacts = [row["prefix"] for row in focused if row.get("status") != "PASS"]
    missing_candidate_helpers = sorted(REQUIRED_CANDIDATE_EVALUATION_HELPERS - candidate_functions)
    missing_controller_helpers = sorted(REQUIRED_CONTROLLER_HELPERS - controller_functions)
    forbidden_imports = sorted(
        (candidate_import_roots | controller_import_roots) & FORBIDDEN_IMPORT_ROOTS
    )

    checks = {
        "focused_verifiers_pass": not failed_artifacts,
        "candidate_evaluation_helpers_present": not missing_candidate_helpers,
        "controller_filter_helpers_present": not missing_controller_helpers,
        "no_page_or_streamlit_imports_in_shared_filter_modules": not forbidden_imports,
        "auto_design_selector_delegates_row_layout_filter": "_filter_auto_design_candidates_by_row_layout(candidates)" in selector_segment,
        "auto_design_selector_has_no_inline_row_layout_formula": "is_valid_reo_layout(" not in selector_segment,
        "bottom_reo_delegates_prerank_filter_policy": "_resolve_design_guide_controller_bottom_reo_prerank_filter_policy(" in bottom_reo_segment,
        "bottom_reo_delegates_growth_filter_policy": "_resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(" in bottom_reo_segment,
        "bottom_reo_has_evaluated_filter_boundary_trace": "_bottom_reo_evaluated_candidate_filter_boundary_record(" in bottom_reo_segment,
        "bottom_reo_result_packaging_is_family_helper": "_build_bottom_reo_recommendation_result(" in bottom_reo_segment,
    }

    failures: list[str] = []
    if failed_artifacts:
        failures.append("focused_artifacts_not_pass:" + ",".join(failed_artifacts))
    if missing_candidate_helpers:
        failures.append("missing_candidate_evaluation_helpers:" + ",".join(missing_candidate_helpers))
    if missing_controller_helpers:
        failures.append("missing_controller_filter_helpers:" + ",".join(missing_controller_helpers))
    if forbidden_imports:
        failures.append("forbidden_imports:" + ",".join(forbidden_imports))
    for key, value in checks.items():
        if not value:
            failures.append("check_failed:" + key)

    status = "PASS" if not failures else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_filtering_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_filtering_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_filtering_lock.v1",
        "status": status,
        "failures": failures,
        "focused_artifacts": focused,
        "missing_candidate_helpers": missing_candidate_helpers,
        "missing_controller_helpers": missing_controller_helpers,
        "forbidden_imports": forbidden_imports,
        "checks": checks,
        "artifact": str(json_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
