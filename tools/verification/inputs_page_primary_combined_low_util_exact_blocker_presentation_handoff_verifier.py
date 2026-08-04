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
    json_path = (
        ARTIFACT_DIR
        / f"inputs_page_primary_combined_low_util_exact_blocker_presentation_handoff_{timestamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"inputs_page_primary_combined_low_util_exact_blocker_presentation_handoff_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_enabled = inputs_page._design_guide_button_contract_enabled
    original_updates_match = inputs_page._updates_match_state
    original_best_safe = inputs_page._best_safe_cleanup_action_proof_allows_executable_cta
    original_exact = inputs_page._exact_cleanup_blocker_for_outside_target_action
    original_disabled = inputs_page._disabled_design_guide_button_contract
    original_green = inputs_page._terminal_exact_cleanup_blocker_should_render_green

    def enabled(contract):
        contract = dict(contract or {})
        calls.append({"event": "contract_enabled", "contract": contract})
        return bool(contract.get("enabled"))

    def updates_match(state, updates):
        calls.append({"event": "updates_match", "state": dict(state), "updates": dict(updates)})
        return False

    def best_safe(**kwargs):
        calls.append({"event": "best_safe", "kwargs": dict(kwargs)})
        return False

    def exact(**kwargs):
        calls.append({"event": "exact_builder", "kwargs": dict(kwargs)})
        return {
            "reason": "bending remains below final threshold",
            "source": kwargs.get("source"),
        }

    def restamp(exact_blockers):
        calls.append({"event": "restamp", "exact_blockers": dict(exact_blockers or {})})
        return dict(exact_blockers or {})

    def disabled(item, *, family, reason):
        calls.append(
            {
                "event": "disabled_contract",
                "item_title": (item or {}).get("title_main") or (item or {}).get("title"),
                "family": family,
                "reason": reason,
            }
        )
        return {"enabled": False, "family": family, "reason": reason}

    def green(item, overview, contract, exact_blockers):
        calls.append(
            {
                "event": "terminal_green_check",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "contract": dict(contract or {}),
                "exact_blockers": dict(exact_blockers or {}),
            }
        )
        return False

    try:
        inputs_page._design_guide_button_contract_enabled = enabled
        inputs_page._updates_match_state = updates_match
        inputs_page._best_safe_cleanup_action_proof_allows_executable_cta = best_safe
        inputs_page._exact_cleanup_blocker_for_outside_target_action = exact
        inputs_page._disabled_design_guide_button_contract = disabled
        inputs_page._terminal_exact_cleanup_blocker_should_render_green = green

        stale_result = (
            inputs_page.render_design_guide_primary_combined_low_util_exact_blocker_presentation_handoff(
                primary_post_click_item={"title_main": "Keep item"},
                primary_render_items=[{"button_contract": {"enabled": True, "family": "bending"}}],
                guidance_items=[{"title": "keep guidance"}],
                render_plan={"visible_guidance_items": [{"title": "keep visible"}], "reason": "keep"},
                dg_presentation={"headline": "Target achieved"},
                guidance_debug={"overview": {"utils": {"bending": 0.9}}},
                primary_guidance_disp_state_for_render={"b": 1},
                dg_overview={},
                visible_utils_for_exact_blockers={"shear": 0.7},
                restamp_exact_blocker_current_utils_fn=restamp,
            )
        )

        exact_primary_item = {
            "title_main": "Bending cleanup action",
            "exact_blockers_by_family": {"shear": {"reason": "shear below detailing floor"}},
            "candidate_search_evidence": {"note": "candidate"},
            "selected_action_updates": {"b": 2},
        }
        exact_result = (
            inputs_page.render_design_guide_primary_combined_low_util_exact_blocker_presentation_handoff(
                primary_post_click_item=exact_primary_item,
                primary_render_items=[
                    {
                        "button_contract": {
                            "enabled": True,
                            "family": "bending",
                            "expected_util": 0.72,
                            "updates": {"b": 2},
                            "candidate_id": "candidate-1",
                        }
                    }
                ],
                guidance_items=[{"title": "old guidance"}],
                render_plan={"visible_guidance_items": [{"title": "old visible"}], "reason": "old"},
                dg_presentation={"headline": "Accepted"},
                guidance_debug={"overview": {"utils": {"bending": 0.71}}},
                primary_guidance_disp_state_for_render={"b": 1},
                dg_overview={"utils": {"bending": 0.71}},
                visible_utils_for_exact_blockers={},
                restamp_exact_blocker_current_utils_fn=restamp,
            )
        )
    finally:
        inputs_page._design_guide_button_contract_enabled = original_enabled
        inputs_page._updates_match_state = original_updates_match
        inputs_page._best_safe_cleanup_action_proof_allows_executable_cta = original_best_safe
        inputs_page._exact_cleanup_blocker_for_outside_target_action = original_exact
        inputs_page._disabled_design_guide_button_contract = original_disabled
        inputs_page._terminal_exact_cleanup_blocker_should_render_green = original_green

    (
        stale_item,
        stale_primary,
        stale_guidance,
        stale_plan,
        stale_presentation,
        stale_debug,
        stale_visible_utils,
    ) = stale_result
    (
        exact_item,
        exact_primary,
        exact_guidance,
        exact_plan,
        exact_presentation,
        exact_debug,
        exact_visible_utils,
    ) = exact_result

    expect(
        "stale_presentation_suppressed",
        stale_presentation == {}
        and stale_item == {"title_main": "Keep item"}
        and stale_primary == [{"button_contract": {"enabled": True, "family": "bending"}}]
        and stale_guidance == [{"title": "keep guidance"}]
        and stale_plan == {"visible_guidance_items": [{"title": "keep visible"}], "reason": "keep"}
        and stale_debug == {"overview": {"utils": {"bending": 0.9}}}
        and stale_visible_utils == {"shear": 0.7},
        (
            f"item={stale_item} primary={stale_primary} guidance={stale_guidance} "
            f"plan={stale_plan} presentation={stale_presentation} debug={stale_debug} "
            f"visible_utils={stale_visible_utils}"
        ),
    )
    expect(
        "combined_exact_blocker_render",
        exact_item.get("title_main") == "Bending and shear cleanup blocked"
        and exact_item.get("family") == "combined"
        and exact_item.get("button_contract")
        == {
            "enabled": False,
            "family": "combined",
            "reason": (
                "Bending cleanup blocked: bending remains below final threshold "
                "Shear cleanup blocked: shear below detailing floor"
            ),
        }
        and exact_plan.get("reason") == "combined_low_util_exact_blocker_primary_render"
        and exact_primary == [exact_item]
        and exact_guidance == [exact_item]
        and exact_presentation == {},
        (
            f"item={exact_item} primary={exact_primary} guidance={exact_guidance} "
            f"plan={exact_plan} presentation={exact_presentation}"
        ),
    )
    expect(
        "combined_exact_debug",
        exact_debug.get("guidance_branch") == "combined_low_util_exact_blocker_primary_render"
        and exact_debug.get("selected_title") == "Bending and shear cleanup blocked"
        and exact_debug.get("primary_guidance_intent") == "specific_blocker"
        and exact_debug.get("button_contract_enabled") is False
        and set(dict(exact_debug.get("exact_blockers_by_family") or {})) == {"bending", "shear"}
        and set(dict(exact_debug.get("candidate_search_evidence") or {}).get("exact_blockers_by_family") or {})
        == {"bending", "shear"}
        and exact_visible_utils == {"bending": 0.71},
        f"debug={exact_debug} visible_utils={exact_visible_utils}",
    )
    expect(
        "call_coverage",
        any(call["event"] == "updates_match" for call in calls)
        and any(call["event"] == "best_safe" for call in calls)
        and any(call["event"] == "exact_builder" for call in calls)
        and any(call["event"] == "disabled_contract" for call in calls)
        and any(call["event"] == "terminal_green_check" for call in calls),
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "stale_result": stale_result,
        "exact_result": exact_result,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Combined Low Util Exact Blocker Presentation Handoff Verifier",
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
