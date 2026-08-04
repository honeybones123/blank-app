"""Selected-family ladder guidance for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable

from design_brain.family_chooser import classify_family_from_raw_flags
from design_brain.family_ladder_dispatch import resolve_family_ladder_dispatch
from design_brain.candidate_evaluation import (
    minimum_longitudinal_row_count_for_spacing,
)
from design_brain.families.bending_fail_governs.geometry_ratio import (
    bending_depth_width_ratio_limit,
)
from design_brain.families.registry import family_strategy_for
from design_brain.geometry_limits import (
    PROJECT_MAX_BEAM_DEPTH_MM,
    PROJECT_MAX_BEAM_WIDTH_MM,
)
_COMBINED_SOURCE_LIMIT_PER_FAMILY = 8
_COMBINED_OVERDESIGN_TERMINAL_FOLD_LIMIT = 32
_SINGLE_FAMILY_LADDER_LIMIT = 12
_MANDATORY_MIXED_REPAIR_CHUNK_SIZE = 16


def _bounded_ordered_stage_specs(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    limit: int = _COMBINED_SOURCE_LIMIT_PER_FAMILY,
) -> tuple[dict[str, Any], ...]:
    """Keep ordered stage coverage without a source-family Cartesian explosion."""

    specs = [
        dict(row)
        for row in list(rows or [])
        if isinstance(row, dict) and dict(row.get("updates") or {})
    ]
    if len(specs) <= max(1, int(limit)):
        return tuple(specs)
    stage_positions: dict[str, list[int]] = {}
    for index, spec in enumerate(specs):
        stage = str(
            spec.get("contract_step")
            or spec.get("selected_strategy_lane")
            or spec.get("contract_runtime_lane_id")
            or spec.get("stage_name")
            or "UNCLASSIFIED"
        )
        stage_positions.setdefault(stage, []).append(index)
    bounded_limit = max(1, int(limit))
    if len(stage_positions) <= bounded_limit:
        stage_groups = list(stage_positions.values())
        selected_indexes = {positions[0] for positions in stage_groups}
        selected_indexes.add(len(specs) - 1)
        optional_indexes = [1]
        for positions in stage_groups:
            spacing_rows = [
                index
                for index in positions
                if specs[index].get("updates", {}).get("s_lig") is not None
            ]
            if not spacing_rows:
                continue
            tightest_spacing = min(
                float(specs[index]["updates"]["s_lig"])
                for index in spacing_rows
            )
            tight_rows = [
                index
                for index in spacing_rows
                if float(specs[index]["updates"]["s_lig"]) == tightest_spacing
            ]

            def _practical_tight_row_key(index: int) -> tuple:
                updates = dict(specs[index].get("updates") or {})
                contract_step_raw = (
                    specs[index].get("contract_step")
                    or specs[index].get("selected_strategy_lane")
                    or specs[index].get("contract_runtime_lane_id")
                    or ""
                )
                try:
                    contract_step = int(contract_step_raw or 0)
                except (TypeError, ValueError):
                    contract_step = 0
                has_diameter = updates.get("lig_d") is not None
                has_legs = updates.get("lig_legs") is not None
                leg_stage = bool(
                    contract_step == 5
                    or str(contract_step_raw).strip().upper()
                    == "LEG_COUNT_REDUCTION"
                )
                return (
                    float(updates.get("D") or 0.0),
                    float(updates.get("b") or updates.get("bw") or 0.0),
                    (
                        0
                        if (leg_stage and not has_diameter)
                        or (not leg_stage and has_diameter)
                        else 1
                    ),
                    float(updates.get("lig_d") or 0.0),
                    (
                        -float(updates.get("lig_legs") or 0.0)
                        if leg_stage
                        else float(updates.get("lig_legs") or 0.0)
                    ),
                    0 if has_legs else 1,
                    len(updates),
                    index,
                )

            practical_index = min(
                tight_rows,
                key=_practical_tight_row_key,
            )
            optional_indexes.append(practical_index)
        for index in optional_indexes:
            if len(selected_indexes) >= bounded_limit:
                break
            selected_indexes.add(index)
        return tuple(specs[index] for index in sorted(selected_indexes))
    selected_indexes = {0, 1, len(specs) - 1}
    for positions in stage_positions.values():
        selected_indexes.add(positions[0])
        selected_indexes.add(positions[-1])
    ordered_indexes = sorted(selected_indexes)
    if len(ordered_indexes) > bounded_limit:
        if bounded_limit == 1:
            ordered_indexes = [ordered_indexes[0]]
        else:
            last_position = len(ordered_indexes) - 1
            sampled_positions = {
                round(slot * last_position / (bounded_limit - 1))
                for slot in range(bounded_limit)
            }
            ordered_indexes = [
                ordered_indexes[position]
                for position in sorted(sampled_positions)
            ]
    return tuple(specs[index] for index in ordered_indexes)


def _run_incremental_shear_fail_bending_overdesign_ladder(
    mixed_strategy: Any,
    base: dict[str, Any],
    *,
    mandatory_sources: tuple[dict[str, Any], ...],
    evaluate_candidate: Callable[..., Any],
    chunk_size: int = _MANDATORY_MIXED_REPAIR_CHUNK_SIZE,
) -> dict[str, Any]:
    """Run every mandatory shear candidate in order until one is valid.

    Bending cleanup is opportunistic for this mixed family.  It must not cap,
    sample, or delay the mandatory shear-underdesign repair.  Chunking keeps
    runtime evidence bounded while preserving reachability of every legal
    reinforcement and geometry step.
    """

    sources = tuple(dict(row) for row in mandatory_sources if isinstance(row, dict))
    bounded_chunk_size = max(1, int(chunk_size))
    aggregate_trace: list[dict[str, Any]] = []
    aggregate_accepted: list[dict[str, Any]] = []
    aggregate_rejected: list[dict[str, Any]] = []
    attempted = 0
    result: dict[str, Any] = {}
    selected: dict[str, Any] = {}

    def _globalise_rows(
        rows: tuple[dict[str, Any], ...] | list[dict[str, Any]],
        *,
        offset: int,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for local_index, row in enumerate(rows or (), start=1):
            row_d = dict(row)
            row_d["candidate_index"] = offset + local_index
            out.append(row_d)
        return out

    for start in range(0, len(sources), bounded_chunk_size):
        chunk = sources[start : start + bounded_chunk_size]
        chunk_result = dict(
            mixed_strategy.contracted_mixed_ladder_result(
                base,
                shear_fail_candidates=chunk,
                bending_overdesign_candidates=(),
                evaluate_candidate=evaluate_candidate,
            )
            or {}
        )
        aggregate_trace.extend(
            _globalise_rows(
                list(chunk_result.get("mixed_merge_trace") or ()),
                offset=start,
            )
        )
        aggregate_accepted.extend(
            _globalise_rows(
                list(chunk_result.get("accepted_candidate_evidence") or ()),
                offset=start,
            )
        )
        aggregate_rejected.extend(
            _globalise_rows(
                list(chunk_result.get("rejected_candidate_evidence") or ()),
                offset=start,
            )
        )
        attempted += len(chunk)
        result = chunk_result
        selected = dict(chunk_result.get("selected_recommendation") or {})
        if selected:
            selected["candidate_index"] = start + int(
                selected.get("candidate_index") or 1
            )
            break

    exhausted = bool(sources) and attempted >= len(sources) and not selected
    result["selected_recommendation"] = dict(selected) if selected else None
    result["candidate_repairs"] = tuple(aggregate_accepted)
    result["mixed_merge_trace"] = tuple(aggregate_trace)
    result["accepted_candidate_evidence"] = tuple(aggregate_accepted)
    result["rejected_candidate_evidence"] = tuple(aggregate_rejected)

    ranking = dict(result.get("ranking_evidence") or {})
    ranking.update(
        {
            "accepted_count": len(aggregate_accepted),
            "rejected_count": len(aggregate_rejected),
            "selected_candidate_id": selected.get("candidate_id") if selected else None,
            "ordered_mandatory_search": True,
        }
    )
    result["ranking_evidence"] = ranking

    source_proof = dict(result.get("candidate_source_proof") or {})
    source_proof.update(
        {
            "merged_candidate_count": attempted,
            "mandatory_candidate_count": len(sources),
            "mandatory_candidates_attempted": attempted,
            "mandatory_search_exhausted": exhausted,
            "mandatory_search_stopped_on_valid_repair": bool(selected),
        }
    )
    result["candidate_source_proof"] = source_proof

    exhausted_proof = dict(result.get("exhausted_proof") or {})
    exhausted_proof["all_shear_repair_candidates_attempted"] = exhausted
    exhausted_proof["mandatory_candidates_attempted"] = attempted
    exhausted_proof["mandatory_candidate_count"] = len(sources)
    result["exhausted_proof"] = exhausted_proof
    result["ordered_mandatory_search"] = {
        "policy": "incremental_until_valid_repair_or_canonical_exhaustion",
        "candidate_count": len(sources),
        "attempted_count": attempted,
        "chunk_size": bounded_chunk_size,
        "stopped_on_valid_repair": bool(selected),
        "canonical_search_exhausted": exhausted,
    }
    return result


def _active_strengthening_ladder_specs(
    family_id: str,
    contract_specs: list[dict[str, Any]],
    *,
    max_evals: int,
) -> list[dict[str, Any]]:
    """Preserve complete incremental ladders for active strength failures."""

    if family_id in {
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
    }:
        return list(contract_specs[:max_evals])
    return list(
        _bounded_ordered_stage_specs(
            contract_specs,
            limit=_SINGLE_FAMILY_LADDER_LIMIT,
        )
    )


def _with_progressive_bending_depth_specs(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    base_depth: float,
) -> tuple[dict[str, Any], ...]:
    """Add bounded reinforcement-plus-depth steps after the second-row step."""

    specs = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    second_row = next(
        (
            row
            for row in specs
            if int(dict(row.get("updates") or {}).get("bot_row_2_bars") or 0) > 0
        ),
        None,
    )
    if second_row is None:
        return tuple(specs)
    second_row_updates = dict(second_row.get("updates") or {})
    progressive: list[dict[str, Any]] = []
    for depth_step in (25.0, 50.0, 75.0, 100.0):
        progressive.append(
            {
                **second_row,
                "updates": {
                    **second_row_updates,
                    "D": float(base_depth + depth_step),
                },
                "contract_step": "MULTI_LAYER_DEPTH_REFINEMENT",
                "contract_runtime_lane_id": "MULTI_LAYER_DEPTH_REFINEMENT",
                "selected_strategy_lane": "MULTI_LAYER_DEPTH_REFINEMENT",
                "stage_name": "multi_layer_depth_refinement",
                "strategy": (
                    "retain the second-row bending repair and increase depth "
                    f"by {depth_step:.0f} mm"
                ),
                "candidate_id": (
                    f"{second_row.get('candidate_id') or 'bending_fail_multi_layer'}"
                    f"_depth_{int(depth_step)}"
                ),
            }
        )
    insert_at = specs.index(second_row) + 1
    return tuple(specs[:insert_at] + progressive + specs[insert_at:])


def _continuous_unlocked_bending_geometry_specs(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    base_depth: float,
    base_width: float,
    width_key: str,
    base_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return one monotonic geometry candidate per depth increment.

    The family source may contain repeated width/depth scans.  For an unlocked
    failing beam the live runtime instead needs a single ordered path that
    advances depth by 25 mm and increases width only when the family-owned
    depth/width rule requires it.
    """

    source = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    non_depth = [
        row
        for row in source
        if "D" not in dict(row.get("updates") or {})
    ]
    reinforcement_rows = [
        row
        for row in source
        if any(
            key in dict(row.get("updates") or {})
            for key in (
                "bot1_count",
                "bot_row_1_bars",
                "db_bot_1",
                "bot_row_1_dia",
                "bot2_count",
                "bot_row_2_bars",
            )
        )
    ]
    # Carry a deterministic contract-approved practical reinforcement state
    # into geometry.  The family contract enumerates diameter progression; the
    # carry-forward policy prefers its N28 practical pivot, then the nearest
    # allowed diameter, smallest legal width, and original ladder order.
    carry_candidates = [
        row
        for row in reinforcement_rows
        if int(
            dict(row.get("updates") or {}).get("bot_row_2_bars")
            or dict(row.get("updates") or {}).get("bot2_count")
            or 0
        )
        > 0
        and "D" not in dict(row.get("updates") or {})
        and row.get("reinforcement_retry_after_width") is True
    ]

    def _carry_forward_rank(row: dict[str, Any]) -> tuple:
        updates = dict(row.get("updates") or {})
        diameter = int(
            updates.get("bot_row_1_dia")
            or updates.get("db_bot_1")
            or 0
        )
        width = float(updates.get(width_key) or base_width)
        return (
            abs(diameter - 28),
            width,
            int(row.get("ladder_index") or 10**9),
        )

    reinforcement_template = (
        min(carry_candidates, key=_carry_forward_rank)
        if carry_candidates
        else (reinforcement_rows[0] if reinforcement_rows else {})
    )
    template_updates = dict(
        reinforcement_template.get("updates") or {}
    )
    carried_updates = {
        key: value
        for key, value in template_updates.items()
        if key != "D"
    }
    carried_width = float(
        carried_updates.get(width_key) or base_width
    )
    base = dict(base_state or {})
    cover_side = float(base.get("cover_side") or 40.0)
    lig_d = float(base.get("lig_d") or 0.0)
    top_count = int(
        base.get("top_row_1_bars")
        or base.get("top1_count")
        or 2
    )
    top_dia = float(
        base.get("top_row_1_dia")
        or base.get("db_top_1")
        or 10.0
    )
    bottom_row_1_count = int(
        carried_updates.get("bot_row_1_bars")
        or carried_updates.get("bot1_count")
        or base.get("bot_row_1_bars")
        or base.get("bot1_count")
        or 2
    )
    bottom_row_1_dia = float(
        carried_updates.get("bot_row_1_dia")
        or carried_updates.get("db_bot_1")
        or base.get("bot_row_1_dia")
        or base.get("db_bot_1")
        or 10.0
    )
    bottom_row_2_count = int(
        carried_updates.get("bot_row_2_bars")
        or carried_updates.get("bot2_count")
        or 0
    )
    bottom_row_2_dia = float(
        carried_updates.get("bot_row_2_dia")
        or carried_updates.get("db_bot_2")
        or bottom_row_1_dia
    )
    source_depths: list[float] = []
    for row in source:
        updates = dict(row.get("updates") or {})
        if "D" not in updates:
            continue
        try:
            depth = float(updates["D"])
        except (TypeError, ValueError):
            continue
        source_depths.append(depth)

    ratio_limit = float(bending_depth_width_ratio_limit())
    final_source_depth = min(
        PROJECT_MAX_BEAM_DEPTH_MM,
        max(source_depths, default=float(base_depth)),
    )
    defensive_depth = PROJECT_MAX_BEAM_DEPTH_MM
    template = reinforcement_template or (source[-1] if source else {})
    progressive: list[dict[str, Any]] = []
    depth = float(base_depth) + 25.0
    while depth <= defensive_depth + 1e-9:
        required_width = max(
            float(base_width),
            float(carried_width),
            math.ceil((depth / ratio_limit) / 50.0) * 50.0,
        )
        if required_width > PROJECT_MAX_BEAM_WIDTH_MM + 1e-9:
            break
        required_top_count = minimum_longitudinal_row_count_for_spacing(
            width=required_width,
            bar_dia=top_dia,
            cover_side=cover_side,
            lig_d=lig_d,
            minimum_count=top_count,
        )
        required_bottom_row_1_count = (
            minimum_longitudinal_row_count_for_spacing(
                width=required_width,
                bar_dia=bottom_row_1_dia,
                cover_side=cover_side,
                lig_d=lig_d,
                minimum_count=bottom_row_1_count,
            )
        )
        required_bottom_row_2_count = (
            minimum_longitudinal_row_count_for_spacing(
                width=required_width,
                bar_dia=bottom_row_2_dia,
                cover_side=cover_side,
                lig_d=lig_d,
                minimum_count=bottom_row_2_count,
            )
            if bottom_row_2_count > 0
            else 0
        )
        progressive.append(
            {
                **template,
                "updates": {
                    **carried_updates,
                    "D": float(depth),
                    **(
                        {width_key: float(required_width)}
                        if required_width > float(base_width) + 1e-9
                        else {}
                    ),
                    **(
                        {
                            "top1_count": int(required_top_count),
                            "top_row_1_bars": int(required_top_count),
                        }
                        if required_top_count > top_count
                        else {}
                    ),
                    **(
                        {
                            "bot1_count": int(
                                required_bottom_row_1_count
                            ),
                            "bot_row_1_bars": int(
                                required_bottom_row_1_count
                            ),
                        }
                        if required_bottom_row_1_count
                        > bottom_row_1_count
                        else {}
                    ),
                    **(
                        {
                            "bot2_count": int(
                                required_bottom_row_2_count
                            ),
                            "bot_row_2_bars": int(
                                required_bottom_row_2_count
                            ),
                        }
                        if required_bottom_row_2_count
                        > bottom_row_2_count
                        else {}
                    ),
                },
                "contract_step": "UNLOCKED_INCREMENTAL_GEOMETRY_REPAIR",
                "contract_runtime_lane_id": "UNLOCKED_INCREMENTAL_GEOMETRY_REPAIR",
                "selected_strategy_lane": "UNLOCKED_INCREMENTAL_GEOMETRY_REPAIR",
                "stage_name": "unlocked_incremental_geometry_repair",
                "strategy": (
                    "retain the strongest legal reinforcement step and "
                    f"increase depth to {depth:.0f} mm"
                    + (
                        f" and width to {required_width:.0f} mm"
                        if required_width > float(base_width) + 1e-9
                        else ""
                    )
                ),
                "candidate_id": (
                    "bending_fail_unlocked_geometry_"
                    f"{int(round(required_width))}x{int(round(depth))}"
                ),
                "reinforcement_carry_forward_policy_id": (
                    "approved_nearest_N28_then_min_width_then_ladder_order.v1"
                ),
            }
        )
        depth += 25.0
    return tuple(non_depth) + tuple(progressive)


