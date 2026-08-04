"""Prove permanent typed ownership for auto-design scoring policy."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import functools
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _candidate(
    *,
    util: float,
    depth: float,
    bars: int,
    rows: int,
    compliant: bool = True,
) -> dict:
    return {
        "state": {
            "D": depth,
            "b": 300.0,
            "bot1_count": bars,
            "db_bot_1": 20,
            "bot2_count": 0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 200.0,
        },
        "overview": {
            "worst_util": util,
            "utils": {"bending": util, "shear": min(util, 0.75)},
            "statuses": {
                "bending": "PASS" if compliant else "FAIL",
                "shear": "PASS",
                "crack": "PASS",
                "deflection": "PASS",
            },
            "packs": {
                "bending": {
                    "summary_phiMu_kNm": 300.0,
                    "summary_Mu_star_kNm": 300.0 * util,
                }
            },
        },
        "is_compliant": compliant,
        "worst_util": util,
        "fail_count": 0 if compliant else 1,
        "depth": depth,
        "width": 300.0,
        "Ast_bot": float(bars) * 314.159,
        "Ast_top": 628.318,
        "row_count": rows,
        "bar_count": bars,
        "reo_complexity": float(bars + rows * 2),
        "reo_congestion_index": 0.2,
        "shear_density": 1.0,
        "bending_components": {"ductility_util": 0.70},
    }


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules.guidance_compute import (
            _application_log_efficiency_growth_rejection,
            _application_candidate_is_good_enough,
            _application_candidate_materially_better_for_mode,
            _application_ensure_candidate_score,
            _application_score_auto_design_candidate,
            build_guidance_compute_runtime,
        )
        import inputs_page_modules.guidance_compute as guidance_compute
        from inputs_page_modules.design_guide.auto_design_scoring import (
            candidate_materially_worsens as candidate_materially_worsens_owned,
        )

    guidance_runtime = build_guidance_compute_runtime(bridge)
    runtime = guidance_runtime.auto_design_solver
    selector = (
        guidance_runtime.one_click_band_candidate
        .select_best_auto_design_candidate
    )
    scoring_slots = (
        (
            runtime._candidate_materially_better_for_mode,
            _application_candidate_materially_better_for_mode,
        ),
        (
            runtime._ensure_candidate_score,
            _application_ensure_candidate_score,
        ),
        (
            runtime._score_auto_design_candidate,
            _application_score_auto_design_candidate,
        ),
        (
            runtime.candidate_materially_worsens,
            candidate_materially_worsens_owned,
        ),
        (
            runtime.candidate_is_good_enough,
            _application_candidate_is_good_enough,
        ),
    )
    for actual, owner in scoring_slots:
        assert isinstance(actual, functools.partial)
        assert actual.func is owner
        assert actual.func.__module__ != "inputs_page_app_contract_bridge"

    modes = tuple(
        bridge._design_mode_config(goal)
        for goal in ("balanced", "shallow", "low_reo")
    )
    seed = _candidate(
        util=1.08,
        depth=600.0,
        bars=6,
        rows=2,
        compliant=False,
    )
    candidates = (
        _candidate(
            util=0.88,
            depth=600.0,
            bars=6,
            rows=2,
        ),
        _candidate(
            util=0.92,
            depth=550.0,
            bars=7,
            rows=2,
        ),
        _candidate(
            util=0.84,
            depth=600.0,
            bars=4,
            rows=1,
        ),
        _candidate(
            util=1.02,
            depth=575.0,
            bars=5,
            rows=2,
            compliant=False,
        ),
    )
    checks = 0
    for mode in modes:
        legacy_seed = deepcopy(seed)
        owned_seed = deepcopy(seed)
        bridge._ensure_candidate_score(legacy_seed, mode, legacy_seed)
        runtime._ensure_candidate_score(owned_seed, mode, owned_seed)
        assert owned_seed == legacy_seed
        checks += 1
        for raw_candidate in candidates:
            legacy_candidate = deepcopy(raw_candidate)
            owned_candidate = deepcopy(raw_candidate)
            legacy_score = bridge._score_auto_design_candidate(
                legacy_candidate,
                mode,
                legacy_seed,
            )
            owned_score = runtime._score_auto_design_candidate(
                owned_candidate,
                mode,
                owned_seed,
            )
            assert owned_score == legacy_score
            assert owned_candidate == legacy_candidate
            checks += 1

            legacy_scored = bridge._ensure_candidate_score(
                deepcopy(raw_candidate),
                mode,
                legacy_seed,
            )
            owned_scored = runtime._ensure_candidate_score(
                deepcopy(raw_candidate),
                mode,
                owned_seed,
            )
            assert owned_scored == legacy_scored
            checks += 1

            assert runtime._candidate_materially_better_for_mode(
                owned_scored,
                owned_seed,
                mode,
            ) == bridge._candidate_materially_better_for_mode(
                legacy_scored,
                legacy_seed,
                mode,
            )
            checks += 1
            assert runtime.candidate_is_good_enough(
                owned_scored,
                mode,
                owned_seed,
            ) == bridge.candidate_is_good_enough(
                legacy_scored,
                mode,
                legacy_seed,
            )
            checks += 1
            assert runtime.candidate_materially_worsens(
                owned_scored,
                owned_seed,
                mode,
                phase="runtime_owner_verifier",
            ) == bridge.candidate_materially_worsens(
                legacy_scored,
                legacy_seed,
                mode,
                phase="runtime_owner_verifier",
            )
            checks += 1

    legacy_trace: list[dict] = []
    owned_trace: list[dict] = []
    bridge._ACTIVE_GUIDANCE_RANK_TRACE = legacy_trace
    guidance_compute._ACTIVE_GUIDANCE_RANK_TRACE = owned_trace
    try:
        for candidate in (None, candidates[0], candidates[2]):
            kwargs = {
                "candidate_family": "bending",
                "seed_candidate": deepcopy(seed),
                "candidate": deepcopy(candidate),
                "extra": {"verifier": True},
            }
            bridge._log_efficiency_growth_rejection(**deepcopy(kwargs))
            _application_log_efficiency_growth_rejection(
                **deepcopy(kwargs)
            )
            checks += 1
    finally:
        bridge._ACTIVE_GUIDANCE_RANK_TRACE = None
        guidance_compute._ACTIVE_GUIDANCE_RANK_TRACE = None
    assert owned_trace == legacy_trace

    for mode in modes:
        legacy_pool = deepcopy(list(candidates))
        owned_pool = deepcopy(list(candidates))
        legacy_seed = deepcopy(seed)
        owned_seed = deepcopy(seed)
        legacy_winner = bridge._select_best_auto_design_candidate(
            legacy_pool,
            mode,
            legacy_seed,
        )
        owned_winner = selector(
            owned_pool,
            mode,
            owned_seed,
        )
        assert owned_winner == legacy_winner
        assert owned_pool == legacy_pool
        checks += 1

    print(
        "PASS: auto-design scoring, selector, and trace callbacks have "
        f"permanent typed owners with exact {checks}/{checks} parity"
    )


if __name__ == "__main__":
    main()
