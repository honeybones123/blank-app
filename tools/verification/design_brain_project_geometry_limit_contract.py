"""Focused contract for the canonical 5,000 mm Design Brain geometry limit."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "design_brain_project_geometry_limit_contract.json"
)


def _flat_geometry(specs: list[dict]) -> tuple[list[float], list[float]]:
    depths: list[float] = []
    widths: list[float] = []
    for spec in specs:
        updates = dict(spec.get("updates") or {})
        if updates.get("D") is not None:
            depths.append(float(updates["D"]))
        width = updates.get("b")
        if width is None:
            width = updates.get("bw")
        if width is not None:
            widths.append(float(width))
    return depths, widths


def main() -> int:
    from design_brain.families.registry import family_strategy_for
    from design_brain.families.serviceability_governs.runtime import (
        _candidate_updates_for_lane,
    )
    from design_brain.families.serviceability_governs import (
        evaluate_serviceability_governs,
    )
    from design_brain.geometry_limits import (
        PROJECT_MAX_BEAM_DEPTH_MM,
        PROJECT_MAX_BEAM_WIDTH_MM,
        project_depth_values,
        project_width_values,
    )

    base = {
        "b": 300.0,
        "D": 500.0,
        "bot1_count": 3,
        "db_bot_1": 16,
        "bot2_count": 0,
        "db_bot_2": 16,
        "top1_count": 2,
        "db_top_1": 12,
        "cover_side": 40.0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
    }
    bending = family_strategy_for(
        "BENDING_FAIL_GOVERNS"
    ).contracted_repair_ladder_specs(base, geometry_locked=False)
    shear = family_strategy_for(
        "SHEAR_FAIL_GOVERNS"
    ).contracted_repair_ladder_specs(base, geometry_locked=False)
    bending_specs = [
        dict(row) for row in list(bending.get("specs") or ()) if isinstance(row, dict)
    ]
    shear_specs = [
        dict(row) for row in list(shear.get("specs") or ()) if isinstance(row, dict)
    ]
    bending_depths, bending_widths = _flat_geometry(bending_specs)
    shear_depths, shear_widths = _flat_geometry(shear_specs)
    combined_strategy = family_strategy_for("COMBINED_BENDING_SHEAR_FAIL")
    combined = combined_strategy.build_target_band_refinement_candidates(
        base,
        bending_fail_candidates=(
            {
                "candidate_id": "bending_seed",
                "updates": {
                    "bot_row_1_bars": 4,
                    "bot_row_1_dia": 20,
                },
            },
        ),
        shear_fail_candidates=(
            {
                "candidate_id": "shear_seed",
                "updates": {
                    "lig_d": 12,
                    "lig_legs": 4,
                    "s_lig": 100.0,
                },
            },
        ),
    )
    combined_updates = [
        dict(row.get("updates") or {}) for row in combined if isinstance(row, dict)
    ]
    combined_depths = [
        float(row.get("D") or 0.0) for row in combined_updates
    ]
    combined_widths = [
        float(row.get("b") or row.get("bw") or 0.0) for row in combined_updates
    ]

    serviceability_base = {
        "geometry": {"beam_depth_mm": 500.0, "beam_width_mm": 300.0},
        "reinforcement": {"bottom_bar_count": 3},
        "constraints": {},
    }
    serviceability_depth = _candidate_updates_for_lane(
        "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
        serviceability_base,
        max_geometry_steps=None,
    )
    serviceability_width = _candidate_updates_for_lane(
        "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
        serviceability_base,
        max_geometry_steps=None,
    )
    serviceability_combined = _candidate_updates_for_lane(
        "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH",
        serviceability_base,
        max_geometry_steps=None,
    )
    serviceability_depth_values = [
        float(dict(row["updates"].get("geometry") or {}).get("beam_depth_mm") or 0.0)
        for row in serviceability_depth
    ]
    serviceability_width_values = [
        float(dict(row["updates"].get("geometry") or {}).get("beam_width_mm") or 0.0)
        for row in serviceability_width
    ]
    combined_geometry = [
        dict(row["updates"].get("geometry") or {})
        for row in serviceability_combined
    ]
    serviceability_exhausted = evaluate_serviceability_governs(
        {"base_state": serviceability_base}
    )
    serviceability_exhausted_proof = dict(
        dict(serviceability_exhausted.evidence.get("runtime_result") or {}).get(
            "exhausted_proof"
        )
        or {}
    )
    shear_no_valid_proof = dict(shear.get("no_valid_repair_proof") or {})

    checks = {
        "canonical_depth_is_5000_mm": PROJECT_MAX_BEAM_DEPTH_MM == 5000.0,
        "canonical_width_is_5000_mm": PROJECT_MAX_BEAM_WIDTH_MM == 5000.0,
        "shared_depth_progression_reaches_exact_limit": (
            project_depth_values(500.0)[-1] == 5000.0
        ),
        "shared_width_progression_reaches_exact_limit": (
            project_width_values(300.0)[-1] == 5000.0
        ),
        "bending_reaches_both_limits": (
            max(bending_depths, default=0.0) == 5000.0
            and max(bending_widths, default=0.0) == 5000.0
        ),
        "bending_never_exceeds_limits": (
            max(bending_depths, default=0.0) <= 5000.0
            and max(bending_widths, default=0.0) <= 5000.0
        ),
        "shear_reaches_both_limits": (
            max(shear_depths, default=0.0) == 5000.0
            and max(shear_widths, default=0.0) == 5000.0
        ),
        "shear_never_exceeds_limits": (
            max(shear_depths, default=0.0) <= 5000.0
            and max(shear_widths, default=0.0) <= 5000.0
        ),
        "combined_reaches_both_limits": (
            max(combined_depths, default=0.0) == 5000.0
            and max(combined_widths, default=0.0) == 5000.0
        ),
        "combined_never_exceeds_limits": (
            max(combined_depths, default=0.0) <= 5000.0
            and max(combined_widths, default=0.0) <= 5000.0
        ),
        "serviceability_depth_reaches_limit": (
            max(serviceability_depth_values, default=0.0) == 5000.0
        ),
        "serviceability_width_reaches_limit": (
            max(serviceability_width_values, default=0.0) == 5000.0
        ),
        "serviceability_combined_reaches_both_limits": bool(
            combined_geometry
            and float(combined_geometry[-1].get("beam_depth_mm") or 0.0) == 5000.0
            and float(combined_geometry[-1].get("beam_width_mm") or 0.0) == 5000.0
        ),
        "family_results_publish_same_limit": (
            bending.get("project_geometry_limit_mm")
            == {"depth": 5000.0, "width": 5000.0}
            and shear.get("project_geometry_limit_mm")
            == {"depth": 5000.0, "width": 5000.0}
        ),
        "shear_blocker_requires_canonical_exhaustion": (
            shear_no_valid_proof.get("allowed") is True
            and shear_no_valid_proof.get("canonical_geometry_exhausted") is True
            and "5000 mm" in str(shear.get("stop_reason_if_no_candidate") or "")
        ),
        "serviceability_blocker_requires_canonical_exhaustion": (
            serviceability_exhausted_proof.get("allowed") is True
            and serviceability_exhausted_proof.get("all_ladder_branches_attempted")
            is True
            and any(
                "5000 mm" in str(reason)
                for reason in serviceability_exhausted_proof.get(
                    "specific_blockers"
                )
                or ()
            )
        ),
    }
    passed = all(checks.values())
    payload = {
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "counts": {
            "bending_specs": len(bending_specs),
            "shear_specs": len(shear_specs),
            "combined_specs": len(combined_updates),
            "serviceability_depth_specs": len(serviceability_depth),
            "serviceability_width_specs": len(serviceability_width),
            "serviceability_combined_specs": len(serviceability_combined),
        },
        "project_geometry_limit_mm": {"depth": 5000.0, "width": 5000.0},
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if not passed:
        print(json.dumps(payload, indent=2))
        return 1
    print("PASS: Design Brain geometry ladders share the absolute 5000 x 5000 mm limit")
    print(f"Artifact: {ARTIFACT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