def _family_merge_source_rows(result: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    """Return safe family-owned candidates, including non-terminal merge inputs."""

    payload = dict(result or {})
    rows = [
        *list(payload.get("specs") or []),
        *list(payload.get("candidate_repairs") or []),
        *list(payload.get("ladder_trace") or []),
    ]
    selected = payload.get("selected_recommendation")
    if isinstance(selected, dict):
        rows.insert(0, selected)
    output: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("accepted") is False or row.get("rejection_reasons"):
            continue
        updates = dict(row.get("updates") or {})
        if not updates:
            continue
        key = tuple(sorted((str(name), repr(value)) for name, value in updates.items()))
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(row))
    return tuple(output)


def _combined_overdesign_stage_result(
    state: dict[str, Any],
    *,
    family_strategy: Any,
    evaluate_auto_design_candidate: Callable[..., Any],
) -> dict[str, Any]:
    """Evaluate one family-owned combined-cleanup stage."""

    bending_source_result = family_strategy_for(
        "BENDING_OVERDESIGN_GOVERNS"
    ).contracted_optimisation_ladder_specs(
        state,
        evaluate_candidate=build_bending_overdesign_live_evaluator(
            evaluate_auto_design_candidate
        ),
    )
    shear_source_result = family_strategy_for(
        "SHEAR_OVERDESIGN_GOVERNS"
    ).contracted_optimisation_ladder_specs(
        state,
        evaluate_candidate=build_shear_overdesign_live_evaluator(
            evaluate_auto_design_candidate
        ),
    )
    bending_sources = tuple(
        {
            **dict(row),
            "source_family_id": "BENDING_OVERDESIGN_GOVERNS",
            "candidate_id": str(
                row.get("candidate_id")
                or row.get("source_candidate_id")
                or f"bending_overdesign_{index}"
            ),
        }
        for index, row in enumerate(
            _bounded_ordered_stage_specs(
                _family_merge_source_rows(bending_source_result),
                limit=_COMBINED_SOURCE_LIMIT_PER_FAMILY,
            ),
            start=1,
        )
        if isinstance(row, dict) and dict(row.get("updates") or {})
    )
    shear_sources = tuple(
        {
            **dict(row),
            "source_family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "candidate_id": str(
                row.get("candidate_id")
                or row.get("source_candidate_id")
                or f"shear_overdesign_{index}"
            ),
        }
        for index, row in enumerate(
            _bounded_ordered_stage_specs(
                _family_merge_source_rows(shear_source_result),
                limit=_COMBINED_SOURCE_LIMIT_PER_FAMILY,
            ),
            start=1,
        )
        if isinstance(row, dict) and dict(row.get("updates") or {})
    )
    result = dict(
        family_strategy.contracted_optimisation_ladder_specs(
            state,
            bending_overdesign_candidates=bending_sources,
            shear_overdesign_candidates=shear_sources,
            evaluate_candidate=build_combined_overdesign_live_evaluator(
                evaluate_auto_design_candidate
            ),
        )
        or {}
    )
    result["combined_source_inventory"] = {
        "bending_total": len(
            list(_family_merge_source_rows(bending_source_result))
        ),
        "shear_total": len(
            list(_family_merge_source_rows(shear_source_result))
        ),
        "bending_selected": len(bending_sources),
        "shear_selected": len(shear_sources),
        "selection_limit_per_family": _COMBINED_SOURCE_LIMIT_PER_FAMILY,
        "selection_policy": "ordered_stage_coverage",
    }
    return result


def _run_incremental_combined_overdesign_ladder(
    base: dict[str, Any],
    *,
    family_strategy: Any,
    evaluate_auto_design_candidate: Callable[..., Any],
    material_proxy: Callable[[dict[str, Any]], float],
    max_fold_steps: int = _COMBINED_OVERDESIGN_TERMINAL_FOLD_LIMIT,
) -> dict[str, Any]:
    """Fold non-terminal combined cleanup steps into one terminal Apply.

    The combined-family contract marks partial optimisation candidates as
    diagnostic only.  Re-enter the two source-family ladders from each safe
    reduced state and compose their updates until the combined runtime proves
    target-band or exact-stop terminal status.  A repeated state or exhausted
    source ladder is returned without converting the last partial step into a
    publishable action.
    """

    terminal_statuses = {
        "TERMINAL_TARGET_BAND",
        "TERMINAL_EXACT_STOP",
        "TERMINAL_BLOCKED_WITH_PROOF",
    }
    working_state = dict(base)
    cumulative_updates: dict[str, Any] = {}
    seen_states: set[tuple[tuple[str, str], ...]] = set()
    fold_trace: list[dict[str, Any]] = []
    final_result: dict[str, Any] = {}
    last_progressing_selected: dict[str, Any] = {}

    def _evaluate_fold_state_candidate(
        state: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Evaluate the accumulated fold state without live-state rehydration."""

        try:
            return evaluate_auto_design_candidate(
                state,
                state_already_resolved=True,
                **kwargs,
            )
        except TypeError as exc:
            if "state_already_resolved" not in str(exc):
                raise
            return evaluate_auto_design_candidate(state, **kwargs)

    def _terminalise_exhausted_family_ladders(
        *,
        fold_index: int,
        selected_template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Represent an exhausted restarted ladder as one exact-stop result."""

        terminal_selected = dict(
            selected_template or last_progressing_selected or {}
        )
        current_state_exact_stop = not bool(cumulative_updates)
        exact_blocker_reason = (
            "family-owned bending and shear cleanup ladders were evaluated "
            "from the current state and produced no further material state "
            "change"
            if current_state_exact_stop
            else
            "family-owned bending and shear cleanup ladders were restarted "
            "from the reduced state and produced no further material state "
            "change"
        )
        if cumulative_updates and terminal_selected:
            terminal_selected["updates"] = dict(cumulative_updates)
            terminal_selected["candidate_id"] = (
                "combined_overdesign_terminal_fold:"
                f"{fold_index}:exact_stop"
            )
            terminal_selected["source_candidate_id"] = terminal_selected[
                "candidate_id"
            ]
            terminal_selected["terminal_candidate_status"] = (
                "TERMINAL_EXACT_STOP"
            )
            terminal_selected["further_cleanup_available"] = False
            terminal_selected["exact_blocker_reason"] = exact_blocker_reason
            terminal_selected["same_click_terminalisation_fold"] = True
            terminal_selected["terminal_fold_iterations"] = fold_index
            terminal_selected["terminal_fold_trace"] = tuple(fold_trace)
            final_result["selected_recommendation"] = terminal_selected
        else:
            # An empty update set is intentionally not exposed as an Apply.
            # It means the already-committed current state is the exact stop.
            final_result["selected_recommendation"] = None

        exact_stop_proof = dict(final_result.get("exact_stop_proof") or {})
        exact_stop_proof.update(
            {
                "terminal_candidate_status": "TERMINAL_EXACT_STOP",
                "no_progressing_family_owned_candidate": True,
                "source_ladders_evaluated_from_current_state": True,
                "source_ladders_restarted_from_reduced_state": bool(
                    cumulative_updates
                ),
                "current_state_terminal_exact_stop": (
                    current_state_exact_stop
                ),
                "cumulative_updates": dict(cumulative_updates),
                "exact_blocker_reason": exact_blocker_reason,
            }
        )
        final_result["exact_stop_proof"] = exact_stop_proof
        final_result["combined_overdesign_terminal_fold"] = {
            "terminal_reached": True,
            "terminal_candidate_status": "TERMINAL_EXACT_STOP",
            "fold_iterations": fold_index,
            "current_state_terminal_exact_stop": current_state_exact_stop,
            "cumulative_updates": dict(cumulative_updates),
            "trace": tuple(fold_trace),
        }
        return final_result

    for fold_index in range(max(1, int(max_fold_steps))):
        stage_result = _combined_overdesign_stage_result(
            working_state,
            family_strategy=family_strategy,
            evaluate_auto_design_candidate=_evaluate_fold_state_candidate,
        )
        final_result = dict(stage_result)
        selected = dict(stage_result.get("selected_recommendation") or {})
        ranked_rows = [
            dict(row)
            for row in list(
                stage_result.get("accepted_candidate_evidence")
                or stage_result.get("candidate_repairs")
                or []
            )
            if isinstance(row, dict)
            and row.get("accepted") is True
            and dict(row.get("updates") or {})
        ]
        ranked_rows.sort(key=lambda row: tuple(row.get("rank_key") or ()))
        ordered_rows: list[dict[str, Any]] = []
        seen_update_sets: set[tuple[tuple[str, str], ...]] = set()
        for row in [selected, *ranked_rows]:
            updates = dict(row.get("updates") or {})
            if not updates:
                continue
            signature = tuple(
                sorted(
                    (str(key), repr(value))
                    for key, value in updates.items()
                )
            )
            if signature in seen_update_sets:
                continue
            seen_update_sets.add(signature)
            ordered_rows.append(dict(row))

        def _coherent_step_updates(
            updates: dict[str, Any] | None,
        ) -> dict[str, Any]:
            """Keep rectangular width aliases equal in evaluated/apply state."""

            coherent = dict(updates or {})
            shape = str(
                working_state.get("section_shape")
                or working_state.get("sec_shape")
                or ""
            ).strip().upper()
            if shape in {"RECT", "RECTANGULAR"}:
                if coherent.get("b") is not None:
                    coherent["bw"] = coherent["b"]
                elif coherent.get("bw") is not None:
                    coherent["b"] = coherent["bw"]
            return coherent

        try:
            before_material = float(material_proxy(working_state))
        except Exception:
            before_material = math.inf

        def _materially_progresses(row: dict[str, Any]) -> bool:
            updates = _coherent_step_updates(row.get("updates"))
            if not any(
                working_state.get(key) != value
                for key, value in updates.items()
            ):
                return False
            trial_state = dict(working_state)
            trial_state.update(updates)
            try:
                after_material = float(material_proxy(trial_state))
            except Exception:
                return False
            return after_material < before_material - 1e-6

        source_transition_attempts: list[dict[str, Any]] = []
        source_transition_summary: dict[str, Any] = {}

        def _source_family_transition_candidate() -> dict[str, Any]:
            """Continue through a combined-to-single-family cleanup transition."""

            source_runtimes = (
                (
                    "BENDING_OVERDESIGN_GOVERNS",
                    build_bending_overdesign_live_evaluator(
                        _evaluate_fold_state_candidate
                    ),
                ),
                (
                    "SHEAR_OVERDESIGN_GOVERNS",
                    build_shear_overdesign_live_evaluator(
                        _evaluate_fold_state_candidate
                    ),
                ),
            )
            transition_rows: list[dict[str, Any]] = []
            for source_family_id, source_evaluator in source_runtimes:
                source_result = dict(
                    family_strategy_for(
                        source_family_id
                    ).contracted_optimisation_ladder_specs(
                        working_state,
                        evaluate_candidate=source_evaluator,
                    )
                    or {}
                )
                selected_source = dict(
                    source_result.get("selected_recommendation") or {}
                )
                source_rows = [
                    selected_source,
                    *[
                        dict(row)
                        for row in list(
                            source_result.get(
                                "accepted_candidate_evidence"
                            )
                            or source_result.get("candidate_repairs")
                            or source_result.get("specs")
                            or []
                        )
                        if isinstance(row, dict)
                    ],
                ]
                source_transition_summary[source_family_id] = {
                    "row_count": len(source_rows),
                    "material_progressing_count": 0,
                    "full_truth_passing_count": 0,
                    "selected_source_candidate_id": (
                        selected_source.get("candidate_id")
                    ),
                }
                seen_source_updates: set[
                    tuple[tuple[str, str], ...]
                ] = set()
                for row in source_rows:
                    if not row or row.get("accepted") is False:
                        continue
                    row = dict(row)
                    row["updates"] = _coherent_step_updates(
                        row.get("updates")
                    )
                    signature = tuple(
                        sorted(
                            (str(key), repr(value))
                            for key, value in dict(
                                row.get("updates") or {}
                            ).items()
                        )
                    )
                    if not signature or signature in seen_source_updates:
                        continue
                    seen_source_updates.add(signature)
                    material_progresses = _materially_progresses(row)
                    transition_attempt = {
                        "source_family_id": source_family_id,
                        "candidate_id": row.get("candidate_id"),
                        "updates": dict(row.get("updates") or {}),
                        "material_progresses": material_progresses,
                        "source_row_all_key_pass": dict(
                            row.get("capacity_summary") or {}
                        ).get("all_key_pass"),
                        "source_row_worst_util": dict(
                            row.get("capacity_summary") or {}
                        ).get("worst_util"),
                    }
                    if not material_progresses:
                        if len(source_transition_attempts) < 12:
                            source_transition_attempts.append(
                                transition_attempt
                            )
                        continue
                    source_transition_summary[source_family_id][
                        "material_progressing_count"
                    ] += 1
                    try:
                        transition_candidate = (
                            _evaluate_fold_state_candidate(
                                working_state,
                                updates=dict(row.get("updates") or {}),
                                source=(
                                    "combined_overdesign_source_family_"
                                    "transition"
                                ),
                                label=str(
                                    row.get("label")
                                    or row.get("candidate_id")
                                    or source_family_id
                                ),
                                action_type="apply_resolved_candidate",
                            )
                        )
                    except Exception:
                        transition_candidate = None
                    transition_overview = dict(
                        (transition_candidate or {}).get("overview") or {}
                    )
                    transition_attempt.update(
                        {
                            "is_compliant": bool(
                                isinstance(transition_candidate, dict)
                                and transition_candidate.get("is_compliant")
                            ),
                            "all_key_pass": bool(
                                transition_overview.get("all_key_pass")
                            ),
                            "worst_util": transition_overview.get(
                                "worst_util"
                            ),
                        }
                    )
                    source_transition_summary[source_family_id][
                        "last_full_truth_attempt"
                    ] = dict(transition_attempt)
                    if (
                        row.get("candidate_id")
                        == selected_source.get("candidate_id")
                    ):
                        source_transition_summary[source_family_id][
                            "selected_source_attempt"
                        ] = dict(transition_attempt)
                    if len(source_transition_attempts) < 12:
                        source_transition_attempts.append(
                            transition_attempt
                        )
                    if not bool(
                        isinstance(transition_candidate, dict)
                        and transition_candidate.get("is_compliant")
                        and transition_overview.get("all_key_pass")
                    ):
                        continue
                    source_transition_summary[source_family_id][
                        "full_truth_passing_count"
                    ] += 1
                    row["source_family_transition"] = True
                    row["source_family_id"] = source_family_id
                    row["source_family_transition_full_truth"] = {
                        "all_key_pass": True,
                        "is_compliant": True,
                        "worst_util": transition_overview.get("worst_util"),
                    }
                    row["terminal_candidate_status"] = (
                        "NON_TERMINAL_FURTHER_CLEANUP_AVAILABLE"
                    )
                    row["further_cleanup_available"] = True
                    transition_rows.append(row)
                    break
            if not transition_rows:
                return {}
            selected_transition = min(
                transition_rows,
                key=lambda row: (
                    float(
                        material_proxy(
                            {
                                **working_state,
                                **dict(row.get("updates") or {}),
                            }
                        )
                    ),
                    0
                    if row.get("source_family_id")
                    == "BENDING_OVERDESIGN_GOVERNS"
                    else 1,
                    str(row.get("candidate_id") or ""),
                ),
            )
            source_transition_summary["selected_candidate_id"] = (
                selected_transition.get("candidate_id")
            )
            return selected_transition

        if (
            selected
            and str(
                selected.get("terminal_candidate_status") or ""
            ).strip().upper()
            not in terminal_statuses
            and not _materially_progresses(selected)
        ):
            selected = next(
                (
                    dict(row)
                    for row in ordered_rows
                    if _materially_progresses(row)
                ),
                selected,
            )
            final_result["selected_recommendation"] = dict(selected)
        if not selected or not _materially_progresses(selected):
            source_transition = _source_family_transition_candidate()
            if source_transition:
                selected = dict(source_transition)
                final_result["selected_recommendation"] = dict(selected)
            elif fold_trace:
                fold_trace[-1]["source_family_transition_attempts"] = tuple(
                    source_transition_attempts
                )
                fold_trace[-1]["source_family_transition_summary"] = dict(
                    source_transition_summary
                )
        step_updates = _coherent_step_updates(selected.get("updates"))
        if selected:
            selected["updates"] = dict(step_updates)
        terminal_status = str(
            selected.get("terminal_candidate_status") or ""
        ).strip().upper()
        if not selected or not step_updates:
            fold_trace.append(
                {
                    "fold_index": fold_index + 1,
                    "terminal_candidate_status": terminal_status or None,
                    "stop_reason": "source_ladder_exhausted_without_candidate",
                }
            )
            return _terminalise_exhausted_family_ladders(
                fold_index=fold_index,
            )

        next_state = dict(working_state)
        next_state.update(step_updates)
        state_signature = tuple(
            sorted(
                (str(key), repr(value))
                for key, value in next_state.items()
            )
        )
        step_changes_state = any(
            working_state.get(key) != value
            for key, value in step_updates.items()
        )
        fold_trace.append(
            {
                "fold_index": fold_index + 1,
                "candidate_id": selected.get("candidate_id"),
                "step_updates": dict(step_updates),
                "terminal_candidate_status": terminal_status or None,
                "further_cleanup_available": bool(
                    selected.get("further_cleanup_available")
                ),
                "step_changes_state": step_changes_state,
            }
        )
        if not step_changes_state or state_signature in seen_states:
            fold_trace[-1]["stop_reason"] = "non_progressing_or_repeated_state"
            return _terminalise_exhausted_family_ladders(
                fold_index=fold_index,
                selected_template=selected,
            )
        seen_states.add(state_signature)
        cumulative_updates.update(step_updates)

        selected["updates"] = dict(cumulative_updates)
        selected["candidate_id"] = (
            "combined_overdesign_terminal_fold:"
            f"{fold_index + 1}:"
            f"{selected.get('candidate_id') or 'candidate'}"
        )
        selected["source_candidate_id"] = selected["candidate_id"]
        selected["same_click_terminalisation_fold"] = (
            terminal_status in terminal_statuses
        )
        selected["terminal_fold_iterations"] = fold_index + 1
        selected["terminal_fold_trace"] = tuple(fold_trace)
        final_result["selected_recommendation"] = selected
        last_progressing_selected = dict(selected)
        final_result["combined_overdesign_terminal_fold"] = {
            "terminal_reached": terminal_status in terminal_statuses,
            "terminal_candidate_status": terminal_status or None,
            "fold_iterations": fold_index + 1,
            "cumulative_updates": dict(cumulative_updates),
            "trace": tuple(fold_trace),
        }
        if terminal_status in terminal_statuses:
            # A terminal result for the currently selected combined candidate
            # does not prove that the post-update state has no remaining
            # single-family cleanup. Re-enter both source ladders from that
            # state so a combined-to-bending/shear family transition is folded
            # into the same Apply. The following iteration either adds the
            # remaining safe reduction or proves the cumulative state is the
            # exact stop.
            working_state = dict(base)
            working_state.update(cumulative_updates)
            continue
        working_state = dict(base)
        working_state.update(cumulative_updates)
    else:
        fold_trace.append(
            {
                "fold_index": int(max_fold_steps),
                "stop_reason": "terminal_fold_guard_exhausted",
            }
        )

    final_result["combined_overdesign_terminal_fold"] = {
        "terminal_reached": False,
        "terminal_candidate_status": str(
            dict(final_result.get("selected_recommendation") or {}).get(
                "terminal_candidate_status"
            )
            or ""
        ).strip()
        or None,
        "fold_iterations": len(
            [
                row
                for row in fold_trace
                if row.get("candidate_id")
            ]
        ),
        "cumulative_updates": dict(cumulative_updates),
        "trace": tuple(fold_trace),
    }
    # Partial combined-overdesign cleanup is diagnostic only.  Do not expose
    # the final non-terminal row as an Apply recommendation.
    final_result["selected_recommendation"] = None
    return final_result


_DIRECT_TARGET_BAND_GUIDANCE_DEPENDENCIES: tuple[str, ...] = (
    "_COMPOUND_BOTTOM_UPDATE_KEYS",
    "_COMPOUND_GEOMETRY_UPDATE_KEYS",
    "_COMPOUND_SHEAR_UPDATE_KEYS",
    "_annotate_candidate_target_band_metrics",
    "_bending_demands_negligible",
    "_build_candidate_search_evidence",
    "_candidate_is_materially_actionable",
    "_compound_guidance_title_reasoning_why",
    "_compound_subfamilies_from_updates",
    "_design_optimisation_goal",
    "_design_width_value",
    "_distance_to_target_band",
    "_evaluate_auto_design_candidate",
    "_family_tag_from_compound_updates",
    "_float_from_state",
    "_guidance_change_lines_for_updates",
    "_guidance_executor_actionability_contract",
    "_guidance_item_from_resolved_candidate",
    "_guidance_state_snapshot",
    "_local_cleanup_candidate_affects_family",
    "_local_cleanup_material_proxy",
    "_post_click_accepted_green_audit",
    "_resolve_design_actions_from_state",
    "_resolve_geometry_width_context",
    "_resolved_efficiency_target_band",
    "_shear_cleanup_materially_reduces_reinforcement",
    "_shear_demands_negligible",
    "_state_update_reduces_bottom_reinforcement",
    "_state_update_reduces_section_size",
    "_updates_match_state",
    "identify_materially_overprovided_non_governing_families",
)


@dataclass(frozen=True)
class FamilyLadderGuidanceRuntime:
    compound_bottom_update_keys: frozenset[str]
    compound_geometry_update_keys: frozenset[str]
    compound_shear_update_keys: frozenset[str]
    annotate_candidate_target_band_metrics: Callable[..., Any]
    bending_demands_negligible: Callable[..., Any]
    build_candidate_search_evidence: Callable[..., Any]
    candidate_is_materially_actionable: Callable[..., Any]
    compound_guidance_title_reasoning_why: Callable[..., Any]
    compound_subfamilies_from_updates: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    design_width_value: Callable[..., Any]
    distance_to_target_band: Callable[..., Any]
    evaluate_auto_design_candidate: Callable[..., Any]
    family_tag_from_compound_updates: Callable[..., Any]
    final_accepted_min_family_util: float
    float_from_state: Callable[..., Any]
    guidance_change_lines_for_updates: Callable[..., Any]
    guidance_executor_actionability_contract: Callable[..., Any]
    guidance_item_from_resolved_candidate: Callable[..., Any]
    guidance_state_snapshot: Callable[..., Any]
    local_cleanup_candidate_affects_family: Callable[..., Any]
    local_cleanup_material_proxy: Callable[..., Any]
    post_click_accepted_green_audit: Callable[..., Any]
    resolve_design_actions_from_state: Callable[..., Any]
    resolve_geometry_width_context: Callable[..., Any]
    resolved_efficiency_target_band: Callable[..., Any]
    shear_cleanup_materially_reduces_reinforcement: Callable[..., Any]
    shear_demands_negligible: Callable[..., Any]
    state_update_reduces_bottom_reinforcement: Callable[..., Any]
    state_update_reduces_section_size: Callable[..., Any]
    state_fingerprint: Callable[..., Any]
    updates_match_state: Callable[..., Any]
    identify_materially_overprovided_families: Callable[..., Any]
    build_bending_fail_shear_overdesign_live_evaluator: Callable[..., Any]
    build_bending_overdesign_live_evaluator: Callable[..., Any]
    build_combined_overdesign_live_evaluator: Callable[..., Any]
    build_shear_fail_bending_overdesign_live_evaluator: Callable[..., Any]
    build_shear_overdesign_live_evaluator: Callable[..., Any]


def _bind_family_ladder_guidance_runtime(
    runtime: FamilyLadderGuidanceRuntime,
) -> None:
    globals().update(
        {
            "_COMPOUND_BOTTOM_UPDATE_KEYS": runtime.compound_bottom_update_keys,
            "_COMPOUND_GEOMETRY_UPDATE_KEYS": runtime.compound_geometry_update_keys,
            "_COMPOUND_SHEAR_UPDATE_KEYS": runtime.compound_shear_update_keys,
        }
    )
    public_names = {
        "identify_materially_overprovided_families",
        "build_bending_fail_shear_overdesign_live_evaluator",
        "build_bending_overdesign_live_evaluator",
        "build_combined_overdesign_live_evaluator",
        "build_shear_fail_bending_overdesign_live_evaluator",
        "build_shear_overdesign_live_evaluator",
    }
    for field_name in tuple(runtime.__dataclass_fields__)[3:]:
        dependency_name = (
            field_name
            if field_name in public_names
            else f"_{field_name}"
        )
        if field_name == "identify_materially_overprovided_families":
            dependency_name = (
                "identify_materially_overprovided_non_governing_families"
            )
        globals()[dependency_name] = getattr(runtime, field_name)


def bind_family_ladder_guidance_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _DIRECT_TARGET_BAND_GUIDANCE_DEPENDENCIES
            if name in namespace
        }
    )


