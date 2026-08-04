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
        f"inputs_page_post_apply_required_checks_terminal_packaging_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_apply_required_checks_terminal_packaging_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def run_case(
        name: str,
        *,
        item: dict,
        residual_item: dict | None = None,
        residual_contract: dict | None = None,
        residual_updates: dict | None = None,
        is_residual: bool = False,
    ) -> dict:
        guidance_debug: dict = {}
        result = inputs_page.render_design_guide_post_apply_required_checks_terminal_packaging(
            post_apply_required_checks_item=dict(item),
            post_apply_residual_width_item=(
                dict(residual_item) if isinstance(residual_item, dict) else residual_item
            ),
            post_apply_residual_width_contract=dict(residual_contract or {}),
            post_apply_residual_width_updates=dict(residual_updates or {}),
            post_apply_terminal_is_residual_width_cleanup=bool(is_residual),
            dg_presentation={"before": True},
            guidance_debug=guidance_debug,
            guidance_items=[{"title": "before"}],
            render_plan={"reason": "before"},
            terminal_state="old_terminal",
            terminal_state_source="old_source",
        )
        guidance_items, render_plan, presentation, terminal_state, terminal_source = result
        case = {
            "name": name,
            "guidance_items": guidance_items,
            "render_plan": render_plan,
            "presentation": presentation,
            "terminal_state": terminal_state,
            "terminal_state_source": terminal_source,
            "debug": guidance_debug,
        }
        cases.append(case)
        return case

    terminal_item = {
        "title_main": "Design is efficient",
        "primary_action": "All required checks pass.",
    }
    case = run_case("accepted_green_terminal_packaging", item=terminal_item)
    terminal_render_item = case["guidance_items"][0]
    expect(
        "accepted_green_terminal_packaging",
        terminal_render_item["selected_family_id"] == "TARGET_BAND_REACHED"
        and case["terminal_state"] is None
        and case["terminal_state_source"] == "post_apply_required_checks_pass_terminal"
        and case["presentation"]["guidance_intent"] == "already_efficient"
        and case["presentation"]["show_apply_button"] is False
        and case["debug"]["post_click_accepted_green"] is True
        and case["debug"]["post_active_repair_green_acceptance_published"] is True
        and case["render_plan"]["reason"] == "post_apply_required_checks_pass_terminal",
        f"case={case}",
    )

    residual_item = {
        "title": "Width cleanup available",
        "primary_action": "Reduce width.",
        "button_contract": {"enabled": True, "action_type": "apply_resolved_candidate", "family": "shear"},
    }
    residual_contract = {
        "enabled": True,
        "action_type": "apply_resolved_candidate",
        "family": "shear_overdesign_governs",
    }
    residual_updates = {"b": 250}
    case = run_case(
        "residual_width_cleanup_packaging",
        item=terminal_item,
        residual_item=residual_item,
        residual_contract=residual_contract,
        residual_updates=residual_updates,
        is_residual=True,
    )
    cleanup_item = case["guidance_items"][0]
    expect(
        "residual_width_cleanup_packaging",
        cleanup_item["local_cleanup_candidate"] is True
        and cleanup_item["source"] == "render_stage_shear_overdesign_residual_width_cleanup_before_terminal"
        and cleanup_item["button_contract"] == residual_contract
        and cleanup_item["updates"] == residual_updates
        and cleanup_item["selected_action_family"] == "shear_overdesign_governs"
        and cleanup_item["selected_family_id"] == "SHEAR_OVERDESIGN_GOVERNS"
        and case["presentation"]["guidance_intent"] == "efficiency_tightening"
        and case["presentation"]["show_apply_button"] is True
        and case["debug"]["post_click_accepted_green"] is False
        and case["debug"]["post_click_design_guide_state"] == "cleanup_action_available"
        and case["debug"]["post_repair_cleanup_promotion_suppressed_reason"]
        == "residual_width_cleanup_action_available",
        f"case={case}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "cases": cases,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Apply Required Checks Terminal Packaging Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Cases",
                "",
                *[f"- `{case['name']}`" for case in cases],
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
