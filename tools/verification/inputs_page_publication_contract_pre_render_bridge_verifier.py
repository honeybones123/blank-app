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
        f"inputs_page_publication_contract_pre_render_bridge_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_publication_contract_pre_render_bridge_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_apply = inputs_page._apply_design_brain_publication_contract_for_render
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    enforced_response = False

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def apply_contract(*, guidance_items, guidance_debug, render_plan, presentation, state, reason):
        events.append(
            {
                "event": "apply_contract",
                "guidance_items": list(guidance_items or []),
                "guidance_debug": dict(guidance_debug or {}),
                "render_plan": dict(render_plan or {}),
                "presentation": dict(presentation or {}),
                "state": dict(state or {}),
                "reason": reason,
            }
        )
        result_debug = dict(guidance_debug or {})
        result_debug["contract_seen"] = True
        result_plan = dict(render_plan or {})
        result_plan["contract_reason"] = reason
        result_presentation = dict(presentation or {})
        result_presentation["contract_seen"] = True
        return (
            list(guidance_items or []) + [{"title": "contract"}],
            result_debug,
            result_plan,
            result_presentation,
            bool(enforced_response),
        )

    def run_case(
        name: str,
        *,
        enforced: bool,
        terminal_state: object = "optimal",
        terminal_source: object = "old_source",
        terminal_render: bool = True,
        invalid_render: bool = True,
    ) -> dict:
        nonlocal events, enforced_response
        events = []
        enforced_response = bool(enforced)
        result = inputs_page.render_design_guide_publication_contract_pre_render_bridge(
            guidance_items=[{"title": "before"}],
            guidance_debug={"before": True},
            render_plan={"reason": "before"},
            dg_presentation={"headline": "before"},
            guidance_disp_state={"b": 300},
            terminal_state=terminal_state,
            terminal_state_source=terminal_source,
            post_cleanup_terminal_render=terminal_render,
            post_cleanup_invalid_render=invalid_render,
        )
        (
            guidance_items,
            guidance_debug,
            render_plan,
            presentation,
            contract_enforced,
            result_terminal_state,
            result_terminal_source,
            result_terminal_render,
            result_invalid_render,
        ) = result
        case = {
            "name": name,
            "guidance_items": guidance_items,
            "guidance_debug": guidance_debug,
            "render_plan": render_plan,
            "presentation": presentation,
            "contract_enforced": contract_enforced,
            "terminal_state": result_terminal_state,
            "terminal_state_source": result_terminal_source,
            "post_cleanup_terminal_render": result_terminal_render,
            "post_cleanup_invalid_render": result_invalid_render,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._apply_design_brain_publication_contract_for_render = apply_contract

        case = run_case("not_enforced_preserves_terminal_flags", enforced=False)
        expect(
            "not_enforced_preserves_terminal_flags",
            case["contract_enforced"] is False
            and case["terminal_state"] == "optimal"
            and case["terminal_state_source"] == "old_source"
            and case["post_cleanup_terminal_render"] is True
            and case["post_cleanup_invalid_render"] is True
            and case["guidance_debug"]["contract_seen"] is True
            and case["events"][0]["reason"] == "design_brain_publication_contract_pre_render",
            f"case={case}",
        )

        case = run_case("enforced_resets_terminal_flags", enforced=True)
        expect(
            "enforced_resets_terminal_flags",
            case["contract_enforced"] is True
            and case["terminal_state"] is None
            and case["terminal_state_source"] == "design_brain_publication_contract_pre_render"
            and case["post_cleanup_terminal_render"] is False
            and case["post_cleanup_invalid_render"] is False,
            f"case={case}",
        )
    finally:
        inputs_page._apply_design_brain_publication_contract_for_render = original_apply

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "cases": cases,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Publication Contract Pre Render Bridge Verifier",
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
