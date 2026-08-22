from __future__ import annotations

from batch_design.models import BatchBeamCase, BatchDesignResult
from batch_design.runner import run_batch_design
from batch_design.ui.results_table import design_results_frame
from application.beam_summary_policy import _sanitize_beam_summary


class _CapacityThenOptimiseAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def evaluate_current_case(self, case, *, assumptions=None, base_state=None):
        del assumptions, base_state
        self.calls.append((case.member_id, "current_capacity"))
        return BatchDesignResult(
            member_id=case.member_id,
            input_case=case,
            passed=False,
            selected_section=case.existing_section,
            utilisation=1.6,
            raw_result={
                "design_brain_payload": {
                    "debug_trace": {
                        "engineering_hash": "current-hash",
                        "input_revision": 4,
                        "overview": {
                            "family_utilisations": {
                                "bending": 1.6,
                                "shear": 0.7,
                            },
                            "family_capacities": {
                                "bending": 125.0,
                                "shear": 210.0,
                            },
                        },
                    }
                }
            },
        )

    def run_case(
        self,
        case,
        *,
        assumptions=None,
        base_state=None,
        request_kind=None,
    ):
        del assumptions, base_state, request_kind
        self.calls.append((case.member_id, "optimisation"))
        return BatchDesignResult(
            member_id=case.member_id,
            input_case=case,
            passed=True,
            selected_section=case.existing_section,
            utilisation=0.92,
            raw_result={"design_brain_payload": {}},
        )


def test_batch_calculates_current_capacity_before_optimisation() -> None:
    adapter = _CapacityThenOptimiseAdapter()
    case = BatchBeamCase(
        member_id="beam_1",
        existing_section="300 x 600",
        mz_star=200.0,
    )

    [result] = run_batch_design([case], adapter)

    assert adapter.calls == [
        ("beam_1", "current_capacity"),
        ("beam_1", "optimisation"),
    ]
    assert result.passed is True
    assert result.utilisation == 0.92
    assert result.raw_result["batch_execution_order"] == (
        "current_capacity",
        "optimisation",
    )
    assert result.raw_result["pre_optimisation"] == {
        "calculated": True,
        "passed": False,
        "selected_section": "300 x 600",
        "utilisation": 1.6,
        "family_utilisations": {"bending": 1.6, "shear": 0.7},
        "family_capacities": {"bending": 125.0, "shear": 210.0},
        "engineering_hash": "current-hash",
        "input_revision": 4,
        "error": None,
    }


def test_batch_result_table_exposes_current_capacity_and_optimised_result() -> None:
    adapter = _CapacityThenOptimiseAdapter()
    case = BatchBeamCase(member_id="beam_1", existing_section="300 x 600", mz_star=200.0)
    results = run_batch_design([case], adapter)

    row = design_results_frame(results).iloc[0].to_dict()

    assert row["Current phiMu (kNm)"] == 125.0
    assert row["Current phiVu (kN)"] == 210.0
    assert row["Current utilisation"] == 1.6
    assert row["Optimised utilisation"] == 0.92


def test_beam_summary_preserves_pre_optimisation_capacity() -> None:
    summary = _sanitize_beam_summary(
        {
            "batch_pre_optimisation_utilisation": 1.6,
            "batch_pre_optimisation_phiMu_kNm": 125.0,
            "batch_pre_optimisation_phiVu_kN": 210.0,
        }
    )

    assert summary["batch_pre_optimisation_utilisation"] == 1.6
    assert summary["batch_pre_optimisation_phiMu_kNm"] == 125.0
    assert summary["batch_pre_optimisation_phiVu_kN"] == 210.0


def test_project_beam_table_exposes_pre_optimisation_capacity(monkeypatch) -> None:
    from batch_design.ui import project_beam_manager_adapters as adapters

    monkeypatch.setattr(
        adapters,
        "build_beam_schedule_rows",
        lambda: [
            {
                "beam_id": "beam_1",
                "beam_label": "Beam 1",
                "current_utilisation": 1.6,
                "current_phi_mu_knm": 125.0,
                "current_phi_vu_kn": 210.0,
            }
        ],
    )

    row = adapters.build_beam_schedule_df().iloc[0].to_dict()

    assert row["current_utilisation"] == 1.6
    assert row["current_phi_mu_knm"] == 125.0
    assert row["current_phi_vu_kn"] == 210.0


class _FailedCapacityAdapter(_CapacityThenOptimiseAdapter):
    def evaluate_current_case(self, case, *, assumptions=None, base_state=None):
        del assumptions, base_state
        self.calls.append((case.member_id, "current_capacity"))
        return BatchDesignResult(
            member_id=case.member_id,
            input_case=case,
            passed=False,
            error="current capacity failed",
        )


def test_batch_does_not_optimise_when_current_capacity_cannot_be_calculated() -> None:
    adapter = _FailedCapacityAdapter()
    case = BatchBeamCase(member_id="beam_1", existing_section="300 x 600", mz_star=200.0)

    [result] = run_batch_design([case], adapter)

    assert adapter.calls == [("beam_1", "current_capacity")]
    assert result.error == "current capacity failed"


def test_current_design_request_uses_authoritative_calculation_without_proposal() -> None:
    from inputs_application.batch_design_guidance import compute_design_guidance_items
    from state_and_helpers import SHARED_DEFAULTS

    state = dict(SHARED_DEFAULTS)
    state.update(
        {
            "b": 300.0,
            "bw": 300.0,
            "D": 600.0,
            "fc": 40.0,
            "fsy": 500.0,
            "Es": 200_000.0,
            "uls_Mstar": 200.0,
            "Mu_star": 200.0,
            "uls_Mstar_pos_manual": 200.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 3,
            "bot_row_1_dia": 20.0,
            "bot_row_1_spacing": 200.0,
            "top_row_count": 1,
            "top_row_1_mode": "Count",
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "top_row_1_spacing": 200.0,
            "_inputs_workspace_revision": 1,
        }
    )

    payload = compute_design_guidance_items(state, request_kind="current_design")

    debug = payload["debug_trace"]
    assert debug["request_kind"] == "current_design"
    assert debug["result_basis"] == "current_design"
    assert debug["overview"]["family_capacities"]["bending"] > 0.0
    assert payload["design_brain_result"]["selected_updates"] == {}
