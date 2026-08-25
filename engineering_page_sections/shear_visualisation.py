"""Shear visualisation layout and support adapters."""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from engineering_page_sections.shear_stress_field import (
    MCFT_STRESS_FIELD_CHART_KEY,
    build_mcft_stress_field_figure,
)
from shear_visuals import (
    BEHAVIOUR_VISUAL_HEIGHT,
    BEHAVIOUR_VISUAL_WIDTH,
    SIDE_VIEW_VISUAL_WIDTH,
)
from ui.design_tokens import BENDING_DIAGRAM_PLOT_HEIGHT_PX
from widgets_helpers import (
    compact_side_view_figure,
    render_plotly_diagram,
)


SHEAR_VISUAL_HEIGHT_PX = BEHAVIOUR_VISUAL_HEIGHT
SHEAR_BEHAVIOUR_MAX_WIDTH_PX = BEHAVIOUR_VISUAL_WIDTH
SHEAR_SIDE_VIEW_MAX_WIDTH_PX = SIDE_VIEW_VISUAL_WIDTH
SHEAR_VISUAL_MAX_WIDTH_PX = 760
SHEAR_VISUAL_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}
MCFT_BEHAVIOUR_MARGIN = dict(l=10, r=10, t=8, b=10)
SHEAR_DIAGRAM_VIEWS = ("Side view", "Section", "Shear diagram", "MCFT")
SHEAR_DIAGRAM_PLOT_HEIGHT_PX = BENDING_DIAGRAM_PLOT_HEIGHT_PX
SHEAR_DIAGRAM_BUNDLE_VERSION = 1
SHEAR_DIAGRAM_BUNDLE_CACHE_KEY = "_shear_diagram_bundle_cache"
SHEAR_DIAGRAM_BUNDLE_CACHE_LIMIT = 2
MCFT_OPTION_KEYS = (
    "show_stm_overlay",
    "show_stm_flow",
    "show_load_flow",
    "show_cracks",
    "show_stress_block",
)
SHEAR_SIDE_VIEW_CAPTION = (
    "Side view: required zone spacings from Check 10 when available; otherwise "
    "provided spacing (s_lig). φV_u check uses effective spacing (provided "
    "unless auto spacing applies envelope spacing)."
)


@dataclass(frozen=True)
class ShearVisualisationRuntime:
    """Explicit application dependencies for the Shear diagram viewport."""

    st: Any
    get_param: Callable[..., Any]
    render_timing_mark: Callable[[str], None]
    render_plotly_diagram: Callable[..., Any]
    render_centered_plotly: Callable[..., Any]
    render_animated_plotly: Callable[..., Any]
    render_section_title: Callable[[str], Any]
    info_button: Callable[..., Any]
    render_lazy_expander: Callable[..., Any]
    render_tabs: Callable[..., Any]
    build_cross_section_figure: Callable[..., go.Figure]
    build_side_view_figure: Callable[..., go.Figure]
    build_sfd_bmd_figure: Callable[..., tuple[go.Figure, go.Figure]]
    theta_v_deg: float


