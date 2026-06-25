from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

EXPECTED_IMPORTS = {
    "build_design_guide_card_decision_display_fields": "_build_design_guide_card_decision_display_fields_core",
    "build_design_guide_card_render_model_fields": "_build_design_guide_card_render_model_fields_core",
}
EXPECTED_DELEGATIONS = {
    "_build_design_guide_card_decision_display_fields": "_build_design_guide_card_decision_display_fields_core",
    "_build_design_guide_card_render_model": "_build_design_guide_card_render_model_fields_core",
}


def _call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            names.add(child.func.id)
    return names


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_output_formatting_usage_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_output_formatting_usage_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Output Formatting Usage Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Proof",
                "",
                "- `inputs_page.py` imports the core display packers from `design_brain.output_formatting`.",
                "- Page wrapper functions delegate to those imported core functions.",
                "- Page wrappers may still collect page-local resolved fields before delegation.",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(INPUTS_PAGE))
    imported_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "design_brain.output_formatting":
            for alias in node.names:
                imported_aliases[alias.name] = alias.asname or alias.name

    delegations: dict[str, dict[str, Any]] = {}
    for wrapper_name, core_name in EXPECTED_DELEGATIONS.items():
        function = _find_function(tree, wrapper_name)
        calls = _call_names(function) if function else set()
        delegations[wrapper_name] = {
            "function_present": function is not None,
            "expected_core": core_name,
            "calls_expected_core": core_name in calls,
            "called_names": sorted(calls),
        }

    checks = {
        "imports_decision_display_core": imported_aliases.get("build_design_guide_card_decision_display_fields")
        == "_build_design_guide_card_decision_display_fields_core",
        "imports_render_model_core": imported_aliases.get("build_design_guide_card_render_model_fields")
        == "_build_design_guide_card_render_model_fields_core",
        "decision_wrapper_delegates": delegations["_build_design_guide_card_decision_display_fields"]["calls_expected_core"],
        "render_model_wrapper_delegates": delegations["_build_design_guide_card_render_model"]["calls_expected_core"],
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_guide_output_formatting_usage_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "inputs_page": str(INPUTS_PAGE),
        "expected_imports": EXPECTED_IMPORTS,
        "imported_aliases": imported_aliases,
        "delegations": delegations,
        "checks": checks,
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("Design Guide output formatting usage FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("Design Guide output formatting usage PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
