from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


REQUIRED_SHELL_RENDER_CALLS = (
    "render_inputs_page_setup_current_coordinator",
    "render_inputs_widget_sections_current_coordinator",
    "render_inputs_summary_pipeline_current_coordinator",
    "render_inputs_tail_current_coordinator",
)


REQUIRED_BOUNDARIES = {
    "session",
    "widgets",
    "summaries",
    "diagrams",
    "calculation_source",
    "calculation_source_hash",
    "calculations",
}


def _function_calls(source: str, function_name: str) -> set[str]:
    tree = ast.parse(source)
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            calls.add(func.id)
        elif isinstance(func, ast.Attribute):
            calls.add(func.attr)
    return calls


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


def _app_route_target() -> str:
    app_path = REPO_ROOT / "app.py"
    source = app_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "PAGES":
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


def _result(ok: bool, **extra: Any) -> dict[str, Any]:
    return {"ok": ok, **extra}


def main() -> int:
    import inputs_page

    boundary_status = {
        name: callable(inputs_page.EXTRACTED_MODULE_BOUNDARIES.get(name))
        for name in sorted(REQUIRED_BOUNDARIES)
    }

    shell_source = inspect.getsource(inputs_page.render_inputs_page)
    shell_module_source = inspect.getsource(inputs_page)
    permanent_page_source = (REPO_ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="replace")
    staging_shell_exists = (REPO_ROOT / "inputs_page_shell.py").exists()

    shell_calls = _function_calls(shell_source, "render_inputs_page")
    render_call_positions = [shell_source.find(call) for call in REQUIRED_SHELL_RENDER_CALLS]

    route_target = _app_route_target()
    checks = {
        "routing_points_to_permanent_shell": route_target == "inputs_page.render_inputs",
        "staging_shell_removed_after_cutover": not staging_shell_exists,
        "shell_composes_old_page_route_coordinators": all(
            call in shell_calls for call in REQUIRED_SHELL_RENDER_CALLS
        ),
        "shell_route_coordinator_order_matches_old_entrypoint": (
            all(position >= 0 for position in render_call_positions)
            and render_call_positions == sorted(render_call_positions)
        ),
        "shell_does_not_call_old_render_inputs": "render_inputs" not in shell_calls,
        "shell_does_not_import_old_inputs_page": not _imports_module(shell_module_source, "inputs_page"),
        "shell_has_no_temporary_legacy_wrapper_classifications": "TEMPORARY_LEGACY_COORDINATOR"
        not in shell_module_source,
        "dead_section_wrappers_removed": all(
            f"def {name}(" not in shell_module_source
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
        "all_extracted_boundaries_importable": all(boundary_status.values()),
        "old_page_entrypoint_removed": "def render_inputs(" not in permanent_page_source,
        "shell_entrypoint_exists": callable(getattr(inputs_page, "render_inputs_page", None)),
        "shell_profiled_alias_exists": callable(getattr(inputs_page, "render_inputs", None)),
    }

    report = {
        "verifier": "inputs_page_shell_parity",
        "browser_parity_basis": (
            "permanent shell render_inputs_page composes the extracted route coordinators "
            "in the locked order; routing now points to inputs_page.render_inputs"
        ),
        "route_target": route_target,
        "checks": checks,
        "boundary_status": boundary_status,
        "shell_render_inputs_page_id": id(inputs_page.render_inputs_page),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
