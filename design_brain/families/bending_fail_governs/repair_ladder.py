from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return int(default)
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def row_clear_spacing(
    width: float,
    count: int,
    dia: int,
    *,
    cover_side: float,
    lig_d: int,
) -> float:
    """Return clear spacing for one bottom reinforcement row."""

    count_i = max(0, int(count))
    if count_i <= 1:
        return float("inf")
    available = float(width) - 2.0 * (float(cover_side) + float(lig_d))
    return (available - float(count_i) * float(dia)) / float(count_i - 1)


def layout_clear_spacing(
    width: float,
    row1: int,
    dia: int,
    row2: int = 0,
    *,
    cover_side: float,
    lig_d: int,
) -> float:
    """Return the controlling clear spacing for a one- or two-row layout."""

    spacings = [
        row_clear_spacing(
            width,
            row1,
            dia,
            cover_side=cover_side,
            lig_d=lig_d,
        )
    ]
    if int(row2 or 0) > 0:
        spacings.append(
            row_clear_spacing(
                width,
                row2,
                dia,
                cover_side=cover_side,
                lig_d=lig_d,
            )
        )
    return min(spacings)


def fits_bottom_reinforcement_layout(
    width: float,
    row1: int,
    dia: int,
    row2: int = 0,
    *,
    cover_side: float,
    lig_d: int,
    minimum_clear_spacing_mm: float,
) -> bool:
    """Return whether the bottom reinforcement layout satisfies spacing."""

    clear = layout_clear_spacing(
        width,
        row1,
        dia,
        row2,
        cover_side=cover_side,
        lig_d=lig_d,
    )
    return clear >= float(minimum_clear_spacing_mm) - 1e-9


def build_bending_fail_layout_updates(
    updates: dict[str, Any],
    *,
    width_key: str,
    base_width: float,
    base_depth: float,
    base_count: int,
    base_dia: int,
    cover_side: float,
    lig_d: int,
) -> tuple[float, float, int, int, int, bool, float]:
    """Return normalized layout fields for one repair-ladder update set."""

    values = dict(updates or {})
    width = _as_float(values.get(width_key), _as_float(values.get("b"), base_width))
    depth = _as_float(values.get("D"), base_depth)
    row1 = _as_int(values.get("bot_row_1_bars"), _as_int(values.get("bot1_count"), base_count))
    row2 = _as_int(values.get("bot_row_2_bars"), _as_int(values.get("bot2_count"), 0))
    dia = _as_int(values.get("bot_row_1_dia"), _as_int(values.get("db_bot_1"), base_dia))
    split = bool(row2 > 0)
    clear = layout_clear_spacing(
        width,
        row1,
        dia,
        row2,
        cover_side=cover_side,
        lig_d=lig_d,
    )
    return width, depth, row1, row2, dia, split, clear


@dataclass(frozen=True)
class BendingFailRepairLadderAddResult:
    """Proof-only boundary for one local repair-ladder `_add(...)` call."""

    action: str
    stage_name: str
    strategy: str
    normalized_layout: dict[str, Any]
    spacing_fit: bool
    blocker_reason: str | None
    update_payload_keys: tuple[str, ...]
    update_diff_keys: tuple[str, ...]
    assigned_candidate_index: int | None
    assigned_label: str | None
    appended_spec_summary: dict[str, Any] | None
    known_bad_mutation_summary: dict[str, Any] | None


@dataclass(frozen=True)
class BendingFailRepairLadderAddDecision:
    """Pure decision payload for one repair-ladder `_add(...)` branch."""

    should_record_known_bad: bool
    should_append_spec: bool
    known_bad_record: dict[str, Any] | None
    spec_payload: dict[str, Any] | None
    add_result: BendingFailRepairLadderAddResult


