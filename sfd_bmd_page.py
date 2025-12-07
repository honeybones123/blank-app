# sfd_bmd_page.py
# ==========================================
# SFD & BMD teaching page for beam app
# ==========================================

import math
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st

from state_and_helpers import get_sync_callbacks, get_param, update_results
from widgets_helpers import (
    apply_global_widget_css,
    apply_calcbox_css,
    number_row,
    calcbox,
)


# ---------------------------------------------------
# Helper: get span from Inputs page
# ---------------------------------------------------
def _span_from_inputs(fallback: float = 6.0) -> float:
    """Read span L from Inputs page; safe fallback if missing."""
    try:
        L_val = get_param("L")
    except TypeError:
        L_val = None

    try:
        if L_val is None:
            return float(fallback)
        L_val = float(L_val)
        if math.isnan(L_val):
            return float(fallback)
        # L from Inputs is in mm, convert to m
        return L_val / 1000.0
    except Exception:
        return float(fallback)


# ---------------------------------------------------
# Helper: draw support symbols
# ---------------------------------------------------
def draw_support(ax, x_pos, kind="pinned", size=0.18):
    """
    Draws a support symbol at x_pos on the x-axis.
    kind: "pinned", "roller", "fixed"
    Designed so the triangle POINTS UP to the beam (beam is along y = 0).
    """
    y_beam = 0.0
    apex_y = y_beam - 0.01          # just under the beam line
    base_y = apex_y - size          # bottom of triangle

    if kind in ("pinned", "roller"):
        half_base = size * 0.8

        # upright triangle (point up touching the beam underside)
        ax.plot(
            [x_pos - half_base, x_pos, x_pos + half_base, x_pos - half_base],
            [base_y, apex_y, base_y, base_y],
            "k", linewidth=1.5
        )

        # hinge dot right at the contact
        ax.plot(x_pos, apex_y, "ko", markersize=3)

        if kind == "roller":
            # roller circle below the triangle
            roller_y = base_y - size * 0.4
            ax.plot(x_pos, roller_y, "ko", markersize=4)

    elif kind == "fixed":
        # thick vertical wall at x_pos
        wall_height = size * 3
        ax.plot(
            [x_pos, x_pos],
            [y_beam - wall_height, y_beam + wall_height],
            "k",
            linewidth=4
        )
        # hatching into wall (left side)
        n_hatch = 5
        for i in range(n_hatch):
            yy = y_beam - wall_height + i * (2 * wall_height / max(n_hatch - 1, 1))
            ax.plot(
                [x_pos - size * 0.7, x_pos],
                [yy - size * 0.4, yy],
                "k",
                linewidth=1
            )


