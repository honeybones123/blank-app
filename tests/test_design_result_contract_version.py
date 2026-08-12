from application.contracts.design_brain import (
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)
from application.design_result_store import EngineeringResultStore
from application.design_run_coordinator import ensure_design_result


def _snapshot(depth_mm: int) -> EngineeringInputSnapshot:
    return EngineeringInputSnapshot(
        geometry={"b": 250, "D": depth_mm},
        materials={"fc": 40},
        reinforcement={"bottom": {"count": 3, "diameter": 20}},
        design_actions={"Mu": 200, "Vu": 200},
        design_settings={},
    )


def _result(snapshot: EngineeringInputSnapshot, version: str):
    return build_authoritative_design_result(
        engineering_snapshot=snapshot,
        current_calculations={"calculation_contract_version": version},
        governing_family="TARGET_BAND_REACHED",
        family_outcome="PASS",
        final_publication={"outcome_state": "PASS"},
        display_model={"title": "Target band reached"},
        cta_model={"enabled": False},
        apply_payload={},
    )


def test_same_hash_result_from_old_calculation_contract_is_recomputed() -> None:
    snapshot = _snapshot(400)
    state = {}
    store = EngineeringResultStore(state)
    store.store(_result(snapshot, "inputs_v2.calculation.v5"))
    calls = []

    result = ensure_design_result(
        result_store=store,
        snapshot=snapshot,
        compute_fn=lambda value: (
            calls.append(value.engineering_hash)
            or _result(value, "inputs_v2.calculation.v6")
        ),
        expected_calculation_contract_version="inputs_v2.calculation.v6",
    )

    assert calls == [snapshot.engineering_hash]
    assert result.current_calculations["calculation_contract_version"] == (
        "inputs_v2.calculation.v6"
    )


def test_old_contract_lru_entry_is_not_restored_after_switching_hashes() -> None:
    snapshot_a = _snapshot(400)
    snapshot_b = _snapshot(425)
    state = {}
    store = EngineeringResultStore(state)
    store.store(_result(snapshot_a, "inputs_v2.calculation.v5"))
    store.store(_result(snapshot_b, "inputs_v2.calculation.v6"))
    calls = []

    result = ensure_design_result(
        result_store=store,
        snapshot=snapshot_a,
        compute_fn=lambda value: (
            calls.append(value.engineering_hash)
            or _result(value, "inputs_v2.calculation.v6")
        ),
        expected_calculation_contract_version="inputs_v2.calculation.v6",
    )

    assert calls == [snapshot_a.engineering_hash]
    assert result.current_calculations["calculation_contract_version"] == (
        "inputs_v2.calculation.v6"
    )