def build_bending_fail_repair_ladder_add_result(
    *,
    stage_name: str,
    strategy: str,
    width: float,
    depth: float,
    row1: int,
    row2: int,
    dia: int,
    split: bool,
    clear: float,
    minimum_clear_spacing_mm: float,
    updates: dict[str, Any],
    diff: dict[str, Any] | None,
    assigned_candidate_index: int | None = None,
    assigned_label: str | None = None,
    appended_spec: dict[str, Any] | None = None,
    known_bad_record: dict[str, Any] | None = None,
) -> BendingFailRepairLadderAddResult:
    """Describe one repair-ladder row-add outcome without mutating caller state."""

    spacing_fit = float(clear) >= float(minimum_clear_spacing_mm) - 1e-9
    update_payload_keys = tuple(sorted(dict(updates or {}).keys()))
    update_diff_keys = tuple(sorted(dict(diff or {}).keys()))
    blocker_reason = None
    if known_bad_record:
        blocker_reason = str(known_bad_record.get("reason") or "") or None

    appended_spec_summary = None
    if appended_spec:
        appended_spec_summary = {
            "ladder_index": appended_spec.get("ladder_index"),
            "contract_step": appended_spec.get("contract_step"),
            "stage_name": appended_spec.get("stage_name"),
            "strategy": appended_spec.get("strategy"),
            "candidate_family_id": appended_spec.get("candidate_family_id"),
            "label": appended_spec.get("label"),
            "update_keys": tuple(sorted(dict(appended_spec.get("updates") or {}).keys())),
            "clear_spacing": appended_spec.get("clear_spacing"),
        }

    known_bad_mutation_summary = None
    if known_bad_record:
        known_bad_mutation_summary = {
            "stage_name": known_bad_record.get("stage_name"),
            "strategy": known_bad_record.get("strategy"),
            "reason": known_bad_record.get("reason"),
            "bottom_bar_count": known_bad_record.get("bottom_bar_count"),
            "bar_diameter": known_bad_record.get("bar_diameter"),
            "split_row": known_bad_record.get("split_row"),
            "clear_spacing": known_bad_record.get("clear_spacing"),
        }

    if known_bad_record:
        action = "skipped_known_bad"
    elif not diff:
        action = "skipped_no_diff"
    else:
        action = "appended_spec"

    return BendingFailRepairLadderAddResult(
        action=action,
        stage_name=stage_name,
        strategy=strategy,
        normalized_layout={
            "b": width,
            "D": depth,
            "bottom_bar_count": row1 + row2,
            "bar_diameter": dia,
            "split_row": split,
            "clear_spacing": clear,
        },
        spacing_fit=spacing_fit,
        blocker_reason=blocker_reason,
        update_payload_keys=update_payload_keys,
        update_diff_keys=update_diff_keys,
        assigned_candidate_index=assigned_candidate_index,
        assigned_label=assigned_label,
        appended_spec_summary=appended_spec_summary,
        known_bad_mutation_summary=known_bad_mutation_summary,
    )


def build_bending_fail_known_bad_spacing_record(
    *,
    stage_name: str,
    strategy: str,
    width: float,
    depth: float,
    row1: int,
    row2: int,
    dia: int,
    split: bool,
    clear: float,
) -> dict[str, Any]:
    """Build the known-bad spacing record for a rejected ladder row."""

    return {
        "stage_name": stage_name,
        "strategy": strategy,
        "b": width,
        "D": depth,
        "bottom_bar_count": row1 + row2,
        "bar_diameter": dia,
        "split_row": split,
        "clear_spacing": clear,
        "reason": "clear_spacing_below_100_mm",
    }


def build_bending_fail_repair_ladder_spec_payload(
    *,
    assigned_candidate_index: int,
    contract_step: int,
    stage_name: str,
    strategy: str,
    updates: dict[str, Any],
    escalation: str | None,
    width: float,
    depth: float,
    row1: int,
    row2: int,
    dia: int,
    split: bool,
    clear: float,
    assigned_label: str,
) -> dict[str, Any]:
    """Build the appendable repair-ladder spec payload for one candidate row."""

    return {
        "ladder_index": assigned_candidate_index,
        "contract_step": int(contract_step),
        "stage_name": stage_name,
        "strategy": strategy,
        "updates": updates,
        "escalation": escalation,
        "candidate_family_id": "BENDING_FAIL_GOVERNS",
        "stop_rule": "stop_on_first_compliant_bending_repair",
        "b": width,
        "D": depth,
        "bottom_bar_count": row1 + row2,
        "bar_diameter": dia,
        "split_row": split,
        "clear_spacing": clear if math.isfinite(clear) else None,
        "label": assigned_label,
    }


