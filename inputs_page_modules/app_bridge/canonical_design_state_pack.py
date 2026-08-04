"""Canonical design-state pack coordination for the Inputs app bridge."""

from __future__ import annotations

import math
from typing import Any, Callable

from inputs_application.canonical_runtime_contracts import (
    CanonicalDesignStatePackRuntime,
)

from section_layout import compute_section_layout_pure as _compute_section_layout_owned
from section_props.reo_layout import (
    compute_longitudinal_reo_layout_T_I as _compute_longitudinal_reo_layout_owned,
    resolve_longitudinal_bars_from_layout as _resolve_longitudinal_bars_owned,
)
from state_and_helpers import (
    build_legacy_longitudinal_mirrors_from_rows as _build_legacy_mirrors_owned,
    effective_depth_with_links_mm as _effective_depth_with_links_owned,
    get_longitudinal_row_inputs as _get_longitudinal_rows_owned,
)


_CANONICAL_DESIGN_STATE_PACK_DEPENDENCIES: tuple[str, ...] = (
    "_canonical_rows_from_reo_layout_for_app_bridge",
    "_canonical_shape_name_and_dims_for_app_bridge",
    "_guidance_state_snapshot_for_summary_bridge",
    "_invalid_canonical_design_state_pack_for_app_bridge",
    "build_legacy_longitudinal_mirrors_from_rows",
    "compute_longitudinal_reo_layout_T_I",
    "compute_section_layout_pure",
    "effective_depth_with_links_mm",
    "get_longitudinal_row_inputs",
    "resolve_longitudinal_bars_from_layout",
)


def canonical_shape_name_and_dims(state: dict) -> tuple[str, dict]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "T-Section", {
            "bf": float(state.get("bf", state.get("b", 0.0)) or 0.0),
            "tf": float(state.get("tf", 0.0) or 0.0),
            "bw": float(state.get("bw", state.get("b", 0.0)) or 0.0),
            "D": float(state.get("D", 0.0) or 0.0),
        }
    if sec_shape == "I":
        return "I-Section", {
            "bf_top": float(state.get("bf", state.get("b", 0.0)) or 0.0),
            "tf_top": float(state.get("tf", 0.0) or 0.0),
            "bf_bot": float(
                state.get("bf_bot", state.get("bf", state.get("b", 0.0)))
                or 0.0
            ),
            "tf_bot": float(
                state.get("tf_bot", state.get("tf", 0.0)) or 0.0
            ),
            "bw": float(
                state.get("tw", state.get("bw", state.get("b", 0.0)))
                or 0.0
            ),
            "D": float(state.get("D", 0.0) or 0.0),
        }
    return "Rectangle (b × D)", {
        "b": float(state.get("b", 0.0) or 0.0),
        "D": float(state.get("D", 0.0) or 0.0),
    }


def canonical_rows_from_reo_layout(
    reo_layout: dict,
    layer_name: str,
) -> list[dict]:
    rows: list[dict] = []
    for index, layer in enumerate(
        reo_layout.get(layer_name) or [],
        start=1,
    ):
        if not isinstance(layer, dict):
            continue
        xs = [float(value) for value in (layer.get("x") or [])]
        diameter = float(layer.get("db", 0.0) or 0.0)
        raw_y = layer.get("y", 0.0)
        y = float(
            (raw_y[0] if isinstance(raw_y, list) and raw_y else raw_y)
            or 0.0
        )
        rows.append(
            {
                "active": bool(xs and diameter > 0.0),
                "row_index": int(layer.get("row_index", index) or index),
                "mode": str(layer.get("mode", "Count") or "Count"),
                "dia": diameter,
                "bar_count_resolved": len(xs),
                "spacing_resolved": float(
                    layer.get("spacing_actual", 0.0) or 0.0
                ),
                "x_positions": xs,
                "y_position": y,
                "steel_area_row": float(
                    layer.get(
                        "steel_area",
                        len(xs) * math.pi * diameter**2 / 4.0,
                    )
                    or 0.0
                ),
                "fit_ok": bool(layer.get("fit_ok", True)),
                "warning": layer.get("warning"),
            }
        )
    return rows


