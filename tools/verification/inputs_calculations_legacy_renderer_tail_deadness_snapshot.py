from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CALCULATION_OWNER = (
    ROOT / "inputs_application" / "page_runtime" / "calculations.py"
)
CALCULATION_TRACE_MODULE = ROOT / "inputs_page_modules" / "calculations" / "trace.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


LEGACY_TOKENS = (
    "bending_table_html = cached_generate_summary_table_html",
    "shear_table_html = cached_generate_summary_table_html",
    "crack_table_html = cached_generate_summary_table_html",
    "defl_table_html = cached_generate_summary_table_html",
    "inputs-top-level-row",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_by_name(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda node: int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno),
    )


def _source_for_node(source: str, node: ast.FunctionDef) -> str:
    return "\n".join(
        source.splitlines()[int(node.lineno) - 1 : int(getattr(node, "end_lineno", node.lineno))]
    )


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Calculations Legacy Renderer Tail Deadness Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Dead Tail",
            "",
            f"- Function: `{payload.get('function_name')}`",
            "",
            "## Boundary",
            "",
            "- The legacy calculation summary-expander tail tokens are absent from `inputs_page.py`.",
            "- The remaining calculation surface is a trace-only coordinator that delegates source/model construction to `inputs_page_modules.calculations`.",
            "- This proof does not move Streamlit rendering, engineering calculations, session state, or CTA/apply behavior.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page_source = _read(INPUTS_PAGE)
    owner_source = _read(CALCULATION_OWNER)
    source = page_source + "\n" + owner_source
    module_source = _read(CALCULATION_TRACE_MODULE)
    tree = ast.parse(owner_source)
    fn = _function_by_name(
        tree,
        "render_inputs_calculation_fragment_current_coordinator",
    )
    function_name = "render_inputs_calculation_fragment_current_coordinator"
    checks: dict[str, Any] = {
        "target_function_found": fn is not None,
        "legacy_renderer_tokens_absent_from_page": not any(token in source for token in LEGACY_TOKENS),
    }
    function_source = ""
    if fn is not None:
        function_source = _source_for_node(owner_source, fn)
        checks["trace_coordinator_delegates_to_module"] = all(
            token in function_source
            for token in (
                "render_inputs_calculation_explainer_trace(",
            )
        )
        checks["trace_coordinator_is_trace_only"] = (
            '"live_calculation_explainer_renderer_cutover": False' in module_source
            and '"calculation_explainer_view_model_trace_only": True' in module_source
        )
    else:
        checks["trace_coordinator_delegates_to_module"] = False
        checks["trace_coordinator_is_trace_only"] = False

    failures = [key for key, value in checks.items() if not value]
    decision = (
        "LEGACY_CALCULATION_RENDERER_TAIL_DELETED"
        if not failures
        else "LEGACY_CALCULATION_RENDERER_TAIL_DELETION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_calculations_legacy_renderer_tail_deadness_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "function_name": function_name,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "live_renderer_switched": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_calculations_legacy_renderer_tail_deadness_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_calculations_legacy_renderer_tail_deadness_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_calculations_legacy_renderer_tail_deadness_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
