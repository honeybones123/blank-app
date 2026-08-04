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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_green_render_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_green_render_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "state_snapshot": "_guidance_state_snapshot",
        "shared_snapshot": "_shared_state_snapshot",
        "zero_signal": "_zero_shear_ligature_cleanup_contract_signal",
        "zero_clear": "render_design_guide_terminal_zero_shear_stale_blocker_clear",
        "target_cleanup": "_shear_low_util_target_cleanup_item",
        "handoff": "render_design_guide_terminal_low_shear_action_handoff",
        "card": "render_design_guide_terminal_card",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def zero_clear(**kwargs):
        calls.append({"event": "zero_clear", "accepted": kwargs.get("terminal_zero_shear_demand_accepted")})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["zero_clear"] = True
        return debug

    def target_cleanup(*args, **kwargs):
        calls.append({"event": "target_cleanup", "threshold": kwargs.get("threshold")})
        return {
            "title_main": "Terminal low shear cleanup",
            "button_contract": {"enabled": True, "family": "shear"},
            "candidate_search_evidence": {"terminal": True},
        }

    def handoff(**kwargs):
        calls.append({"event": "handoff", "title": kwargs.get("terminal_low_shear_action", {}).get("title_main")})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["handoff"] = True
        kwargs["stage_fn"]("handoff_stage")
        return debug, {"headline": "Terminal low shear cleanup"}, "optimal"

    def card(**kwargs):
        calls.append(
            {
                "event": "card",
                "terminal_state": kwargs.get("terminal_state"),
                "shear_util": kwargs.get("terminal_shear_util"),
                "zero": kwargs.get("terminal_zero_shear_demand_accepted"),
            }
        )
        kwargs["stage_fn"]("card_stage")

    stages: list[str] = []

    try:
        inputs_page._guidance_state_snapshot = lambda state: dict(state)
        inputs_page._shared_state_snapshot = lambda: {
            "uls_Vstar": 100.0,
            "load_Vstar_proxy": 100.0,
        }
        inputs_page._zero_shear_ligature_cleanup_contract_signal = lambda state: False
        inputs_page.render_design_guide_terminal_zero_shear_stale_blocker_clear = zero_clear
        inputs_page._shear_low_util_target_cleanup_item = target_cleanup
        inputs_page.render_design_guide_terminal_low_shear_action_handoff = handoff
        inputs_page.render_design_guide_terminal_card = card

        result = inputs_page.render_design_guide_terminal_green_render_branch(
            terminal_state="optimal",
            dg_presentation={"headline": "old"},
            dg_overview={"utils": {"shear": 0.5, "bending": 0.9}, "any_fail": False},
            guidance_debug={"overview": {"utils": {"shear": 0.5, "bending": 0.9}, "any_fail": False}},
            guidance_disp_state={"state": True},
            inputs_render_audit={"audit": True},
            stage_fn=stages.append,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expect(
        "call_order",
        [call["event"] for call in calls] == ["zero_clear", "target_cleanup", "handoff", "card"],
        f"calls={calls}",
    )
    expect("stage_order", stages == ["handoff_stage", "card_stage"], f"stages={stages}")
    expect(
        "output_contract",
        result == (
            {
                "overview": {"utils": {"shear": 0.5, "bending": 0.9}, "any_fail": False},
                "zero_clear": True,
                "handoff": True,
            },
            {"headline": "Terminal low shear cleanup"},
            "optimal",
        ),
        f"result={result}",
    )
    expect(
        "card_received_expected_context",
        calls[-1].get("terminal_state") == "optimal"
        and calls[-1].get("shear_util") == 0.5
        and calls[-1].get("zero") is False,
        f"card={calls[-1] if calls else None}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_terminal_green_render_branch")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = {
        "render_design_guide_terminal_zero_shear_stale_blocker_clear",
        "render_design_guide_terminal_low_shear_action_handoff",
        "render_design_guide_terminal_card",
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
        "render_design_guide_terminal_green_render_branch" in legacy_calls,
        "missing terminal green branch call",
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
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Green Render Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted terminal-green render branch, including zero-shear clearing, low-shear handoff, and terminal card render.",
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