def invalid_canonical_design_state_pack(
    raw: dict,
    *,
    error: str,
    error_stage: str,
) -> dict:
    out = dict(raw or {})
    depth = float(raw.get("D", 0.0) or 0.0)
    cover_top = float(raw.get("cover_top", 0.0) or 0.0)
    cover_bottom = float(raw.get("cover_bot", 0.0) or 0.0)
    link_diameter = float(raw.get("lig_d", 0.0) or 0.0)
    out.update(
        {
            "bot_rows_resolved": [],
            "top_rows_resolved": [],
            "bot_bar_coords": [],
            "top_bar_coords": [],
            "resolved_longitudinal_bars": [],
            "Ast_top_web": 0.0,
            "Ast_top_flange": 0.0,
            "Ast_bottom_web": 0.0,
            "Ast_bottom_flange": 0.0,
            "Ast_top": 0.0,
            "Ast_bot": 0.0,
            "nb_bot": 0,
            "nb_top": 0,
            "db_bot": 0.0,
            "db_top": 0.0,
            "d": _effective_depth_with_links_owned(
                D_mm=depth,
                cover_to_ligs_mm=cover_bottom,
                lig_diameter_mm=link_diameter,
                bar_diameter_mm=0.0,
            ),
            "do": float(depth - cover_top),
            "canonical_pack_built": False,
            "canonical_pack_valid": False,
            "canonical_pack_source": "shared_rebuilt_failed",
            "canonical_pack_error": str(error),
            "canonical_pack_error_stage": str(error_stage),
        }
    )
    return out


def bind_canonical_design_state_pack_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CANONICAL_DESIGN_STATE_PACK_DEPENDENCIES
            if name in namespace
        }
    )


