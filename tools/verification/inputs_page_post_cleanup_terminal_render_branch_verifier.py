from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_node(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def _calls(function_node: ast.FunctionDef) -> set[str]:
    calls: set[str] = set()
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                calls.add(target.id)
            elif isinstance(target, ast.Attribute):
                calls.add(target.attr)
    return calls


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_terminal_render_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_terminal_render_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "selection": "render_design_guide_post_cleanup_terminal_residual_width_selection",
        "packaging": "render_design_guide_post_cleanup_terminal_residual_width_render_packaging",
        "fallback": "render_design_guide_post_cleanup_terminal_accepted_green_fallback",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}
    selection_results = [True, False]

    def selection(**kwargs):
        rendered = selection_results.pop(0)
        calls.append({"event": "selection", "rendered": rendered})
        return {"item": rendered}, {"contract": rendered}, {"b": 350}, {"state": True}, rendered

    def packaging(**kwargs):
        calls.append(
            {
                "event": "packaging",
                "item": kwargs.get("post_cleanup_residual_width_item"),
                "updates": kwargs.get("post_cleanup_residual_width_updates"),
            }
        )
        kwargs["stage"]("packaging_stage")
        return {"packaged": True}

    def fallback(**kwargs):
        calls.append(
            {
                "event": "fallback",
                "audit": kwargs.get("post_cleanup_render_audit"),
            }
        )
        kwargs["stage"]("fallback_stage")

    stages: list[str] = []

    def stage(label: str) -> None:
        stages.append(label)

    try:
        inputs_page.render_design_guide_post_cleanup_terminal_residual_width_selection = selection
        inputs_page.render_design_guide_post_cleanup_terminal_residual_width_render_packaging = packaging
        inputs_page.render_design_guide_post_cleanup_terminal_accepted_green_fallback = fallback

        kwargs = {
            "guidance_debug": {"debug": True},
            "dg_overview": {"overview": True},
            "guidance_disp_state": {"state": True},
            "post_cleanup_render_audit": {"audit": True},
            "inputs_render_audit": {"render": True},
            "terminal_state": "optimal",
            "dg_presentation": {"headline": "ok"},
            "stage": stage,
        }
        inputs_page.render_design_guide_post_cleanup_terminal_render_branch(**kwargs)
        inputs_page.render_design_guide_post_cleanup_terminal_render_branch(**kwargs)
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expect(
        "call_order",
        [call["event"] for call in calls]
        == ["selection", "packaging", "selection", "fallback"],
        f"calls={calls}",
    )
    expect("stage_order", stages == ["packaging_stage", "fallback_stage"], f"stages={stages}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_post_cleanup_terminal_render_branch")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = set(names.values())
    new_calls = _calls(new_node)
    legacy_calls = _calls(legacy_node)
    expect(
        "new_pipeline_owns_moved_calls",
        moved_calls <= new_calls,
        f"missing={sorted(moved_calls - new_calls)}",
    )
    expect(
        "legacy_delegates_once",
        "render_design_guide_post_cleanup_terminal_render_branch" in legacy_calls,
        "missing branch call",
    )
    expect(
        "legacy_no_longer_directly_calls_moved_helpers",
        not (moved_calls & legacy_calls),
        f"still_direct={sorted(moved_calls & legacy_calls)}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "failures": failures,
        "calls": calls,
        "stages": stages,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Terminal Render Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted post-cleanup terminal render branch for residual-width and accepted-green paths.",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({**payload, "json": str(json_path), "report": str(report_path)}, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
