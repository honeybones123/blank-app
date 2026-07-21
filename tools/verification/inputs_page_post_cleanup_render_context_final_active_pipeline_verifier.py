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


def _jsonable(value):
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_render_context_final_active_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_render_context_final_active_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "refresh": "render_design_guide_post_active_failure_repair_shear_blocker_refresh",
        "exact": "render_design_guide_terminal_exact_blocker_render_reconciliation",
        "guard": "render_design_guide_terminal_green_unresolved_family_render_guard",
        "predicate": "render_design_guide_post_cleanup_terminal_render_predicate",
        "low": "render_design_guide_post_cleanup_zero_shear_low_family_cleanup",
        "target": "render_design_guide_active_failure_target_action_item_initialization",
        "keys": "render_design_guide_final_active_failure_key_render_context_setup",
        "acquire": "render_design_guide_final_active_repair_item_acquisition",
        "package": "render_design_guide_final_active_repair_presentation_packaging",
        "rebuild": "render_design_guide_final_active_failure_payload_rebuild",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def refresh(**kwargs):
        calls.append({"event": "refresh", "post_active": kwargs.get("post_active_failure_repair_render")})
        kwargs["guidance_debug"]["refresh"] = True
        kwargs["post_cleanup_render_audit"]["refresh"] = True
        return True

    def exact(**kwargs):
        calls.append({"event": "exact", "refresh": kwargs.get("post_cleanup_render_audit", {}).get("refresh")})
        return {"shear": {"reason": "exact"}}

    def guard(**kwargs):
        calls.append({"event": "guard", "exact": dict(kwargs.get("exact_for_terminal_render") or {})})
        return ["shear"]

    def predicate(**kwargs):
        calls.append(
            {
                "event": "predicate",
                "unresolved": list(kwargs.get("terminal_green_unresolved_for_render") or []),
            }
        )
        return True

    def low(**kwargs):
        calls.append({"event": "low"})
        return ["shear"]

    def target(**kwargs):
        calls.append({"event": "target"})
        items = [dict(kwargs.get("guidance_items")[0], target=True)]
        return items, {"active": True}

    def keys(**kwargs):
        calls.append({"event": "keys", "target": kwargs.get("guidance_items", [{}])[0].get("target")})
        return {"primary": True}, {"bending"}

    def acquire(**kwargs):
        calls.append({"event": "acquire", "keys": sorted(kwargs.get("final_active_fail_keys_for_render") or [])})
        return {"repair": True}

    def package(**kwargs):
        calls.append({"event": "package", "repair": kwargs.get("final_active_repair_item", {}).get("repair")})
        return (
            [{"packaged": True}],
            "packaged_terminal",
            "packaged_source",
            {"headline": "packaged"},
            {"plan": "packaged"},
            True,
        )

    def rebuild(**kwargs):
        calls.append({"event": "rebuild", "terminal": kwargs.get("terminal_state")})
        return (
            [{"rebuilt": True}],
            "rebuilt_terminal",
            "rebuilt_source",
            {"headline": "rebuilt"},
            {"plan": "rebuilt"},
            True,
        )

    try:
        inputs_page.render_design_guide_post_active_failure_repair_shear_blocker_refresh = refresh
        inputs_page.render_design_guide_terminal_exact_blocker_render_reconciliation = exact
        inputs_page.render_design_guide_terminal_green_unresolved_family_render_guard = guard
        inputs_page.render_design_guide_post_cleanup_terminal_render_predicate = predicate
        inputs_page.render_design_guide_post_cleanup_zero_shear_low_family_cleanup = low
        inputs_page.render_design_guide_active_failure_target_action_item_initialization = target
        inputs_page.render_design_guide_final_active_failure_key_render_context_setup = keys
        inputs_page.render_design_guide_final_active_repair_item_acquisition = acquire
        inputs_page.render_design_guide_final_active_repair_presentation_packaging = package
        inputs_page.render_design_guide_final_active_failure_payload_rebuild = rebuild

        result = inputs_page.render_design_guide_post_cleanup_render_context_and_final_active_pipeline(
            post_active_failure_repair_render=True,
            post_cleanup_render_audit={"audit": True},
            guidance_debug={"debug": True},
            guidance_disp_state={"state": True},
            dg_overview={"overview": True},
            guidance_items=[{"initial": True}],
            dg_presentation={"headline": "initial"},
            terminal_state="initial_terminal",
            terminal_state_source="initial_source",
            render_plan={"plan": "initial"},
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "refresh",
            "exact",
            "guard",
            "predicate",
            "low",
            "target",
            "keys",
            "acquire",
            "package",
            "rebuild",
        ],
        f"calls={calls}",
    )
    expect(
        "output_contract",
        result
        == (
            True,
            ["shear"],
            [{"rebuilt": True}],
            "rebuilt_terminal",
            "rebuilt_source",
            {"headline": "rebuilt"},
            {"plan": "rebuilt"},
            {"active": True},
            {"primary": True},
            {"bending"},
        ),
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_post_cleanup_render_context_and_final_active_pipeline")
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
        "render_design_guide_post_cleanup_render_context_and_final_active_pipeline" in legacy_calls,
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
        "result": _jsonable(result),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Render Context Final Active Pipeline Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted post-cleanup render context and final active-failure presentation coordinator.",
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
