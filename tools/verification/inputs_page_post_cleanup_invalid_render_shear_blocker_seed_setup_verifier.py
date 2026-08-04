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
        f"inputs_page_post_cleanup_invalid_render_shear_blocker_seed_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_shear_blocker_seed_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_updates_match_state": inputs_page._updates_match_state,
        "_guidance_cleanup_candidate_id": inputs_page._guidance_cleanup_candidate_id,
    }
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def updates_match_state(state, updates):
        calls.append({"event": "updates_match_state", "state": dict(state or {}), "updates": dict(updates or {})})
        return False

    try:
        inputs_page._updates_match_state = updates_match_state
        inputs_page._guidance_cleanup_candidate_id = (
            lambda family, updates: f"{family}_generated_{len(updates)}"
        )

        available_debug = {
            "overview": {"utils": {"shear": 0.62}},
            "candidate_search_evidence": {
                "family": "shear",
                "best_safe_candidate_updates": {"s_lig": 275},
                "best_safe_final_util": 0.86,
                "one_click_target_reaching_candidate_exists": True,
                "safe_candidate_count": 2,
                "executable_candidate_count": 3,
                "executable_cleanup_count": 4,
                "executable_shear_cleanup_count": 5,
            },
        }
        available_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_seed_setup(
            blocked_render_reason="fallback reason",
            guidance_debug=available_debug,
            guidance_disp_state={"s_lig": 300},
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {
                    "shear": {
                        "reason": "exact shear reason",
                        "current_util": 0.61,
                    }
                }
            },
        )

        fallback_debug = {"overview": {"utils": {"shear": 0.52}}, "candidate_search_evidence": {}}
        fallback_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_seed_setup(
            blocked_render_reason="fallback reason",
            guidance_debug=fallback_debug,
            guidance_disp_state={"s_lig": 300},
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {
                    "shear": {
                        "why_reduction_would_hurt_other_design_elements": "cannot reduce further",
                        "attempted_updates": {"lig_d": 10},
                    }
                }
            },
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    (
        shear_blocker,
        outer_safe_shear_evidence,
        outer_safe_shear_updates,
        outer_safe_shear_expected,
        outer_safe_shear_cleanup_available,
        shear_blocker_reason,
        shear_blocker_util,
        best_safe_updates,
        best_safe_already_applied,
    ) = available_result
    expect(
        "available_path",
        outer_safe_shear_cleanup_available is True
        and outer_safe_shear_updates == {"s_lig": 275}
        and outer_safe_shear_expected == 0.86
        and shear_blocker["best_safe_candidate_updates"] == {"s_lig": 275}
        and shear_blocker["selected_candidate_updates"] == {"s_lig": 275}
        and shear_blocker["best_safe_candidate_applied"] is False
        and shear_blocker["no_second_cta_required"] is False
        and shear_blocker["safe_candidate_count"] == 2
        and shear_blocker["executable_candidate_count"] == 3
        and shear_blocker["executable_cleanup_count"] == 4
        and shear_blocker["executable_shear_cleanup_count"] == 5
        and shear_blocker["local_cleanup_search_ran"] is True
        and shear_blocker["failed_candidate_id"] == "shear_generated_1"
        and shear_blocker["target_low"] == float(inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL)
        and shear_blocker["target_high"] == float(inputs_page.EFFICIENCY_TARGET_UTIL_MAX)
        and shear_blocker["failed_check_util"] == 0.61
        and shear_blocker_reason == "exact shear reason"
        and shear_blocker_util == 0.61
        and best_safe_updates == {"s_lig": 275}
        and best_safe_already_applied is False,
        f"available_result={available_result}",
    )

    (
        fallback_blocker,
        _fallback_evidence,
        fallback_updates,
        fallback_expected,
        fallback_available,
        fallback_reason,
        fallback_util,
        fallback_best_updates,
        fallback_already_applied,
    ) = fallback_result
    expect(
        "fallback_path",
        fallback_available is False
        and fallback_updates == {}
        and fallback_expected is None
        and fallback_blocker["best_safe_candidate_applied"] is True
        and fallback_blocker["no_second_cta_required"] is True
        and fallback_blocker["executable_target_band_candidate_count"] == 0
        and fallback_blocker["failed_candidate_id"] == "shear_generated_1"
        and fallback_reason == "cannot reduce further"
        and fallback_util == 0.52
        and fallback_best_updates == {"lig_d": 10}
        and fallback_already_applied is False,
        f"fallback_result={fallback_result}",
    )
    expect(
        "updates_match_calls",
        len(calls) == 3
        and calls[0]["updates"] == {"s_lig": 275}
        and calls[1]["updates"] == {"s_lig": 275}
        and calls[2]["updates"] == {"lig_d": 10},
        f"calls={calls}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "calls": calls,
        "available_result": {
            "shear_blocker": shear_blocker,
            "outer_safe_shear_evidence": outer_safe_shear_evidence,
            "outer_safe_shear_updates": outer_safe_shear_updates,
            "outer_safe_shear_expected": outer_safe_shear_expected,
            "outer_safe_shear_cleanup_available": outer_safe_shear_cleanup_available,
            "shear_blocker_reason": shear_blocker_reason,
            "shear_blocker_util": shear_blocker_util,
            "best_safe_updates": best_safe_updates,
            "best_safe_already_applied": best_safe_already_applied,
        },
        "fallback_result": {
            "shear_blocker": fallback_blocker,
            "outer_safe_shear_updates": fallback_updates,
            "outer_safe_shear_expected": fallback_expected,
            "outer_safe_shear_cleanup_available": fallback_available,
            "shear_blocker_reason": fallback_reason,
            "shear_blocker_util": fallback_util,
            "best_safe_updates": fallback_best_updates,
            "best_safe_already_applied": fallback_already_applied,
        },
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Shear Blocker Seed Setup Verifier",
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