def _canonical_json_value(value: Any) -> Any:
    """Return deterministic JSON-safe presentation identity data."""

    if isinstance(value, dict):
        return {
            str(key): _canonical_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_canonical_json_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _mcft_option_key(options: dict[str, bool]) -> str:
    return "".join("1" if bool(options[key]) else "0" for key in MCFT_OPTION_KEYS)


def _current_mcft_options(st_module: Any) -> dict[str, bool]:
    defaults = {
        "show_stm_overlay": False,
        "show_stm_flow": False,
        "show_load_flow": False,
        "show_cracks": True,
        "show_stress_block": False,
    }
    return {
        key: bool(st_module.session_state.get(f"shear_{key}", default))
        for key, default in defaults.items()
    }


def _all_mcft_option_states() -> tuple[dict[str, bool], ...]:
    return tuple(
        dict(zip(MCFT_OPTION_KEYS, bits, strict=True))
        for bits in itertools.product((False, True), repeat=len(MCFT_OPTION_KEYS))
    )


def _support_pair_from_resolved_support_type(
    support_type: str | None,
) -> tuple[str, str] | None:
    raw_label = str(support_type or "").strip()
    label = raw_label.replace("-", "–")
    if not label:
        return None
    if raw_label == "Fixed-ended":
        return ("Fixed", "Fixed")
    if label == "Fixed–Pinned":
        return ("Fixed", "Pinned")
    if label == "Pinned–Fixed":
        return ("Pinned", "Fixed")
    if label in (
        "Pinned–Pinned",
        "Continuous – end span",
        "Continuous – interior span",
    ):
        return ("Pinned", "Pinned")
    if label == "Simply supported":
        return ("Pinned", "Roller")
    return None

def _standardise_shear_visual_layout(fig, *, title_pad_t: int = 28):
    fig.update_layout(
        autosize=True,
        height=SHEAR_VISUAL_HEIGHT_PX,
        margin=dict(l=10, r=10, t=title_pad_t, b=10),
    )
    return fig


def _render_centered_shear_plotly(
    fig,
    *,
    chart_key: str,
    max_width_px: int = SHEAR_VISUAL_MAX_WIDTH_PX,
    height_px: int = SHEAR_VISUAL_HEIGHT_PX,
    title_pad_t: int = 28,
    compact_top: bool = False,
    config: dict | None = None,
):
    """Mount a Shear Plotly figure in the established centered frame."""

    fig = _standardise_shear_visual_layout(fig, title_pad_t=title_pad_t)
    fig.update_layout(height=int(height_px))
    wrapper_id = f"shear-plot-wrap-{chart_key}"
    compact_top_css = ""
    if compact_top:
        compact_top_css = "margin-top: 0 !important; padding-top: 0 !important;"

    st.markdown(
        f"""
        <style>
        div[data-testid="stVerticalBlock"] div[data-testid="stElementContainer"]:has(#{wrapper_id}) {{
            width: 100%;
        }}
        #{wrapper_id} {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            {compact_top_css}
        }}
        #{wrapper_id} > div {{
            width: min(100%, {max_width_px}px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f'<div id="{wrapper_id}"><div>', unsafe_allow_html=True)
    render_plotly_diagram(
        fig,
        key=chart_key,
        title="Shear diagram",
        center=True,
        config=config or SHEAR_VISUAL_CONFIG,
    )
    st.markdown("</div></div>", unsafe_allow_html=True)


def _build_shear_cross_section(runtime: ShearVisualisationRuntime) -> go.Figure:
    runtime.render_timing_mark("shear.visualisation.section.build.start")
    figure = runtime.build_cross_section_figure(
        height=SHEAR_DIAGRAM_PLOT_HEIGHT_PX
    )
    figure = compact_side_view_figure(
        _standardise_shear_visual_layout(figure, title_pad_t=8),
        height_px=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
    )
    runtime.render_timing_mark("shear.visualisation.section.build.end")
    return figure


def _render_shear_cross_section(
    runtime: ShearVisualisationRuntime,
    figure: go.Figure | None = None,
) -> None:
    figure = figure or _build_shear_cross_section(runtime)
    runtime.render_timing_mark("shear.visualisation.section.mount.start")
    runtime.render_plotly_diagram(
        figure,
        key="shear_section_diagram",
        title="Shear section",
        center=True,
        config=SHEAR_VISUAL_CONFIG,
    )
    runtime.render_timing_mark("shear.visualisation.section.mount.end")


def _build_shear_side_view(runtime: ShearVisualisationRuntime) -> go.Figure:
    runtime.render_timing_mark("shear.visualisation.side.build.start")
    try:
        phi_vu = float(runtime.get_param("phi_Vu_cap") or 0.0)
        v_eq = float(runtime.get_param("V_eq_kN") or 0.0)
    except (TypeError, ValueError):
        phi_vu, v_eq = 0.0, 0.0
    shear_fails = phi_vu > 0.0 and v_eq > phi_vu + 1e-9
    figure = compact_side_view_figure(
        runtime.build_side_view_figure(
            shear_fails=shear_fails,
            height=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
        ),
        height_px=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
    )
    runtime.render_timing_mark("shear.visualisation.side.build.end")
    return figure


def _render_shear_side_view(
    runtime: ShearVisualisationRuntime,
    figure: go.Figure | None = None,
) -> None:
    figure = figure or _build_shear_side_view(runtime)
    runtime.render_timing_mark("shear.visualisation.side.mount.start")
    runtime.render_plotly_diagram(
        figure,
        key="shear_side_view_diagram",
        title="Shear side view",
        center=True,
        config=SHEAR_VISUAL_CONFIG,
    )
    runtime.render_timing_mark("shear.visualisation.side.mount.end")


def _resolve_shear_visual_supports(
    runtime: ShearVisualisationRuntime,
    length_m: float,
) -> tuple[list[float], list[str]]:
    """Reuse the existing support projection used by the V(x) diagram."""

    from deflection_support import (
        _governing_span_support_pair,
        get_deflection_diagram_support_condition,
    )

    support_positions: list[float] = []
    support_types: list[str] = []
    beam_mode = str(
        runtime.get_param("design_beam_system_mode", "Single span") or "Single span"
    )
    support_resolution = get_deflection_diagram_support_condition(
        runtime.st.session_state
    )
    support_pair = _governing_span_support_pair(
        runtime.st.session_state,
        support_resolution,
    )

    if (
        beam_mode == "Multi-span"
        and isinstance(support_pair, tuple)
        and len(support_pair) == 2
    ):
        try:
            span_count = max(
                1,
                int(
                    float(
                        runtime.st.session_state.get("sfd_span_count", 0.0)
                        or 0.0
                    )
                ),
            )
        except Exception:
            span_count = 1
        controlling_index = int(
            support_resolution.get("controlling_span_idx", 0) or 0
        )
        controlling_index = max(0, min(controlling_index, span_count - 1))
        try:
            span_length_m = float(
                runtime.st.session_state.get(
                    f"sfd_span_len_{controlling_index + 1}", 0.0
                )
                or 0.0
            )
        except Exception:
            span_length_m = 0.0
        if abs(float(span_length_m) - float(length_m)) <= 1e-6:
            support_positions = [0.0, float(length_m)]
            support_types = [str(support_pair[0]), str(support_pair[1])]

    if not support_positions or not support_types:
        support_label = str(
            support_resolution.get("support_type")
            or runtime.get_param("defl_support_type", "Simply supported")
            or "Simply supported"
        )
        support_pair_fallback = _support_pair_from_resolved_support_type(
            support_label
        )
        if "cantilever" in support_label.lower():
            support_positions = [0.0]
            support_types = ["Fixed"]
        elif (
            isinstance(support_pair_fallback, tuple)
            and len(support_pair_fallback) == 2
        ):
            support_positions = [0.0, float(length_m)]
            support_types = [
                str(support_pair_fallback[0]),
                str(support_pair_fallback[1]),
            ]
        else:
            support_positions = [0.0, float(length_m)]
            support_types = ["Pinned", "Roller"]

    return support_positions, support_types


def _build_shear_force_diagram(runtime: ShearVisualisationRuntime) -> go.Figure:
    """Render the established authoritative/fallback V(x) projection."""

    runtime.render_timing_mark("shear.visualisation.force.build.start")
    mode = str(runtime.get_param("actions_mode", "manual") or "manual").strip().lower()
    length_m = max(
        float(runtime.get_param("L", 3000.0) or 3000.0) / 1000.0,
        0.1,
    )
    shear_x_value = runtime.get_param("shear_x", [])
    shear_v_signed_value = runtime.get_param("shear_V_signed", [])
    shear_v_value = runtime.get_param("shear_V", [])
    shear_x_raw = np.asarray(
        [] if shear_x_value is None else shear_x_value,
        dtype=float,
    )
    shear_v_signed_raw = np.asarray(
        [] if shear_v_signed_value is None else shear_v_signed_value,
        dtype=float,
    )
    shear_v_raw = np.asarray(
        [] if shear_v_value is None else shear_v_value,
        dtype=float,
    )
    support_type = str(
        runtime.get_param(
            "support_type",
            runtime.get_param("defl_support_type", "simply_supported"),
        )
        or "simply_supported"
    ).strip().lower()

    if mode == "design" and shear_x_raw.size > 1:
        if shear_v_signed_raw.size == shear_x_raw.size:
            x_plot = shear_x_raw
            v_plot = shear_v_signed_raw
        elif shear_v_raw.size == shear_x_raw.size:
            x_plot = shear_x_raw
            v_plot = shear_v_raw
        else:
            x_plot = np.linspace(0.0, length_m, 100)
            v_plot = np.zeros_like(x_plot, dtype=float)
    else:
        x_plot = np.linspace(0.0, length_m, 100)
        v_star = float(runtime.get_param("uls_Vstar", 0.0) or 0.0)
        if "cantilever" in support_type:
            v_plot = v_star * (1.0 - x_plot / max(length_m, 1e-9))
        else:
            v_plot = v_star * (1.0 - 2.0 * x_plot / max(length_m, 1e-9))

    support_positions, support_types = _resolve_shear_visual_supports(
        runtime,
        length_m,
    )
    figure, _ = runtime.build_sfd_bmd_figure(
        x=x_plot,
        V=v_plot,
        M=np.zeros_like(x_plot, dtype=float),
        L=length_m,
        support_positions=support_positions,
        support_types=support_types,
    )
    figure.update_layout(height=SHEAR_DIAGRAM_PLOT_HEIGHT_PX)
    runtime.render_timing_mark("shear.visualisation.force.build.end")
    return figure


def _render_shear_force_diagram(
    runtime: ShearVisualisationRuntime,
    figure: go.Figure | None = None,
) -> None:
    figure = figure or _build_shear_force_diagram(runtime)
    runtime.render_timing_mark("shear.visualisation.force.mount.start")
    runtime.render_plotly_diagram(
        figure,
        key="shear_visual_sfd_diagram",
        title="Shear force diagram",
        center=True,
        config=SHEAR_VISUAL_CONFIG,
    )
    runtime.render_timing_mark("shear.visualisation.force.mount.end")


def _render_plotly_in_mcft_column(
    fig: go.Figure,
    *,
    chart_key: str,
    render_centered_plotly: Callable[..., Any],
) -> None:
    """MCFT static Plotly: same pipeline as side view / cross-section (full-width block)."""
    render_centered_plotly(
        fig,
        chart_key=chart_key,
        max_width_px=SHEAR_BEHAVIOUR_MAX_WIDTH_PX,
        height_px=SHEAR_VISUAL_HEIGHT_PX,
        title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
        compact_top=True,
    )

def _render_mcft_behaviour_chart(
    fig: go.Figure,
    *,
    chart_key: str,
    animated: bool,
    render_centered_plotly: Callable[..., Any],
    render_animated_plotly: Callable[..., Any],
    height_px: int | None = None,
) -> None:
    plot_h = int(height_px or fig.layout.height or SHEAR_VISUAL_HEIGHT_PX)
    if animated:
        render_animated_plotly(
            fig,
            height=plot_h,
            centered=True,
            chart_key=chart_key,
            compact_top=True,
            title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
            max_width_px=int(BEHAVIOUR_VISUAL_WIDTH),
        )
    else:
        render_centered_plotly(
            fig,
            chart_key=chart_key,
            max_width_px=SHEAR_BEHAVIOUR_MAX_WIDTH_PX,
            height_px=plot_h,
            title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
            compact_top=True,
        )


def _shear_diagram_bundle_fingerprint(runtime: ShearVisualisationRuntime) -> str:
    """Fingerprint only authoritative/presentation inputs used by Shear figures."""

    from inputs_application.active_beam_engineering_state import (
        resolve_active_beam_engineering_state,
    )
    from inputs_application.authoritative_check_packs import (
        current_authoritative_family,
    )

    active_inputs = resolve_active_beam_engineering_state(runtime.st.session_state)
    parameter_names = (
        "actions_mode",
        "loads_edit_mode",
        "sfd_case",
        "load_case",
        "L",
        "span_L_m",
        "sfd_L_m",
        "a_m",
        "load_a_point",
        "a_udl_m",
        "sfd_a_udl",
        "a_cant_m",
        "sfd_a_cant",
        "a_overhang_m",
        "sfd_a_overhang",
        "w_uls_kNm_per_m",
        "w_sls_kNm_per_m",
        "P_uls_kN",
        "P_sls_kN",
        "design_actions_source",
        "design_section_committed",
        "design_section_x_m",
        "section_cursor_x_m",
        "s_lig",
        "lig_legs",
        "phi_Vu_cap",
        "V_eq_kN",
        "shear_auto_design",
        "support_type",
        "defl_support_type",
        "design_beam_system_mode",
        "sfd_span_count",
        "uls_Vstar",
        "active_tension_face",
    )
    state_names = (
        "section_layout",
        "shear_zone_results",
        "shear_x",
        "shear_V_signed",
        "shear_V",
    )
    span_lengths = {
        key: value
        for key, value in runtime.st.session_state.items()
        if str(key).startswith("sfd_span_len_")
    }
    payload = {
        "version": SHEAR_DIAGRAM_BUNDLE_VERSION,
        "beam_revision": active_inputs.revision,
        "engineering_hash": active_inputs.engineering_hash,
        "authority_hash": active_inputs.authority_hash,
        "active_inputs": dict(active_inputs.values),
        "authoritative_shear": current_authoritative_family(
            runtime.st.session_state, "shear"
        ),
        "theta_v_deg": float(runtime.theta_v_deg),
        "parameters": {
            name: runtime.get_param(name, None) for name in parameter_names
        },
        "state": {
            name: runtime.st.session_state.get(name) for name in state_names
        },
        "span_lengths": span_lengths,
    }
    encoded = json.dumps(
        _canonical_json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _shear_bundle_cache(st_module: Any) -> dict[str, Any]:
    cache = st_module.session_state.get(SHEAR_DIAGRAM_BUNDLE_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {"entries": {}, "order": []}
        st_module.session_state[SHEAR_DIAGRAM_BUNDLE_CACHE_KEY] = cache
    cache.setdefault("entries", {})
    cache.setdefault("order", [])
    return cache


def _touch_shear_bundle_cache(cache: dict[str, Any], fingerprint: str) -> None:
    order = [
        str(value)
        for value in list(cache.get("order", []))
        if str(value) != fingerprint
    ]
    order.append(fingerprint)
    entries = cache["entries"]
    while len(order) > SHEAR_DIAGRAM_BUNDLE_CACHE_LIMIT:
        entries.pop(order.pop(0), None)
    cache["order"] = order


def _load_shear_diagram_bundle(
    runtime: ShearVisualisationRuntime,
    fingerprint: str,
) -> dict[str, Any] | None:
    cache = _shear_bundle_cache(runtime.st)
    entry = cache["entries"].get(fingerprint)
    if not isinstance(entry, dict):
        return None
    mcft = entry.get("mcft")
    if not isinstance(mcft, dict) or len(mcft) != 2 ** len(MCFT_OPTION_KEYS):
        cache["entries"].pop(fingerprint, None)
        return None
    try:
        bundle = {
            "fingerprint": fingerprint,
            "side": pio.from_json(str(entry["side"])),
            "section": pio.from_json(str(entry["section"])),
            "force": pio.from_json(str(entry["force"])),
            "mcft": mcft,
        }
    except (KeyError, TypeError, ValueError):
        cache["entries"].pop(fingerprint, None)
        return None
    _touch_shear_bundle_cache(cache, fingerprint)
    return bundle


def _build_shear_diagram_bundle(
    runtime: ShearVisualisationRuntime,
    fingerprint: str,
) -> dict[str, Any]:
    """Prepare every Shear view and every MCFT display-option projection."""

    runtime.render_timing_mark("shear.diagram.bundle.build.start")
    side = _build_shear_side_view(runtime)
    section = _build_shear_cross_section(runtime)
    force = _build_shear_force_diagram(runtime)
    mcft: dict[str, dict[str, Any]] = {}
    for options in _all_mcft_option_states():
        figure, animated = build_mcft_stress_field_figure(
            theta_v_deg=float(runtime.theta_v_deg),
            options=options,
        )
        # The side view and MCFT panels share the same 320 px viewport. The
        # former animated-only 18 px reduction made MCFT visibly shorter even
        # though its surrounding shell remained 320 px high.
        plot_height_px = int(SHEAR_DIAGRAM_PLOT_HEIGHT_PX)
        figure.update_layout(height=plot_height_px)
        mcft[_mcft_option_key(options)] = {
            "figure": figure.to_json(),
            "animated": bool(animated),
        }

    cache = _shear_bundle_cache(runtime.st)
    cache["entries"][fingerprint] = {
        "side": side.to_json(),
        "section": section.to_json(),
        "force": force.to_json(),
        "mcft": mcft,
    }
    _touch_shear_bundle_cache(cache, fingerprint)
    runtime.render_timing_mark("shear.diagram.bundle.build.end")
    return {
        "fingerprint": fingerprint,
        "side": side,
        "section": section,
        "force": force,
        "mcft": mcft,
    }


def _render_shear_diagram_loading_shell(
    runtime: ShearVisualisationRuntime,
    *,
    view_key: str,
) -> None:
    """Reserve the same 320 px canvas used by every live Shear diagram."""

    runtime.st.markdown(
        '<div class="shear-diagram-loading-region" '
        f'data-shear-diagram-shell="{view_key}" '
        'data-shear-diagram-geometry-token="--sb-bending-diagram-plot-height" '
        'role="status" aria-live="polite">'
        '<div class="shear-diagram-loading-shell">'
        '<span class="shear-diagram-loading-icon" aria-hidden="true">&#9711;</span>'
        '<span class="shear-diagram-loading-copy">Shear diagrams loading</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _render_shear_mcft_view(
    runtime: ShearVisualisationRuntime,
    prepared: dict[str, Any] | None = None,
) -> None:
    """Render the existing MCFT projection inside the shared diagram shell."""

    if prepared is not None:
        figure = pio.from_json(str(prepared["figure"]))
        _render_mcft_behaviour_chart(
            figure,
            chart_key=MCFT_STRESS_FIELD_CHART_KEY,
            animated=bool(prepared.get("animated", False)),
            render_centered_plotly=runtime.render_centered_plotly,
            render_animated_plotly=runtime.render_animated_plotly,
            height_px=int(figure.layout.height or SHEAR_DIAGRAM_PLOT_HEIGHT_PX),
        )
        return

    from engineering_page_sections.shear_stress_field import (
        render_mcft_stress_field_diagram,
    )

    render_mcft_stress_field_diagram(
        st_module=runtime.st,
        theta_v_deg=float(runtime.theta_v_deg),
        render_plotly_diagram=runtime.render_plotly_diagram,
        render_animated_plotly=runtime.render_animated_plotly,
        height_px=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
    )


def _render_mcft_display_options(runtime: ShearVisualisationRuntime) -> None:
    """Place the established MCFT overlay controls on the diagram itself."""

    from engineering_page_sections.shear_stress_field import (
        render_mcft_display_options,
    )

    _, info_col = runtime.st.columns([0.95, 0.05])
    with info_col:
        with runtime.info_button(
            help_text=(
                "Strut-and-tie model, strut-and-tie flow, MCFT load flow, "
                "cracks and stress-block overlays for this diagram."
            )
        ):
            render_mcft_display_options(runtime.st)


def _render_stress_field_teaching(runtime: ShearVisualisationRuntime) -> None:
    from engineering_page_sections.shear_stress_field import (
        render_stress_field_teaching,
    )

    runtime.render_lazy_expander(
        "The Stress Field: Explaining the Modified Compression Field Theory and Strut-and-Tie Model",
        lambda: render_stress_field_teaching(
            st_module=runtime.st,
            theta_v_deg=float(runtime.theta_v_deg),
            render_centered_plotly=runtime.render_centered_plotly,
            body_only=True,
        ),
        key="shear_stress_field_teaching_expander",
    )


def _render_shear_mcft_panel_impl(
    runtime: ShearVisualisationRuntime,
    fingerprint: str,
) -> None:
    """Render the cached MCFT projection and its presentation controls."""

    st_module = runtime.st
    bundle = _load_shear_diagram_bundle(runtime, fingerprint)
    if bundle is None:
        return
    options = _current_mcft_options(st_module)
    option_key = _mcft_option_key(options)
    prepared = bundle["mcft"][option_key]
    st_module.markdown(
        '<span data-shear-mcft-option-key="'
        f'{option_key}" aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    _render_shear_mcft_view(runtime, prepared)
    with st_module.container(key="shear_mcft_diagram_options"):
        _render_mcft_display_options(runtime)


_render_shear_mcft_panel = st.fragment(_render_shear_mcft_panel_impl)


def _render_shear_visualisation_bending_pattern(
    runtime: ShearVisualisationRuntime,
    *,
    diagram_shell_generation: int,
) -> None:
    """Render Shear diagrams with the proven native Bending lifecycle."""

    st_module = runtime.st
    generation = int(diagram_shell_generation)
    fingerprint = _shear_diagram_bundle_fingerprint(runtime)
    runtime.render_timing_mark("shear.diagram.bundle.cache_lookup.start")
    bundle = _load_shear_diagram_bundle(runtime, fingerprint)
    cache_hit = bundle is not None
    runtime.render_timing_mark(
        "shear.diagram.bundle.cache_hit"
        if cache_hit
        else "shear.diagram.bundle.cache_miss"
    )

    bundle_clicked = st_module.button(
        "Prepare Shear diagram bundle",
        key="shear_deferred_bundle_button",
    )
    if bundle is None and bundle_clicked:
        from application.visualization_runtime_warmup import (
            start_visualization_runtime_warmup,
            wait_for_visualization_runtime_warmup,
        )

        start_visualization_runtime_warmup()
        wait_for_visualization_runtime_warmup()
        bundle = _build_shear_diagram_bundle(runtime, fingerprint)

    st_module.markdown(
        """
<style>
.st-key-shear_side_plot_frame,
.st-key-shear_section_plot_frame,
.st-key-shear_force_plot_frame,
.st-key-shear_mcft_plot_frame {
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) !important;
  width: 100%;
  min-height: var(--sb-bending-diagram-plot-height, 320px);
  overflow: hidden !important;
}
.st-key-shear_side_plot_frame > div[data-testid="stLayoutWrapper"],
.st-key-shear_section_plot_frame > div[data-testid="stLayoutWrapper"],
.st-key-shear_force_plot_frame > div[data-testid="stLayoutWrapper"],
.st-key-shear_mcft_plot_frame > div[data-testid="stLayoutWrapper"] {
  grid-area: 1 / 1 !important;
  width: 100%;
  min-width: 0 !important;
  max-width: 100% !important;
}
.st-key-shear_side_diagram_shell,
.st-key-shear_section_diagram_shell,
.st-key-shear_force_diagram_shell,
.st-key-shear_mcft_diagram_shell {
  z-index: 2;
  height: var(--sb-bending-diagram-plot-height, 320px);
  pointer-events: none !important;
}
.st-key-shear_side_diagram_live,
.st-key-shear_section_diagram_live,
.st-key-shear_force_diagram_live,
.st-key-shear_mcft_diagram_live {
  z-index: 1;
  min-height: var(--sb-bending-diagram-plot-height, 320px);
}
.st-key-shear_side_diagram_live > div[data-testid="stElementContainer"],
.st-key-shear_section_diagram_live > div[data-testid="stElementContainer"],
.st-key-shear_force_diagram_live > div[data-testid="stElementContainer"],
.st-key-shear_mcft_diagram_live > div[data-testid="stElementContainer"] {
  margin-bottom: 0 !important;
}
.shear-diagram-loading-region {
  box-sizing: border-box;
  height: var(--sb-bending-diagram-plot-height, 320px);
  width: 100%;
  overflow: hidden;
  background: #fff;
  color: #10234a;
  pointer-events: none !important;
}
.shear-diagram-loading-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .7rem;
  height: 100%;
  padding: .85rem 1rem;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  color: #475569;
}
.shear-diagram-loading-copy {
  font-size: .92rem;
  font-weight: 600;
  line-height: 1.4;
}
.st-key-shear_side_diagram_caption,
.st-key-shear_section_diagram_caption,
.st-key-shear_force_diagram_caption,
.st-key-shear_mcft_diagram_caption {
  box-sizing: border-box;
  height: 3rem;
  min-height: 3rem;
  overflow: hidden;
  margin: 0 !important;
  padding: .25rem 0 0 !important;
}
.st-key-shear_mcft_diagram_live
> div[data-testid="stLayoutWrapper"]
> div[data-testid="stVerticalBlock"] {
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) !important;
  grid-template-rows: var(--sb-bending-diagram-plot-height, 320px) !important;
}
.st-key-shear_mcft_diagram_live
> div[data-testid="stLayoutWrapper"]
> div[data-testid="stVerticalBlock"]
> div[data-testid="stLayoutWrapper"] {
  grid-area: 1 / 1 !important;
  min-width: 0 !important;
  max-width: 100% !important;
}
.st-key-shear_mcft_diagram_live
div[data-testid="stLayoutWrapper"]:has(.st-key-shear_mcft_diagram_options) {
  z-index: 2 !important;
  height: 0 !important;
  min-height: 0 !important;
  overflow: visible !important;
}
.st-key-shear_mcft_diagram_options {
  pointer-events: none;
  padding: .25rem .35rem 0 0;
}
.st-key-shear_mcft_diagram_options [data-testid="stPopover"] {
  pointer-events: auto;
}
html:has(.st-key-shear_side_diagram_live .js-plotly-plot)
.st-key-shear_side_plot_frame
> div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_side_diagram_shell),
html:has(.st-key-shear_section_diagram_live .js-plotly-plot)
.st-key-shear_section_plot_frame
> div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_section_diagram_shell),
html:has(.st-key-shear_force_diagram_live .js-plotly-plot)
.st-key-shear_force_plot_frame
> div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_force_diagram_shell),
html:has(.st-key-shear_mcft_diagram_live .js-plotly-plot)
.st-key-shear_mcft_plot_frame
> div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_mcft_diagram_shell),
html:has(.st-key-shear_mcft_diagram_live iframe)
.st-key-shear_mcft_plot_frame
> div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_mcft_diagram_shell) {
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
}
.st-key-shear_deferred_bundle_button {
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
}
</style>
<div id="shear-visuals-block" aria-hidden="true"
     style="display:none;width:0;height:0;overflow:hidden"></div>
        """,
        unsafe_allow_html=True,
    )

    runtime.render_section_title("Visualisation")
    side_tab, section_tab, force_tab, mcft_tab = runtime.render_tabs(
        st_module,
        labels=SHEAR_DIAGRAM_VIEWS,
        scope_id="shear-diagram-navigation",
    )
    with side_tab:
        with st_module.container(key="shear_side_plot_frame"):
            with st_module.container(key="shear_side_diagram_shell"):
                _render_shear_diagram_loading_shell(runtime, view_key="side")
            with st_module.container(key="shear_side_diagram_live"):
                if bundle is not None:
                    _render_shear_side_view(runtime, bundle["side"])
        with st_module.container(key="shear_side_diagram_caption"):
            st_module.caption(SHEAR_SIDE_VIEW_CAPTION)
    with section_tab:
        with st_module.container(key="shear_section_plot_frame"):
            with st_module.container(key="shear_section_diagram_shell"):
                _render_shear_diagram_loading_shell(runtime, view_key="section")
            with st_module.container(key="shear_section_diagram_live"):
                if bundle is not None:
                    _render_shear_cross_section(runtime, bundle["section"])
        with st_module.container(key="shear_section_diagram_caption"):
            st_module.caption("\u00a0")
    with force_tab:
        with st_module.container(key="shear_force_plot_frame"):
            with st_module.container(key="shear_force_diagram_shell"):
                _render_shear_diagram_loading_shell(runtime, view_key="force")
            with st_module.container(key="shear_force_diagram_live"):
                if bundle is not None:
                    _render_shear_force_diagram(runtime, bundle["force"])
        with st_module.container(key="shear_force_diagram_caption"):
            st_module.caption("\u00a0")
    with mcft_tab:
        with st_module.container(key="shear_mcft_plot_frame"):
            with st_module.container(key="shear_mcft_diagram_shell"):
                _render_shear_diagram_loading_shell(runtime, view_key="mcft")
            with st_module.container(key="shear_mcft_diagram_live"):
                if bundle is not None:
                    _render_shear_mcft_panel(runtime, fingerprint)
        with st_module.container(key="shear_mcft_diagram_caption"):
            from engineering_page_sections.shear_stress_field import (
                MCFT_ILLUSTRATION_DISCLAIMER,
            )

            st_module.caption(MCFT_ILLUSTRATION_DISCLAIMER)

    _render_stress_field_teaching(runtime)
    st_module.markdown(
        '<span data-shear-lightweight-ready="'
        f'{generation}" aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    if bundle is not None:
        cache_status = "hit" if cache_hit else "miss"
        st_module.markdown(
            '<span data-shear-diagram-bundle-published="1" '
            f'data-shear-bundle-fingerprint="{fingerprint}" '
            f'data-shear-bundle-cache="{cache_status}" '
            f'data-shear-mcft-projection-count="{len(bundle["mcft"])}" '
            'aria-hidden="true" style="display:none"></span>',
            unsafe_allow_html=True,
        )

    import streamlit.components.v1 as components

    if bundle is not None:
        components.html(
            f"""
