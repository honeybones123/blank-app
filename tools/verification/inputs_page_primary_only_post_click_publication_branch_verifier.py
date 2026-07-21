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
    json_path = ARTIFACT_DIR / f"inputs_page_primary_only_post_click_publication_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_only_post_click_publication_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "apply_context": "render_design_guide_primary_same_flow_cleanup_apply_context",
        "button_enabled": "_design_guide_button_contract_enabled",
        "required": "render_design_guide_primary_low_bending_exact_blocker_required",
        "audit": "render_design_guide_primary_low_bending_post_click_audit_setup",
        "resolution": "_post_click_low_bending_resolution_item",
        "mode": "_design_mode_config",
        "goal": "_design_optimisation_goal",
        "adapter": "_stamp_final_publication_post_click_low_bending_resolution_result_item_adapter",
        "replacement": "render_design_guide_primary_low_bending_resolution_replacement_handoff",
        "combined": "render_design_guide_primary_combined_low_util_exact_blocker_presentation_handoff",
        "publication": "render_design_guide_primary_items_after_publication_contract",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def apply_context(**kwargs):
        calls.append({"event": "apply_context"})
        return {"route": True}, True

    def required(**kwargs):
        calls.append({"event": "required", "expected": kwargs.get("primary_post_click_expected_util")})
        return True

    def audit(**kwargs):
        calls.append({"event": "audit", "title": kwargs.get("primary_post_click_item", {}).get("title_main")})
        return {"utils": {"bending": 0.5}}, {"audit": True}

    def resolution(*args, **kwargs):
        calls.append({"event": "resolution"})
        return {"title_main": "Low bending resolution"}

    def adapter(**kwargs):
        calls.append({"event": "adapter"})
        return {
            "adapted_item": {"title_main": "Adapted low bending"},
            "adapted_item_hash": "adapted-hash",
            "proof_hash": "proof-hash",
        }

    def replacement(**kwargs):
        calls.append({"event": "replacement", "title": kwargs.get("primary_bending_resolution", {}).get("title_main")})
        item = dict(kwargs.get("primary_bending_resolution") or {})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["replacement"] = True
        return [item], [item], {"render_primary_only": True, "visible_guidance_items": [item]}, {"headline": item.get("title_main")}, debug

    def combined(**kwargs):
        calls.append({"event": "combined"})
        item = dict(kwargs.get("primary_post_click_item") or {})
        item["combined"] = True
        return (
            item,
            kwargs.get("primary_render_items"),
            kwargs.get("guidance_items"),
            kwargs.get("render_plan"),
            kwargs.get("dg_presentation"),
            kwargs.get("guidance_debug"),
            {"combined": 0.9},
        )

    def publication(**kwargs):
        calls.append({"event": "publication"})
        return (
            kwargs.get("primary_render_items"),
            kwargs.get("guidance_items"),
            kwargs.get("guidance_debug"),
            kwargs.get("render_plan"),
            kwargs.get("dg_presentation"),
            True,
        )

    try:
        inputs_page.render_design_guide_primary_same_flow_cleanup_apply_context = apply_context
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))
        inputs_page.render_design_guide_primary_low_bending_exact_blocker_required = required
        inputs_page.render_design_guide_primary_low_bending_post_click_audit_setup = audit
        inputs_page._post_click_low_bending_resolution_item = resolution
        inputs_page._design_mode_config = lambda goal: {"target_low": 0.75, "target_high": 1.0}
        inputs_page._design_optimisation_goal = lambda state: "balanced"
        inputs_page._stamp_final_publication_post_click_low_bending_resolution_result_item_adapter = adapter
        inputs_page.render_design_guide_primary_low_bending_resolution_replacement_handoff = replacement
        inputs_page.render_design_guide_primary_combined_low_util_exact_blocker_presentation_handoff = combined
        inputs_page.render_design_guide_primary_items_after_publication_contract = publication

        result = inputs_page.render_design_guide_primary_only_post_click_publication_branch(
            primary_render_items=[
                {
                    "title_main": "Primary",
                    "button_contract": {"enabled": True, "expected_util": 0.5},
                }
            ],
            guidance_items=[{"title_main": "Primary"}],
            guidance_debug={"debug": True},
            render_plan={"render_primary_only": True},
            dg_presentation={"headline": "Primary"},
            primary_guidance_disp_state_for_render={"state": True},
            dg_overview={"overview": True},
            post_cleanup_render_audit={"cleanup": True},
            final_visible_resolution={"final": True},
            visible_utils_for_exact_blockers={"before": 0.1},
            inputs_render_audit={"audit": True},
            restamp_exact_blocker_current_utils_fn=lambda source: source,
            stage_fn=lambda label: None,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expected_item = {"title_main": "Adapted low bending"}
    expected_debug = {
        "debug": True,
        "final_publication_post_click_low_bending_primary_render_binding_cutover_used": True,
        "final_publication_post_click_low_bending_primary_render_binding_cutover_source": "FinalDesignGuidePublication.post_click_low_bending_resolution_result_item_adapter",
        "final_publication_post_click_low_bending_primary_render_binding_cutover_hash": "adapted-hash",
        "final_publication_post_click_low_bending_primary_render_binding_cutover_proof_hash": "proof-hash",
        "final_publication_post_click_low_bending_primary_render_binding_cutover_product_behavior_changed": False,
        "replacement": True,
    }
    expect(
        "call_order",
        [call["event"] for call in calls]
        == ["apply_context", "required", "audit", "resolution", "adapter", "replacement", "combined", "publication"],
        f"calls={calls}",
    )
    expect(
        "output_contract",
        result
        == (
            [expected_item],
            [expected_item],
            expected_debug,
            {"render_primary_only": True, "visible_guidance_items": [expected_item]},
            {"headline": "Adapted low bending"},
            {"combined": 0.9},
            True,
        ),
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_primary_only_post_click_publication_branch")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = {
        "render_design_guide_primary_low_bending_exact_blocker_required",
        "render_design_guide_primary_low_bending_post_click_audit_setup",
        "render_design_guide_primary_low_bending_resolution_replacement_handoff",
        "render_design_guide_primary_combined_low_util_exact_blocker_presentation_handoff",
        "render_design_guide_primary_items_after_publication_contract",
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
        "render_design_guide_primary_only_post_click_publication_branch" in legacy_calls,
        "missing primary post-click branch call",
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
                "# Inputs Page Primary Only Post Click Publication Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted primary-only post-click low-bending, combined low-util, and publication-contract coordinator.",
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
