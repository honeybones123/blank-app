from __future__ import annotations

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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_green_low_bending_suppression_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_green_low_bending_suppression_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_parse = inputs_page._parse_util_value
    original_overview_ok = inputs_page._overview_required_checks_acceptable
    original_resolution_item = inputs_page._post_click_low_bending_resolution_item
    original_button_contracts = inputs_page._design_guide_apply_button_contracts_to_items
    original_display_truth = inputs_page._design_guide_apply_display_truth_to_items
    original_button_contract = inputs_page._design_guide_button_contract
    original_candidate_family = inputs_page._design_guide_candidate_family
    original_rr = inputs_page._recommendation_result_for_primary_guidance_card
    original_bending_item = inputs_page._bending_only_target_band_cleanup_item
    original_disable = inputs_page._disable_cleanup_item_without_target_band_proof
    original_enabled = inputs_page._design_guide_button_contract_enabled

    resolution_enabled = {"value": True}
    bending_enabled = {"value": False}

    def parse(value):
        try:
            return None if value is None else float(value)
        except Exception:
            return None

    def overview_ok(overview):
        calls.append({"event": "overview_ok", "overview": dict(overview or {})})
        return True

    def resolution_item(state, overview, mode_config, audit, *, debug_sink):
        calls.append(
            {
                "event": "resolution_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "mode_config": dict(mode_config or {}),
                "audit": dict(audit or {}),
            }
        )
        if not resolution_enabled["value"]:
            return {}
        debug_sink["guidance_branch"] = "resolution_branch"
        return {
            "title_main": "Resolve low families",
            "action_type": "apply_resolved_candidate",
            "guidance_intent": "specific_blocker",
            "candidate_search_evidence": {"safe_executor_backed_candidates_count": 2},
        }

    def apply_button_contracts(items, *, state):
        calls.append({"event": "apply_button_contracts", "items": list(items or []), "state": dict(state or {})})
        return [dict(item, button_contract_applied=True) for item in list(items or [])]

    def display_truth(items, *, state, overview, mode_config):
        calls.append({"event": "display_truth", "items": list(items or []), "state": dict(state or {})})
        return [dict(item, display_truth_applied=True) for item in list(items or [])]

    def button_contract(item, *, state):
        calls.append({"event": "button_contract", "item": dict(item or {}), "state": dict(state or {})})
        return {"enabled": True, "expected_util": item.get("expected_util", 0.82), "updates": {"n_bars": 4}}

    def candidate_family(item):
        calls.append({"event": "candidate_family", "item": dict(item or {})})
        return str((item or {}).get("family") or "bending")

    def rr(items, state, *, branch, request_kind):
        calls.append(
            {
                "event": "recommendation_result",
                "branch": branch,
                "request_kind": request_kind,
                "items": list(items or []),
                "state": dict(state or {}),
            }
        )
        return {"branch": branch, "count": len(list(items or []))}

    def bending_item(state, overview, mode_config, *, debug_sink):
        calls.append({"event": "bending_item", "state": dict(state or {})})
        if not bending_enabled["value"]:
            return {}
        debug_sink["bending_debug"] = True
        return {
            "title_main": "Tighten bending",
            "action_type": "apply_resolved_candidate",
            "candidate_search_evidence": {"safe_executor_backed_candidates_count": 3},
        }

    def disable(item, *, evidence, state, contract, expected_util):
        calls.append(
            {
                "event": "disable_without_proof",
                "item": dict(item or {}),
                "evidence": dict(evidence or {}),
                "contract": dict(contract or {}),
                "expected_util": expected_util,
            }
        )
        return dict(item or {}), dict(contract or {}), True

    def enabled(contract):
        calls.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool((contract or {}).get("enabled"))

    try:
        inputs_page._parse_util_value = parse
        inputs_page._overview_required_checks_acceptable = overview_ok
        inputs_page._post_click_low_bending_resolution_item = resolution_item
        inputs_page._design_guide_apply_button_contracts_to_items = apply_button_contracts
        inputs_page._design_guide_apply_display_truth_to_items = display_truth
        inputs_page._design_guide_button_contract = button_contract
        inputs_page._design_guide_candidate_family = candidate_family
        inputs_page._recommendation_result_for_primary_guidance_card = rr
        inputs_page._bending_only_target_band_cleanup_item = bending_item
        inputs_page._disable_cleanup_item_without_target_band_proof = disable
        inputs_page._design_guide_button_contract_enabled = enabled

        resolution_items, resolution_debug, resolution_rr = (
            inputs_page.render_design_guide_terminal_green_low_bending_suppression(
                guidance_items=[{"title_main": "Target band achieved"}],
                guidance_debug={},
                guidance_disp_state={"case": "resolution"},
                render_overview={"utils": {"bending": 0.6, "shear": 0.7}, "any_fail": False},
                render_mode_config={"mode": "balanced"},
                family_speed_isolated_bending_repair=False,
                recommendation_result={"old": True},
            )
        )

        resolution_enabled["value"] = False
        bending_enabled["value"] = True
        bending_items, bending_debug, bending_rr = (
            inputs_page.render_design_guide_terminal_green_low_bending_suppression(
                guidance_items=[{"title_main": "already_efficient"}],
                guidance_debug={},
                guidance_disp_state={"case": "bending"},
                render_overview={"utils": {"bending": 0.6, "shear": 0.96}, "any_fail": False},
                render_mode_config={"mode": "balanced"},
                family_speed_isolated_bending_repair=False,
                recommendation_result={"old": True},
            )
        )

        guarded_items, guarded_debug, guarded_rr = (
            inputs_page.render_design_guide_terminal_green_low_bending_suppression(
                guidance_items=[{"title_main": "Target band achieved"}],
                guidance_debug={},
                guidance_disp_state={"case": "guarded"},
                render_overview={"utils": {"bending": 0.6}, "any_fail": False},
                render_mode_config={"mode": "balanced"},
                family_speed_isolated_bending_repair=True,
                recommendation_result={"old": True},
            )
        )
    finally:
        inputs_page._parse_util_value = original_parse
        inputs_page._overview_required_checks_acceptable = original_overview_ok
        inputs_page._post_click_low_bending_resolution_item = original_resolution_item
        inputs_page._design_guide_apply_button_contracts_to_items = original_button_contracts
        inputs_page._design_guide_apply_display_truth_to_items = original_display_truth
        inputs_page._design_guide_button_contract = original_button_contract
        inputs_page._design_guide_candidate_family = original_candidate_family
        inputs_page._recommendation_result_for_primary_guidance_card = original_rr
        inputs_page._bending_only_target_band_cleanup_item = original_bending_item
        inputs_page._disable_cleanup_item_without_target_band_proof = original_disable
        inputs_page._design_guide_button_contract_enabled = original_enabled

    expect(
        "resolution_publication_path",
        resolution_debug.get("terminal_green_low_bending_render_suppressed") is True
        and resolution_debug.get("guidance_branch") == "resolution_branch"
        and resolution_debug.get("selected_action_type") == "apply_resolved_candidate"
        and resolution_debug.get("selected_action_family") == "bending"
        and resolution_debug.get("materially_overprovided_families") == ["bending", "shear"]
        and resolution_rr == {"branch": "resolution_branch", "count": 1}
        and resolution_items[0].get("button_contract") == {"enabled": True, "expected_util": 0.82, "updates": {"n_bars": 4}},
        f"resolution_items={resolution_items} resolution_debug={resolution_debug} resolution_rr={resolution_rr}",
    )
    expect(
        "bending_cleanup_path",
        bending_debug.get("terminal_green_low_bending_render_suppressed") is True
        and bending_debug.get("guidance_branch") == "bending_below_target_bending_only_cleanup"
        and bending_debug.get("selected_action_family") == "bending"
        and bending_debug.get("safe_local_cleanup_count") == 3
        and bending_debug.get("button_contract_enabled") is True
        and bending_rr == {"branch": "bending_below_target_bending_only_cleanup", "count": 1}
        and bending_items[0].get("allow_in_target_primary_action") is True,
        f"bending_items={bending_items} bending_debug={bending_debug} bending_rr={bending_rr}",
    )
    guarded_calls = [
        call
        for call in calls
        if call.get("state") == {"case": "guarded"}
        or call.get("item", {}).get("title_main") == "Target band achieved"
    ]
    expect(
        "family_speed_guard_no_publication",
        guarded_items == [{"title_main": "Target band achieved"}]
        and guarded_debug == {}
        and guarded_rr == {"old": True}
        and not any(call.get("event") in {"resolution_item", "bending_item"} for call in guarded_calls),
        f"guarded_items={guarded_items} guarded_debug={guarded_debug} guarded_rr={guarded_rr} guarded_calls={guarded_calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "resolution_items": resolution_items,
        "resolution_debug": resolution_debug,
        "resolution_rr": resolution_rr,
        "bending_items": bending_items,
        "bending_debug": bending_debug,
        "bending_rr": bending_rr,
        "guarded_items": guarded_items,
        "guarded_debug": guarded_debug,
        "guarded_rr": guarded_rr,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Green Low Bending Suppression Verifier",
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