# ---------------------------------------------------
# Helper: plot load diagram
# ---------------------------------------------------
def plot_load_diagram_plotly(case, L, params):
    """
    Plotly version of the qualitative load diagram.
    Much simpler visually, but interactive.
    """
    fig = go.Figure()

    # Beam line
    fig.add_trace(
        go.Scatter(
            x=[0, L],
            y=[0, 0],
            mode="lines",
            line=dict(width=4),
            showlegend=False,
        )
    )

    # --- Supports ---
    if case.startswith("Simple beam"):
        # pinned at 0 and L – use triangle marker just below beam
        fig.add_trace(
            go.Scatter(
                x=[0, L],
                y=[-0.1, -0.1],
                mode="markers",
                marker=dict(symbol="triangle-up", size=14),
                showlegend=False,
            )
        )
    elif case.startswith("Cantilever"):
        # fixed at left – represent as thick vertical line
        fig.add_shape(
            type="line",
            x0=0,
            x1=0,
            y0=-0.4,
            y1=0.4,
            line=dict(width=8),
        )
    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = params.get("L_main", L)
        fig.add_trace(
            go.Scatter(
                x=[0, L_main],
                y=[-0.1, -0.1],
                mode="markers",
                marker=dict(symbol="triangle-up", size=14),
                showlegend=False,
            )
        )

    # --- Loads ---
    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        xs = [0, L]
        ys = [0.4, 0.4]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(width=0),
                fill="tozeroy",
                opacity=0.3,
                showlegend=False,
            )
        )
        # arrows
        for xi in np.linspace(0.1 * L, 0.9 * L, 7):
            fig.add_annotation(
                x=xi,
                y=0.45,
                ax=xi,
                ay=0.25,
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
            )
        fig.add_annotation(
            x=L / 2,
            y=0.55,
            text=f"w = {w:.2f} kN/m",
            showarrow=False,
        )

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        a = L / 2
        fig.add_annotation(
            x=a,
            y=0.45,
            ax=a,
            ay=0.1,
            showarrow=True,
            arrowhead=2,
        )
        fig.add_annotation(
            x=a,
            y=0.55,
            text=f"P = {P:.2f} kN",
            showarrow=False,
        )

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a = params.get("a", L / 3)
        a = max(0.0, min(a, L))
        fig.add_annotation(
            x=a,
            y=0.45,
            ax=a,
            ay=0.35,
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
        )
        fig.add_annotation(
            x=a,
            y=0.55,
            text=f"P = {P:.2f} kN",
            showarrow=False,
        )

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        fig.add_annotation(
            x=L,
            y=0.45,
            ax=L,
            ay=0.35,
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
        )
        fig.add_annotation(
            x=L,
            y=0.55,
            text=f"P = {P:.2f} kN",
            showarrow=False,
        )

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a = params.get("a_cant", L / 2)
        a = max(0.0, min(a, L))
        fig.add_annotation(
            x=a,
            y=0.45,
            ax=a,
            ay=0.35,
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
        )
        fig.add_annotation(
            x=a,
            y=0.55,
            text=f"P = {P:.2f} kN",
            showarrow=False,
        )

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        xs = [0, L]
        ys = [0.4, 0.4]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(width=0),
                fill="tozeroy",
                opacity=0.3,
                showlegend=False,
            )
        )
        # arrows
        for xi in np.linspace(0.1 * L, 0.9 * L, 7):
            fig.add_annotation(
                x=xi,
                y=0.45,
                ax=xi,
                ay=0.25,
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
            )
        fig.add_annotation(
            x=L / 2,
            y=0.55,
            text=f"w = {w:.2f} kN/m",
            showarrow=False,
        )

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params["w"]
        a = params["a_udl"]
        a = max(0.0, min(a, L))
        xs = [0, a]
        ys = [0.4, 0.4]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(width=0),
                fill="tozeroy",
                opacity=0.3,
                showlegend=False,
            )
        )
        # arrows
        for xi in np.linspace(0.1 * a, 0.9 * a, 5):
            fig.add_annotation(
                x=xi,
                y=0.45,
                ax=xi,
                ay=0.25,
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
            )
        fig.add_annotation(
            x=a / 2,
            y=0.55,
            text=f"w = {w:.2f} kN/m",
            showarrow=False,
        )

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params["P"]
        L_main = params.get("L_main", L)
        a_over = params.get("a_overhang", 0.0)
        L_total = L_main + a_over
        fig.add_annotation(
            x=L_total,
            y=0.45,
            ax=L_total,
            ay=0.35,
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
        )
        fig.add_annotation(
            x=L_total,
            y=0.55,
            text=f"P = {P:.2f} kN",
            showarrow=False,
        )

    fig.update_xaxes(range=[-0.2, L + 0.2], visible=False)
    fig.update_yaxes(range=[-0.7, 0.9], visible=False)

    fig.update_layout(
        height=220,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


# ---------------------------------------------------
# Helper: plot SFD and BMD (Plotly version)
# ---------------------------------------------------
def plot_sfd_bmd_plotly(x, V, M):
    """Return Plotly figures for SFD and BMD."""

    # --- SFD ---
    fig_sfd = go.Figure()
    fig_sfd.add_trace(
        go.Scatter(
            x=x,
            y=V,
            mode="lines",
            name="V(x)",
        )
    )
    fig_sfd.add_hline(y=0, line_width=1, line_color="black")
    fig_sfd.update_layout(
        title="Shear Force Diagram (SFD)",
        xaxis_title="x (m)",
        yaxis_title="V (kN)",
        margin=dict(l=40, r=20, t=40, b=40),
        height=300,
    )

    # --- BMD ---
    fig_bmd = go.Figure()
    fig_bmd.add_trace(
        go.Scatter(
            x=x,
            y=M,
            mode="lines",
            name="M(x)",
        )
    )
    fig_bmd.add_hline(y=0, line_width=1, line_color="black")
    fig_bmd.update_layout(
        title="Bending Moment Diagram (BMD)",
        xaxis_title="x (m)",
        yaxis_title="M (kNm)",
        margin=dict(l=40, r=20, t=40, b=40),
        height=300,
    )

    return fig_sfd, fig_bmd


# ---------------------------------------------------
# Helper: derivation text inside expander
# ---------------------------------------------------
def render_derivation(case, L, params, results):
    """
    Writes full equilibrium derivation for each case.
    Uses st.latex and st.markdown.
    """
    with st.expander("Show full equilibrium derivation (reactions, V(x), M(x))"):
        st.markdown("### Step 1 – Support conditions")

        if case.startswith("Simple beam"):
            st.markdown("- Left support: **pinned**  \n- Right support: **pinned**")
        elif case.startswith("Cantilever"):
            st.markdown("- Left support: **fixed**  \n- Right end: **free**")
        elif case == "Overhanging beam – right overhang with point load at free end":
            st.markdown(
                "- Left support A: **pinned**  \n"
                "- Right support B: **pinned** (internal)  \n"
                "- Right overhang end: **free**"
            )

        st.markdown("---")
        st.markdown("### Step 2 – Reaction forces")

        if case == "Simple beam – UDL over entire span":
            w = params["w"]
            R = results.get("R", w * L / 2.0)
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - wL \cdot \frac{L}{2} = 0")
            st.latex(r"R_2 = \frac{wL}{2}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - wL = 0")
            st.latex(r"R_1 = \frac{wL}{2}")
            st.markdown(f"Numerically, R₁ = R₂ = `{R:.3g}` kN")

        elif case == "Simple beam – partial UDL from left (length a)":
            w = params["w"]
            a = params["a_udl"]
            a = max(0.0, min(a, L))
            R1 = results.get("R1", 0.0)
            R2 = results.get("R2", 0.0)
            st.latex(r"w \text{ over } 0 \le x \le a,\quad 0 \le a \le L")
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - w a \cdot \frac{a}{2} = 0")
            st.latex(r"R_2 = \dfrac{w a^2}{2L}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - w a = 0")
            st.latex(r"R_1 = w a - \dfrac{w a^2}{2L}")
            st.markdown(
                f"With L = `{L:.3g}` m, a = `{a:.3g}` m, w = `{w:.3g}` kN/m:"
            )
            st.markdown(f"- R₁ = `{R1:.3g}` kN  \n- R₂ = `{R2:.3g}` kN")

        elif case == "Simple beam – point load at centre":
            P = params["P"]
            R1 = results["R1"]
            st.latex(r"a = \frac{L}{2}")
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - P \cdot \frac{L}{2} = 0")
            st.latex(r"R_2 = \frac{P}{2}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - P = 0")
            st.latex(r"R_1 = \frac{P}{2}")
            st.markdown(f"With P = `{P:.3g}` kN: R₁ = R₂ = `{R1:.3g}` kN")

        elif case == "Simple beam – point load at distance a from left":
            P = params["P"]
            a = float(params["a"])
            b = L - a
            R1 = results.get("R1", 0.0)
            R2 = results.get("R2", 0.0)
            st.latex(r"a = a,\quad b = L-a")
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - P a = 0")
            st.latex(r"R_2 = \dfrac{Pa}{L}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - P = 0")
            st.latex(r"R_1 = \dfrac{Pb}{L}")
            st.markdown(
                f"With L = `{L:.3g}` m, a = `{a:.3g}` m, b = `{b:.3g}` m, P = `{P:.3g}` kN:"
            )
            st.markdown(f"- R₁ = `{R1:.3g}` kN  \n- R₂ = `{R2:.3g}` kN")

        elif case == "Cantilever – point load at free end":
            P = params["P"]
            st.latex(r"\Sigma V = 0: \quad V_{\text{fixed}} - P = 0")
            st.latex(r"V_{\text{fixed}} = P")
            st.latex(r"\Sigma M_{\text{fixed}} = 0: \quad M_{\text{fixed}} - P L = 0")
            st.latex(r"M_{\text{fixed}} = P L")
            st.markdown(
                f"At the fixed support, shear = `{P:.3g}` kN (up), "
                f"hogging moment = `{P*L:.3g}` kNm."
            )

        elif case == "Cantilever – point load at distance a from fixed end":
            P = params["P"]
            a = params["a_cant"]
            a = max(0.0, min(a, L))
            st.latex(r"\Sigma V = 0: \quad V_{\text{fixed}} - P = 0")
            st.latex(r"V_{\text{fixed}} = P")
            st.latex(r"\Sigma M_{\text{fixed}} = 0: \quad M_{\text{fixed}} - P a = 0")
            st.latex(r"M_{\text{fixed}} = P a")
            st.markdown(
                f"At the fixed support, shear = `{P:.3g}` kN (up), "
                f"hogging moment = `{P*a:.3g}` kNm."
            )

        elif case == "Cantilever – UDL over entire span":
            w = params["w"]
            st.latex(r"\Sigma V = 0: \quad V_{\text{fixed}} - wL = 0")
            st.latex(r"V_{\text{fixed}} = wL")
            st.latex(
                r"\Sigma M_{\text{fixed}} = 0: \quad "
                r"M_{\text{fixed}} - wL \cdot \frac{L}{2} = 0"
            )
            st.latex(r"M_{\text{fixed}} = \frac{wL^2}{2}")
            st.markdown(
                f"At the fixed support, shear = `{w*L:.3g}` kN (up), "
                f"hogging moment = `{0.5*w*L**2:.3g}` kNm."
            )

        elif case == "Overhanging beam – right overhang with point load at free end":
            P = params["P"]
            L_main = params["L_main"]
            a_over = params["a_overhang"]
            RA = results.get("RA", 0.0)
            RB = results.get("RB", 0.0)
            st.latex(r"L = \text{distance between supports}, \quad a = \text{overhang}")
            st.latex(r"\Sigma M_A = 0: \quad R_B L - P(L+a) = 0")
            st.latex(r"R_B = \dfrac{P(L+a)}{L}")
            st.latex(r"\Sigma V = 0: \quad R_A + R_B - P = 0")
            st.latex(r"R_A = P - R_B = -\dfrac{Pa}{L}")
            st.markdown(
                f"With L = `{L_main:.3g}` m, a = `{a_over:.3g}` m, P = `{P:.3g}` kN:"
            )
            st.markdown(f"- R_A = `{RA:.3g}` kN (down)  \n- R_B = `{RB:.3g}` kN (up)")

        st.markdown("---")
        st.markdown("### Step 3 – Shear function \(V(x)\)")

        if case == "Simple beam – UDL over entire span":
            st.latex(
                r"V(x) = R_1 - wx = \frac{wL}{2} - wx,\quad 0 \le x \le L"
            )

        elif case == "Simple beam – partial UDL from left (length a)":
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 - w x & 0 \le x \le a \\"
                r"R_1 - w a & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at centre":
            st.latex(
                r"a = \frac{L}{2}"
            )
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 & 0 \le x < a \\"
                r"R_1 - P & a < x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at distance a from left":
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 & 0 \le x < a \\"
                r"R_1 - P & a < x \le L"
                r"\end{cases}"
            )

        elif case == "Cantilever – point load at free end":
            st.latex(
                r"V(x) = -P,\quad 0 \le x \le L"
            )

        elif case == "Cantilever – point load at distance a from fixed end":
            st.latex(
                r"V(x) = \begin{cases}"
                r"-P & 0 \le x \le a \\"
                r"0 & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Cantilever – UDL over entire span":
            st.latex(
                r"V(x) = -w(L - x),\quad 0 \le x \le L"
            )

        elif case == "Overhanging beam – right overhang with point load at free end":
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_A & 0 \le x < L \\"
                r"R_A + R_B & L < x \le L+a"
                r"\end{cases}"
            )

        st.markdown("---")
        st.markdown("### Step 4 – Moment function \(M(x)\)")

        if case == "Simple beam – UDL over entire span":
            st.latex(
                r"M(x) = R_1 x - \frac{w x^2}{2},\quad 0 \le x \le L"
            )
            st.latex(
                r"M_{\max} = \frac{wL^2}{8} \text{ at } x = \frac{L}{2}"
            )

        elif case == "Simple beam – partial UDL from left (length a)":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x - \dfrac{w x^2}{2} & 0 \le x \le a \\[6pt]"
                r"R_1 x - w a\left(x - \dfrac{a}{2}\right) & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at centre":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x & 0 \le x \le a \\"
                r"R_1 x - P(x-a) & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M_{\max} = \frac{PL}{4} \text{ at } x = \frac{L}{2}"
            )

        elif case == "Simple beam – point load at distance a from left":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x & 0 \le x \le a \\"
                r"R_1 x - P(x-a) & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M_{\max} = R_1 a = \dfrac{Pab}{L} \text{ at } x = a"
            )

        elif case == "Cantilever – point load at free end":
            st.latex(
                r"M(x) = -P(L-x),\quad 0 \le x \le L"
            )
            st.latex(r"M_{\max} = PL \text{ (hogging at fixed end)}")

        elif case == "Cantilever – point load at distance a from fixed end":
            st.latex(
                r"M(x) = \begin{cases}"
                r"-P(a-x) & 0 \le x \le a \\"
                r"0 & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(r"M_{\max} = P a \text{ at the fixed end}")

        elif case == "Cantilever – UDL over entire span":
            st.latex(
                r"M(x) = -\frac{w}{2}(L-x)^2,\quad 0 \le x \le L"
            )
            st.latex(r"M_{\max} = \frac{wL^2}{2} \text{ (hogging at fixed end)}")

        elif case == "Overhanging beam – right overhang with point load at free end":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_A x & 0 \le x \le L \\"
                r"R_A x + R_B(x-L) & L \le x \le L+a"
                r"\end{cases}"
            )
            st.latex(
                r"M_B = R_A L = -Pa \text{ (hogging at support B)}"
            )


