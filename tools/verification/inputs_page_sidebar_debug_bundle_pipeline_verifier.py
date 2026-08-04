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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_sidebar_debug_bundle_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_sidebar_debug_bundle_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []
    payloads: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "initial": "render_design_guide_sidebar_debug_initial_context",
        "safe_combined": "render_design_guide_displayed_primary_safe_combined_promotion",
        "exact_enrich": "render_design_guide_displayed_primary_exact_blocker_enrichment",
        "apply_payload": "render_design_guide_displayed_primary_apply_payload_debug_publication",
        "truth": "render_design_guide_displayed_primary_truth_normalisation",
        "updates": "render_design_guide_displayed_primary_update_family_and_link_state",
        "engine": "render_design_guide_engine_evidence_and_rebind_probe_setup",
        "proof_contract": "render_design_guide_post_click_safe_intent_and_proof_contract_setup",
        "threshold": "render_design_guide_proof_action_threshold_state",
        "blocker": "render_design_guide_displayed_best_safe_outside_threshold_blocker_evidence",
        "terminalization": "render_design_guide_displayed_best_safe_bending_terminalization",
        "contract_bundle": "render_design_guide_final_primary_contract_bundle_setup",
        "target_augment": "render_design_guide_final_primary_target_band_blocker_augmentation",
        "restamp": "render_design_guide_blocker_attempts_and_exact_blocker_restamp_bundle",
        "payload": "render_design_guide_debug_bundle_publication_payload",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}
    threshold_flag = {"value": True}

    def initial(**kwargs):
        calls.append({"event": "initial", "terminal_state": kwargs.get("terminal_state")})
        return (
            {"route": True},
            [{"summary": True}],
            {"overview": True},
            {"primary": True, "action_payload": {"payload": True}},
            {"payload": True},
            True,
            0.91,
            "0.91",
            {"trial": True},
            {"live": True},
            0.9,
            0.91,
            {"mode": True},
            True,
            {"truth": True},
            True,
            {"displayed": True},
            {"displayed_payload": True},
            {"displayed_resolved": True},
            {"evidence": True},
            {"button": True},
        )

    def safe_combined(**kwargs):
        calls.append({"event": "safe_combined"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["safe_combined"] = True
        return (
            debug,
            dict(kwargs.get("displayed_primary_item") or {}, safe=True),
            dict(kwargs.get("displayed_primary_payload") or {}, safe=True),
            dict(kwargs.get("displayed_primary_resolved") or {}, safe=True),
            dict(kwargs.get("displayed_primary_candidate_search_evidence") or {}, safe=True),
            dict(kwargs.get("displayed_primary_button_contract") or {}, safe=True),
        )

    def exact_enrich(**kwargs):
        calls.append({"event": "exact_enrich"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["exact_enrich"] = True
        return (
            debug,
            dict(kwargs.get("displayed_primary_item") or {}, exact=True),
            dict(kwargs.get("displayed_primary_payload") or {}, exact=True),
            dict(kwargs.get("displayed_primary_resolved") or {}, exact=True),
            dict(kwargs.get("displayed_primary_candidate_search_evidence") or {}, exact=True),
        )

    def apply_payload(**kwargs):
        calls.append({"event": "apply_payload"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["apply_payload"] = True
        return debug

    def truth(**kwargs):
        calls.append({"event": "truth"})
        item = dict(kwargs.get("displayed_primary_item") or {})
        return item, {"truth": "display"}, "bending", 0.91, "source", "card", "apply_resolved_candidate"

    def updates(**kwargs):
        calls.append({"event": "updates"})
        return {"n_bars": 5}, ["bending"], "bending", {"eval": True}, {"link": True}

    def engine(**kwargs):
        calls.append({"event": "engine"})
        return (
            {"decision": True},
            {"card": True},
            {"button_debug": True},
            {"outcome": True},
            {"trace": True},
            {"engine_evidence": True},
            {"proof": True},
        )

    def proof_contract(**kwargs):
        calls.append({"event": "proof_contract"})
        return dict(kwargs.get("displayed_primary_button_contract") or {}, proof=True), {"proof": "updated"}

    def threshold(**kwargs):
        calls.append({"event": "threshold", "flag": bool(threshold_flag["value"])})
        return "bending", 0.82, bool(threshold_flag["value"])

    def blocker(**kwargs):
        calls.append({"event": "blocker"})
        return {"blocker": True}

    def terminalization(**kwargs):
        calls.append({"event": "terminalization"})
        return (
            dict(kwargs.get("displayed_primary_item") or {}, terminalized=True),
            dict(kwargs.get("displayed_primary_button_contract") or {}, terminalized=True),
            dict(kwargs.get("displayed_primary_payload") or {}, terminalized=True),
            dict(kwargs.get("displayed_primary_resolved") or {}, terminalized=True),
            dict(kwargs.get("displayed_primary_candidate_search_evidence") or {}, terminalized=True),
        )

    def contract_bundle(**kwargs):
        calls.append({"event": "contract_bundle"})
        return {"contract_bundle": True}, True, {"bundle_payload": True}

    def target_augment(**kwargs):
        calls.append({"event": "target_augment"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["target_augment"] = True
        return debug

    def restamp(**kwargs):
        calls.append({"event": "restamp"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["restamp"] = True
        return (
            dict(kwargs.get("displayed_primary_candidate_search_evidence") or {}, restamped=True),
            dict(kwargs.get("engine_candidate_search_evidence") or {}, restamped=True),
            debug,
            dict(kwargs.get("engine_card_debug") or {}, restamped=True),
            {"exact": True},
        )

    def payload(**kwargs):
        calls.append({"event": "payload"})
        payloads.append({key: value for key, value in kwargs.items()})

    try:
        inputs_page.render_design_guide_sidebar_debug_initial_context = initial
        inputs_page.render_design_guide_displayed_primary_safe_combined_promotion = safe_combined
        inputs_page.render_design_guide_displayed_primary_exact_blocker_enrichment = exact_enrich
        inputs_page.render_design_guide_displayed_primary_apply_payload_debug_publication = apply_payload
        inputs_page.render_design_guide_displayed_primary_truth_normalisation = truth
        inputs_page.render_design_guide_displayed_primary_update_family_and_link_state = updates
        inputs_page.render_design_guide_engine_evidence_and_rebind_probe_setup = engine
        inputs_page.render_design_guide_post_click_safe_intent_and_proof_contract_setup = proof_contract
        inputs_page.render_design_guide_proof_action_threshold_state = threshold
        inputs_page.render_design_guide_displayed_best_safe_outside_threshold_blocker_evidence = blocker
        inputs_page.render_design_guide_displayed_best_safe_bending_terminalization = terminalization
        inputs_page.render_design_guide_final_primary_contract_bundle_setup = contract_bundle
        inputs_page.render_design_guide_final_primary_target_band_blocker_augmentation = target_augment
        inputs_page.render_design_guide_blocker_attempts_and_exact_blocker_restamp_bundle = restamp
        inputs_page.render_design_guide_debug_bundle_publication_payload = payload

        debug_true = inputs_page.render_design_guide_sidebar_debug_bundle_pipeline(
            current_state={"current": True},
            guidance_items=[{"id": "primary"}],
            guidance_debug={},
            guidance_disp_state={"state": True},
            render_plan={"plan": True},
            terminal_state="optimal",
            guidance_compute_ms=12.3,
            guidance_cache_hit=True,
            resolved_guidance_actions=[{"action": True}],
            mode_mt={"mode_mt": True},
            bottom_bt={"bottom": True},
            recommendation_result={"rr": True},
            guidance_dedupe_meta={"dedupe": True},
            banner_generic_only=True,
            fast_focus_section="model",
        )

        threshold_flag["value"] = False
        debug_false = inputs_page.render_design_guide_sidebar_debug_bundle_pipeline(
            current_state={"current": True},
            guidance_items=[{"id": "primary"}],
            guidance_debug={},
            guidance_disp_state={"state": True},
            render_plan={"plan": True},
            terminal_state="optimal",
            guidance_compute_ms=12.3,
            guidance_cache_hit=False,
            resolved_guidance_actions=[],
            mode_mt={},
            bottom_bt={},
            recommendation_result={"rr": False},
            guidance_dedupe_meta={},
            banner_generic_only=False,
            fast_focus_section="guide",
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    events = [call["event"] for call in calls]
    expect(
        "true_path_call_order_and_debug",
        events[:15]
        == [
            "initial",
            "safe_combined",
            "exact_enrich",
            "apply_payload",
            "truth",
            "updates",
            "engine",
            "proof_contract",
            "threshold",
            "blocker",
            "terminalization",
            "contract_bundle",
            "target_augment",
            "restamp",
            "payload",
        ]
        and debug_true.get("restamp") is True,
        f"events={events} debug_true={debug_true}",
    )
    second_events = events[15:]
    expect(
        "false_path_skips_terminalization",
        "terminalization" not in second_events
        and second_events
        == [
            "initial",
            "safe_combined",
            "exact_enrich",
            "apply_payload",
            "truth",
            "updates",
            "engine",
            "proof_contract",
            "threshold",
            "contract_bundle",
            "target_augment",
            "restamp",
            "payload",
        ]
        and debug_false.get("restamp") is True,
        f"second_events={second_events} debug_false={debug_false}",
    )
    expect(
        "payload_fields_preserved",
        len(payloads) == 2
        and payloads[0].get("guidance_compute_ms") == 12.3
        and payloads[0].get("guidance_cache_hit") is True
        and payloads[0].get("banner_generic_only") is True
        and payloads[0].get("fast_focus_section") == "model"
        and payloads[0].get("bundle_exact_blockers") == {"exact": True}
        and payloads[0].get("displayed_primary_candidate_search_evidence", {}).get("terminalized") is True
        and payloads[1].get("guidance_cache_hit") is False
        and payloads[1].get("banner_generic_only") is False,
        f"payloads={payloads}",
    )
    module = ast.parse((ROOT / "inputs_page.py").read_text(encoding="utf-8"))
    fast_panel = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_fast_design_guidance_panel"
    )
    call_count = sum(
        1
        for node in ast.walk(fast_panel)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render_design_guide_sidebar_debug_bundle_pipeline"
    )
    expect(
        "monolith_delegates_sidebar_pipeline_once",
        call_count == 1,
        f"call_count={call_count}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "events": events,
        "payloads": payloads,
        "debug_true": debug_true,
        "debug_false": debug_false,
        "call_count": call_count,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Sidebar Debug Bundle Pipeline Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
