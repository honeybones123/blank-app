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
    json_path = (
        ARTIFACT_DIR
        / f"inputs_page_primary_low_bending_resolution_replacement_handoff_{timestamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"inputs_page_primary_low_bending_resolution_replacement_handoff_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_enabled = inputs_page._design_guide_button_contract_enabled

    def enabled(contract):
        contract = dict(contract or {})
        calls.append({"event": "contract_enabled", "contract": contract})
        return bool(contract.get("enabled"))

    try:
        inputs_page._design_guide_button_contract_enabled = enabled

        primary_render_items = [{"title": "old primary"}]
        guidance_items = [{"title": "old guidance"}]
        render_plan = {"visible_guidance_items": [{"title": "old visible"}], "reason": "old"}
        presentation = {"headline": "Target achieved"}
        guidance_debug = {}
        replacement = {
            "title_main": "Resolve bending blocker",
            "title": "Fallback title",
            "button_contract": {"enabled": False, "reason": "blocked"},
        }
        (
            replaced_primary,
            replaced_guidance,
            replaced_plan,
            replaced_presentation,
            replaced_debug,
        ) = inputs_page.render_design_guide_primary_low_bending_resolution_replacement_handoff(
            primary_bending_resolution=replacement,
            primary_render_items=primary_render_items,
            guidance_items=guidance_items,
            render_plan=render_plan,
            dg_presentation=presentation,
            guidance_debug=guidance_debug,
        )

        untouched_primary = [{"title": "keep primary"}]
        untouched_guidance = [{"title": "keep guidance"}]
        untouched_plan = {"visible_guidance_items": [{"title": "keep visible"}], "reason": "keep"}
        untouched_presentation = {"headline": "Accepted"}
        untouched_debug = {"existing": True}
        (
            enabled_primary,
            enabled_guidance,
            enabled_plan,
            enabled_presentation,
            enabled_debug,
        ) = inputs_page.render_design_guide_primary_low_bending_resolution_replacement_handoff(
            primary_bending_resolution={
                "title_main": "Enabled action",
                "button_contract": {"enabled": True},
            },
            primary_render_items=untouched_primary,
            guidance_items=untouched_guidance,
            render_plan=untouched_plan,
            dg_presentation=untouched_presentation,
            guidance_debug=untouched_debug,
        )
    finally:
        inputs_page._design_guide_button_contract_enabled = original_enabled

    expect(
        "replacement_primary",
        replaced_primary == [replacement]
        and replaced_guidance == [replacement]
        and replaced_plan.get("visible_guidance_items") == [replacement]
        and replaced_plan.get("reason") == "post_click_low_bending_exact_blocker_primary_render",
        (
            f"primary={replaced_primary} guidance={replaced_guidance} "
            f"plan={replaced_plan}"
        ),
    )
    expect(
        "replacement_debug",
        replaced_presentation == {}
        and replaced_debug.get("post_click_low_bending_action_replaced_by_exact_blocker") is True
        and replaced_debug.get("guidance_branch")
        == "post_click_low_bending_exact_blocker_primary_render"
        and replaced_debug.get("selected_title") == "Resolve bending blocker"
        and replaced_debug.get("selected_action_type") is None
        and replaced_debug.get("selected_action_family") == "bending"
        and replaced_debug.get("button_contract") == {"enabled": False, "reason": "blocked"}
        and replaced_debug.get("button_contract_enabled") is False,
        f"presentation={replaced_presentation} debug={replaced_debug}",
    )
    expect(
        "enabled_contract_passthrough",
        enabled_primary == untouched_primary
        and enabled_guidance == untouched_guidance
        and enabled_plan == untouched_plan
        and enabled_presentation == untouched_presentation
        and enabled_debug == untouched_debug,
        (
            f"primary={enabled_primary} guidance={enabled_guidance} plan={enabled_plan} "
            f"presentation={enabled_presentation} debug={enabled_debug}"
        ),
    )
    expect(
        "call_coverage",
        calls
        == [
            {"event": "contract_enabled", "contract": {"enabled": False, "reason": "blocked"}},
            {"event": "contract_enabled", "contract": {"enabled": True}},
        ],
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "replaced_primary": replaced_primary,
        "replaced_guidance": replaced_guidance,
        "replaced_plan": replaced_plan,
        "replaced_presentation": replaced_presentation,
        "replaced_debug": replaced_debug,
        "enabled_primary": enabled_primary,
        "enabled_guidance": enabled_guidance,
        "enabled_plan": enabled_plan,
        "enabled_presentation": enabled_presentation,
        "enabled_debug": enabled_debug,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Low Bending Resolution Replacement Handoff Verifier",
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