# ---------------------------------------------------
# MAIN PAGE RENDER FUNCTION
# ---------------------------------------------------
def render_sfd_bmd_page():
    """
    Standalone SFD/BMD teaching page in the beam app.

    - Same visual style as other pages (title, blurb, summary placeholder)
    - No sidebar, no set_page_config
    - Publishes span + |M|max + |V|max to results:
          sfd_case
          sfd_span_L_m
          sfd_Mmax_abs_kNm
          sfd_Vmax_abs_kN
    """

    apply_global_widget_css()
    apply_calcbox_css()
    sync_callbacks = get_sync_callbacks()

    st.title("Shear & Moment Diagrams (Design / Teaching)")

    summary_placeholder = st.empty()

    # =========================================================
    # BEAM LOADING CONDITION (single source of truth)
    # =========================================================
    st.markdown("### Beam loading condition (single source of truth)")

    load_case = st.selectbox(
        "Loading condition",
        [
            "Simple beam – UDL over entire span",
            "Simple beam – partial UDL from left (length a)",
            "Simple beam – point load at centre",
            "Simple beam – point load at distance a from left",
            "Cantilever – point load at free end",
            "Cantilever – point load at distance a from fixed end",
            "Cantilever – UDL over entire span",
            "Overhanging beam – right overhang with point load at free end",
        ],
        key="load_case",
    )

    # -------- span from Inputs page --------
    L = _span_from_inputs(10.0)  # fallback 10 m if Inputs hasn't run yet

    st.markdown(
        f"**Span for SFD/BMD:** `L = {L:.3g} m` "
        "(read from **Inputs** page; not editable here)."
    )

    # Conditional loads based on load case type
    params: dict = {}
    results_local: dict = {}
    a = None

    # UDL-type cases
    if load_case in [
        "Simple beam – UDL over entire span",
        "Simple beam – partial UDL from left (length a)",
        "Cantilever – UDL over entire span",
    ]:
        g = st.number_input(
            "Dead UDL g (kN/m)",
            min_value=0.0,
            value=8.0,
            step=0.5,
            key="load_g_udl",
            on_change=sync_callbacks.get("load_g_udl", lambda: None),
        )
        q = st.number_input(
            "Live UDL q (kN/m)",
            min_value=0.0,
            value=4.0,
            step=0.5,
            key="load_q_udl",
            on_change=sync_callbacks.get("load_q_udl", lambda: None),
        )
        psi_s = st.number_input(
            "Sustained factor ψ_s",
            min_value=0.0,
            value=0.4,
            step=0.05,
            key="load_psi_udl",
            on_change=sync_callbacks.get("load_psi_udl", lambda: None),
        )

        # Read synced values
        g_shared = get_param("g_udl_kNm_per_m", g)
        q_shared = get_param("q_udl_kNm_per_m", q)
        psi_shared = get_param("psi_udl", psi_s)

        # SLS + ULS equivalents
        w_sls = g_shared + psi_shared * q_shared  # for deflection and SLS diagrams
        gamma_g = 1.2
        gamma_q = 1.5
        w_uls = gamma_g * g_shared + gamma_q * q_shared  # for ULS design M*, V*

        # Store for SFD/BMD computation
        params["w"] = w_sls  # Use SLS for diagrams

        # Optional: partial UDL length
        if load_case == "Simple beam – partial UDL from left (length a)":
            params["a_udl"] = st.number_input(
                "UDL length a from left (m)",
                min_value=0.0,
                value=L / 2,
                step=0.1,
                key="sfd_a_udl",
            )

        update_results(
            span_L_m=float(L),
            g_udl_kNm_per_m=float(g_shared),
            q_udl_kNm_per_m=float(q_shared),
            psi_udl=float(psi_shared),
            w_sls_kNm_per_m=float(w_sls),
            w_uls_kNm_per_m=float(w_uls),
        )

    # Point-load cases
    elif load_case in [
        "Simple beam – point load at centre",
        "Simple beam – point load at distance a from left",
        "Cantilever – point load at free end",
        "Cantilever – point load at distance a from fixed end",
        "Overhanging beam – right overhang with point load at free end",
    ]:
        G_point = st.number_input(
            "Dead point load G (kN)",
            min_value=0.0,
            value=50.0,
            step=5.0,
            key="load_G_point",
            on_change=sync_callbacks.get("load_G_point", lambda: None),
        )
        Q_point = st.number_input(
            "Live point load Q (kN)",
            min_value=0.0,
            value=30.0,
            step=5.0,
            key="load_Q_point",
            on_change=sync_callbacks.get("load_Q_point", lambda: None),
        )
        psi_s = st.number_input(
            "Sustained factor ψ_s for point load",
            min_value=0.0,
            value=0.4,
            step=0.05,
            key="load_psi_point",
            on_change=sync_callbacks.get("load_psi_point", lambda: None),
        )

        # Read synced values
        G_shared = get_param("G_point_kN", G_point)
        Q_shared = get_param("Q_point_kN", Q_point)
        psi_shared = get_param("psi_point", psi_s)

        # SLS + ULS equivalents
        P_sls = G_shared + psi_shared * Q_shared
        gamma_g = 1.2
        gamma_q = 1.5
        P_uls = gamma_g * G_shared + gamma_q * Q_shared

        # Store for SFD/BMD computation
        params["P"] = P_sls  # Use SLS for diagrams

        # Optional eccentricity
        if load_case == "Simple beam – point load at distance a from left":
            a = st.number_input(
                "Distance a from left support (m)",
                min_value=0.0,
                value=L / 3,
                step=0.1,
                key="load_a_point",
                on_change=sync_callbacks.get("load_a_point", lambda: None),
            )
            a_shared = get_param("a_m", a)
            params["a"] = a_shared
        elif load_case == "Cantilever – point load at distance a from fixed end":
            a = st.number_input(
                "Distance a from fixed end (m)",
                min_value=0.0,
                value=L / 2,
                step=0.1,
                key="sfd_a_cant",
            )
            params["a_cant"] = a
        elif load_case == "Overhanging beam – right overhang with point load at free end":
            L_main = L  # span between supports from Inputs
            a_over = st.number_input(
                "Overhang length a (m)",
                min_value=0.0,
                value=2.0,
                step=0.5,
                key="sfd_a_overhang",
            )
            params["L_main"] = L_main
            params["a_overhang"] = a_over

        update_results(
            span_L_m=float(L),
            G_point_kN=float(G_shared),
            Q_point_kN=float(Q_shared),
            psi_point=float(psi_shared),
            P_sls_kN=float(P_sls),
            P_uls_kN=float(P_uls),
            a_m=float(a) if a is not None else None,
        )

    st.markdown("---")

    st.markdown(
        """
This page is a **teaching module** for classic statically determinate beams.
It generates the **load diagram**, **shear force diagram (SFD)** and
**bending moment diagram (BMD)** with full equilibrium derivation.

**Sign convention (for diagrams):**

- Shear \(V(x)\): **upward positive**

- Bending moment \(M(x)\): **sagging positive**  

  (cantilever hogging appears negative)
"""
    )

    # Use load_case for computation (rename for compatibility with existing code)
    case = load_case
    
    # Determine beam_length for plotting
    if case == "Overhanging beam – right overhang with point load at free end":
        beam_length = params.get("L_main", L) + params.get("a_overhang", 0.0)
    else:
        beam_length = L

    # Local results dict for reactions (used in derivation)
    results_local: dict = {}

    # ---------------------------------------------------
    # Compute V(x) and M(x) (same logic as your original)
    # ---------------------------------------------------
    x = None
    V = None
    M = None
    beam_length = L

    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        x = np.linspace(0, L, 400)
        R = w * L / 2.0
        V = R - w * x
        M = R * x - 0.5 * w * x**2
        results_local["R"] = R

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params["w"]
        a = params["a_udl"]
        a = max(0.0, min(a, L))
        x = np.linspace(0, L, 400)
        R2 = w * a**2 / (2 * L)
        R1 = w * a - R2
        V = np.zeros_like(x)
        M = np.zeros_like(x)
        for i, xi in enumerate(x):
            if xi <= a:
                V[i] = R1 - w * xi
                M[i] = R1 * xi - 0.5 * w * xi**2
            else:
                V[i] = R1 - w * a
                M[i] = R1 * xi - w * a * (xi - a / 2)
        results_local["R1"] = R1
        results_local["R2"] = R2

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        a = L / 2.0
        R1 = R2 = P / 2.0
        x = np.linspace(0, L, 400)
        V = np.zeros_like(x)
        M = np.zeros_like(x)
        for i, xi in enumerate(x):
            if xi < a:
                V[i] = R1
                M[i] = R1 * xi
            else:
                V[i] = R1 - P
                M[i] = R1 * xi - P * (xi - a)
        results_local["R1"] = R1
        results_local["R2"] = R2

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a = float(params.get("a", L / 3))  # Default to L/3 if not set
        a = max(0.0, min(a, L))
        b = L - a
        R1 = P * b / L
        R2 = P * a / L
        x = np.linspace(0, L, 400)
        V = np.zeros_like(x)
        M = np.zeros_like(x)
        for i, xi in enumerate(x):
            if xi < a:
                V[i] = R1
                M[i] = R1 * xi
            else:
                V[i] = R1 - P
                M[i] = R1 * xi - P * (xi - a)
        results_local["R1"] = R1
        results_local["R2"] = R2

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        x = np.linspace(0, L, 400)
        V = -P * np.ones_like(x)
        M = -P * (L - x)

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a = params["a_cant"]
        a = max(0.0, min(a, L))
        x = np.linspace(0, L, 400)
        V = np.zeros_like(x)
        M = np.zeros_like(x)
        for i, xi in enumerate(x):
            if xi <= a:
                V[i] = -P
                M[i] = -P * (a - xi)
            else:
                V[i] = 0.0
                M[i] = 0.0

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        x = np.linspace(0, L, 400)
        V = -w * (L - x)
        M = -0.5 * w * (L - x) ** 2

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params["P"]
        L_main = params["L_main"]
        a_over = params["a_overhang"]
        L_total = L_main + a_over
        RA = -P * a_over / L_main
        RB = P * (L_main + a_over) / L_main
        x = np.linspace(0, L_total, 400)
        V = np.zeros_like(x)
        M = np.zeros_like(x)
        for i, xi in enumerate(x):
            if xi <= L_main:
                V[i] = RA
                M[i] = RA * xi
            else:
                V[i] = RA + RB
                M[i] = RA * xi + RB * (xi - L_main)
        beam_length = L_total
        results_local["RA"] = RA
        results_local["RB"] = RB

    # Global maxima (absolute)
    M_max_abs = float(np.max(np.abs(M))) if M is not None else 0.0
    V_max_abs = float(np.max(np.abs(V))) if V is not None else 0.0

    # ---------------------------------------------------
    # Load diagram – directly under inputs
    # ---------------------------------------------------
    st.markdown("---")
    st.subheader("Load diagram (SLS loads)")

    fig_load = plot_load_diagram_plotly(case, beam_length, params)
    st.plotly_chart(fig_load, use_container_width=True)

    # ---------------------------------------------------
    # Full equilibrium derivation – 4 blue calc boxes
    # ---------------------------------------------------
    st.subheader("Equilibrium derivation (SLS)")

    # STEP 1 – support conditions
    step1_md = ""

    if case.startswith("Simple beam"):
        step1_md = """
**Step 1 – Support conditions**

- Left support: **pinned**  

- Right support: **pinned**  

For a simply supported beam of span \\(L\\), the reactions act vertically at each support.
"""
    elif case.startswith("Cantilever"):
        step1_md = """
**Step 1 – Support conditions**

- Left support: **fixed**  

- Right end: **free**  

A cantilever has a fixed end moment and shear at the support and zero reactions at the free end.
"""
    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = params.get("L_main", L)
        step1_md = f"""
**Step 1 – Support conditions**

- Support A (left): **pinned**  

- Support B (internal): **pinned** at distance \\(L = {L_main:.3g}\\,\\text{{m}}\\) from A  

- Right overhang end: **free** at \\(x = L + a\\)
"""

    calcbox(step1_md)

    # STEP 2 – reactions (case-by-case)
    step2_md = ""

    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        R = results_local.get("R", w * L / 2.0)
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

