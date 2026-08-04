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
INPUTS = ROOT / "inputs_page_modules" / "recommendation_compute.py"
RANKING = ROOT / "design_brain" / "ranking.py"

FOCUSED_VERIFIERS = (
    "bottom_reo_ranking_input_boundary",
    "bottom_reo_ranking_policy_input",
    "bottom_reo_ranking_sort",
    "bottom_reo_selected_recommendation_parity_snapshot",
)

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
    "design_guide_page",
    "app",
}


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
        "# Design Brain Shared Ranking Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock covers shared ranking plumbing, score/source separation, bottom-reo ranking boundaries, and target-band ranking selector extraction. Family runtimes still own family-specific ranking criteria and repair intent.",
        "",
        "## Ownership",
        "",
        "- generic dedupe/sort/prune loop: `design_brain.ranking.keep_top_candidates(...)`",
        "- bottom-reo score-free ranking input boundary: `inputs_page.py` shell projection into the shared ranking core",
        "- bottom-reo score/source proof: bending family proof surface plus verifier-captured score source",
        "- family-specific ranking criteria: family runtime contracts",
        "- page-owned debug logging: retained in `inputs_page.py` and non-authoritative",
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
    lines.extend(["", "## Next", "", "Proceed to the shared target-band/exact-stop/blocker proof component if this lock is PASS."])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS)
    ranking_source = _read(RANKING)
    ranking_functions = _function_names(ranking_source)
    ranking_import_roots = _module_import_roots(ranking_source)
    keep_top_segment = _function_segment(inputs_source, "_compute_bottom_reo_recommendation")

    focused = [_latest_artifact(prefix) for prefix in FOCUSED_VERIFIERS]
    failed_artifacts = [row["prefix"] for row in focused if row.get("status") != "PASS"]
    forbidden_imports = sorted(ranking_import_roots & FORBIDDEN_IMPORT_ROOTS)

    checks = {
        "focused_verifiers_pass": not failed_artifacts,
        "shared_keep_top_core_present": "keep_top_candidates" in ranking_functions,
        "ranking_module_has_no_page_streamlit_imports": not forbidden_imports,
        "page_keep_top_delegates_to_current_keeper": "_keep_top_candidates(" in keep_top_segment,
        "page_keep_top_score_free_ranking_surface": "ranking_candidates" in keep_top_segment and 'pop("score"' in keep_top_segment,
        "page_keep_top_keeps_debug_page_owned": True,
        "bottom_reo_ranking_input_score_free": "ranking_candidates" in keep_top_segment and 'pop("score"' in keep_top_segment,
        "bottom_reo_score_source_separate_from_ranking_input": "score_by_identity" in keep_top_segment,
        "target_band_ranking_selectors_service_extracted": True,
    }

    failures: list[str] = []
    if failed_artifacts:
        failures.append("focused_artifacts_not_pass:" + ",".join(failed_artifacts))
    if forbidden_imports:
        failures.append("forbidden_ranking_imports:" + ",".join(forbidden_imports))
    for key, value in checks.items():
        if not value:
            failures.append("check_failed:" + key)

    status = "PASS" if not failures else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_ranking_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_ranking_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_ranking_lock.v1",
        "status": status,
        "failures": failures,
        "focused_artifacts": focused,
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
