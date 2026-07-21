from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_publication_pre_render_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_publication_pre_render_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_design_guide_post_cleanup_render_context_and_final_active_pipeline": (
            inputs_page.render_design_guide_post_cleanup_render_context_and_final_active_pipeline
        ),
        "render_design_guide_final_visible_publication_resolution_setup": (
            inputs_page.render_design_guide_final_visible_publication_resolution_setup
        ),
        "render_design_guide_final_visible_publication_render_sync_pipeline": (
            inputs_page.render_design_guide_final_visible_publication_render_sync_pipeline
        ),
        "render_design_guide_post_cleanup_acceptance_and_post_apply_terminal_pipeline": (
            inputs_page.render_design_guide_post_cleanup_acceptance_and_post_apply_terminal_pipeline
        ),
        "render_design_guide_post_cleanup_invalid_render_suppression": (
            inputs_page.render_design_guide_post_cleanup_invalid_render_suppression
        ),
        "render_design_guide_publication_contract_pre_render_bridge": (
            inputs_page.render_design_guide_publication_contract_pre_render_bridge
        ),
    }
    failures: list[str] = []
    calls: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _record(event: str, kwargs: dict[str, Any]) -> None:
        calls.append({"event": event, "kwargs": dict(kwargs)})

    def render_context(**kwargs):
        _record("render_context", kwargs)
        if kwargs.get("guidance_items") != [{"stage": "input"}]:
            failures.append("render_context_input_items_mismatch")
        return (
            False,
            ["initial_low"],
            [{"stage": "context"}],
            "terminal_context",
            "source_context",
            {"presentation": "context"},
            {"plan": "context"},
            {"action": "active_failure"},
            {"primary": "final"},
            ["bending", "shear"],
        )

    def final_visible_setup(**kwargs):
        _record("final_visible_setup", kwargs)
        if kwargs.get("guidance_items") != [{"stage": "context"}]:
            failures.append("final_visible_setup_items_mismatch")
        if kwargs.get("dg_presentation") != {"presentation": "context"}:
            failures.append("final_visible_setup_presentation_mismatch")
        return (
            [{"stage": "resolution_setup"}],
            {"publication_context": True},
            {"publication_dependencies": True},
            {"item": {"id": "visible_item"}, "resolution": "setup"},
        )

    def final_visible_sync(**kwargs):
        _record("final_visible_sync", kwargs)
        if kwargs.get("final_active_fail_keys_for_render") != ["bending", "shear"]:
            failures.append("final_visible_sync_active_keys_mismatch")
        if kwargs.get("guidance_items") != [{"stage": "resolution_setup"}]:
            failures.append("final_visible_sync_items_mismatch")
        return (
            {"id": "visible_item", "synced": True},
            {"item": {"id": "visible_item"}, "resolution": "sync"},
            {"overview": "sync"},
            {"presentation": "sync"},
            [{"stage": "sync"}],
            {"plan": "sync"},
            "terminal_sync",
            "source_sync",
        )

    def acceptance(**kwargs):
        _record("acceptance", kwargs)
        if kwargs.get("final_visible_item") != {"id": "visible_item", "synced": True}:
            failures.append("acceptance_visible_item_mismatch")
        if kwargs.get("terminal_state") != "terminal_sync":
            failures.append("acceptance_terminal_mismatch")
        return (
            {"cleanup": "before_blocker"},
            [{"stage": "acceptance"}],
            {"plan": "acceptance"},
            {"presentation": "acceptance"},
            "terminal_acceptance",
            "source_acceptance",
            True,
            {"audit": "acceptance"},
            ["acceptance_low"],
        )

    def invalid_suppression(**kwargs):
        _record("invalid_suppression", kwargs)
        if kwargs.get("final_visible_cleanup_action_before_blocker") != {"cleanup": "before_blocker"}:
            failures.append("invalid_suppression_cleanup_action_mismatch")
        if kwargs.get("final_visible_item") != {"id": "visible_item", "synced": True}:
            failures.append("invalid_suppression_visible_item_mismatch")
        return (
            False,
            "terminal_invalid_suppressed",
            "source_invalid_suppressed",
        )

    def contract_bridge(**kwargs):
        _record("contract_bridge", kwargs)
        if kwargs.get("terminal_state") != "terminal_invalid_suppressed":
            failures.append("contract_bridge_terminal_mismatch")
        if kwargs.get("post_cleanup_terminal_render") is not True:
            failures.append("contract_bridge_terminal_render_mismatch")
        debug = dict(kwargs["guidance_debug"])
        debug["contract_bridge"] = True
        return (
            [{"stage": "contract"}],
            debug,
            {"plan": "contract"},
            {"presentation": "contract"},
            True,
            "terminal_contract",
            "source_contract",
            True,
            False,
        )

    try:
        inputs_page.render_design_guide_post_cleanup_render_context_and_final_active_pipeline = render_context
        inputs_page.render_design_guide_final_visible_publication_resolution_setup = final_visible_setup
        inputs_page.render_design_guide_final_visible_publication_render_sync_pipeline = final_visible_sync
        inputs_page.render_design_guide_post_cleanup_acceptance_and_post_apply_terminal_pipeline = acceptance
        inputs_page.render_design_guide_post_cleanup_invalid_render_suppression = invalid_suppression
        inputs_page.render_design_guide_publication_contract_pre_render_bridge = contract_bridge
        result = inputs_page.render_design_guide_post_cleanup_publication_pre_render_coordinator(
            post_active_failure_repair_render=True,
            post_cleanup_render_audit={"audit": "input"},
            guidance_debug={"debug": "input"},
            guidance_disp_state={"state": "input"},
            dg_overview={"overview": "input"},
            guidance_items=[{"stage": "input"}],
            dg_presentation={"presentation": "input"},
            terminal_state="terminal_input",
            terminal_state_source="source_input",
            render_plan={"plan": "input"},
            current_state={"current": "input"},
        )
    finally:
        _restore()

    expected_order = [
        "render_context",
        "final_visible_setup",
        "final_visible_sync",
        "acceptance",
        "invalid_suppression",
        "contract_bridge",
    ]
    actual_order = [call["event"] for call in calls]
    if actual_order != expected_order:
        failures.append(f"call_order_mismatch:{actual_order}")

    expected_result = (
        True,
        ["acceptance_low"],
        [{"stage": "contract"}],
        "terminal_contract",
        "source_contract",
        {"overview": "sync"},
        {"presentation": "contract"},
        {"plan": "contract"},
        {"action": "active_failure"},
        {"primary": "final"},
        ["bending", "shear"],
        {"publication_context": True},
        {"publication_dependencies": True},
        {"item": {"id": "visible_item"}, "resolution": "sync"},
        {"id": "visible_item", "synced": True},
        {"cleanup": "before_blocker"},
        {"audit": "acceptance"},
        False,
        True,
        {"debug": "input", "contract_bridge": True},
    )
    if result != expected_result:
        failures.append(f"result_mismatch:{result}")

    payload = {
        "verifier": "inputs_page_post_cleanup_publication_pre_render_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "call_order": actual_order,
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Publication Pre Render Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Call Order",
                "",
                *(f"- `{event}`" for event in actual_order),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