For a UDL \\(w\\) over \\(0 \\le x \\le L\\):  

\\[
\\sum M_A = 0: \\quad R_2 L - wL \\cdot \\frac{{L}}{{2}} = 0
\\Rightarrow R_2 = \\frac{{wL}}{{2}}
\\]

\\[
\\sum V = 0: \\quad R_1 + R_2 - wL = 0
\\Rightarrow R_1 = \\frac{{wL}}{{2}}
\\]

For the selected data:

- \\(w = {w:.3g}\\,\\text{{kN/m}}\\)  

- \\(L = {L:.3g}\\,\\text{{m}}\\)  

so numerically \\(R_1 = R_2 = \\dfrac{{wL}}{{2}} = {R:.3g}\\,\\text{{kN}}\\).
"""

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        R1 = results_local.get("R1", P / 2.0)
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

Point load \\(P\\) at midspan \\(a = L/2\\):  

\\[
\\sum M_A = 0: \\quad R_2 L - P \\cdot \\frac{{L}}{{2}} = 0
\\Rightarrow R_2 = \\frac{{P}}{{2}}
\\]

\\[
\\sum V = 0: \\quad R_1 + R_2 - P = 0
\\Rightarrow R_1 = \\frac{{P}}{{2}}
\\]

For the selected data:

- \\(P = {P:.3g}\\,\\text{{kN}}\\)  

- \\(L = {L:.3g}\\,\\text{{m}}\\)

so numerically \\(R_1 = R_2 = {R1:.3g}\\,\\text{{kN}}\\).
"""

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a_val = params["a"]
        R1 = results_local.get("R1", 0.0)
        R2 = results_local.get("R2", 0.0)
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

