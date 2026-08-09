"""Deterministic 1,000-operation Runtime state and calculation fuzz gate."""

from __future__ import annotations

from collections import Counter
import math
import random
from typing import Any, Callable

from application.contracts.design_brain import stable_authority_hash
from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)
from inputs_application.new_design_brain_adapter import calculate_v2_authoritative_result
from tools.verification.recipes.one_click_recipe_defs import build_state


SEED = 20260809
SEQUENCES = 50
OPERATIONS_PER_SEQUENCE = 20
OPERATION_TYPES = (
    "geometry",
    "materials",
    "longitudinal_reinforcement",
    "shear_reinforcement",
    "manual_actions",
    "load_analysis_actions",
    "serviceability",
    "locks",
    "ui_state",
    "navigation",
)


def _different(rng: random.Random, current: Any, choices: tuple[Any, ...]) -> Any:
    alternatives = tuple(value for value in choices if value != current)
    return rng.choice(alternatives or choices)


def _geometry(state: dict[str, Any], rng: random.Random) -> None:
    state["b"] = _different(rng, state.get("b"), (250.0, 300.0, 350.0, 450.0, 600.0))
    state["bw"] = state["b"]
    state["D"] = _different(rng, state.get("D"), (350.0, 400.0, 500.0, 650.0, 800.0))
    state["L"] = _different(rng, state.get("L"), (4000.0, 6000.0, 8000.0, 10000.0))
    state["sec_shape"] = _different(rng, state.get("sec_shape"), ("RECT", "T", "I"))


def _materials(state: dict[str, Any], rng: random.Random) -> None:
    state["fc"] = _different(rng, state.get("fc"), (20.0, 25.0, 32.0, 40.0, 50.0, 65.0, 80.0, 100.0))
    state["fsy"] = 500.0


def _longitudinal(state: dict[str, Any], rng: random.Random) -> None:
    bars = _different(rng, state.get("bot_row_1_bars"), (2, 3, 4, 5, 6, 8, 10, 12))
    diameter = _different(rng, state.get("bot_row_1_dia"), (10.0, 12.0, 16.0, 20.0, 24.0, 28.0, 32.0))
    cover = _different(rng, state.get("cover_bot"), (25.0, 30.0, 40.0, 50.0, 60.0))
    state.update(
        bot1_count=bars,
        bot_row_1_bars=bars,
        nb_bot=bars,
        db_bot_1=diameter,
        bot_row_1_dia=diameter,
        db_bot=diameter,
        cover_bot=cover,
    )


def _shear(state: dict[str, Any], rng: random.Random) -> None:
    if rng.random() < 0.2:
        state.update(lig_d=0, lig_legs=0, s_lig=200.0)
        return
    state.update(
        lig_d=_different(rng, state.get("lig_d"), (10, 12, 16)),
        lig_legs=_different(rng, state.get("lig_legs"), (2, 4, 6, 8)),
        s_lig=_different(rng, state.get("s_lig"), (75.0, 100.0, 150.0, 200.0, 250.0, 300.0)),
    )


def _manual_actions(state: dict[str, Any], rng: random.Random) -> None:
    moment = rng.choice((0.0, 20.0, 100.0, 200.0, 500.0, 900.0))
    shear = rng.choice((0.0, 10.0, 75.0, 200.0, 500.0, 900.0))
    state.update(
        actions_mode="manual",
        uls_Mstar=moment,
        uls_Mstar_pos_manual=moment,
        uls_Mstar_neg_manual=0.0,
        Mu_star=moment,
        Mu_star_manual=moment,
        uls_Vstar=shear,
        Vu_star=shear,
        Vu_star_manual=shear,
    )


def _load_actions(state: dict[str, Any], rng: random.Random) -> None:
    positive = rng.choice((0.0, 50.0, 150.0, 350.0, 700.0))
    negative = -rng.choice((0.0, 25.0, 100.0, 250.0))
    shear = rng.choice((0.0, 40.0, 160.0, 400.0, 800.0))
    state.update(
        actions_mode="design",
        design_actions_source="max",
        M_pos_max_uls_kNm=positive,
        M_neg_min_uls_kNm=negative,
        M_pos_max_sls_kNm=0.7 * positive,
        M_neg_min_sls_kNm=0.7 * negative,
        V_max_abs_uls_kN=shear,
        N_max_abs_uls_kN=0.0,
    )


