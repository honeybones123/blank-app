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
        f"inputs_page_post_cleanup_invalid_render_best_safe_shear_action_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_best_safe_shear_action_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_evaluate_auto_design_candidate",
        "_design_mode_config",
        "_design_optimisation_goal",
        "_guidance_item_from_resolved_candidate",
        "_run_design_guide_combined_low_util_orchestration",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

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
        return {"overview": {"utils": {"shear": 0.86}}}

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
            "family": "shear",
            "action_payload": {"updates": dict(candidate_copy.get("updates") or {})},
            "resolved_candidate": {"updates": dict(candidate_copy.get("updates") or {})},
            "candidate_search_evidence": dict(candidate_copy.get("candidate_search_evidence") or {}),
        }

    def combined_orchestration(**kwargs):
        shear_item = dict(kwargs.get("shear_item") or {})
        calls.append(
            {
                "event": "combined_orchestration",
                "mode_config": dict(kwargs.get("mode_config") or {}),
                "shear_item": shear_item,
            }
        )
        return {
            "debug_update": {"combined_best_safe_debug": True},
            "item": {"title_main": "Combined best-safe replacement", "combined": True},
        }

    try:
        inputs_page._evaluate_auto_design_candidate = evaluate_candidate
        inputs_page._design_mode_config = lambda goal: {"target_high": 0.95, "goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"
        inputs_page._guidance_item_from_resolved_candidate = guidance_item_from_candidate
        inputs_page._run_design_guide_combined_low_util_orchestration = combined_orchestration

        guidance_debug = {"overview": {"utils": {"shear": 0.62}}}
        active_result = inputs_page.render_design_guide_post_cleanup_invalid_render_best_safe_shear_action_setup(
            best_safe_updates={"s_lig": 250},
            best_safe_already_applied=False,
            shear_links_at_detailing_floor=False,
            shear_blocker={
                "safe_candidate_count": 2,
                "executable_candidate_count": 3,
                "executable_cleanup_count": 4,
                "safe_shear_cleanup_count": 5,
                "executable_shear_cleanup_count": 6,
                "failed_candidate_reasons": ["safe candidate still below target"],
            },
            shear_blocker_reason="no material candidate reached target",
            shear_blocker_util=0.61,
            outer_safe_shear_cleanup_available=True,
            guidance_debug=guidance_debug,
            guidance_disp_state={"s_lig": 300, "lig_d": 12, "lig_legs": 2},
        )

        gated_result = inputs_page.render_design_guide_post_cleanup_invalid_render_best_safe_shear_action_setup(
            best_safe_updates={"s_lig": 250},
            best_safe_already_applied=True,
            shear_links_at_detailing_floor=False,
            shear_blocker={},
            shear_blocker_reason="already applied",
            shear_blocker_util=0.5,
            outer_safe_shear_cleanup_available=False,
            guidance_debug={},
            guidance_disp_state={"s_lig": 250},
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    evaluate_calls = [call for call in calls if call["event"] == "evaluate_candidate"]
    item_calls = [call for call in calls if call["event"] == "guidance_item_from_candidate"]
    combined_calls = [call for call in calls if call["event"] == "combined_orchestration"]
    candidate = item_calls[0]["candidate"] if item_calls else {}
    evidence = dict(candidate.get("candidate_search_evidence") or {})
    shear_item = dict(combined_calls[0].get("shear_item") or {}) if combined_calls else {}
    shear_payload = dict(shear_item.get("action_payload") or {})
    shear_resolved = dict(shear_item.get("resolved_candidate") or {})

    expect(
        "active_result_replaced_by_combined_item",
        active_result == {"title_main": "Combined best-safe replacement", "combined": True},
        f"active_result={active_result}",
    )
    expect(
        "active_evaluate_call",
        len(evaluate_calls) == 1
        and evaluate_calls[0]["updates"] == {"s_lig": 250}
        and evaluate_calls[0]["source"] == "post_cleanup_low_shear_best_safe_action"
        and evaluate_calls[0]["action_type"] == "apply_resolved_candidate",
        f"evaluate_calls={evaluate_calls}",
    )
    expect(
        "candidate_stamped",
        candidate.get("updates") == {"s_lig": 250}
        and candidate.get("action_type") == "apply_resolved_candidate"
        and candidate.get("best_safe_partial_cleanup") is True
        and candidate.get("no_second_cta_required") is False
        and candidate.get("family") == "shear"
        and candidate.get("subfamilies") == ["shear"]
        and candidate.get("local_cleanup_candidate") is True
        and evidence.get("best_safe_final_util") == 0.86
        and evidence.get("starting_util") == 0.61
        and evidence.get("target_high") == 0.95
        and evidence.get("best_safe_candidate_updates") == {"s_lig": 250}
        and evidence.get("failed_candidate_reasons") == ["safe candidate still below target"],
        f"candidate={candidate}",
    )
    expect(
        "shear_item_stamped_for_combined_orchestration",
        shear_item.get("guidance_intent") == "efficiency_tightening"
        and shear_item.get("local_cleanup_candidate") is True
        and shear_item.get("best_safe_partial_cleanup") is True
        and shear_item.get("no_second_cta_required") is False
        and shear_payload.get("candidate_search_evidence") == evidence
        and shear_payload.get("best_safe_partial_cleanup") is True
        and shear_resolved.get("candidate_search_evidence") == evidence
        and shear_resolved.get("no_second_cta_required") is False,
        f"shear_item={shear_item}",
    )
    expect(
        "debug_update",
        guidance_debug.get("combined_best_safe_debug") is True,
        f"guidance_debug={guidance_debug}",
    )
    expect(
        "gated_result_no_extra_calls",
        gated_result is None and len(calls) == 3,
        f"gated_result={gated_result} calls={calls}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "active_result": active_result,
        "gated_result": gated_result,
        "guidance_debug": guidance_debug,
        "calls": calls,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Best Safe Shear Action Setup Verifier",
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
