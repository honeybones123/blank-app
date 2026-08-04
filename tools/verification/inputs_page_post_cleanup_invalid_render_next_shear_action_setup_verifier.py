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
        f"inputs_page_post_cleanup_invalid_render_next_shear_action_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_next_shear_action_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_shear_low_util_target_cleanup_item",
        "_shear_best_safe_cleanup_item_from_evidence",
        "_shear_tightening_as_local_cleanup_item",
        "_resolve_design_actions_from_state",
        "_resolved_efficiency_target_band",
        "_design_mode_config",
        "_design_optimisation_goal",
        "_guidance_cleanup_candidate_id",
        "_guidance_item_from_resolved_candidate",
        "_format_guidance_title",
        "_resolve_recommendation_updates",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}
    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def none_cleanup(*args, **kwargs):
        calls.append({"event": "none_cleanup", "kwargs": dict(kwargs)})
        return None

    def direct_item_from_candidate(candidate, *, state, overview, title, reasoning, status, primary_action):
        calls.append(
            {
                "event": "direct_item_from_candidate",
                "candidate": dict(candidate or {}),
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "title": title,
                "reasoning": reasoning,
                "status": status,
                "primary_action": primary_action,
            }
        )
        return {
            "title_main": title,
            "title": title,
            "candidate_search_evidence": dict(candidate.get("candidate_search_evidence") or {}),
        }

    def resolve_updates(item, *, state):
        calls.append(
            {
                "event": "resolve_updates",
                "item_title": (item or {}).get("title_main") or (item or {}).get("title"),
                "state": dict(state or {}),
            }
        )
        return dict((item or {}).get("updates") or {})

    try:
        inputs_page._shear_low_util_target_cleanup_item = none_cleanup
        inputs_page._shear_best_safe_cleanup_item_from_evidence = none_cleanup
        inputs_page._shear_tightening_as_local_cleanup_item = none_cleanup
        inputs_page._resolve_design_actions_from_state = lambda state: ["existing_action"]
        inputs_page._resolved_efficiency_target_band = lambda mode_config, *, goal: (0.8, 0.95, "band")
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"
        inputs_page._guidance_cleanup_candidate_id = lambda family, updates: f"{family}_generated"
        inputs_page._guidance_item_from_resolved_candidate = direct_item_from_candidate
        inputs_page._format_guidance_title = lambda title, util: f"{title} ({util:.2f})"
        inputs_page._resolve_recommendation_updates = resolve_updates

        guidance_debug = {
            "overview": {"worst_util": 0.91},
            "candidate_search_evidence": {
                "target_band_candidates": [
                    {
                        "candidate_id": "shear_direct",
                        "preview_pass": True,
                        "safe_executor_backed": True,
                        "proposed_updates": {"link_spacing": 175},
                        "preview_util": 0.9,
                    }
                ]
            },
        }
        post_cleanup_render_audit = {"post_click_unresolved_low_util_families": ["shear"]}
        action_result = inputs_page.render_design_guide_post_cleanup_invalid_render_next_shear_action_setup(
            blocked_render_item={"family": "bending", "title": "Bending blocker"},
            guidance_debug=guidance_debug,
            guidance_disp_state={"b": 300},
            post_cleanup_render_audit=post_cleanup_render_audit,
            post_cleanup_low_families=["bending", "shear"],
            post_cleanup_shear_exact={},
            post_cleanup_shear_false_blocker_candidate_available=True,
        )

        exact_item = {
            "title": "Shear exact evidence",
            "candidate_search_evidence": {
                "exact_blockers_by_family": {
                    "shear": {"reason": "no better safe discrete candidate"}
                }
            },
        }

        def exact_cleanup(*args, **kwargs):
            calls.append({"event": "exact_cleanup"})
            return dict(exact_item)

        inputs_page._shear_low_util_target_cleanup_item = exact_cleanup
        guidance_debug_merge = {"overview": {"worst_util": 0.76}}
        post_cleanup_render_audit_merge = {
            "post_click_exact_blockers_by_family": {"bending": {"reason": "existing"}},
            "post_click_cleanup_evidence_by_family": {"bending": {"reason": "existing"}},
            "post_click_unresolved_low_util_families": ["bending", "shear"],
        }
        merge_result = inputs_page.render_design_guide_post_cleanup_invalid_render_next_shear_action_setup(
            blocked_render_item={"family": "bending", "title": "Bending blocker"},
            guidance_debug=guidance_debug_merge,
            guidance_disp_state={"b": 300},
            post_cleanup_render_audit=post_cleanup_render_audit_merge,
            post_cleanup_low_families=["bending", "shear"],
            post_cleanup_shear_exact={},
            post_cleanup_shear_false_blocker_candidate_available=False,
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    expect(
        "direct_action_result",
        action_result["family"] == "shear"
        and action_result["guidance_intent"] == "efficiency_tightening"
        and action_result["local_cleanup_candidate"] is True
        and action_result["next_unresolved_family"] == "shear"
        and action_result["next_unresolved_family_action_available"] is True
        and action_result["updates"] == {"link_spacing": 175}
        and action_result["candidate_id"] == "shear_direct"
        and action_result["button_contract"]["enabled"] is True
        and action_result["button_contract"]["expected_util"] == 0.9,
        f"action_result={action_result}",
    )
    expect(
        "direct_action_debug",
        guidance_debug["guidance_branch"] == "post_cleanup_low_shear_action_after_bending_blocker"
        and guidance_debug["selected_action_family"] == "shear"
        and guidance_debug["selected_action_type"] == "apply_resolved_candidate"
        and guidance_debug["primary_guidance_intent"] == "efficiency_tightening"
        and guidance_debug["resolved_low_util_families"] == ["shear"]
        and guidance_debug["unresolved_low_util_families"] == ["bending"],
        f"guidance_debug={guidance_debug}",
    )
    expect(
        "merge_exact_result",
        merge_result == {"family": "bending", "title": "Bending blocker"}
        and post_cleanup_render_audit_merge["post_click_exact_blockers_by_family"]["shear"]
        == {"reason": "no better safe discrete candidate"}
        and post_cleanup_render_audit_merge["cleanup_evidence_by_family"]["shear"]
        == {"reason": "no better safe discrete candidate"}
        and post_cleanup_render_audit_merge["post_click_unresolved_low_util_families"] == ["bending"]
        and guidance_debug_merge["post_click_exact_blockers_by_family"]["shear"]
        == {"reason": "no better safe discrete candidate"},
        (
            f"merge_result={merge_result} audit={post_cleanup_render_audit_merge} "
            f"debug={guidance_debug_merge}"
        ),
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "calls": calls,
        "action_result": action_result,
        "action_guidance_debug": guidance_debug,
        "merge_result": merge_result,
        "merge_guidance_debug": guidance_debug_merge,
        "merge_audit": post_cleanup_render_audit_merge,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Next Shear Action Setup Verifier",
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