def _serviceability(state: dict[str, Any], rng: random.Random) -> None:
    state["sls_Mstar"] = _different(
        rng,
        state.get("sls_Mstar"),
        (0.0, 25.0, 100.0, 250.0, 500.0, 850.0),
    )
    state["defl_limit_ratio"] = _different(
        rng,
        state.get("defl_limit_ratio"),
        (200.0, 250.0, 300.0, 400.0),
    )


def _locks(state: dict[str, Any], rng: random.Random) -> None:
    key = rng.choice(("optimisation_lock_width", "optimisation_lock_depth", "lock_bottom", "lock_shear"))
    state[key] = not bool(state.get(key, False))


def _ui_state(state: dict[str, Any], rng: random.Random) -> None:
    state["expanded_panels"] = [rng.choice(("geometry", "actions", "design_brain"))]
    state["scroll_state"] = rng.randrange(0, 5000)
    state["loading_flags"] = {"design_brain": bool(rng.randrange(2))}


def _navigation(state: dict[str, Any], rng: random.Random) -> None:
    state["selected_page"] = rng.choice(
        ("Beam Inputs", "Load Analysis", "Bending", "Shear", "Deflection")
    )
    state["active_tabs"] = {"inputs": rng.choice(("Geometry", "Actions", "Design Brain"))}


OPERATIONS: dict[str, Callable[[dict[str, Any], random.Random], None]] = {
    "geometry": _geometry,
    "materials": _materials,
    "longitudinal_reinforcement": _longitudinal,
    "shear_reinforcement": _shear,
    "manual_actions": _manual_actions,
    "load_analysis_actions": _load_actions,
    "serviceability": _serviceability,
    "locks": _locks,
    "ui_state": _ui_state,
    "navigation": _navigation,
}


def _assert_finite(value: Any, path: str = "result") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        assert math.isfinite(float(value)), f"non-finite {path}: {value!r}"
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_finite(item, f"{path}.{key}")
        return
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _assert_finite(item, f"{path}[{index}]")


def verify_stateful_runtime_fuzz() -> Counter[str]:
    rng = random.Random(SEED)
    counts: Counter[str] = Counter()
    total_operations = 0

    for sequence in range(SEQUENCES):
        state = build_state()
        state["L"] = 6000.0
        state["input_revision"] = 0
        revision = 0
        previous_snapshot = build_engineering_input_snapshot_from_resolved_state(state)

        operation_order = list(OPERATION_TYPES) * 2
        rng.shuffle(operation_order)
        for operation_name in operation_order:
            before = previous_snapshot
            OPERATIONS[operation_name](state, rng)
            ui_only = operation_name in {"ui_state", "navigation"}
            if not ui_only:
                revision += 1
                state["input_revision"] = revision
            snapshot = build_engineering_input_snapshot_from_resolved_state(state)
            if ui_only:
                assert snapshot.engineering_hash == before.engineering_hash

            result = calculate_v2_authoritative_result(
                engineering_snapshot=snapshot,
                resolved_inputs=state,
                input_revision=revision,
            )
            assert result.engineering_hash == snapshot.engineering_hash
            assert result.current_calculations["v2_source_revision"] == revision
            assert result.current_calculations["v2_source_hash"]
            assert result.publication_authority_hash == stable_authority_hash(
                result.publication_authority_payload()
            )
            _assert_finite(result.current_calculations["actions_used"], "actions")
            _assert_finite(result.current_calculations["families"], "families")

            previous_snapshot = snapshot
            counts[operation_name] += 1
            total_operations += 1

        assert revision == 16, f"sequence {sequence} revision drift: {revision}"

    assert total_operations == 1000
    assert counts == Counter({name: 100 for name in OPERATION_TYPES})
    return counts


def main() -> None:
    counts = verify_stateful_runtime_fuzz()
    print(
        "stateful Runtime fuzz contract: PASS "
        f"({sum(counts.values())} operations, {SEQUENCES} sequences, seed={SEED})"
    )


if __name__ == "__main__":
    main()
