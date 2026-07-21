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
    json_path = ARTIFACT_DIR / f"inputs_page_primary_only_late_shear_action_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_only_late_shear_action_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "st": "st",
        "state_snapshot": "_guidance_state_snapshot",
        "shared_snapshot": "_shared_state_snapshot",
        "zero_signal": "_zero_shear_ligature_cleanup_contract_signal",
        "skip_probe": "_skip_bending_fail_post_publication_probe",
        "residual_blocker": "_post_active_repair_residual_shear_exact_blocker",
        "applied_blocker": "_post_click_applied_residual_shear_exact_blocker",
        "failures": "_overview_active_failure_keys",
        "target_cleanup": "_shear_low_util_target_cleanup_item",
        "intent": "_build_final_design_guide_late_render_shear_action_intent_contract_result",
        "handoff": "render_design_guide_primary_only_shear_action_handoff",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def skip_probe(*args, **kwargs):
        calls.append({"event": "skip_probe"})
        return False

    def residual_blocker(*args, **kwargs):
        calls.append({"event": "residual_blocker"})
        return {"residual": True}

    def applied_blocker(*args, **kwargs):
        calls.append({"event": "applied_blocker"})
        return None

    def target_cleanup(*args, **kwargs):
        calls.append({"event": "target_cleanup", "threshold": kwargs.get("threshold")})
        return {
            "title_main": "Late shear cleanup",
            "button_contract": {"enabled": True, "family": "shear"},
            "candidate_search_evidence": {"late": True},
        }

    def intent(**kwargs):
        calls.append({"event": "intent", "failures": kwargs.get("active_strength_failures")})
        return {"result": {}, "proof_hash": "proof"}

    def handoff(**kwargs):
        calls.append({"event": "handoff", "title": kwargs.get("render_shear_action", {}).get("title_main")})
        action = dict(kwargs.get("render_shear_action") or {})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["handoff"] = True
        return (
            action,
            [action],
            [action],
            dict(kwargs.get("render_current_state_for_shear") or {}),
            {"headline": action.get("title_main")},
            debug,
        )

    try:
        inputs_page.st = SimpleNamespace(session_state={})
        inputs_page._guidance_state_snapshot = lambda state: dict(state)
        inputs_page._shared_state_snapshot = lambda: {
            "uls_Vstar": 100.0,
            "load_Vstar_proxy": 100.0,
        }
        inputs_page._zero_shear_ligature_cleanup_contract_signal = lambda state: False
        inputs_page._skip_bending_fail_post_publication_probe = skip_probe
        inputs_page._post_active_repair_residual_shear_exact_blocker = residual_blocker
        inputs_page._post_click_applied_residual_shear_exact_blocker = applied_blocker
        inputs_page._overview_active_failure_keys = lambda overview: set()
        inputs_page._shear_low_util_target_cleanup_item = target_cleanup
        inputs_page._build_final_design_guide_late_render_shear_action_intent_contract_result = intent
        inputs_page.render_design_guide_primary_only_shear_action_handoff = handoff

        result = inputs_page.render_design_guide_primary_only_late_shear_action_branch(
            render_plan={"visible_guidance_items": [{"title_main": "Original"}]},
            guidance_items=[{"title_main": "Original"}],
            guidance_debug={"overview": {"utils": {"shear": 0.5, "bending": 0.9}, "any_fail": False}},
            guidance_disp_state={"state": True},
            dg_overview={"utils": {"shear": 0.5, "bending": 0.9}, "any_fail": False},
            dg_presentation={"headline": "old"},
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expected_action = {
        "title_main": "Late shear cleanup",
        "button_contract": {"enabled": True, "family": "shear"},
        "candidate_search_evidence": {"late": True},
    }
    expect(
        "call_order",
        [call["event"] for call in calls]
        == ["skip_probe", "residual_blocker", "applied_blocker", "target_cleanup", "intent", "handoff"],
        f"calls={calls}",
    )
    expect(
        "output_contract",
        result
        == (
            [expected_action],
            [expected_action],
            {"uls_Vstar": 100.0, "load_Vstar_proxy": 100.0},
            {"headline": "Late shear cleanup"},
            {"overview": {"utils": {"shear": 0.5, "bending": 0.9}, "any_fail": False}, "handoff": True},
        ),
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_primary_only_late_shear_action_branch")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = {
        "_build_final_design_guide_late_render_shear_action_intent_contract_result",
        "render_design_guide_primary_only_shear_action_handoff",
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
        "render_design_guide_primary_only_late_shear_action_branch" in legacy_calls,
        "missing late shear branch call",
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
                "# Inputs Page Primary Only Late Shear Action Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted primary-only late shear recovery coordinator before primary post-click handling.",
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
