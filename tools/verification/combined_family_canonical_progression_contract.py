"""Lock canonical reinforcement parity and unlocked combined progression."""

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
    / "combined_family_canonical_progression_contract.json"
)


def main() -> int:
    from design_brain.families.combined_bending_shear_fail import (
        CombinedBendingShearFailFamily,
    )
    from inputs_application.candidate_metrics import candidate_bottom_updates

    base = {
        "b": 350.0,
        "D": 400.0,
        "cover_side": 40.0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 300.0,
        "bot_row_count": 1,
        "bot_row_1_bars": 4,
        "bot_row_1_dia": 16,
        "bot_row_2_bars": 0,
        "bot_row_2_dia": 16,
        "bot1_count": 4,
        "db_bot_1": 16,
        "bot2_count": 0,
        "db_bot_2": 0,
        "top_row_count": 1,
        "top_row_1_bars": 2,
        "top_row_1_dia": 10,
        "top1_count": 2,
        "db_top_1": 10,
    }
    bending_sources = (
        {
            "source_family_id": "BENDING_FAIL_GOVERNS",
            "candidate_id": "nearest_reinforcement",
            "updates": {
                "b": 500.0,
                "bot_row_1_bars": 4,
                "bot_row_1_dia": 20,
            },
        },
        {
            "source_family_id": "BENDING_FAIL_GOVERNS",
            "candidate_id": "second_row_reinforcement",
            "updates": {
                "b": 400.0,
                "bot_row_count": 2,
                "bot_row_1_bars": 3,
                "bot_row_1_dia": 28,
                "bot_row_2_bars": 2,
                "bot_row_2_dia": 28,
            },
        },
    )
    shear_sources = (
        {
            "source_family_id": "SHEAR_FAIL_GOVERNS",
            "candidate_id": "nearest_spacing",
            "updates": {"s_lig": 300.0},
        },
        {
            "source_family_id": "SHEAR_FAIL_GOVERNS",
            "candidate_id": "strongest_links",
            "updates": {
                "s_lig": 100.0,
                "lig_d": 16,
                "lig_legs": 6,
            },
        },
    )

    family = CombinedBendingShearFailFamily()
    progression = family.build_target_band_refinement_candidates(
        base,
        bending_fail_candidates=bending_sources,
        shear_fail_candidates=shear_sources,
        limit=12,
    )
    updates = [
        dict(row.get("updates") or {})
        for row in progression
        if isinstance(row, dict)
    ]
    depths = [float(row.get("D") or 0.0) for row in updates]
    first = dict(updates[0] if updates else {})
    source_pair_count = (
        len(shear_sources) + max(0, len(bending_sources) - 1)
    )
    expected_depths = [
        425.0 + 25.0 * step
        for step in range(12)
        for _ in range(source_pair_count)
    ]
    first_depth_updates = [
        row for row in updates if float(row.get("D") or 0.0) == 425.0
    ]
    restart_orders = {
        str((row.get("evidence") or {}).get("reinforcement_restart_order") or "")
        for row in progression
        if isinstance(row, dict)
    }
    candidate_state = {**base, **first}
    bottom = dict(candidate_bottom_updates(candidate_state) or {})

    ladder = family.contracted_repair_ladder_specs(
        base,
        bending_fail_candidates=bending_sources,
        shear_fail_candidates=shear_sources,
        approved_combined_merge_candidates=progression,
    )
    ladder_specs = [
        dict(row)
        for row in list(ladder.get("specs") or [])
        if isinstance(row, dict)
    ]
    progressive_specs = [
        row
        for row in ladder_specs
        if str(row.get("candidate_id") or "").startswith(
            "combined_incremental_geometry_"
        )
        or str(row.get("merge_rule_id") or "")
        == "APPROVED_COMBINED_MERGE_RULE"
    ]
    candidate_source_proof = dict(
        ladder.get("candidate_source_proof") or {}
    )
    target_band_refinement_proof = dict(
        ladder.get("target_band_refinement_proof") or {}
    )
    progression_ids = [
        str(row.get("candidate_id") or "")
        for row in progression
        if isinstance(row, dict)
    ]
    progressive_spec_ids = [
        str(row.get("candidate_id") or "")
        for row in progressive_specs
    ]

    guidance_source = (
        ROOT
        / "inputs_page_modules"
        / "design_guide"
        / "family_ladder_guidance.py"
    ).read_text(encoding="utf-8")
    checks = {
        "progression_restarts_source_pairs_at_each_requested_depth": (
            len(updates) == 12 * source_pair_count
        ),
        "depth_advances_by_25_mm_after_each_source_restart": (
            depths == expected_depths
        ),
        "second_row_repair_is_carried": (
            int(first.get("bot_row_1_bars") or 0) == 3
            and int(first.get("bot_row_2_bars") or 0) == 2
            and int(first.get("bot_row_1_dia") or 0) == 28
            and int(first.get("bot_row_2_dia") or 0) == 28
        ),
        "strongest_shear_repair_is_available_at_first_depth": any(
            int(row.get("lig_d") or 0) == 16
            and int(row.get("lig_legs") or 0) == 6
            and float(row.get("s_lig") or 0.0) == 100.0
            for row in first_depth_updates
        ),
        "each_shear_stage_restarts_bending_choices": (
            restart_orders
            == {"shear_progression_with_nearest_stage_bending_restart"}
        ),
        "canonical_rows_override_stale_legacy_aliases": bottom
        == {
            "db_bot_1": 28,
            "db_bot_2": 28,
            "bot1_count": 3,
            "bot2_count": 2,
        },
        "runtime_contains_progressive_candidates": (
            len(progressive_specs) == len(progression)
        ),
        "progressive_candidates_preserve_family_order": (
            progressive_spec_ids == progression_ids
        ),
        "progression_skips_duplicate_placeholder_evaluation": (
            candidate_source_proof.get(
                "duplicate_placeholder_evaluation_skipped"
            )
            is True
            and int(
                candidate_source_proof.get(
                    "deferred_approved_candidate_count"
                )
                or 0
            )
            == len(progression)
            and int(
                target_band_refinement_proof.get(
                    "deferred_to_application_evaluator_count"
                )
                or 0
            )
            == len(progression)
            and target_band_refinement_proof.get(
                "application_evaluator_owns_exact_stop"
            )
            is True
        ),
        "application_requests_family_owned_refinement": (
            "build_target_band_refinement_candidates(" in guidance_source
            and "bending_fail_candidates=bending_sources" in guidance_source
            and "shear_fail_candidates=shear_sources" in guidance_source
        ),
        "combined_contract_order_is_not_stage_sampled": (
            'if dispatch_family_id == "COMBINED_BENDING_SHEAR_FAIL"'
            in guidance_source
            and "contract_specs[:max_evals]" in guidance_source
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "combined_family_canonical_progression_contract.v1",
        "status": "PASS" if not failures else "FAIL",
        "root_cause_category": "candidate_search_failure",
        "checks": checks,
        "failures": failures,
        "depths": depths,
        "first_updates": first,
        "candidate_bottom_projection": bottom,
        "ladder_spec_count": len(ladder_specs),
        "progressive_spec_count": len(progressive_specs),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: combined family keeps canonical reinforcement and incremental "
        "geometry in contract order"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
