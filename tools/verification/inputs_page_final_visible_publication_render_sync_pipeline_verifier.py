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
    json_path = ARTIFACT_DIR / f"inputs_page_final_visible_publication_render_sync_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_final_visible_publication_render_sync_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "bind": "render_design_guide_final_visible_item_binding_and_zero_shear_projection",
        "promote": "render_design_guide_final_visible_blocker_promotion_projection",
        "context": "render_design_guide_final_visible_post_click_contract_context",
        "replacement": "render_design_guide_post_click_bending_replacement_setup",
        "proofs": "render_design_guide_post_click_replacement_final_contract_proofs",
        "boundaries": "render_design_guide_visible_publication_contract_boundaries",
        "rescue": "render_design_guide_safe_combined_family_selection_rescue",
        "restamp": "render_design_guide_combined_visible_safe_cleanup_restamp",
        "sync": "render_design_guide_final_visible_render_plan_presentation_sync",
        "rebind": "render_design_guide_render_stage_intent_contract_rebind",
        "exact": "render_design_guide_primary_button_debug_and_exact_completion",
        "materialize": "render_design_guide_enabled_contract_final_evidence_blocker_materialization",
        "proof": "render_design_guide_selected_action_debug_and_publication_mutation_proof",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def bind(**kwargs):
        calls.append({"event": "bind"})
        return {"id": "visible", "button_contract": {"enabled": True}}

    def promote(**kwargs):
        calls.append({"event": "promote", "id": kwargs.get("final_visible_item", {}).get("id")})
        return dict(kwargs["final_visible_item"], promoted=True), dict(kwargs["final_visible_resolution"], promoted=True)

    def context(**kwargs):
        calls.append({"event": "context", "promoted": kwargs.get("final_visible_item", {}).get("promoted")})
        return {
            "final_contract_for_post_click": {"enabled": True},
            "final_family_for_post_click": "bending",
            "final_expected_util_for_post_click": 0.9,
            "final_current_bending_util_for_post_click": 1.1,
            "post_click_unresolved_families_for_visible": {"bending"},
            "post_click_below_floor_families_for_visible": {"shear"},
            "last_apply_route_for_visible": {"route": True},
            "same_flow_cleanup_apply_for_visible": True,
            "binding_audit_for_visible": {"binding": True},
            "post_click_contract_check_input_proof": {"proof": True},
            "post_click_final_contract_predicate_result_adapter": {"adapter": True},
            "post_click_final_contract_predicates": {"predicate": True},
            "post_click_bending_low_contract_enabled": True,
            "post_click_bending_exact_blocker_on_visible_item": True,
            "post_click_bending_low_requires_exact_blocker": True,
            "post_click_bending_low_visible_action": True,
        }

    def replacement(**kwargs):
        calls.append(
            {
                "event": "replacement",
                "low_visible": kwargs.get("post_click_bending_low_visible_action"),
                "route": kwargs.get("last_apply_route_for_visible", {}).get("route"),
            }
        )
        return (
            dict(kwargs["final_visible_item"], replacement=True),
            dict(kwargs["final_visible_resolution"], replacement=True),
            {"audit": True},
            {"resolution": True},
            {"contract": True},
            True,
            {"source": True},
        )

    def proofs(**kwargs):
        calls.append(
            {
                "event": "proofs",
                "family": kwargs.get("final_family_for_post_click"),
                "same_flow": kwargs.get("same_flow_cleanup_apply_for_visible"),
            }
        )
        return {"audit_proof": True}, {"decision": True}, {"adapter": True}

    def boundaries(**kwargs):
        calls.append({"event": "boundaries", "keys": sorted(kwargs.get("final_active_fail_keys_for_render") or [])})
        return (
            dict(kwargs["final_visible_item"], bounded=True),
            dict(kwargs["final_visible_resolution"], bounded=True),
            {"family": True},
            True,
        )

    def rescue(**kwargs):
        calls.append({"event": "rescue", "applied": kwargs.get("family_selection_item_applied")})
        return dict(kwargs["final_visible_item"], rescued=True), dict(kwargs["final_visible_resolution"], rescued=True)

    def restamp(**kwargs):
        calls.append({"event": "restamp"})
        return dict(kwargs["final_visible_item"], restamped=True), dict(kwargs["final_visible_resolution"], restamped=True)

    def sync(**kwargs):
        calls.append({"event": "sync"})
        return (
            dict(kwargs["final_visible_item"], synced=True),
            dict(kwargs["final_visible_resolution"], synced=True),
            {"overview": "synced"},
            {"headline": "synced"},
            [{"synced": True}],
            {"plan": "synced"},
            "synced_terminal",
            "synced_source",
        )

    def rebind(**kwargs):
        calls.append({"event": "rebind"})
        contract = dict(kwargs["final_visible_contract"], rebound=True)
        return dict(kwargs["final_visible_item"], rebound=True, button_contract=contract), contract

    def exact(**kwargs):
        calls.append({"event": "exact", "rebound": kwargs.get("final_visible_contract", {}).get("rebound")})
        return dict(kwargs["final_visible_item"], exact=True)

    def materialize(**kwargs):
        calls.append({"event": "materialize"})
        return dict(kwargs["final_visible_item"], materialized=True)

    def proof(**kwargs):
        calls.append({"event": "proof", "materialized": kwargs.get("final_visible_item", {}).get("materialized")})
        kwargs["guidance_debug"]["proof_called"] = True

    try:
        inputs_page.render_design_guide_final_visible_item_binding_and_zero_shear_projection = bind
        inputs_page.render_design_guide_final_visible_blocker_promotion_projection = promote
        inputs_page.render_design_guide_final_visible_post_click_contract_context = context
        inputs_page.render_design_guide_post_click_bending_replacement_setup = replacement
        inputs_page.render_design_guide_post_click_replacement_final_contract_proofs = proofs
        inputs_page.render_design_guide_visible_publication_contract_boundaries = boundaries
        inputs_page.render_design_guide_safe_combined_family_selection_rescue = rescue
        inputs_page.render_design_guide_combined_visible_safe_cleanup_restamp = restamp
        inputs_page.render_design_guide_final_visible_render_plan_presentation_sync = sync
        inputs_page.render_design_guide_render_stage_intent_contract_rebind = rebind
        inputs_page.render_design_guide_primary_button_debug_and_exact_completion = exact
        inputs_page.render_design_guide_enabled_contract_final_evidence_blocker_materialization = materialize
        inputs_page.render_design_guide_selected_action_debug_and_publication_mutation_proof = proof

        debug = {"debug": True}
        result = inputs_page.render_design_guide_final_visible_publication_render_sync_pipeline(
            final_visible_resolution={"item": {"id": "initial"}},
            guidance_debug=debug,
            current_state={"state": True},
            dg_overview={"overview": "initial"},
            dg_presentation={"headline": "initial"},
            post_cleanup_render_audit={"audit": True},
            final_active_fail_keys_for_render={"bending"},
            guidance_disp_state={"disp": True},
            guidance_items=[{"old": True}],
            render_plan={"plan": "old"},
            terminal_state="old_terminal",
            terminal_state_source="old_source",
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "bind",
            "promote",
            "context",
            "replacement",
            "proofs",
            "boundaries",
            "rescue",
            "restamp",
            "sync",
            "rebind",
            "exact",
            "materialize",
            "proof",
        ],
        f"calls={calls}",
    )
    final_visible_item, final_visible_resolution, dg_overview, dg_presentation, guidance_items, render_plan, terminal_state, terminal_state_source = result
    expect(
        "output_contract",
        final_visible_item.get("materialized") is True
        and final_visible_resolution.get("synced") is True
        and dg_overview == {"overview": "synced"}
        and dg_presentation == {"headline": "synced"}
        and guidance_items == [{"synced": True}]
        and render_plan == {"plan": "synced"}
        and terminal_state == "synced_terminal"
        and terminal_state_source == "synced_source"
        and debug.get("proof_called") is True,
        f"result={result} debug={debug}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_final_visible_publication_render_sync_pipeline")
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
        "render_design_guide_final_visible_publication_render_sync_pipeline" in legacy_calls,
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
        "result": {
            "final_visible_item": final_visible_item,
            "final_visible_resolution": final_visible_resolution,
            "dg_overview": dg_overview,
            "dg_presentation": dg_presentation,
            "guidance_items": guidance_items,
            "render_plan": render_plan,
            "terminal_state": terminal_state,
            "terminal_state_source": terminal_state_source,
            "debug": debug,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Visible Publication Render Sync Pipeline Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted final-visible publication render sync coordinator and its final contract/debug stamping sequence.",
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
