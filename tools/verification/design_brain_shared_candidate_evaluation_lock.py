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
MODULE_PATH = ROOT / "design_brain" / "candidate_evaluation.py"

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
}

REQUIRED_MODEL_NAMES = {
    "BeamCandidateInput",
    "BeamCandidateUpdate",
    "BeamCandidateEvaluation",
}

REQUIRED_HELPERS = {
    "stable_candidate_evaluation_hash",
    "build_candidate_state_hash",
    "evaluate_design_candidate_with_updates",
    "resolve_design_candidate_overview_for_safety_check",
}

SEPARATELY_SCOPED_HELPER_PREFIXES = (
    "filter_",
    "rank_",
    "select_",
    "score_",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(set(imports))


def _function_and_class_names(source: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    functions: set[str] = set()
    classes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.add(node.name)
    return functions, classes


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or "").upper()
    if "PASS" in status:
        normalized = "PASS"
    elif "FAIL" in status:
        normalized = "FAIL"
    elif "PARTIAL" in status:
        normalized = "PARTIAL"
    else:
        normalized = status or "UNKNOWN"
    return {"found": True, "status": normalized, "path": str(path)}


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Candidate Evaluation Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This locks the base candidate evaluation boundary: model shape, stable hashes, plain-data evaluator handoff, and overview-for-safety helper.",
        "",
        "Filtering, ranking, and final candidate selection helpers are intentionally left to their own shared-component rows.",
        "",
        "## Checks",
        "",
        f"- boundary snapshot PASS: `{snapshot['checks']['boundary_snapshot_pass']}`",
        f"- forbidden imports absent: `{snapshot['checks']['forbidden_imports_absent']}`",
        f"- required models present: `{snapshot['checks']['required_models_present']}`",
        f"- required helpers present: `{snapshot['checks']['required_helpers_present']}`",
        f"- separately scoped helpers identified: `{len(snapshot['separately_scoped_helpers'])}`",
        "",
        "## Separately Scoped Helpers",
        "",
    ]
    for name in snapshot["separately_scoped_helpers"][:80]:
        lines.append(f"- `{name}`")
    if len(snapshot["separately_scoped_helpers"]) > 80:
        lines.append(f"- ... `{len(snapshot['separately_scoped_helpers']) - 80}` more")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- JSON: `{snapshot['artifact']}`",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = _read(MODULE_PATH)
    imports = _module_imports(source)
    functions, classes = _function_and_class_names(source)
    forbidden_imports = sorted(
        imported
        for imported in imports
        if imported.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS
    )
    missing_models = sorted(REQUIRED_MODEL_NAMES - classes)
    missing_helpers = sorted(REQUIRED_HELPERS - functions)
    boundary = _latest_artifact("candidate_evaluation_boundary")
    separately_scoped = sorted(
        name
        for name in functions
        if name.startswith(SEPARATELY_SCOPED_HELPER_PREFIXES)
        or "_rank" in name
        or "_selection" in name
        or "_candidate_sort" in name
    )
    failures: list[str] = []
    if boundary.get("status") != "PASS":
        failures.append("candidate_evaluation_boundary_not_pass")
    if forbidden_imports:
        failures.append("forbidden_imports:" + ",".join(forbidden_imports))
    if missing_models:
        failures.append("missing_models:" + ",".join(missing_models))
    if missing_helpers:
        failures.append("missing_helpers:" + ",".join(missing_helpers))
    status = "PASS" if not failures else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_candidate_evaluation_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_candidate_evaluation_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_candidate_evaluation_lock.v1",
        "status": status,
        "failures": failures,
        "module_path": str(MODULE_PATH),
        "boundary_snapshot": boundary,
        "forbidden_imports": forbidden_imports,
        "missing_models": missing_models,
        "missing_helpers": missing_helpers,
        "separately_scoped_helpers": separately_scoped,
        "checks": {
            "boundary_snapshot_pass": boundary.get("status") == "PASS",
            "forbidden_imports_absent": not forbidden_imports,
            "required_models_present": not missing_models,
            "required_helpers_present": not missing_helpers,
        },
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
