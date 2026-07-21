from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class _FakeSessionState(dict):
    pass


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = _FakeSessionState()


def main() -> int:
    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import current_coordinators as current

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_guidance_item_postprocess_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_guidance_item_postprocess_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    fake_st = _FakeStreamlit()
    events: list[str] = []
    provider_originals = {
        name: getattr(bridge, name)
        for name in (
            "_dedupe_guidance_items_for_display",
            "_collapse_to_single_primary_guidance_item",
            "_recommendation_result_for_primary_guidance_card",
            "_suppress_redundant_guidance_items",
            "_consolidate_guidance_items_by_family",
            "_maybe_promote_safe_local_cleanup_primary",
            "_prefer_target_band_guidance_item_order",
            "_align_guidance_items_to_candidate_search_evidence",
            "_design_guide_apply_copy_model_to_items",
            "_design_guide_apply_button_contracts_to_items",
            "_design_guide_apply_display_truth_to_items",
            "_design_mode_config",
            "_design_optimisation_goal",
            "_local_cleanup_post_apply_acceptance_matches",
        )
    }
    current_originals = {
        "provider": current._CURRENT_COORDINATOR_PROVIDER,
        "st": current._ST_MODULE,
        "os": current._OS_MODULE,
        "sys": current._SYS_MODULE,
    }
    try:
        bridge._dedupe_guidance_items_for_display = lambda items, state: (
            events.append("dedupe") or ([{"id": "deduped"}], {"deduped": True})
        )
        bridge._collapse_to_single_primary_guidance_item = lambda items, state: (
            events.append("collapse")
            or (
                [{"id": "collapsed"}],
                {
                    "collapsed": True,
                    "reason": "unit",
                    "subfamilies": ["bending"],
                    "covered_fail_keys": ["bending"],
                    "remaining_fail_keys": [],
                },
            )
        )
        recommendation_calls: list[dict[str, Any]] = []

        def _recommend(items, state, *, branch, request_kind):
            events.append("recommend")
            recommendation_calls.append({"branch": branch, "request_kind": request_kind, "count": len(items)})
            return {"recommendation": len(recommendation_calls)}

        bridge._recommendation_result_for_primary_guidance_card = _recommend
        bridge._suppress_redundant_guidance_items = lambda items, reco: (
            events.append("redundancy") or (list(items), {"suppressed": False, "reason": None})
        )
        bridge._consolidate_guidance_items_by_family = lambda items: (
            events.append("family") or (list(items), {"applied": False, "primary_family": "bending"})
        )

        def _promote(items, **kwargs):
            events.append("local_cleanup")
            return list(items), {
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_local_cleanup_count": 1,
                "executable_safe_cleanup_count": 1,
            }

        bridge._maybe_promote_safe_local_cleanup_primary = _promote
        bridge._prefer_target_band_guidance_item_order = lambda items, **kwargs: events.append("prefer") or list(items)
        bridge._align_guidance_items_to_candidate_search_evidence = lambda items: events.append("align") or list(items)
        bridge._design_guide_apply_copy_model_to_items = lambda items, **kwargs: events.append("copy") or list(items)
        bridge._design_guide_apply_button_contracts_to_items = lambda items, **kwargs: events.append("buttons") or list(items)
        bridge._design_guide_apply_display_truth_to_items = lambda items, **kwargs: events.append("display") or list(items)
        bridge._design_optimisation_goal = lambda state: "balanced"
        bridge._design_mode_config = lambda goal: {"goal": goal}
        bridge._local_cleanup_post_apply_acceptance_matches = lambda state: False
        current.configure_design_guide_current_provider(
            bridge,
            st_module=fake_st,
            os_module=os,
            sys_module=sys,
        )

        stages: list[str] = []
        result = current.render_design_guide_item_postprocess_current_coordinator(
            guidance_items_raw=[{"id": "raw"}],
            guidance_disp_state={"D": 500},
            guidance_debug={"guidance_branch": "branch_a", "overview": {}, "efficiency_tightening_state": {}},
            _stage=lambda label: stages.append(str(label)),
        )
    finally:
        for name, value in provider_originals.items():
            setattr(bridge, name, value)
        current.configure_design_guide_current_provider(
            current_originals["provider"],
            st_module=current_originals["st"],
            os_module=current_originals["os"],
            sys_module=current_originals["sys"],
        )

    expected_stages = [
        "after_dedupe",
        "after_collapse",
        "after_recommendation_result",
        "after_redundancy",
        "after_family_consolidation",
        "after_local_cleanup_promote",
        "after_prefer_order",
        "after_copy_model",
        "after_button_contracts",
        "after_display_truth",
        "after_render_acceptance_audit",
        "after_final_recommendation_result",
    ]
    expected_events = [
        "dedupe",
        "collapse",
        "recommend",
        "redundancy",
        "family",
        "local_cleanup",
        "prefer",
        "align",
        "copy",
        "buttons",
        "display",
        "recommend",
    ]
    guidance_debug = {
        "dedupe": result.get("guidance_dedupe_meta"),
        "collapse": result.get("collapse_meta"),
        "recommendation": result.get("_recommendation_result"),
        "redundancy": result.get("redundancy_meta"),
        "family": result.get("family_suppression_meta"),
    }
    failures: list[str] = []
    if stages != expected_stages:
        failures.append(f"stage_order_mismatch:{stages}")
    if events != expected_events:
        failures.append(f"event_order_mismatch:{events}")
    if result.get("_branch_for_rr") != "branch_a":
        failures.append(f"branch_mismatch:{result.get('_branch_for_rr')}")
    if result.get("guidance_dedupe_meta") != {"deduped": True}:
        failures.append("dedupe_meta_missing")
    if result.get("collapse_meta", {}).get("collapsed") is not True:
        failures.append("collapse_meta_missing")
    if fake_st.session_state.get("_design_guide_single_primary_debug", {}).get("guidance_items_visible_count") != 1:
        failures.append("single_primary_session_debug_missing")
    if result.get("_recommendation_result") != {"recommendation": 2}:
        failures.append(f"recommendation_result_mismatch:{result.get('_recommendation_result')}")
    guidance_items = list(result.get("guidance_items") or [])
    if len(guidance_items) != 1 or guidance_items[0].get("id") != "collapsed":
        failures.append(f"guidance_items_mismatch:{guidance_items}")
    if len(recommendation_calls) != 2:
        failures.append(f"recommendation_call_count_mismatch:{recommendation_calls}")

    payload = {
        "verifier": "inputs_page_guidance_item_postprocess_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "events": events,
        "stages": stages,
        "result_debug": guidance_debug,
        "recommendation_calls": recommendation_calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Item Postprocess Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                f"- events: `{events}`",
                f"- stages: `{stages}`",
                f"- recommendation calls: `{recommendation_calls}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
