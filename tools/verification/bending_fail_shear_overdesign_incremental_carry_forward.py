from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (
    resolve_longitudinal_bar_spacing_rule,
)
from design_brain.families.registry import family_strategy_for
from inputs_page_modules.design_guide.family_ladder_guidance import (
    _continuous_unlocked_bending_geometry_specs,
    _with_progressive_bending_depth_specs,
)


def main() -> int:
    state = {
        "b": 350.0,
        "bw": 300.0,
        "D": 400.0,
        "d": 342.0,
        "cover_side": 40.0,
        "lig_d": 10,
        "bot1_count": 4,
        "db_bot_1": 16,
        "bot2_count": 0,
        "db_bot_2": 16,
        "bot_row_count": 1,
        "bot_row_1_bars": 4,
        "bot_row_1_dia": 16,
        "bot_row_2_bars": 0,
        "bot_row_2_dia": 16,
        "top1_count": 2,
        "db_top_1": 10,
        "top_row_1_bars": 2,
        "top_row_1_dia": 10,
    }
    source = family_strategy_for(
        "BENDING_FAIL_GOVERNS"
    ).contracted_repair_ladder_specs(
        state,
        width_key="b",
        geometry_locked=False,
    )
    source_specs = [
        dict(row)
        for row in list(source.get("specs") or [])
        if isinstance(row, dict)
    ]
    retried_multi_layer = [
        row
        for row in source_specs
        if row.get("reinforcement_retry_after_width") is True
        and int(dict(row.get("updates") or {}).get("bot_row_2_bars") or 0)
        > 0
    ]
    if not retried_multi_layer:
        raise AssertionError(
            "width increase did not retry the blocked multi-layer lane"
        )

    progression = _continuous_unlocked_bending_geometry_specs(
        _with_progressive_bending_depth_specs(
            source_specs,
            base_depth=400.0,
        ),
        base_depth=400.0,
        base_width=350.0,
        width_key="b",
        base_state=state,
    )
    depth_rows = [
        dict(row)
        for row in progression
        if float(dict(row.get("updates") or {}).get("D") or 0.0) > 400.0
    ]
    if not depth_rows:
        raise AssertionError("unlocked bending depth progression is empty")

    previous_depth = 400.0
    previous_row_1_count = 3
    previous_row_2_count = 2
    for row in depth_rows:
        updates = dict(row.get("updates") or {})
        depth = float(updates.get("D") or 0.0)
        if abs(depth - previous_depth - 25.0) > 1e-9:
            raise AssertionError(
                f"depth progression is not continuous: {previous_depth} -> {depth}"
            )
        previous_depth = depth
        row_1_count = int(updates.get("bot_row_1_bars") or 0)
        row_2_count = int(updates.get("bot_row_2_bars") or 0)
        if row_1_count < previous_row_1_count:
            raise AssertionError("depth progression lost first-row reinforcement")
        if row_2_count < previous_row_2_count:
            raise AssertionError("depth progression lost second-row reinforcement")
        previous_row_1_count = row_1_count
        previous_row_2_count = row_2_count
        if int(updates.get("bot_row_1_dia") or 0) != 28:
            raise AssertionError("depth progression lost reinforcement diameter")
        spacing = resolve_longitudinal_bar_spacing_rule(state, updates)
        if not bool(spacing.get("valid")):
            raise AssertionError(
                f"depth progression violated longitudinal spacing: {spacing}"
            )

    target = next(
        (
            dict(row.get("updates") or {})
            for row in depth_rows
            if abs(
                float(dict(row.get("updates") or {}).get("D") or 0.0)
                - 575.0
            )
            <= 1e-9
        ),
        None,
    )
    if target is None:
        raise AssertionError("expected 575 mm incremental candidate is absent")
    if float(target.get("b") or 0.0) != 400.0:
        raise AssertionError(
            "575 mm candidate did not retain the nearest legal width"
        )
    if int(target.get("bot_row_1_bars") or 0) != 3:
        raise AssertionError("575 mm candidate changed first-row count")
    if int(target.get("bot_row_2_bars") or 0) != 2:
        raise AssertionError("575 mm candidate changed second-row count")

    print(
        "PASS: width retry and unlocked bending depth progression preserve "
        "the legal 3+2 N28 detailing state"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