Point load \\(P\\) at distance \\(a\\) from left support:  

\\[
\\sum M_A = 0: \\quad R_2 L - P a = 0
\\Rightarrow R_2 = \\frac{{Pa}}{{L}}
\\]

\\[
\\sum V = 0: \\quad R_1 + R_2 - P = 0
\\Rightarrow R_1 = \\frac{{Pb}}{{L}} = \\frac{{P(L-a)}}{{L}}
\\]

For the selected data:

- \\(P = {P:.3g}\\,\\text{{kN}}\\)  

- \\(L = {L:.3g}\\,\\text{{m}}\\)  

- \\(a = {a_val:.3g}\\,\\text{{m}}\\)

so numerically \\(R_1 = {R1:.3g}\\,\\text{{kN}}\\), \\(R_2 = {R2:.3g}\\,\\text{{kN}}\\).
"""

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params["w"]
        a_udl = params["a_udl"]
        R1 = results_local.get("R1", 0.0)
        R2 = results_local.get("R2", 0.0)
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

Partial UDL \\(w\\) over length \\(a\\) from left:  

\\[
\\sum M_A = 0: \\quad R_2 L - w a \\cdot \\frac{{a}}{{2}} = 0
\\Rightarrow R_2 = \\frac{{w a^2}}{{2L}}
\\]

\\[
\\sum V = 0: \\quad R_1 + R_2 - w a = 0
\\Rightarrow R_1 = w a - R_2
\\]

For the selected data:

- \\(w = {w:.3g}\\,\\text{{kN/m}}\\)  

- \\(L = {L:.3g}\\,\\text{{m}}\\)  

- \\(a = {a_udl:.3g}\\,\\text{{m}}\\)

so numerically \\(R_1 = {R1:.3g}\\,\\text{{kN}}\\), \\(R_2 = {R2:.3g}\\,\\text{{kN}}\\).
"""

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

