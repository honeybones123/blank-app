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
        f"inputs_page_post_cleanup_invalid_render_visible_blocker_completion_and_promotion_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_visible_blocker_completion_and_promotion_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_attach_family_status_display_payload",
        "_complete_visible_low_util_blocker_evidence",
        "_visible_safe_combined_cleanup_action_from_evidence",
        "_visible_safe_low_util_cleanup_action_from_evidence",
        "_design_guide_item_is_visible_blocker",
        "_design_guide_button_contract_enabled",
        "_exact_cleanup_blocker_for_outside_target_action",
        "_disabled_design_guide_button_contract",
        "_design_guide_candidate_family",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def attach(item, *, state):
        calls.append({"event": "attach", "item": dict(item or {}), "state": dict(state or {})})
        out = dict(item or {})
        out["family_status_attached"] = True
        return out

    def complete(item, overview, state, *, debug_sink=None):
        calls.append(
            {
                "event": "complete",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "state": dict(state or {}),
            }
        )
        out = dict(item or {})
        out["visible_evidence_completed"] = True
        if isinstance(debug_sink, dict):
            debug_sink["completed_called"] = True
        return out

    def combined(item, overview, state, *, debug_sink=None):
        calls.append(
            {
                "event": "combined",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "state": dict(state or {}),
            }
        )
        if (item or {}).get("promote_combined"):
            if isinstance(debug_sink, dict):
                debug_sink["combined_promoted"] = True
            return {"title_main": "Combined safe cleanup", "combined": True}
        return None

    def low_util(item, overview, state, *, debug_sink=None):
        calls.append(
            {
                "event": "low_util",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "state": dict(state or {}),
            }
        )
        return None

    def is_visible(item):
        calls.append({"event": "is_visible", "item": dict(item or {})})
        return bool((item or {}).get("visible_blocker"))

    def contract_enabled(contract):
        calls.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool((contract or {}).get("enabled"))

    def exact_blocker(**kwargs):
        calls.append({"event": "exact_blocker", "kwargs": dict(kwargs)})
        return {
            "reason": "hidden action remains below final threshold",
            "best_safe_final_util": kwargs.get("final_util"),
            "source": kwargs.get("source"),
        }

    def restamp(exact):
        calls.append({"event": "restamp", "exact": dict(exact or {})})
        return {
            family: {**dict(blocker), "restamped": True}
            for family, blocker in dict(exact or {}).items()
        }

    def disabled_contract(item, *, family, reason):
        calls.append(
            {
                "event": "disabled_contract",
                "item": dict(item or {}),
                "family": family,
                "reason": reason,
            }
        )
        return {"enabled": False, "family": family, "blocking_reason": reason}

    try:
        inputs_page._attach_family_status_display_payload = attach
        inputs_page._complete_visible_low_util_blocker_evidence = complete
        inputs_page._visible_safe_combined_cleanup_action_from_evidence = combined
        inputs_page._visible_safe_low_util_cleanup_action_from_evidence = low_util
        inputs_page._design_guide_item_is_visible_blocker = is_visible
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._exact_cleanup_blocker_for_outside_target_action = exact_blocker
        inputs_page._disabled_design_guide_button_contract = disabled_contract
        inputs_page._design_guide_candidate_family = lambda item: str((item or {}).get("family") or "shear")

        combined_debug = {"overview": {"utils": {"shear": 0.7}}}
        combined_item, combined_best_safe, combined_utils = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_visible_blocker_completion_and_promotion(
                blocked_render_item={"title_main": "Blocker", "promote_combined": True},
                blocked_render_is_best_safe_action=False,
                blocked_render_reason="combined path",
                guidance_debug=combined_debug,
                guidance_disp_state={"s_lig": 300},
                dg_overview={},
                visible_utils_for_exact_blockers={},
                restamp_exact_blocker_current_utils_fn=restamp,
            )
        )

        generated_debug = {"overview": {"utils": {"shear": 0.62}}}
        generated_item, generated_best_safe, generated_utils = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_visible_blocker_completion_and_promotion(
                blocked_render_item={
                    "title_main": "Shear visible blocker",
                    "visible_blocker": True,
                    "family": "shear",
                    "button_contract": {
                        "enabled": True,
                        "family": "shear",
                        "expected_util": 0.72,
                        "updates": {"s_lig": 250},
                        "candidate_id": "safe-row",
                    },
                    "candidate_search_evidence": {},
                },
                blocked_render_is_best_safe_action=False,
                blocked_render_reason="visible blocker reason",
                guidance_debug=generated_debug,
                guidance_disp_state={"s_lig": 300},
                dg_overview={},
                visible_utils_for_exact_blockers={},
                restamp_exact_blocker_current_utils_fn=restamp,
            )
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    generated_exact = dict(generated_item.get("exact_blockers_by_family") or {})
    generated_cleanup = dict(generated_item.get("cleanup_evidence_by_family") or {})
    generated_evidence = dict(generated_item.get("candidate_search_evidence") or {})

    expect(
        "combined_promotion",
        combined_item == {"title_main": "Combined safe cleanup", "combined": True}
        and combined_best_safe is True
        and combined_utils == {}
        and combined_debug.get("combined_promoted") is True
        and combined_debug.get("completed_called") is True,
        f"combined_item={combined_item} combined_debug={combined_debug}",
    )
    expect(
        "generated_exact",
        generated_best_safe is False
        and generated_exact.get("shear", {}).get("source")
        == "visible_blocker_hidden_cleanup_below_final_threshold"
        and generated_exact.get("shear", {}).get("current_util") == 0.62
        and generated_exact.get("shear", {}).get("starting_util") == 0.62
        and generated_exact.get("shear", {}).get("failed_check_util") == 0.62
        and generated_exact.get("shear", {}).get("attempted_util") == 0.72
        and generated_exact.get("shear", {}).get("no_second_cta_required") is True
        and generated_exact.get("shear", {}).get("restamped") is True
        and generated_cleanup.get("shear") == generated_exact.get("shear")
        and generated_evidence.get("exact_blockers_by_family") == generated_exact
        and generated_utils == {"shear": 0.62},
        f"generated_item={generated_item} generated_utils={generated_utils}",
    )
    expect(
        "hidden_action_disabled",
        generated_item.get("button_contract") == {
            "enabled": False,
            "family": "shear",
            "blocking_reason": "visible blocker reason",
        }
        and generated_item.get("selected_action_updates") == {}
        and generated_item.get("action_type") is None
        and generated_item.get("action_payload") == {}
        and generated_item.get("resolved_candidate") == {}
        and generated_item.get("primary_card_actionable") is False,
        f"generated_item={generated_item}",
    )
    expect(
        "call_coverage",
        any(call["event"] == "exact_blocker" for call in calls)
        and any(call["event"] == "disabled_contract" for call in calls)
        and any(call["event"] == "restamp" for call in calls)
        and len([call for call in calls if call["event"] == "combined"]) >= 2,
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "combined_item": combined_item,
        "combined_best_safe": combined_best_safe,
        "combined_utils": combined_utils,
        "combined_debug": combined_debug,
        "generated_item": generated_item,
        "generated_best_safe": generated_best_safe,
        "generated_utils": generated_utils,
        "generated_debug": generated_debug,
        "calls": calls,
        "failures": failures,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Visible Blocker Completion And Promotion Verifier",
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
