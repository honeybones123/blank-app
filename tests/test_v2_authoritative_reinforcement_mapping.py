from __future__ import annotations

import math
import pytest

from application.contracts.design_brain import EngineeringInputSnapshot
from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)
from inputs_application.v2_engineering_calculation_adapter import (
    _beam_inputs_from_snapshot,
    _v2_api,
    calculate_v2_authoritative_result,
)


def test_engineering_snapshot_payload_is_recursively_immutable() -> None:
    snapshot = EngineeringInputSnapshot(
        geometry={"b": 275.0, "nested": {"values": [1, 2]}},
    )
    original_hash = snapshot.engineering_hash

    with pytest.raises(TypeError):
        snapshot.geometry["b"] = 300.0  # type: ignore[index]
    with pytest.raises(TypeError):
        snapshot.geometry["nested"]["values"][0] = 9  # type: ignore[index]

    exported = snapshot.to_dict()
    exported["geometry"]["nested"]["values"][0] = 9
    assert snapshot.geometry["nested"]["values"] == (1, 2)
    assert snapshot.engineering_hash == original_hash


def _snapshot_with_bottom_rows(*, row_1: tuple[int, int], row_2: tuple[int, int]) -> EngineeringInputSnapshot:
    return EngineeringInputSnapshot(
        geometry={"b": 275.0, "D": 500.0, "L": 2000.0, "sec_shape": "RECT"},
        materials={"fc": 40.0, "fsy": 500.0},
        reinforcement={
            "bot_row_1_bars": row_1[0],
            "bot_row_1_dia": row_1[1],
            "bot_row_2_bars": row_2[0],
            "bot_row_2_dia": row_2[1],
            "cover_bot": 40.0,
            "rowgap_bot": 60.0,
            "top_bars": 2,
            "db_top": 10,
            "cover_top": 40.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 150.0,
        },
        design_actions={"Mu": 135.0, "Vu": 0.0, "Tu": 0.0, "Nu": 0.0},
    )


def test_same_diameter_second_row_is_part_of_authoritative_v2_input() -> None:
    api = _v2_api()
    current, row_counts, _ = _beam_inputs_from_snapshot(
        _snapshot_with_bottom_rows(row_1=(4, 12), row_2=(4, 12)),
        api,
        revision=7,
    )

    assert current.bottom.bars == 8
    assert row_counts == (4, 4)
    assert current.bottom_arrangement is not None
    assert current.bottom_arrangement.total_bar_count == 8
    assert current.bottom_arrangement.clear_row_gap_mm == 60.0
    assert current.bottom_arrangement.effective_depth_mm == pytest.approx(408.0)

    result = api["EngineeringCalculator"]().calculate(current)
    expected_area = 8.0 * math.pi * 12.0**2 / 4.0
    assert result.families["bending"]["Ast_tension_mm2"] == expected_area
    assert result.families["ductility"]["effective_depth_mm"] == pytest.approx(408.0)


def test_mixed_diameter_rows_preserve_exact_area_and_area_weighted_depth() -> None:
    api = _v2_api()
    current, row_counts, _ = _beam_inputs_from_snapshot(
        _snapshot_with_bottom_rows(row_1=(3, 20), row_2=(2, 16)),
        api,
        revision=8,
    )

    assert current.bottom.bars == 5
    assert row_counts == (3, 2)
    assert current.bottom_arrangement is not None
    assert tuple(
        row.bar_diameter_mm for row in current.bottom_arrangement.rows
    ) == (20.0, 16.0)

    result = api["EngineeringCalculator"]().calculate(current)
    expected_area = (
        3.0 * math.pi * 20.0**2 / 4.0
        + 2.0 * math.pi * 16.0**2 / 4.0
    )
    assert result.families["bending"]["Ast_tension_mm2"] == expected_area
    assert result.families["ductility"]["effective_depth_mm"] == (
        current.bottom_arrangement.effective_depth_mm
    )


