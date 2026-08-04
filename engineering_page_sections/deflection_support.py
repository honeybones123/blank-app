"""Deflection support and multispan section ownership."""

from __future__ import annotations

from deflection_support import (
    compute_and_store_multispan_deflection_metrics,
    get_deflection_diagram_support_condition,
    get_resolved_deflection_support_type,
)


def bind_runtime(namespace: dict) -> None:
    """Bind calculation adapters used by the page coordinator."""

    globals().update(
        {
            key: value
            for key, value in namespace.items()
            if not key.startswith("__")
        }
    )


def _refresh_deflection_effective_span_from_mm(
    L_mm,
    fallback_mm: float = 0.0,
) -> float | None:
    try:
        L_current_mm = float(L_mm if L_mm is not None else fallback_mm)
    except (TypeError, ValueError):
        L_current_mm = float(fallback_mm or 0.0)
    if not math.isfinite(L_current_mm) or L_current_mm <= 0.0:
        return None
    L_eff_m = L_current_mm / 1000.0
    st.session_state["defl_L_eff"] = L_eff_m
    return L_eff_m


def seed_design_deflection_support_widget_before_render(
    widget_key: str,
    resolved: str,
) -> None:
    if str(st.session_state.get("actions_mode", "manual") or "manual") != "design":
        return
    support_type = _normalize_deflection_support_type(resolved)
    try:
        st.session_state["defl_support_type"] = support_type
        if widget_key:
            st.session_state[str(widget_key)] = support_type
    except Exception:
        pass


def _is_design_multispan_mode(state: dict) -> bool:
    return _calc_is_design_multispan_mode(
        state,
        actions_mode_default=get_param("actions_mode", "manual"),
    )


def _multispan_design_elastic_loads(source: dict):
    return _calc_multispan_design_elastic_loads(
        source,
        psi_point_default=get_param("psi_point", 0.4),
        psi_udl_default=get_param("psi_udl", 0.4),
    )


def _active_multispan_lengths_m(state: dict) -> list[float]:
    return _calc_active_multispan_lengths_m(state)
