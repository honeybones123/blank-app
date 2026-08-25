"""Application-owned bottom-reinforcement display projections."""

from __future__ import annotations

from typing import Any


_GUIDANCE_CHANGE_ARROW = "->"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return int(default)


def _normalised_sec_shape(raw: Any) -> str:
    value = str(raw or "RECT").strip().upper()
    if value in ("T", "T-SECTION", "T_SECTION", "T-BEAM"):
        return "T"
    if value in ("I", "I-SECTION", "I_SECTION", "I-BEAM"):
        return "I"
    return "RECT"


def _change_line_prefixes(state: dict[str, Any] | None) -> tuple[str, str]:
    raw = (state or {}).get("sec_shape") or (state or {}).get("inputs_sec_shape")
    if _normalised_sec_shape(raw) in ("T", "I"):
        return "Web bottom reo", "Web top reo"
    return "Bottom reo", "Top reo"


def _width_context(state: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", _as_float(state.get("bw", state.get("b", 300.0)), 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", _as_float(state.get("tw", state.get("b", 200.0)), 200.0)
    return "b", "Width b (mm)", _as_float(state.get("b", 400.0), 400.0)


def _practical_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def format_longitudinal_reinforcement_rows(
    state: dict[str, Any] | None,
    *,
    face: str,
) -> str:
    """Return every active committed longitudinal row for compact cards.

    Row 2 values can remain stored while disabled, so the declared row count
    is the activation authority.  Older projects without that field infer the
    active rows from the non-zero count, matching the engineering adapter.
    """

    values = dict(state or {})
    prefix = "top" if str(face).strip().lower() == "top" else "bot"
    declared_key = f"{prefix}_row_count"
    second_count = _as_int(
        values.get(
            f"{prefix}_row_2_bars",
            values.get(f"{prefix}2_count", 0),
        ),
        0,
    )
    declared_rows = _as_int(
        values.get(declared_key),
        2 if second_count > 0 else 1,
    )
    declared_rows = 1 if declared_rows <= 1 else 2
    parts: list[str] = []
    for row_index in range(1, declared_rows + 1):
        mode = str(
            values.get(
                f"{prefix}_row_{row_index}_mode",
                values.get(f"{prefix}{row_index}_layout_mode", "Count"),
            )
            or "Count"
        ).strip().lower()
        diameter = _as_int(
            values.get(
                f"{prefix}_row_{row_index}_dia",
                values.get(
                    f"db_{prefix}_{row_index}",
                    values.get(f"db_{prefix}", 0),
                ),
            ),
            0,
        )
        if mode == "spacing":
            spacing = _as_int(
                values.get(
                    f"{prefix}_row_{row_index}_spacing",
                    values.get(f"{prefix}{row_index}_spacing", 0),
                ),
                0,
            )
            if diameter > 0 and spacing > 0:
                parts.append(f"N{diameter} @ {spacing}")
            continue
        count = _as_int(
            values.get(
                f"{prefix}_row_{row_index}_bars",
                values.get(f"{prefix}{row_index}_count", 0),
            ),
            0,
        )
        if count > 0 and diameter > 0:
            parts.append(f"{count}-N{diameter}")
    return " + ".join(parts) if parts else "None"


def _bottom_label(state: dict[str, Any]) -> str:
    canonical = format_longitudinal_reinforcement_rows(state, face="bottom")
    if canonical != "None":
        return canonical.replace("-N", "N")
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = _as_int(state.get("bot1_count"), 0)
        count_2 = _as_int(state.get("bot2_count"), 0)
        dia = _as_int(state.get("db_bot_1", state.get("db_bot", 0)), 0)
        if count_1 > 0:
            return _practical_label(count_1, count_2, dia)
    return f"N{_as_int(state.get('db_bot_1'), 0)} @ {int(_as_float(state.get('bot1_spacing'), 0.0))}"


def _top_label(state: dict[str, Any]) -> str:
    canonical = format_longitudinal_reinforcement_rows(state, face="top")
    if canonical != "None":
        return canonical.replace("-N", "N")
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = _as_int(state.get("top1_count"), 0)
    count_2 = _as_int(state.get("top2_count"), 0)
    if mode_1 == "Count" and mode_2 == "Count":
        dia = _as_int(state.get("db_top_1", state.get("db_top", 0)), 0)
        if count_1 > 0 or count_2 > 0:
            return _practical_label(count_1, count_2, dia)
        return "None"
    return f"N{_as_int(state.get('db_top_1'), 0)} @ {int(_as_float(state.get('top1_spacing'), 0.0))}"


def _shear_fragment(state: dict[str, Any]) -> str | None:
    legs = _as_int(state.get("lig_legs"), 0)
    if legs <= 0:
        return None
    return f"N{_as_int(state.get('lig_d'), 0)}, {legs}-leg @{int(_as_float(state.get('s_lig'), 0.0))}"


def build_bottom_reo_guidance_change_lines_for_updates(
    before: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> list[str]:
    """Build the visible change-line projection for bottom-reo recommendations."""

    if not updates:
        return []
    before_state = dict(before or {}) if isinstance(before, dict) else {}
    after_state = dict(before_state)
    after_state.update(dict(updates or {}))
    lines: list[str] = []
    _, _, before_width = _width_context(before_state)
    _, _, after_width = _width_context(after_state)
    try:
        if abs(float(after_width) - float(before_width)) > 1e-6:
            lines.append(f"Width: {int(round(float(before_width)))} {_GUIDANCE_CHANGE_ARROW} {int(round(float(after_width)))} mm")
    except (TypeError, ValueError):
        pass
    try:
        before_depth = _as_float(before_state.get("D"), 0.0)
        after_depth = _as_float(after_state.get("D"), 0.0)
        if abs(after_depth - before_depth) > 1e-6:
            lines.append(f"Depth: {int(round(before_depth))} {_GUIDANCE_CHANGE_ARROW} {int(round(after_depth))} mm")
    except (TypeError, ValueError):
        pass
    before_bottom = _bottom_label(before_state)
    after_bottom = _bottom_label(after_state)
    bottom_phrase, top_phrase = _change_line_prefixes(after_state)
    if before_bottom != after_bottom:
        lines.append(f"{bottom_phrase}: {before_bottom} {_GUIDANCE_CHANGE_ARROW} {after_bottom}")
    before_top = _top_label(before_state)
    after_top = _top_label(after_state)
    if before_top != after_top:
        lines.append(f"{top_phrase}: {before_top} {_GUIDANCE_CHANGE_ARROW} {after_top}")
    before_shear = _shear_fragment(before_state)
    after_shear = _shear_fragment(after_state)
    if before_shear != after_shear:
        if after_shear is None:
            lines.append(f"Shear links: {before_shear} {_GUIDANCE_CHANGE_ARROW} removed")
        elif before_shear is None:
            lines.append(f"Shear links: none {_GUIDANCE_CHANGE_ARROW} {after_shear}")
        else:
            lines.append(f"Shear links: {before_shear} {_GUIDANCE_CHANGE_ARROW} {after_shear}")
    return lines


__all__ = [
    "build_bottom_reo_guidance_change_lines_for_updates",
    "format_longitudinal_reinforcement_rows",
]
