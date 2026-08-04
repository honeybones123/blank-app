from __future__ import annotations

import logging
import numpy as np
import plotly.graph_objects as go

from .reo_layout import dev_warnings_bars_outside_concrete, resolve_longitudinal_bars_from_layout
from .shear_layout import compute_shear_reo_layout_T_I

_log = logging.getLogger(__name__)


def _box_mesh(x0, x1, y0, y1, z0, z1):
    """
    Returns vertices + triangle indices for a rectangular box Mesh3d.
    Matches the style used in the main app (simple triangulated prism).
    """
    vx = np.array([x0, x1, x1, x0, x0, x1, x1, x0], dtype=float)
    vy = np.array([y0, y0, y1, y1, y0, y0, y1, y1], dtype=float)
    vz = np.array([z0, z0, z0, z0, z1, z1, z1, z1], dtype=float)

    tri_i = [0, 0, 0, 4, 4, 1, 5, 2, 6, 3, 7, 6]
    tri_j = [1, 2, 3, 5, 7, 5, 6, 6, 7, 7, 4, 2]
    tri_k = [2, 3, 0, 6, 4, 2, 7, 3, 4, 0, 5, 1]
    return vx, vy, vz, tri_i, tri_j, tri_k


def _add_cylinder_surface(traces, x0, x1, y0, z0, db, color_hex):
    """True-scale longitudinal bar as a cylinder surface (radius=db/2 in data units)."""
    r = float(db) / 2.0
    if r <= 0:
        return

    n_theta = 16  # performance/quality balance
    theta = np.linspace(0.0, 2.0 * np.pi, n_theta)

    X = np.column_stack([np.full(n_theta, float(x0)), np.full(n_theta, float(x1))])
    Y = np.column_stack([float(y0) + r * np.cos(theta), float(y0) + r * np.cos(theta)])
    Z = np.column_stack([float(z0) + r * np.sin(theta), float(z0) + r * np.sin(theta)])

    traces.append(
        go.Surface(
            x=X, y=Y, z=Z,
            colorscale=[[0, color_hex], [1, color_hex]],
            showscale=False,
            opacity=1.0,
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _beamwise_stirrup_x_positions(L_vis: float, s_eff: float) -> list[float]:
    """Stirrup / tie station positions along beam axis (0 .. L_vis), capped for performance."""
    x_positions = [0.0]
    x = float(s_eff)
    while x < float(L_vis) - 1e-6:
        x_positions.append(float(x))
        x += float(s_eff)
    if float(L_vis) not in x_positions:
        x_positions.append(float(L_vis))
    max_frames = 250
    if len(x_positions) > max_frames:
        step = max(1, len(x_positions) // max_frames)
        x_positions = x_positions[::step]
        if x_positions[-1] != float(L_vis):
            x_positions.append(float(L_vis))
    return x_positions


def _outer_cage_from_reo_points(reo_points, *, b_env: float, D_env: float):
    if not reo_points:
        return None

    try:
        min_y = min(float(pt["x"]) - float(pt["db"]) / 2.0 for pt in reo_points)
        max_y = max(float(pt["x"]) + float(pt["db"]) / 2.0 for pt in reo_points)
        min_z = min(float(pt["y"]) - float(pt["db"]) / 2.0 for pt in reo_points)
        max_z = max(float(pt["y"]) + float(pt["db"]) / 2.0 for pt in reo_points)
    except Exception:
        return None

    y0 = max(5.0, min_y)
    y1 = min(float(b_env) - 5.0, max_y)
    z0 = max(5.0, min_z)
    z1 = min(float(D_env) - 5.0, max_z)
    if y1 <= y0 or z1 <= z0:
        return None
    return {"x0": y0, "x1": y1, "y0": z0, "y1": z1}


def make_section_3d_figure(
    *,
    shape_name: str,
    dims: dict,
    reo_layout: dict | None,
    reo_inputs: dict | None = None,
    show_shear: bool = False,
    L_vis: float = 900.0,
):
    """
    3D section/short-extrusion viewer matching the main app's look:
      - x = beam length
      - y = section width axis (same as 2D x)
      - z = section depth from top (same as 2D y), with autorange reversed

    Concrete is drawn as union of boxes (flange/web).
    Bars are drawn as Scatter3d lines along x (0..L_vis).
    """
    shape = (shape_name or "").strip()


    # -------------------------
    # Concrete geometry (T + I only)
    # -------------------------
    meshes = []

    def add_concrete_box(y0, y1, z0, z1):
        vx, vy, vz, ii, jj, kk = _box_mesh(0.0, float(L_vis), y0, y1, z0, z1)
        meshes.append(
            go.Mesh3d(
                x=vx,
                y=vy,
                z=vz,
                i=ii,
                j=jj,
                k=kk,
                color="#cccccc",
                opacity=0.25,
                flatshading=True,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if shape.startswith("T"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); bw = float(dims["bw"]); D = float(dims["D"])
        x_web0 = (bf - bw) / 2.0
        x_web1 = x_web0 + bw

        # flange (top): z 0..tf, y 0..bf
        add_concrete_box(0.0, bf, 0.0, tf)
        # web: z tf..D, y x_web0..x_web1
        add_concrete_box(x_web0, x_web1, tf, D)

        b_env = bf
        D_env = D

    elif shape.startswith("I"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); tw = float(dims["tw"]); D = float(dims["D"])
        x_web0 = (bf - tw) / 2.0
        x_web1 = x_web0 + tw

        # top flange: z 0..tf, y 0..bf
        add_concrete_box(0.0, bf, 0.0, tf)
        # web: z tf..(D-tf), y x_web0..x_web1
        if D - tf > tf:
            add_concrete_box(x_web0, x_web1, tf, D - tf)
        # bottom flange: z (D-tf)..D, y 0..bf
        add_concrete_box(0.0, bf, D - tf, D)

        b_env = bf
        D_env = D

    else:
        raise ValueError("3D section viewer (Stage 1) supports T and I sections only.")

    def _outline_points_T_I(shape_label, dims_map):
        pts = []
        if shape_label.startswith("T"):
            bf = float(dims_map["bf"]); tf = float(dims_map["tf"]); bw = float(dims_map["bw"]); D = float(dims_map["D"])
            x_web0 = (bf - bw) / 2.0
            x_web1 = x_web0 + bw
            pts = [
                (0.0, 0.0),
                (bf, 0.0),
                (bf, tf),
                (x_web1, tf),
                (x_web1, D),
                (x_web0, D),
                (x_web0, tf),
                (0.0, tf),
                (0.0, 0.0),
            ]
        elif shape_label.startswith("I"):
            bf = float(dims_map["bf"]); tf = float(dims_map["tf"]); tw = float(dims_map["tw"]); D = float(dims_map["D"])
            x_web0 = (bf - tw) / 2.0
            x_web1 = x_web0 + tw
            pts = [
                (0.0, 0.0),
                (bf, 0.0),
                (bf, tf),
                (x_web1, tf),
                (x_web1, D - tf),
                (bf, D - tf),
                (bf, D),
                (0.0, D),
                (0.0, D - tf),
                (x_web0, D - tf),
                (x_web0, tf),
                (0.0, tf),
                (0.0, 0.0),
            ]
        return pts

    # -------------------------
    # Bars (extruded cylinders)
    # reo_layout format: {"top":[{"x":[...],"y":[...],"db":..}, ...], "bottom":[...]}
    # -------------------------
    traces = []
    traces.extend(meshes)

    # --- Wireframe outline like RECT viewer ---
    pts2d = _outline_points_T_I(shape, dims)
    ys = [p[0] for p in pts2d]  # section x -> 3D y
    zs = [p[1] for p in pts2d]  # section y -> 3D z (depth from top)

    wire_color = "rgba(20,20,20,0.95)"
    wire_w = 6

    # outline at x=0 and x=L_vis
    traces.append(go.Scatter3d(
        x=[0.0] * len(pts2d),
        y=ys, z=zs,
        mode="lines",
        line=dict(width=wire_w, color=wire_color),
        hoverinfo="skip",
        showlegend=False,
    ))
    traces.append(go.Scatter3d(
        x=[float(L_vis)] * len(pts2d),
        y=ys, z=zs,
        mode="lines",
        line=dict(width=wire_w, color=wire_color),
        hoverinfo="skip",
        showlegend=False,
    ))

    # connect vertices along length
    for i in range(len(pts2d) - 1):
        traces.append(go.Scatter3d(
            x=[0.0, float(L_vis)],
            y=[ys[i], ys[i]],
            z=[zs[i], zs[i]],
            mode="lines",
            line=dict(width=wire_w, color=wire_color),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Longitudinal bars: one cylinder per resolved bar (same source as 2D section plots).
    # Avoid merging duplicate top/bottom + top_web/bottom_web lists and wrong depth for each x.
    reo_points: list[dict] = []
    if reo_layout:
        resolved = resolve_longitudinal_bars_from_layout(
            shape_name=shape,
            dims=dims,
            reo_layout=reo_layout,
        )
        for msg in dev_warnings_bars_outside_concrete(resolved, shape, dims):
            _log.warning(msg)
        for bar in resolved:
            face = str(bar.get("face") or "bottom")
            color = "#d62728" if face == "top" else "#1f77b4"
            _add_cylinder_surface(
                traces,
                0.0,
                float(L_vis),
                float(bar.get("x_mm", 0.0) or 0.0),
                float(bar.get("y_mm", 0.0) or 0.0),
                float(bar.get("dia_mm", 0.0) or 0.0),
                color,
            )
            reo_points.append({
                "x": float(bar.get("x_mm", 0.0) or 0.0),
                "y": float(bar.get("y_mm", 0.0) or 0.0),
                "db": float(bar.get("dia_mm", 0.0) or 0.0),
                "layer": "top" if face == "top" else "bottom",
            })

    # -------------------------
    # Shear cage (optional)
    # -------------------------
    if show_shear and reo_inputs:
        lig_d = float(reo_inputs.get("lig_d", 0.0))
        lig_legs = int(reo_inputs.get("lig_legs", 0))
        s_lig = float(reo_inputs.get("s_lig", 200.0) or 200.0)
        s_eff = max(40.0, s_lig)
        if lig_d > 0 and lig_legs >= 2:
            shear = compute_shear_reo_layout_T_I(
                shape_name=shape,
                dims=dims,
                cover_side=float(reo_inputs.get("cover_side", 0.0)),
                cover_top=float(reo_inputs.get("cover_top", 0.0)),
                cover_bot=float(reo_inputs.get("cover_bot", 0.0)),
                lig_d=lig_d,
                lig_legs=lig_legs,
                reo_points=reo_points,
            )
            outer_cage = _outer_cage_from_reo_points(reo_points, b_env=b_env, D_env=D_env)
            shear_cage_only = shear.get("cage")
            # Match 2D: web-constrained shear cage from compute_shear_reo_layout_T_I, not full
            # longitudinal-bar envelope (which spans bf and draws links through flange void).
            cage = shear_cage_only or outer_cage
            legs = []
            for stirrup in shear.get("stirrups", []):
                legs.extend(stirrup.get("legs", []))

            line_w = max(2.5, abs(lig_d) * 0.42)
            x_positions = _beamwise_stirrup_x_positions(L_vis, s_eff)

            if cage:
                y0 = float(cage["x0"])
                y1 = float(cage["x1"])
                z0 = float(cage["y0"])
                z1 = float(cage["y1"])

                # Longitudinal cage edges
                for y_pos, z_pos in ((y0, z0), (y1, z0), (y1, z1), (y0, z1)):
                    traces.append(
                        go.Scatter3d(
                            x=[0.0, float(L_vis)],
                            y=[y_pos, y_pos],
                            z=[z_pos, z_pos],
                            mode="lines",
                            line=dict(width=line_w, color="black"),
                            hoverinfo="skip",
                            showlegend=False,
                        )
                    )

                # Stirrup frames along beam length
                frame_y = [y0, y1, y1, y0, y0]
                frame_z = [z0, z0, z1, z1, z0]

                for x_pos in x_positions:
                    traces.append(
                        go.Scatter3d(
                            x=[x_pos] * len(frame_y),
                            y=frame_y,
                            z=frame_z,
                            mode="lines",
                            line=dict(width=max(1.5, line_w * 0.85), color="black"),
                            hoverinfo="skip",
                            showlegend=False,
                        )
                    )

            # Internal legs shown at each frame position
            for leg in legs:
                y_pos = float(leg["x1"])
                z0 = float(leg["y1"])
                z1 = float(leg["y2"])
                for x_pos in x_positions:
                    traces.append(
                        go.Scatter3d(
                            x=[x_pos, x_pos],
                            y=[y_pos, y_pos],
                            z=[z0, z1],
                            mode="lines",
                            line=dict(width=max(1.5, line_w * 0.8), color="black"),
                            hoverinfo="skip",
                            showlegend=False,
                        )
                    )

    # Flange transverse detailing (same geometry as 2D make_sectionA_figure); not tied to show_shear.
    if reo_inputs is not None and len(shape) > 0 and shape[0] in ("T", "I"):
        try:
            from .plotly_section import _build_flange_transverse_reo_geometry
            from .shape_utils import normalise_shape_name as _nsk_fl

            _skf = _nsk_fl(shape)
            if _skf in ("T", "I"):
                _rlay = reo_layout if isinstance(reo_layout, dict) else {}
                _resolved_fl = resolve_longitudinal_bars_from_layout(
                    shape_name=shape,
                    dims=dims,
                    reo_layout=_rlay,
                )
                _fl_shapes, _ = _build_flange_transverse_reo_geometry(
                    shape_key=_skf,
                    dims=dims,
                    reo=reo_inputs,
                    resolved_longitudinal_bars=_resolved_fl,
                )
                _tf_mm = float(dims.get("tf", 0.0) or 0.0)
                _d_mm = float(dims.get("D", 0.0) or 0.0)
                _top_sp = max(
                    40.0,
                    float(reo_inputs.get("top_flange_transverse_spacing", 200.0) or 200.0),
                )
                _bot_sp = max(
                    40.0,
                    float(reo_inputs.get("bot_flange_transverse_spacing", 200.0) or 200.0),
                )
                for _fs in _fl_shapes:
                    if str(_fs.get("type")) != "rect":
                        continue
                    xa = float(_fs["x0"])
                    ya = float(_fs["y0"])
                    xb = float(_fs["x1"])
                    yb = float(_fs["y1"])
                    y_lo, y_hi = min(ya, yb), max(ya, yb)
                    if y_hi <= _tf_mm + 1.0:
                        s_sp = _top_sp
                    elif y_lo >= _d_mm - _tf_mm - 1.0:
                        s_sp = _bot_sp
                    else:
                        s_sp = _top_sp
                    lw_ft = max(
                        1.5,
                        float((_fs.get("line") or {}).get("width", 1.2) or 1.2) * 1.25,
                    )
                    fr_y = [xa, xb, xb, xa, xa]
                    fr_z = [ya, ya, yb, yb, ya]
                    for _x_pos in _beamwise_stirrup_x_positions(L_vis, s_sp):
                        traces.append(
                            go.Scatter3d(
                                x=[_x_pos] * 5,
                                y=fr_y,
                                z=fr_z,
                                mode="lines",
                                line=dict(width=lw_ft, color="rgba(35,35,35,0.92)"),
                                hoverinfo="skip",
                                showlegend=False,
                            )
                        )
        except Exception:
            pass

    fig = go.Figure(data=traces)

    # camera: same vibe as main app (scaled by length)
    k = max(2.2, float(L_vis) / 2000.0)

    fig.update_layout(
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        scene_camera=dict(
            eye=dict(x=k, y=k, z=k * 0.6),
            center=dict(x=0, y=0, z=0),
            up=dict(x=0, y=0, z=1),
        ),
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
        ),
    )

    # Nice framing
    fig.update_scenes(
        xaxis=dict(range=[0, float(L_vis)], visible=False),
        yaxis=dict(range=[-0.05 * b_env, 1.05 * b_env], visible=False),
        zaxis=dict(range=[1.05 * D_env, -0.05 * D_env], visible=False),
    )

    return fig
