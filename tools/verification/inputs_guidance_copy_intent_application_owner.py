"""Verify application-owned guidance intent and card copy against the bridge."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide.guidance_copy_model import (
        apply_guidance_copy_model_to_item,
    )
    from inputs_page_modules.guidance_compute import (
        _bind_guidance_compute_runtime,
        _application_bending_near_limit_specific_title,
        _application_describe_guidance_step,
        _application_guidance_before_after_text,
        _application_guidance_item_as_advisory,
        _derive_design_guide_guidance_intent,
        build_guidance_compute_runtime,
    )

    runtime = build_guidance_compute_runtime(bridge)
    _bind_guidance_compute_runtime(
        runtime=runtime,
        st_module=bridge.st,
        os_module=bridge.os,
        sys_module=bridge.sys,
    )
    cases = (
        {
            "item": {
                "check_key": "bending",
                "title_main": "Increase bending capacity",
                "action_type": "increase_depth",
                "action_payload": {"updates": {"D": 650.0}},
                "util": 1.1,
            },
            "state": {"D": 600.0},
            "overview": {
                "any_fail": True,
                "all_key_pass": False,
                "worst_util": 1.1,
                "statuses": {"bending": "FAIL"},
            },
            "efficiency_state": {},
        },
        {
            "item": {
                "check_key": "shear",
                "title_main": "Reduce conservative links",
                "action_type": "increase_link_spacing",
                "action_payload": {"updates": {"s_lig": 250.0}},
                "util": 0.3,
            },
            "state": {"s_lig": 200.0, "lig_legs": 2, "lig_d": 10.0},
            "overview": {
                "all_key_pass": True,
                "worst_util": 0.88,
                "statuses": {"shear": "PASS"},
                "utils": {"shear": 0.3, "bending": 0.88},
            },
            "efficiency_state": {"classification": "overdesigned"},
        },
        {
            "item": {
                "check_key": "general",
                "title_main": "Efficient design",
                "design_guide_terminal_state": "optimal",
                "util": 0.88,
            },
            "state": {"D": 600.0},
            "overview": {
                "all_key_pass": True,
                "worst_util": 0.88,
                "statuses": {"bending": "PASS", "shear": "PASS"},
            },
            "efficiency_state": {"classification": "optimal"},
        },
        {
            "item": {
                "check_key": "crack",
                "title_main": "Review crack control",
                "util": 0.75,
            },
            "state": {"D": 600.0},
            "overview": {
                "all_key_pass": True,
                "worst_util": 0.75,
                "statuses": {"crack": "PASS"},
            },
            "efficiency_state": {"classification": "passing"},
        },
    )
    checks = 0
    for case in cases:
        owned_intent = _derive_design_guide_guidance_intent(
            deepcopy(case["item"]),
            state=deepcopy(case["state"]),
            overview=deepcopy(case["overview"]),
            efficiency_state=deepcopy(case["efficiency_state"]),
        )
        bridge_intent = bridge._derive_design_guide_guidance_intent(
            deepcopy(case["item"]),
            state=deepcopy(case["state"]),
            overview=deepcopy(case["overview"]),
            efficiency_state=deepcopy(case["efficiency_state"]),
        )
        assert owned_intent == bridge_intent
        checks += 1

    advisory_cases = (
        (
            None,
            "candidate_not_commit_eligible",
        ),
        (
            {
                "action_type": "increase_depth",
                "action_payload": {"updates": {"D": 650.0}},
                "primary_action": "Increase depth",
            },
            "primary_efficiency_card_not_executor_backed",
        ),
        (
            {
                "action_type": "increase_link_spacing",
                "action_payload": {"updates": {"s_lig": 250.0}},
                "primary_action": "Reduce links",
            },
            "blocked_shear_cleanup_does_not_reach_final_family_threshold",
        ),
    )
    for item, reason in advisory_cases:
        assert _application_guidance_item_as_advisory(
            deepcopy(item),
            blocked_reason=reason,
        ) == bridge._guidance_item_as_advisory(
            deepcopy(item),
            blocked_reason=reason,
        )
        checks += 1

    title_cases = (
        ("balanced", "increase_width"),
        ("balanced", "increase_depth"),
        ("low_reo", "apply_bottom_recommendation"),
        ("shallow", "other"),
    )
    for goal, action_type in title_cases:
        assert _application_bending_near_limit_specific_title(
            goal,
            action_type,
        ) == bridge._bending_near_limit_specific_title(goal, action_type)
        checks += 1

    step_cases = (
        (
            {"D": 600.0},
            {"D": 650.0},
            "increase_depth",
            {"D": 650.0},
        ),
        (
            {"b": 300.0},
            {"b": 350.0},
            "increase_width",
            {"b": 350.0},
        ),
        (
            {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0},
            {"lig_d": 10, "lig_legs": 2, "s_lig": 250.0},
            "increase_link_spacing",
            {"s_lig": 250.0},
        ),
        (
            {"g_udl_kNm_per_m": 10.0},
            {"g_udl_kNm_per_m": 8.0},
            "deflection_reduce_sustained_load",
            {"g_udl_kNm_per_m": 8.0},
        ),
    )
    for args in step_cases:
        assert _application_describe_guidance_step(*args) == (
            bridge._describe_guidance_step(*args)
        )
        checks += 1

    before_after_cases = (
        (
            {
                "action_type": "increase_depth",
                "action_payload": {"updates": {"D": 650.0}},
            },
            {"D": 600.0},
        ),
        (
            {
                "action_type": "apply_geometry_recommendation",
                "action_payload": {},
            },
            {"D": 600.0, "b": 300.0},
        ),
        ({}, {"D": 600.0}),
    )
    for item, state in before_after_cases:
        assert _application_guidance_before_after_text(
            deepcopy(item),
            deepcopy(state),
        ) == bridge._guidance_before_after_text(
            deepcopy(item),
            deepcopy(state),
        )
        checks += 1

    title_cases = (
        (
            {},
            {},
            {},
            None,
            "",
        ),
        (
            {"label": "Increase depth"},
            {"D": 650.0},
            {"D": 600.0},
            None,
            "",
        ),
        (
            {"label": "Reduce shear links"},
            {"D": 650.0},
            {"D": 600.0},
            "Geometry update",
            "Apply recommendation",
        ),
        (
            {
                "label": "Locked winner",
                "title_locked_from_final_winner": True,
                "canonical_winner_label": "Final selected design",
            },
            {"D": 650.0, "s_lig": 250.0},
            {"D": 600.0, "s_lig": 200.0},
            None,
            "",
        ),
        (
            {"label": "Apply recommendation"},
            {"bot1_count": 3, "D": 550.0},
            {"bot1_count": 4, "D": 600.0},
            None,
            "Optimisation available",
        ),
    )
    canonical = (
        runtime.resolved_candidate_guidance
        .resolve_canonical_guidance_title_from_candidate
    )
    for candidate, updates, state, spec_label, fallback in title_cases:
        kwargs = {
            "state": deepcopy(state),
            "spec_label": spec_label,
            "fallback_title": fallback,
        }
        assert canonical(
            deepcopy(candidate),
            deepcopy(updates),
            **kwargs,
        ) == bridge._resolve_canonical_guidance_title_from_candidate(
            deepcopy(candidate),
            deepcopy(updates),
            **kwargs,
        )
        checks += 1

        owned_copy = apply_guidance_copy_model_to_item(
            deepcopy(case["item"]),
            state=deepcopy(case["state"]),
            overview=deepcopy(case["overview"]),
            efficiency_state=deepcopy(case["efficiency_state"]),
            derive_guidance_intent=_derive_design_guide_guidance_intent,
        )
        bridge_copy = bridge._design_guide_apply_copy_model_to_item(
            deepcopy(case["item"]),
            state=deepcopy(case["state"]),
            overview=deepcopy(case["overview"]),
            efficiency_state=deepcopy(case["efficiency_state"]),
        )
        assert owned_copy == bridge_copy
        checks += 1

    source = (
        ROOT / "inputs_page_modules" / "design_guide" / "guidance_copy_model.py"
    ).read_text(encoding="utf-8")
    assert "inputs_page_app_contract_bridge" not in source
    assert "inputs_page_route_coordinators" not in source
    print(f"PASS exact guidance intent and copy parity {checks}/{checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
