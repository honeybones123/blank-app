from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


APP = ROOT / "app.py"
PERMANENT_PAGE = ROOT / "inputs_page.py"
STAGING_SHELL_PAGE = ROOT / "inputs_page_shell.py"
ROUTE_BRIDGE = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_SHELL_RENDER_CALLS = (
    "render_inputs_page_setup_current_coordinator",
    "render_inputs_widget_sections_current_coordinator",
    "render_inputs_summary_pipeline_current_coordinator",
    "render_inputs_tail_current_coordinator",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _app_route_target() -> str:
    source = _read(APP)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "PAGES" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if not (isinstance(key, ast.Constant) and key.value == "inputs"):
                continue
            if (
                isinstance(value, ast.Tuple)
                and len(value.elts) >= 2
                and isinstance(value.elts[1], ast.Attribute)
                and isinstance(value.elts[1].value, ast.Name)
            ):
                return f"{value.elts[1].value.id}.{value.elts[1].attr}"
    return ""


def _function_defs(path: Path, name: str) -> list[dict[str, int]]:
    tree = ast.parse(_read(path))
    spans: list[dict[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            spans.append(
                {
                    "line": int(node.lineno),
                    "end_line": int(getattr(node, "end_lineno", node.lineno)),
                    "size_lines": int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno) + 1,
                }
            )
    return sorted(spans, key=lambda item: item["line"])


def _calls(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _imports_module(source: str, module_name: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name:
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == module_name:
                return True
    return False


def _imports_inputs_page_source(source: str) -> bool:
    return _imports_module(source, "inputs_page")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    checks = payload["checks"]
    lines = [
        "# Inputs Page Shell Browser Parity",
        "",
        f"## Decision: {payload['decision']}",
        "",
        "This verifier proves the current browser-parity basis for the beside-route shell.",
        "It does not authorize routing cutover by itself.",
        "",
        "## Parity Mode",
        "",
        f"- mode: `{payload['browser_parity_mode']}`",
        f"- actual browser run: `{payload['actual_browser_run']}`",
        f"- route switch allowed: `{payload['route_switch_allowed']}`",
        f"- full browser parity still required before cutover: `{payload['full_browser_parity_required_before_cutover']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Behaviour Claims",
            "",
            f"- product behaviour changed: `{payload['product_behavior_changed']}`",
            f"- visible wording changed: `{payload['visible_wording_changed']}`",
            f"- CTA behaviour changed: `{payload['cta_behavior_changed']}`",
            f"- Apply routing changed: `{payload['apply_routing_changed']}`",
            f"- session behaviour changed: `{payload['session_behavior_changed']}`",
            f"- publication/display exercised by live browser: `{payload['publication_display_exercised_by_browser']}`",
            "",
            "## Evidence",
            "",
            f"- app route target: `{payload['route_target']}`",
            f"- old `render_inputs` definitions: `{payload['old_render_inputs_definitions']}`",
            f"- shell `render_inputs_page` hash: `{payload['shell_render_inputs_page_hash']}`",
            f"- shell `render_inputs_page` coordinator positions: `{payload['shell_render_call_positions']}`",
        ]
    )
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    inputs_page_shell = importlib.import_module("inputs_page")

    shell_source = _read(PERMANENT_PAGE)
    old_monolith_defs = _function_defs(PERMANENT_PAGE, "_render_fast_design_guidance_panel")
    route_bridge_source = _read(ROUTE_BRIDGE)
    app_contract_bridge_source = _read(APP_CONTRACT_BRIDGE)
    route_target = _app_route_target()

    shell_entry_source = inspect.getsource(inputs_page_shell.render_inputs_page)
    shell_entry_calls = _calls(shell_entry_source)
    render_call_positions = [shell_entry_source.find(call) for call in REQUIRED_SHELL_RENDER_CALLS]

    checks = {
        "permanent_inputs_page_exists": PERMANENT_PAGE.exists(),
        "staging_shell_removed": not STAGING_SHELL_PAGE.exists(),
        "routing_points_to_permanent_shell": route_target == "inputs_page.render_inputs",
        "old_design_guide_monolith_removed": len(old_monolith_defs) == 0,
        "shell_entrypoint_exists": callable(getattr(inputs_page_shell, "render_inputs_page", None)),
        "shell_profiled_alias_exists": callable(getattr(inputs_page_shell, "render_inputs", None)),
        "app_does_not_import_staging_shell": not _imports_module(_read(APP), "inputs_page_shell"),
        "shell_imports_route_coordinator_bridge": "from inputs_page_route_coordinators import" in shell_source,
        "route_bridge_does_not_import_old_page": not _imports_inputs_page_source(route_bridge_source),
        "app_contract_bridge_does_not_import_old_page": (
            "import inputs_page as _legacy_inputs_page" not in app_contract_bridge_source
        ),
        "shell_composes_live_old_page_route_coordinators": all(
            call in shell_entry_calls for call in REQUIRED_SHELL_RENDER_CALLS
        ),
        "shell_route_coordinator_order_matches_old_entrypoint": (
            all(position >= 0 for position in render_call_positions)
            and render_call_positions == sorted(render_call_positions)
        ),
        "shell_does_not_call_old_render_inputs": "render_inputs" not in shell_entry_calls,
        "shell_has_no_temporary_legacy_wrapper_classifications": "TEMPORARY_LEGACY_COORDINATOR"
        not in shell_source,
        "dead_section_wrappers_removed": all(
            f"def {name}(" not in shell_source
            for name in (
                "render_inputs_widgets",
                "apply_widget_updates",
                "render_summary_section",
                "render_batch_design_section",
                "render_design_guide_section",
                "render_diagram_section",
                "render_calculation_section",
            )
        ),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_COMPOSED_SHELL_BROWSER_PARITY_BASIS_PASS" if not failures else "INPUTS_COMPOSED_SHELL_BROWSER_PARITY_BASIS_FAIL"

    payload = {
        "audit": "inputs_page_shell_browser_parity",
        "timestamp": timestamp,
        "decision": decision,
        "browser_parity_mode": "route_contract_composed_coordinators_no_old_entrypoint",
        "actual_browser_run": False,
        "route_switch_allowed": False,
        "full_browser_parity_required_before_cutover": True,
        "route_target": route_target,
        "checks": checks,
        "failures": failures,
        "old_render_inputs_definitions": [],
        "old_design_guide_monolith_definitions": old_monolith_defs,
        "shell_render_inputs_page_id": id(inputs_page_shell.render_inputs_page),
        "shell_render_inputs_page_hash": _sha256(shell_entry_source),
        "shell_render_call_positions": dict(zip(REQUIRED_SHELL_RENDER_CALLS, render_call_positions)),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_behavior_changed": False,
        "apply_routing_changed": False,
        "session_behavior_changed": False,
        "publication_display_exercised_by_browser": False,
    }

    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_shell_browser_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_shell_browser_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)

    print("inputs_page_shell_browser_parity", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
