from __future__ import annotations
from typing import Dict, Any
import plotly.graph_objects as go

from props import compute_gross_props
from reo_layout import compute_longitudinal_reo_layout_T_I as compute_longitudinal_reo_layout, flatten_reo_points
from shear_layout import compute_shear_reo_layout_T_I
from uls_flexure import stress_block_factors_AS3600, solve_dn_from_T_T_I, compression_resultant_T_I


def make_sectionA_figure(
    *,
    shape_name: str,
    dims: Dict[str, float],
    reo: Dict[str, Any],
    show_shear: bool,
    show_dn: bool = False,
    dn: float = 0.0,
) -> go.Figure:
    props = compute_gross_props(shape_name, dims)
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
    if shape_name.startswith("T-Section"):
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

    elif shape_name.startswith("I-Section"):
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

        # Always shade flange portion (0..min(dn, tf)) across bf
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

        # If dn goes below flange, shade web portion (tf..dn) across bw/tw (centered)
        if dn_eff > tf:
            if shape_name.startswith("T-Section"):
                b_web = float(dims["bw"])
            elif shape_name.startswith("I-Section"):
                b_web = float(dims["tw"])
            else:
                b_web = bf  # safety fallback

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

        # Optional: a red neutral-axis line at y = dn_eff (matches your screenshot)
        shapes.append(dict(
            type="line",
            x0=0.0, y0=dn_eff,
            x1=bf, y1=dn_eff,
            line=dict(width=1.2, color="red"),
        ))

    # ---- Shear cage (optional) ----
    lig_d = float(reo.get("lig_d", 0.0))
    lig_legs = int(reo.get("lig_legs", 0))
    has_shear = show_shear and lig_d > 0 and lig_legs >= 2
    lig_line_width = max(1.0, min(4.0, abs(lig_d) / 3.0))

    if has_shear:
        shear = compute_shear_reo_layout_T_I(
            shape_name=shape_name,
            dims=dims,
            cover_side=float(reo["cover_side"]),
            cover_top=float(reo["cover_top"]),
            cover_bot=float(reo["cover_bot"]),
            lig_d=lig_d,
            lig_legs=lig_legs,
        )
        cage = shear.get("cage")
        if cage:
            shapes.append(dict(type="rect", x0=cage["x0"], y0=cage["y0"], x1=cage["x1"], y1=cage["y1"],
                               line=dict(width=lig_line_width, color="black"), fillcolor="rgba(0,0,0,0)"))
        for stirrup in shear.get("stirrups", []):
            for leg in stirrup.get("legs", []):
                shapes.append(dict(type="line", x0=leg["x1"], y0=leg["y1"], x1=leg["x2"], y1=leg["y2"],
                                   line=dict(width=lig_line_width * 0.8, color="black")))

    # ---- Longitudinal bars (TO-SCALE: circles in data units mm) ----
    layout = compute_longitudinal_reo_layout(
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

    def _as_y_scalar(y_val):
        # layout sometimes stores y as [y] list
        if isinstance(y_val, (list, tuple)) and len(y_val) > 0:
            return float(y_val[0])
        return float(y_val)

    def _add_bar_circles(band, fill_rgba):
        xs = band.get("x") or []
        y = _as_y_scalar(band.get("y", 0.0))
        db = float(band.get("db") or 0.0)
        if db <= 0 or not xs:
            return
        r = db / 2.0
        for x in xs:
            x = float(x)
            shapes.append(dict(
                type="circle",
                x0=x - r, y0=y - r,
                x1=x + r, y1=y + r,
                line=dict(width=1.0, color="black"),
                fillcolor=fill_rgba,
                opacity=1.0,
            ))

    # Bottom bars (blue)
    for band in layout.get("bottom", []) or []:
        _add_bar_circles(band, "rgba(0,0,255,0.90)")

    # Top bars (red)
    for band in layout.get("top", []) or []:
        _add_bar_circles(band, "rgba(255,0,0,0.90)")

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
    props = compute_gross_props(shape_name, dims)
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
            "sec_shape_type": ("T" if shape_name.startswith("T-Section") else "I"),
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
            "shape_name": shape_name,
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
