"""Verify current Inputs primary CTA queue extraction and runtime binding."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "primary_button_queue.py"
RUNTIME = ROOT / "inputs_application" / "page_runtime" / "__init__.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _restore_module_globals(module, originals: dict[str, object], missing: object) -> None:
    for name, value in originals.items():
        if value is missing:
            module.__dict__.pop(name, None)
        else:
            module.__dict__[name] = value


def main() -> int:
    module_source = MODULE.read_text(encoding="utf-8")
    runtime_source = RUNTIME.read_text(encoding="utf-8")
    workspace_source = (
        ROOT / "inputs_application" / "engineering_workspace.py"
    ).read_text(encoding="utf-8")
    module_node = _function_node(
        module_source,
        "_queue_primary_design_guide_button_action",
    )

    from inputs_application import page_runtime as runtime
    from inputs_page_modules.design_guide import primary_button_queue as extracted

    dependency_names = tuple(
        getattr(extracted, "_PRIMARY_BUTTON_QUEUE_DEPENDENCIES", ())
    )
    missing = object()
    originals = {
        name: extracted.__dict__.get(name, missing) for name in dependency_names
    }
    markers = {name: object() for name in dependency_names}
    try:
        extracted.bind_primary_button_queue_dependencies(markers)
        binder_bound_all_dependencies = all(
            extracted.__dict__.get(name) is marker
            for name, marker in markers.items()
        )
    finally:
        _restore_module_globals(extracted, originals, missing)

    checks: dict[str, bool] = {
        "module_contains_extracted_body": (
            (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1
            > 190
        ),
        "module_has_dependency_binder": (
            "def bind_primary_button_queue_dependencies" in module_source
        ),
        "module_declares_dependency_surface": bool(dependency_names)
        and all(name in module_source for name in dependency_names),
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "callback_queues_cta_intent_without_executing_apply": (
            "st.session_state" in module_source
            and 'st.session_state["_inputs_action_apply_recommendation"] = True'
            in module_source
            and "_begin_design_guide_apply_trace(" in module_source
            and "apply_recommendation_result(rec_dict)" not in module_source
            and "handle_auto_design" in module_source
        ),
        "design_guide_fragment_entry_consumes_pending_apply": (
            "runtime.handle_pending_apply()" in workspace_source
        ),
        "runtime_registers_queue_module": (
            "inputs_page_modules.design_guide.primary_button_queue"
            in getattr(runtime, "_DESIGN_GUIDE_DEPENDENCY_MODULE_NAMES", ())
        ),
        "runtime_discovers_declared_binders": (
            "_bind_declared_runtime_dependencies(provider)" in runtime_source
        ),
        "runtime_configures_current_coordinator_provider": (
            "configure_design_guide_current_provider(" in runtime_source
        ),
        "binder_binds_all_declared_dependencies": binder_bound_all_dependencies,
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "module_function_lines": (
            module_node.end_lineno or module_node.lineno
        ) - module_node.lineno + 1,
        "dependency_count": len(dependency_names),
        "runtime_module": "inputs_page_modules.design_guide.primary_button_queue",
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_primary_button_queue_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_primary_button_queue_extraction_{stamp}.md"
    json_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Button Queue Extraction",
                "",
                f"Status: `{result['status']}`",
                "",
                "The verifier now checks the current typed runtime dependency provider. "
                "The removed app-contract bridge is not required.",
                "",
                f"- Extracted module function lines: `{result['module_function_lines']}`",
                f"- Declared dependency count: `{result['dependency_count']}`",
                "",
                "## Checks",
                "",
                *[
                    f"- `{name}`: `{'PASS' if passed else 'FAIL'}`"
                    for name, passed in checks.items()
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
