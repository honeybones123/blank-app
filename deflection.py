# deflection_page.py
import math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path

from state_and_helpers import (
    init_shared_session_state,
    get_param,
    get_sync_callbacks,
    get_widget_key_for_shared,
    is_design_governing,
    resolve_design_actions,
    update_results,  # kept for contract / future use
    DEFLECTION_LIMIT_OPTIONS,
    DEFLECTION_LIMIT_HELP_TEXT,
    get_deflection_limit_ratio,
    get_deflection_limit_label_from_ratio,
    TAB_KEYS,
)
from widgets_helpers import (
    apply_global_widget_css,
    apply_result_page_css,
    apply_calcbox_css,
    apply_step_summary_expander_css,
    render_result_page_title,
    render_page_explainer_expander,
    number_row,
    calcbox,
    label_with_hover,
    v2_number_input,
    v2_selectbox,
    v2_checkbox,
    v2_radio,
    info_i_button,
    page_divider,
    render_longitudinal_reo_rows,
    render_longitudinal_reo_row_config_controls,
    main_longitudinal_reo_pair_labels,
)
from step_ui import init_step_ui_state, render_expandable_step
from engineering_check_ui import DEFLECTION_CHECK_SUMMARY_COLUMNS
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks
from deflection_checks_helpers import build_deflection_check_rows_from_state


# Standard reinforcement lists (shared with Inputs page patterns)
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


# ------------------------------------------------------------
#  Shared helpers
# ------------------------------------------------------------
SUPPORT_DEFLECTION_MAP = {
    "Simply supported": {"k2": 5.0 / 384.0, "diagram": "simply_supported_udl"},
    # Same idealisation as simply supported for k₂ (ends rotationally free); symbols differ (pin+pin).
    "Pinned–Pinned": {"k2": 5.0 / 384.0, "diagram": "simply_supported_udl"},
    "Continuous – end span": {"k2": 2.4 / 384.0, "diagram": "continuous_span_udl"},
    "Continuous – interior span": {"k2": 1.5 / 384.0, "diagram": "continuous_span_udl"},
    # Fixed-ended (design-driven): UDL fixed–fixed midspan coefficient 1/384 (δ = wL⁴/(384EI))
    "Fixed-ended": {"k2": 1.0 / 384.0, "diagram": "fixed_fixed_udl"},
    # One fixed + one pinned (UDL): δ_max ≈ wL⁴/(185EI) — distinct from fixed–fixed and simply supported
    "Fixed–Pinned": {"k2": 1.0 / 185.0, "diagram": "fixed_pinned_udl"},
    "Pinned–Fixed": {"k2": 1.0 / 185.0, "diagram": "fixed_pinned_udl"},
    "Cantilever": {"k2": 1.0 / 8.0, "diagram": "cantilever_udl"},
}
_DEBUG_DEFLECTION_SUPPORT_RESOLUTION = False


