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
    json_path = ARTIFACT_DIR / f"inputs_page_postprocess_pre_render_plan_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_postprocess_pre_render_plan_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_design_guide_guidance_item_postprocess": inputs_page.render_design_guide_guidance_item_postprocess,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_mode_config": inputs_page._design_mode_config,
        "render_design_guide_family_speed_isolated_bending_repair": inputs_page.render_design_guide_family_speed_isolated_bending_repair,
        "render_design_guide_terminal_green_low_bending_suppression": inputs_page.render_design_guide_terminal_green_low_bending_suppression,
        "render_design_guide_acceptance_audit_state": inputs_page.render_design_guide_acceptance_audit_state,
        "render_design_guide_post_apply_publication_chain": inputs_page.render_design_guide_post_apply_publication_chain,
        "render_design_guide_pre_render_plan_pipeline": inputs_page.render_design_guide_pre_render_plan_pipeline,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(name: str, *, invalid_cleanup_taken: bool, not_started: bool):
        calls: list[dict[str, Any]] = []
        stage_calls: list[str] = []
        raw_items = [{"title_main": "Raw"}]
        initial_debug = {"overview": {"utils": {"bending": 0.9}}}
        initial_state = {"depth": 500}

        def postprocess(**kwargs):
            calls.append({"event": "postprocess", "kwargs": dict(kwargs)})
            return (
                [{"title_main": "Post"}],
                {"overview": {"utils": {"bending": 0.91}}, "postprocessed": True},
                {"dedupe": True},
                {"collapse": True},
                "branch-a",
                {"rr": "post"},
                {"redundancy": False},
                {"suppression": False},
                {"cleanup": False},
            )

        def goal(state):
            calls.append({"event": "goal", "state": dict(state)})
            return "efficiency"

        def mode_config(goal_name):
            calls.append({"event": "mode_config", "goal": goal_name})
            return {"mode": goal_name}

        def family_speed(**kwargs):
            calls.append({"event": "family_speed", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["family_speed"] = True
            return True, debug

        def low_bending(**kwargs):
            calls.append({"event": "low_bending", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["low_bending"] = True
            return [{"title_main": "Suppressed"}], debug, {"rr": "suppressed"}

        def acceptance(**kwargs):
            calls.append({"event": "acceptance", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["acceptance"] = True
            return (
                {"audit": True},
                debug,
                {"route": True},
                "label",
                "family",
                True,
                {"accepted": True},
                False,
            )

        def publication(**kwargs):
            calls.append({"event": "publication", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["publication"] = True
            return (
                [{"title_main": "Published"}],
                debug,
                {"rr": "published"},
                invalid_cleanup_taken,
            )

        def pre_render(**kwargs):
            calls.append({"event": "pre_render", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["pre_render"] = True
            state = dict(kwargs["guidance_disp_state"])
            state["pre_rendered"] = True
            return (
                debug,
                state,
                [{"title_main": "Visible"}],
                {"rr": "pre_render"},
                not_started,
                ["repair"],
                "optimal",
                "derived",
                {"terminal": True},
                {"pending": True},
                {"visible_guidance_items": [{"title_main": "Visible"}], "reason": "test"},
                True,
                [{"title_main": "Visible"}],
                False,
                "reconciled",
                True,
            )

        try:
            inputs_page.render_design_guide_guidance_item_postprocess = postprocess
            inputs_page._design_optimisation_goal = goal
            inputs_page._design_mode_config = mode_config
            inputs_page.render_design_guide_family_speed_isolated_bending_repair = family_speed
            inputs_page.render_design_guide_terminal_green_low_bending_suppression = low_bending
            inputs_page.render_design_guide_acceptance_audit_state = acceptance
            inputs_page.render_design_guide_post_apply_publication_chain = publication
            inputs_page.render_design_guide_pre_render_plan_pipeline = pre_render
            result = inputs_page.render_design_guide_postprocess_pre_render_plan_coordinator(
                guidance_items_raw=raw_items,
                guidance_debug=initial_debug,
                guidance_disp_state=initial_state,
                current_state={"current": True},
                fingerprint="fp-1",
                fast_focus_section="guide",
                guidance_fresh_compute_used=True,
                sidebar_debug=True,
                stage=lambda label: stage_calls.append(label),
            )
        finally:
            _restore()
        case = {"name": name, "result": result, "calls": calls, "stage_calls": stage_calls}
        cases.append(case)
        return case

    case = _run_case("normal_recommendation_needed", invalid_cleanup_taken=False, not_started=False)
    if [call["event"] for call in case["calls"]] != [
        "postprocess",
        "goal",
        "mode_config",
        "family_speed",
        "low_bending",
        "acceptance",
        "publication",
        "pre_render",
    ]:
        failures.append(f"normal_call_order_mismatch:{case}")
    result = case["result"]
    if result != (
        [{"title_main": "Visible"}],
        {
            "overview": {"utils": {"bending": 0.91}},
            "postprocessed": True,
            "family_speed": True,
            "low_bending": True,
            "acceptance": True,
            "publication": True,
            "pre_render": True,
        },
        {"depth": 500, "pre_rendered": True},
        {"dedupe": True},
        {"rr": "pre_render"},
        "optimal",
        "derived",
        {"pending": True},
        {"visible_guidance_items": [{"title_main": "Visible"}], "reason": "test"},
        False,
        False,
    ):
        failures.append(f"normal_result_mismatch:{case}")
    pre_render_kwargs = case["calls"][-1]["kwargs"]
    if pre_render_kwargs.get("recommendation_needed") is not True:
        failures.append(f"normal_recommendation_needed_mismatch:{case}")
    if pre_render_kwargs.get("branch_for_recommendation") != "branch-a":
        failures.append(f"normal_branch_mismatch:{case}")
    if pre_render_kwargs.get("redundancy_meta") != {"redundancy": False}:
        failures.append(f"normal_redundancy_mismatch:{case}")
    if pre_render_kwargs.get("collapse_meta") != {"collapse": True}:
        failures.append(f"normal_collapse_mismatch:{case}")

    case = _run_case("invalid_cleanup_suppresses_recommendation", invalid_cleanup_taken=True, not_started=True)
    if case["result"][-1] is not True:
        failures.append(f"early_not_started_flag_mismatch:{case}")
    pre_render_kwargs = case["calls"][-1]["kwargs"]
    if pre_render_kwargs.get("recommendation_needed") is not False:
        failures.append(f"invalid_cleanup_recommendation_needed_mismatch:{case}")

    payload = {
        "verifier": "inputs_page_postprocess_pre_render_plan_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Postprocess Pre Render Plan Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` early={case['result'][-1]}" for case in cases),
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
