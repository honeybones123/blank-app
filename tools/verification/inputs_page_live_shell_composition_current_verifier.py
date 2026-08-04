from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    matches: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            matches.append(
                (node.end_lineno - node.lineno + 1, node.lineno, node.end_lineno)
            )
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def _ordered(source: str, tokens: list[str]) -> bool:
    positions = [source.find(token) for token in tokens]
    return all(position >= 0 for position in positions) and positions == sorted(
        positions
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = (
        ARTIFACT_DIR
        / f"inputs_page_live_shell_composition_current_{timestamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"inputs_page_live_shell_composition_current_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_path = ROOT / "inputs_page.py"
    workspace_path = ROOT / "inputs_application" / "engineering_workspace.py"
    runtime_path = ROOT / "inputs_application" / "page_runtime" / "__init__.py"
    legacy_paths = (
        ROOT / "inputs_page_route_coordinators.py",
        ROOT / "inputs_page_app_contract_bridge.py",
    )
    shell_source = shell_path.read_text(encoding="utf-8", errors="ignore")
    workspace_source = workspace_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )
    runtime_source = runtime_path.read_text(encoding="utf-8", errors="ignore")
    render_inputs_source, render_inputs_size = _function_source(
        shell_source,
        "render_inputs_page",
    )
    render_workspace_source, render_workspace_size = _function_source(
        workspace_source,
        "render_engineering_workspace",
    )

    checks = {
        "legacy_bridge_files_absent": all(
            not path.exists() for path in legacy_paths
        ),
        "shell_builds_typed_page_runtime": (
            "build_inputs_page_runtime()" in shell_source
        ),
        "shell_builds_typed_workspace_runtime": (
            "build_engineering_workspace_runtime(" in shell_source
        ),
        "shell_calls_one_typed_engineering_workspace": (
            render_inputs_source.count(
                "_render_engineering_workspace(page_context=page_context)"
            )
            == 1
            and 'fragment_name="engineering_workspace"'
            not in render_inputs_source
        ),
        "shell_route_order_is_stable": _ordered(
            render_inputs_source,
            [
                "_INPUTS_PAGE_RUNTIME.render_page_setup(",
                "_render_engineering_workspace(page_context=page_context)",
                "_INPUTS_PAGE_RUNTIME.render_tail(",
            ],
        ),
        "shell_does_not_render_sections_directly": all(
            token not in render_inputs_source
            for token in (
                "render_inputs_summary_fragment_section(",
                "render_inputs_calculation_fragment_section(",
                "render_inputs_controls_fragment_section(",
                "render_inputs_design_guide_fragment_section(",
                "render_inputs_widget_fragment_section(",
            )
        ),
        "workspace_has_one_authoritative_transaction": (
            render_workspace_source.count(
                "prepare_engineering_workspace_transaction("
            )
            == 1
        ),
        "workspace_section_order_preserves_ui": _ordered(
            render_workspace_source,
            [
                "prepare_engineering_workspace_transaction(",
                "render_inputs_summary_fragment_section",
                "render_inputs_calculation_fragment_section",
                "render_inputs_controls_fragment_section(",
                "render_inputs_design_guide_fragment_section",
                "render_inputs_widget_fragment_section",
            ],
        ),
        "workspace_has_sibling_section_fragments": all(
            token in render_workspace_source
            for token in (
                'fragment_name="summary"',
                'fragment_name="calculation"',
                'fragment_name="design_guide"',
                'fragment_name="input"',
            )
        )
        and render_workspace_source.count("run_inputs_fragment(") == 4,
        "design_guide_remains_above_widget_inputs": (
            render_workspace_source.find(
                "render_inputs_design_guide_fragment_section"
            )
            < render_workspace_source.find(
                "render_inputs_widget_fragment_section"
            )
        ),
        "typed_runtime_has_explicit_concern_ports": all(
            token in runtime_source
            for token in (
                "render_summary_pipeline: PageCallable",
                "render_calculation: PageCallable",
                "render_design_guide: PageCallable",
                "render_widget_sections: PageCallable",
                "refresh_authoritative_result: PageCallable",
            )
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "verifier": "inputs_page_live_shell_composition_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "shell_render_inputs_page_size": render_inputs_size,
        "engineering_workspace_size": render_workspace_size,
        "certified_boundary": (
            "thin shell plus one typed transaction and sibling Summary, "
            "Calculation, Design Guide, and Input fragments"
        ),
    }
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Live Shell Composition Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Certified Boundary",
                "",
                payload["certified_boundary"],
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{value}`" for name, value in checks.items()),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