# region agent log
def _dbg_defl_support_ndjson(data: dict) -> None:
    """Append one NDJSON line to debug-55de1f.log (debug session 55de1f)."""
    try:
        import json
        import os
        import time

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug-55de1f.log")
        row = {
            "sessionId": "55de1f",
            "runId": "defl_design_support",
            "timestamp": int(time.time() * 1000),
            "location": "deflection.py:get_deflection_diagram_support_condition",
            **data,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


# endregion

# Standard dropdown order; design-resolved fixed/pinned variants are appended when active.
DEFLECTION_SUPPORT_OPTIONS_BASE = [
    "Simply supported",
    "Pinned–Pinned",
    "Continuous – end span",
    "Continuous – interior span",
    "Cantilever",
]

def _normalize_deflection_support_type(value: str | None) -> str:
    raw = (value or "").strip().replace("-", "–")
    # Map key uses ASCII hyphen in "Fixed-ended"; replace() turns it into Fixed–ended (en-dash).
    if raw == "Fixed–ended":
        raw = "Fixed-ended"
    if raw in SUPPORT_DEFLECTION_MAP:
        return raw
    raw_low = raw.lower()
    if "cantilever" in raw_low or raw == "Fixed–Free":
        return "Cantilever"
    if raw == "Fixed-ended" or "fixed-ended" in raw_low:
        return "Fixed-ended"
    if "fixed–pinned" in raw_low or "fixed-pinned" in raw_low:
        return "Fixed–Pinned"
    if "pinned–fixed" in raw_low or "pinned-fixed" in raw_low:
        return "Pinned–Fixed"
    if "fixed–fixed" in raw_low or "fixed-fixed" in raw_low:
        return "Fixed-ended"
    if "continuous" in raw_low:
        return "Continuous – interior span"
    if raw_low in ("pinned–pinned", "pinned-pinned"):
        return "Pinned–Pinned"
    if "simply" in raw_low:
        return "Simply supported"
    if "pinned" in raw_low:
        return "Simply supported"
    return "Simply supported"


def _defl_support_type_from_design_selection(
    load_case: str | None, support_condition: str | None
) -> str:
    """
    Match sfd_bmd_page._defl_support_type_from_selection (single-span design model).
    Returns a label that _normalize_deflection_support_type understands.
    """
    case_text = (load_case or "").strip()
    cond = (support_condition or "").strip().replace("-", "–")
    if case_text == "Overhanging beam – right overhang with point load at free end":
        return "Simply supported"
    if cond == "Fixed–Free" or case_text.startswith("Cantilever"):
        return "Cantilever"
    if cond == "Simply supported":
        return "Simply supported"
    if cond == "Pinned–Pinned":
        return "Pinned–Pinned"
    if cond == "Fixed–Fixed":
        return "Fixed-ended"
    if cond == "Fixed–Pinned":
        return "Fixed–Pinned"
    if cond == "Pinned–Fixed":
        return "Pinned–Fixed"
    return _support_type_from_sfd_case(case_text)


def _deflection_support_options_for_value(resolved: str) -> list[str]:
    opts = list(DEFLECTION_SUPPORT_OPTIONS_BASE)
    if resolved in SUPPORT_DEFLECTION_MAP and resolved not in opts:
        opts = opts + [resolved]
    return opts


def _sync_design_deflection_support_widgets(resolved: str) -> None:
    """In design mode, keep all mapped widgets aligned with the resolved support type."""
    if str(st.session_state.get("actions_mode", "manual") or "manual") != "design":
        return
    for wk, sk in TAB_KEYS.items():
        if sk != "defl_support_type":
            continue
        try:
            if wk in st.session_state and st.session_state[wk] != resolved:
                st.session_state[wk] = resolved
        except Exception:
            pass


def _is_design_multispan_mode(state: dict) -> bool:
    mode = str(state.get("actions_mode", get_param("actions_mode", "manual")) or "manual").strip().lower()
    beam_mode = str(state.get("sfd_beam_system_mode", "") or "").strip()
    case_text = str(state.get("sfd_case", "") or "").strip()
    return mode == "design" and (
        beam_mode == "Multi-span" or case_text.startswith("Multi-span continuous beam")
    )


def _multispan_design_elastic_loads(source: dict) -> tuple[list[float], list[str], list[dict], list[dict], list[dict], list[dict]]:
    """
    Design-page multi-span model: characteristic (g+q) and sustained (g + ψ q) SLS loads
    for the same geometry the SFD/BMD page uses with ``solve_beam_structure``.
    """
    n_spans = int(float(source.get("sfd_span_count", 0.0) or 0.0))
    node_positions_m: list[float] = [0.0]
    for i in range(1, n_spans + 1):
        li = float(source.get(f"sfd_span_len_{i}", 0.0) or 0.0)
        node_positions_m.append(node_positions_m[-1] + max(0.0, li))
    support_types = [
        str(source.get(f"sfd_support_type_{j}", "Pinned") or "Pinned")
        for j in range(1, n_spans + 2)
    ]
    L_tot = float(node_positions_m[-1]) if node_positions_m else 0.0
    psi_point = float(source.get("load_psi_point", get_param("psi_point", 0.4)) or 0.4)
    psi_udl = float(source.get("load_psi_udl", get_param("psi_udl", 0.4)) or 0.4)
    n_point = int(float(source.get("sfd_ms_point_count", 0.0) or 0.0))
    pl_char: list[dict] = []
    pl_sust: list[dict] = []
    for i in range(1, max(0, n_point) + 1):
        G = float(source.get(f"load_ms_G_{i}", 0.0) or 0.0)
        Q = float(source.get(f"load_ms_Q_{i}", 0.0) or 0.0)
        x = float(source.get(f"load_ms_x_{i}", 0.0) or 0.0)
        x = max(node_positions_m[0], min(L_tot, x))
        pl_char.append({"x_m": x, "P_kN": G + Q})
        pl_sust.append({"x_m": x, "P_kN": G + psi_point * Q})
    n_udl = int(float(source.get("sfd_ms_udl_count", 0.0) or 0.0))
    udl_char: list[dict] = []
    udl_sust: list[dict] = []
    for i in range(1, max(0, n_udl) + 1):
        g = float(source.get(f"load_ms_g_{i}", 0.0) or 0.0)
        q = float(source.get(f"load_ms_q_{i}", 0.0) or 0.0)
        x0 = float(source.get(f"load_ms_x0_{i}", 0.0) or 0.0)
        x1 = float(source.get(f"load_ms_x1_{i}", L_tot) or 0.0)
        x0 = max(node_positions_m[0], min(L_tot, x0))
        x1 = max(node_positions_m[0], min(L_tot, x1))
        if x1 <= x0:
            continue
        udl_char.append({"x_start_m": x0, "x_end_m": x1, "w_kN_per_m": g + q})
        udl_sust.append({"x_start_m": x0, "x_end_m": x1, "w_kN_per_m": g + psi_udl * q})
    return node_positions_m, support_types, pl_char, udl_char, pl_sust, udl_sust


def _active_multispan_lengths_m(state: dict) -> list[float]:
    lengths: list[float] = []
    try:
        n_spans = int(float(state.get("sfd_span_count", 0.0) or 0.0))
    except Exception:
        n_spans = 0
    for i in range(1, n_spans + 1):
        try:
            li = float(state.get(f"sfd_span_len_{i}", 0.0) or 0.0)
        except Exception:
            li = 0.0
        lengths.append(max(0.0, li))
    return lengths


def compute_and_store_multispan_deflection_metrics(
    *,
    state: dict | None = None,
    Ec: float,
    Ief: float,
    g_kNm: float,
    q_kNm: float,
    psi_s: float,
    defl_limit_ratio: float,
    Ast: float = 0.0,
    Asc: float = 0.0,
) -> dict:
    """
    Canonical multispan governing metrics writer.

    Writes only:
    - defl_span_deflections_mm
    - defl_span_utilisations

    Primary path (design multispan): **elastic line from** ``beam_analysis.solve_beam_structure``
    with the same nodal geometry, support fixities (pinned/roller/fixed), point loads
    (G+Q and sustained G+ψQ), and UDL segments as the Design page — then
    δ(x) ≈ sag_char(x) + kₛₛ·sag_sus(x), and each span stores **max |δ|** within that span.

    Fallback: per-span ``calc_deflection_as3600`` with k₂ end/interior approximation
    if the FEM path fails.
    """
    source = state if isinstance(state, dict) else st.session_state

    if not _is_design_multispan_mode(source):
        source.pop("defl_span_deflections_mm", None)
        source.pop("defl_span_utilisations", None)
        source.pop("defl_multispan_metrics_source", None)
        return {"available": False, "reason": "not design multispan mode"}

    span_lengths = _active_multispan_lengths_m(source)
    if len(span_lengths) < 2:
        source.pop("defl_span_deflections_mm", None)
        source.pop("defl_span_utilisations", None)
        source.pop("defl_multispan_metrics_source", None)
        return {"available": False, "reason": "insufficient active spans"}

    try:
        ratio = float(get_deflection_limit_ratio(defl_limit_ratio))
    except Exception:
        ratio = 250.0
    if ratio <= 0:
        ratio = 250.0

    span_deflections_mm: list[float] = []
    span_utilisations: list[float] = []
    n_spans = len(span_lengths)
    span_g_inputs: list[float] = []
    span_q_inputs: list[float] = []
    for i in range(1, n_spans + 1):
        try:
            span_g_inputs.append(float(source.get(f"load_ms_g_{i}", 0.0) or 0.0))
        except Exception:
            span_g_inputs.append(0.0)
        try:
            span_q_inputs.append(float(source.get(f"load_ms_q_{i}", 0.0) or 0.0))
        except Exception:
            span_q_inputs.append(0.0)

    g_fallback = float(g_kNm)
    q_fallback = float(q_kNm)

    metrics_source = "multispan_fem_elastic"
    used_solver = False
    node_positions_m: list[float] = []
    try:
        from beam_analysis import solve_beam_structure

        node_positions_m, support_types_ms, pl_c, udl_c, pl_s, udl_s = (
            _multispan_design_elastic_loads(source)
        )
        if len(node_positions_m) >= 2 and len(support_types_ms) == len(node_positions_m):
            ei_knm2 = max(float(Ec) * float(Ief) / 1e9, 1e-12)
            res_c = solve_beam_structure(
                node_positions_m,
                support_types_ms,
                pl_c,
                udl_c,
                n_points_per_span=96,
                ei_knm2_for_deflection=ei_knm2,
            )
            res_s = solve_beam_structure(
                node_positions_m,
                support_types_ms,
                pl_s,
                udl_s,
                n_points_per_span=96,
                ei_knm2_for_deflection=ei_knm2,
            )
            w_c = res_c.get("w_mm")
            w_s = res_s.get("w_mm")
            x_sol = res_c.get("x")
            if (
                isinstance(w_c, list)
                and isinstance(w_s, list)
                and isinstance(x_sol, list)
                and len(w_c) == len(w_s) == len(x_sol)
                and len(w_c) > 0
            ):
                x_arr = np.asarray(x_sol, dtype=float)
                w_c_arr = np.asarray(w_c, dtype=float)
                w_s_arr = np.asarray(w_s, dtype=float)
                ratio_asc = (float(Asc) / float(Ast)) if float(Ast) > 0 else 0.0
                kcs_line = max(0.8, 2.0 - 1.2 * ratio_asc)
                # Nodal FE w_mm follows typical “positive up”; flip so sag is positive like δ in calc_deflection_as3600.
                sag_c_mm = -w_c_arr
                sag_s_mm = -w_s_arr
                delta_line_mm = sag_c_mm + kcs_line * sag_s_mm
                span_deflections_mm = []
                span_utilisations = []
                for idx, span_len_m in enumerate(span_lengths):
                    if span_len_m <= 0:
                        span_deflections_mm.append(0.0)
                        span_utilisations.append(0.0)
                        continue
                    x_left = float(node_positions_m[idx])
                    x_right = float(node_positions_m[idx + 1])
                    mask = (x_arr >= x_left - 1e-9) & (x_arr <= x_right + 1e-9)
                    if not np.any(mask):
                        span_deflections_mm.append(0.0)
                        span_utilisations.append(0.0)
                        continue
                    delta_abs = float(np.max(np.abs(delta_line_mm[mask])))
                    limit_mm = (float(span_len_m) * 1000.0) / ratio
                    util = (delta_abs / limit_mm) if limit_mm > 0 else 0.0
                    span_deflections_mm.append(delta_abs)
                    span_utilisations.append(util)
                used_solver = True
    except Exception:
        used_solver = False
        metrics_source = "multispan_fem_elastic_failed"

    if not used_solver:
        metrics_source = "per_span_k2_approx"
        span_deflections_mm = []
        span_utilisations = []
        for idx, span_len_m in enumerate(span_lengths):
            if span_len_m <= 0:
                span_deflections_mm.append(0.0)
                span_utilisations.append(0.0)
                continue

            span_support = (
                "Continuous – end span"
                if idx in (0, n_spans - 1)
                else "Continuous – interior span"
            )
            try:
                g_i = float(span_g_inputs[idx])
            except Exception:
                g_i = 0.0
            try:
                q_i = float(span_q_inputs[idx])
            except Exception:
                q_i = 0.0
            if (g_i + q_i) == 0.0 and (g_fallback + q_fallback) > 0.0:
                g_i, q_i = g_fallback, q_fallback

            calc = calc_deflection_as3600(
                L_m=float(span_len_m),
                Ec=float(Ec),
                Ief=float(Ief),
                g_kNm=g_i,
                q_kNm=q_i,
                psi_s=float(psi_s),
                support_type=span_support,
                Ast=float(Ast),
                Asc=float(Asc),
            )
            if isinstance(calc, dict) and not calc.get("ok", True):
                span_deflections_mm.append(0.0)
                span_utilisations.append(0.0)
                continue

            delta_abs = abs(float(calc.get("delta_total", 0.0) or 0.0))
            limit_mm = (float(span_len_m) * 1000.0) / ratio
            util = (delta_abs / limit_mm) if limit_mm > 0 else 0.0
            span_deflections_mm.append(delta_abs)
            span_utilisations.append(util)

    source["defl_span_deflections_mm"] = span_deflections_mm
    source["defl_span_utilisations"] = span_utilisations
    source["defl_multispan_metrics_source"] = metrics_source
    return {
        "available": True,
        "span_deflections_mm": span_deflections_mm,
        "span_utilisations": span_utilisations,
    }


def _pick_controlling_span_index(state: dict) -> tuple[int, str]:
    """
    Deterministic controlling-span selector for the diagram:
    1) span with max utilisation (if available)
    2) span with max deflection magnitude (if available)
    3) longest active span
    4) first active span
    """
    vals = state.get("defl_span_utilisations")
    if isinstance(vals, (list, tuple)) and vals:
        nums = []
        for i, v in enumerate(vals):
            try:
                nums.append((i, abs(float(v))))
            except Exception:
                pass
        if nums:
            idx = max(nums, key=lambda t: t[1])[0]
            return idx, "highest deflection utilisation"

    vals = state.get("defl_span_deflections_mm")
    if isinstance(vals, (list, tuple)) and vals:
        nums = []
        for i, v in enumerate(vals):
            try:
                nums.append((i, abs(float(v))))
            except Exception:
                pass
        if nums:
            idx = max(nums, key=lambda t: t[1])[0]
            return idx, "largest absolute deflection"

    span_lengths = []
    try:
        n_spans = int(float(state.get("sfd_span_count", 0.0) or 0.0))
    except Exception:
        n_spans = 0
    for i in range(1, n_spans + 1):
        try:
            li = float(state.get(f"sfd_span_len_{i}", 0.0) or 0.0)
        except Exception:
            li = 0.0
        span_lengths.append(max(0.0, li))
    if span_lengths:
        idx = max(range(len(span_lengths)), key=lambda i: span_lengths[i])
        return int(idx), "longest active span"

    return 0, "fallback"


def get_deflection_diagram_support_condition(state: dict | None = None) -> dict:
    """
    Single source of truth for deflection support (k₂ / F_d,ef / diagrams / summaries).

    - Manual mode: resolved from user ``defl_support_type`` (normalized).
    - Design + multi-span: Continuous end vs interior from controlling span index.
    - Design + single-span: derived from ``sfd_case`` + support condition. Prefer canonical
      ``design_support_condition`` (set_shared) over ``sfd_support_condition`` (widget can lag after edits).
      Beam system uses ``sfd_beam_system_mode`` or ``design_beam_system_mode``.
    """
    source = state if isinstance(state, dict) else st.session_state
    # Avoid treating missing/empty actions_mode as manual: dict.get skips get_param default when key exists.
    _am = source.get("actions_mode")
    if _am is None or (isinstance(_am, str) and _am.strip() == ""):
        _am = get_param("actions_mode", "manual")
    mode = str(_am or "manual").strip().lower()
    if mode not in ("manual", "design"):
        mode = "manual"
    # Early Deflection renders can compute mode as manual before session is consistent; trust global toggle.
    if is_design_governing():
        mode = "design"

    raw_widget = str(
        source.get("defl_support_type")
        or get_param("defl_support_type", "Simply supported")
        or "Simply supported"
    )
    canonical = _normalize_deflection_support_type(raw_widget)

    beam_mode = str(
        source.get("sfd_beam_system_mode")
        or source.get("design_beam_system_mode")
        or ""
    ).strip()
    raw_cf = raw_widget.strip().casefold()
    sfd_case_norm = str(source.get("sfd_case", "") or "").strip()
    # Multispan: prefer current Design-page beam system. Stale defl_support_type == "Continuous beam"
    # must not imply multispan when sfd_beam_system_mode is explicitly Single span.
    # (Manual mode still uses the same rule; resolution ignores is_multi on the manual branch.)
    if beam_mode == "Single span":
        is_multi = False
    elif beam_mode == "Multi-span":
        is_multi = True
    else:
        is_multi = (
            raw_cf == "continuous beam"
            or sfd_case_norm.startswith("Multi-span continuous beam")
        )

    controlling_idx = 0
    controlling_reason = "single-span"

    continuous_end_side = None
    _dbg_branch = ""
    _dbg_derived = None
    if mode == "manual":
        _dbg_branch = "manual"
        resolved = canonical
        controlling_idx, controlling_reason = 0, "manual selection"
    elif mode == "design" and is_multi:
        _dbg_branch = "design_multispan"
        controlling_idx, controlling_reason = _pick_controlling_span_index(source)
        try:
            n_spans = int(float(source.get("sfd_span_count", 0.0) or 0.0))
        except Exception:
            n_spans = 0
        if n_spans >= 2:
            resolved = (
                "Continuous – end span"
                if controlling_idx in (0, n_spans - 1)
                else "Continuous – interior span"
            )
            if controlling_idx == 0:
                continuous_end_side = "right"
            elif controlling_idx == n_spans - 1:
                continuous_end_side = "left"
        else:
            resolved = "Continuous – interior span"
    else:
        _dbg_branch = "design_single_span"
        load_case = str(source.get("sfd_case", "") or "")
        sfd_sup = source.get("sfd_support_condition")
        des_sup = source.get("design_support_condition")
        # Canonical design_* updates first on Design page; sfd_* widget value can stay stale one rerun.
        support_condition = des_sup or sfd_sup
        derived = _defl_support_type_from_design_selection(load_case, support_condition)
        _dbg_derived = derived
        resolved = _normalize_deflection_support_type(derived)
        controlling_idx, controlling_reason = 0, "design single-span (SFD)"

    support_type = _normalize_deflection_support_type(resolved)
    _sync_design_deflection_support_widgets(support_type)

    # region agent log
    if str(st.session_state.get("page_slug") or st.session_state.get("_active_page_slug") or "") == "deflection":
        _dbg_defl_support_ndjson(
            {
                "hypothesisId": "H_defl_support",
                "message": "support_resolution",
                "data": {
                    "fix_version": "distinct_fixed_pinned_k2+sketch+coalesce_v2",
                    "state_is_plain_dict": isinstance(state, dict),
                    "branch": _dbg_branch,
                    "mode": mode,
                    "beam_mode": beam_mode,
                    "is_multi": bool(is_multi),
                    "sfd_beam_system_mode": str(source.get("sfd_beam_system_mode", "")),
                    "design_beam_system_mode": str(source.get("design_beam_system_mode", "")),
                    "sfd_case_prefix": (str(source.get("sfd_case", "") or "")[:50]),
                    "sfd_support_condition": repr(source.get("sfd_support_condition")),
                    "design_support_condition": repr(source.get("design_support_condition")),
                    "support_condition_coalesced": repr(
                        source.get("design_support_condition")
                        or source.get("sfd_support_condition")
                    ),
                    "sfd_vs_design_conflict": bool(
                        source.get("sfd_support_condition") is not None
                        and source.get("design_support_condition") is not None
                        and str(source.get("sfd_support_condition")).strip()
                        != str(source.get("design_support_condition")).strip()
                    ),
                    "derived": repr(_dbg_derived),
                    "resolved_before_final_norm": repr(resolved),
                    "support_type_out": support_type,
                },
            }
        )
    # endregion

    out = {
        "support_type": support_type,
        "mode": mode,
        "canonical_support_type": canonical,
        "multi_span": bool(is_multi),
        "controlling_span_idx": int(max(0, controlling_idx)),
        "controlling_reason": controlling_reason,
        "continuous_end_side": continuous_end_side,
    }
    if _DEBUG_DEFLECTION_SUPPORT_RESOLUTION:
        try:
            print(
                "DEFLECTION_SUPPORT_RESOLUTION",
                {
                    "mode": out["mode"],
                    "actions_source": str(source.get("actions_source", "")),
                    "raw_defl_support_type": str(source.get("defl_support_type", "")),
                    "raw_sfd_beam_system_mode": str(source.get("sfd_beam_system_mode", "")),
                    "raw_sfd_support_condition": str(source.get("sfd_support_condition", "")),
                    "canonical": out["canonical_support_type"],
                    "multi_span": out["multi_span"],
                    "controlling_span_idx": out["controlling_span_idx"],
                    "controlling_reason": out["controlling_reason"],
                    "resolved": out["support_type"],
                },
            )
        except Exception:
            pass
    return out


def get_resolved_deflection_support_type(state: dict | None = None) -> str:
    """Resolved support label for deflection — use instead of raw ``defl_support_type`` in calcs/summaries."""
    return get_deflection_diagram_support_condition(state)["support_type"]


def _governing_span_support_pair(state: dict, support_resolution: dict) -> tuple[str, str] | None:
    try:
        if str(support_resolution.get("mode", "")).strip().lower() != "design":
            return None
        if not bool(support_resolution.get("multi_span")):
            return None
        n_spans = int(float(state.get("sfd_span_count", 0.0) or 0.0))
        if n_spans < 1:
            return None
        idx = int(support_resolution.get("controlling_span_idx", 0) or 0)
        idx = max(0, min(idx, n_spans - 1))
        left_i = idx + 1
        right_i = idx + 2
        left = str(state.get(f"sfd_support_type_{left_i}", "Pinned") or "Pinned")
        right = str(state.get(f"sfd_support_type_{right_i}", "Pinned") or "Pinned")
        return (left, right)
    except Exception:
        return None


def _support_props(support_type: str) -> dict:
    return SUPPORT_DEFLECTION_MAP.get(
        support_type, SUPPORT_DEFLECTION_MAP["Simply supported"]
    )


def _add_deflection_supports_plotly(
    fig: go.Figure,
    support_type: str | None,
    L_mm: float,
    D_mm: float,
    support_pair: tuple[str, str] | None = None,
) -> None:
    """
    Illustrative supports under the undeformed beam (bottom fibre y = -D_mm).

    Drawing-only (no change to k₂ or analysis):
    - Simply supported: pin + roller; span terminates at supports (no overhang).
    - Cantilever: fixed wall at one end only.
    - Fixed-ended: fixed (hatched) walls both ends.
    - Fixed–Pinned / Pinned–Fixed: fixed at one end, pin + roller at the other (design order).
    - Continuous – end span: pins at both ends (beam body extension is drawn in
      ``build_deflected_beam_plotly``). Interior continuity on the **right**.
    - Continuous – interior span: pins at both ends; extension on both sides from
      ``build_deflected_beam_plotly``.
    """
    st_val = (support_type or "").strip()
    y_bot = -float(D_mm)
    L_mm = float(L_mm)
    support_w = max(0.02 * float(L_mm), 18.0)
    support_d = max(0.12 * float(D_mm), 10.0)
    hatch_dx = max(0.015 * float(L_mm), 12.0)
    roller_r = max(0.04 * float(D_mm), 5.0)

    def _pinned(x_pos: float, *, roller: bool) -> None:
        y_base = y_bot - support_d
        y_ground = y_base - max(0.12 * float(D_mm), 8.0)
        fig.add_shape(
            type="path",
            path=(
                f"M {x_pos - support_w},{y_base} L {x_pos + support_w},"
                f"{y_base} L {x_pos},{y_bot} Z"
            ),
            line=dict(color="rgba(35,35,35,1.0)", width=1.4),
            fillcolor="rgba(35,35,35,0.12)",
            layer="below",
        )
        fig.add_shape(
            type="line",
            x0=x_pos - support_w * 1.15,
            y0=y_ground,
            x1=x_pos + support_w * 1.15,
            y1=y_ground,
            line=dict(color="rgba(80,80,80,0.85)", width=1.0),
            layer="below",
        )
        if roller:
            fig.add_shape(
                type="circle",
                xref="x",
                yref="y",
                x0=x_pos - roller_r,
                y0=y_base - support_d * 0.45 - roller_r,
                x1=x_pos + roller_r,
                y1=y_base - support_d * 0.45 + roller_r,
                line=dict(color="rgba(35,35,35,1.0)", width=1.2),
                fillcolor="rgba(255,255,255,0.55)",
                layer="below",
            )

    def _fixed(x_pos: float) -> None:
        y_min = y_bot - 0.55 * float(D_mm)
        y_max = 0.55 * float(D_mm)
        fig.add_shape(
            type="line",
            x0=x_pos,
            y0=y_min,
            x1=x_pos,
            y1=y_max,
            line=dict(color="rgba(35,35,35,1.0)", width=6),
            layer="below",
        )
        for frac in (0.08, 0.28, 0.48, 0.68, 0.88):
            y_val = y_min + frac * (y_max - y_min)
            fig.add_shape(
                type="line",
                x0=x_pos - hatch_dx,
                y0=y_val + 0.10 * float(D_mm),
                x1=x_pos,
                y1=y_val - 0.04 * float(D_mm),
                line=dict(color="rgba(80,80,80,0.82)", width=1.0),
                layer="below",
            )

    def _draw_support_from_label(x_pos: float, label: str, *, right_edge: bool = False) -> None:
        l = str(label or "Pinned").strip().lower()
        if l == "fixed":
            _fixed(x_pos)
        elif l == "roller":
            _pinned(x_pos, roller=True)
        else:
            # For right-end pinned in a simple-support view, keep roller convention.
            _pinned(x_pos, roller=bool(right_edge and st_val == "Simply supported"))

    if isinstance(support_pair, tuple) and len(support_pair) == 2:
        left_lbl = str(support_pair[0] or "Pinned")
        right_lbl = str(support_pair[1] or "Pinned")
        _draw_support_from_label(0.0, left_lbl, right_edge=False)
        _draw_support_from_label(float(L_mm), right_lbl, right_edge=True)
        return

    if st_val == "Cantilever":
        _fixed(0.0)
    elif st_val == "Fixed-ended":
        _fixed(0.0)
        _fixed(float(L_mm))
    elif st_val == "Fixed–Pinned":
        _fixed(0.0)
        _pinned(float(L_mm), roller=True)
    elif st_val == "Pinned–Fixed":
        _pinned(0.0, roller=False)
        _fixed(float(L_mm))
    elif st_val == "Continuous – end span":
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=False)
    elif st_val == "Continuous – interior span":
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=False)
    elif st_val == "Pinned–Pinned":
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=False)
    else:
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=True)


