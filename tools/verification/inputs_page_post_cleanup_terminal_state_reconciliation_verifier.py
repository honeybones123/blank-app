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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_terminal_state_reconciliation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_terminal_state_reconciliation_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_in_target = inputs_page._is_in_target_zone_with_eps
    original_mode_config = inputs_page._design_mode_config
    original_goal = inputs_page._design_optimisation_goal

    failures: list[str] = []
    cases: list[dict] = []
    calls: list[str] = []
    in_target_result = True

    def fake_in_target(overview, mode_config, *, eps):
        calls.append("in_target")
        return bool(in_target_result)

    def fake_mode_config(goal):
        calls.append("mode_config")
        return {"goal": goal}

    def fake_goal(state):
        calls.append("goal")
        return "balanced"

    def run_case(
        name: str,
        *,
        in_target: bool,
        overview: dict,
        render_plan: dict,
        terminal_state: str,
        expected_terminal_state: str,
        expected_terminal_source: str,
        expected_passive_underband: bool,
        expected_positive: bool,
    ) -> None:
        nonlocal in_target_result
        calls.clear()
        in_target_result = in_target
        guidance_debug = {"overview": dict(overview)}
        (
            passive_underband,
            build_active_shear_blocker,
            terminal_state_current_in_target,
            actual_terminal_state,
            actual_terminal_source,
            updated_debug,
        ) = inputs_page.render_design_guide_post_cleanup_terminal_state_reconciliation(
            presentation_headline="Cleanup is advisory for this design state"
            if expected_passive_underband
            else "Other",
            presentation_subtext="",
            guidance_debug=guidance_debug,
            guidance_disp_state={"D": 500},
            render_plan=render_plan,
            terminal_state=terminal_state,
            terminal_state_source="before_source",
        )
        cases.append(
            {
                "name": name,
                "terminal_state": actual_terminal_state,
                "terminal_state_current_in_target": terminal_state_current_in_target,
                "passive_underband": passive_underband,
                "calls": list(calls),
            }
        )
        if passive_underband is not expected_passive_underband:
            failures.append(f"{name}:passive_underband:expected={expected_passive_underband}:actual={passive_underband}")
        if build_active_shear_blocker is not True:
            failures.append(f"{name}:build_active_shear_blocker_not_true")
        if terminal_state_current_in_target is not in_target:
            failures.append(f"{name}:in_target_flag:expected={in_target}:actual={terminal_state_current_in_target}")
        if actual_terminal_state != expected_terminal_state:
            failures.append(f"{name}:terminal_state:expected={expected_terminal_state}:actual={actual_terminal_state}")
        if actual_terminal_source != expected_terminal_source:
            failures.append(f"{name}:terminal_source:expected={expected_terminal_source}:actual={actual_terminal_source}")
        if bool(updated_debug.get("design_guide_terminal_positive")) is not expected_positive:
            failures.append(f"{name}:terminal_positive:expected={expected_positive}:debug={updated_debug}")
        if expected_positive:
            expected_debug = {
                "design_guide_terminal_state": expected_terminal_state,
                "design_guide_terminal_state_source": expected_terminal_source,
                "design_guide_has_actionable_recommendation": False,
                "primary_guidance_intent": "already_efficient",
                "primary_card_intent": "already_efficient",
                "primary_card_title": "Design is efficient - further reductions would weaken capacity",
            }
            for key, expected in expected_debug.items():
                if updated_debug.get(key) != expected:
                    failures.append(f"{name}:debug[{key}]:expected={expected}:actual={updated_debug.get(key)}")
        if "in_target" not in calls:
            failures.append(f"{name}:missing_in_target_call")

    try:
        inputs_page._is_in_target_zone_with_eps = fake_in_target
        inputs_page._design_mode_config = fake_mode_config
        inputs_page._design_optimisation_goal = fake_goal

        run_case(
            "render_plan_terminal_state_promotes_when_in_target",
            in_target=True,
            overview={"any_fail": False},
            render_plan={"terminal_state": "optimal", "terminal_state_source": "render_plan"},
            terminal_state="not_terminal",
            expected_terminal_state="optimal",
            expected_terminal_source="render_plan",
            expected_passive_underband=True,
            expected_positive=True,
        )
        run_case(
            "render_plan_terminal_state_does_not_promote_when_out_of_target",
            in_target=False,
            overview={"any_fail": False},
            render_plan={"terminal_state": "optimal", "terminal_state_source": "render_plan"},
            terminal_state="not_terminal",
            expected_terminal_state="not_terminal",
            expected_terminal_source="before_source",
            expected_passive_underband=False,
            expected_positive=False,
        )
        run_case(
            "existing_terminal_state_is_preserved",
            in_target=True,
            overview={"any_fail": False},
            render_plan={"terminal_state": "very_low_demand", "terminal_state_source": "render_plan"},
            terminal_state="optimal",
            expected_terminal_state="optimal",
            expected_terminal_source="before_source",
            expected_passive_underband=False,
            expected_positive=False,
        )
        run_case(
            "overview_failure_blocks_render_plan_terminal_promotion",
            in_target=True,
            overview={"any_fail": True},
            render_plan={"terminal_state": "optimal", "terminal_state_source": "render_plan"},
            terminal_state="not_terminal",
            expected_terminal_state="not_terminal",
            expected_terminal_source="before_source",
            expected_passive_underband=False,
            expected_positive=False,
        )
    finally:
        inputs_page._is_in_target_zone_with_eps = original_in_target
        inputs_page._design_mode_config = original_mode_config
        inputs_page._design_optimisation_goal = original_goal

    payload_out = {
        "verifier": "inputs_page_post_cleanup_terminal_state_reconciliation_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Terminal State Reconciliation Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['terminal_state']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