def decide_bending_fail_repair_ladder_add(
    *,
    step: int,
    stage_name: str,
    strategy: str,
    updates: dict[str, Any],
    diff: dict[str, Any] | None,
    spacing_blocked: bool,
    width: float,
    depth: float,
    row1: int,
    row2: int,
    dia: int,
    split: bool,
    clear: float,
    minimum_clear_spacing_mm: float,
    escalation: str | None = None,
    assigned_candidate_index: int | None = None,
    assigned_label: str | None = None,
) -> BendingFailRepairLadderAddDecision:
    """Return pure payloads for one repair-ladder add decision."""

    if spacing_blocked:
        known_bad_record = build_bending_fail_known_bad_spacing_record(
            stage_name=stage_name,
            strategy=strategy,
            width=width,
            depth=depth,
            row1=row1,
            row2=row2,
            dia=dia,
            split=split,
            clear=clear,
        )
        return BendingFailRepairLadderAddDecision(
            should_record_known_bad=True,
            should_append_spec=False,
            known_bad_record=known_bad_record,
            spec_payload=None,
            add_result=build_bending_fail_repair_ladder_add_result(
                stage_name=stage_name,
                strategy=strategy,
                width=width,
                depth=depth,
                row1=row1,
                row2=row2,
                dia=dia,
                split=split,
                clear=clear,
                minimum_clear_spacing_mm=minimum_clear_spacing_mm,
                updates=updates,
                diff=None,
                known_bad_record=known_bad_record,
            ),
        )

    if not diff:
        return BendingFailRepairLadderAddDecision(
            should_record_known_bad=False,
            should_append_spec=False,
            known_bad_record=None,
            spec_payload=None,
            add_result=build_bending_fail_repair_ladder_add_result(
                stage_name=stage_name,
                strategy=strategy,
                width=width,
                depth=depth,
                row1=row1,
                row2=row2,
                dia=dia,
                split=split,
                clear=clear,
                minimum_clear_spacing_mm=minimum_clear_spacing_mm,
                updates=updates,
                diff=diff,
            ),
        )

    if assigned_candidate_index is None or assigned_label is None:
        raise ValueError("assigned_candidate_index and assigned_label are required for appendable repair ladder adds")

    spec_payload = build_bending_fail_repair_ladder_spec_payload(
        assigned_candidate_index=assigned_candidate_index,
        contract_step=step,
        stage_name=stage_name,
        strategy=strategy,
        updates=diff,
        escalation=escalation,
        width=width,
        depth=depth,
        row1=row1,
        row2=row2,
        dia=dia,
        split=split,
        clear=clear,
        assigned_label=assigned_label,
    )
    return BendingFailRepairLadderAddDecision(
        should_record_known_bad=False,
        should_append_spec=True,
        known_bad_record=None,
        spec_payload=spec_payload,
        add_result=build_bending_fail_repair_ladder_add_result(
            stage_name=stage_name,
            strategy=strategy,
            width=width,
            depth=depth,
            row1=row1,
            row2=row2,
            dia=dia,
            split=split,
            clear=clear,
            minimum_clear_spacing_mm=minimum_clear_spacing_mm,
            updates=updates,
            diff=diff,
            assigned_candidate_index=assigned_candidate_index,
            assigned_label=assigned_label,
            appended_spec=spec_payload,
        ),
    )


def build_bending_fail_repair_ladder_result(
    *,
    governing_state: str,
    candidate_strategy: str,
    bar_diameters_tried: list[int],
    depth_steps_mm: list[float],
    width_steps_mm: list[float],
    minimum_clear_spacing_mm: float,
    known_bad_candidates_skipped: list[dict[str, Any]],
    ranking_rule: str,
    stop_reason_if_no_candidate: str,
    specs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the public BENDING_FAIL_GOVERNS repair-ladder result shape."""

    return {
        "family_name": "BENDING_FAIL_GOVERNS",
        "governing_state": governing_state,
        "candidate_strategy": candidate_strategy,
        "bar_diameters_tried": list(bar_diameters_tried or []),
        "depth_steps_mm": list(depth_steps_mm or []),
        "width_steps_mm": list(width_steps_mm or []),
        "minimum_clear_spacing_mm": float(minimum_clear_spacing_mm),
        "known_bad_candidate_count": len(list(known_bad_candidates_skipped or [])),
        "known_bad_candidates_skipped": list(known_bad_candidates_skipped or [])[:20],
        "ranking_rule": ranking_rule,
        "stop_reason_if_no_candidate": stop_reason_if_no_candidate,
        "specs": list(specs or []),
    }


__all__ = [
    "BendingFailRepairLadderAddDecision",
    "BendingFailRepairLadderAddResult",
    "build_bending_fail_known_bad_spacing_record",
    "build_bending_fail_repair_ladder_add_result",
    "build_bending_fail_repair_ladder_spec_payload",
    "decide_bending_fail_repair_ladder_add",
    "build_bending_fail_repair_ladder_result",
    "build_bending_fail_layout_updates",
    "fits_bottom_reinforcement_layout",
    "layout_clear_spacing",
    "row_clear_spacing",
]