At the fixed support:  

\\[
\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - P = 0
\\Rightarrow V_{{\\text{{fixed}}}} = P
\\]

\\[
\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - P L = 0
\\Rightarrow M_{{\\text{{fixed}}}} = P L
\\]

For the selected data:

- \\(P = {P:.3g}\\,\\text{{kN}}\\)  

- \\(L = {L:.3g}\\,\\text{{m}}\\)

so at the fixed support: shear = \\({P:.3g}\\,\\text{{kN}}\\) (up), hogging moment = \\({P*L:.3g}\\,\\text{{kNm}}\\).
"""

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a_cant = params["a_cant"]
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

At the fixed support:  

\\[
\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - P = 0
\\Rightarrow V_{{\\text{{fixed}}}} = P
\\]

\\[
\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - P a = 0
\\Rightarrow M_{{\\text{{fixed}}}} = P a
\\]

For the selected data:

- \\(P = {P:.3g}\\,\\text{{kN}}\\)  

- \\(L = {L:.3g}\\,\\text{{m}}\\)  

- \\(a = {a_cant:.3g}\\,\\text{{m}}\\)

so at the fixed support: shear = \\({P:.3g}\\,\\text{{kN}}\\) (up), hogging moment = \\({P*a_cant:.3g}\\,\\text{{kNm}}\\).
"""

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