def _build_canonical_design_state_pack_for_app_bridge(
    state: dict,
    *,
    runtime: CanonicalDesignStatePackRuntime | None = None,
) -> dict:
    snapshot = (
        runtime.guidance_state_snapshot
        if runtime is not None
        else _guidance_state_snapshot_for_summary_bridge
    )
    raw = snapshot(dict(state or {}))
    raw_synced = dict(raw)
    raw_synced.update(_build_legacy_mirrors_owned(raw_synced))
    out = dict(raw_synced)
    shape_name, dims = canonical_shape_name_and_dims(raw_synced)
    cover_top = float(raw_synced.get("cover_top", 0.0) or 0.0)
    cover_bot = float(raw_synced.get("cover_bot", 0.0) or 0.0)
    cover_side = float(raw_synced.get("cover_side", 0.0) or 0.0)
    rowgap_top = float(raw_synced.get("rowgap_top", 0.0) or 0.0)
    rowgap_bot = float(raw_synced.get("rowgap_bot", 0.0) or 0.0)
    lig_d = float(raw_synced.get("lig_d", 0.0) or 0.0)
    lig_legs = int(raw_synced.get("lig_legs", 2) or 2)
    min_clear_spacing = float(raw_synced.get("min_clear_spacing", 20.0) or 20.0)
    reo_layout: dict = {}
    try:
        if shape_name in ("T-Section", "I-Section"):
            reo_layout = _compute_longitudinal_reo_layout_owned(
                shape_name=shape_name,
                dims=dims,
                cover_side=cover_side,
                cover_top=cover_top,
                cover_bot=cover_bot,
                min_clear_spacing=min_clear_spacing,
                rowgap_top=rowgap_top,
                rowgap_bot=rowgap_bot,
                reo=raw_synced,
            )
        else:
            sec = _compute_section_layout_owned(
                b=float(raw_synced.get("b", 0.0) or 0.0),
                D=float(raw_synced.get("D", 0.0) or 0.0),
                cover_bot=cover_bot,
                cover_top=cover_top,
                cover_side=cover_side,
                nb_or_s_bot_1=float(raw_synced.get("bot1_count", raw_synced.get("nb_bot_1", 0.0)) or 0.0),
                db_bot_1=float(raw_synced.get("db_bot_1", 0.0) or 0.0),
                nb_or_s_bot_2=float(raw_synced.get("bot2_count", raw_synced.get("nb_bot_2", 0.0)) or 0.0),
                db_bot_2=float(raw_synced.get("db_bot_2", raw_synced.get("db_bot_1", 0.0)) or 0.0),
                nb_or_s_top_1=float(raw_synced.get("top1_count", raw_synced.get("nb_top_1", 0.0)) or 0.0),
                db_top_1=float(raw_synced.get("db_top_1", 0.0) or 0.0),
                nb_or_s_top_2=float(raw_synced.get("top2_count", raw_synced.get("nb_top_2", 0.0)) or 0.0),
                db_top_2=float(raw_synced.get("db_top_2", raw_synced.get("db_top_1", 0.0)) or 0.0),
                rowgap_bot=rowgap_bot,
                rowgap_top=rowgap_top,
                lig_legs=lig_legs,
                lig_d=lig_d,
                bottom_rows=_get_longitudinal_rows_owned("bot", source=raw_synced),
                top_rows=_get_longitudinal_rows_owned("top", source=raw_synced),
            )
            reo_layout = dict(sec.get("reo_layout", {}) or {})
    except Exception:
        reo_layout = {}
    if not isinstance(reo_layout, dict):
        reo_layout = {}
    if not reo_layout:
        return invalid_canonical_design_state_pack(
            raw_synced,
            error="no_bars_resolved",
            error_stage="reo_layout_empty",
        )
    try:
        bars = _resolve_longitudinal_bars_owned(shape_name=shape_name, dims=dims, reo_layout=reo_layout)
    except AssertionError as exc:
        if "no bars resolved" in str(exc).lower():
            return invalid_canonical_design_state_pack(
                raw_synced,
                error="no_bars_resolved",
                error_stage="resolve_longitudinal_bars",
            )
        return invalid_canonical_design_state_pack(
            raw_synced,
            error="canonical_pack_failed",
            error_stage="resolve_longitudinal_bars",
        )
    except Exception:
        return invalid_canonical_design_state_pack(
            raw_synced,
            error="canonical_pack_failed",
            error_stage="resolve_longitudinal_bars",
        )
    if not bars:
        return invalid_canonical_design_state_pack(
            raw_synced,
            error="no_bars_resolved",
            error_stage="resolve_longitudinal_bars",
        )
    bot_rows = canonical_rows_from_reo_layout(reo_layout, "bottom")
    top_rows = canonical_rows_from_reo_layout(reo_layout, "top")
    out["bot_rows_resolved"] = bot_rows
    out["top_rows_resolved"] = top_rows
    out["bot_bar_coords"] = [{"x": x, "y": r["y_position"], "db": r["dia"], "row_index": r["row_index"]} for r in bot_rows for x in r.get("x_positions", [])]
    out["top_bar_coords"] = [{"x": x, "y": r["y_position"], "db": r["dia"], "row_index": r["row_index"]} for r in top_rows for x in r.get("x_positions", [])]
    out["resolved_longitudinal_bars"] = list(bars or [])
    top_bars = [bar for bar in bars if str(bar.get("face")) == "top"]
    bottom_bars = [bar for bar in bars if str(bar.get("face")) == "bottom"]
    out["Ast_top_web"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in top_bars if "web" in str(bar.get("zone", ""))))
    out["Ast_top_flange"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in top_bars if "flange" in str(bar.get("zone", ""))))
    out["Ast_bottom_web"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in bottom_bars if "web" in str(bar.get("zone", ""))))
    out["Ast_bottom_flange"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in bottom_bars if "flange" in str(bar.get("zone", ""))))
    out["Ast_top"] = float(out["Ast_top_web"] + out["Ast_top_flange"])
    out["Ast_bot"] = float(out["Ast_bottom_web"] + out["Ast_bottom_flange"])
    out["nb_bot"] = int(sum(int(r.get("bar_count_resolved", 0) or 0) for r in bot_rows))
    out["nb_top"] = int(sum(int(r.get("bar_count_resolved", 0) or 0) for r in top_rows))
    out["db_bot"] = float(max((float(bar.get("dia_mm", 0.0) or 0.0) for bar in bottom_bars), default=0.0))
    out["db_top"] = float(max((float(bar.get("dia_mm", 0.0) or 0.0) for bar in top_bars), default=0.0))
    primary_bot = next((r for r in bot_rows if r.get("active")), None)
    primary_top = next((r for r in top_rows if r.get("active")), None)
    if primary_bot:
        out["s_bot"] = float(primary_bot.get("spacing_resolved", out.get("s_bot", 0.0)) or 0.0)
    if primary_top:
        out["s_top"] = float(primary_top.get("spacing_resolved", out.get("s_top", 0.0)) or 0.0)
    bar_dia = float(primary_bot.get("dia", out.get("db_bot_1", 0.0)) if primary_bot else out.get("db_bot_1", 0.0) or 0.0)
    D = float(raw_synced.get("D", 0.0) or 0.0)
    out["d"] = _effective_depth_with_links_owned(D_mm=D, cover_to_ligs_mm=cover_bot, lig_diameter_mm=lig_d, bar_diameter_mm=bar_dia)
    out["do"] = float(D - float(primary_top.get("y_position", 0.0) if primary_top else (cover_top + float(out.get("db_top_1", 0.0) or 0.0) / 2.0)))
    out["canonical_pack_built"] = True
    out["canonical_pack_valid"] = True
    out["canonical_pack_source"] = "shared_rebuilt"
    out["canonical_pack_error"] = None
    out["canonical_pack_error_stage"] = None
    return out
