from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .shear_layout import compute_shear_reo_layout_T_I


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

    # -------------------------
    # Bars (extruded lines)
    # reo_layout format: {"top":[{"x":[...],"y":[...],"db":..}, ...], "bottom":[...]}
    # -------------------------
    traces = []
    traces.extend(meshes)

    def add_bar_lines(layer_list, color: str):
        if not layer_list:
            return
        for layer in layer_list:
            xs = layer.get("x") or []
            y_list = layer.get("y") or []
            db = float(layer.get("db") or 0.0)

            # we store y as a list in some layouts; accept scalar too
            if isinstance(y_list, (list, tuple)) and len(y_list) > 0:
                z_pos = float(y_list[0])
            else:
                z_pos = float(y_list)

            line_w = max(2.0, abs(db) * 0.4)
            for y_pos in xs:
                traces.append(
                    go.Scatter3d(
                        x=[0.0, float(L_vis)],
                        y=[float(y_pos), float(y_pos)],
                        z=[z_pos, z_pos],
                        mode="lines",
                        line=dict(width=line_w, color=color),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

    if reo_layout:
        # Be robust to both legacy ("top"/"bottom") and newer grouped keys.
        bottom_layers = []
        top_layers = []

        def _as_list(x):
            if not x:
                return []
            return x if isinstance(x, list) else [x]

        bottom_layers += _as_list(reo_layout.get("bottom"))
        bottom_layers += _as_list(reo_layout.get("bottom_flange"))
        bottom_layers += _as_list(reo_layout.get("bottom_web"))
        bottom_layers += _as_list(reo_layout.get("bottom_left"))
        bottom_layers += _as_list(reo_layout.get("bottom_right"))

        top_layers += _as_list(reo_layout.get("top"))
        top_layers += _as_list(reo_layout.get("top_flange"))
        top_layers += _as_list(reo_layout.get("top_web"))
        top_layers += _as_list(reo_layout.get("top_left"))
        top_layers += _as_list(reo_layout.get("top_right"))

        add_bar_lines(bottom_layers, "blue")
        add_bar_lines(top_layers, "red")

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
            )
            cage = shear.get("cage")
            legs = []
            for stirrup in shear.get("stirrups", []):
                legs.extend(stirrup.get("legs", []))

            line_w = max(2.0, abs(lig_d) * 0.35)

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
                x_positions = [0.0]
                x = s_eff
                while x < float(L_vis) - 1e-6:
                    x_positions.append(float(x))
                    x += s_eff
                if float(L_vis) not in x_positions:
                    x_positions.append(float(L_vis))

                # Safety cap
                MAX_FRAMES = 250
                if len(x_positions) > MAX_FRAMES:
                    step = max(1, len(x_positions) // MAX_FRAMES)
                    x_positions = x_positions[::step]
                    if x_positions[-1] != float(L_vis):
                        x_positions.append(float(L_vis))

                for x_pos in x_positions:
                    traces.append(
                        go.Scatter3d(
                            x=[x_pos] * len(frame_y),
                            y=frame_y,
                            z=frame_z,
                            mode="lines",
                            line=dict(width=max(1.5, line_w * 0.8), color="black"),
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