At the fixed support:  

\\[
\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - wL = 0
\\Rightarrow V_{{\\text{{fixed}}}} = wL
\\]

\\[
\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - wL \\cdot \\frac{{L}}{{2}} = 0
\\Rightarrow M_{{\\text{{fixed}}}} = \\frac{{wL^2}}{{2}}
\\]

For the selected data:

- \\(w = {w:.3g}\\,\\text{{kN/m}}\\)  

- \\(L = {L:.3g}\\,\\text{{m}}\\)

so at the fixed support: shear = \\({w*L:.3g}\\,\\text{{kN}}\\) (up), hogging moment = \\({0.5*w*L**2:.3g}\\,\\text{{kNm}}\\).
"""

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params["P"]
        L_main = params.get("L_main", L)
        a_over = params.get("a_overhang", 0.0)
        RA = results_local.get("RA", 0.0)
        RB = results_local.get("RB", 0.0)
        step2_md = f"""
**Step 2 – Reactions from equilibrium**

\\[
\\sum M_A = 0: \\quad R_B L - P(L+a) = 0
\\Rightarrow R_B = \\frac{{P(L+a)}}{{L}}
\\]

\\[
\\sum V = 0: \\quad R_A + R_B - P = 0
\\Rightarrow R_A = P - R_B = -\\frac{{Pa}}{{L}}
\\]

For the selected data:

- \\(P = {P:.3g}\\,\\text{{kN}}\\)  

- \\(L = {L_main:.3g}\\,\\text{{m}}\\) (span between supports)

- \\(a = {a_over:.3g}\\,\\text{{m}}\\) (overhang)

so numerically \\(R_A = {RA:.3g}\\,\\text{{kN}}\\) (down), \\(R_B = {RB:.3g}\\,\\text{{kN}}\\) (up).
"""

    if step2_md:
        calcbox(step2_md)

    # STEP 3 – shear function V(x)
    step3_md = ""

    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        R = results_local.get("R", w * L / 2.0)
        step3_md = f"""
**Step 3 – Shear function \\(V(x)\\)**

Taking sections from the left:

\\[
V(x) = R_1 - wx = \\frac{{wL}}{{2}} - wx, \\quad 0 \\le x \\le L
\\]

The shear diagram is linear, crossing zero at midspan for symmetric loading.

With \\(R_1 = {R:.3g}\\,\\text{{kN}}\\) and \\(w = {w:.3g}\\,\\text{{kN/m}}\\), the shear at \\(x = 0\\) is \\(V(0) = {R:.3g}\\,\\text{{kN}}\\).
"""

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        R1 = results_local.get("R1", P / 2.0)
        step3_md = f"""
**Step 3 – Shear function \\(V(x)\\)**

Let \\(a = L/2\\). For a centre point load:

\\[
V(x) = 
\\begin{{cases}}
R_1 & 0 \\le x < a\\\\
R_1 - P & a < x \\le L
\\end{{cases}}
\\]

with \\(R_1 = P/2 = {R1:.3g}\\,\\text{{kN}}\\).
"""

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a_val = params["a"]
        R1 = results_local.get("R1", 0.0)
        step3_md = f"""
**Step 3 – Shear function \\(V(x)\\)**

\\[
V(x) = 
\\begin{{cases}}
R_1 & 0 \\le x < a\\\\
R_1 - P & a < x \\le L
\\end{{cases}}
\\]

with \\(R_1 = {R1:.3g}\\,\\text{{kN}}\\) and \\(a = {a_val:.3g}\\,\\text{{m}}\\).
"""

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params["w"]
        a_udl = params["a_udl"]
        R1 = results_local.get("R1", 0.0)
        step3_md = f"""
**Step 3 – Shear function \\(V(x)\\)**

