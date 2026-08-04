"""Shared Deflection support and service-load runtime.

This module owns no Streamlit rendering.  It is the neutral dependency used by
calculation, reporting, diagram, and page layers that need the resolved support
condition or multispan publication adapter.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from calculations.deflection import (
    defl_support_type_from_design_selection,
    deflection_support_options_for_value,
    derive_equiv_udl_from_actions,
    governing_span_support_pair,
    multispan_deflection_metric_values,
    normalize_deflection_support_type,
    pick_controlling_span_index,
    resolve_deflection_equiv_loads_from_inputs,
    support_props,
)
from state_runtime_gateway import get_param, is_design_governing


# Compatibility names used by existing callers while page dependencies are
# removed.  Their authority remains calculations.deflection.
_deflection_support_options_for_value = deflection_support_options_for_value
_derive_equiv_udl_from_actions = derive_equiv_udl_from_actions
_governing_span_support_pair = governing_span_support_pair
_support_props = support_props


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
    """Compute and publish the canonical governing multispan metrics."""

    source = state if isinstance(state, dict) else st.session_state
    try:
        from beam_analysis import solve_beam_structure
    except Exception:
        solve_beam_structure = None

    metrics = multispan_deflection_metric_values(
        state=source,
        Ec=Ec,
        Ief=Ief,
        g_kNm=g_kNm,
        q_kNm=q_kNm,
        psi_s=psi_s,
        defl_limit_ratio=defl_limit_ratio,
        Ast=Ast,
        Asc=Asc,
        actions_mode_default=get_param("actions_mode", "manual"),
        psi_point_default=get_param("psi_point", 0.4),
        psi_udl_default=get_param("psi_udl", 0.4),
        solve_beam_structure_fn=solve_beam_structure,
    )

    if not metrics.get("available"):
        source.pop("defl_span_deflections_mm", None)
        source.pop("defl_span_utilisations", None)
        source.pop("defl_multispan_metrics_source", None)
        return metrics

    span_deflections_mm = metrics["span_deflections_mm"]
    span_utilisations = metrics["span_utilisations"]
    source["defl_span_deflections_mm"] = span_deflections_mm
    source["defl_span_utilisations"] = span_utilisations
    source["defl_multispan_metrics_source"] = metrics["metrics_source"]
    return {
        "available": True,
        "span_deflections_mm": span_deflections_mm,
        "span_utilisations": span_utilisations,
    }


def get_deflection_diagram_support_condition(state: dict | None = None) -> dict:
    """Resolve the canonical Deflection support condition without UI imports."""

    source = state if isinstance(state, dict) else st.session_state
    actions_mode = source.get("actions_mode")
    if actions_mode is None or (
        isinstance(actions_mode, str) and actions_mode.strip() == ""
    ):
        actions_mode = get_param("actions_mode", "manual")
    mode = str(actions_mode or "manual").strip().lower()
    if mode not in ("manual", "design"):
        mode = "manual"
    if is_design_governing():
        mode = "design"

    raw_widget = str(
        source.get("defl_support_type")
        or get_param("defl_support_type", "Simply supported")
        or "Simply supported"
    )
    canonical = normalize_deflection_support_type(raw_widget)

    beam_mode = str(
        source.get("sfd_beam_system_mode")
        or source.get("design_beam_system_mode")
        or ""
    ).strip()
    raw_case = str(source.get("sfd_case", "") or "").strip()
    if beam_mode == "Single span":
        is_multi = False
    elif beam_mode == "Multi-span":
        is_multi = True
    else:
        is_multi = (
            raw_widget.strip().casefold() == "continuous beam"
            or raw_case.startswith("Multi-span continuous beam")
        )

    controlling_idx = 0
    controlling_reason = "single-span"
    continuous_end_side = None

    if mode == "manual":
        resolved = canonical
        controlling_reason = "manual selection"
    elif is_multi:
        controlling_idx, controlling_reason = pick_controlling_span_index(source)
        try:
            n_spans = int(float(source.get("sfd_span_count", 0.0) or 0.0))
        except Exception:
            n_spans = 0
        if n_spans >= 2:
            resolved = (
                "Continuous â€“ end span"
                if controlling_idx in (0, n_spans - 1)
                else "Continuous â€“ interior span"
            )
            if controlling_idx == 0:
                continuous_end_side = "right"
            elif controlling_idx == n_spans - 1:
                continuous_end_side = "left"
        else:
            resolved = "Continuous â€“ interior span"
    else:
        load_case = str(source.get("sfd_case", "") or "")
        support_condition = source.get("design_support_condition") or source.get(
            "sfd_support_condition"
        )
        resolved = normalize_deflection_support_type(
            defl_support_type_from_design_selection(load_case, support_condition)
        )
        controlling_reason = "design single-span (SFD)"

    return {
        "support_type": normalize_deflection_support_type(resolved),
        "mode": mode,
        "canonical_support_type": canonical,
        "multi_span": bool(is_multi),
        "controlling_span_idx": int(max(0, controlling_idx)),
        "controlling_reason": controlling_reason,
        "continuous_end_side": continuous_end_side,
    }


def get_resolved_deflection_support_type(state: dict | None = None) -> str:
    """Return the resolved support label used by calculations and summaries."""

    return get_deflection_diagram_support_condition(state)["support_type"]


def deflection_has_service_load_for_calc(state: dict[str, Any] | None = None) -> bool:
    """Return whether the resolved service-load model has positive total load."""

    source = state if isinstance(state, dict) else st.session_state
    g_udl = get_param("g_udl_kNm_per_m", None)
    q_udl = get_param("q_udl_kNm_per_m", None)
    w_sls = get_param("w_sls_kNm_per_m", None)
    sls_M_kNm = get_param("sls_Mstar", 0.0)
    sls_V_kN = get_param("sls_Vstar", 0.0)
    L_m = float(get_param("L", 3000.0) or 0.0) / 1000.0
    L_m_for_fd = get_param("defl_L_eff", L_m)
    if L_m_for_fd is None or L_m_for_fd <= 0:
        L_m_for_fd = get_param("span_L_m", L_m)
    support_type = get_deflection_diagram_support_condition(source).get(
        "support_type", "Simply supported"
    )
    derived = derive_equiv_udl_from_actions(
        M_kNm=sls_M_kNm,
        V_kN=sls_V_kN,
        L_m=float(L_m_for_fd or 0.0),
        support_type=str(support_type),
    )
    g_eq, q_eq = resolve_deflection_equiv_loads_from_inputs(
        derived=derived,
        w_sls=w_sls,
        g_udl=g_udl,
        q_udl=q_udl,
    )
    return (float(g_eq) + float(q_eq)) > 1e-12


__all__ = [
    "_deflection_support_options_for_value",
    "_derive_equiv_udl_from_actions",
    "_governing_span_support_pair",
    "_support_props",
    "compute_and_store_multispan_deflection_metrics",
    "deflection_has_service_load_for_calc",
    "get_deflection_diagram_support_condition",
    "get_resolved_deflection_support_type",
]
