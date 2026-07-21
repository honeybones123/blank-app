"""Canonical design-state pack coordination for the Inputs app bridge."""

from __future__ import annotations

from typing import Any


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


def bind_canonical_design_state_pack_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CANONICAL_DESIGN_STATE_PACK_DEPENDENCIES
            if name in namespace
        }
    )


def _build_canonical_design_state_pack_for_app_bridge(state: dict) -> dict:
    raw = _guidance_state_snapshot_for_summary_bridge(dict(state or {}))
    raw_synced = dict(raw)
    raw_synced.update(build_legacy_longitudinal_mirrors_from_rows(raw_synced))
    out = dict(raw_synced)
    shape_name, dims = _canonical_shape_name_and_dims_for_app_bridge(raw_synced)
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
            reo_layout = compute_longitudinal_reo_layout_T_I(
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
            sec = compute_section_layout_pure(
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
                bottom_rows=get_longitudinal_row_inputs("bot", source=raw_synced),
                top_rows=get_longitudinal_row_inputs("top", source=raw_synced),
            )
            reo_layout = dict(sec.get("reo_layout", {}) or {})
    except Exception:
        reo_layout = {}
    if not isinstance(reo_layout, dict):
        reo_layout = {}
    if not reo_layout:
        return _invalid_canonical_design_state_pack_for_app_bridge(
            raw_synced,
            error="no_bars_resolved",
            error_stage="reo_layout_empty",
        )
    try:
        bars = resolve_longitudinal_bars_from_layout(shape_name=shape_name, dims=dims, reo_layout=reo_layout)
    except AssertionError as exc:
        if "no bars resolved" in str(exc).lower():
            return _invalid_canonical_design_state_pack_for_app_bridge(
                raw_synced,
                error="no_bars_resolved",
                error_stage="resolve_longitudinal_bars",
            )
        return _invalid_canonical_design_state_pack_for_app_bridge(
            raw_synced,
            error="canonical_pack_failed",
            error_stage="resolve_longitudinal_bars",
        )
    except Exception:
        return _invalid_canonical_design_state_pack_for_app_bridge(
            raw_synced,
            error="canonical_pack_failed",
            error_stage="resolve_longitudinal_bars",
        )
    if not bars:
        return _invalid_canonical_design_state_pack_for_app_bridge(
            raw_synced,
            error="no_bars_resolved",
            error_stage="resolve_longitudinal_bars",
        )
    bot_rows = _canonical_rows_from_reo_layout_for_app_bridge(reo_layout, "bottom")
    top_rows = _canonical_rows_from_reo_layout_for_app_bridge(reo_layout, "top")
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
    bar_dia = float(primary_bot.get("dia", out.get("db_bot_1", 0.0)) if primary_bot else out.get("db_bot_1", 0.0) or 0.0)
    D = float(raw_synced.get("D", 0.0) or 0.0)
    out["d"] = effective_depth_with_links_mm(D_mm=D, cover_to_ligs_mm=cover_bot, lig_diameter_mm=lig_d, bar_diameter_mm=bar_dia)
    out["do"] = float(D - float(primary_top.get("y_position", 0.0) if primary_top else (cover_top + float(out.get("db_top_1", 0.0) or 0.0) / 2.0)))
    out["canonical_pack_built"] = True
    out["canonical_pack_valid"] = True
    out["canonical_pack_source"] = "shared_rebuilt"
    out["canonical_pack_error"] = None
    out["canonical_pack_error_stage"] = None
    return out
