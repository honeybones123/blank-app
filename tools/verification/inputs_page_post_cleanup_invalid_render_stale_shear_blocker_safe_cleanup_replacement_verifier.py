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
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_stale_shear_blocker_safe_cleanup_replacement_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_stale_shear_blocker_safe_cleanup_replacement_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_guidance_state_snapshot",
        "_build_design_actions_context",
        "_collect_design_overview",
        "_shear_overdesign_contract_width_cleanup_item",
        "_design_guide_cleanup_item_publishable",
        "_stamp_zero_bending_demand_exclusion",
        "_design_guide_display_truth_for_item",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def guidance_state_snapshot(state):
        calls.append({"event": "guidance_state_snapshot", "state": dict(state or {})})
        snap = dict(state or {})
        snap["snapshot"] = True
        return snap

    def build_context(state):
        calls.append({"event": "build_context", "state": dict(state or {})})
        return {"context": True}

    def collect_overview(state, *, context):
        calls.append({"event": "collect_overview", "state": dict(state or {}), "context": dict(context or {})})
        return {"all_key_pass": True, "any_fail": False, "utils": {"shear": 0.55}}

    def cleanup_item(state, overview, *, threshold, allow_best_safe_below_threshold, prefer_supplied_state):
        calls.append(
            {
                "event": "cleanup_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "threshold": threshold,
                "allow_best_safe_below_threshold": allow_best_safe_below_threshold,
                "prefer_supplied_state": prefer_supplied_state,
            }
        )
        return {
            "title_main": "Shear width cleanup",
            "action_type": "apply_resolved_candidate",
            "button_contract": {"enabled": True},
            "candidate_search_evidence": {
                "safe_candidate_count": 2,
                "executable_candidate_count": 3,
            },
            "action_payload": {},
        }

    def publishable(item):
        calls.append({"event": "publishable", "title": (item or {}).get("title_main")})
        return True

    def stamp_zero_bending(target, state, utils):
        calls.append(
            {
                "event": "stamp_zero_bending",
                "target_title": (target or {}).get("title_main"),
                "state": dict(state or {}),
                "utils": dict(utils or {}),
            }
        )
        target["zero_bending_demand_excluded"] = True

    def display_truth(item, *, state, overview):
        calls.append(
            {
                "event": "display_truth",
                "title": (item or {}).get("title_main"),
                "state": dict(state or {}),
                "overview": dict(overview or {}),
            }
        )
        return {"displayed_status": "EFFICIENCY", "displayed_util": 0.55}

    try:
        inputs_page._guidance_state_snapshot = guidance_state_snapshot
        inputs_page._build_design_actions_context = build_context
        inputs_page._collect_design_overview = collect_overview
        inputs_page._shear_overdesign_contract_width_cleanup_item = cleanup_item
        inputs_page._design_guide_cleanup_item_publishable = publishable
        inputs_page._stamp_zero_bending_demand_exclusion = stamp_zero_bending
        inputs_page._design_guide_display_truth_for_item = display_truth

        guidance_debug = {"overview": {"utils": {"shear": 0.7}}}
        active_item, active_title, active_truth = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_stale_shear_blocker_safe_cleanup_replacement(
                blocked_render_item={"title_main": "Shear cleanup blocked by final efficiency threshold"},
                blocked_render_title_lower="shear cleanup blocked by final efficiency threshold",
                blocked_render_truth={"old": True},
                current_state={"s_lig": 300},
                dg_overview={},
                guidance_debug=guidance_debug,
            )
        )
        active_call_count = len(calls)

        original_item = {"title_main": "Other card"}
        original_truth = {"old": True}
        gated_item, gated_title, gated_truth = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_stale_shear_blocker_safe_cleanup_replacement(
                blocked_render_item=original_item,
                blocked_render_title_lower="other card",
                blocked_render_truth=original_truth,
                current_state={"s_lig": 300},
                dg_overview={},
                guidance_debug={},
            )
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    evidence = dict(active_item.get("candidate_search_evidence") or {}) if isinstance(active_item, dict) else {}
    payload = dict(active_item.get("action_payload") or {}) if isinstance(active_item, dict) else {}
    stamp_calls = [call for call in calls if call["event"] == "stamp_zero_bending"]

    expect(
        "active_replacement",
        isinstance(active_item, dict)
        and active_item.get("title_main") == "Shear width cleanup"
        and active_item.get("guidance_intent") == "optional_cleanup"
        and active_item.get("local_cleanup_candidate") is True
        and active_item.get("best_safe_partial_cleanup") is True
        and active_item.get("no_second_cta_required") is False
        and active_item.get("zero_bending_demand_excluded") is True
        and active_title == "shear width cleanup"
        and active_truth == {"displayed_status": "EFFICIENCY", "displayed_util": 0.55}
        and active_item.get("display_truth") == active_truth,
        f"active_item={active_item} active_title={active_title} active_truth={active_truth}",
    )
    expect(
        "evidence_and_payload",
        evidence.get("safe_candidate_count") == 2
        and evidence.get("executable_candidate_count") == 3
        and evidence.get("best_safe_partial_cleanup") is True
        and evidence.get("no_second_cta_required") is False
        and evidence.get("outside_target_band_allowed") is True
        and evidence.get("outside_target_band_allowed_category") == "safe_incremental_cleanup_below_final_threshold"
        and payload.get("candidate_search_evidence") == evidence
        and payload.get("best_safe_partial_cleanup") is True
        and payload.get("no_second_cta_required") is False,
        f"active_item={active_item}",
    )
    expect(
        "debug_stamping",
        guidance_debug.get("guidance_branch") == "render_stale_shear_blocker_replaced_by_safe_cleanup"
        and guidance_debug.get("selected_action_family") == "shear"
        and guidance_debug.get("primary_guidance_intent") == "optional_cleanup"
        and guidance_debug.get("button_contract_enabled") is True
        and guidance_debug.get("design_guide_has_actionable_recommendation") is True
        and guidance_debug.get("safe_local_cleanup_count") == 2
        and guidance_debug.get("executable_safe_cleanup_count") == 3
        and guidance_debug.get("zero_bending_demand_excluded") is True
        and len(stamp_calls) == 2,
        f"guidance_debug={guidance_debug} stamp_calls={stamp_calls}",
    )
    expect(
        "gated_noop",
        gated_item is original_item
        and gated_title == "other card"
        and gated_truth is original_truth
        and len(calls) == active_call_count,
        f"gated_item={gated_item} gated_title={gated_title} gated_truth={gated_truth} calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "active_item": active_item,
        "active_title": active_title,
        "active_truth": active_truth,
        "guidance_debug": guidance_debug,
        "gated_item": gated_item,
        "gated_title": gated_title,
        "gated_truth": gated_truth,
        "calls": calls,
        "failures": failures,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Stale Shear Blocker Safe Cleanup Replacement Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "json": str(json_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
