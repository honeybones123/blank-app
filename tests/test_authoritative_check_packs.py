from application.contracts.design_brain import AuthoritativeDesignResult
from application.design_result_store import EngineeringResultStore
from bending_checks_helpers import build_bending_check_rows_from_state
from crack_checks_helpers import build_crack_check_rows_from_state
from deflection_checks_helpers import build_deflection_check_rows_from_state
from shear_checks_helpers import build_shear_check_rows_from_state
from inputs_application.authoritative_check_packs import (
    current_authoritative_check_pack,
    current_authoritative_family,
)
from inputs_application.engineering_input_store import InputSnapshotStore


def _state_with_pack(*, revision_offset: int = 0) -> dict:
    state: dict = {}
    inputs = InputSnapshotStore(state)
    inputs.capture_draft({"b": 250.0}, source="test")
    transaction = inputs.commit_draft(source="test")
    result = AuthoritativeDesignResult(
        engineering_hash="engineering-hash",
        current_calculations={
            "source": "inputs_v2",
            "families": {
                "creep": {"phi_cc_t": 1.25},
                "shrinkage": {"eps_cs_total_micro": 612.0},
            },
            "packs": {
                "bending": {
                    "source": "inputs_v2",
                    "rows": [{"uid": "v2_bending_capacity", "status": "PASS"}],
                },
                "shear": {
                    "source": "inputs_v2",
                    "rows": [{"uid": "v2_shear_capacity", "status": "PASS"}],
                },
                "crack": {
                    "source": "inputs_v2",
                    "rows": [{"uid": "v2_crack_control", "status": "INFO"}],
                },
                "deflection": {
                    "source": "inputs_v2",
                    "rows": [{"uid": "v2_deflection", "status": "INFO"}],
                },
            }
        },
    )
    EngineeringResultStore(state).store(
        result,
        source_input_revision=transaction.revision + revision_offset,
    )
    return state


def test_authoritative_pack_is_returned_as_a_defensive_copy() -> None:
    state = _state_with_pack()

    first = current_authoritative_check_pack(state, "bending")
    assert first is not None
    first["rows"][0]["status"] = "FAIL"

    second = current_authoritative_check_pack(state, "bending")
    assert second is not None
    assert second["rows"][0]["status"] == "PASS"


def test_authoritative_pack_rejects_a_stale_input_revision() -> None:
    state = _state_with_pack(revision_offset=-1)

    assert current_authoritative_check_pack(state, "bending") is None


def test_authoritative_pack_rejects_non_v2_sources() -> None:
    state = _state_with_pack()
    result = EngineeringResultStore(state).current()
    assert result is not None
    result.current_calculations["packs"]["bending"]["source"] = "legacy"

    assert current_authoritative_check_pack(state, "bending") is None


def test_all_summary_helpers_use_the_same_revision_matched_v2_result() -> None:
    state = _state_with_pack()

    assert build_bending_check_rows_from_state(state)["rows"][0]["uid"] == "v2_bending_capacity"
    assert build_shear_check_rows_from_state(state)["rows"][0]["uid"] == "v2_shear_capacity"
    assert build_crack_check_rows_from_state(state)["rows"][0]["uid"] == "v2_crack_control"
    assert build_deflection_check_rows_from_state(state)["rows"][0]["uid"] == "v2_deflection"


def test_page_local_stale_values_cannot_replace_authoritative_summary_packs() -> None:
    state = _state_with_pack()
    before = {
        "bending": build_bending_check_rows_from_state(state),
        "shear": build_shear_check_rows_from_state(state),
        "crack": build_crack_check_rows_from_state(state),
        "deflection": build_deflection_check_rows_from_state(state),
    }

    # Simulate stale values left by visiting detailed result pages.  Summary
    # consumers must continue to project the revision-matched V2 publication.
    state.update(
        {
            "Mu_star": 999999.0,
            "phi_Mu_cap": 1.0,
            "Vu_star": 999999.0,
            "phi_Vu": 1.0,
            "w_calc": 99.0,
            "delta_total": 999.0,
        }
    )

    after = {
        "bending": build_bending_check_rows_from_state(state),
        "shear": build_shear_check_rows_from_state(state),
        "crack": build_crack_check_rows_from_state(state),
        "deflection": build_deflection_check_rows_from_state(state),
    }
    assert after == before


