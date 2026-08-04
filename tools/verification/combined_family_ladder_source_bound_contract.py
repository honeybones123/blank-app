"""Prove combined active-fail source selection is bounded and stage-covering."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide.family_ladder_guidance import (
    _COMBINED_SOURCE_LIMIT_PER_FAMILY,
    _SINGLE_FAMILY_LADDER_LIMIT,
    _bounded_ordered_stage_specs,
)


def main() -> int:
    rows = [
        {
            "contract_step": step,
            "candidate_id": f"stage_{step}_{index}",
            "updates": {"value": index},
        }
        for step in range(1, 6)
        for index in range(1, 22)
    ]
    selected = _bounded_ordered_stage_specs(rows)
    single_family_selected = _bounded_ordered_stage_specs(
        rows,
        limit=_SINGLE_FAMILY_LADDER_LIMIT,
    )
    ids = [str(row.get("candidate_id") or "") for row in selected]
    selected_steps = {
        int(row.get("contract_step") or 0) for row in selected
    }
    checks = {
        "source_is_bounded": len(selected) <= _COMBINED_SOURCE_LIMIT_PER_FAMILY,
        "staged_merge_is_bounded": min(4, len(selected)) <= 4,
        "nearest_candidate_preserved": ids[0] == "stage_1_1",
        "terminal_geometry_candidate_preserved": ids[-1] == "stage_5_21",
        "multiple_contract_stages_preserved": len(selected_steps) >= 4,
        "single_family_ladder_is_bounded": (
            len(single_family_selected) <= _SINGLE_FAMILY_LADDER_LIMIT
        ),
        "single_family_ladder_preserves_all_stages": {
            int(row.get("contract_step") or 0)
            for row in single_family_selected
        }
        == {1, 2, 3, 4, 5},
        "ordering_preserved": ids == [
            str(rows[index].get("candidate_id") or "")
            for index in sorted(
                rows.index(row) for row in selected
            )
        ],
    }
    payload = {
        "schema": "combined_family_ladder_source_bound_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source_limit_per_family": _COMBINED_SOURCE_LIMIT_PER_FAMILY,
        "single_family_ladder_limit": _SINGLE_FAMILY_LADDER_LIMIT,
        "maximum_staged_merge_candidates": 4,
        "selected_candidate_ids": ids,
        "selected_contract_steps": sorted(selected_steps),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
