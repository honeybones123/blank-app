from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_acceptance_post_apply_terminal_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_acceptance_post_apply_terminal_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "best": "render_design_guide_post_cleanup_best_safe_terminal",
        "green": "render_design_guide_post_active_repair_green_acceptance",
        "route": "render_design_guide_post_apply_terminal_route_audit_setup",
        "acceptable": "_overview_required_checks_acceptable",
        "accepted_item": "_post_active_repair_target_accepted_item",
        "mode": "_design_mode_config",
        "goal": "_design_optimisation_goal",
        "parse": "_parse_util_value",
        "residual": "render_design_guide_post_apply_residual_width_cleanup_selection",
        "packaging": "render_design_guide_post_apply_required_checks_terminal_packaging",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}
    original_st = inputs_page.st

    def best(**kwargs):
        calls.append({"event": "best", "terminal": kwargs.get("terminal_state")})
        return (
            True,
            [{"best": True}],
            {"plan": "best"},
            {"headline": "best"},
            "best_terminal",
            "best_source",
        )

    def green(**kwargs):
        calls.append({"event": "green", "post_active": kwargs.get("post_active_failure_repair_render")})
        audit = dict(kwargs.get("post_cleanup_render_audit") or {})
        audit["green"] = True
        return (
            False,
            False,
            audit,
            ["shear"],
            [{"green": True}],
            {"plan": "green"},
            {"headline": "green"},
            "green_terminal",
            "green_source",
        )

    def route(**kwargs):
        calls.append({"event": "route", "route": kwargs.get("post_apply_terminal_route", {}).get("route")})
        return (
            {"any_fail": False, "worst_util": 0.82, "all_key_pass": True},
            {"route_overview": True},
            True,
            {"audit": True},
        )

    def acceptable(overview):
        calls.append({"event": "acceptable", "worst": dict(overview or {}).get("worst_util")})
        return True

    def accepted_item(*args, **kwargs):
        calls.append({"event": "accepted_item", "allow": kwargs.get("allow_required_checks_terminal")})
        return {"accepted": True}

    def goal(state):
        calls.append({"event": "goal"})
        return "balanced"

    def mode(goal_name):
        calls.append({"event": "mode", "goal": goal_name})
        return {"mode": goal_name}

    def parse(value):
        calls.append({"event": "parse", "value": value})
        return float(value)

    def residual(**kwargs):
        calls.append(
            {
                "event": "residual",
                "in_target": kwargs.get("post_apply_terminal_in_target_band"),
            }
        )
        return {"residual": True}, {"enabled": True}, {"b": 350}, {"state": True}, True

    def packaging(**kwargs):
        calls.append(
            {
                "event": "packaging",
                "residual": kwargs.get("post_apply_terminal_is_residual_width_cleanup"),
            }
        )
        return (
            [{"packaged": True}],
            {"plan": "packaged"},
            {"headline": "packaged"},
            "packaged_terminal",
            "packaged_source",
        )

    try:
        inputs_page.render_design_guide_post_cleanup_best_safe_terminal = best
        inputs_page.render_design_guide_post_active_repair_green_acceptance = green
        inputs_page.render_design_guide_post_apply_terminal_route_audit_setup = route
        inputs_page._overview_required_checks_acceptable = acceptable
        inputs_page._post_active_repair_target_accepted_item = accepted_item
        inputs_page._design_mode_config = mode
        inputs_page._design_optimisation_goal = goal
        inputs_page._parse_util_value = parse
        inputs_page.render_design_guide_post_apply_residual_width_cleanup_selection = residual
        inputs_page.render_design_guide_post_apply_required_checks_terminal_packaging = packaging
        inputs_page.st = SimpleNamespace(
            session_state={inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY: {"route": True}}
        )

        result = inputs_page.render_design_guide_post_cleanup_acceptance_and_post_apply_terminal_pipeline(
            final_visible_resolution={"item": {"id": "visible"}},
            final_visible_item={"id": "visible"},
            post_cleanup_render_audit={"audit": True},
            post_active_failure_repair_render=True,
            post_cleanup_terminal_render=True,
            post_cleanup_low_families=["bending"],
            dg_overview={"overview": True},
            dg_presentation={"headline": "initial"},
            guidance_debug={"debug": True},
            guidance_disp_state={"state": True},
            guidance_items=[{"initial": True}],
            render_plan={"plan": "initial"},
            terminal_state="initial_terminal",
            terminal_state_source="initial_source",
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])
        inputs_page.st = original_st

    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "best",
            "green",
            "route",
            "acceptable",
            "goal",
            "mode",
            "accepted_item",
            "parse",
            "residual",
            "packaging",
        ],
        f"calls={calls}",
    )
    expect(
        "output_contract",
        result
        == (
            True,
            [{"packaged": True}],
            {"plan": "packaged"},
            {"headline": "packaged"},
            "packaged_terminal",
            "packaged_source",
            False,
            {"audit": True, "green": True},
            ["shear"],
        ),
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_post_cleanup_acceptance_and_post_apply_terminal_pipeline")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = {
        "render_design_guide_post_cleanup_best_safe_terminal",
        "render_design_guide_post_active_repair_green_acceptance",
        "render_design_guide_post_apply_terminal_route_audit_setup",
        "render_design_guide_post_apply_residual_width_cleanup_selection",
        "render_design_guide_post_apply_required_checks_terminal_packaging",
    }
    new_calls = _calls(new_node)
    legacy_calls = _calls(legacy_node)
    expect(
        "new_pipeline_owns_moved_calls",
        moved_calls <= new_calls,
        f"missing={sorted(moved_calls - new_calls)}",
    )
    expect(
        "legacy_delegates_once",
        "render_design_guide_post_cleanup_acceptance_and_post_apply_terminal_pipeline" in legacy_calls,
        "missing pipeline call",
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
                "# Inputs Page Post Cleanup Acceptance Post Apply Terminal Pipeline Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted post-cleanup best-safe, post-active green, and post-apply required-check terminal packaging coordinator.",
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
