# curved_beam_diagram.py

import numpy as np

import matplotlib.pyplot as plt

from matplotlib.patches import Polygon



# -----------------------------

# Small helpers

# -----------------------------

def _quad_bezier(P0, P1, P2, n=160):

    t = np.linspace(0.0, 1.0, n)

    return (1 - t)[:, None] ** 2 * P0 + 2 * (1 - t)[:, None] * t[:, None] * P1 + t[:, None] ** 2 * P2



def _bezier_tangent(P0, P1, P2, t):

    # derivative of quadratic bezier

    return 2 * (1 - t) * (P1 - P0) + 2 * t * (P2 - P1)



def _follow_curve_arrow(ax, P0, P1, P2, t0, t1, color, lw=3.5, head=16, z=20):

    # Draw arrow along curve from t0 -> t1 (direction preserved)

    C = _quad_bezier(P0, P1, P2, n=220)

    ts = np.linspace(0, 1, len(C))

    # clip segment

    m = (ts >= min(t0, t1)) & (ts <= max(t0, t1))

    seg = C[m]

    ts_seg = ts[m]

    if len(seg) < 5:

        return



    # ensure direction matches t0 -> t1

    if t1 < t0:

        seg = seg[::-1]

        ts_seg = ts_seg[::-1]



    ax.plot(seg[:, 0], seg[:, 1], color=color, lw=lw, solid_capstyle="round", zorder=z)



    # arrowhead at end (t1 position), aligned with local tangent

    # Find the point closest to t1 (the intended end)

    idx_end = np.argmin(np.abs(ts_seg - t1))

    end = seg[idx_end]

    tan = _bezier_tangent(P0, P1, P2, t1)

    tan = tan / (np.linalg.norm(tan) + 1e-9)

    # Reverse tangent if we're going backwards

    if t1 < t0:

        tan = -tan

    back = end - tan * 0.06  # small back step in data coords

    ax.annotate(

        "",

        xy=(end[0], end[1]),

        xytext=(back[0], back[1]),

        arrowprops=dict(arrowstyle="-|>", lw=lw, color=color, mutation_scale=head),

        zorder=z + 1,

    )