def _overdesign_family_id_from_cleanup_updates(updates: dict | None) -> str:
    keys = set(dict(updates or {}))
    has_shear = bool(keys & _COMPOUND_SHEAR_UPDATE_KEYS)
    has_bottom = bool(keys & _COMPOUND_BOTTOM_UPDATE_KEYS) or any(
        str(key).startswith("bot") or str(key).startswith("db_bot") for key in keys
    )
    has_geometry = bool(keys & _COMPOUND_GEOMETRY_UPDATE_KEYS)
    if has_shear and (has_bottom or has_geometry):
        return "COMBINED_OVERDESIGN"
    if has_shear:
        return "SHEAR_OVERDESIGN_GOVERNS"
    if has_bottom:
        return "BENDING_OVERDESIGN_GOVERNS"
    if has_geometry:
        return "GEOMETRY_DETAILING_GOVERNS"
    return ""


def _overdesign_family_id_from_cleanup_family(family: Any) -> str:
    normalised = str(family or "").strip().lower()
    if normalised == "bending":
        return "BENDING_OVERDESIGN_GOVERNS"
    if normalised == "shear":
        return "SHEAR_OVERDESIGN_GOVERNS"
    if normalised == "combined":
        return "COMBINED_OVERDESIGN"
    if normalised == "geometry":
        return "GEOMETRY_DETAILING_GOVERNS"
    if normalised.endswith("_governs") or normalised.endswith("_overdesign"):
        return str(family or "").strip()
    return ""


