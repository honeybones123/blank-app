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
        f"inputs_page_post_cleanup_invalid_render_final_blocker_action_packaging_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_final_blocker_action_packaging_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_resolve_recommendation_updates",
        "_guidance_item_best_safe_partial_cleanup",
        "_design_guide_button_contract",
        "_design_guide_display_truth_for_item",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def resolve_updates(item, *, state):
        calls.append(
            {
                "event": "resolve_updates",
                "title": (item or {}).get("title_main"),
                "state": dict(state or {}),
            }
        )
        return dict((item or {}).get("updates") or {})

    def is_best_safe(item):
        calls.append({"event": "is_best_safe", "title": (item or {}).get("title_main")})
        return bool((item or {}).get("best_safe_partial_cleanup"))

    def button_contract(item, *, state):
        calls.append(
            {
                "event": "button_contract",
                "title": (item or {}).get("title_main"),
                "state": dict(state or {}),
            }
        )
        return {
            "enabled": True,
            "actionable": True,
            "family": "shear",
            "updates": dict((item or {}).get("updates") or {}),
        }

    def display_truth(item, *, state, overview):
        calls.append(
            {
                "event": "display_truth",
                "title": (item or {}).get("title_main"),
                "state": dict(state or {}),
                "overview": dict(overview or {}),
            }
        )
        return {"displayed_status": "EFFICIENCY", "displayed_util": 0.82}

    try:
        inputs_page._resolve_recommendation_updates = resolve_updates
        inputs_page._guidance_item_best_safe_partial_cleanup = is_best_safe
        inputs_page._design_guide_button_contract = button_contract
        inputs_page._design_guide_display_truth_for_item = display_truth

        shear_blocker = {"reason": "final shear threshold reached", "current_util": 0.61}
        blocker_debug = {}
        blocker_item, blocker_truth, blocker_is_best_safe = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_final_blocker_action_packaging(
                blocked_render_item={
                    "title_main": "Shear cleanup blocked by final efficiency threshold",
                    "candidate_search_evidence": {"existing": True},
                },
                blocked_render_title_lower="shear cleanup blocked by final efficiency threshold",
                blocked_render_truth={"displayed_status": "BLOCKED", "displayed_util": 0.61},
                shear_blocker=shear_blocker,
                shear_blocker_reason="final shear threshold reached",
                shear_blocker_util=0.61,
                guidance_debug=blocker_debug,
                guidance_disp_state={"s_lig": 300},
            )
        )
        blocker_call_count = len(calls)

        best_safe_debug = {"overview": {"utils": {"shear": 0.82}}}
        best_safe_item, best_safe_truth, best_safe_is_best_safe = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_final_blocker_action_packaging(
                blocked_render_item={
                    "title_main": "Best safe shear cleanup",
                    "action_type": "apply_resolved_candidate",
                    "best_safe_partial_cleanup": True,
                    "updates": {"s_lig": 250},
                    "candidate_search_evidence": {
                        "safe_candidate_count": 2,
                        "executable_candidate_count": 2,
                        "safe_shear_cleanup_count": 2,
                        "executable_shear_cleanup_count": 2,
                    },
                },
                blocked_render_title_lower="best safe shear cleanup",
                blocked_render_truth={"displayed_status": "OLD"},
                shear_blocker=shear_blocker,
                shear_blocker_reason="unused for action branch",
                shear_blocker_util=0.5,
                guidance_debug=best_safe_debug,
                guidance_disp_state={"s_lig": 300},
            )
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    blocker_evidence = dict(blocker_item.get("candidate_search_evidence") or {})
    blocker_contract = dict(blocker_item.get("button_contract") or {})
    expect(
        "blocker_packaging",
        blocker_is_best_safe is False
        and blocker_truth == {"displayed_status": "BLOCKED", "displayed_util": 0.61}
        and blocker_item.get("action_type") is None
        and blocker_item.get("primary_card_actionable") is False
        and blocker_item.get("guidance_intent") == "specific_blocker"
        and blocker_item.get("terminal_state_blocked_by_local_cleanup") is True
        and blocker_item.get("displayed_status") == "BLOCKED"
        and blocker_item.get("post_commit_util") == 0.61
        and blocker_evidence.get("candidate_search_exhaustive") is True
        and blocker_evidence.get("outside_target_band_allowed") is False
        and blocker_evidence.get("exact_blockers_by_family") == {"shear": shear_blocker}
        and blocker_contract.get("enabled") is False
        and blocker_contract.get("blocking_reason") == "final shear threshold reached",
        f"blocker_item={blocker_item} blocker_truth={blocker_truth}",
    )
    expect(
        "blocker_debug",
        blocker_debug.get("primary_guidance_intent") == "specific_blocker"
        and blocker_debug.get("selected_action_family") == "shear"
        and blocker_debug.get("safe_local_cleanup_count") == 0
        and blocker_debug.get("candidate_search_evidence") == blocker_evidence
        and blocker_debug.get("primary_button_contract") == blocker_contract,
        f"blocker_debug={blocker_debug}",
    )

    best_safe_contract = dict(best_safe_item.get("button_contract") or {})
    best_safe_evidence = dict(best_safe_item.get("candidate_search_evidence") or {})
    expect(
        "best_safe_action",
        best_safe_is_best_safe is True
        and best_safe_item.get("button_contract") == {
            "enabled": True,
            "actionable": True,
            "family": "shear",
            "updates": {"s_lig": 250},
        }
        and best_safe_item.get("display_truth") == {"displayed_status": "EFFICIENCY", "displayed_util": 0.82}
        and best_safe_truth == {"displayed_status": "EFFICIENCY", "displayed_util": 0.82},
        f"best_safe_item={best_safe_item} best_safe_truth={best_safe_truth}",
    )
    expect(
        "best_safe_debug",
        best_safe_debug.get("primary_guidance_intent") == "efficiency_tightening"
        and best_safe_debug.get("selected_action_family") == "shear"
        and best_safe_debug.get("selected_action_type") == "apply_resolved_candidate"
        and best_safe_debug.get("design_guide_has_actionable_recommendation") is True
        and best_safe_debug.get("candidate_search_evidence") == best_safe_evidence
        and best_safe_debug.get("primary_button_contract") == best_safe_contract
        and best_safe_debug.get("primary_display_truth") == best_safe_truth
        and best_safe_debug.get("safe_local_cleanup_count") == 2
        and best_safe_debug.get("executable_safe_cleanup_count") == 2,
        f"best_safe_debug={best_safe_debug}",
    )
    expect(
        "call_shape",
        len(calls) == blocker_call_count + 4
        and any(call["event"] == "button_contract" for call in calls[blocker_call_count:])
        and any(call["event"] == "display_truth" for call in calls[blocker_call_count:]),
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "blocker_item": blocker_item,
        "blocker_truth": blocker_truth,
        "blocker_is_best_safe": blocker_is_best_safe,
        "blocker_debug": blocker_debug,
        "best_safe_item": best_safe_item,
        "best_safe_truth": best_safe_truth,
        "best_safe_is_best_safe": best_safe_is_best_safe,
        "best_safe_debug": best_safe_debug,
        "calls": calls,
        "failures": failures,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Final Blocker Action Packaging Verifier",
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
