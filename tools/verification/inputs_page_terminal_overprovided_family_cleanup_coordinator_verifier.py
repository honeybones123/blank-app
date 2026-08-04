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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_overprovided_family_cleanup_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_overprovided_family_cleanup_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_design_guide_terminal_overprovided_family_cleanup_setup": inputs_page.render_design_guide_terminal_overprovided_family_cleanup_setup,
        "render_design_guide_terminal_direct_cleanup_item_selection": inputs_page.render_design_guide_terminal_direct_cleanup_item_selection,
        "render_design_guide_terminal_direct_cleanup_bounded_proof_branch": inputs_page.render_design_guide_terminal_direct_cleanup_bounded_proof_branch,
        "render_design_guide_terminal_direct_cleanup_actionability_precheck": inputs_page.render_design_guide_terminal_direct_cleanup_actionability_precheck,
        "render_design_guide_terminal_direct_cleanup_allowed_branch": inputs_page.render_design_guide_terminal_direct_cleanup_allowed_branch,
        "render_design_guide_terminal_direct_cleanup_advisory_branch": inputs_page.render_design_guide_terminal_direct_cleanup_advisory_branch,
        "_guidance_item_is_resolved_one_click": inputs_page._guidance_item_is_resolved_one_click,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(name: str, *, branch: str, adapter_ran: bool = True, adapter_promoted: bool = False):
        calls: list[str] = []
        getter_calls: list[str] = []
        debug: dict[str, Any] = {}

        def stage(label: str) -> None:
            calls.append(f"stage:{label}")

        def trace(label: str, **payload: Any) -> None:
            calls.append(f"trace:{label}:{payload.get('material_family_count')}")

        def engine_getter() -> dict[str, Any]:
            getter_calls.append("engine")
            return {"decision": "existing"}

        def presentation_getter() -> dict[str, Any]:
            getter_calls.append("presentation")
            return {"headline": "existing"}

        def setup(*, dg_overview, stage, trace):
            calls.append("setup")
            if branch == "no_material":
                return {}, [], None, None, False
            return {"shear": 0.62}, ["shear"], "bending", 0.62, False

        def item_selection(**kwargs):
            calls.append("item_selection")
            return {"title_main": "Direct cleanup", "resolved": True}

        def bounded(**kwargs):
            calls.append("bounded")
            if branch == "bounded":
                return (
                    [{"title_main": "Bounded proof"}],
                    None,
                    None,
                    "direct_target_band_bounded_proof_unresolved",
                    {"decision": "bounded"},
                    {"headline": "bounded"},
                    {"reason": "direct_target_band_bounded_proof_unresolved"},
                    True,
                )
            return (
                kwargs["guidance_items"],
                kwargs["recommendation_result"],
                kwargs["terminal_state"],
                kwargs["terminal_state_source"],
                kwargs["dg_engine_decision"],
                kwargs["dg_presentation"],
                kwargs["render_plan"],
                False,
            )

        def actionability(**kwargs):
            calls.append("actionability")
            if branch == "allowed":
                return kwargs["direct_cleanup_item"], True, None, {"safe_executor_backed_candidates_count": 2}
            return kwargs["direct_cleanup_item"], False, "candidate_not_executor_backed", {"reason": "blocked"}

        def allowed(**kwargs):
            calls.append("allowed")
            kwargs["guidance_debug"]["allowed_branch"] = True
            return ([kwargs["direct_cleanup_item"]], None, "blocked_by_safe_local_cleanup")

        def advisory(**kwargs):
            calls.append("advisory")
            kwargs["guidance_debug"]["advisory_branch"] = True
            return (
                [{"title_main": "Advisory"}],
                None,
                None,
                "direct_cleanup_not_executor_backed_blocker",
                {"reason": "direct_cleanup_not_executor_backed_blocker"},
            )

        try:
            inputs_page.render_design_guide_terminal_overprovided_family_cleanup_setup = setup
            inputs_page.render_design_guide_terminal_direct_cleanup_item_selection = item_selection
            inputs_page.render_design_guide_terminal_direct_cleanup_bounded_proof_branch = bounded
            inputs_page.render_design_guide_terminal_direct_cleanup_actionability_precheck = actionability
            inputs_page.render_design_guide_terminal_direct_cleanup_allowed_branch = allowed
            inputs_page.render_design_guide_terminal_direct_cleanup_advisory_branch = advisory
            inputs_page._guidance_item_is_resolved_one_click = lambda item: True
            result = inputs_page.render_design_guide_terminal_overprovided_family_cleanup_coordinator(
                final_local_cleanup_adapter_ran=adapter_ran,
                final_local_cleanup_adapter_promoted=adapter_promoted,
                terminal_state="optimal",
                terminal_state_source="pre_existing_terminal",
                guidance_items=[{"title_main": "Existing"}],
                recommendation_result={"status": "old"},
                dg_engine_decision_getter=engine_getter,
                dg_presentation_getter=presentation_getter,
                render_plan={"reason": "old"},
                guidance_debug=debug,
                guidance_disp_state={"depth": 500},
                dg_overview={"utils": {"shear": 0.62}},
                dg_mode_cfg={},
                stage=stage,
                trace=trace,
            )
        finally:
            _restore()
        case = {
            "name": name,
            "branch": branch,
            "result": result,
            "calls": calls,
            "getter_calls": getter_calls,
            "debug": debug,
        }
        cases.append(case)
        return case

    case = _run_case("adapter_not_run_noop", branch="no_material", adapter_ran=False)
    if case["calls"]:
        failures.append(f"adapter_not_run_called_dependencies:{case}")
    if case["getter_calls"]:
        failures.append(f"adapter_not_run_getter_called:{case}")
    if case["result"][0] != [{"title_main": "Existing"}] or case["result"][1] != {"status": "old"}:
        failures.append(f"adapter_not_run_state_mismatch:{case}")

    case = _run_case("adapter_promoted_noop", branch="no_material", adapter_promoted=True)
    if case["calls"]:
        failures.append(f"adapter_promoted_called_dependencies:{case}")
    if case["getter_calls"]:
        failures.append(f"adapter_promoted_getter_called:{case}")

    case = _run_case("terminal_without_material_families", branch="no_material")
    if case["calls"] != ["setup"]:
        failures.append(f"no_material_call_order_mismatch:{case}")
    if case["getter_calls"]:
        failures.append(f"no_material_getter_called:{case}")

    case = _run_case("bounded_proof_handled", branch="bounded")
    if case["calls"] != ["setup", "item_selection", "bounded"]:
        failures.append(f"bounded_call_order_mismatch:{case}")
    if case["getter_calls"] != ["engine", "presentation"]:
        failures.append(f"bounded_getter_order_mismatch:{case}")
    if case["result"][3] != "direct_target_band_bounded_proof_unresolved":
        failures.append(f"bounded_terminal_source_mismatch:{case}")
    if case["result"][4] != {"decision": "bounded"} or case["result"][5] != {"headline": "bounded"}:
        failures.append(f"bounded_threaded_state_mismatch:{case}")

    case = _run_case("allowed_actionability_branch", branch="allowed")
    if case["calls"] != ["setup", "item_selection", "bounded", "actionability", "allowed"]:
        failures.append(f"allowed_call_order_mismatch:{case}")
    if case["debug"].get("family_utils") != {"shear": 0.62}:
        failures.append(f"allowed_family_utils_missing:{case}")
    if case["debug"].get("local_cleanup_search_ran") is not True:
        failures.append(f"allowed_search_flag_missing:{case}")
    if case["result"][3] != "blocked_by_safe_local_cleanup":
        failures.append(f"allowed_terminal_source_mismatch:{case}")

    case = _run_case("advisory_actionability_branch", branch="advisory")
    if case["calls"] != ["setup", "item_selection", "bounded", "actionability", "advisory"]:
        failures.append(f"advisory_call_order_mismatch:{case}")
    if case["result"][6] != {"reason": "direct_cleanup_not_executor_backed_blocker"}:
        failures.append(f"advisory_render_plan_mismatch:{case}")
    if case["debug"].get("advisory_branch") is not True:
        failures.append(f"advisory_debug_missing:{case}")

    payload = {
        "verifier": "inputs_page_terminal_overprovided_family_cleanup_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Overprovided Family Cleanup Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` calls={case['calls']}" for case in cases),
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
