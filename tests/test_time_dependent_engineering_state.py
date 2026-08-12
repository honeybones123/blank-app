from __future__ import annotations

import pytest

from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.time_dependent_engineering_state import (
    resolve_time_dependent_engineering_state,
)


def _commit(state: dict, *, beam_id: str = "B1") -> dict:
    session = {"active_beam_id": beam_id}
    InputSnapshotStore(session).commit_for_beam(
        beam_id,
        state,
        source="test",
    )
    return session


def _base_state(**updates) -> dict:
    state = {
        "sec_shape": "RECT",
        "b": 300.0,
        "D": 600.0,
        "fc": 40.0,
        "Ec": 30000.0,
        "actions_mode": "manual",
        "actions_source": "Manual design actions (inputs below)",
        "uls_Mstar": 500.0,
        "sls_Mstar": 120.0,
        "sls_Mstar_pos_manual": 120.0,
        "sls_Mstar_neg_manual": 0.0,
        "cover_bot": 30.0,
        "cover_top": 30.0,
        "lig_d": 0.0,
        "nb_bot": 3,
        "db_bot": 20.0,
        "nb_top": 2,
        "db_top": 12.0,
    }
    state.update(updates)
    return state


def test_creep_projection_uses_committed_sls_action_not_stale_session_mirror():
    session = _commit(_base_state())
    session.update(
        {
            "sls_Mstar": 0.0,
            "stress_ratio": 0.0,
            "sustained_Mstar_kNm": 0.0,
        }
    )

    resolved = resolve_time_dependent_engineering_state(session)

    assert resolved.values["sustained_Mstar_kNm"] == pytest.approx(120.0)
    assert resolved.values["sustained_sigma_cs_mpa"] > 0.0
    assert resolved.values["stress_ratio"] > 0.0


def test_uls_change_does_not_replace_sls_sustained_action():
    first = resolve_time_dependent_engineering_state(
        _commit(_base_state(uls_Mstar=100.0))
    )
    second = resolve_time_dependent_engineering_state(
        _commit(_base_state(uls_Mstar=900.0))
    )

    assert second.values["sustained_Mstar_kNm"] == pytest.approx(
        first.values["sustained_Mstar_kNm"]
    )
    assert second.values["stress_ratio"] == pytest.approx(
        first.values["stress_ratio"]
    )


def test_shrinkage_drivers_follow_committed_geometry_and_ignore_page_local_loads():
    session = _commit(_base_state(b=425.0, D=725.0, fc=50.0))
    session.update(
        {
            "load_g_udl": 99.0,
            "design_M_sls_kNm": 999.0,
            "b": 200.0,
            "D": 300.0,
            "fc": 25.0,
        }
    )

    resolved = resolve_time_dependent_engineering_state(session)

    assert resolved.values["b"] == pytest.approx(425.0)
    assert resolved.values["D"] == pytest.approx(725.0)
    assert resolved.values["fc"] == pytest.approx(50.0)