def render_curved_beam_fig(

    L=6.0,

    D=0.8,

    b=0.4,

    dn_uls=0.21,                # in metres (or any consistent unit)

    ts_centroid_y=None,         # y from bottom (same units as D)

    curvature=0.22,             # 0 = straight, higher = more sag

    title=None,

):

    """

    2D 'looks-3D' sagging beam diagram (not rotatable).

    - Compression (red) at TOP, arrows pointing IN to midspan

    - Tension (blue) at BOTTOM, arrows pointing OUT away from midspan

    - Neutral axis dashed (ULS) + centered label

    - Ts centroid marker + label

    """

    # -----------------------------

    # Geometry in a simple 2D frame

    # -----------------------------

    x0, x2 = 0.0, float(L)

    y_mid = 0.0



    # sag amount (positive = sagging downward in drawing)

    sag = float(curvature) * D



    # Top/bottom centerlines (front face)

    y_top = y_mid + D / 2

    y_bot = y_mid - D / 2



    # Quadratic bezier control points for top and bottom edges

    # Midpoint goes DOWN by sag for sagging moment.

    P0_top = np.array([x0, y_top])

    P2_top = np.array([x2, y_top])

    P1_top = np.array([(x0 + x2) / 2, y_top - sag])



    P0_bot = np.array([x0, y_bot])

    P2_bot = np.array([x2, y_bot])

    P1_bot = np.array([(x0 + x2) / 2, y_bot - sag])



    top = _quad_bezier(P0_top, P1_top, P2_top, n=220)

    bot = _quad_bezier(P0_bot, P1_bot, P2_bot, n=220)



    # "depth" offset to fake 3D

    dx3 = 0.18 * D

    dy3 = 0.10 * D



    top_b = top + np.array([dx3, dy3])

    bot_b = bot + np.array([dx3, dy3])



    # Neutral axis (ULS) – offset down from top fibre by dn_uls.

    # Build NA curve by shifting top curve down by dn_uls.

    dn = float(dn_uls)

    na = top.copy()

    na[:, 1] = na[:, 1] - dn



    # Ts centroid location (y from bottom)

    if ts_centroid_y is None:

        ts_centroid_y = 0.12 * D

    ts_y = y_bot + float(ts_centroid_y)



    # Put centroid at midspan with same sag-shape as bottom fibre (approx)

    x_mid = (x0 + x2) / 2

    # evaluate bottom curve y at midspan by picking closest point

    i_mid = np.argmin(np.abs(bot[:, 0] - x_mid))

    y_mid_bot = bot[i_mid, 1]

    # map "distance from bottom" onto local section at midspan

    local_D = top[i_mid, 1] - bot[i_mid, 1]

    ts_point = np.array([x_mid, y_mid_bot + float(ts_centroid_y) / D * local_D])



    # -----------------------------

    # Plot

    # -----------------------------

    fig, ax = plt.subplots(figsize=(10.5, 3.6), dpi=140)



    # Back face outline

    ax.plot(top_b[:, 0], top_b[:, 1], color="black", lw=1.2, alpha=0.35)

    ax.plot(bot_b[:, 0], bot_b[:, 1], color="black", lw=1.2, alpha=0.35)

    ax.plot([top[0, 0], top_b[0, 0]], [top[0, 1], top_b[0, 1]], color="black", lw=1.2, alpha=0.35)

    ax.plot([top[-1, 0], top_b[-1, 0]], [top[-1, 1], top_b[-1, 1]], color="black", lw=1.2, alpha=0.35)

    ax.plot([bot[0, 0], bot_b[0, 0]], [bot[0, 1], bot_b[0, 1]], color="black", lw=1.2, alpha=0.35)

    ax.plot([bot[-1, 0], bot_b[-1, 0]], [bot[-1, 1], bot_b[-1, 1]], color="black", lw=1.2, alpha=0.35)



    # Front face outline

    ax.plot(top[:, 0], top[:, 1], color="black", lw=2.0)

    ax.plot(bot[:, 0], bot[:, 1], color="black", lw=2.0)

    ax.plot([top[0, 0], bot[0, 0]], [top[0, 1], bot[0, 1]], color="black", lw=2.0)

    ax.plot([top[-1, 0], bot[-1, 0]], [top[-1, 1], bot[-1, 1]], color="black", lw=2.0)



    # Fill compression/tension "zones" lightly (optional but matches your language)

    # compression zone (top half-ish)

    comp_poly = np.vstack([top, na[::-1]])

    ax.add_patch(Polygon(comp_poly, closed=True, facecolor=(1.0, 0.0, 0.0, 0.08), edgecolor="none", zorder=0))

    tens_poly = np.vstack([na, bot[::-1]])

    ax.add_patch(Polygon(tens_poly, closed=True, facecolor=(0.0, 0.2, 1.0, 0.06), edgecolor="none", zorder=0))



    # Neutral axis dashed

    ax.plot(na[:, 0], na[:, 1], ls="--", lw=2.0, color="black", alpha=0.6)



    # Labels

    ax.text(x_mid, top[i_mid, 1] + 0.22 * D, "Compression", color="red", ha="center", va="center", fontsize=16, fontweight="bold")

    ax.text(x_mid, bot[i_mid, 1] - 0.28 * D, "Tension", color=(0.0, 0.35, 0.7), ha="center", va="center", fontsize=16, fontweight="bold")



    # -----------------------------

    # Curved arrows MATCHING beam curvature

    # Compression: two arrows pointing IN toward midspan

    # Tension: two arrows pointing OUT away from midspan

    # -----------------------------

    # Compression arrows on/near top fibre: left -> mid, right -> mid

    # Use top curve but slightly offset down so it sits inside compression zone

    top_in = top.copy()

    top_in[:, 1] -= 0.10 * D

    P0c = np.array([x0, y_top - 0.10 * D])

    P2c = np.array([x2, y_top - 0.10 * D])

    P1c = np.array([(x0 + x2) / 2, (y_top - 0.10 * D) - sag])



    # Draw compression line (thick red curve)
    comp_curve = _quad_bezier(P0c, P1c, P2c, n=220)
    ax.plot(comp_curve[:, 0], comp_curve[:, 1], color="red", lw=4.0, zorder=25)
    
    # --- Compression arrows (IN to centroid / midspan) ---
    # Use same pattern as tension arrows but reversed direction
    _follow_curve_arrow(ax, P0c, P1c, P2c, t0=0.10, t1=0.50, color="red", lw=4.0, head=20, z=35)  # left -> mid
    _follow_curve_arrow(ax, P0c, P1c, P2c, t0=0.30, t1=0.50, color="red", lw=4.0, head=20, z=35)  # left quarter -> mid
    _follow_curve_arrow(ax, P0c, P1c, P2c, t0=0.90, t1=0.50, color="red", lw=4.0, head=20, z=35)  # right -> mid
    _follow_curve_arrow(ax, P0c, P1c, P2c, t0=0.70, t1=0.50, color="red", lw=4.0, head=20, z=35)  # right quarter -> mid

    # Tension arrows on/near bottom fibre: mid -> left, mid -> right (OUTWARD)
    P0t = np.array([x0, y_bot + 0.10 * D])
    P2t = np.array([x2, y_bot + 0.10 * D])
    P1t = np.array([(x0 + x2) / 2, (y_bot + 0.10 * D) - sag])

    # Draw tension line (thick blue curve)
    tens_curve = _quad_bezier(P0t, P1t, P2t, n=220)
    ax.plot(tens_curve[:, 0], tens_curve[:, 1], color=(0.0, 0.35, 0.7), lw=4.0, zorder=25)
    
    # --- Tension arrows (OUT away from centroid / midspan) ---
    _follow_curve_arrow(ax, P0t, P1t, P2t, t0=0.50, t1=0.10, color=(0.0, 0.35, 0.7), lw=4.0, head=20, z=35)  # mid -> left
    _follow_curve_arrow(ax, P0t, P1t, P2t, t0=0.50, t1=0.30, color=(0.0, 0.35, 0.7), lw=4.0, head=20, z=35)  # mid -> left quarter
    _follow_curve_arrow(ax, P0t, P1t, P2t, t0=0.50, t1=0.90, color=(0.0, 0.35, 0.7), lw=4.0, head=20, z=35)  # mid -> right
    _follow_curve_arrow(ax, P0t, P1t, P2t, t0=0.50, t1=0.70, color=(0.0, 0.35, 0.7), lw=4.0, head=20, z=35)  # mid -> right quarter



    # Cosmetics

    if title:

        ax.set_title(title, fontsize=18, loc="left")

    ax.set_aspect("equal", adjustable="box")

    ax.axis("off")

    ax.set_xlim(-0.25 * D, L + dx3 + 0.25 * D)

    ax.set_ylim(y_bot - 0.55 * D, y_top + 0.55 * D)



    return fig

