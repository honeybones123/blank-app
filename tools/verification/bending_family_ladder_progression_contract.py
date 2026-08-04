"""Focused proof for the reinforcement-first exhaustive bending ladder."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.families.bending_fail import BendingFailFamily  # noqa: E402
from design_brain.families.bending_fail_governs.runtime import (  # noqa: E402
    bending_fail_governs_contract_lane_order,
)
from inputs_page_modules.design_guide.family_ladder_guidance import (  # noqa: E402
    _active_strengthening_ladder_specs,
)


EXPECTED_ORDER = (
    "GEOMETRY_SANITY",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "MULTI_LAYER_REO",
    "DEPTH_INCREASE",
    "WIDTH_INCREASE",
    "EXACT_STOP",
    "NO_VALID_STRATEGY",
)
LIVE_BASE_MAX_EVALS = 384


def _fixture_state() -> dict:
    return {
        "b": 300.0,
        "D": 350.0,
        "bot1_count": 2,
        "db_bot_1": 10,
        "bot_row_1_bars": 2,
        "bot_row_1_dia": 10,
        "cover_side": 40.0,
        "lig_d": 0,
    }


def main() -> int:
    family = BendingFailFamily()
    unlocked = family.contracted_repair_ladder_specs(
        _fixture_state(),
        geometry_locked=False,
    )
    locked = family.contracted_repair_ladder_specs(
        _fixture_state(),
        geometry_locked=True,
    )
    unlocked_specs = [
        dict(spec)
        for spec in list(unlocked.get("specs") or [])
        if isinstance(spec, dict)
    ]
    locked_specs = [
        dict(spec)
        for spec in list(locked.get("specs") or [])
        if isinstance(spec, dict)
    ]
    effective_live_max_evals = max(
        LIVE_BASE_MAX_EVALS,
        len(unlocked_specs),
    )
    active_specs = _active_strengthening_ladder_specs(
        "BENDING_FAIL_GOVERNS",
        unlocked_specs,
        max_evals=effective_live_max_evals,
    )
    phases = [
        int(spec.get("bending_ladder_phase"))
        for spec in unlocked_specs
    ]
    first_by_phase = {
        phase: next(
            (
                index
                for index, value in enumerate(phases)
                if value == phase
            ),
            None,
        )
        for phase in range(7)
    }
    nearest_reinforcement_rejection = next(
        (
            dict(row)
            for row in list(
                unlocked.get("known_bad_candidates_skipped") or []
            )
            if str(row.get("stage_name") or "")
            == "contract_runtime_single_layer_bottom_reo"
        ),
        {},
    )
    checks = {
        "contract_order_is_reinforcement_first": (
            bending_fail_governs_contract_lane_order()
            == EXPECTED_ORDER
        ),
        "unlocked_ladder_is_nonempty": bool(unlocked_specs),
        "candidate_indexes_are_contiguous": [
            spec.get("ladder_index")
            for spec in unlocked_specs
        ]
        == list(range(1, len(unlocked_specs) + 1)),
        "phases_are_monotonic": phases == sorted(phases),
        "nearest_reinforcement_step_was_considered": bool(
            nearest_reinforcement_rejection
        ),
        "nearest_illegal_step_has_detailing_reason": (
            nearest_reinforcement_rejection.get("reason")
            == "clear_spacing_below_100_mm"
        ),
        "diameter_then_second_row_then_depth_then_width": (
            first_by_phase[1] is not None
            and first_by_phase[2] is not None
            and first_by_phase[3] is not None
            and first_by_phase[4] is not None
            and first_by_phase[1]
            < first_by_phase[2]
            < first_by_phase[3]
            < first_by_phase[4]
        ),
        "width_restarts_reinforcement": first_by_phase[5] is not None,
        "unlocked_ladder_expands_live_ceiling": (
            len(unlocked_specs) > 12
            and effective_live_max_evals >= len(unlocked_specs)
        ),
        "live_dispatch_consumes_every_unlocked_step": (
            len(active_specs) == len(unlocked_specs)
        ),
        "locked_geometry_has_no_geometry_candidates": all(
            int(spec.get("bending_ladder_phase")) < 3
            for spec in locked_specs
        ),
        "locked_geometry_retains_reinforcement_repairs": bool(
            locked_specs
        ),
        "all_candidates_are_family_owned": all(
            spec.get("candidate_family_id")
            == "BENDING_FAIL_GOVERNS"
            for spec in unlocked_specs + locked_specs
        ),
    }
    payload = {
        "schema": "bending_family_ladder_progression_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "contract_order": list(
            bending_fail_governs_contract_lane_order()
        ),
        "unlocked_candidate_count": len(unlocked_specs),
        "live_consumed_candidate_count": len(active_specs),
        "locked_candidate_count": len(locked_specs),
        "phase_first_indexes": first_by_phase,
        "live_base_max_evals": LIVE_BASE_MAX_EVALS,
        "effective_live_max_evals": effective_live_max_evals,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
