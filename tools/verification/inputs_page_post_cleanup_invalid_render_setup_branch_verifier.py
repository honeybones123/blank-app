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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_invalid_render_setup_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_invalid_render_setup_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "initial": "render_design_guide_post_cleanup_invalid_render_initial_blocker_setup",
        "next": "render_design_guide_post_cleanup_invalid_render_next_shear_action_setup",
        "intent_gate": "render_design_guide_post_cleanup_intent_contract_gate_setup",
        "intent_preferred": "render_design_guide_post_cleanup_intent_action_preferred_setup",
        "reset": "render_design_guide_post_cleanup_invalid_render_shear_exact_blocker_reset",
        "required": "render_design_guide_post_cleanup_invalid_render_shear_blocker_required",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def initial(**kwargs):
        calls.append({"event": "initial"})
        return (
            False,
            0.7,
            {"truth": "initial"},
            "initial_reason",
            {"item": "initial"},
            {"shear": "exact"},
            True,
            True,
        )

    def next_action(**kwargs):
        calls.append({"event": "next", "item": kwargs.get("blocked_render_item")})
        return {"item": "next"}

    def intent_gate(**kwargs):
        calls.append({"event": "intent_gate"})
        return (
            {"contract": True},
            {"row": True},
            "shear",
            ["shear"],
            False,
            False,
        )

    def intent_preferred(**kwargs):
        calls.append(
            {
                "event": "intent_preferred",
                "item": kwargs.get("blocked_render_item"),
                "family": kwargs.get("intent_family"),
            }
        )
        return (
            {"item": "preferred"},
            True,
            "preferred_reason",
            {"enabled": True},
            {"truth": "preferred"},
        )

    def reset(**kwargs):
        calls.append({"event": "reset", "item": kwargs.get("blocked_render_item")})
        return {"item": "reset"}

    def required(**kwargs):
        calls.append({"event": "required", "item": kwargs.get("blocked_render_item")})
        return True

    try:
        inputs_page.render_design_guide_post_cleanup_invalid_render_initial_blocker_setup = initial
        inputs_page.render_design_guide_post_cleanup_invalid_render_next_shear_action_setup = next_action
        inputs_page.render_design_guide_post_cleanup_intent_contract_gate_setup = intent_gate
        inputs_page.render_design_guide_post_cleanup_intent_action_preferred_setup = intent_preferred
        inputs_page.render_design_guide_post_cleanup_invalid_render_shear_exact_blocker_reset = reset
        inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_required = required

        result = inputs_page.render_design_guide_post_cleanup_invalid_render_setup_branch(
            guidance_debug={"debug": True},
            guidance_disp_state={"state": True},
            dg_overview={"overview": True},
            post_cleanup_render_audit={"audit": True},
            post_cleanup_low_families=["shear"],
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expect(
        "call_order",
        [call["event"] for call in calls]
        == ["initial", "next", "intent_gate", "intent_preferred", "reset", "required"],
        f"calls={calls}",
    )
    expect(
        "output_contract",
        result
        == (
            True,
            0.7,
            {"truth": "preferred"},
            "preferred_reason",
            {"item": "reset"},
            {"shear": "exact"},
            True,
            True,
            None,
            True,
        ),
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_post_cleanup_invalid_render_setup_branch")
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
        "render_design_guide_post_cleanup_invalid_render_setup_branch" in legacy_calls,
        "missing setup branch call",
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
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Setup Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted invalid-render setup branch before deeper shear-blocker packaging.",
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