def deflected_longitudinal_profile_mm(
    L_mm: float,
    support_type: str | None,
    delta_total: float,
    n_pts: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Spanwise mesh and longitudinal deflection w (mm, negative sag), using the same
    normalised curvature template as the Deflection page diagram.
    """
    L_mm = float(L_mm)
    if L_mm <= 0.0 or not math.isfinite(L_mm):
        return np.array([0.0], dtype=float), np.array([0.0], dtype=float)
    delta_total = float(delta_total)
    if not math.isfinite(delta_total):
        delta_total = 0.0
    n_pts = max(2, int(n_pts))
    x = np.linspace(0.0, L_mm, n_pts)
    xi = x / L_mm
    shape_kind = _support_props(support_type).get(
        "diagram", "simply_supported_udl"
    )
    if shape_kind == "cantilever_udl":
        shape = xi**2 * (3.0 - 2.0 * xi)
    elif shape_kind in (
        "continuous_span_udl",
        "fixed_fixed_udl",
        "fixed_pinned_udl",
    ):
        shape = (4.0 * xi * (1.0 - xi)) ** 2
    else:
        shape = 4.0 * xi * (1.0 - xi)
    shape = shape / max(float(np.max(shape)), 1.0)
    y_long = -delta_total * shape
    return x, y_long


def build_deflected_beam_plotly(
    x_mm,
    w_mm,
    L_mm,
    D_mm,
    support_type: str | None = None,
    continuous_end_side: str | None = None,
    support_pair: tuple[str, str] | None = None,
    *,
    undeformed_fillcolor: str | None = None,
    undeformed_line: dict | None = None,
    deflected_fillcolor: str | None = None,
    deflected_line: dict | None = None,
    show_legend: bool = True,
) -> go.Figure:
    """
    Illustrative deflected beam: undeformed and deflected rectangular bodies with vertical exaggeration.
    Hover on the deflected top fibre shows actual (unscaled) deflection from w_mm.
    """
    x = np.asarray(x_mm, dtype=float).reshape(-1)
    w = np.asarray(w_mm, dtype=float).reshape(-1)
    L_mm = float(L_mm)
    D_mm = float(max(D_mm, 1.0))

    # Drawing-only: extend mesh past interior supports so undeformed + deflected
    # fills (and blue outline) show continuity, matching pin positions at 0 and L_mm.
    st_val = (support_type or "").strip()
    if x.size:
        _stub = max(0.025 * L_mm, 20.0)
        if st_val == "Continuous – interior span":
            x0 = float(x[0])
            if x0 > -_stub + 1e-6:
                left_pts = np.linspace(-_stub, x0, 8, endpoint=False)
                if left_pts.size:
                    x = np.r_[left_pts, x]
                    w = np.r_[np.full_like(left_pts, w[0]), w]
        if st_val == "Continuous – end span" and str(continuous_end_side or "right").lower() == "left":
            x0 = float(x[0])
            if x0 > -_stub + 1e-6:
                left_pts = np.linspace(-_stub, x0, 8, endpoint=False)
                if left_pts.size:
                    x = np.r_[left_pts, x]
                    w = np.r_[np.full_like(left_pts, w[0]), w]
        if st_val == "Continuous – end span" and str(continuous_end_side or "right").lower() != "left":
            xn = float(x[-1])
            right_pts = np.linspace(xn, xn + _stub, 8)[1:]
            if right_pts.size:
                x = np.r_[x, right_pts]
                w = np.r_[w, np.full_like(right_pts, w[-1])]
        if st_val == "Continuous – interior span":
            xn = float(x[-1])
            right_pts = np.linspace(xn, xn + _stub, 8)[1:]
            if right_pts.size:
                x = np.r_[x, right_pts]
                w = np.r_[w, np.full_like(right_pts, w[-1])]

    max_abs_defl = float(np.max(np.abs(w))) if w.size else 0.0
    target_visual_drop = max(0.20 * D_mm, 35.0)
    if max_abs_defl <= 1e-15:
        scale_factor = 1.0
    else:
        raw_sf = target_visual_drop / max_abs_defl
        scale_factor = min(max(raw_sf, 1.0), 40.0)
    w_vis = w * scale_factor

    x_poly = np.r_[x, x[::-1], x[:1]]
    y_undeformed_poly = np.r_[np.zeros_like(
        x), (-D_mm) * np.ones_like(x)[::-1], [0.0]]
    y_deformed_poly = np.r_[w_vis, (w_vis - D_mm)[::-1], [w_vis[0]]]

    sf_display = f"{scale_factor:g}"

    _u_fill = (
        undeformed_fillcolor
        if undeformed_fillcolor is not None
        else "rgba(210,210,210,0.22)"
    )
    _u_line = (
        undeformed_line
        if undeformed_line is not None
        else dict(color="rgba(140,140,140,0.95)", width=1.5, dash="dash")
    )
    _d_fill = (
        deflected_fillcolor
        if deflected_fillcolor is not None
        else "rgba(31,119,180,0.30)"
    )
    _d_line = (
        deflected_line
        if deflected_line is not None
        else dict(color="rgba(31,119,180,1.0)", width=2)
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x_poly,
            y=y_undeformed_poly,
            fill="toself",
            mode="lines",
            line=_u_line,
            fillcolor=_u_fill,
            name="Undeformed beam",
            hoverinfo="skip",
            legendgroup="u",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_poly,
            y=y_deformed_poly,
            fill="toself",
            mode="lines",
            line=_d_line,
            fillcolor=_d_fill,
            name="Deflected beam",
            hoverinfo="skip",
            legendgroup="d",
        )
    )

    custom = np.column_stack([x, w])
    fig.add_trace(
        go.Scatter(
            x=x,
            y=w_vis,
            mode="lines",
            line=dict(color="rgba(0,0,0,0)", width=16),
            customdata=custom,
            hovertemplate="x = %{customdata[0]:.1f} mm<br>δ (actual) = %{customdata[1]:.2f} mm<extra></extra>",
            name="Deflection (hover)",
            showlegend=False,
        )
    )

    if w.size:
        i_max = int(np.argmax(np.abs(w)))
        dmax_actual = float(w[i_max])
        fig.add_trace(
            go.Scatter(
                x=[x[i_max]],
                y=[w_vis[i_max]],
                mode="markers",
                marker=dict(
                    size=11,
                    color="#c0392b",
                    symbol="circle",
                    line=dict(width=1, color="white"),
                ),
                name="Max |δ|",
                hovertemplate=(
                    f"Δmax = {dmax_actual:.2f} mm (actual)<extra></extra>"
                ),
            )
        )
        fig.add_annotation(
            x=x[i_max],
            y=w_vis[i_max],
            text=f"Δmax = {dmax_actual:.2f} mm",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            axref="pixel",
            ayref="pixel",
            ax=48,
            ay=-42,
            font=dict(size=11, color="#333"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="rgba(0,0,0,0.15)",
            borderwidth=1,
            borderpad=4,
        )

    _add_deflection_supports_plotly(fig, support_type, L_mm, D_mm, support_pair=support_pair)

    fig.update_layout(
        title=dict(
            text=(
                f"Deflected shape (illustrative, vertical exaggeration ×{sf_display}; "
                "hover shows actual deflection)"
            ),
            x=0.5,
            xanchor="center",
            font=dict(size=13, color="#222"),
        ),
        xaxis_title="Span position x (mm)",
        yaxis_title="Illustrated vertical position (mm)",
        template="simple_white",
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=420,
        margin=dict(l=64, r=48, t=72, b=56),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.10)",
            zeroline=False,
            range=[-0.03 * L_mm, L_mm * 1.03] if L_mm > 0 else None,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.10)",
            zeroline=True,
            zerolinecolor="rgba(0,0,0,0.22)",
            zerolinewidth=1,
        ),
        hovermode="closest",
    )
    return fig


def _support_type_from_sfd_case(case: str) -> str:
    case = (case or "").strip()
    if case.startswith("Cantilever"):
        return "Cantilever"
    if case.startswith("Simple beam"):
        return "Simply supported"
    if case.startswith("Overhanging beam"):
        return "Simply supported"
    return "Simply supported"


def _seed_from_param(name: str, fallback: float) -> float:
    """Read numeric from shared state with get_param(name), with fallback."""
    try:
        v = get_param(name)
    except TypeError:
        v = None

    try:
        if v is None:
            return float(fallback)
        v = float(v)
        if math.isnan(v):
            return float(fallback)
        return v
    except Exception:
        return float(fallback)


def _render_readonly_value(
    label: str,
    value,
    unit: str,
    help_text: str | None = None,
):
    """
    Render a read-only value with label and optional help text.
    Uses the same styling as other read-only inputs.
    """
    col1, col2 = st.columns([1, 2])
    with col1:
        label_with_hover(label, help_text)
    with col2:
        if value is None:
            display_value = "—"
            color_style = "color: #999;"
        else:
            if isinstance(value, float):
                if unit == "mm":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "mm²":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "MPa":
                    display_value = f"{value:.2f} {unit}"
                else:
                    display_value = f"{value:.1f} {unit}"
            else:
                display_value = f"{value} {unit}" if unit else str(value)
            color_style = ""

        st.markdown(
            f"""
<div class="readonly-param" style="padding: 0.5rem 0.75rem; margin: 0;">
  <div class="readonly-param-value" style="font-size: 1rem; margin: 0; {color_style}">{display_value}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _derive_equiv_udl_from_actions(M_kNm, V_kN, L_m, support_type):
    """
    Derive equivalent full-span UDL (kN/m) from M* and/or V*.
    Accept zeros; only None is treated as missing.
    """
    note_parts = []
    # Guard: L_m must be plausible (m, not mm)
    if L_m is None:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m missing",
        }
    try:
        L_m = float(L_m)
    except Exception:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m not numeric",
        }
    if not math.isfinite(L_m):
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m not finite",
        }
    if L_m > 50:
        note_parts.append(
    f"WARNING: L_m={L_m} looks like mm, not m (expected ~0–50).")
        # Do not auto-convert silently; return None so caller can fall back to
        # g+q.
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": " ".join(note_parts),
        }
    if L_m <= 0:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m must be > 0",
        }

    # ---- Coefficients by support type ----
    support = (support_type or "").strip()
    if support == "Cantilever":
        aM, aV = 2.0, 1.0
        # UDL consistency for cantilever: M ≈ V*L/2
        cons_M = lambda V: (V * L_m / 2.0)
    else:
        # Treat simply supported + continuous using SS coefficients
        aM, aV = 8.0, 2.0
        # UDL consistency for simply supported: M ≈ V*L/4
        cons_M = lambda V: (V * L_m / 4.0)

    # ---- Accept zeros; only None is “missing” ----
    wM = None
    wV = None
    if M_kNm is not None and math.isfinite(float(M_kNm)):
        M_abs = abs(float(M_kNm))
        wM = aM * M_abs / (L_m ** 2)
    if V_kN is not None and math.isfinite(float(V_kN)):
        V_abs = abs(float(V_kN))
        wV = aV * V_abs / L_m

    # ---- Combine / select ----
    if wM is None and wV is None:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "No M or V provided",
        }
    if wM is None:
        return {
            "w_kN_per_m": wV,
            "w_from_M": None,
            "w_from_V": wV,
            "consistent": None,
            "note": "Derived from V only",
        }
    if wV is None:
        return {
            "w_kN_per_m": wM,
            "w_from_M": wM,
            "w_from_V": None,
            "consistent": None,
            "note": "Derived from M only",
        }

    # Both exist: check consistency with UDL model
    M_implied = cons_M(abs(float(V_kN)))
    M_provided = abs(float(M_kNm))
    if M_implied > 0:
        ratio = M_provided / M_implied
        consistent = (0.85 <= ratio <= 1.15)
    else:
        ratio = None
        consistent = None

    if ratio is not None:
        note_parts.append(
            f"M/V UDL consistency ratio = {ratio:.2f} (≈1 means consistent full-span UDL).")

    if consistent is True:
        w = 0.5 * (wM + wV)
        note_parts.append("M and V consistent → using average(wM, wV).")
    else:
        w = max(wM, wV)
        note_parts.append(
            "M and V not consistent with full-span UDL → using max(wM, wV) (conservative).")

    return {
        "w_kN_per_m": w,
        "w_from_M": wM,
        "w_from_V": wV,
        "consistent": consistent,
        "note": " ".join(note_parts),
    }


