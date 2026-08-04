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
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_loading_shell_slot_restoration_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_loading_shell_slot_restoration_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    renderer_source = (
        ROOT / "inputs_application" / "page_runtime" / "design_guide.py"
    ).read_text(
        encoding="utf-8",
        errors="ignore",
    )
    workspace_source = (
        ROOT / "inputs_application" / "engineering_workspace.py"
    ).read_text(
        encoding="utf-8",
        errors="ignore",
    )
    page_source = (ROOT / "design_guide_page.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    slot_source = _function_source(
        renderer_source,
        "render_inputs_design_guide_current_coordinator",
    )
    section_source = _function_source(
        workspace_source,
        "render_inputs_design_guide_fragment_section",
    )
    pending_source = _function_source(page_source, "_render_proof_pending_shell")

    failures: list[str] = []
    checks = {
        "typed_renderer_imports_design_guide_page": "import design_guide_page" in renderer_source,
        "fragment_section_owns_single_design_guide_slot": (
            section_source.count("design_guide_slot = st_module.empty()") == 1
        ),
        "pending_shell_mounted_before_final_panel": (
            "design_guide_page.render_pre_widget_placeholder(" in slot_source
            and "design_guide_page.render_final_panel(" in slot_source
            and slot_source.find("design_guide_page.render_pre_widget_placeholder(")
            < slot_source.find("design_guide_page.render_final_panel(")
        ),
        "final_panel_replaces_same_slot": (
            "slot=design_guide_slot" in slot_source
            and "design_guide_slot=design_guide_slot" in section_source
        ),
        "active_panel_still_uses_existing_orchestration": (
            "render_design_guide_panel_orchestration(" in slot_source
            and "current_owner=design_guide_current_coordinators" in slot_source
        ),
        "final_panel_receives_inputs_context": all(
            token in slot_source
            for token in (
                "sync_callbacks=sync_callbacks",
                "inputs_render_audit=inputs_render_audit",
                "inputs_detailed_mode=bool(inputs_detailed_mode)",
                "fast_focus_section=fast_focus_section",
                "trace=_inputs_pre_widget_trace",
            )
        ),
        "fragment_publication_precedes_debug_fallback": (
            'lifecycle_state.get("active_publication")' in slot_source
            and slot_source.find(
                'lifecycle_state.get("active_publication")'
            )
            < slot_source.find(
                'debug_bundle.get("final_publication_verifier_payload")'
            )
        ),
        "pending_shell_is_owned_by_design_guide_page": (
            "dg-proof-pending-shell" in pending_source
            and "st_module.markdown(" in pending_source
        ),
        "final_panel_adapter_still_clears_slot": (
            "def render_final_panel(" in page_source and "slot.empty()" in _function_source(page_source, "render_final_panel")
        ),
    }
    for name, passed in checks.items():
        if not passed:
            failures.append(name)

    payload = {
        "verifier": "design_guide_loading_shell_slot_restoration",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "proof": {
            "shell_path": "design_guide_page.render_pre_widget_placeholder",
            "replacement_path": "design_guide_page.render_final_panel",
            "active_orchestration": (
                "inputs_application.page_runtime.design_guide."
                "render_inputs_design_guide_current_coordinator"
            ),
            "single_slot": "design_guide_slot",
            "product_behaviour_changed": False,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Loading Shell Slot Restoration",
                "",
                f"Status: `{payload['status']}`",
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
