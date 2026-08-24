from __future__ import annotations

from batch_design.models import BatchBeamCase, BatchDesignResult
from batch_design.runner import run_batch_design
from batch_design.ui.results_table import design_results_frame
from batch_design.ui.passive_capacity import apply_passive_capacity_checks
from batch_design.ui.project_beam_load_table import project_beam_editor_styler
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
        "statuses": {},
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


def test_current_design_request_uses_authoritative_calculation_without_proposal(monkeypatch) -> None:
    from inputs_application import batch_design_guidance
    from state_and_helpers import SHARED_DEFAULTS

    class _ForbiddenDesignBrainService:
        def run(self, request):
            del request
            raise AssertionError("current-design capacity must not activate Design Brain")

    monkeypatch.setattr(
        batch_design_guidance,
        "_V2_BATCH_DESIGN_BRAIN_SERVICE",
        _ForbiddenDesignBrainService(),
    )

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

    payload = batch_design_guidance.compute_design_guidance_items(
        state,
        request_kind="current_design",
    )

    debug = payload["debug_trace"]
    assert debug["request_kind"] == "current_design"
    assert debug["result_basis"] == "current_design"
    assert debug["overview"]["family_capacities"]["bending"] > 0.0
    assert payload["design_brain_result"]["selected_updates"] == {}


class _PassiveCapacityOnlyAdapter:
    def __init__(self) -> None:
        self.current_calls = 0
        self.design_brain_calls = 0

    def evaluate_current_case(self, case, *, assumptions=None, base_state=None):
        del assumptions, base_state
        self.current_calls += 1
        return BatchDesignResult(
            member_id=case.member_id,
            input_case=case,
            passed=True,
            utilisation=0.82,
            raw_result={
                "design_brain_payload": {
                    "debug_trace": {
                        "overview": {
                            "statuses": {
                                "bending": "PASS",
                                "shear": "PASS",
                                "crack": "PASS",
                                "deflection": "PASS",
                            },
                            "family_utilisations": {
                                "bending": 0.82,
                                "shear": 0.61,
                                "crack": 0.45,
                                "deflection": 0.50,
                            },
                            "family_capacities": {
                                "bending": 245.0,
                                "shear": 310.0,
                            },
                        }
                    }
                }
            },
        )

    def run_case(self, *args, **kwargs):
        del args, kwargs
        self.design_brain_calls += 1
        raise AssertionError("passive table status must not run Design Brain")


def test_project_table_passively_calculates_status_without_design_brain() -> None:
    import pandas as pd

    adapter = _PassiveCapacityOnlyAdapter()
    frame = pd.DataFrame(
        [
            {
                "beam_id": "beam_1",
                "beam_label": "Beam 1",
                "sec_shape": "RECT",
                "b": 300.0,
                "D": 600.0,
                "L": 6.0,
                "mz_star": 200.0,
                "vy_star": 100.0,
            }
        ]
    )
    cache = {}

    result = apply_passive_capacity_checks(
        frame,
        adapter=adapter,
        beam_records={"beam_1": {"params": {"b": 300.0, "D": 600.0}}},
        assumptions={},
        cache=cache,
    )

    row = result.iloc[0].to_dict()
    assert adapter.current_calls == 1
    assert adapter.design_brain_calls == 0
    assert row["capacity_status"] == "PASS"
    assert row["current_phi_mu_knm"] == 245.0
    assert row["current_phi_vu_kn"] == 310.0
    assert row["current_utilisation"] == 0.82
    assert row["Mu_utilisation"] == 0.82

    # A normal Streamlit rerun reuses the calculation-only result.
    second = apply_passive_capacity_checks(
        frame,
        adapter=adapter,
        beam_records={"beam_1": {"params": {"b": 300.0, "D": 600.0}}},
        assumptions={},
        cache=cache,
    )
    assert adapter.current_calls == 1
    assert second.iloc[0]["capacity_status"] == "PASS"


def test_project_table_passive_capacity_cache_invalidates_with_actions() -> None:
    import pandas as pd

    adapter = _PassiveCapacityOnlyAdapter()
    cache = {}
    frame = pd.DataFrame(
        [{"beam_id": "beam_1", "b": 300.0, "D": 600.0, "mz_star": 200.0}]
    )
    common = {
        "adapter": adapter,
        "beam_records": {"beam_1": {"params": {"b": 300.0, "D": 600.0}}},
        "assumptions": {},
        "cache": cache,
    }

    apply_passive_capacity_checks(frame, **common)
    changed = frame.copy(deep=True)
    changed.loc[0, "mz_star"] = 250.0
    apply_passive_capacity_checks(changed, **common)

    assert adapter.current_calls == 2
    assert adapter.design_brain_calls == 0


def test_project_table_row_styles_are_status_coordinated() -> None:
    import pandas as pd

    frame = pd.DataFrame(
        [
            {"beam_id": "pass", "overall_status": "PASS"},
            {"beam_id": "fail", "overall_status": "FAIL"},
            {"beam_id": "check", "overall_status": "CHECK"},
        ]
    )
    computed = project_beam_editor_styler(frame)._compute()

    assert ("background-color", "#ecfdf3") in computed.ctx[(0, 0)]
    assert ("background-color", "#fff1f2") in computed.ctx[(1, 0)]
    assert ("background-color", "#fffbeb") in computed.ctx[(2, 0)]
