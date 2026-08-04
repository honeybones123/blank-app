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
        f"inputs_page_post_cleanup_invalid_render_publication_and_secondary_items_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_publication_and_secondary_items_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_apply = inputs_page._apply_design_brain_publication_contract_for_render
    original_render_secondary = inputs_page._render_guidance_secondary_items

    def apply_contract(**kwargs):
        calls.append({"event": "apply_contract", "kwargs": kwargs})
        item = dict(kwargs["guidance_items"][0])
        item["contract_enforced"] = True
        return (
            [item],
            {"debug": "updated"},
            {"plan": "updated"},
            {"presentation": "updated"},
            True,
        )

    def render_secondary(items, **kwargs):
        calls.append(
            {
                "event": "render_secondary",
                "items": [dict(item) for item in items],
                "kwargs": kwargs,
            }
        )

    def stage(name):
        calls.append({"event": "stage", "name": name})

    try:
        inputs_page._apply_design_brain_publication_contract_for_render = apply_contract
        inputs_page._render_guidance_secondary_items = render_secondary
        (
            item,
            guidance_debug,
            render_plan,
            presentation,
            enforced,
        ) = inputs_page.render_design_guide_post_cleanup_invalid_render_publication_and_secondary_items(
            blocked_render_item={"title_main": "Blocked cleanup", "family": "shear"},
            guidance_debug={"debug": "old"},
            render_plan={"plan": "old"},
            dg_presentation={"presentation": "old"},
            guidance_disp_state={"s_lig": 300},
            dg_overview={"utils": {"shear": 0.62}},
            inputs_render_audit={"audit": True},
            stage_fn=stage,
        )
    finally:
        inputs_page._apply_design_brain_publication_contract_for_render = original_apply
        inputs_page._render_guidance_secondary_items = original_render_secondary

    apply_call = next((call for call in calls if call["event"] == "apply_contract"), {})
    render_call = next((call for call in calls if call["event"] == "render_secondary"), {})
    stage_call = next((call for call in calls if call["event"] == "stage"), {})

    expect(
        "publication_contract_return",
        item == {"title_main": "Blocked cleanup", "family": "shear", "contract_enforced": True}
        and guidance_debug == {"debug": "updated"}
        and render_plan == {"plan": "updated"}
        and presentation == {"presentation": "updated"}
        and enforced is True,
        (
            f"item={item} guidance_debug={guidance_debug} render_plan={render_plan} "
            f"presentation={presentation} enforced={enforced}"
        ),
    )
    expect(
        "publication_contract_inputs",
        apply_call.get("kwargs", {}).get("reason")
        == "design_brain_publication_contract_blocker_render"
        and apply_call.get("kwargs", {}).get("state") == {"s_lig": 300}
        and apply_call.get("kwargs", {}).get("guidance_items")
        == [{"title_main": "Blocked cleanup", "family": "shear"}],
        f"apply_call={apply_call}",
    )
    expect(
        "secondary_render_inputs",
        render_call.get("items")
        == [{"title_main": "Blocked cleanup", "family": "shear", "contract_enforced": True}]
        and render_call.get("kwargs", {}).get("guidance_disp_state") == {"s_lig": 300}
        and render_call.get("kwargs", {}).get("current_overview") == {"utils": {"shear": 0.62}}
        and render_call.get("kwargs", {}).get("inputs_render_audit") == {"audit": True}
        and render_call.get("kwargs", {}).get("start_index") == 0
        and render_call.get("kwargs", {}).get("primary_card_presentation")
        == {"presentation": "updated"},
        f"render_call={render_call}",
    )
    expect(
        "stage_checkpoint",
        stage_call.get("name") == "post_plan.after_render_invalid_cleanup_blocker",
        f"stage_call={stage_call}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Publication And Secondary Items Verifier",
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
