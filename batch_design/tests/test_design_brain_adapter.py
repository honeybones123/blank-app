from batch_design.design_brain_adapter import (
    BatchDesignGuidanceAdapter,
    batch_case_to_design_brain_state,
    batch_design_result_from_design_brain_payload,
)
from batch_design.models import BatchBeamCase


def _payload_for_state(state):
    return {
        "design_brain_result": {
            "outcome_id": "passing_exact_stop",
            "selected_candidate_label": "RECT 300 x 600",
        },
        "debug_trace": {
            "overview": {
                "all_key_pass": True,
                "any_fail": False,
                "worst_util": 0.86,
                "statuses": {"bending": "PASS", "shear": "PASS"},
                "actions_used": {
                    "Mu": state["uls_Mstar"],
                    "Vu": state["uls_Vstar"],
                    "Nu": state["uls_Nstar"],
                },
            }
        },
    }


def test_batch_case_to_design_brain_state_maps_imported_actions_without_mutating_base():
    base_state = {"b": 250.0, "D": 550.0, "fc": 40.0}
    case = BatchBeamCase(
        member_id="M1",
        existing_section="300 x 600",
        length=6.5,
        n_star=-25.0,
        vy_star=75.0,
        mz_star=180.0,
    )

    mapped = batch_case_to_design_brain_state(case, base_state)

    assert base_state == {"b": 250.0, "D": 550.0, "fc": 40.0}
    assert mapped["uls_Mstar"] == 180.0
    assert mapped["Mu_star"] == 180.0
    assert mapped["uls_Mstar_pos_manual"] == 180.0
    assert mapped["uls_Mstar_neg_manual"] == 0.0
    assert mapped["uls_Vstar"] == 75.0
    assert mapped["Vu_star"] == 75.0
    assert mapped["uls_Nstar"] == -25.0
    assert mapped["span_L_m"] == 6.5
    assert mapped["b"] == 300.0
    assert mapped["bw"] == 300.0
    assert mapped["D"] == 600.0
    assert mapped["batch_design_concrete_section"] == "RECT 300 x 600"
    assert mapped["batch_design_action_mapping"] == {
        "moment_component": "mz_star",
        "shear_component": "vy_star",
    }


def test_batch_case_to_design_brain_state_ignores_non_concrete_existing_section():
    base_state = {"b": 250.0, "bw": 250.0, "D": 550.0, "fc": 40.0}
    case = BatchBeamCase(
        member_id="M1",
        existing_section="310UB40",
        length=6.5,
        vy_star=75.0,
        mz_star=180.0,
    )

    mapped = batch_case_to_design_brain_state(case, base_state)

    assert mapped["uls_Mstar"] == 180.0
    assert mapped["uls_Vstar"] == 75.0
    assert mapped["span_L_m"] == 6.5
    assert mapped["b"] == 250.0
    assert mapped["bw"] == 250.0
    assert mapped["D"] == 550.0
    assert "batch_design_concrete_section" not in mapped


def test_batch_case_to_design_brain_state_can_use_alternate_action_components():
    case = BatchBeamCase(member_id="M2", vy_star=20.0, vz_star=95.0, my_star=-140.0, mz_star=40.0)

    mapped = batch_case_to_design_brain_state(
        case,
        {},
        assumptions={"moment_component": "my_star", "shear_component": "vz_star"},
    )

    assert mapped["uls_Mstar"] == -140.0
    assert mapped["uls_Mstar_pos_manual"] == 0.0
    assert mapped["uls_Mstar_neg_manual"] == 140.0
    assert mapped["uls_Vstar"] == 95.0
    assert mapped["batch_design_action_mapping"] == {
        "moment_component": "my_star",
        "shear_component": "vz_star",
    }


def test_adapter_calls_existing_single_beam_runner_with_mapped_state_and_matches_direct_payload_projection():
    calls = []
    case = BatchBeamCase(member_id="M3", existing_section="300 x 600", vy_star=80.0, mz_star=150.0)

    def base_state_provider():
        return {"fc": 40.0, "b": 300.0, "D": 600.0}

    def design_guidance_runner(state, **kwargs):
        calls.append({"state": dict(state), "kwargs": dict(kwargs)})
        return _payload_for_state(state)

    adapter = BatchDesignGuidanceAdapter(
        base_state_provider=base_state_provider,
        design_guidance_runner=design_guidance_runner,
    )

    adapter_result = adapter.run_case(case, assumptions={"moment_component": "mz_star"})
    direct_state = batch_case_to_design_brain_state(
        case,
        base_state_provider(),
        assumptions={"moment_component": "mz_star"},
    )
    direct_result = batch_design_result_from_design_brain_payload(
        case,
        _payload_for_state(direct_state),
        mapped_state=direct_state,
    )

    assert len(calls) == 1
    assert calls[0]["state"] == direct_state
    assert calls[0]["kwargs"] == {
        "guidance_debug_verbose": True,
        "debug_enabled": False,
        "request_kind": "auto_design",
    }
    assert adapter_result.to_dict() == direct_result.to_dict()
    assert adapter_result.passed is True
    assert adapter_result.selected_section == "RECT 300 x 600"
    assert adapter_result.utilisation == 0.86


def test_adapter_returns_controlled_failure_for_invalid_single_beam_runner_payload():
    adapter = BatchDesignGuidanceAdapter(
        base_state_provider=lambda: {},
        design_guidance_runner=lambda state, **kwargs: None,
    )

    result = adapter.run_case(BatchBeamCase(member_id="bad", mz_star=10.0))

    assert result.passed is False
    assert result.error == "Design Brain runner returned a non-dict payload."
    assert result.warnings[0].severity == "error"
