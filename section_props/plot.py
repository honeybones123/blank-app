from __future__ import annotations

from typing import Dict, Optional
import plotly.graph_objects as go


def plot_shape(shape_name: str, dims: Dict[str, float], reo: Optional[Dict[str, float]] = None) -> go.Figure:
    """
    Plotly 2D section diagram with the SAME conventions as your real app:
    - shapes list for outlines
    - traces list for bars
    - y-axis reversed
    - axis hidden
    """
    shapes = []
    traces = []

    # Determine section envelope width/depth
    b = None
    D = None

    # ---- outline helpers ----
    def add_rect(x0, y0, x1, y1, lw=1.2):
        shapes.append(
            dict(
                type="rect",
                x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(width=lw, color="black"),
                fillcolor="rgba(0,0,0,0)",
            )
        )

    # ---- create outlines ----
    if shape_name.startswith("Rectangle"):
        b, D = float(dims["b"]), float(dims["D"])
        add_rect(0, 0, b, D)

    elif shape_name.startswith("Hollow Rectangle"):
        b, D = float(dims["b"]), float(dims["D"])
        t = float(dims["t"])
        add_rect(0, 0, b, D)
        add_rect(t, t, b - t, D - t)

    elif shape_name.startswith("T-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); bw = float(dims["bw"]); D = float(dims["D"])
        b = bf
        add_rect(0, 0, bf, tf)              # flange
        xw = (bf - bw) / 2.0
        add_rect(xw, tf, xw + bw, D)        # web

    elif shape_name.startswith("I-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); tw = float(dims["tw"]); D = float(dims["D"])
        b = bf
        add_rect(0, 0, bf, tf)              # top flange
        xw = (bf - tw) / 2.0
        add_rect(xw, tf, xw + tw, D - tf)   # web
        add_rect(0, D - tf, bf, D)          # bottom flange

    elif shape_name.startswith("Circle") or shape_name.startswith("Hollow Circle"):
        D = float(dims["D"]); b = D
        shapes.append(dict(type="circle", x0=0, y0=0, x1=D, y1=D, line=dict(width=1.2, color="black")))
        if shape_name.startswith("Hollow Circle"):
            t = float(dims["t"])
            shapes.append(dict(type="circle", x0=t, y0=t, x1=D-t, y1=D-t, line=dict(width=1.2, color="black")))

    else:
        b, D = 400.0, 600.0
        add_rect(0, 0, b, D)

    # ---- reo overlay using same 2-layer structure as app ----
    if reo and b and D and not (shape_name.startswith("Circle") or shape_name.startswith("Hollow Circle")):
        from .section_layout import compute_longitudinal_reo_layout

        layout = compute_longitudinal_reo_layout(
            b=b, D=D,
            cover_side=float(reo.get("cover_side", reo.get("cover", 40.0))),
            cover_top=float(reo.get("cover_top", reo.get("cover", 40.0))),
            cover_bot=float(reo.get("cover_bot", reo.get("cover", 40.0))),
            nb_top=int(reo.get("n_top", 0)),
            db_top=float(reo.get("db_top", reo.get("db", 20.0))),
            nb_bot=int(reo.get("n_bot", 0)),
            db_bot=float(reo.get("db_bot", reo.get("db", 20.0))),
            min_clear_spacing=float(reo.get("s_min", 20.0)),
            rowgap_top=float(reo.get("rowgap_top", 60.0)),
            rowgap_bot=float(reo.get("rowgap_bot", 60.0)),
        )

        # ----- Shear reinforcement (stirrups/ties) - only draw when present -----
        lig_d = float(reo.get("lig_d", 0.0))
        lig_legs = int(reo.get("lig_legs", 0))
        lig_line_width = max(1.0, min(4.0, abs(lig_d) / 3.0))

        has_shear = lig_d > 0 and lig_legs >= 2

        if has_shear:
            from .section_layout import compute_shear_reo_layout_pure

            cover_top = float(reo.get("cover_top", reo.get("cover", 40.0)))
            cover_bot = float(reo.get("cover_bot", reo.get("cover", 40.0)))
            cover_side = float(reo.get("cover_side", min(cover_top, cover_bot)))

            shear_layout = compute_shear_reo_layout_pure(
                b=b, D=D,
                cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
                lig_d=lig_d, lig_legs=lig_legs,
            )

            cage_shear = shear_layout.get("cage")
            if cage_shear:
                shapes.append(
                    dict(
                        type="rect",
                        x0=cage_shear["x0"], y0=cage_shear["y0"],
                        x1=cage_shear["x1"], y1=cage_shear["y1"],
                        line=dict(width=lig_line_width, color="black"),
                        fillcolor="rgba(0,0,0,0)",
                    )
                )

            for stirrup in shear_layout.get("stirrups", []):
                for leg in stirrup.get("legs", []):
                    shapes.append(
                        dict(
                            type="line",
                            x0=leg["x1"], y0=leg["y1"],
                            x1=leg["x2"], y1=leg["y2"],
                            line=dict(width=lig_line_width * 0.8, color="black"),
                        )
                    )

        # BOTTOM reinforcement (blue)
        for layer in layout.get("bottom", []):
            xs = layer["x"]
            ys = layer["y"]
            db = float(layer.get("db", 0.0))
            marker_size = max(5, min(10, db * 0.35))
            traces.append(
                go.Scatter(
                    x=xs, y=ys,
                    mode="markers",
                    marker=dict(color="blue", size=marker_size, line=dict(width=0.7, color="black")),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        # TOP reinforcement (red)
        for layer in layout.get("top", []):
            xs = layer["x"]
            ys = layer["y"]
            db = float(layer.get("db", 0.0))
            marker_size = max(5, min(10, db * 0.35))
            traces.append(
                go.Scatter(
                    x=xs, y=ys,
                    mode="markers",
                    marker=dict(color="red", size=marker_size, line=dict(width=0.7, color="black")),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    if not traces:
        traces.append(go.Scatter(x=[0], y=[0], mode="markers", marker=dict(size=1, color="rgba(0,0,0,0)")))

    fig = go.Figure(data=traces)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(
        visible=False,
        scaleanchor="x",
        scaleratio=1,
        range=[D * 1.02, -0.10 * D],  # SAME as your real app
    )
    fig.update_layout(
        height=520,
        margin=dict(l=0, r=0, t=0, b=40),
        shapes=shapes,
        dragmode=False,
        showlegend=False,
    )
    return fig


def apply_section_axes(fig: go.Figure, *, W: float, D: float, pad_frac: float = 0.20) -> go.Figure:
    pad = pad_frac * W
    fig.update_xaxes(range=[-pad, W + pad])
    fig.update_yaxes(range=[D + 0.15 * D, -0.15 * D])
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig
