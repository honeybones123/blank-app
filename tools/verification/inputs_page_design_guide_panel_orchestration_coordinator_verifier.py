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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_panel_orchestration_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_panel_orchestration_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "render_design_guide_panel_orchestration_coordinator",
        "render_design_guide_panel_entry_trace_and_stage_coordinator",
        "render_design_guide_initial_state_and_loading_coordinator",
        "render_design_guide_compute_preparation_coordinator",
        "render_design_guide_postprocess_pre_render_plan_coordinator",
        "render_design_guide_active_guard_presentation_engine_coordinator",
        "render_design_guide_presentation_post_cleanup_gate_coordinator",
        "render_design_guide_post_cleanup_publication_pre_render_coordinator",
        "render_design_guide_final_render_branch_dispatch_coordinator",
        "render_design_guide_panel_exit_state",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _verify_old_wrapper_deleted() -> None:
        deleted = not hasattr(inputs_page, "_render_fast_design_guidance_panel")
        cases.append({"name": "old_wrapper_deleted", "deleted": deleted})
        if not deleted:
            failures.append("old_wrapper_still_present")

    def _install_orchestration_stubs(
        calls: list[str],
        *,
        loading_rendered: bool = False,
        fast_terminal_rendered: bool = False,
        not_started_rendered: bool = False,
        early_shear_return: bool = False,
    ) -> None:
        def entry(**kwargs):
            calls.append("entry")
            return 123.0, lambda label: calls.append(f"stage:{label}")

        def initial(**kwargs):
            calls.append("initial")
            if kwargs.get("inputs_render_audit") != {"audit": "orchestration"}:
                failures.append("initial_inputs_render_audit_mismatch")
            return (
                {"current": "state"},
                ("fingerprint",),
                False,
                {"settle": "gate"},
                loading_rendered,
                False,
            )

        def compute(**kwargs):
            calls.append("compute")
            if kwargs.get("fingerprint") != ("fingerprint",):
                failures.append("compute_fingerprint_mismatch")
            return (
                [{"raw": 1}],
                {"debug": "compute"},
                False,
                True,
                False,
                True,
                False,
                False,
                True,
                {"disp": "state"},
                4.2,
                fast_terminal_rendered,
            )

        def postprocess(**kwargs):
            calls.append("postprocess")
            if kwargs.get("guidance_items_raw") != [{"raw": 1}]:
                failures.append("postprocess_raw_items_mismatch")
            return (
                [{"item": "postprocess"}],
                {"debug": "postprocess"},
                {"disp": "postprocess"},
                {"dedupe": "meta"},
                {"recommendation": "postprocess"},
                "terminal_pre",
                "source_pre",
                {"pending": "recommendation"},
                {"plan": "postprocess"},
                {"banner": "postapply"},
                not_started_rendered,
            )

        def active_guard(**kwargs):
            calls.append("active_guard")
            if kwargs.get("pending_recommendation") != {"pending": "recommendation"}:
                failures.append("active_guard_pending_mismatch")
            return (
                [{"item": "active"}],
                {"debug": "active"},
                [{"raw": "active"}],
                "terminal_active",
                "source_active",
                {"recommendation": "active"},
                {"overview": "active"},
                {"mode": "cfg"},
                True,
                {"engine": "decision"},
                {"presentation": "active"},
                {"utils": "active"},
            )

        def cleanup_gate(**kwargs):
            calls.append("cleanup_gate")
            if kwargs.get("dg_overview") != {"overview": "active"}:
                failures.append("cleanup_gate_overview_mismatch")
            return (
                [{"item": "cleanup"}],
                {"presentation": "cleanup"},
                {"recommendation": "cleanup"},
                {"debug": "cleanup"},
                "terminal_cleanup",
                "source_cleanup",
                True,
                {"audit": "cleanup"},
                early_shear_return,
            )

        def publication_pre_render(**kwargs):
            calls.append("publication_pre_render")
            if kwargs.get("post_cleanup_render_audit") != {"audit": "cleanup"}:
                failures.append("publication_pre_render_audit_mismatch")
            return (
                False,
                ["low"],
                [{"item": "publication"}],
                "terminal_publication",
                "source_publication",
                {"overview": "publication"},
                {"presentation": "publication"},
                {"plan": "publication"},
                {"action": "active_failure"},
                {"primary": "final"},
                ["active_fail"],
                {"context": "publication"},
                {"dependencies": "publication"},
                {"resolution": "publication"},
                {"item": "visible"},
                {"cleanup": "before_blocker"},
                {"audit": "publication"},
                False,
                True,
                {"debug": "publication"},
            )

        def dispatch(**kwargs):
            calls.append("dispatch")
            if kwargs.get("final_visible_resolution") != {"resolution": "publication"}:
                failures.append("dispatch_resolution_mismatch")
            if kwargs.get("terminal_state_current_in_target") is not True:
                failures.append("dispatch_terminal_in_target_mismatch")
            return (
                {"debug": "dispatch"},
                {"plan": "dispatch"},
                {"presentation": "dispatch"},
                "terminal_dispatch",
                {"utils": "dispatch"},
                [{"item": "dispatch"}],
            )

        def exit_state(**kwargs):
            calls.append("exit")
            if kwargs.get("render_post_apply_banner") != {"banner": "postapply"}:
                failures.append("exit_banner_mismatch")
            if kwargs.get("fingerprint") != ("fingerprint",):
                failures.append("exit_fingerprint_mismatch")

        inputs_page.render_design_guide_panel_entry_trace_and_stage_coordinator = entry
        inputs_page.render_design_guide_initial_state_and_loading_coordinator = initial
        inputs_page.render_design_guide_compute_preparation_coordinator = compute
        inputs_page.render_design_guide_postprocess_pre_render_plan_coordinator = postprocess
        inputs_page.render_design_guide_active_guard_presentation_engine_coordinator = active_guard
        inputs_page.render_design_guide_presentation_post_cleanup_gate_coordinator = cleanup_gate
        inputs_page.render_design_guide_post_cleanup_publication_pre_render_coordinator = publication_pre_render
        inputs_page.render_design_guide_final_render_branch_dispatch_coordinator = dispatch
        inputs_page.render_design_guide_panel_exit_state = exit_state

    def _run_orchestration_case(name: str, expected_order: list[str], **flags: bool) -> None:
        calls: list[str] = []
        try:
            _install_orchestration_stubs(calls, **flags)
            inputs_page.render_design_guide_panel_orchestration_coordinator(
                inputs_render_audit={"audit": "orchestration"},
                fast_focus_section="focus",
            )
        finally:
            _restore()
        cases.append({"name": name, "call_order": calls})
        if calls != expected_order:
            failures.append(f"{name}_order_mismatch:{calls}")

    _verify_old_wrapper_deleted()
    _run_orchestration_case(
        "normal_order",
        [
            "entry",
            "initial",
            "compute",
            "postprocess",
            "active_guard",
            "cleanup_gate",
            "publication_pre_render",
            "dispatch",
            "exit",
        ],
    )
    _run_orchestration_case("loading_return", ["entry", "initial"], loading_rendered=True)
    _run_orchestration_case(
        "fast_terminal_return",
        ["entry", "initial", "compute"],
        fast_terminal_rendered=True,
    )
    _run_orchestration_case(
        "not_started_return",
        ["entry", "initial", "compute", "postprocess"],
        not_started_rendered=True,
    )
    _run_orchestration_case(
        "early_shear_return",
        ["entry", "initial", "compute", "postprocess", "active_guard", "cleanup_gate"],
        early_shear_return=True,
    )

    payload = {
        "verifier": "inputs_page_design_guide_panel_orchestration_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Panel Orchestration Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
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
