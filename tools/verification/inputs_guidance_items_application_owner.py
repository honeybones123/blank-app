"""Verify permanent guidance-item ownership against the frozen bridge."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import guidance_items as owned

    states = [
        {},
        {"design_optimisation_goal": "balanced"},
        {
            "design_optimisation_goal": "shallower_beam",
            "exact_stop_proven": True,
            "exact_stop_proof": {"source": "verification"},
        },
    ]
    overviews = [
        {"worst_util": 0.0},
        {"worst_util": 0.72},
        {"worst_util": 0.94},
    ]
    checks = 0
    for state, overview in zip(states, overviews):
        for name in (
            "_passing_guidance_item",
            "_optimal_guidance_item",
            "_very_low_demand_guidance_item",
        ):
            assert getattr(owned, name)(state, overview) == getattr(bridge, name)(
                state,
                overview,
            )
            checks += 1

    for status, util in (
        ("START", None),
        ("FAIL", 1.2),
        ("PASS", 0.95),
        ("PASS", 0.4),
    ):
        args = ("x", "Title", "Do", None, "Why", "Levers", None, None)
        assert owned._guidance_item(
            *args,
            status=status,
            util=util,
        ) == bridge._guidance_item(
            *args,
            status=status,
            util=util,
        )
        checks += 1

    for state in (
        {},
        {"D": 600.0, "L": 6000.0},
        {"b": 0.0, "D": 0.0, "L": 0.0, "uls_Mstar": 120.0},
        {"b": 0.0, "D": 0.0, "L": 0.0, "bot1_count": 3, "db_bot_1": 20.0},
        {"b": 0.0, "D": 0.0, "L": 0.0, "lig_legs": 2, "lig_d": 10.0, "s_lig": 200.0},
    ):
        assert owned._guidance_start_item(state) == bridge._guidance_start_item(state)
        checks += 1

    not_started_cases = (
        (
            {},
            {"utils": {"bending": None, "shear": None}},
        ),
        (
            {"b": 400.0, "D": 600.0, "L": 6000.0},
            {"utils": {"bending": 0.8, "shear": 0.7}},
        ),
        (
            {
                "b": 400.0,
                "D": 600.0,
                "L": 6000.0,
                "uls_Mstar": 100.0,
                "Ast_bot": 1200.0,
                "nb_bot": 3,
                "db_bot": 20.0,
                "lig_legs": 2,
                "lig_d": 10.0,
                "s_lig": 200.0,
            },
            {"utils": {"bending": 0.8, "shear": 0.7}},
        ),
        (
            {
                "sec_shape": "T",
                "bw": 300.0,
                "D": 700.0,
                "L": 7000.0,
                "Ast_bot": 1500.0,
                "nb_bot": 4,
                "db_bot": 20.0,
                "lig_legs": 2,
                "lig_d": 10.0,
                "s_lig": 150.0,
            },
            {"utils": {"bending": 0.85, "shear": 0.75}},
        ),
    )
    for state, overview in not_started_cases:
        assert owned._guidance_not_started(
            state,
            overview,
        ) == bridge._guidance_not_started(state, overview)
        checks += 1

    solver_cases = (
        {},
        {"meta": {"status": "no_action"}, "updates": {"D": 650.0}},
        {
            "title": "Auto Design Solution",
            "description": "Increase depth",
            "updates": {"D": 650.0},
            "meta": {"util": "0.91"},
        },
        {
            "title": "Compound result",
            "updates": {"D": 650.0, "b": 450.0},
            "resolved_candidate": {
                "updates": {"D": 650.0, "b": 450.0},
                "label": "Resolved compound",
                "action_type": "apply_compound_guidance",
            },
            "meta": {"util": "invalid"},
        },
    )
    for solver_result in solver_cases:
        assert owned._auto_design_solver_recommendation_as_guidance_item(
            solver_result
        ) == bridge._auto_design_solver_recommendation_as_guidance_item(
            solver_result
        )
        checks += 1

    resolved_one_click_cases = (
        {},
        {"action_type": "apply_resolved_candidate", "action_payload": {}},
        {
            "action_type": "apply_resolved_candidate",
            "action_payload": {
                "resolved_candidate_updates": {"D": 650.0},
                "resolved_candidate_reaches_target_band": True,
            },
        },
        {
            "action_type": "apply_compound_guidance",
            "action_payload": {
                "resolved_candidate_updates": {"D": 650.0},
                "resolved_candidate_reaches_target_band": False,
            },
        },
    )
    for item in resolved_one_click_cases:
        assert owned._guidance_item_is_resolved_one_click(
            item
        ) == bridge._guidance_item_is_resolved_one_click(item)
        checks += 1

    source = (
        ROOT / "inputs_page_modules" / "design_guide" / "guidance_items.py"
    ).read_text(encoding="utf-8")
    assert "inputs_page_app_contract_bridge" not in source
    assert "inputs_page_route_coordinators" not in source
    print(f"PASS exact application-owner guidance item parity {checks}/{checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