def test_time_dependent_pages_read_the_same_authoritative_family_result() -> None:
    state = _state_with_pack()

    assert current_authoritative_family(state, "creep") == {"phi_cc_t": 1.25}
    assert current_authoritative_family(state, "shrinkage") == {
        "eps_cs_total_micro": 612.0
    }


def test_time_dependent_family_rejects_stale_input_revision() -> None:
    state = _state_with_pack(revision_offset=-1)

    assert current_authoritative_family(state, "creep") is None
    assert current_authoritative_family(state, "shrinkage") is None


def test_general_pages_prefer_the_active_beam_publication_over_transient_result() -> None:
    state: dict = {"active_beam_id": "beam-a"}
    inputs = InputSnapshotStore(state)
    beam_snapshot = inputs.commit_for_beam(
        "beam-a",
        {"b": 325.0},
        source="test",
    )
    beam_result = AuthoritativeDesignResult(
        engineering_hash=str(beam_snapshot.engineering_hash),
        current_calculations={
            "source": "inputs_v2",
            "packs": {
                "shear": {
                    "source": "inputs_v2",
                    "summary_capacity_kN": 288.5,
                    "rows": [{"uid": "beam-owned-shear"}],
                }
            },
        },
    )
    transient_result = AuthoritativeDesignResult(
        engineering_hash="stale-page-local-result",
        current_calculations={
            "source": "inputs_v2",
            "packs": {
                "shear": {
                    "source": "inputs_v2",
                    "summary_capacity_kN": 304.2,
                    "rows": [{"uid": "transient-shear"}],
                }
            },
        },
    )
    EngineeringResultStore(state).store(
        transient_result,
        source_input_revision=beam_snapshot.revision,
    )
    state["_inputs_authoritative_design_result_by_beam_v1"] = {
        "beam-a": beam_result
    }
    state["_inputs_authoritative_design_result_revision_by_beam_v1"] = {
        "beam-a": beam_snapshot.revision
    }

    pack = current_authoritative_check_pack(state, "shear")

    assert pack is not None
    assert pack["summary_capacity_kN"] == 288.5
    assert pack["rows"][0]["uid"] == "beam-owned-shear"


def test_general_pages_reject_a_stale_active_beam_publication() -> None:
    state: dict = {"active_beam_id": "beam-a"}
    inputs = InputSnapshotStore(state)
    beam_snapshot = inputs.commit_for_beam(
        "beam-a",
        {"b": 325.0},
        source="test",
    )
    state["_inputs_authoritative_design_result_by_beam_v1"] = {
        "beam-a": AuthoritativeDesignResult(
            engineering_hash="old",
            current_calculations={
                "source": "inputs_v2",
                "packs": {
                    "shear": {
                        "source": "inputs_v2",
                        "rows": [{"uid": "stale"}],
                    }
                },
            },
        )
    }
    state["_inputs_authoritative_design_result_revision_by_beam_v1"] = {
        "beam-a": beam_snapshot.revision - 1
    }

    assert current_authoritative_check_pack(state, "shear") is None


def test_summary_helpers_never_fall_back_to_page_local_calculations() -> None:
    state = {
        "Mu_star": 999999.0,
        "phi_Mu_cap": 1.0,
        "Vu_star": 999999.0,
        "phi_Vu": 1.0,
        "w_calc": 99.0,
        "delta_total": 999.0,
    }

    packs = (
        build_bending_check_rows_from_state(state),
        build_shear_check_rows_from_state(state),
        build_crack_check_rows_from_state(state),
        build_deflection_check_rows_from_state(state),
    )

    assert all(pack["source"] == "inputs_v2_unavailable" for pack in packs)
    assert all(pack["rows"][0]["status"] == "INFO" for pack in packs)
    assert all("999" not in str(pack) for pack in packs)


def test_retired_summary_fallback_implementations_are_deleted() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    forbidden = {
        "crack_checks_helpers.py": "compute_crack_results(publish=False)",
        "deflection_checks_helpers.py": "calc_deflection_as3600",
        "shear_checks_helpers.py": "run_shear_calc() directly",
        "shear_page_runtime.py": "build_shear_summary_rows_with_overrides",
        "calculations/shear.py": "def build_shear_summary_rows_with_overrides",
    }
    for relative_path, marker in forbidden.items():
        assert marker not in (root / relative_path).read_text(encoding="utf-8")