def has_udl_line_loads(g_udl: float | None, q_udl: float | None) -> bool:
    """True when explicit dead + live line UDLs (kN/m) sum to a positive value."""
    return float(g_udl or 0.0) + float(q_udl or 0.0) > 0.0


def resolve_deflection_equiv_loads_from_inputs(
    *,
    derived: dict,
    w_sls: float | None,
    g_udl: float | None,
    q_udl: float | None,
) -> tuple[float, float]:
    """
    Map SLS-derived / stored UDL inputs to (g_equiv, q_equiv) for calc_deflection_as3600.

    ``derived`` must be the dict from ``_derive_equiv_udl_from_actions`` for the same inputs.
    """
    if derived["w_kN_per_m"] is not None:
        w_used = float(derived["w_kN_per_m"])
    elif w_sls is not None:
        w_used = float(w_sls)
    else:
        w_used = float((g_udl or 0.0) + (q_udl or 0.0))

    if w_used > 0:
        if g_udl is not None and q_udl is not None and (float(g_udl) + float(q_udl)) > 0:
            g_ratio = float(g_udl) / float(float(g_udl) + float(q_udl))
            g_equiv = w_used * g_ratio
            q_equiv = w_used * (1.0 - g_ratio)
        else:
            g_equiv = w_used
            q_equiv = 0.0
    else:
        g_equiv = float(g_udl or 0.0)
        q_equiv = float(q_udl or 0.0)
    return g_equiv, q_equiv


def deflection_has_service_load_for_calc() -> bool:
    """
    True when the resolved service UDL model has positive total load (g_equiv + q_equiv),
    matching ``compute_deflection_results`` / the Deflection page.
    """
    g_udl = get_param("g_udl_kNm_per_m", None)
    q_udl = get_param("q_udl_kNm_per_m", None)
    w_sls = get_param("w_sls_kNm_per_m", None)
    sls_M_kNm = get_param("sls_Mstar", 0.0)
    sls_V_kN = get_param("sls_Vstar", 0.0)
    L = get_param("L", 3000.0)
    L_m = float(L or 0.0) / 1000.0
    L_m_for_fd = get_param("defl_L_eff", L_m)
    if L_m_for_fd is None or L_m_for_fd <= 0:
        L_m_for_fd = get_param("span_L_m", L_m)
    if L_m_for_fd is None:
        L_m_for_fd = 0.0
    support_type = get_deflection_diagram_support_condition(st.session_state).get(
        "support_type", "Simply supported"
    )
    derived = _derive_equiv_udl_from_actions(
        M_kNm=sls_M_kNm,
        V_kN=sls_V_kN,
        L_m=float(L_m_for_fd),
        support_type=str(support_type),
    )
    g_eq, q_eq = resolve_deflection_equiv_loads_from_inputs(
        derived=derived,
        w_sls=w_sls,
        g_udl=g_udl,
        q_udl=q_udl,
    )
    return (float(g_eq) + float(q_eq)) > 1e-12


# ------------------------------------------------------------
#  Deflection helper: map load case → closed-form δ formula
# ------------------------------------------------------------
def _deflection_from_sfd_case(
    case: str,
    L: float,
    w_eff: float | None,
    P_sls: float | None,
    E: float,
    I: float,
):
    """
    Returns (delta_max, latex_formula, location_text) for classic SLS load cases.

    Assumes:
      - L in your length unit
      - w_eff in force/length
      - P_sls in force
      - E, I consistent with your deflection units
    """
    delta_max = None
    formula = r"\text{No closed-form deflection linked for this case yet.}"
    location = "—"

    # 1. Simple beam – UDL over entire span
    if case == "Simple beam – UDL over entire span" and w_eff is not None:
        # δ_max = 5 w L^4 / (384 E I) at midspan
        delta_max = 5.0 * w_eff * L**4 / (384.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{5 w L^4}{384 E I}"
            r"\quad\text{(simply supported, full UDL, midspan)}"
        )
        location = "At midspan (x = L/2)"

    # 2. Simple beam – point load at centre
    elif case == "Simple beam – point load at centre" and P_sls is not None:
        # δ_max = P L^3 / (48 E I)
        delta_max = P_sls * L**3 / (48.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{P L^3}{48 E I}"
            r"\quad\text{(simply supported, centre point load)}"
        )
        location = "At midspan (x = L/2)"

    # 3. Cantilever – point load at free end
    elif case == "Cantilever – point load at free end" and P_sls is not None:
        # δ_max = P L^3 / (3 E I)
        delta_max = P_sls * L**3 / (3.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{P L^3}{3 E I}"
            r"\quad\text{(cantilever, end point load)}"
        )
        location = "At free end (x = L)"

    # 4. Cantilever – UDL over entire span
    elif case == "Cantilever – UDL over entire span" and w_eff is not None:
        # δ_max = w L^4 / (8 E I)
        delta_max = w_eff * L**4 / (8.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{w L^4}{8 E I}"
            r"\quad\text{(cantilever, full UDL)}"
        )
        location = "At free end (x = L)"

    # Other cases (partial UDL, eccentric point load, overhang etc.) can be
    # added later.

    return delta_max, formula, location


# ------------------------------------------------------------
#  Core deflection helpers (AS 3600:2018 Cl. 8.5)
# ------------------------------------------------------------
def calc_ief_simplified(fc, beff, bw, d, Ast):
    """
    AS 3600:2018 Cl. 8.5.3.1(2),(3) simplified Ief for reinforced members.
    """
    beff = max(beff, 1.0)
    bw = max(bw, 1.0)
    d = max(d, 1.0)
    fc = max(fc, 1.0)

    beta = beff / bw
    p = Ast / (beff * d) if beff * d > 0 else 0.0  # reinforcement ratio
    p_lim = 0.001 * (fc ** (1.0 / 3.0)) / (beta ** (2.0 / 3.0))

    if p >= p_lim:
        # Eqn (8.5.3.1(2)) type
        k1 = (5.0 - 0.04 * fc) * p + 0.002
        ief = k1 * beff * (d ** 3)
        ief_max = (0.1 / (beta ** (2.0 / 3.0))) * beff * (d ** 3)
    else:
        # Eqn (8.5.3.1(3)) type
        k1 = (0.055 * (fc ** (1.0 / 3.0)) / (beta ** (2.0 / 3.0))) - 50.0 * p
        ief = k1 * beff * (d ** 3)
        ief_max = (0.06 / (beta ** (2.0 / 3.0))) * beff * (d ** 3)

    ief = min(ief, ief_max)
    return max(ief, 0.0), beta, p, p_lim, max(ief_max, 0.0), max(k1, 0.0)


def calc_deflection_as3600(
    L_m,
    Ec,
    Ief,
    g_kNm,
    q_kNm,
    psi_s,
    support_type,
    Ast,
    Asc,
):
    """Return dict with short-term, long-term components and total deflection (mm)."""
    if L_m is None:
        return {
            "ok": False,
            "error": "Effective span is missing (L_m is None).",
        }
    try:
        L_m = float(L_m)
    except Exception:
        return {"ok": False, "error": "Effective span is not a valid number."}
    if L_m <= 0:
        return {"ok": False, "error": "Effective span must be > 0."}
    L_mm = L_m * 1000.0
    L4 = L_mm ** 4
    Ief = max(Ief, 1.0)
    Ec = max(Ec, 1.0)

    k2 = _support_props(support_type).get("k2", 5.0 / 384.0)

    # kN/m → N/mm (1 kN/m = 1 N/mm numerically)
    w_total = g_kNm + q_kNm
    w_sust = g_kNm + psi_s * q_kNm

    delta_short_total = k2 * w_total * L4 / (Ec * Ief)
    delta_short_sust = k2 * w_sust * L4 / (Ec * Ief)

    ratio_Asc_Ast = (Asc / Ast) if Ast > 0 else 0.0
    kcs = 2.0 - 1.2 * ratio_Asc_Ast
    kcs = max(kcs, 0.8)

    delta_long_add = kcs * delta_short_sust
    delta_total = delta_short_total + delta_long_add

    return dict(
        L_mm=L_mm,
        k2=k2,
        w_total=w_total,
        w_sust=w_sust,
        delta_short_total=delta_short_total,
        delta_short_sust=delta_short_sust,
        kcs=kcs,
        delta_long_add=delta_long_add,
        delta_total=delta_total,
    )


def calc_span_depth_limit(
    ief,
    beff,
    bw,
    d,
    fc,
    Ec,
    Fdef_kNm,
    support_type,
    defl_limit_ratio,
):
    """
    Deemed-to-conform span/depth ratio from AS 3600:2018 Cl. 8.5.4.
    Returns (L_over_d_limit, k1, k2).
    """
    # Guard against None values to prevent TypeError
    beff = max(beff if beff is not None else 1.0, 1.0)
    bw = max(bw if bw is not None else 1.0, 1.0)
    d = max(d if d is not None else 1.0, 1.0)
    Ec = max(Ec if Ec is not None else 1.0, 1.0)
    ief = max(ief if ief is not None else 1.0, 1.0)
    fc = fc if fc is not None else 32.0
    Fdef_kNm = Fdef_kNm if Fdef_kNm is not None else 0.0
    defl_limit_ratio = defl_limit_ratio if defl_limit_ratio is not None else 250.0

    k1 = ief / (beff * (d ** 3))

    k2 = _support_props(support_type).get("k2", 5.0 / 384.0)

    delta_over_L = 1.0 / defl_limit_ratio if defl_limit_ratio > 0 else 0.0
    Fdef = Fdef_kNm

    if Fdef <= 0 or delta_over_L <= 0:
        return None, k1, k2

    inside = (k1 * delta_over_L * beff * Ec) / (k2 * Fdef)
    if inside <= 0:
        return None, k1, k2

    L_over_d_limit = inside ** (1.0 / 3.0)
    return L_over_d_limit, k1, k2


