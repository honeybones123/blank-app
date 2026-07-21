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
    json_path = ARTIFACT_DIR / f"inputs_page_final_render_branch_dispatch_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_final_render_branch_dispatch_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_design_guide_post_cleanup_terminal_render_branch": (
            inputs_page.render_design_guide_post_cleanup_terminal_render_branch
        ),
        "render_design_guide_post_cleanup_invalid_render_setup_branch": (
            inputs_page.render_design_guide_post_cleanup_invalid_render_setup_branch
        ),
        "render_design_guide_post_cleanup_invalid_render_shear_blocker_packaging_branch": (
            inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_packaging_branch
        ),
        "render_design_guide_post_cleanup_invalid_render_blocker_completion_branch": (
            inputs_page.render_design_guide_post_cleanup_invalid_render_blocker_completion_branch
        ),
        "render_design_guide_post_cleanup_invalid_render_debug_publication_branch": (
            inputs_page.render_design_guide_post_cleanup_invalid_render_debug_publication_branch
        ),
        "_terminal_green_card_is_safe": inputs_page._terminal_green_card_is_safe,
        "render_design_guide_terminal_green_render_branch": inputs_page.render_design_guide_terminal_green_render_branch,
        "render_design_guide_primary_only_late_shear_action_branch": (
            inputs_page.render_design_guide_primary_only_late_shear_action_branch
        ),
        "render_design_guide_primary_only_post_click_publication_branch": (
            inputs_page.render_design_guide_primary_only_post_click_publication_branch
        ),
        "render_design_guide_visible_items_after_render_plan": inputs_page.render_design_guide_visible_items_after_render_plan,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _base_kwargs(**overrides):
        kwargs = {
            "post_cleanup_terminal_render": False,
            "post_cleanup_invalid_render": False,
            "guidance_debug": {"overview": {"all_key_pass": True}},
            "dg_overview": {"overview": "base"},
            "guidance_disp_state": {"state": "base"},
            "post_cleanup_render_audit": {"audit": "base"},
            "inputs_render_audit": {"inputs": "audit"},
            "terminal_state": "needs_action",
            "dg_presentation": {"presentation": "base"},
            "post_cleanup_low_families": ["low"],
            "current_state": {"current": "base"},
            "visible_utils_for_exact_blockers": {"utils": "base"},
            "post_active_failure_repair_render": True,
            "render_plan": {},
            "guidance_items": [{"item": "base"}],
            "final_visible_resolution": {"resolution": "base"},
            "terminal_state_current_in_target": False,
            "restamp_exact_blocker_current_utils_fn": lambda value: {"restamped_current": value},
            "restamp_exact_blocker_maps_in_evidence_fn": lambda value: {"restamped_maps": value},
            "stage": lambda label: None,
        }
        kwargs.update(overrides)
        return kwargs

    def _install_stubs(call_log: list[str]) -> None:
        def terminal_render(**kwargs):
            call_log.append("terminal_render")

        def invalid_setup(**kwargs):
            call_log.append("invalid_setup")
            return (
                True,
                0.91,
                {"truth": "setup"},
                "setup_reason",
                {"item": "setup"},
                False,
                False,
                True,
                0.82,
                True,
            )

        def shear_packaging(**kwargs):
            call_log.append("shear_packaging")
            if kwargs.get("current_state") != {"current": "base"}:
                failures.append("shear_packaging_current_state_mismatch")
            return (
                {"item": "packaged"},
                {"truth": "packaged"},
                False,
                0.77,
            )

        def blocker_completion(**kwargs):
            call_log.append("blocker_completion")
            if kwargs.get("restamp_exact_blocker_current_utils_fn") is None:
                failures.append("blocker_completion_missing_restamp_current")
            return (
                {"item": "completed"},
                False,
                True,
                {"utils": "completed"},
                {"contract": "completed"},
                {"truth": "bundle"},
                {"evidence": "bundle"},
                {"exact": "bundle"},
                False,
            )

        def debug_publication(**kwargs):
            call_log.append("debug_publication")
            if kwargs.get("visible_utils_for_exact_blockers") != {"utils": "completed"}:
                failures.append("debug_publication_visible_utils_mismatch")
            if kwargs.get("restamp_exact_blocker_maps_in_evidence_fn") is None:
                failures.append("debug_publication_missing_restamp_maps")
            return (
                {"item": "debug"},
                {"debug": "invalid"},
                {"plan": "invalid"},
                {"presentation": "invalid"},
                {"utils": "invalid"},
                True,
            )

        def terminal_green_safe(overview, guidance_debug, *, state):
            call_log.append("terminal_green_safe")
            return True

        def terminal_green(**kwargs):
            call_log.append("terminal_green")
            return (
                {"debug": "green"},
                {"presentation": "green"},
                "terminal_green",
            )

        def primary_late(**kwargs):
            call_log.append("primary_late")
            return (
                [{"primary": "late"}],
                [{"item": "late"}],
                {"state": "primary"},
                {"presentation": "late"},
                {"debug": "late"},
            )

        def primary_publication(**kwargs):
            call_log.append("primary_publication")
            if kwargs.get("primary_render_items") != [{"primary": "late"}]:
                failures.append("primary_publication_items_mismatch")
            if kwargs.get("final_visible_resolution") != {"resolution": "base"}:
                failures.append("primary_publication_resolution_mismatch")
            return (
                [{"primary": "published"}],
                [{"item": "published"}],
                {"debug": "published"},
                {"plan": "published"},
                {"presentation": "published"},
                {"utils": "published"},
                True,
            )

        def visible_items(**kwargs):
            call_log.append("visible_items")
            return [{"visible": "rendered"}]

        inputs_page.render_design_guide_post_cleanup_terminal_render_branch = terminal_render
        inputs_page.render_design_guide_post_cleanup_invalid_render_setup_branch = invalid_setup
        inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_packaging_branch = shear_packaging
        inputs_page.render_design_guide_post_cleanup_invalid_render_blocker_completion_branch = blocker_completion
        inputs_page.render_design_guide_post_cleanup_invalid_render_debug_publication_branch = debug_publication
        inputs_page._terminal_green_card_is_safe = terminal_green_safe
        inputs_page.render_design_guide_terminal_green_render_branch = terminal_green
        inputs_page.render_design_guide_primary_only_late_shear_action_branch = primary_late
        inputs_page.render_design_guide_primary_only_post_click_publication_branch = primary_publication
        inputs_page.render_design_guide_visible_items_after_render_plan = visible_items

    def _run_case(name: str, expected_order: list[str], expected_result: tuple, **overrides) -> None:
        call_log: list[str] = []
        try:
            _install_stubs(call_log)
            result = inputs_page.render_design_guide_final_render_branch_dispatch_coordinator(
                **_base_kwargs(**overrides)
            )
        finally:
            _restore()
        cases.append({"name": name, "call_order": list(call_log), "result": result})
        if call_log != expected_order:
            failures.append(f"{name}_call_order_mismatch:{call_log}")
        if result != expected_result:
            failures.append(f"{name}_result_mismatch:{result}")

    _run_case(
        "terminal_render",
        ["terminal_render"],
        (
            {"overview": {"all_key_pass": True}},
            {},
            {"presentation": "base"},
            "needs_action",
            {"utils": "base"},
            [{"item": "base"}],
        ),
        post_cleanup_terminal_render=True,
    )
    _run_case(
        "invalid_render",
        ["invalid_setup", "shear_packaging", "blocker_completion", "debug_publication"],
        (
            {"debug": "invalid"},
            {"plan": "invalid"},
            {"presentation": "invalid"},
            "needs_action",
            {"utils": "invalid"},
            [{"item": "base"}],
        ),
        post_cleanup_invalid_render=True,
    )
    _run_case(
        "terminal_green",
        ["terminal_green_safe", "terminal_green"],
        (
            {"debug": "green"},
            {},
            {"presentation": "green"},
            "terminal_green",
            {"utils": "base"},
            [{"item": "base"}],
        ),
        terminal_state="optimal",
        terminal_state_current_in_target=True,
    )
    _run_case(
        "primary_only",
        ["primary_late", "primary_publication"],
        (
            {"debug": "published"},
            {"plan": "published"},
            {"presentation": "published"},
            "needs_action",
            {"utils": "published"},
            [{"item": "published"}],
        ),
        render_plan={"render_primary_only": True},
    )
    _run_case(
        "visible_items",
        ["visible_items"],
        (
            {"overview": {"all_key_pass": True}},
            {},
            {"presentation": "base"},
            "needs_action",
            {"utils": "base"},
            [{"item": "base"}],
        ),
    )

    payload = {
        "verifier": "inputs_page_final_render_branch_dispatch_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Render Branch Dispatch Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` order={case['call_order']}" for case in cases),
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
