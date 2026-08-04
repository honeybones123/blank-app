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
        f"inputs_page_post_cleanup_intent_action_preferred_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_intent_action_preferred_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_guidance_item": inputs_page._guidance_item,
        "_guidance_cleanup_candidate_id": inputs_page._guidance_cleanup_candidate_id,
        "_attach_family_status_display_payload": inputs_page._attach_family_status_display_payload,
    }
    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def guidance_item(
        family,
        title,
        summary,
        primary_action,
        why,
        key_checks,
        arg7,
        arg8,
        *,
        status,
        util,
    ):
        calls.append(
            {
                "event": "guidance_item",
                "family": family,
                "title": title,
                "summary": summary,
                "primary_action": primary_action,
                "why": why,
                "key_checks": key_checks,
                "status": status,
                "util": util,
            }
        )
        return {
            "family": family,
            "title_main": title,
            "title": title,
            "status": status,
            "util": util,
        }

    def attach_family_status_display_payload(item, *, state):
        calls.append(
            {
                "event": "attach_family_status_display_payload",
                "item": dict(item or {}),
                "state": dict(state or {}),
            }
        )
        item = dict(item or {})
        display_truth = dict(item.get("display_truth") or {})
        display_truth["attached"] = True
        item["display_truth"] = display_truth
        return item

    try:
        inputs_page._guidance_item = guidance_item
        inputs_page._guidance_cleanup_candidate_id = (
            lambda family, updates: f"{family}_generated_from_{len(updates)}"
        )
        inputs_page._attach_family_status_display_payload = attach_family_status_display_payload

        guidance_debug = {
            "candidate_search_evidence": {
                "selected_candidate_util": 0.86,
                "selected_candidate_id": "evidence_candidate",
                "reason": "evidence reason",
                "exact_blockers_by_family": {
                    "shear": {
                        "reason": "exact shear reason",
                        "best_safe_final_util": 0.86,
                    }
                },
            },
        }
        action_result = inputs_page.render_design_guide_post_cleanup_intent_action_preferred_setup(
            blocked_render_item={"family": "bending", "title": "Bending blocker"},
            blocked_render_is_best_safe_action=False,
            blocked_render_reason="original_reason",
            blocked_render_truth={"original": True},
            guidance_debug=guidance_debug,
            guidance_disp_state={"b": 300},
            intent_contract={
                "family": "shear",
                "updates": {"link_spacing": 175},
            },
            intent_row={"title": "Shear cleanup row", "check_key": "shear"},
            intent_family="shear",
            intent_low_families={"shear"},
            current_strength_fail_for_intent=set(),
            intent_target_contract_blocked=False,
        )
        noop_debug = {}
        noop_result = inputs_page.render_design_guide_post_cleanup_intent_action_preferred_setup(
            blocked_render_item={"family": "bending", "title": "Bending blocker"},
            blocked_render_is_best_safe_action=False,
            blocked_render_reason="original_reason",
            blocked_render_truth={"original": True},
            guidance_debug=noop_debug,
            guidance_disp_state={"b": 300},
            intent_contract={"family": "shear", "updates": {"link_spacing": 175}},
            intent_row={"title": "Shear cleanup row", "check_key": "shear"},
            intent_family="shear",
            intent_low_families={"shear"},
            current_strength_fail_for_intent={"shear"},
            intent_target_contract_blocked=False,
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    (
        blocked_render_item,
        blocked_render_is_best_safe_action,
        blocked_render_reason,
        blocked_render_contract,
        blocked_render_truth,
    ) = action_result
    expect(
        "action_item_stamped",
        blocked_render_item["title_main"] == "Shear cleanup row"
        and blocked_render_item["guidance_intent"] == "efficiency_tightening"
        and blocked_render_item["local_cleanup_candidate"] is True
        and blocked_render_item["best_safe_partial_cleanup"] is True
        and blocked_render_item["family"] == "shear"
        and blocked_render_item["updates"] == {"link_spacing": 175}
        and blocked_render_item["candidate_id"] == "evidence_candidate"
        and blocked_render_item["button_contract"]["enabled"] is True
        and blocked_render_item["button_contract"]["action_type"] == "apply_resolved_candidate"
        and blocked_render_item["action_payload"]["resolved_candidate_updates"] == {"link_spacing": 175}
        and blocked_render_item["resolved_candidate"]["candidate_post_util"] == 0.86,
        f"blocked_render_item={blocked_render_item}",
    )
    expect(
        "returned_state",
        blocked_render_is_best_safe_action is True
        and blocked_render_reason == "post_cleanup_invalid_render_action_preferred"
        and blocked_render_contract["family"] == "shear"
        and blocked_render_truth["attached"] is True,
        f"action_result={action_result}",
    )
    expect(
        "debug_stamps",
        guidance_debug["guidance_branch"] == "post_cleanup_invalid_render_low_util_action_preferred"
        and guidance_debug["terminal_state_blocked_by_local_cleanup"] is False
        and guidance_debug["selected_action_family"] == "shear"
        and guidance_debug["selected_action_type"] == "apply_resolved_candidate"
        and guidance_debug["selected_title"] == "Shear cleanup row"
        and guidance_debug["primary_guidance_intent"] == "efficiency_tightening",
        f"guidance_debug={guidance_debug}",
    )
    expect(
        "noop_gate",
        noop_result
        == (
            {"family": "bending", "title": "Bending blocker"},
            False,
            "original_reason",
            {},
            {"original": True},
        )
        and noop_debug == {},
        f"noop_result={noop_result} noop_debug={noop_debug}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "calls": calls,
        "action_result": {
            "blocked_render_item": blocked_render_item,
            "blocked_render_is_best_safe_action": blocked_render_is_best_safe_action,
            "blocked_render_reason": blocked_render_reason,
            "blocked_render_contract": blocked_render_contract,
            "blocked_render_truth": blocked_render_truth,
        },
        "guidance_debug": guidance_debug,
        "noop_result": list(noop_result),
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Intent Action Preferred Setup Verifier",
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
