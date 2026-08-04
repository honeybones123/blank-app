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


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_debug_bundle_stamping_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_debug_bundle_stamping_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    fake_st = FakeStreamlit()
    original_st = inputs_page.st
    original_candidate_family = inputs_page._design_guide_candidate_family

    def candidate_family(item):
        calls.append({"event": "candidate_family", "item": dict(item or {})})
        return str((item or {}).get("family") or "bending")

    def restamp_maps(evidence):
        calls.append({"event": "restamp_maps", "evidence": dict(evidence or {})})
        out = dict(evidence or {})
        out["maps_restamped"] = True
        return out

    def restamp_current(exact):
        calls.append({"event": "restamp_current", "exact": dict(exact or {})})
        return {
            family: {**dict(blocker), "current_restamped": True}
            for family, blocker in dict(exact or {}).items()
        }

    try:
        inputs_page.st = fake_st
        inputs_page._design_guide_candidate_family = candidate_family
        (
            visible_utils,
            evidence,
            exact,
            cleanup,
        ) = inputs_page.render_design_guide_post_cleanup_invalid_render_debug_bundle_stamping(
            blocked_render_item={
                "title_main": "Blocked shear cleanup",
                "action_type": "apply",
                "guidance_intent": "specific_blocker",
                "family": "shear",
                "post_click_exact_blockers_by_family": {"shear": {"reason": "post exact"}},
                "post_click_cleanup_evidence_by_family": {"shear": {"reason": "post cleanup"}},
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": False,
                "safe_local_cleanup_count": 1,
                "executable_safe_cleanup_count": 0,
            },
            blocked_render_contract={
                "enabled": False,
                "updates": {"s_lig": 250},
                "preview_pass": False,
            },
            blocked_render_truth_for_bundle={
                "displayed_util": 0.62,
                "displayed_status": "BLOCKED",
                "display_truth_source": "post_commit_truth",
                "source_summary_util": 0.7,
                "source_candidate_util": 0.72,
                "source_post_commit_util": 0.62,
            },
            blocked_render_evidence_for_bundle={"source": "evidence"},
            blocked_render_exact_blockers_for_bundle={"shear": {"reason": "exact"}},
            blocked_render_cleanup_evidence_for_bundle={"shear": {"reason": "cleanup"}},
            blocked_render_engine_decision_for_bundle={
                "card": {"title": "Blocked shear cleanup"},
                "debug": {"candidate_search_evidence": {"source": "debug"}},
            },
            blocked_render_is_best_safe_action=False,
            blocked_render_rewritten_to_active_green=False,
            blocked_render_reason="visible blocker reason",
            guidance_debug={"overview": {"utils": {"shear": 0.62, "bending": 0.9}}},
            dg_overview={},
            visible_utils_for_exact_blockers={},
            restamp_exact_blocker_maps_in_evidence_fn=restamp_maps,
            restamp_exact_blocker_current_utils_fn=restamp_current,
        )
    finally:
        inputs_page.st = original_st
        inputs_page._design_guide_candidate_family = original_candidate_family

    debug_bundle = dict(fake_st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})
    engine_decision = dict(debug_bundle.get("design_guide_engine_decision") or {})
    engine_card = dict(engine_decision.get("card") or {})
    engine_debug = dict(engine_decision.get("debug") or {})

    expect(
        "returned_restamped_payloads",
        visible_utils == {"shear": 0.62, "bending": 0.9}
        and evidence.get("maps_restamped") is True
        and exact.get("shear", {}).get("current_restamped") is True
        and cleanup.get("shear", {}).get("current_restamped") is True,
        f"visible_utils={visible_utils} evidence={evidence} exact={exact} cleanup={cleanup}",
    )
    expect(
        "session_debug_bundle",
        debug_bundle.get("selected_title") == "Blocked shear cleanup"
        and debug_bundle.get("selected_action_family") == "shear"
        and debug_bundle.get("button_contract_enabled") is False
        and debug_bundle.get("displayed_util") == 0.62
        and debug_bundle.get("terminal_state_blocked_by_local_cleanup") is True
        and debug_bundle.get("terminal_state_block_reason") == "visible blocker reason"
        and debug_bundle.get("design_guide_terminal_state") is None
        and debug_bundle.get("design_guide_terminal_positive") is False
        and debug_bundle.get("design_guide_has_actionable_recommendation") is False,
        f"debug_bundle={debug_bundle}",
    )
    expect(
        "engine_decision_restamped",
        engine_card.get("maps_restamped") is True
        and engine_debug.get("maps_restamped") is True
        and debug_bundle.get("exact_blockers_by_family") == exact
        and debug_bundle.get("cleanup_evidence_by_family") == cleanup,
        f"engine_decision={engine_decision} debug_bundle={debug_bundle}",
    )
    expect(
        "call_coverage",
        len([call for call in calls if call["event"] == "restamp_maps"]) >= 3
        and len([call for call in calls if call["event"] == "restamp_current"]) == 2
        and len([call for call in calls if call["event"] == "candidate_family"]) >= 2,
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "visible_utils": visible_utils,
        "debug_bundle": debug_bundle,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Debug Bundle Stamping Verifier",
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