<script>
(() => {{
  const doc = window.parent.document;
  const generation = {generation};
  const fingerprint = {fingerprint!r};
  const runtimeKey = '__sbShearDiagramReadyRuntime';
  const prior = window.parent[runtimeKey];
  if (prior && prior.cleanup) prior.cleanup();
  let cancelled = false;
  let timer = 0;
  const completePlot = (selector) => {{
    const plot = doc.querySelector(selector);
    if (!plot || !plot._fullLayout || !plot._fullData) return false;
    return Boolean(
      plot.querySelector('.scatterlayer .trace')
      || plot.querySelector('g.shapelayer .shape-group')
    );
  }};
  const completeMcft = () => completePlot(
    '.st-key-shear_mcft_diagram_live .js-plotly-plot'
  ) || Boolean(doc.querySelector('.st-key-shear_mcft_diagram_live iframe'));
  const markReady = () => {{
    if (cancelled) return;
    const published = [...doc.querySelectorAll(
      '[data-shear-diagram-bundle-published="1"]'
    )].find((node) =>
      node.getAttribute('data-shear-bundle-fingerprint') === fingerprint
    );
    const complete = Boolean(
      published
      && completePlot('.st-key-shear_side_diagram_live .js-plotly-plot')
      && completePlot('.st-key-shear_section_diagram_live .js-plotly-plot')
      && completePlot('.st-key-shear_force_diagram_live .js-plotly-plot')
      && completeMcft()
    );
    if (!complete) {{
      timer = window.setTimeout(markReady, 25);
      return;
    }}
    published.setAttribute('data-testid', 'shear-diagram-ready');
    published.setAttribute('data-shear-diagram-ready', String(generation));
    published.setAttribute(
      'data-shear-diagram-bundle-ready', String(generation)
    );
  }};
  markReady();
  window.parent[runtimeKey] = {{
    cleanup: () => {{
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    }}
  }};
}})();
</script>
            """,
            height=0,
        )
    else:
        components.html(
            f"""
