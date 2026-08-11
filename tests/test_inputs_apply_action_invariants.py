from __future__ import annotations

from inputs_application.adapters import SharedStateSessionPort
from inputs_application.contracts import InputsSessionMutation
from inputs_application.engineering_input_store import InputSnapshotStore


def _baseline() -> dict[str, object]:
    return {
        "b": 250.0,
        "D": 400.0,
        "L": 5000.0,
        "actions_source": "manual",
        "actions_mode": "manual",
        "design_actions_source": "beam_inputs",
        "uls_Mstar": 321.0,
        "uls_Mstar_pos_manual": 321.0,
        "uls_Mstar_neg_manual": -45.0,
        "uls_Vstar": 123.0,
        "uls_Nstar": 17.0,
        "sls_Mstar": 190.0,
        "sls_Mstar_pos_manual": 190.0,
        "sls_Mstar_neg_manual": -22.0,
        "sls_Vstar": 75.0,
        "sls_Nstar": 9.0,
        "Tu_star": 12.0,
        "P_star": 3.0,
        "N_star": 17.0,
    }


def test_typed_apply_merges_into_canonical_snapshot_without_changing_actions() -> None:
    state: dict[str, object] = {"active_beam_id": "beam-1"}
    store = InputSnapshotStore(state)
    before = store.commit_active_beam(
        _baseline(),
        changed_keys=tuple(_baseline()),
        source="test:seed",
    )
    finalised: list[dict[str, object]] = []

    def set_shared(key: str, value: object, **_kwargs: object) -> None:
        state[key] = value

    port = SharedStateSessionPort(
        session_state=state,
        set_shared=set_shared,
        finalize_publish=lambda **kwargs: finalised.append(dict(kwargs)),
        persist_active_beam=lambda: None,
        store_post_apply_acceptance=False,
    )
    port.commit(
        InputsSessionMutation(
            updates={
                "b": 300.0,
                "bot_row_1_bars": 4,
                # Even a malformed payload cannot overwrite action authority.
                "uls_Mstar": 0.0,
                "sls_Mstar": 0.0,
            },
            status="rerun_required",
            rerun_required=True,
        )
    )

    after = store.current_for_beam("beam-1")
    assert after.revision == before.revision + 1
    assert after.snapshot["b"] == 300.0
    assert after.snapshot["bot_row_1_bars"] == 4
    for key, value in _baseline().items():
        if key not in {"b", "D", "L"}:
            assert after.snapshot[key] == value
    assert state["_typed_apply_input_transaction_probe"][
        "design_actions_preserved"
    ] is True
    assert finalised


def test_zero_actions_remain_zero_only_when_zero_before_apply() -> None:
    state: dict[str, object] = {"active_beam_id": "beam-2"}
    baseline = _baseline()
    for key in tuple(baseline):
        if key.startswith(("uls_", "sls_")) or key in {
            "Tu_star",
            "P_star",
            "N_star",
        }:
            baseline[key] = 0.0
    store = InputSnapshotStore(state)
    store.commit_active_beam(
        baseline,
        changed_keys=tuple(baseline),
        source="test:seed",
    )

    port = SharedStateSessionPort(
        session_state=state,
        set_shared=lambda key, value, **_kwargs: state.__setitem__(key, value),
        finalize_publish=lambda **_kwargs: None,
        persist_active_beam=lambda: None,
        store_post_apply_acceptance=False,
    )
    port.commit(
        InputsSessionMutation(
            updates={"D": 450.0},
            status="rerun_required",
            rerun_required=True,
        )
    )

    after = store.current_for_beam("beam-2")
    assert after.snapshot["D"] == 450.0
    assert after.snapshot["uls_Mstar"] == 0.0
    assert after.snapshot["sls_Mstar"] == 0.0