def test_runtime_aliases_preserve_shear_method_and_time_dependent_inputs() -> None:
    snapshot = EngineeringInputSnapshot(
        geometry={"b": 275.0, "D": 500.0, "L": 2000.0},
        materials={"fc": 40.0, "fsy": 500.0},
        reinforcement={
            "bot1_count": 4,
            "db_bot_1": 20,
            "bot2_count": 2,
            "db_bot_2": 16,
            "cover_bot": 40.0,
            "top_bars": 2,
            "db_top": 10,
            "cover_top": 40.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 150.0,
        },
        design_actions={"Mu": 100.0, "Vu": 100.0},
        design_settings={"k_v_method": "AS 3600 Clause 8.2.4.2 general method"},
    )
    api = _v2_api()
    current, rows, _ = _beam_inputs_from_snapshot(
        snapshot,
        api,
        revision=9,
        resolved_inputs={"t_shrink": 730.0, "t_creep": 540.0, "age_at_loading": 56.0},
    )

    assert rows == (4, 2)
    assert tuple(row.bar_diameter_mm for row in current.bottom_arrangement.rows) == (20.0, 16.0)
    assert current.shear.use_general_kv is True
    assert current.time_dependent.shrinkage_time_days == 730.0
    assert current.time_dependent.creep_time_days == 540.0
    assert current.time_dependent.age_at_loading_days == 56.0


def test_authoritative_creep_strain_uses_resolved_manual_sls_moment() -> None:
    snapshot = EngineeringInputSnapshot(
        geometry={"b": 300.0, "D": 600.0, "L": 4000.0, "sec_shape": "RECT"},
        materials={"fc": 40.0, "fsy": 500.0},
        reinforcement={
            "bot1_count": 4,
            "db_bot_1": 20,
            "cover_bot": 40.0,
            "top_bars": 2,
            "db_top": 12,
            "cover_top": 40.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 150.0,
        },
        design_actions={
            "resolved": {
                "Mu": 150.0,
                "Vu": 0.0,
                "SLS_M": 100.0,
                "SLS_M_pos": 100.0,
                "SLS_M_neg": 0.0,
                "SLS_V": 0.0,
            }
        },
    )

    result = calculate_v2_authoritative_result(
        engineering_snapshot=snapshot,
        resolved_inputs={},
        input_revision=10,
    )
    creep = result.current_calculations["families"]["creep"]

    assert creep["sustained_sigma_cs_mpa"] > 0.0
    assert creep["stress_ratio"] > 0.0
    assert creep["eps_cc_micro"] > 0.0


def test_authoritative_creep_strain_uses_load_analysis_sls_projection() -> None:
    resolved_inputs = {
        "b": 300.0,
        "D": 600.0,
        "L": 4000.0,
        "sec_shape": "RECT",
        "fc": 40.0,
        "fsy": 500.0,
        **{
            "bot1_count": 4,
            "db_bot_1": 20,
            "cover_bot": 40.0,
            "top_bars": 2,
            "db_top": 12,
            "cover_top": 40.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 150.0,
        },
        "actions_mode": "design",
        "actions_source": "Teaching SFD/BMD page (|M|max, |V|max)",
        "sfd_Mmax_abs_kNm": 150.0,
        "M_pos_max_uls_kNm": 150.0,
        "M_neg_min_uls_kNm": 0.0,
        "sfd_Msls_max_kNm": 90.0,
        "M_pos_max_sls_kNm": 90.0,
        "M_neg_min_sls_kNm": 0.0,
    }
    snapshot = build_engineering_input_snapshot_from_resolved_state(
        resolved_inputs
    )

    result = calculate_v2_authoritative_result(
        engineering_snapshot=snapshot,
        resolved_inputs=resolved_inputs,
        input_revision=11,
    )
    creep = result.current_calculations["families"]["creep"]

    assert creep["sustained_sigma_cs_mpa"] > 0.0
    assert creep["eps_cc_micro"] > 0.0


def test_bending_summary_publishes_every_authoritative_detailed_check() -> None:
    snapshot = _snapshot_with_bottom_rows(
        row_1=(4, 20),
        row_2=(0, 0),
    )
    result = calculate_v2_authoritative_result(
        engineering_snapshot=snapshot,
        resolved_inputs={},
        input_revision=12,
    )
    assert (
        result.current_calculations["calculation_contract_version"]
        == "inputs_v2.calculation.v2"
    )
    rows = result.current_calculations["packs"]["bending"]["rows"]
    rows_by_uid = {row["uid"]: row for row in rows}

    assert set(rows_by_uid) == {
        "v2_bending_capacity",
        "v2_bending_minimum_tensile",
        "v2_bending_ductility",
        "v2_bending_service_moment",
        "v2_bending_minimum_capacity",
    }
    minimum_capacity = rows_by_uid["v2_bending_minimum_capacity"]
    assert "Mu,min =" in minimum_capacity["action"]
    assert "ϕMu,cap =" in minimum_capacity["capacity"]
    assert minimum_capacity["util"] != "—"
    assert minimum_capacity["status"] in {"PASS", "FAIL"}