<script>
(() => {{
  const doc = window.parent.document;
  const generation = {generation};
  const runtimeKey = '__sbShearDiagramBundleRuntime';
  const prior = window.parent[runtimeKey];
  if (prior && prior.cleanup) prior.cleanup();
  let cancelled = false;
  let timer = 0;
  const requestBundleAfterPaint = () => {{
    if (cancelled) return;
    const light = doc.querySelector(
      `[data-shear-lightweight-ready="${{generation}}"]`
    );
    const page = doc.querySelector(
      `[data-shear-page-lightweight-ready="${{generation}}"]`
    );
    const ready = doc.querySelector(
      `[data-shear-diagram-bundle-ready="${{generation}}"]`
    );
    if (ready) return;
    if (!light || !page) {{
      timer = window.setTimeout(requestBundleAfterPaint, 25);
      return;
    }}
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {{
      if (cancelled) return;
      doc.documentElement.setAttribute(
        'data-sb-shear-lightweight-painted', String(generation)
      );
      timer = window.setTimeout(() => {{
        const button = doc.querySelector(
          '.st-key-shear_deferred_bundle_button button'
        );
        if (button && !button.disabled) button.click();
      }}, 150);
    }}));
  }};
  requestBundleAfterPaint();
  window.parent[runtimeKey] = {{
    cleanup: () => {{
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    }}
  }};
}})();
</script>
            """,
            height=0,
        )


def render_shear_visualisation_block(
    runtime: ShearVisualisationRuntime,
    *,
    diagram_shell_generation: int,
) -> None:
    """Render the Shear bundle through the native Bending diagram pattern."""

    _render_shear_visualisation_bending_pattern(
        runtime,
        diagram_shell_generation=diagram_shell_generation,
    )


__all__ = [
    "MCFT_BEHAVIOUR_MARGIN",
    "SHEAR_SIDE_VIEW_MAX_WIDTH_PX",
    "SHEAR_BEHAVIOUR_MAX_WIDTH_PX",
    "SHEAR_VISUAL_CONFIG",
    "SHEAR_DIAGRAM_PLOT_HEIGHT_PX",
    "SHEAR_DIAGRAM_VIEWS",
    "SHEAR_VISUAL_HEIGHT_PX",
    "SHEAR_VISUAL_MAX_WIDTH_PX",
    "ShearVisualisationRuntime",
    "_render_centered_shear_plotly",
    "_render_mcft_behaviour_chart",
    "_render_plotly_in_mcft_column",
    "_render_shear_cross_section",
    "_render_shear_side_view",
    "_render_shear_force_diagram",
    "_render_shear_mcft_panel_impl",
    "_render_shear_mcft_view",
    "_standardise_shear_visual_layout",
    "render_shear_visualisation_block",
]