def _family_ladder_guidance_item(
    state: dict,
    overview: dict | None,
    mode_config: dict,
    *,
    strengthening: bool,
    debug_sink: dict | None = None,
    runtime: FamilyLadderGuidanceRuntime | None = None,
) -> dict | None:
    if runtime is not None:
        _bind_family_ladder_guidance_runtime(runtime)
    """Resolve a target-band update through the selected family ladder."""
    base = _guidance_state_snapshot(dict(state or {}))
    if not base:
        return None
    geometry_locked = bool(base.get("optimisation_lock_geometry", False))
    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal(base))
    width_key, _, base_width = _resolve_geometry_width_context(base)
    base_width = float(base_width or 0.0)
    base_depth = float(_float_from_state(base, "D", 0.0) or 0.0)
    if base_width <= 0.0 or base_depth <= 0.0:
        return None

    candidates: list[dict] = []
    seen_updates: set[tuple] = set()
    # A single-family repair ladder is already bounded by its family contract.
    # Keep enough room to evaluate that ordered ladder in full.  Sampling the
    # SHEAR_FAIL_GOVERNS ladder previously skipped later depth/width restart
    # steps and could turn an unlocked, repairable beam into a blocked card.
    max_evals = 384
    defer_active_shear_blocker = False
    deferred_full_audit_top_n = 80
    material_family_set: set[str] = set()
    try:
        _, material_families, _ = identify_materially_overprovided_non_governing_families(
            dict(overview or {})
        )
        material_family_set = {
            str(family or "").strip().lower()
            for family in list(material_families or [])
        }
    except Exception:
        material_family_set = set()
    if not strengthening:
        overview_utils = dict((overview or {}).get("utils") or {})
        overview_statuses = dict((overview or {}).get("statuses") or {})
        for family in ("bending", "shear"):
            try:
                utilisation = float(overview_utils.get(family))
            except (TypeError, ValueError):
                continue
            status = str(
                overview_statuses.get(family) or ""
            ).strip().upper()
            if (
                status not in {"FAIL", "FAILED", "ERROR"}
                and utilisation
                < float(_final_accepted_min_family_util)
            ):
                material_family_set.add(family)
    # The canonical material-overprovision classifier owns family membership.
    # The accepted-green floor can add an unresolved overprovided family; the
    # higher preferred target floor remains a ranking goal and must not turn a
    # single-family cleanup into a combined cleanup.
    statuses = dict((overview or {}).get("statuses") or {})
    try:
        strengthening_design_actions = _resolve_design_actions_from_state(base)
    except Exception:
        strengthening_design_actions = dict(
            (overview or {}).get("actions_used") or {}
        )
    if strengthening and "shear" in material_family_set:
        # A zero-demand, reinforcement-inactive shear check is not an
        # overdesign family.  Treating its displayed 0.0 utilisation as
        # material overprovision incorrectly diverts a pure bending failure
        # into the mixed bending/shear ladder, whose shear updates are then
        # (correctly) rejected by the executor as meaningless.
        shear_reinforcement_active = bool(
            float(_float_from_state(base, "lig_d", 0.0) or 0.0) > 0.0
            and int(_float_from_state(base, "lig_legs", 0.0) or 0.0) > 0
        )
        if (
            _shear_demands_negligible(strengthening_design_actions)
            and not shear_reinforcement_active
        ):
            material_family_set.discard("shear")
            if isinstance(debug_sink, dict):
                debug_sink[
                    "zero_demand_inactive_shear_excluded_from_mixed_family"
                ] = True
    if (
        strengthening
        and "bending" in material_family_set
        and _bending_demands_negligible(strengthening_design_actions)
    ):
        # A zero-demand bending check is inactive while a real shear failure is
        # being repaired.  Its displayed low utilisation must not divert the
        # active repair into the shear-fail/bending-overdesign mixed family.
        # Any minimum-reinforcement cleanup remains a later cleanup concern.
        material_family_set.discard("bending")
        if isinstance(debug_sink, dict):
            debug_sink[
                "zero_demand_bending_excluded_from_mixed_failure_family"
            ] = True
    active_failure_keys = {
        family
        for family in ("bending", "shear")
        if str(statuses.get(family) or "").strip().upper() in {"FAIL", "FAILED"}
    }
    dispatch_family_id = ""
    if strengthening:
        if active_failure_keys >= {"bending", "shear"}:
            dispatch_family_id = "COMBINED_BENDING_SHEAR_FAIL"
        elif active_failure_keys == {"bending"} and "shear" in material_family_set:
            dispatch_family_id = "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
        elif active_failure_keys == {"shear"} and "bending" in material_family_set:
            dispatch_family_id = "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
        elif active_failure_keys == {"bending"}:
            dispatch_family_id = "BENDING_FAIL_GOVERNS"
        elif active_failure_keys == {"shear"}:
            dispatch_family_id = "SHEAR_FAIL_GOVERNS"
    elif material_family_set >= {"bending", "shear"}:
        dispatch_family_id = "COMBINED_OVERDESIGN"
    elif material_family_set == {"bending"}:
        dispatch_family_id = "BENDING_OVERDESIGN_GOVERNS"
    elif material_family_set == {"shear"}:
        dispatch_family_id = "SHEAR_OVERDESIGN_GOVERNS"
    dispatch_decision = resolve_family_ladder_dispatch(
        {
            "selected_family_id": dispatch_family_id,
            "classification_passed": bool(dispatch_family_id),
        }
    ).to_dict()
    approved_candidate_contract_id = str(
        dispatch_decision.get("candidate_contract_id") or ""
    ).strip()
    approved_generation_policy_id = str(
        dispatch_decision.get("generation_policy_id") or ""
    ).strip()
    approved_evaluation_policy_id = str(
        dispatch_decision.get("evaluation_policy_id") or ""
    ).strip()
    approved_selection_policy_id = str(
        dispatch_decision.get("selection_policy_id") or ""
    ).strip()
    if dispatch_decision.get("should_run_family_ladder") and not all(
        (
            approved_candidate_contract_id,
            approved_generation_policy_id,
            approved_evaluation_policy_id,
            approved_selection_policy_id,
        )
    ):
        raise RuntimeError("family ladder dispatch has no approved candidate system")
    if isinstance(debug_sink, dict):
        debug_sink["family_ladder_dispatch"] = dict(dispatch_decision)
        debug_sink["family_ladder_dispatch_selected_family_id"] = (
            dispatch_decision.get("normalised_family_id")
        )
        debug_sink["family_ladder_dispatch_should_run_first"] = bool(
            dispatch_decision.get("should_run_family_ladder")
        )
        debug_sink["legacy_search_used_despite_family_ladder_available"] = bool(
            False
        )

    def _candidate_action_type_for_updates(updates: dict) -> str:
        keys = set(updates.keys())
        has_geom = bool(keys & _COMPOUND_GEOMETRY_UPDATE_KEYS)
        has_bottom = bool(keys & _COMPOUND_BOTTOM_UPDATE_KEYS)
        has_shear = bool(keys & _COMPOUND_SHEAR_UPDATE_KEYS)
        if sum(1 for flag in (has_geom, has_bottom, has_shear) if flag) >= 2:
            return "apply_resolved_candidate"
        if has_shear:
            return "apply_shear_recommendation"
        if has_bottom:
            return "apply_bottom_recommendation"
        if has_geom:
            return "apply_geometry_recommendation" if strengthening else "tighten_geometry"
        return "apply_resolved_candidate"

    def _evaluate_updates(
        updates: dict,
        label: str,
        *,
        source_stage: str = "family_ladder",
        trusted_family_selected: bool = False,
    ) -> dict | None:
        if len(candidates) >= max_evals:
            return None
        u = dict(updates or {})
        if not u or _updates_match_state(base, u):
            return None
        if (
            not trusted_family_selected
            and not _candidate_is_materially_actionable(base, u)
        ):
            return None
        if not strengthening:
            trial_state_for_materiality = dict(base)
            trial_state_for_materiality.update(u)
            if material_family_set and not any(
                _local_cleanup_candidate_affects_family(family, u)
                for family in material_family_set
            ):
                return None
            before_proxy = _local_cleanup_material_proxy(base)
            after_proxy = _local_cleanup_material_proxy(trial_state_for_materiality)
            if after_proxy >= before_proxy - 1e-6:
                return None
            if _state_update_reduces_section_size(base, trial_state_for_materiality) is False:
                try:
                    w0 = float(_design_width_value(base) or 0.0)
                    w1 = float(_design_width_value(trial_state_for_materiality) or w0)
                    d0 = float(_float_from_state(base, "D", 0.0) or 0.0)
                    d1 = float(_float_from_state(trial_state_for_materiality, "D", d0) or d0)
                    if w1 > w0 + 1e-9 or d1 > d0 + 1e-9:
                        return None
                except Exception:
                    pass
            if not (
                _state_update_reduces_section_size(base, trial_state_for_materiality)
                or _state_update_reduces_bottom_reinforcement(base, trial_state_for_materiality)
                or _shear_cleanup_materially_reduces_reinforcement(base, trial_state_for_materiality)
            ):
                return None
        sig = tuple(sorted((str(k), str(v)) for k, v in u.items()))
        if sig in seen_updates and not trusted_family_selected:
            return None
        seen_updates.add(sig)
        action_type = _candidate_action_type_for_updates(u)
        try:
            cand = _evaluate_auto_design_candidate(
                base,
                updates=u,
                source="design_guide_direct_target_band_search",
                label=label,
                action_type=action_type,
            )
        except Exception:
            cand = None
        if not isinstance(cand, dict):
            return None
        _annotate_candidate_target_band_metrics(cand, mode_config)
        # Direct Design Guide evidence must use the same governing preview
        # utilisation the visible summary will publish after the click.
        try:
            preview_worst = float(((cand.get("overview") or {}).get("worst_util")))
        except (TypeError, ValueError):
            preview_worst = None
        if preview_worst is not None and math.isfinite(preview_worst):
            cand["candidate_post_util"] = preview_worst
            cand["worst_util"] = preview_worst
            cand["candidate_distance_to_target_band"] = _distance_to_target_band(
                preview_worst,
                float(t_lo),
                float(t_hi),
            )
            cand["candidate_reaches_target_band"] = bool(float(t_lo) <= preview_worst <= float(t_hi))
        cand["updates"] = dict(u)
        cand["action_type"] = "apply_resolved_candidate"
        executor_probe_item = {
            "action_type": "apply_resolved_candidate",
            "family": _family_tag_from_compound_updates(u, base),
            "updates": dict(u),
            "action_payload": {
                "updates": dict(u),
                "resolved_candidate_updates": dict(u),
            },
            "resolved_candidate": {
                "updates": dict(u),
                "action_type": "apply_resolved_candidate",
            },
        }
        try:
            executor_valid, executor_reason = (
                _guidance_executor_actionability_contract(
                    executor_probe_item,
                    state=base,
                )
            )
        except Exception as exc:
            executor_valid = False
            executor_reason = (
                "executor_actionability_contract_error:"
                + type(exc).__name__
            )
        cand["is_executable"] = bool(executor_valid)
        cand["executor_actionability_reason"] = str(
            executor_reason or ""
        )
        if trusted_family_selected:
            # The selected-family runtime has already evaluated and ranked
            # this exact update through the full executor-backed adapter.
            cand["is_executable"] = True
            cand["advisory_only"] = False
        trial_state_for_final_audit = dict(base)
        trial_state_for_final_audit.update(u)
        final_acceptance_audit = _post_click_accepted_green_audit(
            dict(cand.get("overview") or {}),
            blocker_source=dict(cand),
            state=trial_state_for_final_audit,
            build_active_shear_blocker=not defer_active_shear_blocker,
        )
        cand["final_acceptance_audit"] = dict(final_acceptance_audit)
        cand["final_accepted_green_valid"] = bool(
            final_acceptance_audit.get("post_click_accepted_green_valid")
        )
        cand["final_unresolved_low_util_families"] = list(
            final_acceptance_audit.get("post_click_unresolved_low_util_families") or []
        )
        cand["final_families_below_threshold"] = list(
            final_acceptance_audit.get("post_click_families_below_final_threshold") or []
        )
        if not strengthening:
            trial_state = dict(base)
            trial_state.update(u)
            before_proxy = _local_cleanup_material_proxy(base)
            after_proxy = _local_cleanup_material_proxy(trial_state)
            cand["candidate_complexity_score"] = len(u)
            cand["material_proxy_before"] = before_proxy
            cand["material_proxy_after"] = after_proxy
            cand["material_proxy_delta"] = after_proxy - before_proxy
            cand["net_efficiency_delta"] = before_proxy - after_proxy
            cand["is_executable"] = True
            cand["advisory_only"] = False
            if material_family_set:
                affected = [
                    family for family in sorted(material_family_set)
                    if _local_cleanup_candidate_affects_family(family, u)
                ]
                cand["affected_family"] = affected[0] if len(affected) == 1 else "combined"
        cand["guidance_change_lines"] = _guidance_change_lines_for_updates(base, u)
        subfamilies = _compound_subfamilies_from_updates(u)
        cand["subfamilies"] = list(subfamilies)
        cand["recommendation_family_tag"] = _family_tag_from_compound_updates(u, base)
        cand["candidate_source_stage"] = str(source_stage)
        candidate_from_approved_ladder = bool(
            dispatch_decision.get("should_run_family_ladder")
            and str(source_stage).startswith("family_ladder:")
        )
        cand["candidate_contract_id"] = approved_candidate_contract_id or None
        cand["candidate_generation_policy_id"] = (
            approved_generation_policy_id or None
        )
        cand["candidate_evaluation_policy_id"] = (
            approved_evaluation_policy_id or None
        )
        cand["candidate_selection_policy_id"] = (
            approved_selection_policy_id or None
        )
        cand["candidate_contract_approved"] = candidate_from_approved_ladder
        title, _, _ = _compound_guidance_title_reasoning_why(
            base,
            u,
            subfamilies,
            strengthening=bool(strengthening),
        )
        cand["label"] = str(title or label or "Direct target-band candidate")
        candidates.append(cand)
        return cand

    def _is_safe_ladder_target(candidate: dict | None) -> bool:
        if not isinstance(candidate, dict):
            return False
        try:
            candidate_util = float(candidate.get("candidate_post_util"))
        except (TypeError, ValueError):
            return False
        return bool(
            candidate.get("is_compliant")
            and (candidate.get("overview") or {}).get("all_key_pass")
            and float(t_lo) <= candidate_util <= float(t_hi)
            and candidate.get("final_accepted_green_valid")
            and candidate.get("is_executable")
            and not candidate.get("advisory_only")
            and dict(candidate.get("updates") or {})
        )

    def _is_family_exact_stop_candidate(
        candidate: dict | None,
        *,
        selected: dict | None,
        ladder_result: dict | None,
    ) -> bool:
        """Accept a mixed-family winner only when its owner proves exact stop.

        The generic green audit requires every family to enter the preferred
        target band. Mixed repair/overdesign families intentionally permit the
        mandatory failing family to be repaired while an already-compliant
        opportunistic family remains below band, but only with the contracted
        no-higher-ranked-candidate exact-stop proof.
        """

        if not isinstance(candidate, dict):
            return False
        selected_d = dict(selected or {})
        result_d = dict(ladder_result or {})
        proof = dict(result_d.get("exact_stop_proof") or {})
        evaluation = dict(selected_d.get("evaluation") or {})
        engineering_status = dict(evaluation.get("engineering_status") or {})
        code_status = str(
            dict(evaluation.get("code_compliance_status") or {}).get("status")
            or ""
        ).upper()
        constructability_status = str(
            dict(evaluation.get("constructability_status") or {}).get("status")
            or ""
        ).upper()
        candidate_overview = dict(candidate.get("overview") or {})
        mandatory_repair_proven = bool(
            (
                proof.get("selected_shear_repaired") is True
                and proof.get("selected_bending_compliant") is True
                and proof.get("bending_optimisation_opportunistic_only") is True
            )
            or (
                proof.get("selected_bending_repaired") is True
                and proof.get("selected_shear_compliant") is True
                and proof.get("shear_optimisation_opportunistic_only") is True
            )
        )
        return bool(
            selected_d.get("accepted") is True
            and proof.get("no_higher_ranked_candidate_exists") is True
            and mandatory_repair_proven
            and engineering_status.get("candidate_valid") is True
            and code_status == "PASS"
            and constructability_status == "PASS"
            and candidate_overview.get("all_key_pass")
            and dict(candidate.get("updates") or {})
        )

    def _is_shear_overdesign_discrete_stop_candidate(
        candidate: dict | None,
        *,
        selected: dict | None,
        ladder_result: dict | None,
    ) -> bool:
        """Accept the family-owned smallest safe width when the next step fails."""

        if dispatch_family_id != "SHEAR_OVERDESIGN_GOVERNS":
            return False
        if not isinstance(candidate, dict):
            return False
        selected_d = dict(selected or {})
        result_d = dict(ladder_result or {})
        ranking = dict(result_d.get("ranking_proof") or {})
        geometry = dict(result_d.get("geometry_restriction_proof") or {})
        overview_after = dict(candidate.get("overview") or {})
        width_candidates = [
            dict(row)
            for row in list(
                geometry.get("width_candidates_tested") or []
            )
            if isinstance(row, dict)
        ]
        blocked_width_candidates = [
            row
            for row in width_candidates
            if row.get("accepted") is False
        ]
        return bool(
            selected_d.get("accepted") is True
            and str(selected_d.get("lane_id") or "") == "WIDTH_REDUCTION"
            and ranking.get("smallest_safe_width_selected") is True
            and geometry.get("width_reduction_attempted") is True
            and geometry.get("smallest_safe_width") is not None
            and bool(blocked_width_candidates)
            and candidate.get("is_compliant")
            and overview_after.get("all_key_pass")
            and candidate.get("final_accepted_green_valid")
            and candidate.get("is_executable")
            and not candidate.get("advisory_only")
            and dict(candidate.get("updates") or {})
        )

    ladder_success = False
    ladder_candidate: dict | None = None
    ladder_attempts = 0
    family_ladder_candidate_trace: list[dict[str, Any]] = []
    family_ladder_result: dict[str, Any] = {}
    active_strength_specs: list[dict[str, Any]] = []
    if (
        strengthening
        and dispatch_decision.get("should_run_family_ladder")
        and dispatch_family_id
        in {
            "BENDING_FAIL_GOVERNS",
            "SHEAR_FAIL_GOVERNS",
            "COMBINED_BENDING_SHEAR_FAIL",
        }
    ):
        try:
            family_strategy = family_strategy_for(dispatch_family_id)
            if dispatch_family_id == "COMBINED_BENDING_SHEAR_FAIL":
                bending_ladder = family_strategy_for(
                    "BENDING_FAIL_GOVERNS"
                ).contracted_repair_ladder_specs(
                    base,
                    width_key=width_key,
                    geometry_locked=geometry_locked,
                )
                shear_ladder = family_strategy_for(
                    "SHEAR_FAIL_GOVERNS"
                ).contracted_repair_ladder_specs(
                    base,
                    width_key=width_key,
                    geometry_locked=geometry_locked,
                )
                bending_sources = tuple(
                    {
                        **dict(row),
                        "source_family_id": "BENDING_FAIL_GOVERNS",
                        "candidate_id": str(
                            row.get("candidate_id")
                            or row.get("source_candidate_id")
                            or f"bending_ladder_{index}"
                        ),
                    }
                    for index, row in enumerate(
                        _bounded_ordered_stage_specs(
                            list(bending_ladder.get("specs") or [])
                        ),
                        start=1,
                    )
                    if isinstance(row, dict)
                )
                shear_sources = tuple(
                    {
                        **dict(row),
                        "source_family_id": "SHEAR_FAIL_GOVERNS",
                        "candidate_id": str(
                            row.get("candidate_id")
                            or row.get("source_candidate_id")
                            or f"shear_ladder_{index}"
                        ),
                    }
                    for index, row in enumerate(
                        _bounded_ordered_stage_specs(
                            list(shear_ladder.get("specs") or [])
                        ),
                        start=1,
                    )
                    if isinstance(row, dict)
                )
                approved_combined_candidates = ()
                if (
                    not geometry_locked
                    and callable(
                        getattr(
                            family_strategy,
                            "build_target_band_refinement_candidates",
                            None,
                        )
                    )
                ):
                    approved_combined_candidates = tuple(
                        family_strategy.build_target_band_refinement_candidates(
                            base,
                            bending_fail_candidates=bending_sources,
                            shear_fail_candidates=shear_sources,
                        )
                    )
                family_ladder_result = dict(
                    family_strategy.contracted_repair_ladder_specs(
                        base,
                        bending_fail_candidates=bending_sources,
                        shear_fail_candidates=shear_sources,
                        approved_combined_merge_candidates=(
                            approved_combined_candidates
                        ),
                    )
                    or {}
                )
                family_ladder_result["combined_source_inventory"] = {
                    "bending_total": len(list(bending_ladder.get("specs") or [])),
                    "shear_total": len(list(shear_ladder.get("specs") or [])),
                    "bending_selected": len(bending_sources),
                    "shear_selected": len(shear_sources),
                    "approved_combined_selected": len(
                        approved_combined_candidates
                    ),
                    "maximum_merged_candidates": min(
                        max_evals,
                        (
                            len(bending_sources)
                            + len(shear_sources)
                            + len(bending_sources) * len(shear_sources)
                            + len(approved_combined_candidates)
                        ),
                    ),
                    "selection_policy": (
                        "reinforcement_only_then_shear_only_then_"
                        "combined_adjustment_then_geometry"
                    ),
                }
            else:
                family_ladder_result = dict(
                    family_strategy.contracted_repair_ladder_specs(
                        base,
                        width_key=width_key,
                        geometry_locked=geometry_locked,
                    )
                    or {}
                )
            contract_specs = [
                dict(row)
                for row in list(family_ladder_result.get("specs") or [])
                if isinstance(row, dict) and dict(row.get("updates") or {})
            ]
            if dispatch_family_id in {
                "BENDING_FAIL_GOVERNS",
                "SHEAR_FAIL_GOVERNS",
                "COMBINED_BENDING_SHEAR_FAIL",
            }:
                # A product evaluation ceiling is not an engineering stop.
                # Every selected-family contract candidate must remain
                # reachable; the loop still short-circuits on the first safe
                # target-band repair.
                max_evals = max(
                    int(max_evals),
                    len(candidates) + len(contract_specs),
                )
            # Active strength failures use deterministic, contract-bounded
            # ladders. Preserve every legal incremental step so a later
            # reinforcement or geometry repair cannot be lost to sampling.
            active_specs = _active_strengthening_ladder_specs(
                dispatch_family_id,
                contract_specs,
                max_evals=max_evals,
            )
            active_strength_specs = list(active_specs)
            for spec in active_specs:
                ladder_attempts += 1
                ladder_candidate_id = str(
                    spec.get("candidate_id")
                    or spec.get("source_candidate_id")
                    or f"{dispatch_family_id}:ladder:{ladder_attempts}"
                )
                candidate = _evaluate_updates(
                    dict(spec.get("updates") or {}),
                    str(
                        spec.get("label")
                        or f"{dispatch_family_id} contract ladder"
                    ),
                    source_stage=f"family_ladder:{dispatch_family_id}",
                )
                if isinstance(candidate, dict):
                    candidate["family_ladder_candidate_id"] = (
                        ladder_candidate_id
                    )
                candidate_overview = dict((candidate or {}).get("overview") or {})
                candidate_acceptance = dict(
                    (candidate or {}).get("final_acceptance_audit") or {}
                )
                family_ladder_candidate_trace.append(
                    {
                        "candidate_id": ladder_candidate_id,
                        "label": str(spec.get("label") or ""),
                        "updates": dict(spec.get("updates") or {}),
                        "candidate_post_util": (candidate or {}).get(
                            "candidate_post_util"
                        ),
                        "is_compliant": bool(
                            (candidate or {}).get("is_compliant")
                        ),
                        "all_key_pass": bool(
                            candidate_overview.get("all_key_pass")
                        ),
                        "in_target_band": bool(
                            isinstance(candidate, dict)
                            and candidate.get("candidate_post_util") is not None
                            and float(t_lo)
                            <= float(candidate.get("candidate_post_util"))
                            <= float(t_hi)
                        ),
                        "final_accepted_green_valid": bool(
                            (candidate or {}).get(
                                "final_accepted_green_valid"
                            )
                        ),
                        "final_acceptance_invalid_reason": str(
                            candidate_acceptance.get(
                                "post_click_accepted_green_invalid_reason"
                            )
                            or ""
                        ),
                        "families_below_final_threshold": list(
                            candidate_acceptance.get(
                                "post_click_families_below_final_threshold"
                            )
                            or []
                        ),
                        "unresolved_low_util_families": list(
                            candidate_acceptance.get(
                                "post_click_unresolved_low_util_families"
                            )
                            or []
                        ),
                        "is_executable": bool(
                            (candidate or {}).get("is_executable")
                        ),
                        "advisory_only": bool(
                            (candidate or {}).get("advisory_only")
                        ),
                    }
                )
                if _is_safe_ladder_target(candidate):
                    ladder_candidate = candidate
                    ladder_success = True
                    break
        except Exception as exc:
            family_ladder_result = {
                "family_id": dispatch_family_id,
                "error": type(exc).__name__,
            }
            if isinstance(debug_sink, dict):
                debug_sink["family_ladder_dispatch_error"] = type(exc).__name__
    if (
        not ladder_success
        and strengthening
        and dispatch_decision.get("should_run_family_ladder")
        and dispatch_family_id
        in {
            "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        }
    ):
        try:
            mixed_strategy = family_strategy_for(dispatch_family_id)
            if dispatch_family_id == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS":
                mandatory_result = family_strategy_for(
                    "BENDING_FAIL_GOVERNS"
                ).contracted_repair_ladder_specs(
                    base,
                    width_key=width_key,
                    geometry_locked=geometry_locked,
                )
                # Safety repair owns this transaction.  Do not spend the
                # pre-repair pass evaluating optional shear cleanup: once the
                # bending repair is applied, the next classification can
                # offer cleanup against the repaired beam.
                opportunistic_result = {"specs": ()}
                mandatory_sources = tuple(
                    {
                        **dict(row),
                        "source_family_id": "BENDING_FAIL_GOVERNS",
                        "candidate_id": str(
                            row.get("candidate_id")
                            or row.get("source_candidate_id")
                            or f"bending_fail_{index}"
                        ),
                    }
                    for index, row in enumerate(
                        (
                            _continuous_unlocked_bending_geometry_specs(
                                _with_progressive_bending_depth_specs(
                                    list(mandatory_result.get("specs") or []),
                                    base_depth=float(base.get("D") or 350.0),
                                ),
                                base_depth=float(base.get("D") or 350.0),
                                base_width=float(base_width),
                                width_key=width_key,
                                base_state=base,
                            )
                            if not geometry_locked
                            else tuple(mandatory_result.get("specs") or ())
                        ),
                        start=1,
                    )
                    if isinstance(row, dict) and dict(row.get("updates") or {})
                )
                opportunistic_sources = ()
                family_ladder_result = dict(
                    mixed_strategy.contracted_mixed_ladder_result(
                        base,
                        bending_fail_candidates=mandatory_sources,
                        shear_overdesign_candidates=opportunistic_sources,
                        evaluate_candidate=build_bending_fail_shear_overdesign_live_evaluator(
                            _evaluate_auto_design_candidate
                        ),
                    )
                    or {}
                )
            else:
                mandatory_result = family_strategy_for(
                    "SHEAR_FAIL_GOVERNS"
                ).contracted_repair_ladder_specs(
                    base,
                    width_key=width_key,
                    geometry_locked=geometry_locked,
                )
                # Safety repair owns this transaction.  Optional bending
                # cleanup is evaluated after shear passes and the result is
                # reclassified, exactly as the reciprocal bending-fail mixed
                # family defers optional shear cleanup.
                opportunistic_result = {"specs": ()}
                mandatory_sources = tuple(
                    {
                        **dict(row),
                        "source_family_id": "SHEAR_FAIL_GOVERNS",
                        "candidate_id": str(
                            row.get("candidate_id")
                            or row.get("source_candidate_id")
                            or f"shear_fail_{index}"
                        ),
                    }
                    for index, row in enumerate(
                        list(mandatory_result.get("specs") or []),
                        start=1,
                    )
                    if isinstance(row, dict) and dict(row.get("updates") or {})
                )
                opportunistic_sources = ()
                family_ladder_result = (
                    _run_incremental_shear_fail_bending_overdesign_ladder(
                        mixed_strategy,
                        base,
                        mandatory_sources=mandatory_sources,
                        evaluate_candidate=build_shear_fail_bending_overdesign_live_evaluator(
                            _evaluate_auto_design_candidate
                        ),
                    )
                )
            family_ladder_result["combined_source_inventory"] = {
                "mandatory_total": len(
                    list(mandatory_result.get("specs") or [])
                ),
                "opportunistic_total": len(
                    list(opportunistic_result.get("specs") or [])
                ),
                "mandatory_selected": len(mandatory_sources),
                "opportunistic_selected": len(opportunistic_sources),
                "selection_limit_per_family": (
                    None
                    if dispatch_family_id
                    == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
                    else _COMBINED_SOURCE_LIMIT_PER_FAMILY
                ),
                "selection_policy": (
                    "incremental_until_valid_repair_or_canonical_exhaustion"
                    if dispatch_family_id
                    == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
                    else "ordered_stage_coverage"
                ),
                "mandatory_selection_policy": (
                    "all_deterministic_repair_candidates"
                    if dispatch_family_id
                    in {
                        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
                        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
                    }
                    else "ordered_stage_coverage"
                ),
            }
            mixed_rows = list(
                family_ladder_result.get("mixed_merge_trace")
                or family_ladder_result.get("candidate_repairs")
                or []
            )
            ladder_attempts += len(mixed_rows)
            selected = dict(
                family_ladder_result.get("selected_recommendation") or {}
            )
            selected_updates = dict(selected.get("updates") or {})
            if selected_updates:
                candidate = _evaluate_updates(
                    selected_updates,
                    f"{dispatch_family_id} contract ladder",
                    source_stage=f"family_ladder:{dispatch_family_id}",
                    trusted_family_selected=bool(
                        selected.get("accepted") is True
                    ),
                )
                family_exact_stop_accepted = _is_family_exact_stop_candidate(
                    candidate,
                    selected=selected,
                    ladder_result=family_ladder_result,
                )
                selected_evaluation = dict(
                    selected.get("evaluation") or {}
                )
                family_exact_stop_acceptance_probe = {
                    "candidate_present": isinstance(candidate, dict),
                    "candidate_updates": dict(
                        (candidate or {}).get("updates") or {}
                    ),
                    "candidate_all_key_pass": bool(
                        dict((candidate or {}).get("overview") or {}).get(
                            "all_key_pass"
                        )
                    ),
                    "selected_accepted": selected.get("accepted") is True,
                    "selected_engineering_valid": (
                        dict(
                            selected_evaluation.get("engineering_status")
                            or {}
                        ).get("candidate_valid")
                        is True
                    ),
                    "selected_code_status": str(
                        dict(
                            selected_evaluation.get(
                                "code_compliance_status"
                            )
                            or {}
                        ).get("status")
                        or ""
                    ).upper(),
                    "selected_constructability_status": str(
                        dict(
                            selected_evaluation.get(
                                "constructability_status"
                            )
                            or {}
                        ).get("status")
                        or ""
                    ).upper(),
                    "exact_stop_proof": dict(
                        family_ladder_result.get("exact_stop_proof")
                        or {}
                    ),
                    "family_exact_stop_accepted": bool(
                        family_exact_stop_accepted
                    ),
                }
                family_ladder_result[
                    "family_exact_stop_acceptance_probe"
                ] = dict(family_exact_stop_acceptance_probe)
                if isinstance(debug_sink, dict):
                    debug_sink[
                        "family_exact_stop_acceptance_probe"
                    ] = dict(family_exact_stop_acceptance_probe)
                if _is_safe_ladder_target(candidate) or family_exact_stop_accepted:
                    if isinstance(candidate, dict):
                        candidate["family_exact_stop_accepted"] = bool(
                            family_exact_stop_accepted
                        )
                        candidate["family_exact_stop_proof"] = dict(
                            family_ladder_result.get("exact_stop_proof") or {}
                        )
                    ladder_candidate = candidate
                    ladder_success = True
        except Exception as exc:
            family_ladder_result = {
                "family_id": dispatch_family_id,
                "error": type(exc).__name__,
            }
            if isinstance(debug_sink, dict):
                debug_sink["family_ladder_dispatch_error"] = type(exc).__name__
    if (
        not ladder_success
        and
        not strengthening
        and dispatch_decision.get("should_run_family_ladder")
        and dispatch_family_id
        in {
            "BENDING_OVERDESIGN_GOVERNS",
            "SHEAR_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
        }
    ):
        try:
            family_strategy = family_strategy_for(dispatch_family_id)
            if dispatch_family_id == "BENDING_OVERDESIGN_GOVERNS":
                family_ladder_result = dict(
                    family_strategy.contracted_optimisation_ladder_specs(
                        base,
                        evaluate_candidate=build_bending_overdesign_live_evaluator(
                            _evaluate_auto_design_candidate
                        ),
                    )
                    or {}
                )
            elif dispatch_family_id == "SHEAR_OVERDESIGN_GOVERNS":
                family_ladder_result = dict(
                    family_strategy.contracted_optimisation_ladder_specs(
                        base,
                        evaluate_candidate=build_shear_overdesign_live_evaluator(
                            _evaluate_auto_design_candidate
                        ),
                    )
                    or {}
                )
            else:
                family_ladder_result = (
                    _run_incremental_combined_overdesign_ladder(
                        base,
                        family_strategy=family_strategy,
                        evaluate_auto_design_candidate=(
                            _evaluate_auto_design_candidate
                        ),
                        material_proxy=_local_cleanup_material_proxy,
                    )
                )
            family_ladder_rows = list(
                family_ladder_result.get("ladder_trace")
                or family_ladder_result.get("candidate_repairs")
                or family_ladder_result.get("specs")
                or []
            )
            ladder_attempts += len(family_ladder_rows)
            family_selected = dict(
                family_ladder_result.get("selected_recommendation") or {}
            )
            if not family_selected:
                family_specs = [
                    dict(row)
                    for row in list(family_ladder_result.get("specs") or [])
                    if isinstance(row, dict)
                ]
                family_selected = family_specs[0] if family_specs else {}
            accepted_family_rows = [
                dict(row)
                for row in list(
                    family_ladder_result.get("accepted_candidate_evidence")
                    or family_ladder_result.get("candidate_repairs")
                    or []
                )
                if isinstance(row, dict)
                and row.get("accepted") is True
                and dict(row.get("updates") or {})
            ]
            accepted_family_rows.sort(
                key=lambda row: tuple(row.get("rank_key") or ())
            )
            ordered_family_rows: list[dict[str, Any]] = []
            seen_family_updates: set[tuple[tuple[str, str], ...]] = set()
            for row in [family_selected, *accepted_family_rows]:
                family_updates = dict(row.get("updates") or {})
                if not family_updates:
                    continue
                update_signature = tuple(
                    sorted(
                        (str(key), repr(value))
                        for key, value in family_updates.items()
                    )
                )
                if update_signature in seen_family_updates:
                    continue
                seen_family_updates.add(update_signature)
                ordered_family_rows.append(dict(row))
            for family_row in ordered_family_rows:
                family_updates = dict(family_row.get("updates") or {})
                candidate = _evaluate_updates(
                    family_updates,
                    str(
                        family_row.get("label")
                        or f"{dispatch_family_id} contract ladder"
                    ),
                    source_stage=f"family_ladder:{dispatch_family_id}",
                )
                discrete_stop_accepted = (
                    _is_shear_overdesign_discrete_stop_candidate(
                        candidate,
                        selected=family_row,
                        ladder_result=family_ladder_result,
                    )
                )
                combined_terminal_accepted = bool(
                    dispatch_family_id == "COMBINED_OVERDESIGN"
                    and str(
                        family_row.get("terminal_candidate_status") or ""
                    ).strip().upper()
                    in {
                        "TERMINAL_TARGET_BAND",
                        "TERMINAL_EXACT_STOP",
                        "TERMINAL_BLOCKED_WITH_PROOF",
                    }
                    and isinstance(candidate, dict)
                    and candidate.get("is_compliant")
                    and dict(candidate.get("overview") or {}).get(
                        "all_key_pass"
                    )
                    and candidate.get("is_executable")
                    and not candidate.get("advisory_only")
                )
                if (
                    _is_safe_ladder_target(candidate)
                    or discrete_stop_accepted
                    or combined_terminal_accepted
                ):
                    if isinstance(candidate, dict):
                        candidate["family_exact_stop_accepted"] = bool(
                            discrete_stop_accepted
                            or (
                                combined_terminal_accepted
                                and str(
                                    family_row.get(
                                        "terminal_candidate_status"
                                    )
                                    or ""
                                ).strip().upper()
                                != "TERMINAL_TARGET_BAND"
                            )
                        )
                        if discrete_stop_accepted:
                            candidate["family_exact_stop_proof"] = {
                                "category": "discrete_increment_limit",
                                "smallest_safe_width": dict(
                                    family_ladder_result.get(
                                        "geometry_restriction_proof"
                                    )
                                    or {}
                                ).get("smallest_safe_width"),
                                "next_width_step_blocked": True,
                            }
                        elif combined_terminal_accepted:
                            candidate["family_exact_stop_proof"] = {
                                "category": (
                                    "combined_overdesign_terminal_fold"
                                ),
                                "terminal_candidate_status": (
                                    family_row.get(
                                        "terminal_candidate_status"
                                    )
                                ),
                                "terminal_fold": dict(
                                    family_ladder_result.get(
                                        "combined_overdesign_terminal_fold"
                                    )
                                    or {}
                                ),
                            }
                    ladder_candidate = candidate
                    ladder_success = True
                    break
                candidate_overview = dict(
                    (candidate or {}).get("overview") or {}
                )
                if bool(
                    isinstance(candidate, dict)
                    and candidate.get("is_compliant")
                    and candidate_overview.get("all_key_pass")
                    and candidate.get("is_executable")
                    and not candidate.get("advisory_only")
                    and dict(candidate.get("updates") or {})
                    and not (
                        dispatch_family_id == "COMBINED_OVERDESIGN"
                        and str(
                            family_row.get(
                                "terminal_candidate_status"
                            )
                            or ""
                        ).strip().upper()
                        == "NON_TERMINAL_FURTHER_CLEANUP_AVAILABLE"
                    )
                ):
                    # The family runtime has already ranked every
                    # engineering-safe candidate. Generic cleanup materiality
                    # screening may reject its first row (for example, a
                    # geometry reduction that adds more steel). Continue in
                    # that same ranked order and publish the first candidate
                    # that is both a real material reduction and a full
                    # authoritative pass, even when a discrete beam cannot put
                    # every overprovided family inside the preferred band.
                    candidate["family_safe_pass_fallback"] = True
                    ladder_candidate = candidate
                    ladder_success = True
                    if isinstance(debug_sink, dict):
                        debug_sink[
                            "family_safe_pass_fallback_selected"
                        ] = True
                        debug_sink[
                            "family_safe_pass_fallback_candidate_count"
                        ] = 1
                    break
        except Exception as exc:
            family_ladder_result = {
                "family_id": dispatch_family_id,
                "error": type(exc).__name__,
            }
            if isinstance(debug_sink, dict):
                debug_sink["family_ladder_dispatch_error"] = type(exc).__name__
    def _current_state_exact_stop_evidence(
        *,
        source_family_id: str,
        source: str,
        proof: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        exact_stop_proof = {
            **dict(proof or {}),
            "terminal_candidate_status": "TERMINAL_EXACT_STOP",
            "current_state_terminal_exact_stop": True,
            "no_progressing_family_owned_candidate": True,
            "source_family_id": source_family_id,
        }
        return {
            "source": source,
            "family_ladder_terminal_exact_stop": True,
            "exact_stop_proven": True,
            "exact_stop_proof": exact_stop_proof,
            "family_ladder_runtime_result": dict(family_ladder_result),
            "source_family_id": source_family_id,
            "family": "EXACT_STOP_PROVEN",
            "family_id": "EXACT_STOP_PROVEN",
            "selected_family": "EXACT_STOP_PROVEN",
            "selected_family_id": "EXACT_STOP_PROVEN",
            "published_family_id": "EXACT_STOP_PROVEN",
            "cta_family_id": "EXACT_STOP_PROVEN",
            "apply_payload_family_id": "EXACT_STOP_PROVEN",
            "candidate_family_id": "EXACT_STOP_PROVEN",
            "card_family_id": "EXACT_STOP_PROVEN",
            "matched_family_ids": ["EXACT_STOP_PROVEN"],
            "family_match_passed": True,
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "family_ladder_exhausted": False,
            "no_second_cta_required": True,
            "legacy_fallback_allowed": False,
            "generic_optimisation_cleanup_skipped": True,
            "generic_publication_fallback_skipped": True,
            "family_early_dispatch_used": True,
        }

    combined_terminal_fold = dict(
        family_ladder_result.get("combined_overdesign_terminal_fold") or {}
    )
    combined_current_state_exact_stop = bool(
        not ladder_success
        and dispatch_family_id == "COMBINED_OVERDESIGN"
        and combined_terminal_fold.get("terminal_reached") is True
        and str(
            combined_terminal_fold.get("terminal_candidate_status") or ""
        ).strip().upper()
        == "TERMINAL_EXACT_STOP"
        and combined_terminal_fold.get("current_state_terminal_exact_stop")
        is True
        and not dict(combined_terminal_fold.get("cumulative_updates") or {})
    )
    if combined_current_state_exact_stop:
        terminal_evidence = _current_state_exact_stop_evidence(
            source_family_id="COMBINED_OVERDESIGN",
            source="combined_overdesign_family_ladder_terminal_fold",
            proof=dict(family_ladder_result.get("exact_stop_proof") or {}),
        )
        if isinstance(debug_sink, dict):
            debug_sink.update(terminal_evidence)
            debug_sink["family_ladder_runtime_selected"] = False
            debug_sink[
                "combined_overdesign_current_state_exact_stop"
            ] = True
        return terminal_evidence
    if (
        not ladder_success
        and dispatch_decision.get("should_run_family_ladder")
        and (active_failure_keys or material_family_set)
    ):
        full_truth_passing_candidates = [
            candidate
            for candidate in candidates
            if bool(candidate.get("is_compliant"))
            and bool((candidate.get("overview") or {}).get("all_key_pass"))
            and bool(dict(candidate.get("updates") or {}))
        ]
        safe_passing_candidates = [
            candidate
            for candidate in full_truth_passing_candidates
            if bool(candidate.get("is_executable"))
            and not bool(candidate.get("advisory_only"))
        ]
        if isinstance(debug_sink, dict):
            debug_sink["family_full_truth_passing_candidate_count"] = len(
                full_truth_passing_candidates
            )
            debug_sink["family_full_truth_passing_executor_rejections"] = [
                {
                    "label": candidate.get("label"),
                    "executor_actionability_reason": candidate.get(
                        "executor_actionability_reason"
                    ),
                    "advisory_only": bool(candidate.get("advisory_only")),
                }
                for candidate in full_truth_passing_candidates
                if not bool(candidate.get("is_executable"))
                or bool(candidate.get("advisory_only"))
            ][:8]
        if safe_passing_candidates:
            ladder_candidate = min(
                safe_passing_candidates,
                key=lambda candidate: (
                    _distance_to_target_band(
                        float(
                            candidate.get("candidate_post_util")
                            or candidate.get("worst_util")
                            or 0.0
                        ),
                        float(t_lo),
                        float(t_hi),
                    ),
                    len(dict(candidate.get("updates") or {})),
                    str(candidate.get("label") or ""),
                ),
            )
            ladder_candidate["family_safe_pass_fallback"] = True
            ladder_success = True
            if isinstance(debug_sink, dict):
                debug_sink["family_safe_pass_fallback_selected"] = True
                debug_sink["family_safe_pass_fallback_candidate_count"] = len(
                    safe_passing_candidates
                )
    current_state_overdesign_exact_stop = bool(
        not ladder_success
        and not strengthening
        and dispatch_family_id
        in {
            "BENDING_OVERDESIGN_GOVERNS",
            "SHEAR_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
        }
        and dispatch_decision.get("should_run_family_ladder")
        and not dispatch_decision.get("legacy_fallback_allowed")
        and bool((overview or {}).get("all_key_pass"))
        and not bool((overview or {}).get("any_fail"))
        and bool(family_ladder_rows)
        and not family_ladder_result.get("error")
        and not safe_passing_candidates
    )
    if current_state_overdesign_exact_stop:
        terminal_evidence = _current_state_exact_stop_evidence(
            source_family_id=dispatch_family_id,
            source="overdesign_family_ladder_current_state_exact_stop",
            proof={
                "family_ladder_attempts": int(ladder_attempts),
                "family_ladder_candidate_count": len(family_ladder_rows),
                "full_truth_passing_candidate_count": len(
                    full_truth_passing_candidates
                ),
                "safe_executable_candidate_count": 0,
                "current_state_all_key_pass": True,
            },
        )
        if isinstance(debug_sink, dict):
            debug_sink.update(terminal_evidence)
            debug_sink["family_ladder_runtime_selected"] = False
            debug_sink["overdesign_current_state_exact_stop"] = True
        return terminal_evidence
    project_geometry_limit = dict(
        family_ladder_result.get("project_geometry_limit_mm") or {}
    )
    project_depth_limit = float(
        project_geometry_limit.get("depth") or 0.0
    )
    project_width_limit = float(
        project_geometry_limit.get("width") or 0.0
    )
    evaluated_depths = [
        float(dict(spec.get("updates") or {}).get("D") or 0.0)
        for spec in active_strength_specs
        if dict(spec.get("updates") or {}).get("D") is not None
    ]
    evaluated_widths = [
        float(
            dict(spec.get("updates") or {}).get("b")
            or dict(spec.get("updates") or {}).get("bw")
            or 0.0
        )
        for spec in active_strength_specs
        if (
            dict(spec.get("updates") or {}).get("b") is not None
            or dict(spec.get("updates") or {}).get("bw") is not None
        )
    ]
    canonical_project_geometry_exhausted = bool(
        dispatch_family_id
        in {
            "BENDING_FAIL_GOVERNS",
            "SHEAR_FAIL_GOVERNS",
            "COMBINED_BENDING_SHEAR_FAIL",
        }
        and project_depth_limit == PROJECT_MAX_BEAM_DEPTH_MM
        and project_width_limit == PROJECT_MAX_BEAM_WIDTH_MM
        and active_strength_specs
        and ladder_attempts >= len(active_strength_specs)
        and max(evaluated_depths, default=0.0)
        >= project_depth_limit - 1e-9
        and max(evaluated_widths, default=0.0)
        >= project_width_limit - 1e-9
    )
    if (
        not ladder_success
        and strengthening
        and active_failure_keys
        and not geometry_locked
        and not dispatch_decision.get("legacy_fallback_allowed")
        and not canonical_project_geometry_exhausted
    ):
        # An implementation limit is not an engineering blocker.  Unlocked
        # under-design must never be converted into a visible blocked card.
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "unlocked_underdesign_ladder_failed_to_repair": True,
                    "family_ladder_exhaustion_not_publishable": True,
                    "geometry_locked": False,
                    "family_ladder_runtime_result": dict(family_ladder_result),
                }
            )
        return None
    if (
        not ladder_success
        and not dispatch_decision.get("legacy_fallback_allowed")
    ):
        runtime_trace = list(
            family_ladder_candidate_trace
            or family_ladder_result.get("candidate_trace")
            or family_ladder_result.get("combined_merge_trace")
            or family_ladder_result.get("mixed_merge_trace")
            or family_ladder_result.get("candidate_repairs")
            or []
        )
        family_ladder_result["candidate_trace"] = list(runtime_trace)
        runtime_selected = dict(
            family_ladder_result.get("selected_recommendation") or {}
        )
        runtime_accepted = [
            dict(row)
            for row in list(
                family_ladder_result.get("accepted_candidate_evidence")
                or family_ladder_result.get("candidate_repairs")
                or []
            )
            if isinstance(row, dict) and row.get("accepted") is True
        ]
        runtime_rejected = [
            dict(row)
            for row in list(
                family_ladder_result.get("rejected_candidate_evidence")
                or []
            )
            if isinstance(row, dict)
        ]
        representative_rejected = (
            min(
                runtime_rejected,
                key=lambda row: tuple(row.get("rank_key") or ()),
            )
            if runtime_rejected
            and all(isinstance(row.get("rank_key"), (list, tuple)) for row in runtime_rejected)
            else (runtime_rejected[0] if runtime_rejected else {})
        )
        full_truth_attempts = [
            dict(candidate)
            for candidate in candidates
            if isinstance(candidate, dict)
            and dict(candidate.get("updates") or {})
        ]

        def _full_truth_attempt_rank(candidate: dict[str, Any]) -> tuple:
            candidate_overview = dict(candidate.get("overview") or {})
            candidate_utils = dict(candidate_overview.get("utils") or {})
            failing_utils: list[float] = []
            for family, status in dict(
                candidate_overview.get("statuses") or {}
            ).items():
                if str(status or "").strip().upper() == "PASS":
                    continue
                try:
                    failing_utils.append(float(candidate_utils.get(family)))
                except (TypeError, ValueError):
                    continue
            try:
                worst_util = float(
                    max(failing_utils)
                    if failing_utils
                    else candidate.get("candidate_post_util")
                    or candidate_overview.get("worst_util")
                    or float("inf")
                )
            except (TypeError, ValueError):
                worst_util = float("inf")
            return (
                not bool(candidate_overview.get("all_key_pass")),
                not bool(candidate.get("is_compliant")),
                worst_util,
                not bool(candidate.get("is_executable")),
                len(dict(candidate.get("updates") or {})),
                str(
                    candidate.get("family_ladder_candidate_id")
                    or candidate.get("candidate_id")
                    or candidate.get("label")
                    or ""
                ),
            )

        if strengthening and active_failure_keys and full_truth_attempts:
            # The family strategy result can contain contract-level ranking
            # metadata whose utilisation values are not the authoritative
            # full candidate evaluation.  A blocked underdesign card must be
            # explained only by the same full-truth candidates that were
            # actually screened above.
            attempted_candidate = min(
                full_truth_attempts,
                key=_full_truth_attempt_rank,
            )
        else:
            attempted_candidate = dict(
                runtime_selected or representative_rejected
            )
        attempted_evaluation = dict(
            attempted_candidate.get("evaluation") or attempted_candidate
        )
        selected_updates = dict(attempted_candidate.get("updates") or {})
        selected_candidate_id = str(
            attempted_candidate.get("family_ladder_candidate_id")
            or attempted_candidate.get("candidate_id")
            or f"{dispatch_family_id}:family_ladder_exhausted"
        )
        current_utils = dict((overview or {}).get("utils") or {})
        actions_used = dict((overview or {}).get("actions_used") or {})

        def _display_number(value: Any) -> str:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return str(value or "").strip() or "recorded"
            if abs(number - round(number)) <= 1e-9:
                return str(int(round(number)))
            return f"{number:.2f}".rstrip("0").rstrip(".")

        def _bottom_label(source: dict[str, Any]) -> str:
            count_1 = int(float(source.get("bot1_count") or 0))
            dia_1 = int(float(source.get("db_bot_1") or 0))
            count_2 = int(float(source.get("bot2_count") or 0))
            dia_2 = int(float(source.get("db_bot_2") or dia_1 or 0))
            rows = []
            if count_1 > 0 and dia_1 > 0:
                rows.append(f"{count_1}N{dia_1}")
            if count_2 > 0 and dia_2 > 0:
                rows.append(f"{count_2}N{dia_2}")
            return " + ".join(rows) or "recorded bottom reinforcement"

        def _link_label(source: dict[str, Any]) -> str:
            legs = int(float(source.get("lig_legs") or 0))
            dia = int(float(source.get("lig_d") or 0))
            spacing = float(source.get("s_lig") or 0)
            if legs <= 0 or dia <= 0 or spacing <= 0:
                return "no links"
            return (
                f"{legs}-leg N{dia} @ "
                f"{_display_number(spacing)} mm"
            )

        attempted_state = dict(base)
        attempted_state.update(selected_updates)
        attempted_change_parts: list[str] = []
        if "D" in selected_updates and selected_updates.get("D") != base.get("D"):
            attempted_change_parts.append(
                "depth from "
                f"{_display_number(base.get('D'))} mm to "
                f"{_display_number(selected_updates.get('D'))} mm"
            )
        if width_key in selected_updates and selected_updates.get(width_key) != base.get(width_key):
            attempted_change_parts.append(
                "width from "
                f"{_display_number(base.get(width_key))} mm to "
                f"{_display_number(selected_updates.get(width_key))} mm"
            )
        if set(selected_updates) & {
            "bot1_count",
            "bot2_count",
            "db_bot_1",
            "db_bot_2",
            "bot_row_1_bars",
            "bot_row_1_dia",
            "bot_row_2_bars",
            "bot_row_2_dia",
        }:
            attempted_change_parts.append(
                "bottom reinforcement from "
                f"{_bottom_label(base)} to {_bottom_label(attempted_state)}"
            )
        if set(selected_updates) & {"lig_legs", "lig_d", "s_lig"}:
            attempted_change_parts.append(
                "shear links from "
                f"{_link_label(base)} to {_link_label(attempted_state)}"
            )
        attempted_change_label = (
            "changing " + ", ".join(attempted_change_parts)
            if attempted_change_parts
            else "the recorded family-ladder cleanup change"
        )
        attempted_overview = dict(
            attempted_candidate.get("overview") or {}
        )
        attempted_overview_utils = dict(
            attempted_overview.get("utils") or {}
        )
        attempted_overview_statuses = dict(
            attempted_overview.get("statuses") or {}
        )
        selected_bending_util = (
            attempted_overview_utils.get("bending")
            if strengthening and active_failure_keys
            else attempted_evaluation.get("bending_utilisation_after")
        )
        selected_shear_util = (
            attempted_overview_utils.get("shear")
            if strengthening and active_failure_keys
            else attempted_evaluation.get("shear_utilisation_after")
        )
        attempted_family_utils = {
            "bending": selected_bending_util,
            "shear": selected_shear_util,
        }
        below_floor = [
            family
            for family, value in attempted_family_utils.items()
            if value is not None
            and float(value) < float(_final_accepted_min_family_util)
        ]
        over_capacity = [
            family
            for family, value in attempted_family_utils.items()
            if value is not None and float(value) > 1.0
        ]
        attempted_passed = (
            bool(
                attempted_candidate.get("is_compliant")
                and attempted_overview.get("all_key_pass")
            )
            if strengthening and active_failure_keys
            else bool(
                attempted_candidate.get("accepted") is True
                or (
                    attempted_evaluation.get("candidate_valid") is True
                    and not over_capacity
                )
            )
        )
        rejection_reasons = [
            str(reason).strip()
            for reason in list(
                attempted_candidate.get("rejection_reasons") or []
            )
            if str(reason).strip()
        ]
        full_truth_failed_families = [
            str(family).strip().lower()
            for family, status in attempted_overview_statuses.items()
            if str(status or "").strip().upper() != "PASS"
        ]
        if strengthening and active_failure_keys and full_truth_failed_families:
            limiting_family = max(
                full_truth_failed_families,
                key=lambda family: float(
                    attempted_overview_utils.get(family) or 0.0
                ),
            )
            limiting_util = attempted_overview_utils.get(limiting_family)
            failed_check_name = f"{limiting_family} design check"
            failed_check_limit = 1.0
            rejection_category = (
                rejection_reasons[0]
                if rejection_reasons
                else f"{limiting_family} remained above its design limit"
            )
        elif over_capacity:
            limiting_family = max(
                over_capacity,
                key=lambda family: float(attempted_family_utils[family]),
            )
            failed_check_name = f"{limiting_family} capacity limit"
            failed_check_limit = 1.0
            rejection_category = (
                rejection_reasons[0]
                if rejection_reasons
                else f"{limiting_family} remained above capacity"
            )
        else:
            limiting_family = (
                min(
                    (
                        (family, float(value))
                        for family, value in attempted_family_utils.items()
                        if value is not None
                    ),
                    key=lambda pair: pair[1],
                )[0]
                if any(
                    value is not None
                    for value in attempted_family_utils.values()
                )
                else "combined"
            )
            failed_check_name = "accepted cleanup floor"
            failed_check_limit = float(_final_accepted_min_family_util)
            rejection_category = (
                "Safe but still below accepted efficiency floor"
                if below_floor
                else (
                    rejection_reasons[0]
                    if rejection_reasons
                    else "No better preferred-band candidate"
                )
            )
        if not (
            strengthening
            and active_failure_keys
            and full_truth_failed_families
        ):
            limiting_util = attempted_family_utils.get(limiting_family)
        current_state_sentence = (
            "Bending utilisation is currently "
            f"{_display_number(current_utils.get('bending'))} and shear "
            "utilisation is currently "
            f"{_display_number(current_utils.get('shear'))}."
        )
        attempted_result_sentence = (
            (
                "The attempted design passed all required checks, but was "
                f"rejected as {rejection_category}"
            )
            if attempted_passed
            else (
                f"The attempted design was rejected because "
                f"{rejection_category}"
            )
        ) + (
            f": {limiting_family} utilisation became "
            f"{_display_number(limiting_util)} against "
            f"{failed_check_name} {_display_number(failed_check_limit)}."
        )
        detailed_blocker_reason = (
            f"{current_state_sentence} We tried {attempted_change_label}. "
            f"{attempted_result_sentence} Keeping the current section and "
            "reinforcement arrangement."
        )
        family_flags = {
            "bending_fail": dispatch_family_id
            in {
                "BENDING_FAIL_GOVERNS",
                "COMBINED_BENDING_SHEAR_FAIL",
                "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            },
            "shear_fail": dispatch_family_id
            in {
                "SHEAR_FAIL_GOVERNS",
                "COMBINED_BENDING_SHEAR_FAIL",
                "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            },
            "bending_overdesigned": (
                dispatch_family_id
                in {
                    "BENDING_OVERDESIGN_GOVERNS",
                    "COMBINED_OVERDESIGN",
                    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
                }
            ),
            "shear_overdesigned": (
                dispatch_family_id
                in {
                    "SHEAR_OVERDESIGN_GOVERNS",
                    "COMBINED_OVERDESIGN",
                    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
                }
            ),
        }
        classification = classify_family_from_raw_flags(
            family_flags,
            evidence={
                "source": "design_guide_family_ladder_exhaustion",
                "family_ladder_attempts": int(ladder_attempts),
                "legacy_fallback_allowed": False,
            },
        )
        blocker_families = []
        if family_flags["bending_fail"]:
            blocker_families.append("bending")
        if family_flags["shear_fail"]:
            blocker_families.append("shear")
        if family_flags["bending_overdesigned"] and "bending" not in blocker_families:
            blocker_families.append("bending")
        if family_flags["shear_overdesigned"] and "shear" not in blocker_families:
            blocker_families.append("shear")
        blocker_reason = (
            (
                "Geometry is locked. The Design Guide tried all "
                f"{int(ladder_attempts)} legal reinforcement and link "
                "strengthening steps, but none made every required check "
                "pass. Unlock geometry to continue through depth and width "
                "increases."
            )
            if strengthening and active_failure_keys and geometry_locked
            else (
                "No safe one-click change was found after the Design Guide "
                f"checked all {int(ladder_attempts)} legal steps for the "
                "current constraints."
            )
        )
        full_truth_safe_candidates = [
            candidate
            for candidate in full_truth_attempts
            if bool(candidate.get("is_compliant"))
            and bool(
                dict(candidate.get("overview") or {}).get("all_key_pass")
            )
        ]
        full_truth_safe_executor_candidates = [
            candidate
            for candidate in full_truth_safe_candidates
            if bool(candidate.get("is_executable"))
            and not bool(candidate.get("advisory_only"))
        ]
        full_truth_executable_candidates = [
            candidate
            for candidate in full_truth_attempts
            if bool(candidate.get("is_executable"))
            and not bool(candidate.get("advisory_only"))
        ]
        if strengthening and active_failure_keys:
            safe_candidate_count = len(full_truth_safe_candidates)
            safe_executor_candidate_count = len(
                full_truth_safe_executor_candidates
            )
            executable_candidate_count = len(
                full_truth_executable_candidates
            )
            rejected_candidate_count = max(
                0,
                len(full_truth_attempts) - len(full_truth_safe_candidates),
            )
        else:
            safe_candidate_count = len(runtime_accepted)
            safe_executor_candidate_count = len(runtime_accepted)
            executable_candidate_count = len(runtime_accepted)
            rejected_candidate_count = len(runtime_rejected)
        attempted_update_sets = [
            set(dict(row.get("updates") or {}))
            for row in full_truth_attempts
        ]
        geometry_update_keys = {"D", width_key}
        bottom_reo_update_keys = {
            "bot1_count",
            "bot2_count",
            "db_bot_1",
            "db_bot_2",
            "bot_row_1_bars",
            "bot_row_1_dia",
            "bot_row_2_bars",
            "bot_row_2_dia",
            "bot_row_count",
        }
        shear_update_keys = {"lig_legs", "lig_d", "s_lig"}
        geometry_strengthening_searched = any(
            keys & geometry_update_keys for keys in attempted_update_sets
        )
        reo_strengthening_searched = any(
            keys & bottom_reo_update_keys for keys in attempted_update_sets
        )
        shear_strengthening_searched = any(
            keys & shear_update_keys for keys in attempted_update_sets
        )
        combined_strengthening_searched = any(
            keys & bottom_reo_update_keys
            and keys & shear_update_keys
            for keys in attempted_update_sets
        )
        rejected_repair_reasons = list(
            dict.fromkeys(
                [
                    str(rejection_category),
                    *[
                        (
                            f"{family} remained "
                            f"{str(attempted_overview_statuses.get(family) or 'unresolved').lower()}"
                        )
                        for family in full_truth_failed_families
                    ],
                ]
            )
        )
        active_repair_route_inventory = {
            "geometry": {
                "searched": bool(geometry_strengthening_searched),
                "locked": bool(geometry_locked),
            },
            "bottom reo": {
                "searched": bool(reo_strengthening_searched),
            },
            "links": {
                "searched": bool(shear_strengthening_searched),
            },
            "combined": {
                "searched": bool(combined_strengthening_searched),
            },
        }

        def _family_specific_blocker_reason(family: str) -> str:
            current_util = current_utils.get(family)
            attempted_util = attempted_family_utils.get(family)
            attempted_status = str(
                attempted_overview_statuses.get(family) or "unresolved"
            ).strip().upper()
            if attempted_status == "PASS":
                family_result = (
                    f"the best combined attempt repaired {family} to "
                    f"{_display_number(attempted_util)} PASS"
                )
            else:
                family_result = (
                    f"the best combined attempt left {family} at "
                    f"{_display_number(attempted_util)} "
                    f"{attempted_status or 'UNRESOLVED'}"
                )
            limiting_result = (
                f"{limiting_family} remained at "
                f"{_display_number(limiting_util)} against "
                f"{failed_check_name} "
                f"{_display_number(failed_check_limit)}"
            )
            lock_result = (
                " Geometry is locked, so the ladder could not continue "
                "through depth or width increases."
                if geometry_locked
                else ""
            )
            return (
                f"{family.title()} started at "
                f"{_display_number(current_util)}. We tried "
                f"{attempted_change_label}; {family_result}, but "
                f"{limiting_result}.{lock_result}"
            )

        canonical_geometry_blocker_reason = (
            "Project maximum beam depth and width reached at 5000 mm after "
            "the complete unlocked family ladder."
        )
        exact_blockers = {
            family: {
                "family": family,
                "reason": (
                    canonical_geometry_blocker_reason
                    if canonical_project_geometry_exhausted
                    else _family_specific_blocker_reason(family)
                ),
                "family_specific_reason": (
                    canonical_geometry_blocker_reason
                    if canonical_project_geometry_exhausted
                    else _family_specific_blocker_reason(family)
                ),
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "attempted_candidate_count": int(ladder_attempts),
                "safe_candidate_count": int(safe_candidate_count),
                "safe_repair_candidate_count": int(
                    safe_candidate_count
                ),
                "safe_executor_backed_candidates_count": int(
                    safe_executor_candidate_count
                ),
                "executable_candidate_count": int(
                    executable_candidate_count
                ),
                "executable_repair_candidate_count": int(
                    executable_candidate_count
                ),
                "target_band_candidate_count": 0,
                "no_second_cta_required": True,
                "best_safe_candidate_applied": False,
                "exact_stop_proven": True,
                "family_ladder_exhausted": True,
                "geometry_locked": bool(geometry_locked),
                "canonical_project_geometry_exhausted": bool(
                    canonical_project_geometry_exhausted
                ),
                "project_geometry_limit_mm": dict(
                    project_geometry_limit
                ),
                "geometry_strengthening_searched": bool(
                    geometry_strengthening_searched
                ),
                "reo_strengthening_searched": bool(
                    reo_strengthening_searched
                ),
                "longitudinal_reinforcement_strengthening_searched": bool(
                    reo_strengthening_searched
                ),
                "shear_strengthening_searched": bool(
                    shear_strengthening_searched
                ),
                "combined_strengthening_searched": bool(
                    combined_strengthening_searched
                ),
                "active_repair_route_inventory": dict(
                    active_repair_route_inventory
                ),
                "rejected_repair_reasons": list(
                    rejected_repair_reasons
                ),
                "failed_candidate_id": selected_candidate_id,
                "best_rejected_candidate_id": selected_candidate_id,
                "failed_check_name": failed_check_name,
                "failed_check_status": (
                    "PASS_BUT_REJECTED"
                    if attempted_passed
                    else "REJECTED"
                ),
                "failed_check_util": attempted_family_utils.get(family),
                "failed_check_demand": (
                    actions_used.get("Mu")
                    if family == "bending"
                    else actions_used.get("Vu")
                ),
                "failed_check_capacity_or_limit": failed_check_limit,
                "current_util": current_utils.get(family),
                "attempted_util": attempted_family_utils.get(family),
                "attempted_passed": attempted_passed,
                "attempted_updates": dict(selected_updates),
                "attempted_change_label": attempted_change_label,
                "current_arrangement_label": (
                    "current section and reinforcement arrangement"
                ),
                "retained_arrangement_label": (
                    "current section and reinforcement arrangement"
                ),
                "rejection_category": rejection_category,
                "runtime_rejected_candidate_count": int(
                    rejected_candidate_count
                ),
                "candidate_trace": list(
                    runtime_trace
                ),
            }
            for family in blocker_families
        }
        blocker_attempts = dict(exact_blockers)
        if (
            dispatch_family_id == "COMBINED_BENDING_SHEAR_FAIL"
            and {"bending", "shear"}.issubset(set(blocker_families))
        ):
            blocker_attempts["combined"] = {
                "family": "combined",
                "reason": detailed_blocker_reason,
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "attempted_candidate_count": int(ladder_attempts),
                "safe_repair_candidate_count": int(
                    safe_candidate_count
                ),
                "executable_repair_candidate_count": int(
                    executable_candidate_count
                ),
                "best_rejected_candidate_id": selected_candidate_id,
                "failed_candidate_id": selected_candidate_id,
                "failed_check_name": failed_check_name,
                "failed_check_status": (
                    "PASS_BUT_REJECTED"
                    if attempted_passed
                    else "REJECTED"
                ),
                "failed_check_util": limiting_util,
                "failed_check_capacity_or_limit": failed_check_limit,
                "attempted_updates": dict(selected_updates),
                "active_repair_route_inventory": dict(
                    active_repair_route_inventory
                ),
                "geometry_locked": bool(geometry_locked),
                "geometry_strengthening_searched": bool(
                    geometry_strengthening_searched
                ),
                "reo_strengthening_searched": bool(
                    reo_strengthening_searched
                ),
                "shear_strengthening_searched": bool(
                    shear_strengthening_searched
                ),
                "combined_strengthening_searched": bool(
                    combined_strengthening_searched
                ),
                "rejected_repair_reasons": list(
                    rejected_repair_reasons
                ),
                "candidate_trace": list(runtime_trace),
            }
        exhaustion_evidence = {
            **classification,
            "source": "design_guide_family_ladder_exhaustion",
            "family_ladder_exhausted": True,
            "family_ladder_attempts": int(ladder_attempts),
            "family_ladder_candidate_count": int(ladder_attempts),
            "family_ladder_runtime_result": dict(family_ladder_result),
            "family_ladder_candidate_trace": list(
                family_ladder_candidate_trace
            ),
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "safe_candidate_count": int(safe_candidate_count),
            "safe_repair_candidate_count": int(safe_candidate_count),
            "safe_executor_backed_candidates_count": int(
                safe_executor_candidate_count
            ),
            "executable_candidate_count": int(
                executable_candidate_count
            ),
            "executable_repair_candidate_count": int(
                executable_candidate_count
            ),
            "target_band_candidate_count": 0,
            "no_second_cta_required": True,
            "geometry_locked": bool(geometry_locked),
            "geometry_strengthening_searched": bool(
                geometry_strengthening_searched
            ),
            "reo_strengthening_searched": bool(
                reo_strengthening_searched
            ),
            "shear_strengthening_searched": bool(
                shear_strengthening_searched
            ),
            "combined_strengthening_searched": bool(
                combined_strengthening_searched
            ),
            "active_repair_route_inventory": dict(
                active_repair_route_inventory
            ),
            "rejected_repair_reasons": list(
                rejected_repair_reasons
            ),
            "blocker_attempts_by_family": dict(blocker_attempts),
            "exact_blockers_by_family": dict(exact_blockers),
            "post_click_exact_blockers_by_family": dict(exact_blockers),
            "blocking_reason": blocker_reason,
            "legacy_fallback_allowed": False,
            "generic_one_click_solver_skipped": True,
            "generic_target_band_search_skipped": True,
            "generic_optimisation_cleanup_skipped": True,
            "generic_publication_fallback_skipped": True,
            "family_early_dispatch_used": True,
            "direct_target_band_bypassed_by_family_owner": True,
        }
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "direct_target_band_search_used": False,
                    "direct_target_band_ladder_success": False,
                    "direct_target_band_ladder_attempts": int(ladder_attempts),
                    "family_ladder_runtime_result": dict(family_ladder_result),
                    "family_ladder_runtime_selected": False,
                    "family_ladder_exhausted_without_legacy_fallback": True,
                }
            )
            debug_sink.update(exhaustion_evidence)
        return exhaustion_evidence

    if not candidates:
        if isinstance(debug_sink, dict):
            debug_sink["direct_target_band_search_used"] = False
            debug_sink["direct_target_band_search_candidate_count"] = 0
            debug_sink["direct_target_band_ladder_success"] = False
            debug_sink["direct_target_band_ladder_attempts"] = int(
                ladder_attempts
            )
            debug_sink["local_cleanup_candidate_search_evidence"] = _build_candidate_search_evidence(
                selected_candidate=None,
                all_candidates=[],
                target_low=float(t_lo),
                target_high=float(t_hi),
                exhaustive=False,
                search_scope="design_guide_family_ladder",
                selected_title=None,
            )
        return None
    safe = [c for c in candidates if bool(c.get("is_compliant")) and bool((c.get("overview") or {}).get("all_key_pass"))]
    if not safe:
        evidence = _build_candidate_search_evidence(
            selected_candidate=None,
            all_candidates=candidates,
            target_low=float(t_lo),
            target_high=float(t_hi),
            exhaustive=True,
            search_scope="design_guide_direct_target_band_search",
            selected_title=None,
        )
        if isinstance(debug_sink, dict):
            debug_sink["direct_target_band_search_used"] = True
            debug_sink["direct_target_band_search_candidate_count"] = len(candidates)
            debug_sink["candidate_search_evidence"] = dict(evidence)
            debug_sink["local_cleanup_candidate_search_evidence"] = dict(evidence)
        return None
    target = [
        c for c in safe
        if c.get("candidate_post_util") is not None
        and float(t_lo) <= float(c.get("candidate_post_util")) <= float(t_hi)
    ]
    current_material_family_set = set(material_family_set)

    def _direct_candidate_final_cleanup_key(c: dict) -> tuple:
        updates = dict(c.get("updates") or {})
        overview_after = dict(c.get("overview") or {})
        final_audit = dict(c.get("final_acceptance_audit") or {})
        final_valid = bool(
            c.get("final_accepted_green_valid")
            or final_audit.get("post_click_accepted_green_valid")
        )
        unresolved_low = list(
            c.get("final_unresolved_low_util_families")
            or final_audit.get("post_click_unresolved_low_util_families")
            or []
        )
        below_threshold = list(
            c.get("final_families_below_threshold")
            or final_audit.get("post_click_families_below_final_threshold")
            or []
        )
        if overview_after:
            _, remaining_families, _ = identify_materially_overprovided_non_governing_families(overview_after)
            remaining_count = len(remaining_families)
        else:
            remaining_count = 99
        affected_current = {
            family
            for family in current_material_family_set
            if _local_cleanup_candidate_affects_family(family, updates)
        }
        missing_current_count = len(current_material_family_set - affected_current) if current_material_family_set else 0
        try:
            material_delta = float(c.get("material_proxy_delta") or 0.0)
        except Exception:
            material_delta = 0.0
        return (
            0 if final_valid else 1,
            len(unresolved_low),
            len(below_threshold),
            remaining_count,
            missing_current_count,
            len(dict(c.get("updates") or {})),
            material_delta,
            str(c.get("label") or ""),
        )

    def _refresh_candidate_full_acceptance_audit(c: dict) -> None:
        if not isinstance(c, dict):
            return
        trial_state = dict(base)
        trial_state.update(dict(c.get("updates") or {}))
        final_audit = _post_click_accepted_green_audit(
            dict(c.get("overview") or {}),
            blocker_source=dict(c),
            state=trial_state,
            build_active_shear_blocker=True,
        )
        c["final_acceptance_audit"] = dict(final_audit)
        c["final_accepted_green_valid"] = bool(final_audit.get("post_click_accepted_green_valid"))
        c["final_unresolved_low_util_families"] = list(
            final_audit.get("post_click_unresolved_low_util_families") or []
        )
        c["final_families_below_threshold"] = list(
            final_audit.get("post_click_families_below_final_threshold") or []
        )

    if defer_active_shear_blocker:
        shortlist_pool = list(target or safe)
        shortlist = sorted(
            shortlist_pool,
            key=lambda c: (
                _direct_candidate_final_cleanup_key(c),
                _distance_to_target_band(
                    float(c.get("candidate_post_util") or c.get("worst_util") or 0.0),
                    t_lo,
                    t_hi,
                ),
            ),
        )[:deferred_full_audit_top_n]
        for candidate in shortlist:
            _refresh_candidate_full_acceptance_audit(candidate)

    family_ladder_required = bool(
        dispatch_decision.get("should_run_family_ladder")
    )
    if ladder_success and isinstance(ladder_candidate, dict):
        # The selected family owns both candidate order and its stop.  Do not
        # replace that winner with a later generic minimum: doing so discards
        # family proof such as safe-pass fallback intent and can make the
        # visible copy contradict an enabled executor action.
        if not ladder_candidate.get("candidate_contract_approved"):
            raise RuntimeError(
                "family ladder winner did not originate from approved family contract"
            )
        selected = ladder_candidate
    elif family_ladder_required:
        # A family-owned ladder is the only authority allowed to emit an
        # actionable finalist.  ``target``/``safe`` below are legacy search
        # projections and may still contain a plausible-looking row when the
        # contracted ladder exhausted or errored.  Publishing that row would
        # make the live pipeline reject it later (or, worse, allow a family
        # mismatch).  Keep the evidence for the blocker, but expose no
        # updates so every family has the same fail-closed structure.
        selected = {
            "label": "No approved family candidate available",
            "updates": {},
            "candidate_contract_approved": False,
            "candidate_source_stage": "family_ladder:exhausted",
            "family": dispatch_family_id,
            "family_id": dispatch_family_id,
        }
    elif target:
        target_mid = (float(t_lo) + float(t_hi)) / 2.0
        selected = min(
            target,
            key=lambda c: (
                _direct_candidate_final_cleanup_key(c),
                abs(float(c.get("candidate_post_util") or 0.0) - target_mid),
            ),
        )
    else:
        selected = min(
            safe,
            key=lambda c: (
                _direct_candidate_final_cleanup_key(c),
                _distance_to_target_band(float(c.get("candidate_post_util") or c.get("worst_util") or 0.0), t_lo, t_hi),
            ),
        )
    if defer_active_shear_blocker:
        _refresh_candidate_full_acceptance_audit(selected)
    evidence = _build_candidate_search_evidence(
        selected_candidate=selected,
        all_candidates=candidates,
        target_low=float(t_lo),
        target_high=float(t_hi),
        exhaustive=not ladder_success,
        search_scope=(
            "design_guide_family_ladder"
            if ladder_success
            else "design_guide_family_ladder_exhausted"
        ),
        selected_title=str(selected.get("label") or ""),
    )
    evidence["ladder_success"] = bool(ladder_success)
    evidence["ladder_attempts"] = int(ladder_attempts)
    evidence["candidate_source_stage"] = str(
        selected.get("candidate_source_stage") or "family_ladder"
    )
    evidence["candidate_contract_id"] = selected.get("candidate_contract_id")
    evidence["candidate_generation_policy_id"] = selected.get(
        "candidate_generation_policy_id"
    )
    evidence["candidate_evaluation_policy_id"] = selected.get(
        "candidate_evaluation_policy_id"
    )
    evidence["candidate_selection_policy_id"] = selected.get(
        "candidate_selection_policy_id"
    )
    evidence["candidate_contract_approved"] = bool(
        selected.get("candidate_contract_approved")
    )
    if bool(selected.get("family_exact_stop_accepted")):
        evidence["candidate_search_exhaustive"] = True
        evidence["outside_target_band_allowed"] = True
        evidence["outside_target_band_allowed_category"] = (
            "discrete_increment_limit"
        )
        evidence["outside_target_band_allowed_reason"] = (
            "The selected family proved this is the smallest safe discrete "
            "width; the next width step fails the full engineering checks."
        )
        evidence["family_exact_stop_proof"] = dict(
            selected.get("family_exact_stop_proof") or {}
        )
    selected["candidate_search_evidence"] = dict(evidence)
    selected["candidate_id"] = evidence.get("selected_candidate_id")
    selected["source_candidate_id"] = evidence.get("selected_candidate_id")
    selected["canonical_winner_label"] = str(selected.get("label") or "Direct target-band candidate")
    selected["title_locked_from_final_winner"] = True
    selected_updates_for_family = dict(selected.get("updates") or {})
    selected_update_keys = {str(key) for key in selected_updates_for_family}
    width_only_cleanup = bool(selected_update_keys) and selected_update_keys.issubset(
        {"b", "bw", "beam_width", "beam_width_mm"}
    )
    try:
        direct_design_actions = _resolve_design_actions_from_state(base)
    except Exception:
        direct_design_actions = {}
    shear_overdesign_width_cleanup = bool(
        (not strengthening)
        and width_only_cleanup
        and _bending_demands_negligible(direct_design_actions)
        and not _shear_demands_negligible(direct_design_actions)
    )
    if strengthening and dispatch_family_id:
        # Family selection is an input to candidate search, not a publication
        # inference.  Stamp the already-selected family onto the winning
        # candidate so CTA/apply/publication cannot independently reclassify
        # a pure failure after the ladder has run.
        family_flags = {
            "geometry_detailing_fail": False,
            "serviceability_fail": False,
            "bending_fail": dispatch_family_id
            in {
                "BENDING_FAIL_GOVERNS",
                "COMBINED_BENDING_SHEAR_FAIL",
                "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            },
            "shear_fail": dispatch_family_id
            in {
                "SHEAR_FAIL_GOVERNS",
                "COMBINED_BENDING_SHEAR_FAIL",
                "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            },
            "bending_overdesigned": dispatch_family_id
            == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            "shear_overdesigned": dispatch_family_id
            == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            "bending_within_target_band": False,
            "shear_within_target_band": False,
            "locked_repair_blocked": False,
            "legal_repair_exists": True,
            "repair_required": True,
            "exact_stop_proven": False,
            "bending_acceptable": dispatch_family_id
            in {
                "SHEAR_FAIL_GOVERNS",
                "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            },
            "shear_acceptable": dispatch_family_id
            in {
                "BENDING_FAIL_GOVERNS",
                "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            },
            "bending_not_applicable": bool(
                dispatch_family_id == "SHEAR_FAIL_GOVERNS"
                and _bending_demands_negligible(direct_design_actions)
            ),
            "shear_not_applicable": bool(
                dispatch_family_id == "BENDING_FAIL_GOVERNS"
                and _shear_demands_negligible(direct_design_actions)
            ),
        }
        classification = classify_family_from_raw_flags(
            family_flags,
            evidence={
                "source": "design_guide_family_ladder_dispatch",
                "family_ladder_attempts": int(ladder_attempts),
                "family_ladder_success": bool(ladder_success),
            },
        )
        for family_key in (
            "family",
            "family_id",
            "selected_family_id",
            "published_family_id",
            "cta_family_id",
            "apply_payload_family_id",
            "candidate_family_id",
            "card_family_id",
        ):
            selected[family_key] = dispatch_family_id
            evidence[family_key] = dispatch_family_id
        selected["authoritative_family_override"] = dispatch_family_id
        evidence["authoritative_family_override"] = dispatch_family_id
        evidence["family_selection_source"] = "family_ladder_dispatch"
        evidence["family_selection_contract"] = "family_selection_contract"
        evidence["family_chooser_contract"] = "family_chooser_contract"
        evidence["family_match_passed"] = bool(
            classification.get("classification_passed")
            and classification.get("selected_family_id")
            == dispatch_family_id
        )
        evidence["family_match_violation_reason"] = (
            None
            if evidence["family_match_passed"]
            else "family_ladder_dispatch_and_classifier_disagree"
        )
        evidence["matched_family_ids"] = list(
            classification.get("matched_family_ids") or [dispatch_family_id]
        )
        evidence["raw_state_flags"] = dict(
            classification.get("raw_state_flags") or family_flags
        )
        evidence["rejected_families"] = dict(
            classification.get("rejected_families") or {}
        )
        evidence["selection_evidence"] = dict(
            classification.get("selection_evidence") or {}
        )
        evidence["selection_reason"] = str(
            classification.get("selection_reason")
            or f"family_ladder_dispatch:{dispatch_family_id}"
        )
        evidence["family_route_owner"] = str(
            dispatch_decision.get("strategy_owner") or ""
        )
    if shear_overdesign_width_cleanup:
        selected["family"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["selected_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["published_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["cta_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["apply_payload_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["candidate_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["card_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["contract_runtime_authority"] = "run_shear_overdesign_governs_runtime"
        selected["contract_runtime_driven"] = True
        selected["recommendation_family_tag"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["subfamilies"] = ["shear"]
        evidence["family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["selected_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["published_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["cta_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["apply_payload_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["contract_runtime_authority"] = "run_shear_overdesign_governs_runtime"
        evidence["contract_runtime_driven"] = True
        evidence["contract_width_cleanup_owned_by_shear_overdesign"] = True
    item = _guidance_item_from_resolved_candidate(
        selected,
        state=base,
        overview=dict(overview or {}),
        title=str(selected.get("label") or "Direct target-band candidate"),
        reasoning=(
            "This option searches the available geometry and reinforcement moves before "
            "accepting an outside-target step."
        ),
        status="FAIL" if bool((overview or {}).get("any_fail")) else "EFFICIENCY",
        primary_action="Apply recommendation",
    )
    item["candidate_search_evidence"] = dict(evidence)
    item["local_cleanup_candidate"] = not bool(strengthening)
    item["guidance_intent"] = (
        "required_fix" if bool(strengthening) else "optional_cleanup"
    )
    item["family_safe_pass_fallback"] = bool(
        selected.get("family_safe_pass_fallback")
    )
    evidence["family_safe_pass_fallback"] = bool(
        item["family_safe_pass_fallback"]
    )
    evidence["family_safe_pass_fallback_intent"] = str(
        item["guidance_intent"]
    )
    item["source"] = "generate_in_target_local_cleanup_candidates"
    if strengthening and dispatch_family_id:
        item["authoritative_family_override"] = dispatch_family_id
    state_fingerprint = str(_state_fingerprint(base))
    item["state_fingerprint"] = state_fingerprint
    item["final_visible_state_fingerprint"] = state_fingerprint
    _published_family_id = str(
        evidence.get("selected_family_id")
        or evidence.get("family_id")
        or evidence.get("cta_family_id")
        or ""
    ).strip()
    if strengthening and dispatch_family_id:
        _published_family_id = dispatch_family_id
    if not bool(strengthening):
        _selected_updates_for_publication = selected.get("updates") or selected.get("final_updates")
        _owner_family_id = _overdesign_family_id_from_cleanup_family(selected.get("affected_family"))
        _updates_family_id = _overdesign_family_id_from_cleanup_updates(_selected_updates_for_publication)
        if _owner_family_id:
            # Family ownership is determined before candidate construction.
            # Width reduction is an explicit SHEAR_OVERDESIGN_GOVERNS lane,
            # so a shear-owned cleanup does not become combined merely
            # because that lane carries both shear and width updates.
            _published_family_id = _owner_family_id
        elif _published_family_id.lower() in {"", "general", "other"}:
            _published_family_id = _updates_family_id
    if _published_family_id:
        for _family_key in (
            "family",
            "family_id",
            "selected_family_id",
            "published_family_id",
            "cta_family_id",
            "apply_payload_family_id",
            "candidate_family_id",
            "card_family_id",
        ):
            evidence[_family_key] = _published_family_id
    item["affected_family"] = _published_family_id or item.get("family") or item.get("check_key")
    item["candidate_search_evidence"] = dict(evidence)
    payload = dict(item.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["family_safe_pass_fallback"] = bool(
        item["family_safe_pass_fallback"]
    )
    payload["family_safe_pass_fallback_intent"] = str(
        item["guidance_intent"]
    )
    payload["source_candidate_id"] = evidence.get("selected_candidate_id")
    payload["state_fingerprint"] = state_fingerprint
    if _published_family_id:
        item["family"] = _published_family_id
        item["family_id"] = _published_family_id
        item["selected_family_id"] = _published_family_id
        item["published_family_id"] = _published_family_id
        item["cta_family_id"] = _published_family_id
        item["apply_payload_family_id"] = _published_family_id
        item["candidate_family_id"] = _published_family_id
        item["card_family_id"] = _published_family_id
        payload["family_id"] = _published_family_id
        payload["family"] = _published_family_id
        payload["selected_family_id"] = _published_family_id
        payload["published_family_id"] = _published_family_id
        payload["cta_family_id"] = _published_family_id
        payload["apply_payload_family_id"] = _published_family_id
    item["action_payload"] = payload
    button_contract = dict(item.get("button_contract") or {})
    button_contract["state_fingerprint"] = state_fingerprint
    button_contract["family_safe_pass_fallback"] = bool(
        item["family_safe_pass_fallback"]
    )
    button_contract["family_safe_pass_fallback_intent"] = str(
        item["guidance_intent"]
    )
    item["button_contract"] = button_contract
    resolved = dict(item.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["family_safe_pass_fallback"] = bool(
        item["family_safe_pass_fallback"]
    )
    resolved["family_safe_pass_fallback_intent"] = str(
        item["guidance_intent"]
    )
    resolved["candidate_id"] = evidence.get("selected_candidate_id")
    resolved["source_candidate_id"] = evidence.get("selected_candidate_id")
    resolved["state_fingerprint"] = state_fingerprint
    if _published_family_id:
        resolved["family_id"] = _published_family_id
        resolved["family"] = _published_family_id
        resolved["selected_family_id"] = _published_family_id
        resolved["published_family_id"] = _published_family_id
        resolved["cta_family_id"] = _published_family_id
        resolved["apply_payload_family_id"] = _published_family_id
    item["resolved_candidate"] = resolved
    if isinstance(debug_sink, dict):
        debug_sink["direct_target_band_search_used"] = True
        debug_sink["direct_target_band_search_candidate_count"] = len(candidates)
        debug_sink["direct_target_band_ladder_success"] = bool(
            ladder_success
        )
        debug_sink["direct_target_band_ladder_attempts"] = int(
            ladder_attempts
        )
        debug_sink["family_ladder_runtime_result"] = dict(family_ladder_result)
        debug_sink["family_ladder_runtime_selected"] = bool(
            ladder_success
            and str(
                (ladder_candidate or {}).get("candidate_source_stage") or ""
            ).startswith("family_ladder:")
        )
        debug_sink["candidate_search_evidence"] = dict(evidence)
        debug_sink["local_cleanup_candidate_search_evidence"] = dict(evidence)
    return item


__all__ = [
    "FamilyLadderGuidanceRuntime",
    "bind_family_ladder_guidance_dependencies",
    "_family_ladder_guidance_item",
]
