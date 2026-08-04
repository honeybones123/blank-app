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
        f"inputs_page_post_cleanup_invalid_render_initial_blocker_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_initial_blocker_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_post_click_low_bending_resolution_item": inputs_page._post_click_low_bending_resolution_item,
        "_visible_safe_low_util_cleanup_action_from_evidence": inputs_page._visible_safe_low_util_cleanup_action_from_evidence,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_updates_match_state": inputs_page._updates_match_state,
    }
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def blocker_item(state, overview, mode_config, audit, *, debug_sink):
        calls.append(
            {
                "event": "blocker_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "mode_config": dict(mode_config or {}),
                "audit": dict(audit or {}),
                "debug_sink_id": id(debug_sink),
            }
        )
        return {"family": "bending", "title": "Bending blocker"}

    def safe_low_util_action(item, overview, state, *, debug_sink):
        calls.append(
            {
                "event": "safe_low_util_action",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "state": dict(state or {}),
                "debug_sink_id": id(debug_sink),
            }
        )
        return {"family": "shear", "title": "Promoted shear cleanup"}

    def updates_match_state(state, updates):
        calls.append(
            {
                "event": "updates_match_state",
                "state": dict(state or {}),
                "updates": dict(updates or {}),
            }
        )
        return False

    guidance_debug = {"overview": {"worst_util": 0.72, "governing_util": 0.91}}
    post_cleanup_render_audit = {
        "post_click_accepted_green_invalid_reason": "custom_invalid_reason",
        "post_click_exact_blockers_by_family": {
            "shear": {
                "best_safe_candidate_updates": {"link_spacing": 175},
                "best_safe_candidate_applied": False,
                "safe_candidate_count": 1,
            }
        },
    }

    try:
        inputs_page._post_click_low_bending_resolution_item = blocker_item
        inputs_page._visible_safe_low_util_cleanup_action_from_evidence = safe_low_util_action
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"
        inputs_page._updates_match_state = updates_match_state
        result = inputs_page.render_design_guide_post_cleanup_invalid_render_initial_blocker_setup(
            guidance_debug=guidance_debug,
            guidance_disp_state={"b": 300},
            post_cleanup_render_audit=post_cleanup_render_audit,
            post_cleanup_low_families=["shear"],
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    (
        blocked_render_is_best_safe_action,
        blocked_render_util,
        blocked_render_truth,
        blocked_render_reason,
        blocked_render_item,
        post_cleanup_shear_exact,
        post_cleanup_shear_false_blocker_candidate_available,
        post_cleanup_shear_unresolved,
    ) = result
    expect(
        "returned_blocker_setup",
        blocked_render_is_best_safe_action is True
        and blocked_render_util == 0.72
        and blocked_render_truth == {}
        and blocked_render_reason == "custom_invalid_reason"
        and blocked_render_item == {"family": "shear", "title": "Promoted shear cleanup"},
        f"result={result}",
    )
    expect(
        "shear_predicate",
        post_cleanup_shear_exact == {
            "best_safe_candidate_updates": {"link_spacing": 175},
            "best_safe_candidate_applied": False,
            "safe_candidate_count": 1,
        }
        and post_cleanup_shear_false_blocker_candidate_available is True
        and post_cleanup_shear_unresolved is True,
        f"result={result}",
    )
    expect(
        "debug_and_calls",
        guidance_debug["post_cleanup_blocker_promoted_to_safe_low_util_action"] is True
        and [call["event"] for call in calls]
        == ["blocker_item", "safe_low_util_action", "updates_match_state"],
        f"guidance_debug={guidance_debug} calls={calls}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "calls": calls,
        "result": {
            "blocked_render_is_best_safe_action": blocked_render_is_best_safe_action,
            "blocked_render_util": blocked_render_util,
            "blocked_render_truth": blocked_render_truth,
            "blocked_render_reason": blocked_render_reason,
            "blocked_render_item": blocked_render_item,
            "post_cleanup_shear_exact": post_cleanup_shear_exact,
            "post_cleanup_shear_false_blocker_candidate_available": post_cleanup_shear_false_blocker_candidate_available,
            "post_cleanup_shear_unresolved": post_cleanup_shear_unresolved,
        },
        "guidance_debug": guidance_debug,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Initial Blocker Setup Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
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
                "verdict": payload["verdict"],
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
