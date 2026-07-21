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
        f"inputs_page_post_cleanup_invalid_render_final_safe_shear_action_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_final_safe_shear_action_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_candidate_preview_statuses_have_explicit_fail",
        "_evaluate_auto_design_candidate",
        "_overview_required_checks_acceptable",
        "_guidance_cleanup_candidate_id",
        "_guidance_item_from_resolved_candidate",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def preview_has_fail(statuses):
        calls.append({"event": "preview_has_fail", "statuses": dict(statuses or {})})
        return False

    def evaluate_candidate(state, *, updates, source, label, action_type):
        calls.append(
            {
                "event": "evaluate_candidate",
                "state": dict(state or {}),
                "updates": dict(updates or {}),
                "source": source,
                "label": label,
                "action_type": action_type,
            }
        )
        return {
            "overview": {"any_fail": False, "statuses": {}, "worst_util": 0.89},
            "candidate_post_util": 0.91,
        }

    def required_checks_acceptable(overview):
        calls.append({"event": "required_checks_acceptable", "overview": dict(overview or {})})
        return True

    def guidance_item_from_candidate(candidate, *, state, overview, title, reasoning, status, primary_action):
        candidate_copy = dict(candidate or {})
        calls.append(
            {
                "event": "guidance_item_from_candidate",
                "candidate": candidate_copy,
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
            "action_type": candidate_copy.get("action_type"),
            "action_payload": {"updates": dict(candidate_copy.get("updates") or {})},
            "resolved_candidate": {"updates": dict(candidate_copy.get("updates") or {})},
        }

    try:
        inputs_page._candidate_preview_statuses_have_explicit_fail = preview_has_fail
        inputs_page._evaluate_auto_design_candidate = evaluate_candidate
        inputs_page._overview_required_checks_acceptable = required_checks_acceptable
        inputs_page._guidance_cleanup_candidate_id = lambda family, updates: f"{family}_generated"
        inputs_page._guidance_item_from_resolved_candidate = guidance_item_from_candidate

        blocked_item = {
            "title_main": "Shear cleanup blocked by final efficiency threshold",
            "candidate_search_evidence": {
                "closest_safe_candidate_id": "safe-1",
                "safe_candidate_count": 1,
                "executable_candidate_count": 1,
                "exact_blockers_by_family": {"bending": {"reason": "bending exact blocker"}},
                "candidate_rows": [
                    {
                        "candidate_id": "safe-1",
                        "safe_executor_backed": True,
                        "is_executable": True,
                        "preview_pass": True,
                        "proposed_updates": {"s_lig": 250},
                        "preview_util": 0.91,
                        "preview_statuses": {},
                        "title": "Shear repair row",
                    },
                    {
                        "candidate_id": "unsafe",
                        "safe_executor_backed": False,
                        "is_executable": True,
                        "preview_pass": True,
                        "proposed_updates": {"s_lig": 225},
                    },
                ],
            },
        }
        active_item, active_title = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_final_safe_shear_action_setup(
                blocked_render_item=blocked_item,
                blocked_render_title_lower="shear cleanup blocked by final efficiency threshold",
                guidance_debug={"overview": {"utils": {"shear": 0.52}}},
                guidance_disp_state={"s_lig": 300, "lig_d": 12},
            )
        )
        active_call_count = len(calls)

        unchanged_item = {"title_main": "Other blocker"}
        gated_item, gated_title = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_final_safe_shear_action_setup(
                blocked_render_item=unchanged_item,
                blocked_render_title_lower="other blocker",
                guidance_debug={},
                guidance_disp_state={},
            )
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    evaluate_calls = [call for call in calls if call["event"] == "evaluate_candidate"]
    guidance_calls = [call for call in calls if call["event"] == "guidance_item_from_candidate"]
    candidate = dict(guidance_calls[0].get("candidate") or {}) if guidance_calls else {}
    evidence = dict(candidate.get("candidate_search_evidence") or {})
    payload = dict(active_item.get("action_payload") or {}) if isinstance(active_item, dict) else {}
    resolved = dict(active_item.get("resolved_candidate") or {}) if isinstance(active_item, dict) else {}

    expect(
        "active_item",
        isinstance(active_item, dict)
        and active_item.get("title_main") == "Shear capacity is low"
        and active_item.get("guidance_intent") == "required_fix"
        and active_item.get("primary_card_actionable") is True
        and active_item.get("best_safe_partial_cleanup") is True
        and active_item.get("no_second_cta_required") is False
        and active_title == "shear capacity is low",
        f"active_item={active_item} active_title={active_title}",
    )
    expect(
        "candidate_eval",
        len(evaluate_calls) == 1
        and evaluate_calls[0]["updates"] == {"s_lig": 250}
        and evaluate_calls[0]["source"] == "final_selected_shear_active_fail_safe_row_action"
        and evaluate_calls[0]["label"] == "Shear repair row"
        and evaluate_calls[0]["action_type"] == "apply_resolved_candidate",
        f"evaluate_calls={evaluate_calls}",
    )
    expect(
        "candidate_evidence",
        candidate.get("candidate_id") == "safe-1"
        and candidate.get("source_candidate_id") == "safe-1"
        and candidate.get("updates") == {"s_lig": 250}
        and candidate.get("family") == "shear"
        and candidate.get("recommendation_family_tag") == "shear"
        and evidence.get("safe_executor_backed_candidates_count") == 1
        and evidence.get("safe_candidate_count") == 1
        and evidence.get("executable_candidate_count") == 1
        and evidence.get("selected_candidate_id") == "safe-1"
        and evidence.get("best_safe_candidate_updates") == {"s_lig": 250}
        and evidence.get("best_safe_final_util") == 0.91,
        f"candidate={candidate}",
    )
    expect(
        "item_payloads",
        active_item.get("candidate_search_evidence") == evidence
        and active_item.get("exact_blockers_by_family") == {"bending": {"reason": "bending exact blocker"}}
        and payload.get("candidate_search_evidence") == evidence
        and resolved.get("candidate_search_evidence") == evidence,
        f"active_item={active_item}",
    )
    expect(
        "gated_noop",
        gated_item is unchanged_item
        and gated_title == "other blocker"
        and len(calls) == active_call_count,
        f"gated_item={gated_item} gated_title={gated_title} calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "active_item": active_item,
        "active_title": active_title,
        "gated_item": gated_item,
        "gated_title": gated_title,
        "calls": calls,
        "failures": failures,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Final Safe Shear Action Setup Verifier",
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