def format_L_over_delta(delta_mm, L_mm):
    if delta_mm <= 0:
        return "–"
    ratio = L_mm / delta_mm
    if ratio <= 0:
        return "–"
    return f"L/{ratio:,.0f}"


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_deflection():
    """Deflection page – short-term, long-term, span/depth to AS 3600:2018 Cl. 8.5."""
    # NOTE: init_shared_session_state() is called by app.py router before this
    # function runs.

    # Pages must NOT call init/hydrate themselves - the router owns the
    # lifecycle.

    sync_callbacks = get_sync_callbacks()

    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()

    apply_global_widget_css()
    apply_result_page_css()
    apply_calcbox_css()
    apply_step_summary_expander_css()
    sync_callbacks = get_sync_callbacks()  # not used yet but kept for contract

    # CSS for readonly-param styling (for linked values)
    st.markdown(
        """
<style>
/* Read-only linked-parameter chips */
.readonly-param {
  border-left: 4px solid #6c757d;
  background-color: rgba(108, 117, 125, 0.08);
  padding: 0.4rem 0.6rem;
  margin-bottom: 0.4rem;
  border-radius: 0 0.35rem 0.35rem 0;
  font-size: 0.85rem;
}
.readonly-param-value {
  font-weight: 500;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # Initialize step UI state (matches Shear pattern)
    init_step_ui_state("deflection")

    def _render_deflection_explainer() -> None:
        st.markdown(
            """
This page checks **reinforced concrete beam deflections** to AS 3600:2018:

- Short-term deflection
- Long-term deflection using **kₛₛ**
- Deemed-to-conform **span-to-depth ratio**
- **Simplified effective stiffness** \\(I_{ef}\\) for reinforced members
            """
        )

    render_result_page_title("Beam Deflection")

    if not deflection_has_service_load_for_calc():
        st.info("No loads applied — deflection not calculated")

    # Reserve space for the top summary table
    summary_placeholder = st.empty()

    # --- Hydrate deflection page widget keys from shared (only if missing/None) ---
    def _seed_widget_from_shared(
        widget_key: str,
        shared_key: str,
        fallback: float = 0.0,
    ):
        if widget_key not in st.session_state or st.session_state[widget_key] is None:
            v = get_param(shared_key, fallback)
            st.session_state[widget_key] = fallback if v is None else v

    _seed_widget_from_shared("defl_b", "b", 0.0)
    _seed_widget_from_shared("defl_D", "D", 0.0)
    _seed_widget_from_shared("defl_L", "L", 0.0)
    _seed_widget_from_shared("defl_fc", "fc", 0.0)
    defl_support_widget_key = (
        get_widget_key_for_shared("defl_support_type", prefix="defl_")
        or "defl_defl_support_type"
    )
    _seed_widget_from_shared(defl_support_widget_key, "defl_support_type", "Simply supported")
    defl_limit_widget_key = (
        get_widget_key_for_shared("defl_limit_ratio", prefix="defl_")
        or "defl_defl_limit_ratio"
    )
    _seed_widget_from_shared(defl_limit_widget_key, "defl_limit_ratio", 250.0)
    # ---------- Actions from Inputs page ----------
    actions_source = get_param(
        "actions_source",
        "Manual design actions (inputs below)",
    )
    is_design_driven = (
        "Teaching" in actions_source
        or actions_source == "Teaching SFD/BMD page (|M|max, |V|max)"
    )

    # Deflection always uses SLS actions (manual inputs)
    M_used = get_param("sls_Mstar", 0.0)
    V_used = get_param("sls_Vstar", 0.0)

    # Also get the final chosen values (SLS actions for display/other uses)
    Mu_star = get_param("sls_Mstar", 0.0)
    Vu_star = get_param("sls_Vstar", 0.0)

    # ---------- Unified loading from SFD/BMD page ----------
    load_case = st.session_state.get("load_case", None)
    L_sfd = get_param("span_L_m", None)  # span in m

    # Get SLS loads (either UDL or point load depending on case)
    w_sls = get_param("w_sls_kNm_per_m", None)  # SLS UDL if applicable
    P_sls = get_param("P_sls_kN", None)  # SLS point load if applicable
    a = get_param("a_m", None)  # Distance a for point loads

    # For display in calcbox (fallback values)
    g = get_param("g_udl_kNm_per_m", 0.0)
    q = get_param("q_udl_kNm_per_m", 0.0)
    psi_s = get_param("psi_udl", 0.4)
    G_point = get_param("G_point_kN", 0.0)
    Q_point = get_param("Q_point_kN", 0.0)

    # Determine effective load for deflection
    w_eff = w_sls if w_sls is not None else None

    # Deflected shape slot (filled after inputs + reo + compute in this run).
    diagram_placeholder = st.empty()

    st.markdown("**Design inputs**")

    # Helper function for label-left / widget-right layout with hover help
    def _input_row(label: str, help_text: str | None, render_widget_fn):
        c1, c2 = st.columns([1.2, 1.0])
        with c1:
            label_with_hover(label, help_text)
        with c2:
            return render_widget_fn()

    def _derive_fd_ef(
        actions_source: str,
        support_type_value: str,
        L_m_value: float | None,
        V_manual_kN: float | None,
        V_design_kN: float | None,
        fallback_value: float,
    ) -> tuple[float, str, str, dict]:
        """Derive F_d,ef from action source with explicit branch tracking."""
        is_manual = actions_source == "Manual design actions (inputs below)"
        is_design = (
            "Teaching" in actions_source
            or actions_source == "Teaching SFD/BMD page (|M|max, |V|max)"
        )

        branch = "fallback"
        source_text = "Fallback value used because derivation inputs were unavailable."
        meta = {
            "V_kN": None,
            "L_m": L_m_value,
            "support_type": support_type_value,
            "formula_label": None,
            "actions_source": actions_source,
        }

        V_kN = V_manual_kN if is_manual else V_design_kN if is_design else None
        if (
            L_m_value is not None
            and L_m_value > 0
            and V_kN is not None
            and V_kN > 0
        ):
            if support_type_value in ("Simply supported", "Pinned–Pinned"):
                fd_ef_used = 2.0 * V_kN / L_m_value
                formula_label = "2V/L"
            elif support_type_value == "Cantilever":
                fd_ef_used = V_kN / L_m_value
                formula_label = "V/L"
            else:
                fd_ef_used = V_kN / L_m_value
                formula_label = "V/L"

            if is_manual:
                branch = "manual_actions"
                source_text = "Derived from manual Inputs-page actions."
            elif is_design:
                branch = "design_actions"
                source_text = "Derived from Teaching / design actions."
            else:
                branch = "fallback"
                source_text = (
                    "Fallback value used because derivation inputs were unavailable."
                )

            meta.update({"V_kN": V_kN, "formula_label": formula_label})
            return fd_ef_used, branch, source_text, meta

        return fallback_value, branch, source_text, meta

    # 3-column layout matching Shear pattern
    col_geom, col_mats, col_loads = st.columns(3, gap="large")

    # ---------- Column 1: Geometry ----------
    with col_geom:
        st.markdown("**Geometry**")
        L_seed_mm = _seed_from_param("L", 3000.0)
        L_eff = st.session_state.get("defl_L_eff", L_seed_mm / 1000.0)

        b_seed = _seed_from_param("b", 300.0)
        b = _input_row(
            "Beam width b (mm)",
            "Beam width of the section.",
            lambda: v2_number_input(
                label="Value",
                key="defl_b",
                default=b_seed,
                step=10.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_b"],
            ),
        )

        # Beam depth D (mm)
        D_seed = _seed_from_param("D", 600.0)
        D = _input_row(
            "Beam depth D (mm)",
            "Overall beam depth from compression face to soffit.",
            lambda: v2_number_input(
                label="Value",
                key="defl_D",
                default=D_seed,
                step=10.0,
                label_visibility="collapsed",
                on_change=sync_callbacks.get("defl_D") or (lambda: None),
            ),
        )
        # Ensure D is a float for calculations
        if D is None:
            D = D_seed
        else:
            D = float(D)

        # Span L (mm)
        L_seed = _seed_from_param("L", 3000.0)
        L = _input_row(
            "Span L (mm)",
            "Clear span used for deflection checks.",
            lambda: v2_number_input(
                label="Value",
                key="defl_L",
                default=L_seed,
                step=100.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_L"],
            ),
        )

        # Derived: web width (for calculations; shown in calc box)
        bw = st.session_state.get("defl_bw", b)

        # Read-only: effective flange width (computed/derived)
        beff_widget = st.session_state.get("defl_beff", None)
        if beff_widget is not None:
            beff = float(beff_widget)
        else:
            beff = _seed_from_param("defl_beff", b_seed)

        # Derived: effective depth (for calculations; shown in calc box)
        d = _seed_from_param("d", 550.0)

    # ---------- Column 2: Materials ----------
    with col_mats:
        st.markdown("**Materials**")

        fc_seed = _seed_from_param("fc", 32.0)
        fc = _input_row(
            "Concrete strength f'c (MPa)",
            "Concrete compressive strength.",
            lambda: v2_number_input(
                label="Value",
                key="defl_fc",
                default=fc_seed,
                step=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_fc"],
            ),
        )

        Ec_short = float(get_param("Ec", 30000.0) or 30000.0)
        phi_cc_t = float(get_param("phi_cc_t", 2.0) or 0.0)
        Ec = float(get_param("Eceff", Ec_short) or Ec_short)
        stress_ratio = float(get_param("stress_ratio", 0.0) or 0.0)
        sustained_sigma_cs = float(get_param("sustained_sigma_cs_mpa", 0.0) or 0.0)
        sustained_mstar = float(get_param("sustained_Mstar_kNm", 0.0) or 0.0)
        sustained_z_comp = float(get_param("sustained_section_modulus_mm3", 0.0) or 0.0)

    # ---------- Column 3: Serviceability ----------
    with col_loads:
        st.markdown("**Serviceability**")
        # Governing multispan metrics come from compute_all_results / final compute below
        # (not an early preview write) so support resolution matches per-span loads.
        support_resolution = get_deflection_diagram_support_condition(st.session_state)
        design_controls = is_design_governing()
        w_support = (
            defl_support_widget_key
        )
        current_support_type = support_resolution["support_type"]
        support_options = _deflection_support_options_for_value(current_support_type)
        support_help_text = (
            "Support condition determines the deflection coefficient k₂ used in "
            "AS 3600 deflection calculations."
        )
        default_idx = (
            support_options.index(current_support_type)
            if current_support_type in support_options
            else 0
        )

        if design_controls:
            st.info(
                "🔒 Support condition (k₂) is **auto-derived** from the Design / SFD model. "
                "It stays aligned with the value used in calculations."
            )
        support_type_widget = _input_row(
            "Support condition (k₂)",
            support_help_text,
            lambda: v2_selectbox(
                label="Value",
                key=w_support,
                options=support_options,
                default_index=default_idx,
                label_visibility="collapsed",
                disabled=design_controls,
                on_change=sync_callbacks[w_support],
            ),
        )
        support_type = (
            support_resolution["support_type"]
            if design_controls
            else _normalize_deflection_support_type(support_type_widget)
        )

        defl_limit_default = get_deflection_limit_ratio(get_param("defl_limit_ratio", 250.0))
        defl_limit_ratio = _input_row(
            "Deflection limit L/Δ",
            DEFLECTION_LIMIT_HELP_TEXT,
            lambda: v2_selectbox(
                label="Value",
                key=defl_limit_widget_key,
                options=list(DEFLECTION_LIMIT_OPTIONS.values()),
                default_index=list(DEFLECTION_LIMIT_OPTIONS.values()).index(defl_limit_default),
                format_func=lambda v: get_deflection_limit_label_from_ratio(v),
                label_visibility="collapsed",
                on_change=sync_callbacks[defl_limit_widget_key],
            ),
        )

    page_divider()

    # Derive F_d,ef from Inputs / Teaching actions (after column inputs)
    V_design_kN = get_param("Vu_star", 0.0) or 0.0
    V_manual_kN = get_param("Vu_star_manual", 0.0) or 0.0

    L_m_for_fd = get_param("defl_L_eff", 0.0)
    if L_m_for_fd is None or L_m_for_fd <= 0:
        L_m_for_fd = get_param("span_L_m", 0.0)
        if L_m_for_fd is None:
            L_m_for_fd = 0.0

    fd_fallback = get_param("defl_Fdef", 12.0)

    defl_limit_ratio = float(get_deflection_limit_ratio(defl_limit_ratio))
    defl_limit_label = get_deflection_limit_label_from_ratio(defl_limit_ratio)

    fd_ef_used, fd_ef_source_branch, value_source_text, fd_ef_meta = _derive_fd_ef(
        actions_source=actions_source,
        support_type_value=support_type,
        L_m_value=L_m_for_fd,
        V_manual_kN=V_manual_kN,
        V_design_kN=V_design_kN,
        fallback_value=fd_fallback,
    )

    Fdef_kNm = fd_ef_used

    with st.container():
        _defl_sec_shape_ui = str(get_param("sec_shape", "RECT") or "RECT")
        _defl_bot_md, _defl_top_md = main_longitudinal_reo_pair_labels(
            _defl_sec_shape_ui, variant="sentence_lower"
        )
        _reo_pad_l, _reo_mid, _reo_pad_r = st.columns([1, 3, 1])
        with _reo_mid:
            reo_col_left, reo_col_right = st.columns([1, 1], gap="large")
            with reo_col_left:
                _defl_bot_title_col, _defl_bot_info_col = st.columns(
                    [0.92, 0.08], vertical_alignment="center"
                )
                with _defl_bot_title_col:
                    st.markdown(f"**{_defl_bot_md.title()}**")
                rowgap_bot_val = float(
                    st.session_state.get(
                        "defl_rowgap_bot", get_param("rowgap_bot", 60.0)
                    )
                    or 60.0
                )
                with _defl_bot_info_col:
                    with info_i_button(
                        help_text="Row count and vertical gap between reinforcement layers."
                    ):
                        render_longitudinal_reo_row_config_controls(
                            page_prefix="defl",
                            section="bot",
                            sync_callbacks=sync_callbacks,
                            rowgap_widget_key="defl_rowgap_bot",
                            rowgap_default=rowgap_bot_val,
                            rowgap_help_text=(
                                "Clear vertical gap between reinforcement rows (mm)."
                            ),
                            sec_shape=_defl_sec_shape_ui,
                        )
                render_longitudinal_reo_rows(
                    page_prefix="defl",
                    section="bot",
                    sync_callbacks=sync_callbacks,
                    layout_modes=REO_LAYOUT_MODE,
                    count_options=REO_COUNTS_0_12,
                    spacing_options=REO_SPACINGS,
                    dia_options=REO_BAR_DIAS,
                    single_column=True,
                    sec_shape=_defl_sec_shape_ui,
                )

            with reo_col_right:
                _defl_top_title_col, _defl_top_info_col = st.columns(
                    [0.92, 0.08], vertical_alignment="center"
                )
                with _defl_top_title_col:
                    st.markdown(f"**{_defl_top_md.title()}**")
                rowgap_top_val = float(
                    st.session_state.get(
                        "defl_rowgap_top", get_param("rowgap_top", 60.0)
                    )
                    or 60.0
                )
                with _defl_top_info_col:
                    with info_i_button(
                        help_text="Row count and vertical gap between reinforcement layers."
                    ):
                        render_longitudinal_reo_row_config_controls(
                            page_prefix="defl",
                            section="top",
                            sync_callbacks=sync_callbacks,
                            rowgap_widget_key="defl_rowgap_top",
                            rowgap_default=rowgap_top_val,
                            rowgap_help_text=(
                                "Clear vertical gap between reinforcement rows (mm)."
                            ),
                            sec_shape=_defl_sec_shape_ui,
                        )
                render_longitudinal_reo_rows(
                    page_prefix="defl",
                    section="top",
                    sync_callbacks=sync_callbacks,
                    layout_modes=REO_LAYOUT_MODE,
                    count_options=REO_COUNTS_0_12,
                    spacing_options=REO_SPACINGS,
                    dia_options=REO_BAR_DIAS,
                    single_column=True,
                    sec_shape=_defl_sec_shape_ui,
                )

    page_divider()

    # Read derived reinforcement areas for calculations (no UI rows)
    Ast = _seed_from_param("Ast_bot", 2010.0)
    Asc = _seed_from_param("Ast_top", 0.0)

    # Always refresh deflection results for summary/reporting.
    from deflection_core import compute_deflection_results
    compute_deflection_results(publish=True)

    # --------------------------------------------------------
    # SINGLE COMPUTED VALUES BLOCK (compute once, use everywhere)
    # --------------------------------------------------------
    # Compute Ief_selected once based on checkbox state
    use_simplified_ief = st.session_state.get("defl_use_simplified_ief", True)
    try:
        if use_simplified_ief:
            Ief_selected, beta, p, p_lim, Ief_max, k1_from_ief = calc_ief_simplified(
                fc=fc,
                beff=beff,
                bw=bw,
                d=d,
                Ast=Ast,
            )
        else:
            Ief_selected = st.session_state.get("defl_Ief_user", 1.0e11)
            beta = beff / bw if (bw is not None and bw > 0) else 1.0
            p = (
                Ast / (beff * d)
                if (beff is not None and d is not None and beff * d > 0)
                else 0.0
            )
            p_lim = 0.0
            Ief_max = Ief_selected
            k1_from_ief = (
                Ief_selected / (beff * (d**3))
                if (beff is not None and d is not None and beff * d > 0)
                else 0.0
            )
    except Exception:
        Ief_selected = 1.0e11
        beta = beff / bw if (bw is not None and bw > 0) else 1.0
        p = (
            Ast / (beff * d)
            if (beff is not None and d is not None and beff * d > 0)
            else 0.0
        )
        p_lim = 0.0
        Ief_max = Ief_selected
        k1_from_ief = (
            Ief_selected / (beff * (d**3))
            if (beff is not None and d is not None and beff * d > 0)
            else 0.0
        )

    # --- hard guard: never let L_m be None (prevents session-killing exception) ---
    L_eff_m = get_param("defl_L_eff")

    if L_eff_m is None:
        L_eff_m = float(get_param("L")) / 1000.0

    if L_eff_m <= 0:
        L_eff_m = 0.1

    L_eff_m = float(L_eff_m) if L_eff_m is not None else None
    derived = _derive_equiv_udl_from_actions(
        M_kNm=M_used,
        V_kN=V_used,
        L_m=L_eff_m,
        support_type=support_type,
    )
    if derived["w_kN_per_m"] is not None:
        w_used = derived["w_kN_per_m"]
        w_source = "actions"
    else:
        w_used = (g + q) if (g is not None and q is not None) else 0.0
        w_source = "g+q"

    if w_used > 0:
        if (g + q) > 0:
            g_ratio = g / (g + q)
            g_used = w_used * g_ratio
            q_used = w_used * (1 - g_ratio)
        else:
            g_used = w_used
            q_used = 0.0
    else:
        g_used = g
        q_used = q

    compute_and_store_multispan_deflection_metrics(
        state=st.session_state,
        Ec=float(Ec),
        Ief=float(Ief_selected),
        g_kNm=float(g_used),
        q_kNm=float(q_used),
        psi_s=float(psi_s),
        defl_limit_ratio=float(defl_limit_ratio),
        Ast=float(Ast),
        Asc=float(Asc),
    )
    support_resolution = get_deflection_diagram_support_condition(st.session_state)
    support_type = support_resolution["support_type"]

    try:
        from src.debug.debug_flags import is_debug_enabled as _is_dbg_defl
    except Exception:
        def _is_dbg_defl():
            return False
    if _is_dbg_defl() and _is_design_multispan_mode(st.session_state):
        try:
            _n_dbg = int(float(st.session_state.get("sfd_span_count", 0) or 0))
        except Exception:
            _n_dbg = 0
        _lens_dbg = [
            float(st.session_state.get(f"sfd_span_len_{i}", 0) or 0)
            for i in range(1, max(0, _n_dbg) + 1)
        ]
        _g_dbg = [
            float(st.session_state.get(f"load_ms_g_{i}", 0) or 0)
            for i in range(1, max(0, _n_dbg) + 1)
        ]
        _q_dbg = [
            float(st.session_state.get(f"load_ms_q_{i}", 0) or 0)
            for i in range(1, max(0, _n_dbg) + 1)
        ]
        _sup_dbg = [
            "Continuous – end span"
            if _i in (0, max(0, _n_dbg - 1))
            else "Continuous – interior span"
            for _i in range(max(0, _n_dbg))
        ]
        with st.expander("Debug: multispan governing-span inputs (final)", expanded=True):
            st.write("**controlling_span_idx (0-based):**", support_resolution.get("controlling_span_idx"))
            st.write("**controlling_reason:**", support_resolution.get("controlling_reason"))
            st.write("**sfd_span_len_i (m):**", _lens_dbg)
            st.write("**load_ms_g_i (kN/m):**", _g_dbg)
            st.write("**load_ms_q_i (kN/m):**", _q_dbg)
            st.write("**defl_span_deflections_mm:**", st.session_state.get("defl_span_deflections_mm"))
            st.write("**defl_span_utilisations:**", st.session_state.get("defl_span_utilisations"))
            st.write("**per-span support class (metric loop):**", _sup_dbg)

    # Passive display only (no widget mutation): when support is design-governed,
    # show the governing support condition used by calculations and plots.
    if str(support_resolution.get("mode", "")).strip().lower() == "design":
        st.caption(f"Governing support condition (from Design/SFD): **{support_type}**")
    # Keep F_d,ef and downstream span/depth expressions aligned with the final
    # governing support_type selected after multispan metrics are refreshed.
    fd_ef_used, fd_ef_source_branch, value_source_text, fd_ef_meta = _derive_fd_ef(
        actions_source=actions_source,
        support_type_value=support_type,
        L_m_value=L_m_for_fd,
        V_manual_kN=V_manual_kN,
        V_design_kN=V_design_kN,
        fallback_value=fd_fallback,
    )
    Fdef_kNm = fd_ef_used

    results = calc_deflection_as3600(
        L_m=L_eff_m,
        Ec=Ec,
        Ief=Ief_selected,
        g_kNm=g_used,
        q_kNm=q_used,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )

    if results is None or (
        isinstance(results, dict) and results.get("ok") is False
    ):
        error_msg = (
            results.get(
                "error",
                "Deflection calculation failed: invalid span length.",
            )
            if isinstance(results, dict)
            else "Deflection calculation failed: invalid span length."
        )
        st.warning(error_msg)
        return

    L_mm = results["L_mm"]
    delta_short_total = results["delta_short_total"]
    delta_short_sust = results["delta_short_sust"]
    delta_long_add = results["delta_long_add"]
    delta_total = results["delta_total"]
    kcs = results["kcs"]
    w_total = w_used  # Use computed w_used instead of g + q
    w_sust = results["w_sust"]
    k2 = results["k2"]

    # Deflected shape (rendered in slot above reinforcement; same computed values)
    with diagram_placeholder.container():
        st.markdown("**Deflected shape**")
        st.caption("Illustrative — see figure title for vertical exaggeration")
        st.caption(
            f"Resolved support condition for governing span: {support_type}"
        )
        support_pair = _governing_span_support_pair(st.session_state, support_resolution)
        if support_resolution.get("multi_span"):
            _span_no = int(support_resolution.get("controlling_span_idx", 0)) + 1
            _reason = str(support_resolution.get("controlling_reason", "fallback") or "fallback")
            if _reason in ("highest deflection utilisation", "largest absolute deflection"):
                _basis = f"selected from calculated per-span deflection results ({_reason})"
            elif _reason == "longest active span":
                _basis = "selected by longest active span"
            else:
                _basis = "selected by fallback"
            st.caption(
                f"Governing span: Span {_span_no}, {_basis}. "
                f"The displayed support condition and sketch follow this governing span."
            )

        if delta_total is None:
            st.info("Provide inputs to view deflected shape.")
        else:
            x, y_long = deflected_longitudinal_profile_mm(
                L_mm, support_type, float(delta_total), n_pts=200
            )

            D_mm = float(D) if D is not None else 600.0
            beam_fig = build_deflected_beam_plotly(
                x_mm=x,
                w_mm=y_long,
                L_mm=L_mm,
                D_mm=D_mm,
                support_type=support_type,
                continuous_end_side=support_resolution.get("continuous_end_side"),
                support_pair=support_pair,
            )
            _c1, _c2, _c3 = st.columns([0.06, 1.0, 0.06])
            with _c2:
                st.plotly_chart(
                    beam_fig,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
        page_divider()

    L_over_delta_short = format_L_over_delta(delta_short_total, L_mm)
    L_over_delta_long_add = format_L_over_delta(delta_long_add, L_mm)
    L_over_delta_total = format_L_over_delta(delta_total, L_mm)

    L_over_d = (L_mm / d) if d > 0 else 0.0
    L_over_d_limit, k1_span, k2_span = calc_span_depth_limit(
        ief=Ief_selected,
        beff=beff,
        bw=bw,
        d=d,
        fc=fc,
        Ec=Ec,
        Fdef_kNm=Fdef_kNm,
        support_type=support_type,
        defl_limit_ratio=defl_limit_ratio,
    )

    # Closed-form deflection (with unit fix: convert L to mm, P to N)
    delta_max = None
    formula_latex = None
    delta_loc = None
    if (
        load_case is not None
        and L_sfd is not None
        and Ec is not None
        and Ief_selected is not None
        and L_sfd > 0
        and Ec > 0
        and Ief_selected > 0
    ):
        L_mm_sfd = float(L_sfd) * 1000.0
        w_eff_n_per_mm = w_eff if w_eff is not None else None
        P_sls_n = P_sls * 1000.0 if P_sls is not None else None
        E_mpa = float(Ec)
        I_mm4 = float(Ief_selected)

        delta_max, formula_latex, delta_loc = _deflection_from_sfd_case(
            case=load_case,
            L=L_mm_sfd,
            w_eff=w_eff_n_per_mm,
            P_sls=P_sls_n,
            E=E_mpa,
            I=I_mm4,
        )

    # --------------------------------------------------------
    # Summary + stacked calculation sections (Crack-style vertical flow)
    # --------------------------------------------------------
    with summary_placeholder.container():
        render_page_explainer_expander(_render_deflection_explainer)
        defl_pack = build_deflection_check_rows_from_state(st.session_state)
        ROWS = defl_pack.get("rows", [])
        update_results("deflection", {"rows": ROWS, "summary": defl_pack})
        render_clickable_summary_table(
            ROWS,
            key_prefix="defl_summary",
            columns=DEFLECTION_CHECK_SUMMARY_COLUMNS,
        )
        bind_summary_clicks()
        page_divider()

    use_simplified_ief_checkbox = v2_checkbox(
        label="Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
        key="defl_use_simplified_ief",
        default=use_simplified_ief,
        on_change=sync_callbacks["defl_use_simplified_ief"],
    )

    # Display-only: show the already computed Ief_selected
    if not use_simplified_ief_checkbox:
        Ief_user_display = v2_number_input(
            label="User-specified Iₑf (mm⁴)",
            key="defl_Ief_user",
            default=Ief_selected,
            step=1.0e10,
            format="%.3e",
        )
        # Note: Changing this will require rerun to update calculations

    # Build 2-line summary for Ief step
    ief_method = "Simplified" if use_simplified_ief_checkbox else "User input"
    # Guard against None values for formatting
    Ief_selected_display = Ief_selected if Ief_selected is not None else 1.0e11
    ief_summary = (
        f"**Check 1 — Effective stiffness $I_{{ef}}$**  \n"
        f"$I_{{ef}} = {Ief_selected_display:,.3e}\\,\\mathrm{{mm}}^4$  "
        f"({ief_method.lower()} reinforced-member option)"
    )

    # Guard against None values before formatting
    fc_display = fc if fc is not None else 32.0
    bw_display = bw if bw is not None else 300.0
    beff_display = beff if beff is not None else 300.0
    d_display = d if d is not None else 550.0
    Ast_display = Ast if Ast is not None else 2010.0
    beta_display = beta if beta is not None else 1.0
    p_display = p if p is not None else 0.0
    p_lim_display = p_lim if p_lim is not None else 0.0
    Ief_max_display = Ief_max if Ief_max is not None else 1.0e11
    k1_from_ief_display = k1_from_ief if k1_from_ief is not None else 0.0
    use_high_branch = p_display >= p_lim_display
    if use_high_branch:
        ief_branch_label = "p ≥ p_lim"
        k1_expr = (5.0 - 0.04 * fc_display) * p_display + 0.002
        k1_expr_md = (
            rf"(5 - 0.04\ \times\ {fc_display:.1f})\ \times\ "
            rf"{p_display:.5f} + 0.002"
        )
    else:
        ief_branch_label = "p < p_lim"
        k1_expr = (0.055 * (fc_display ** (1.0 / 3.0)) /
                   (beta_display ** (2.0 / 3.0))) - 50.0 * p_display
        k1_expr_md = (
            rf"0.055\ \times\ ({fc_display:.1f})^{{1/3}}/({beta_display:.3f})^{{2/3}} "
            rf"- 50\ \times\ {p_display:.5f}"
        )

    ief_calc_md = rf"""
*Purpose: Compute the effective second moment of area $I_{{ef}}$ for a reinforced concrete member using the simplified expressions in AS 3600:2018 Cl. 8.5.3.1(2) and (3). This cracked stiffness is then used in all deflection checks.*

**Inputs:**

- Concrete strength: $f'_c = {fc_display:.1f}\,\text{{MPa}}$
- Web / stem width (derived): $b_w = {bw_display:.1f}\,\text{{mm}}$
- Effective flange width (derived): $b_{{ef}} = {beff_display:.1f}\,\text{{mm}}$
- Effective depth (derived): $d = {d_display:.1f}\,\text{{mm}}$
- Tension steel area (derived): $A_{{st}} = {Ast_display:.1f}\,\text{{mm}}^2$

Derived section parameters:

- Width ratio:
  $$
  \beta = \dfrac{{b_{{ef}}}}{{b_w}} = \dfrac{{{beff_display:.1f}}}{{{bw_display:.1f}}} = {beta_display:.3f}
  $$
- Reinforcement ratio:
  $$
  p = \dfrac{{A_{{st}}}}{{b_{{ef}} d}} = \dfrac{{{Ast_display:.1f}}}{{{beff_display:.1f}\times {d_display:.1f}}} = {p_display:.5f}
  $$
- Limit ratio:
  $$
  p_{{lim}} = 0.001 \dfrac{{(f'_c)^{{1/3}}}}{{\beta^{{2/3}}}}
  = 0.001 \dfrac{{({fc_display:.1f})^{{1/3}}}}{{({beta_display:.3f})^{{2/3}}}}
  = {p_lim_display:.5f}
  $$

---

**Formula:**

For reinforced members (AS 3600:2018 Cl. 8.5.3.1):

If $p \ge p_{{lim}}$:

$$
I_{{ef}} = \left[(5 - 0.04 f'_c)\, p + 0.002 \right]\, b_{{ef}} d^3
$$

If $p < p_{{lim}}$:

$$
I_{{ef}} = \left[0.055 (f'_c)^{{1/3}} / \beta^{{2/3}} - 50 p \right]\, b_{{ef}} d^3
$$

Capped by:

$$
I_{{ef}} \le I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4
$$

and

$$
k_1 = \dfrac{{I_{{ef}}}}{{b_{{ef}} d^3}}
$$

---

**Substitution:**

Using the current inputs:

- Branch used: {ief_branch_label}
- Coefficient:
  $$
  k_1 = {k1_expr_md} = {k1_expr:.5f}
  $$
- Effective stiffness:
  $$
  I_{{ef}} = k_1\, b_{{ef}} d^3 = {k1_expr:.5f}\times {beff_display:.1f}\times ({d_display:.1f})^3
  \approx {Ief_selected_display:,.3e}\,\text{{mm}}^4
  $$
- Cap check:
  $$
  I_{{ef}} \le I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4
  $$

---

**Result:**

- $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$
- $k_1 = {k1_from_ief:.5f}$
- (cap) $I_{{ef,max}} = {Ief_max:,.3e}\,\text{{mm}}^4$

_Ref: AS 3600:2018 Cl. 8.5.3.1(2) & (3) – simplified $I_{{ef}}$ for reinforced members._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_ief",
        title="Effective stiffness ($I_{ef}$) – input choice",
        summary_md=ief_summary,
        status_kind=None,
        calc_md=ief_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    # Short-term deflection step
    limit_delta_mm = L_mm / defl_limit_ratio if defl_limit_ratio > 0 else None
    util_short = delta_short_total / \
        limit_delta_mm if limit_delta_mm and limit_delta_mm > 0 else None
    short_status = "pass" if (util_short is not None and util_short <=
                              1.0) else "fail" if util_short is not None else None

    _short_res = (
        "PASS"
        if short_status == "pass"
        else "FAIL"
        if short_status == "fail"
        else "—"
    )
    short_summary = (
        f"**Check 2 — Short-term deflection**  \n"
        f"$\\delta_{{st,total}} = {delta_short_total:.2f}\\,\\mathrm{{mm}}$ "
        f"({L_over_delta_short}) | Result: {_short_res}"
    )

    # Determine source label for display
    source_label = "Teaching SFD/BMD page" if is_design_driven else "Manual design actions"
    w_from_M = derived.get("w_from_M") if isinstance(derived, dict) else None
    w_from_V = derived.get("w_from_V") if isinstance(derived, dict) else None
    if w_source == "actions" and derived.get("w_kN_per_m") is not None:
        wM_str = f"{w_from_M:.2f}" if w_from_M is not None else "—"
        wV_str = f"{w_from_V:.2f}" if w_from_V is not None else "—"
        load_line = (
            f"- Total service load: $w = {w_total:.2f}\\,\\text{{kN/m}}$ "
            f"(from actions; $w_M={wM_str}$, $w_V={wV_str}$)"
        )
    else:
        load_line = (
            f"- Total service load: $w = g + q = {w_total:.2f}\\,\\text{{kN/m}}$"
        )

    short_calc_md = rf"""
*Purpose: Determine the short-term midspan deflection under total service load $w$ using the effective stiffness $I_{{ef}}$ from the Iₑf step (AS 3600 Cl. 8.5.3.1).*

**Inputs:**

- Actions source: {source_label}
- Effective span (derived):
  $$
  L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm / 1000.0:.3f}\,\text{{m}} = {L_mm:.0f}\,\text{{mm}}
  $$
{load_line}
- Support condition: {support_type}
- Deflection coefficient (support condition):  
  $k_2 = {k2:.5f}$  
  *(Code-defined coefficient based on support condition per AS 3600 Cl. 8.5.3.1)*
- Concrete modulus (derived): $E_c = 4700\sqrt{{f'_c}} = {Ec_short:.0f}\,\text{{MPa}}$
- Effective modulus (derived): $E_{{c,eff}} = \dfrac{{E_c}}{{1+\varphi_{{cc}}(t)}} = {Ec:.0f}\,\text{{MPa}}$
- Effective second moment: $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$

---

**Formula:**

Short-term deflection due to total service load:

$$
\delta_{{st,total}} = k_2 \dfrac{{w\, L_{{eff}}^4}}{{E_{{c,eff}}\, I_{{ef}}}}
$$

where $k_2$ is the deflection coefficient determined by support condition (AS 3600 Cl. 8.5.3.1).

---

**Substitution:**

$$
\delta_{{st,total}}
= ({k2:.5f}) \times ({w_total:.2f})\,
  \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
\approx {delta_short_total:.2f}\,\text{{mm}}
$$

---

**Result:**

- Short-term deflection (total load):  
  $\delta_{{st,total}} \approx {delta_short_total:.2f}\,\text{{mm}}$
- Deflection ratio:  
  $L/\delta_{{st,total}} \approx {L_over_delta_short}$
{f'- Utilisation: {util_short:.2f} → {"✓ PASS" if short_status == "pass" else "✗ FAIL"}' if util_short is not None else ''}

_Ref: AS 3600:2018 Cl. 8.5.3.1 – deflection using effective stiffness $I_{{ef}}$._
"""
    render_expandable_step(
        page_key="deflection",
        step_id="defl_short",
        title="Short-term deflection",
        summary_md=short_summary,
        status_kind=short_status,
        calc_md=short_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    limit_delta_mm = L_mm / defl_limit_ratio if defl_limit_ratio > 0 else None
    util_long = (
        delta_long_add / limit_delta_mm
        if limit_delta_mm and limit_delta_mm > 0
        else None
    )
    util_total = (
        delta_total / limit_delta_mm
        if limit_delta_mm and limit_delta_mm > 0
        else None
    )
    long_status = (
        "pass"
        if (util_total is not None and util_total <= 1.0)
        else "fail"
        if util_total is not None
        else None
    )

    limit_delta_mm_display = limit_delta_mm if limit_delta_mm is not None else 0.0
    util_total_display = util_total if util_total is not None else 0.0

    ratio_Asc_Ast = (Asc / Ast) if Ast > 0 else 0.0

    _long_res = (
        "PASS"
        if long_status == "pass"
        else "FAIL"
        if long_status == "fail"
        else "—"
    )
    long_summary = (
        f"**Check 3 — Long-term deflection**  \n"
        f"$\\delta_{{total}} = {delta_total:.2f}\\,\\mathrm{{mm}}$ "
        f"({L_over_delta_total}) | Includes: Long-term deflection with "
        f"$k_{{cs}}$; Result: {_long_res}"
    )

    source_label = "Teaching SFD/BMD page" if is_design_driven else "Manual design actions"

    long_calc_md = rf"""
*Purpose: Determine the additional long-term deflection due to sustained loading (creep + shrinkage) and the resulting total deflection to AS 3600 Cl. 8.5.3.2.*

**Inputs:**

- Actions source: {source_label}
- Effective span (derived):
  $$
  L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm / 1000.0:.3f}\,\text{{m}} = {L_mm:.0f}\,\text{{mm}}
  $$
- Support condition: {support_type}
- Sustained load:
  $$
  w_{{sust}} = g + \psi_s q = {g_used:.2f} + {psi_s:.2f}\times {q_used:.2f} = {w_sust:.2f}\,\text{{kN/m}}
  $$
- Sustained factor: $\psi_s = {psi_s:.2f}$
- Tension steel: $A_{{st}} = {Ast:.0f}\,\text{{mm}}^2$
- Compression steel: $A_{{sc}} = {Asc:.0f}\,\text{{mm}}^2$
- Steel ratio:
  $$
  \dfrac{{A_{{sc}}}}{{A_{{st}}}} = \dfrac{{{Asc:.0f}}}{{{Ast:.0f}}} = {ratio_Asc_Ast:.3f}
  $$
- Creep/shrinkage multiplier:
  $$
  k_{{cs}} = \max\left[ 2 - 1.2 \left(\dfrac{{A_{{sc}}}}{{A_{{st}}}}\right),\, 0.8 \right]
  = \max\left[ 2 - 1.2 \times {ratio_Asc_Ast:.3f},\, 0.8 \right] = {kcs:.2f}
  $$
- Sustained concrete stress path (from creep workflow):
  $$
  \sigma_{{cs}} = \dfrac{{M_{{sust}}\times10^6}}{{Z_{{comp}}}}
  = \dfrac{{{sustained_mstar:.2f}\times10^6}}{{{sustained_z_comp:.2e}}}
  \approx {sustained_sigma_cs:.2f}\,\text{{MPa}}
  $$
  $$
  \text{{stress\_ratio}} = \dfrac{{\sigma_{{cs}}}}{{f'_c}}
  = \dfrac{{{sustained_sigma_cs:.2f}}}{{{fc:.1f}}}
  = {stress_ratio:.3f}
  $$
- Effective modulus path used in deflection:
  $$
  E_{{c,eff}} = \dfrac{{E_c}}{{1+\phi_{{cc}}(t)}}
  = \dfrac{{{Ec_short:.0f}}}{{1+{phi_cc_t:.2f}}}
  = {Ec:.0f}\,\text{{MPa}}
  $$
- Other parameters as per short-term:
  $k_2 = {k2:.5f},\ L_{{eff}} = {L_mm:.0f}\,\text{{mm}},\
   I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$

---

**Formula:**

Short-term deflection due to **sustained load only**:

$$
\delta_{{st,sust}} = k_2 \dfrac{{w_{{sust}} L_{{eff}}^4}}{{E_{{c,eff}} I_{{ef}}}}
$$

Creep/shrinkage multiplier:

$$
k_{{cs}} = \max\left[ 2 - 1.2 \left(\dfrac{{A_{{sc}}}}{{A_{{st}}}}\right),\, 0.8 \right]
$$

Additional long-term deflection:

$$
\delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
$$

Total deflection:

$$
\delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
$$

Adopted limit ratio: **{defl_limit_label}**

Deflection limit:

$$
\delta_{{limit}} = \dfrac{{L_{{eff}}}}{{(L/\Delta)}} = \dfrac{{{L_mm:.0f}}}{{{defl_limit_ratio:.0f}}}
$$

---

**Substitution:**

Short-term sustained:

$$
\delta_{{st,sust}}
= ({k2:.5f}) \times ({w_sust:.2f})\,
  \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
\approx {delta_short_sust:.2f}\,\text{{mm}}
$$

Additional long-term:

$$
\delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
= ({kcs:.2f}) \times ({delta_short_sust:.2f})
\approx {delta_long_add:.2f}\,\text{{mm}}
$$

Total:

$$
\delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
= {delta_short_total:.2f} + {delta_long_add:.2f}
\approx {delta_total:.2f}\,\text{{mm}}
$$

Adopted limit ratio: **{defl_limit_label}**

Deflection limit and utilisation:

$$
\delta_{{limit}} = \dfrac{{L_{{eff}}}}{{(L/\Delta)}} = \dfrac{{{L_mm:.0f}}}{{{defl_limit_ratio:.0f}}}
 = {limit_delta_mm_display:.2f}\,\text{{mm}}
$$

$$
\text{{Utilisation}} = \dfrac{{\delta_{{total}}}}{{\delta_{{limit}}}}
 = \dfrac{{{delta_total:.2f}}}{{{limit_delta_mm_display:.2f}}} = {util_total_display:.2f}
$$

---

**Result:**

- Short-term sustained:  
  $\delta_{{st,sust}} \approx {delta_short_sust:.2f}\,\text{{mm}}$
- Additional long-term:  
  $\delta_{{LT,add}} \approx {delta_long_add:.2f}\,\text{{mm}}$  
  (ratio $\approx {L_over_delta_long_add}$)
- Total deflection:  
  $\delta_{{total}} \approx {delta_total:.2f}\,\text{{mm}}$  
  (ratio $\approx {L_over_delta_total}$)
{f'- Utilisation: {util_total:.2f} → {"✓ PASS" if long_status == "pass" else "✗ FAIL"}' if util_total is not None else ''}

_Ref: AS 3600:2018 Cl. 8.5.3.2 – long-term deflection using $k_{{cs}}$ and sustained loads._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_long",
        title="Long-term deflection",
        summary_md=long_summary,
        status_kind=long_status,
        calc_md=long_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    L_m = L_m_for_fd
    if L_m is None or L_m <= 0:
        L_m = float(get_param("span_L_m", 0.0) or 0.0)

    support_type_display = support_type

    value_source = value_source_text
    fd_ef_meta_used = fd_ef_meta or {}

    # Determine loading condition description
    if fd_ef_source_branch in ("manual_actions", "design_actions"):
        if support_type == "Simply supported":
            loading_condition = "Simply supported, UDL over full span"
        elif support_type == "Cantilever":
            loading_condition = "Cantilever, UDL over full span"
        else:
            loading_condition = f"{support_type}, UDL over full span"
    else:
        loading_condition = "Fallback value"

    # Build summary
    fd_ef_summary = (
        f"**Check 4 — Effective design load F_d,ef**  \n"
        f"$F_{{d,ef}} = {fd_ef_used:.2f}\\,\\mathrm{{kN/m}}$ | "
        f"Source: {value_source}"
    )

    if (
        fd_ef_source_branch in ("manual_actions", "design_actions")
        and fd_ef_meta_used.get("V_kN", 0.0) > 0
        and L_m > 0
    ):
        V_kN = fd_ef_meta_used.get("V_kN", 0.0)
        if support_type == "Simply supported":
            equation_latex = r"V_{\max} = \frac{wL}{2} \quad \Rightarrow \quad w = \frac{2V_{\max}}{L}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{2 \times {V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )
        elif support_type == "Cantilever":
            equation_latex = r"V_{\max} = wL \quad \Rightarrow \quad w = \frac{V_{\max}}{L}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{{V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )
        else:
            equation_latex = r"w = \frac{V_{\max}}{L} \quad \text{(approximate)}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{{V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )

        source_label = (
            "Manual inputs"
            if fd_ef_source_branch == "manual_actions"
            else "Teaching SFD/BMD"
        )

        fd_ef_calc_md = rf"""
*Purpose: Determine the equivalent uniform distributed load $F_{{d,ef}}$ used for span-to-depth ratio checks per AS 3600 Cl. 8.5.4. This value is reverse-engineered from the design shear force $V^*$ and span length $L$ based on the support condition and loading pattern.*

**Step 1 – Inputs:**

- Source: {source_label}
- Design shear: $V^* = {V_kN:.1f}\,\text{{kN}}$
- Effective span: $L = {L_m:.2f}\,\text{{m}}$
- Support condition: {support_type_display}
- Loading condition: {loading_condition}

---

**Step 2 – Model / equations:**

For {loading_condition}:

$$
{equation_latex}
$$

---

**Step 3 – Substitution:**

$$
{substitution_latex}
$$

---

**Step 4 – Result:**

- Effective design load:
  $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$

*Note: This equivalent UDL is used for serviceability deflection checks and span-to-depth ratio calculations per AS 3600 Cl. 8.5.4.*

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits.*
"""
    else:
        fd_ef_calc_md = rf"""
*Purpose: The effective design load $F_{{d,ef}}$ is used for span-to-depth ratio checks per AS 3600 Cl. 8.5.4. This value represents an equivalent uniform distributed load used in serviceability calculations.*

**Step 1 – Inputs:**

- Effective design load: $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$
- Effective span: $L = {L_m:.2f}\,\text{{m}}$
- Support condition: {support_type_display}
- Source: {value_source}

---

**Step 2 – Model / equations:**

Derivation inputs were unavailable; using the stored fallback value.

---

**Step 3 – Substitution:**

$$
F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}
$$

---

**Step 4 – Result:**

- Effective design load:
  $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$

*Note: This value is used for span-to-depth ratio calculations per AS 3600 Cl. 8.5.4.*

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_effective_load",
        title="Effective design load F_d,ef",
        summary_md=fd_ef_summary,
        status_kind=None,
        calc_md=fd_ef_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    util_span = (
        L_over_d / L_over_d_limit
        if L_over_d_limit is not None and L_over_d_limit > 0
        else None
    )
    span_defl_status = None
    if L_over_d_limit is not None and L_over_d_limit > 0 and L_over_d > 0:
        span_passes = L_over_d <= L_over_d_limit
        span_defl_status = "pass" if span_passes else "fail"

    limit_text = f"{L_over_d_limit:.1f}" if L_over_d_limit is not None else "—"

    # Guard against None values before formatting
    L_mm_display = L_mm if L_mm is not None else 6000.0
    d_display_span = d if d is not None else 550.0
    L_over_d_display = L_over_d if L_over_d is not None else 0.0
    k1_span_display = k1_span if k1_span is not None else 0.0
    k2_span_display = k2_span if k2_span is not None else 0.013
    defl_limit_ratio_display = defl_limit_ratio if defl_limit_ratio is not None else 250.0
    Fdef_kNm_display = Fdef_kNm if Fdef_kNm is not None else 12.0
    Ec_display_span = Ec if Ec is not None else 10000.0
    beff_display_span = beff if beff is not None else 300.0
    value_source_text_display = (
        value_source_text or "See Effective design load section above."
    )

    _span_res = (
        "PASS"
        if span_defl_status == "pass"
        else "FAIL"
        if span_defl_status == "fail"
        else "—"
    )
    span_summary = (
        f"**Check 5 — Span/depth deemed-to-conform check**  \n"
        f"$L_{{ef}}/d = {L_over_d_display:.1f}$ vs limit = {limit_text} | "
        f"Result: {_span_res}"
    )

    span_calc_md = rf"""
*Purpose: Check whether the span-to-depth ratio $L_{{ef}}/d$ satisfies the deemed-to-conform limit given in AS 3600:2018 Cl. 8.5.4, using the previously calculated $I_{{ef}}$ (via $k_1$).*

**Inputs:**

- Effective span (derived):
  $$
  L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm_display / 1000.0:.3f}\,\text{{m}} = {L_mm_display:.0f}\,\text{{mm}}
  $$
- Effective depth (derived): $d = {d_display_span:.1f}\,\text{{mm}}$
  ⇒ current ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} = {L_over_d_display:.1f}
  $$
- Support condition: {support_type}
- Stiffness factor from Iₑf step: $k_1 = {k1_span_display:.5f}$
- Deflection constant (support type): $k_2 = {k2_span_display:.5f}$
- Deflection limit (adopted: {defl_limit_label}):
  $$
  \left(\dfrac{{\Delta}}{{L_{{ef}}}}\right)_{{limit}} = \dfrac{{1}}{{{defl_limit_ratio_display:.0f}}}
  $$
- Effective design load (derived for span/depth): $F_{{d,ef}} = {Fdef_kNm_display:.2f}\,\text{{kN/m}}$
  *{value_source_text_display}*
- Concrete modulus (derived): $E_c = 4700\sqrt{{f'_c}} = {Ec_short:.0f}\,\text{{MPa}}$
- Effective modulus (derived): $E_{{c,eff}} = \dfrac{{E_c}}{{1+\varphi_{{cc}}(t)}} = {Ec_display_span:.0f}\,\text{{MPa}}$
- Effective flange width: $b_{{ef}} = {beff_display_span:.1f}\,\text{{mm}}$

---

**Formula:**

Deemed-to-conform span-to-depth limit:

$$
\frac{{L_{{ef}}}}{{d}} \le
\left[
\dfrac{{k_1 \, (\Delta/L_{{ef}}) \, b_{{ef}} E_{{c,eff}}}}{{k_2 F_{{d,ef}}}}
\right]^{{1/3}}
$$

---

**Substitution:**
"""
    if L_over_d_limit is not None:
        span_calc_md += rf"""

Right-hand-side limit:

$$
\left(\frac{{L_{{ef}}}}{{d}}\right)_{{limit}}
=
\left[
\dfrac{{({k1_span_display:.5f}) \times (1/{defl_limit_ratio_display:.0f}) \times ({beff_display_span:.1f}) \times ({Ec_display_span:.0f})}}
      {{({k2_span_display:.5f}) \times ({Fdef_kNm_display:.2f})}}
\right]^{{1/3}}
\approx {L_over_d_limit:.1f}
$$

---

**Result:**

- Allowed ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} \le {L_over_d_limit:.1f}
  $$
- Actual ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} = {L_over_d:.1f}
  $$

Conclusion: **{"✅ OK – deemed to conform" if span_defl_status == "pass" else "❌ NG – exceeds deemed limit"}**
"""
    else:
        span_calc_md += r"""

No limit could be computed because $F_{d,ef} \le 0$.

---

**Result:**

- Span/depth deemed-to-conform check not applicable for the current inputs.
"""

    span_calc_md += r"""

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_span_depth",
        title="Span/depth deemed-to-conform check",
        summary_md=span_summary,
        status_kind=span_defl_status,
        calc_md=span_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    
    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()