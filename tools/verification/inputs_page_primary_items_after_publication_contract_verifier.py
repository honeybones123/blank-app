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
    json_path = ARTIFACT_DIR / f"inputs_page_primary_items_after_publication_contract_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_items_after_publication_contract_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_apply = inputs_page._apply_design_brain_publication_contract_for_render
    original_render = inputs_page._render_guidance_secondary_items

    def apply_contract(**kwargs):
        calls.append({"event": "apply_contract", "kwargs": dict(kwargs)})
        guidance_items = [{"title": "contract primary", "button_contract": {"enabled": False}}]
        guidance_debug = {**dict(kwargs.get("guidance_debug") or {}), "contract": "applied"}
        render_plan = {**dict(kwargs.get("render_plan") or {}), "reason": "contract_reason"}
        presentation = {"headline": "contract presentation"}
        return guidance_items, guidance_debug, render_plan, presentation, True

    def render_items(items, **kwargs):
        calls.append({"event": "render_items", "items": list(items or []), "kwargs": dict(kwargs)})

    stage_events: list[str] = []

    def stage(name: str) -> None:
        stage_events.append(name)
        calls.append({"event": "stage", "name": name})

    try:
        inputs_page._apply_design_brain_publication_contract_for_render = apply_contract
        inputs_page._render_guidance_secondary_items = render_items

        enforced_result = inputs_page.render_design_guide_primary_items_after_publication_contract(
            primary_render_items=[{"title": "old primary"}],
            guidance_items=[],
            guidance_debug={"existing": True},
            render_plan={"reason": "old"},
            dg_presentation={"headline": "old"},
            primary_guidance_disp_state_for_render={"state": "primary"},
            dg_overview={"overview": True},
            inputs_render_audit={"audit": True},
            stage_fn=stage,
        )

        def apply_empty(**kwargs):
            calls.append({"event": "apply_contract_empty", "kwargs": dict(kwargs)})
            return [], {}, {}, {}, False

        inputs_page._apply_design_brain_publication_contract_for_render = apply_empty
        empty_stage_events: list[str] = []

        def empty_stage(name: str) -> None:
            empty_stage_events.append(name)
            calls.append({"event": "empty_stage", "name": name})

        empty_result = inputs_page.render_design_guide_primary_items_after_publication_contract(
            primary_render_items=[],
            guidance_items=[],
            guidance_debug={},
            render_plan={},
            dg_presentation=None,
            primary_guidance_disp_state_for_render={},
            dg_overview={},
            inputs_render_audit={},
            stage_fn=empty_stage,
        )
    finally:
        inputs_page._apply_design_brain_publication_contract_for_render = original_apply
        inputs_page._render_guidance_secondary_items = original_render

    (
        enforced_primary,
        enforced_guidance,
        enforced_debug,
        enforced_plan,
        enforced_presentation,
        enforced_flag,
    ) = enforced_result
    (
        empty_primary,
        empty_guidance,
        empty_debug,
        empty_plan,
        empty_presentation,
        empty_flag,
    ) = empty_result

    expect(
        "enforced_contract_primary_replacement",
        enforced_primary == [{"title": "contract primary", "button_contract": {"enabled": False}}]
        and enforced_guidance == [{"title": "contract primary", "button_contract": {"enabled": False}}]
        and enforced_debug == {"existing": True, "contract": "applied"}
        and enforced_plan == {"reason": "contract_reason"}
        and enforced_presentation == {"headline": "contract presentation"}
        and enforced_flag is True,
        (
            f"primary={enforced_primary} guidance={enforced_guidance} debug={enforced_debug} "
            f"plan={enforced_plan} presentation={enforced_presentation} flag={enforced_flag}"
        ),
    )
    expect(
        "stage_and_render_order",
        stage_events
        == [
            "post_plan.before_render_primary_only_item",
            "post_plan.after_render_primary_only_item",
        ]
        and [call["event"] for call in calls[:4]]
        == ["apply_contract", "stage", "render_items", "stage"]
        and calls[2]["items"] == enforced_primary
        and calls[2]["kwargs"]
        == {
            "guidance_disp_state": {"state": "primary"},
            "current_overview": {"overview": True},
            "inputs_render_audit": {"audit": True},
            "start_index": 0,
            "primary_card_presentation": {"headline": "contract presentation"},
        },
        f"stage_events={stage_events} calls={calls[:4]}",
    )
    expect(
        "empty_path_no_render",
        empty_primary == []
        and empty_guidance == []
        and empty_debug == {}
        and empty_plan == {}
        and empty_presentation == {}
        and empty_flag is False
        and empty_stage_events == [],
        (
            f"primary={empty_primary} guidance={empty_guidance} debug={empty_debug} "
            f"plan={empty_plan} presentation={empty_presentation} flag={empty_flag} "
            f"stages={empty_stage_events}"
        ),
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "stage_events": stage_events,
        "empty_stage_events": empty_stage_events,
        "enforced_result": enforced_result,
        "empty_result": empty_result,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Items After Publication Contract Verifier",
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
