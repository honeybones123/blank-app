from __future__ import annotations
from typing import Dict, Any, List, Tuple
import plotly.graph_objects as go

from section_props.props import compute_gross_props
from section_props.shape_utils import normalise_shape_name
from section_props.reo_layout import (
    compute_longitudinal_reo_layout,
    flatten_reo_points,
    resolve_longitudinal_bars_from_layout,
    resolve_active_tension_reinforcement,
)
try:
    from section_props.section_layout import compute_shear_reo_layout_pure
except ImportError:
    # Fallback to the app-level layout helper if package resolution is partial during startup.
    from section_layout import compute_shear_reo_layout_pure
from section_props.shear_layout import compute_shear_reo_layout_T_I
from section_props.uls_flexure import (
    stress_block_factors_AS3600,
    solve_dn_from_T_T_I,
    compression_resultant_T_I,
)


def _build_flange_transverse_reo_geometry(
    *,
    shape_key: str,
    dims: Dict[str, float],
    reo: Dict[str, Any],
    resolved_longitudinal_bars: List[Dict[str, Any]] | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Build flange-contained transverse detailing reinforcement geometry.
    This helper is intentionally independent from web shear-ligature generators.
    """
    shapes: list[dict] = []
    warnings: list[str] = []

    if shape_key not in ("T", "I"):
        return shapes, warnings

    bf = float(dims.get("bf", 0.0) or 0.0)
    tf = float(dims.get("tf", 0.0) or 0.0)
    D = float(dims.get("D", 0.0) or 0.0)
    if bf <= 0.0 or tf <= 0.0 or D <= 0.0:
        return shapes, warnings

    web_w = float(dims.get("bw", dims.get("tw", bf)) or bf)
    x_web0 = (bf - web_w) / 2.0
    x_web1 = x_web0 + web_w

    cover_side = float(reo.get("cover_side", 40.0) or 40.0)
    cover_top = float(reo.get("cover_top", 40.0) or 40.0)
    cover_bot = float(reo.get("cover_bot", 40.0) or 40.0)
    # Flange–web junction is an internal horizontal face: use side cover (not top/bot of whole beam).
    cover_top_flange_soffit = float(reo.get("cover_top_flange_soffit", cover_side) or cover_side)
    cover_bot_flange_crown = float(reo.get("cover_bot_flange_crown", cover_side) or cover_side)

    bars = list(resolved_longitudinal_bars or [])

    def _single_flange_tie_rect(*, top: bool, dia: float, color: str) -> None:
        """
        Build one flange-local rectangular tie from flange longitudinal reo envelope.
        Falls back to cover-based flange bounds if envelope bars are unavailable.
        """
        inset = max(0.5 * dia, 2.0)
        x_min_lim = cover_side + inset
        x_max_lim = bf - cover_side - inset
        if top:
            y_min_lim = cover_top + inset
            y_max_lim = tf - cover_top_flange_soffit - inset
            flange_bars = [
                b for b in bars
                if str(b.get("face")) == "top" and "flange" in str(b.get("zone", ""))
            ]
        else:
            y_min_lim = (D - tf) + cover_bot_flange_crown + inset
            y_max_lim = D - cover_bot - inset
            flange_bars = [
                b for b in bars
                if str(b.get("face")) == "bottom" and "flange" in str(b.get("zone", ""))
            ]

        use_fallback = len(flange_bars) == 0
        if use_fallback:
            x0 = x_min_lim
            x1 = x_max_lim
            y0 = y_min_lim
            y1 = y_max_lim
            warnings.append("Flange transverse tie used flange-bound fallback (no resolved flange longitudinal bars found).")
        else:
            left_edge = min(float(b.get("x_mm", 0.0) or 0.0) - float(b.get("dia_mm", 0.0) or 0.0) / 2.0 for b in flange_bars)
            right_edge = max(float(b.get("x_mm", 0.0) or 0.0) + float(b.get("dia_mm", 0.0) or 0.0) / 2.0 for b in flange_bars)
            x0 = left_edge
            x1 = right_edge

            if top:
                top_bar_edge = min(float(b.get("y_mm", 0.0) or 0.0) - float(b.get("dia_mm", 0.0) or 0.0) / 2.0 for b in flange_bars)
                y0 = top_bar_edge
                y1 = y_max_lim
            else:
                y0 = y_min_lim
                bottom_bar_edge = max(float(b.get("y_mm", 0.0) or 0.0) + float(b.get("dia_mm", 0.0) or 0.0) / 2.0 for b in flange_bars)
                y1 = bottom_bar_edge

            # Gross flange pad + tiny hinge so bar-hugging coords are not erased by cover+tie inset.
            hinge = max(0.25, 0.05 * dia)
            if top:
                cx0, cx1 = hinge, bf - hinge
                cy0, cy1 = hinge, tf - hinge
            else:
                cx0, cx1 = hinge, bf - hinge
                cy0, cy1 = (D - tf) + hinge, D - hinge
            x0 = max(cx0, min(cx1, x0))
            x1 = max(cx0, min(cx1, x1))
            y0 = max(cy0, min(cy1, y0))
            y1 = max(cy0, min(cy1, y1))
            if x1 < x0:
                x0, x1 = x1, x0
            if y1 < y0:
                y0, y1 = y1, y0

        if (x1 - x0) <= 4.0 or (y1 - y0) <= 4.0:
            warnings.append("Flange transverse rectangular tie does not fit inside flange after cover/envelope placement.")
            return
        shapes.append(
            dict(
                type="rect",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(width=1.2, color=color),
                fillcolor="rgba(0,0,0,0)",
            )
        )

    top_enabled = bool(reo.get("top_flange_transverse_enabled", False))
    bot_enabled = bool(reo.get("bot_flange_transverse_enabled", False))
    top_dia = float(reo.get("top_flange_transverse_dia", 10.0) or 10.0)
    bot_dia = float(reo.get("bot_flange_transverse_dia", 10.0) or 10.0)
    _ = (
        int(reo.get("top_flange_transverse_legs", 2) or 2),
        int(reo.get("bot_flange_transverse_legs", 2) or 2),
        float(reo.get("top_flange_transverse_spacing", 200.0) or 200.0),
        float(reo.get("bot_flange_transverse_spacing", 200.0) or 200.0),
    )

    # Top flange tie: one rectangle fully inside y=[0, tf]
    if top_enabled and top_dia > 0.0:
        _single_flange_tie_rect(top=True, dia=top_dia, color="rgba(35,35,35,0.90)")

    # Bottom flange tie (I-sections): one rectangle fully inside y=[D-tf, D]
    if shape_key == "I" and bot_enabled and bot_dia > 0.0:
        _single_flange_tie_rect(top=False, dia=bot_dia, color="rgba(35,35,35,0.90)")

    return shapes, warnings


def make_sectionA_figure(
    *,
    shape_name: str,
    dims: Dict[str, float],
    reo: Dict[str, Any],
    show_shear: bool,
    show_dn: bool = False,
    dn: float = 0.0,
    tension_face: str | None = None,
) -> go.Figure:
    shape_key = normalise_shape_name(shape_name)
    tf_raw = (tension_face or "").strip().lower()
    tension_face_norm: str | None = tf_raw if tf_raw in ("bottom", "top") else None
    props = compute_gross_props(shape_key, dims)
    b = float(props["b_env"])
    D = float(props["D_env"])

    shapes = []
    traces = []

    def add_rect(x0, y0, x1, y1, lw=1.2):
        shapes.append(dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(width=lw, color="black"),
                           fillcolor="rgba(0,0,0,0)"))

    def add_path(points, lw=1.2):
        # points: list[(x,y)] closed or open; we will close it
        if not points:
            return
        p = points[:]
        if p[0] != p[-1]:
            p.append(p[0])
        d = f"M {p[0][0]},{p[0][1]} " + " ".join([f"L {x},{y}" for x, y in p[1:]]) + " Z"
        shapes.append(dict(type="path", path=d, line=dict(width=lw, color="black"), fillcolor="rgba(0,0,0,0)"))

    # ---- Outline ----
    if shape_key == "T":
        bf = float(dims["bf"]); tf = float(dims["tf"]); bw = float(dims["bw"])
        x_web0 = (bf - bw) / 2.0
        x_web1 = x_web0 + bw

        outline = [
            (0, 0),
            (bf, 0),
            (bf, tf),
            (x_web1, tf),
            (x_web1, D),
            (x_web0, D),
            (x_web0, tf),
            (0, tf),
        ]
        add_path(outline)

    elif shape_key == "I":
        bf = float(dims["bf"]); tf = float(dims["tf"]); tw = float(dims["tw"])
        x_web0 = (bf - tw) / 2.0
        x_web1 = x_web0 + tw

        outline = [
            (0, 0),
            (bf, 0),
            (bf, tf),
            (x_web1, tf),
            (x_web1, D - tf),
            (bf, D - tf),
            (bf, D),
            (0, D),
            (0, D - tf),
            (x_web0, D - tf),
            (x_web0, tf),
            (0, tf),
        ]
        add_path(outline)

    else:
        add_rect(0, 0, b, D)

    # ---- dn shading (cross-section only) ----
    if show_dn and dn and dn > 0:
        bf = float(dims["bf"])
        tf = float(dims["tf"])
        Dsec = float(dims["D"])
        dn_eff = min(float(dn), Dsec)

        if tension_face_norm == "top":
            # Hogging: compression zone below the neutral axis (y measured from top).
            shapes.append(dict(
                type="rect",
                x0=0.0, y0=float(dn_eff),
                x1=bf, y1=float(Dsec),
                line=dict(width=1.0, color="red"),
                fillcolor="rgba(255,0,0,0.12)",
                layer="below",
            ))
        else:
            # Sagging (or legacy): compression zone above the neutral axis.
            h1 = min(dn_eff, tf)
            if h1 > 0:
                shapes.append(dict(
                    type="rect",
                    x0=0.0, y0=0.0,
                    x1=bf, y1=h1,
                    line=dict(width=1.0, color="red"),
                    fillcolor="rgba(255,0,0,0.12)",
                    layer="below",
                ))

            if dn_eff > tf:
                if shape_name == "T":
                    b_web = float(dims["bw"])
                elif shape_name == "I":
                    b_web = float(dims["tw"])
                else:
                    b_web = bf

                x0w = (bf - b_web) / 2.0
                x1w = x0w + b_web

                shapes.append(dict(
                    type="rect",
                    x0=x0w, y0=tf,
                    x1=x1w, y1=dn_eff,
                    line=dict(width=1.0, color="red"),
                    fillcolor="rgba(255,0,0,0.12)",
                    layer="below",
                ))

        shapes.append(dict(
            type="line",
            x0=0.0, y0=dn_eff,
            x1=bf, y1=dn_eff,
            line=dict(width=1.2, color="red"),
        ))

    if shape_key in ("T", "I"):
        top_rows = [row for row in (reo.get("top_rows") or []) if row.get("active")]
        bottom_rows = [row for row in (reo.get("bottom_rows") or []) if row.get("active")]
        layout = compute_longitudinal_reo_layout(
            shape_name=shape_key,
            dims=dims,
            cover_side=float(reo["cover_side"]),
            cover_top=float(reo["cover_top"]),
            cover_bot=float(reo["cover_bot"]),
            min_clear_spacing=float(reo["min_clear_spacing"]),
            rowgap_top=float(reo["rowgap_top"]),
            rowgap_bot=float(reo["rowgap_bot"]),
            reo=reo,
            max_rows=max(len(top_rows), len(bottom_rows), 2),
        )
    else:
        layout = {"top": [], "bottom": []}

    # ---- Shear cage (optional) ----
    lig_d = float(reo.get("lig_d", 0.0))
    lig_legs = int(reo.get("lig_legs", 0))
    has_shear = show_shear and lig_d > 0 and lig_legs >= 2
    lig_line_width = max(1.0, min(4.0, abs(lig_d) / 3.0))

    if has_shear:
        is_rect = shape_key == "RECT"
        is_ti = shape_key in ("T", "I")

        if is_ti:
            shear = compute_shear_reo_layout_T_I(
                shape_name=shape_key,
                dims=dims,
                cover_side=float(reo["cover_side"]),
                cover_top=float(reo["cover_top"]),
                cover_bot=float(reo["cover_bot"]),
                lig_d=lig_d,
                lig_legs=lig_legs,
                reo_points=flatten_reo_points(layout),
            )
            cage = shear.get("cage")
            if cage:
                shapes.append(dict(type="rect", x0=cage["x0"], y0=cage["y0"], x1=cage["x1"], y1=cage["y1"],
                                   line=dict(width=lig_line_width, color="black"), fillcolor="rgba(0,0,0,0)"))
            for stirrup in shear.get("stirrups", []):
                for leg in stirrup.get("legs", []):
                    shapes.append(dict(type="line", x0=leg["x1"], y0=leg["y1"], x1=leg["x2"], y1=leg["y2"],
                                       line=dict(width=lig_line_width * 0.8, color="black")))
        elif is_rect:
            b = float(dims.get("b", 0.0) or 0.0)
            D = float(dims.get("D", 0.0) or 0.0)

            cover_side = float(reo.get("cover_side", 40.0) or 40.0)
            cover_top = float(reo.get("cover_top", 40.0) or 40.0)
            cover_bot = float(reo.get("cover_bot", 40.0) or 40.0)

            if lig_d > 0 and lig_legs >= 2:
                shear = compute_shear_reo_layout_pure(
                    b=b,
                    D=D,
                    cover_bot=cover_bot,
                    cover_top=cover_top,
                    cover_side=cover_side,
                    lig_d=lig_d,
                    lig_legs=lig_legs,
                )
                cage = shear.get("cage")
                if cage:
                    shapes.append(dict(
                        type="rect",
                        x0=cage["x0"], y0=cage["y0"], x1=cage["x1"], y1=cage["y1"],
                        line=dict(color="black", width=2),
                        fillcolor="rgba(0,0,0,0)",
                    ))
                for stirrup in shear.get("stirrups", []):
                    for leg in stirrup.get("legs", []):
                        shapes.append(dict(
                            type="line",
                            x0=leg["x1"], y0=leg["y1"], x1=leg["x2"], y1=leg["y2"],
                            line=dict(color="black", width=2),
                        ))

    # ---- Longitudinal bars (canonical resolved model) ----
    has_layout_bars = any(
        bool(band.get("x"))
        for bands in layout.values()
        if isinstance(bands, list)
        for band in bands
        if isinstance(band, dict)
    )
    resolved_bars = (
        resolve_longitudinal_bars_from_layout(
            shape_name=shape_key,
            dims=dims,
            reo_layout=layout,
        )
        if has_layout_bars
        else []
    )
    active_ids = set()
    if tension_face_norm in ("top", "bottom"):
        active = resolve_active_tension_reinforcement(
            dims,
            resolved_bars,
            "negative" if tension_face_norm == "top" else "positive",
        )
        active_ids = {str(bar.get("id")) for bar in (active.get("active_bars") or [])}

    zone_fill_active = {
        "web": "rgba(0,102,204,0.95)",
        "flange_left": "rgba(24,146,89,0.95)",
        "flange_right": "rgba(24,146,89,0.95)",
    }
    zone_fill_inactive = {
        "web": "rgba(130,130,130,0.45)",
        "flange_left": "rgba(130,130,130,0.45)",
        "flange_right": "rgba(130,130,130,0.45)",
    }
    for bar in resolved_bars:
        x = float(bar.get("x_mm", 0.0) or 0.0)
        y = float(bar.get("y_mm", 0.0) or 0.0)
        db = float(bar.get("dia_mm", 0.0) or 0.0)
        if db <= 0.0:
            continue
        zone = str(bar.get("zone", "web"))
        is_active = str(bar.get("id", "")) in active_ids if active_ids else False
        fill_rgba = (zone_fill_active if is_active else zone_fill_inactive).get(zone, "rgba(120,120,120,0.50)")
        line_col = "black" if is_active else "rgba(80,80,80,0.65)"
        r = db / 2.0
        shapes.append(dict(
            type="circle",
            x0=x - r, y0=y - r,
            x1=x + r, y1=y + r,
            line=dict(width=1.0, color=line_col),
            fillcolor=fill_rgba,
            opacity=1.0,
        ))

    # Optional flange transverse detailing/distribution reinforcement.
    # This uses flange-contained geometry only (not web stirrup geometry).
    flange_trans_shapes, flange_trans_warnings = _build_flange_transverse_reo_geometry(
        shape_key=shape_key,
        dims=dims,
        reo=reo,
        resolved_longitudinal_bars=resolved_bars,
    )
    shapes.extend(flange_trans_shapes)

    # Dev-only containment guards: every flange-transverse shape must stay in flange region.
    try:
        import streamlit as st

        if st.session_state.get("_dev_mode", False) and shape_key in ("T", "I"):
            bf = float(dims.get("bf", b) or b)
            tf = float(dims.get("tf", 0.0) or 0.0)
            web_w = float(dims.get("bw", dims.get("tw", bf)) or bf)
            x_web0 = (bf - web_w) / 2.0
            x_web1 = x_web0 + web_w
            Dsec = float(dims.get("D", D) or D)
            bad_ids = []
            for idx, sh in enumerate(flange_trans_shapes, start=1):
                if sh.get("type") != "rect":
                    bad_ids.append(idx)
                    continue
                x0 = float(sh.get("x0", 0.0) or 0.0)
                x1 = float(sh.get("x1", 0.0) or 0.0)
                y0 = float(sh.get("y0", 0.0) or 0.0)
                y1 = float(sh.get("y1", 0.0) or 0.0)
                dash_style = str(((sh.get("line") or {}).get("dash", "")) or "").strip().lower()
                if dash_style:
                    bad_ids.append(idx)
                # must be in top flange or bottom flange zone only
                in_top = (y0 >= -1e-6 and y1 <= tf + 1e-6)
                in_bottom = (shape_key == "I" and y0 >= (Dsec - tf) - 1e-6 and y1 <= Dsec + 1e-6)
                # single tie should stay inside flange width limits.
                in_flange_span = (x0 >= -1e-6) and (x1 <= bf + 1e-6)
                if not (in_top or in_bottom) or not in_flange_span:
                    bad_ids.append(idx)
            dev_warn = list(flange_trans_warnings)
            if bad_ids:
                dev_warn.append(f"Flange transverse geometry containment failed for shapes: {bad_ids}")
            st.session_state["_debug_flange_transverse_visual_warnings"] = dev_warn
    except Exception:
        pass

    if not traces:
        traces.append(go.Scatter(x=[0], y=[0], mode="markers", marker=dict(size=1, color="rgba(0,0,0,0)")))

    fig = go.Figure(data=traces)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(
        visible=False,
        scaleanchor="x",
        scaleratio=1,
        range=[D * 1.02, -0.10 * D],
    )
    fig.update_layout(
        height=520,
        margin=dict(l=0, r=0, t=0, b=40),
        shapes=shapes,
        dragmode=False,
        showlegend=False,
    )
    return fig


def build_stage1_payload(
    *,
    shape_name: str,
    dims: Dict[str, float],
    reo: Dict[str, Any],
) -> Dict[str, Any]:
    """
    This is the payload you will later drop into:
      - crack page
      - deflection page
      - report diagrams
    """
    shape_token = normalise_shape_name(shape_name)
    props = compute_gross_props(shape_token, dims)
    b_env = float(props["b_env"])
    D_env = float(props["D_env"])

    reo_layout = compute_longitudinal_reo_layout(
        shape_name=shape_name,
        dims=dims,
        cover_side=float(reo["cover_side"]),
        cover_top=float(reo["cover_top"]),
        cover_bot=float(reo["cover_bot"]),
        min_clear_spacing=float(reo["min_clear_spacing"]),
        rowgap_top=float(reo["rowgap_top"]),
        rowgap_bot=float(reo["rowgap_bot"]),
        reo=reo,
        max_rows=2,
    )

    payload = {
        "section": {
            "sec_shape_type": ("T" if shape_token == "T" else "I"),
            "sec_dims_mm": {k: float(v) for k, v in dims.items()},
            "sec_b_env_mm": b_env,
            "sec_D_env_mm": D_env,
            "sec_b_web_mm": float(props.get("b_web")),
        },
        "gross_props": {
            "sec_A_g_mm2": float(props["A_g"]),
            "sec_ybar_top_g_mm": float(props["ybar_top_g"]),
            "sec_Ixx_g_mm4": float(props["Ixx_g"]),
            "sec_Ztop_g_mm3": float(props["Ztop_g"]),
            "sec_Zbot_g_mm3": float(props["Zbot_g"]),
        },
        "reo": {
            "reo_inputs": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in reo.items()},
            "reo_layout": reo_layout,
            "reo_points": flatten_reo_points(reo_layout),
        },
        # --- Page bundles (Stage 1 uses these) ---
        "for_crack_page": {
            "A_g_mm2": float(props["A_g"]),
            "Ixx_g_mm4": float(props["Ixx_g"]),
            "Ztop_g_mm3": float(props["Ztop_g"]),
            "Zbot_g_mm3": float(props["Zbot_g"]),
            "ybar_top_g_mm": float(props["ybar_top_g"]),
            "D_env_mm": D_env,
            "reo_points": flatten_reo_points(reo_layout),
            "covers_mm": {
                "top": float(reo["cover_top"]),
                "bot": float(reo["cover_bot"]),
                "side": float(reo["cover_side"]),
            },
        },
        "for_deflection_page": {
            "Ixx_g_mm4": float(props["Ixx_g"]),
            "A_g_mm2": float(props["A_g"]),
            "ybar_top_g_mm": float(props["ybar_top_g"]),
            "D_env_mm": D_env,
            "reo_points": flatten_reo_points(reo_layout),
        },
        "for_report_diagrams": {
            "shape_name": shape_token,
            "dims_mm": {k: float(v) for k, v in dims.items()},
            "reo_inputs": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in reo.items()},
        },
    }
    payload["reo_points"] = payload["reo"]["reo_points"]
    payload["reo_layout"] = payload["reo"]["reo_layout"]
    # --- ULS bending helpers (T/I) ---
    # These are not "the bending design" yet — they are the exact functions + outputs you can plug into bending page.
    fc_demo = float(reo.get("fc_mpa", 50.0))  # optional; will default to 50 for demo
    alpha2, gamma = stress_block_factors_AS3600(fc_demo)

    payload["uls_helpers"] = {
        "fc_mpa": fc_demo,
        "alpha2": alpha2,
        "gamma": gamma,
        "notes": "Use solve_dn_from_T_T_I() with your actual T (from steel model) to get dn and yC for T/I sections.",
    }
    return payload
