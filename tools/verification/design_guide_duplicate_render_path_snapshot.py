"""Prove the Design Guide has one authoritative card render path.

The pre-widget path is allowed to render only a transient loading shell. The
final coordinator owns the publication-backed card and CTA rendering.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _current_route_source() -> tuple[str, str]:
    """Read the current extracted route coordinator, not the retired root path."""
    candidates = (
        ROOT / "inputs_application" / "page_runtime" / "design_guide.py",
        ROOT / "inputs_page_route_coordinators.py",
    )
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore"), str(path)
    return "", str(candidates[0])


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_duplicate_render_path_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_duplicate_render_path_snapshot_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    page_source = (ROOT / "design_guide_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source, route_path = _current_route_source()
    pre_source = _function_source(page_source, "render_pre_widget_placeholder")
    final_source = _function_source(page_source, "render_final_panel")

    checks = {
        "single_pre_widget_placeholder_definition": page_source.count(
            "def render_pre_widget_placeholder"
        ) == 1,
        "pre_widget_has_no_proof_backed_card_renderer": all(
            token not in pre_source
            for token in ("_proof_backed_placeholder_card", "_render_proof_backed_card", "data-testid=\"design-guide-card\"")
        ),
        "pre_widget_retains_loading_shell": "_render_proof_pending_shell" in pre_source,
        "final_panel_clears_same_slot": "slot.empty()" in final_source,
        "fragment_is_mounted_inside_stable_slot": (
            "with slot.container():" in final_source
            and "fragment(_render_panel_content)()" in final_source
        ),
        "nested_workspace_fragment_is_disabled": (
            "_inputs_engineering_workspace_fragment_mode" in final_source
            and "parent_fragment_active" in final_source
            and "not parent_fragment_active" in final_source
            and '"outer_fragment" if parent_fragment_active' in final_source
        ),
        "parent_fragment_renders_without_nested_slot_container": (
            "if parent_fragment_active:" in final_source
            and "_render_panel_content()" in final_source
            and '"outer_fragment"' in final_source
        ),
        "cta_renderer_has_render_epoch_guard": (
            "_design_guide_render_epoch" in (ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py").read_text(encoding="utf-8", errors="ignore")
            and "_design_guide_cta_rendered_epoch" in (ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py").read_text(encoding="utf-8", errors="ignore")
        ),
        "route_disables_duplicate_pre_heading": "render_heading=False" in route_source,
        "final_card_remains_current_coordinator_owned": (
            "render_design_guide_panel_orchestration(" in route_source
            and "design_guide_page.render_final_panel(" in route_source
            and "render_panel=render_panel" in route_source
            and "fragment_name=\"design_guide\"" not in route_source
        ),
        "removed_pre_card_helpers_have_no_references": all(
            token not in page_source
            for token in ("_proof_backed_placeholder_card", "_render_proof_backed_card")
        ),
        "cta_rendering_not_moved_to_shell": "render_design_guide_component_cta" not in pre_source,
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "verifier": "design_guide_duplicate_render_path_snapshot",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "ownership": {
            "pre_widget": "transient loading shell only",
            "final_panel": "authoritative publication-backed card and CTA",
            "deleted": [
                "pre-widget proof-backed duplicate card renderer",
                "unused pre-widget proof-card builder",
            ],
        },
        "product_behaviour_changed": False,
        "route_source": route_path,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Duplicate Render Path Snapshot",
                "",
                f"Status: `{payload['status']}`",
                "",
                "The pre-widget slot now renders only the transient loading shell. The final panel remains the single publication-backed card and CTA path.",
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