\\[
V(x) = 
\\begin{{cases}}
R_1 - w x & 0 \\le x \\le a\\\\
R_1 - w a & a \\le x \\le L
\\end{{cases}}
\\]

with \\(R_1 = {R1:.3g}\\,\\text{{kN}}\\), \\(w = {w:.3g}\\,\\text{{kN/m}}\\), and \\(a = {a_udl:.3g}\\,\\text{{m}}\\).
"""

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        step3_md = f"""
**Step 3 – Shear function \\(V(x)\\)**

\\[
V(x) = -P, \\quad 0 \\le x \\le L
\\]

The shear is constant (negative, indicating downward) along the entire length.
"""

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a_cant = params["a_cant"]
        step3_md = f"""
**Step 3 – Shear function \\(V(x)\\)**

\\[
V(x) = 
\\begin{{cases}}
-P & 0 \\le x \\le a\\\\
0 & a \\le x \\le L
\\end{{cases}}
\\]

The shear is constant (negative) from the fixed end to the load position, then zero beyond.
"""

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        step3_md = f"""
**Step 3 – Shear function \\(V(x)\\)**

\\[
V(x) = -w(L-x), \\quad 0 \\le x \\le L
\\]

The shear increases linearly from \\(-wL\\) at the fixed end to zero at the free end.
"""

    if step3_md:
        calcbox(step3_md)

    # STEP 4 – moment function M(x)
    step4_md = ""

    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        R = results_local.get("R", w * L / 2.0)
        M_max = w * L**2 / 8.0
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**

Integrating the shear:

\\[
M(x) = R_1 x - \\frac{{w x^2}}{{2}},
\\quad 0 \\le x \\le L
\\]

Maximum sagging moment occurs at midspan:

\\[
M_{{\\max}} = \\frac{{wL^2}}{{8}} = {M_max:.3g}\\,\\text{{kNm}} \\text{{ at }} x = \\frac{{L}}{{2}}
\\]
"""

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        M_max = P * L / 4.0
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**

\\[
M(x) = 
\\begin{{cases}}
R_1 x & 0 \\le x \\le a\\\\
R_1 x - P(x-a) & a \\le x \\le L
\\end{{cases}}
\\]

with \\(R_1 = P/2\\), so \\(M_{{\\max}} = PL/4 = {M_max:.3g}\\,\\text{{kNm}}\\) at midspan.
"""

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a_val = params["a"]
        R1 = results_local.get("R1", 0.0)
        M_max = R1 * a_val
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**

\\[
M(x) = 
\\begin{{cases}}
R_1 x & 0 \\le x \\le a\\\\
R_1 x - P(x-a) & a \\le x \\le L
\\end{{cases}}
\\]

Maximum moment occurs at the load position:

\\[
M_{{\\max}} = R_1 a = {M_max:.3g}\\,\\text{{kNm}} \\text{{ at }} x = {a_val:.3g}\\,\\text{{m}}
\\]
"""

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params["w"]
        a_udl = params["a_udl"]
        R1 = results_local.get("R1", 0.0)
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**

\\[
M(x) = 
\\begin{{cases}}
R_1 x - \\frac{{w x^2}}{{2}} & 0 \\le x \\le a\\\\
R_1 x - w a \\left(x - \\frac{{a}}{{2}}\\right) & a \\le x \\le L
\\end{{cases}}
\\]

Maximum moment occurs within the loaded region or at the end of the UDL.
"""

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        M_max = P * L
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**

\\[
M(x) = -P(L-x), \\quad 0 \\le x \\le L
\\]

Maximum hogging moment occurs at the fixed end:

\\[
M_{{\\max}} = PL = {M_max:.3g}\\,\\text{{kNm}} \\text{{ (hogging at fixed end)}}
\\]
"""

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a_cant = params["a_cant"]
        M_max = P * a_cant
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**

\\[
M(x) = 
\\begin{{cases}}
-P(a-x) & 0 \\le x \\le a\\\\
0 & a \\le x \\le L
\\end{{cases}}
\\]

Maximum hogging moment occurs at the fixed end:

\\[
M_{{\\max}} = P a = {M_max:.3g}\\,\\text{{kNm}} \\text{{ (hogging at fixed end)}}
\\]
"""

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        M_max = w * L**2 / 2.0
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**

\\[
M(x) = -\\frac{{w}}{{2}}(L-x)^2, \\quad 0 \\le x \\le L
\\]

Maximum hogging moment occurs at the fixed end:

\\[
M_{{\\max}} = \\frac{{wL^2}}{{2}} = {M_max:.3g}\\,\\text{{kNm}} \\text{{ (hogging at fixed end)}}
\\]
"""

    if step4_md:
        calcbox(step4_md)

    # Push SFD/BMD results into shared state
    update_results(
        span_L_m=float(L),
        sfd_Msls_max_kNm=float(M_max_abs),
        sfd_Vsls_max_kN=float(V_max_abs),
    )

    # Top summary bar (like other pages)
    summary_placeholder.info(
        f"SFD/BMD SLS: case = {case}, L = {L:.3g} m, "
        f"|V|_max ≈ {V_max_abs:.3g} kN, |M|_max ≈ {M_max_abs:.3g} kNm."
    )

    # ---------------------------------------------------
    # Show SFD & BMD
    # ---------------------------------------------------
    st.markdown("---")
    st.subheader("Shear force and bending moment diagrams")

    fig_sfd, fig_bmd = plot_sfd_bmd_plotly(x, V, M)
    col_sfd, col_bmd = st.columns(2)

    with col_sfd:
        st.plotly_chart(fig_sfd, use_container_width=True)

    with col_bmd:
        st.plotly_chart(fig_bmd, use_container_width=True)

