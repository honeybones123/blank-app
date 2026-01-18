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
    page_divider,
    step_expander_calcbox,
    apply_step_summary_expander_css,
    v2_number_input,
    v2_selectbox,
    v2_checkbox,
    v2_radio,
)
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks


def _label_with_hover(label: str, help_text: str) -> None:
    """Hover tooltip on the label text itself (no visible paragraph)."""
    safe = (help_text or "").replace('"', "&quot;")
    st.markdown(f'<span title="{safe}">{label}</span>', unsafe_allow_html=True)


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
                y=0,
                ax=xi,
                ay=0.45,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
                arrowcolor="black",
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
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=a,
            y=0,
            ax=a,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=a,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a_val = params.get("a")
        if a_val is None:
            a = L / 3
        else:
            a = float(a_val)
        a = max(0.0, min(a, L))
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=a,
            y=0,
            ax=a,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=a,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=L,
            y=0,
            ax=L,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=L,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a_val = params.get("a_cant")
        if a_val is None:
            a = L / 2
        else:
            a = float(a_val)
        a = max(0.0, min(a, L))
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=a,
            y=0,
            ax=a,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=a,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
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
                y=0,
                ax=xi,
                ay=0.45,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
                arrowcolor="black",
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
                y=0,
                ax=xi,
                ay=0.45,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
                arrowcolor="black",
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
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=L_total,
            y=0,
            ax=L_total,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=L_total,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
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

    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()

    apply_global_widget_css()
    apply_calcbox_css()
    
    # Override global widget max-width so selectboxes can fill their column
    st.markdown(
        """
        <style>
        /* Override global widget max-width so selectboxes can fill their column */
        body div[data-testid="stSelectbox"],
        body div[data-testid="stSelectbox"] > div {
            width: 100% !important;
            max-width: none !important;
        }

        body div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            width: 100% !important;
            max-width: none !important;
        }

        /* Let selected option text wrap instead of ellipsis */
        body div[data-testid="stSelectbox"] div[data-baseweb="select"] span {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            line-height: 1.2em !important;
        }

        /* Ensure nested elements also allow wrapping */
        body div[data-testid="stSelectbox"] div[data-baseweb="select"] * {
            white-space: normal !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    sync_callbacks = get_sync_callbacks()

    # Define stable UIDs for each calc box (step)
    EQ_SLS_UID = {
        "step1": "eq_sls_step1_support",
        "step2": "eq_sls_step2_reactions",
        "step3": "eq_sls_step3_shear_vx",
        "step4": "eq_sls_step4_moment_mx",
    }

    st.title("Shear & Moment Diagrams (Design / Teaching)")

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

    summary_placeholder = st.empty()

    # =========================================================
    # BEAM LOADING CONDITION (single source of truth)
    # =========================================================
    st.markdown("### Beam loading condition (single source of truth)")

    # Standardized row grid widths (label col + input col)
    ROW_COLS = [1.0, 3.0]
    
    # Force all inputs in the input column to start at the same left edge
    st.markdown("""
    <style>
    /* Make every widget in the loading section fill its column starting at the same left edge */
    .loading-grid [data-testid="stSelectbox"],
    .loading-grid [data-testid="stSelectbox"] > div,
    .loading-grid [data-testid="stSelectbox"] div[data-baseweb="select"],
    .loading-grid [data-testid="stNumberInput"],
    .loading-grid [data-testid="stNumberInput"] > div {
      width: 100% !important;
      max-width: 100% !important;
      margin-left: 0 !important;
    }

    /* Cap loading selectbox size but keep left edge aligned */
    .loading-grid .loading-select [data-testid="stSelectbox"],
    .loading-grid .loading-select [data-testid="stSelectbox"] > div,
    .loading-grid .loading-select div[data-baseweb="select"] {
      width: 100% !important;
      max-width: 620px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Wrap the entire loading section in a container
    st.markdown("<div class='loading-grid'>", unsafe_allow_html=True)
    
    # Loading condition dropdown as a row (label left, widget right, hover help)
    LOADING_OPTIONS = [
        "Simple beam – UDL over entire span",
        "Simple beam – partial UDL from left (length a)",
        "Simple beam – point load at centre",
        "Simple beam – point load at distance a from left",
        "Cantilever – point load at free end",
        "Cantilever – point load at distance a from fixed end",
        "Cantilever – UDL over entire span",
        "Overhanging beam – right overhang with point load at free end",
    ]
    
    # Get current selection index
    current_case = st.session_state.get("load_case", LOADING_OPTIONS[0])
    loading_index = LOADING_OPTIONS.index(current_case) if current_case in LOADING_OPTIONS else 0
    
    # Loading condition row with standardized column ratio
    c1, c2 = st.columns(ROW_COLS, vertical_alignment="center")
    with c1:
        _label_with_hover(
            "Loading condition",
            "Choose the beam support and load case used to derive reactions, SFD and BMD. "
            "This is the single source of truth for bending and shear demand used elsewhere in the app."
        )
    with c2:
        st.markdown("<div class='loading-select'>", unsafe_allow_html=True)
        load_case = v2_selectbox(
            label="__loading_condition_select__",
            key="load_case",
            options=LOADING_OPTIONS,
            default_index=loading_index,
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # -------- span as editable widget --------
    L_seed = get_param("span_L_m", 6.0)
    L_seed = max(0.1, L_seed)  # Ensure it meets min_value
    
    # Custom row for Span L (needs min_value=0.1, step=0.5) - aligned with other inputs
    c1, c2 = st.columns(ROW_COLS, vertical_alignment="center")
    with c1:
        _label_with_hover(
            "Span L (m)",
            "Beam span used for reactions, SFD and BMD."
        )
    with c2:
        L = v2_number_input(
            label="Value",
            key="load_L",
            default=L_seed,
            min_value=0.1,
            step=0.5,
            on_change=sync_callbacks.get("load_L", lambda: None),
            label_visibility="collapsed",
        )
    
    # Update session state
    update_results(span_L_m=float(L))

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
        # Dead UDL g row - using ROW_COLS for alignment
        c1, c2 = st.columns(ROW_COLS, vertical_alignment="center")
        with c1:
            _label_with_hover(
                "Dead UDL g (kN/m)",
                "Permanent action line load used for SFD/BMD demand derivation."
            )
        with c2:
            g = v2_number_input(
                label="Value",
                key="load_g_udl",
                default=float(st.session_state.get("load_g_udl", get_param("g_udl_kNm_per_m", 8.0))),
                step=1.0,
                format="%.1f",
                label_visibility="collapsed",
                on_change=sync_callbacks.get("load_g_udl", lambda: None),
            )
        
        # Live UDL q row - using ROW_COLS for alignment
        c1, c2 = st.columns(ROW_COLS, vertical_alignment="center")
        with c1:
            _label_with_hover(
                "Live UDL q (kN/m)",
                "Imposed action line load used for SFD/BMD demand derivation."
            )
        with c2:
            q = v2_number_input(
                label="Value",
                key="load_q_udl",
                default=float(st.session_state.get("load_q_udl", get_param("q_udl_kNm_per_m", 4.0))),
                step=1.0,
                format="%.1f",
                label_visibility="collapsed",
                on_change=sync_callbacks.get("load_q_udl", lambda: None),
            )
        
        # Sustained factor ψ_s row - using ROW_COLS for alignment
        c1, c2 = st.columns(ROW_COLS, vertical_alignment="center")
        with c1:
            _label_with_hover(
                "Sustained factor ψ_s",
                "Portion of variable action treated as sustained for long-term effects (used by deflection/creep logic)."
            )
        with c2:
            psi_s = v2_number_input(
                label="Value",
                key="load_psi_udl",
                default=float(st.session_state.get("load_psi_udl", get_param("psi_udl", 0.4))),
                step=0.05,
                format="%.2f",
                label_visibility="collapsed",
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
            params["a_udl"] = v2_number_input(
                label="UDL length a from left (m)",
                key="sfd_a_udl",
                default=L / 2,
                min_value=0.0,
                step=0.1,
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
        G_point = v2_number_input(
            label="Dead point load G (kN)",
            key="load_G_point",
            default=50.0,
            min_value=0.0,
            step=5.0,
            on_change=sync_callbacks.get("load_G_point", lambda: None),
        )
        Q_point = v2_number_input(
            label="Live point load Q (kN)",
            key="load_Q_point",
            default=30.0,
            min_value=0.0,
            step=5.0,
            on_change=sync_callbacks.get("load_Q_point", lambda: None),
        )
        psi_s = v2_number_input(
            label="Sustained factor ψ_s for point load",
            key="load_psi_point",
            default=0.4,
            min_value=0.0,
            step=0.05,
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
            a = v2_number_input(
                label="Distance a from left support (m)",
                key="load_a_point",
                default=L / 3,
                min_value=0.0,
                step=0.1,
                on_change=sync_callbacks.get("load_a_point", lambda: None),
            )
            a_shared = get_param("a_m", a)
            params["a"] = a_shared
        elif load_case == "Cantilever – point load at distance a from fixed end":
            a = v2_number_input(
                label="Distance a from fixed end (m)",
                key="sfd_a_cant",
                default=L / 2,
                min_value=0.0,
                step=0.1,
            )
            params["a_cant"] = a
        elif load_case == "Overhanging beam – right overhang with point load at free end":
            L_main = L  # span between supports from Inputs
            a_over = v2_number_input(
                label="Overhang length a (m)",
                key="sfd_a_overhang",
                default=2.0,
                min_value=0.0,
                step=0.5,
            )
            params["L_main"] = L_main
            params["a_overhang"] = a_over

        # Note: a_m is a shared input (synced via widget callback), not a result
        # The widget callback will sync load_a_point -> a_m automatically
        update_results(
            span_L_m=float(L),
            G_point_kN=float(G_shared),
            Q_point_kN=float(Q_shared),
            psi_point=float(psi_shared),
            P_sls_kN=float(P_sls),
            P_uls_kN=float(P_uls),
        )

    # Close the loading-grid container
    st.markdown("</div>", unsafe_allow_html=True)

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
        a_val = params.get("a")
        if a_val is None:
            a = L / 3
        else:
            a = float(a_val)
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
    # Build summary rows and render clickable summary table
    # ---------------------------------------------------
    # Determine support type for summary
    support_type = "—"
    if case.startswith("Simple beam"):
        support_type = "Pinned–Pinned"
    elif case.startswith("Cantilever"):
        support_type = "Fixed–Free"
    elif case == "Overhanging beam – right overhang with point load at free end":
        support_type = "Pinned–Pinned (overhang)"

    # Get capacity values for limit display (reuse existing computed values)
    phi_Mu_cap = get_param("phi_Mu_cap", None)
    phi_Vu_cap = get_param("phi_Vu_cap", None)
    
    # Determine limit strings for derivation rows
    shear_limit = "—"
    if phi_Vu_cap is not None and not (isinstance(phi_Vu_cap, float) and math.isnan(phi_Vu_cap)) and phi_Vu_cap > 0:
        shear_limit = f"φV_u,cap = {phi_Vu_cap:.1f} kN"
    
    moment_limit = "—"
    if phi_Mu_cap is not None and not (isinstance(phi_Mu_cap, float) and math.isnan(phi_Mu_cap)) and phi_Mu_cap > 0:
        moment_limit = f"φM_u = {phi_Mu_cap:.1f} kNm"

    # Build summary rows for clickable table
    rows_summary = [
        {"Check": "Support conditions", "Value": support_type, "Limit": "—", "Utilisation": "—", "Status": "OK"},
        {"Check": "Reactions", "Value": "Derived", "Limit": "—", "Utilisation": "—", "Status": "OK"},
        {"Check": "Shear derivation", "Value": f"|V|_max = {V_max_abs:.2f} kN", "Limit": shear_limit, "Utilisation": "—", "Status": "OK"},
        {"Check": "Moment derivation", "Value": f"|M|_max = {M_max_abs:.2f} kNm", "Limit": moment_limit, "Utilisation": "—", "Status": "OK"},
    ]

    check_to_uid = {
        "Support conditions": EQ_SLS_UID["step1"],
        "Reactions": EQ_SLS_UID["step2"],
        "Shear derivation": EQ_SLS_UID["step3"],
        "Moment derivation": EQ_SLS_UID["step4"],
    }

    check_to_tab = {
        "Support conditions": "SLS",
        "Reactions": "SLS",
        "Shear derivation": "SLS",
        "Moment derivation": "SLS",
    }

    ROWS = []
    for r in rows_summary:
        check = r.get("Check", "")
        limit = r.get("Limit", "—")
        util_str = r.get("Utilisation", "—")
        status_str = r.get("Status", "")
        
        # Explicitly set capacity limits for derivation rows (before styling logic)
        if check == "Shear derivation":
            limit = shear_limit
            # Calculate utilisation: demand vs capacity
            if phi_Vu_cap not in (0, None) and not (isinstance(phi_Vu_cap, float) and math.isnan(phi_Vu_cap)):
                util_val = V_max_abs / phi_Vu_cap
                util_str = str(round(util_val, 3)) if util_val is not None else "—"
                status_str = "OK" if (util_val is not None and util_val <= 1.0) else "NG"
                ok = True if status_str == "OK" else False
            else:
                util_str = "—"
                status_str = "—"
                ok = None
        elif check == "Moment derivation":
            limit = moment_limit
            # Calculate utilisation: demand vs capacity
            if phi_Mu_cap not in (0, None) and not (isinstance(phi_Mu_cap, float) and math.isnan(phi_Mu_cap)):
                util_val = M_max_abs / phi_Mu_cap
                util_str = str(round(util_val, 3)) if util_val is not None else "—"
                status_str = "OK" if (util_val is not None and util_val <= 1.0) else "NG"
                ok = True if status_str == "OK" else False
            else:
                util_str = "—"
                status_str = "—"
                ok = None
        
        # Determine if this is a check row (has numeric utilisation for pass/fail)
        # A row is a check row only if it has a numeric utilisation (not just a limit)
        is_check_row = util_str not in ("", "—", None)
        
        # Force derivation rows to be treated as check rows
        if check in ("Shear derivation", "Moment derivation"):
            is_check_row = True
        
        # Determine ok status for styling (True=pass/green, False=fail/red, None=neutral-blue)
        if not is_check_row:
            # No utilisation check → neutral blue styling
            # Keep util as "—" but DO NOT touch limit (derivation rows can show limits)
            util_str = "—"
            ok = None
        else:
            # Has utilisation check → derive ok from status (if not already set above)
            if ok is None:
                if status_str == "OK":
                    ok = True
                elif status_str in ("NG", "Fail", "Not OK"):
                    ok = False
                else:
                    # For rows with utilisation, derive status from util if status is not explicitly set
                    if util_str != "—" and status_str == "":
                        try:
                            util_val = float(util_str)
                            if not math.isnan(util_val):
                                status_str = "OK" if util_val <= 1.0 else "NG"
                                ok = True if util_val <= 1.0 else False
                            else:
                                ok = None
                        except (ValueError, TypeError):
                            ok = None
                    else:
                        ok = None

        ROWS.append({
            "title": check,
            "value": r.get("Value", "—"),
            "limit": limit,
            "util": util_str,
            "status": status_str,
            "ok": ok,
            "uid": check_to_uid.get(check, ""),
            "tab": check_to_tab.get(check, "SLS"),
        })

    # Render clickable summary table
    with summary_placeholder.container():
        st.markdown("## Summary")
        render_clickable_summary_table(ROWS, key_prefix="design_summary")
    
    page_divider()

    # ---------------------------------------------------
    # Load diagram – directly under inputs
    # ---------------------------------------------------
    st.subheader("Load diagram (SLS loads)")

    fig_load = plot_load_diagram_plotly(case, beam_length, params)
    st.plotly_chart(fig_load, width="stretch")

    # ---------------------------------------------------
    # Full equilibrium derivation – 4 blue calc boxes
    # ---------------------------------------------------
    st.subheader("Equilibrium derivation (SLS)")

    # STEP 1 – Support conditions (expandable)
    step1_md = ""
    step1_summary = ""
    
    if case.startswith("Simple beam"):
        step1_summary = f"Step 1 – Support conditions | Simply supported (pinned–pinned) beam of span $L = {L:.1f}$ m → vertical reactions at supports"
        step1_md = f"""
**1) Inputs**  \n
- Left support: pinned  \n
- Right support: pinned  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0$  \n
- $\\sum M = 0$  \n\n
**3) Substitute / derive**  \n
- For a simply supported beam, reactions act vertically at each support.  \n\n
**4) Result**  \n
- Proceed to solve for $R_A$ and $R_B$ from equilibrium.
"""
    elif case.startswith("Cantilever"):
        step1_summary = f"Step 1 – Support conditions | Cantilever (fixed–free) beam of span $L = {L:.1f}$ m → fixed end moment and shear at support, zero reactions at free end"
        step1_md = f"""
**1) Inputs**  \n
- Left support: fixed  \n
- Right end: free  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0$  \n
- $\\sum M = 0$  \n\n
**3) Substitute / derive**  \n
- A cantilever has a fixed end moment and shear at the support and zero reactions at the free end.  \n\n
**4) Result**  \n
- Proceed to solve for reactions at the fixed end.
"""
    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = params.get("L_main", L)
        step1_summary = f"Step 1 – Support conditions | Overhanging beam with pinned supports (span $L = {L_main:.1f}$ m) and free overhang end → reactions at pinned supports"
        step1_md = f"""
**1) Inputs**  \n
- Support A (left): pinned  \n
- Support B (internal): pinned at distance $L = {L_main:.3g}\\, \\text{{m}}$ from A  \n
- Right overhang end: free at $x = L + a$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0$  \n
- $\\sum M = 0$  \n\n
**3) Substitute / derive**  \n
- Reactions act at the pinned supports.  \n\n
**4) Result**  \n
- Proceed to solve for $R_A$ and $R_B$ from equilibrium.
"""
    else:
        step1_md = ""
        step1_summary = ""
    
    if step1_md and step1_summary:
        step1_uid = EQ_SLS_UID["step1"]
        step_expander_calcbox(
            uid=step1_uid,
            summary_line=step1_summary,
            details_md=step1_md,
            status=None,
        )

    # STEP 2 – reactions (case-by-case)
    step2_md = ""

    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        R = results_local.get("R", w * L / 2.0)
        wL_val = w * L
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Use $\\sum V=0$ and $\\sum M=0$: $R_1 = R_2 = {R:.1f}$ kN"
        step2_md = f"""
**1) Inputs**  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Total load: $wL = {wL_val:.3g}\\, \\text{{kN}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - wL = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - wL \\cdot \\frac{{L}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{wL}}{{2}} = \\frac{{{w:.3g} \\times {L:.3g}}}{{2}} = \\frac{{{wL_val:.3g}}}{{2}} = {R:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = wL - R_2 = {wL_val:.3g} - {R:.3g} = {R:.3g}\\, \\text{{kN}}$$  \n\n
**4) Result**  \n
$R_1 = R_2 = {R:.3g}\\, \\text{{kN}}$ (both reactions equal for symmetric loading).
"""

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        R1 = results_local.get("R1", P / 2.0)
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at midspan: $R_1 = R_2 = {R1:.1f}$ kN"
        step2_md = f"""
**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Load position: $a = L/2 = {L/2:.3g}\\, \\text{{m}}$ (midspan)  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - P = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - P \\cdot \\frac{{L}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{P}}{{2}} = \\frac{{{P:.3g}}}{{2}} = {R1:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = P - R_2 = {P:.3g} - {R1:.3g} = {R1:.3g}\\, \\text{{kN}}$$  \n\n
**4) Result**  \n
$R_1 = R_2 = {R1:.3g}\\, \\text{{kN}}$ (equal reactions for symmetric loading).
"""

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a_val = params.get("a")
        if a_val is None:
            a_val = L / 3
        else:
            a_val = float(a_val)
        R1 = results_local.get("R1", P * (L - a_val) / L)
        R2 = results_local.get("R2", P * a_val / L)
        b_val = L - a_val
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at $a = {a_val:.1f}$ m: $R_1 = {R1:.1f}$ kN, $R_2 = {R2:.1f}$ kN"
        step2_md = f"""
**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Distance from left: $a = {a_val:.3g}\\, \\text{{m}}$  \n
- Distance from right: $b = L - a = {b_val:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - P = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - P a = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{Pa}}{{L}} = \\frac{{{P:.3g} \\times {a_val:.3g}}}{{{L:.3g}}} = \\frac{{{P*a_val:.3g}}}{{{L:.3g}}} = {R2:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = P - R_2 = {P:.3g} - {R2:.3g} = {R1:.3g}\\, \\text{{kN}}$$  \n
Alternatively: $R_1 = \\frac{{Pb}}{{L}} = \\frac{{{P:.3g} \\times {b_val:.3g}}}{{{L:.3g}}} = {R1:.3g}\\, \\text{{kN}}$  \n\n
**4) Result**  \n
$R_1 = {R1:.3g}\\, \\text{{kN}}$, $R_2 = {R2:.3g}\\, \\text{{kN}}$.
"""

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params["w"]
        a_udl = params["a_udl"]
        wa_val = w * a_udl
        R2 = results_local.get("R2", w * a_udl**2 / (2 * L))
        R1 = results_local.get("R1", wa_val - R2)
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Partial UDL $w = {w:.1f}$ kN/m over $a = {a_udl:.1f}$ m: $R_1 = {R1:.1f}$ kN, $R_2 = {R2:.1f}$ kN"
        step2_md = f"""
**1) Inputs**  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- UDL length: $a = {a_udl:.3g}\\, \\text{{m}}$  \n
- Total partial load: $wa = {wa_val:.3g}\\, \\text{{kN}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - wa = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - wa \\cdot \\frac{{a}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{wa^2}}{{2L}} = \\frac{{{w:.3g} \\times {a_udl:.3g}^2}}{{2 \\times {L:.3g}}} = \\frac{{{w*a_udl**2:.3g}}}{{{2*L:.3g}}} = {R2:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = wa - R_2 = {wa_val:.3g} - {R2:.3g} = {R1:.3g}\\, \\text{{kN}}$$  \n\n
**4) Result**  \n
$R_1 = {R1:.3g}\\, \\text{{kN}}$, $R_2 = {R2:.3g}\\, \\text{{kN}}$.
"""

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        V_fixed = P
        M_fixed = P * L
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at free end: $V = {V_fixed:.1f}$ kN, $M = {M_fixed:.1f}$ kNm (hogging)"
        step2_md = f"""
**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - P = 0$  \n
- $\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - P L = 0$  \n\n
**3) Substitute / derive**  \n
From vertical equilibrium:  \n
$$V_{{\\text{{fixed}}}} = P = {P:.3g}\\, \\text{{kN}}$$  \n
From moment equilibrium:  \n
$$M_{{\\text{{fixed}}}} = P L = {P:.3g} \\times {L:.3g} = {M_fixed:.3g}\\, \\text{{kNm}}$$  \n\n
**4) Result**  \n
At the fixed support: shear = $V = {V_fixed:.3g}\\, \\text{{kN}}$ (upward), hogging moment = $M = {M_fixed:.3g}\\, \\text{{kNm}}$.
"""

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a_cant = params["a_cant"]
        V_fixed = P
        M_fixed = P * a_cant
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at $a = {a_cant:.1f}$ m: $V = {V_fixed:.1f}$ kN, $M = {M_fixed:.1f}$ kNm (hogging)"
        step2_md = f"""
**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Distance from fixed end: $a = {a_cant:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - P = 0$  \n
- $\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - P a = 0$  \n\n
**3) Substitute / derive**  \n
From vertical equilibrium:  \n
$$V_{{\\text{{fixed}}}} = P = {P:.3g}\\, \\text{{kN}}$$  \n
From moment equilibrium:  \n
$$M_{{\\text{{fixed}}}} = P a = {P:.3g} \\times {a_cant:.3g} = {M_fixed:.3g}\\, \\text{{kNm}}$$  \n\n
**4) Result**  \n
At the fixed support: shear = $V = {V_fixed:.3g}\\, \\text{{kN}}$ (upward), hogging moment = $M = {M_fixed:.3g}\\, \\text{{kNm}}$.
"""

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        wL_val = w * L
        V_fixed = wL_val
        M_fixed = w * L**2 / 2.0
        
        step2_summary = f"Step 2 – Reactions from equilibrium | UDL $w = {w:.1f}$ kN/m over $L = {L:.1f}$ m: $V = {V_fixed:.1f}$ kN, $M = {M_fixed:.1f}$ kNm (hogging)"
        step2_md = f"""
**1) Inputs**  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Total load: $wL = {wL_val:.3g}\\, \\text{{kN}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - wL = 0$  \n
- $\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - wL \\cdot \\frac{{L}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From vertical equilibrium:  \n
$$V_{{\\text{{fixed}}}} = wL = {w:.3g} \\times {L:.3g} = {V_fixed:.3g}\\, \\text{{kN}}$$  \n
From moment equilibrium:  \n
$$M_{{\\text{{fixed}}}} = \\frac{{wL^2}}{{2}} = \\frac{{{w:.3g} \\times {L:.3g}^2}}{{2}} = \\frac{{{w*L**2:.3g}}}{{2}} = {M_fixed:.3g}\\, \\text{{kNm}}$$  \n\n
**4) Result**  \n
At the fixed support: shear = $V = {V_fixed:.3g}\\, \\text{{kN}}$ (upward), hogging moment = $M = {M_fixed:.3g}\\, \\text{{kNm}}$.
"""

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params["P"]
        L_main = params.get("L_main", L)
        a_over = params.get("a_overhang", 0.0)
        RA = results_local.get("RA", -P * a_over / L_main)
        RB = results_local.get("RB", P * (L_main + a_over) / L_main)
        L_plus_a = L_main + a_over
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN on overhang: $R_A = {RA:.1f}$ kN, $R_B = {RB:.1f}$ kN"
        step2_md = f"""
**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span between supports: $L = {L_main:.3g}\\, \\text{{m}}$  \n
- Overhang length: $a = {a_over:.3g}\\, \\text{{m}}$  \n
- Total distance: $L + a = {L_plus_a:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_A + R_B - P = 0$  \n
- $\\sum M_A = 0: \\quad R_B L - P(L+a) = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_B = \\frac{{P(L+a)}}{{L}} = \\frac{{{P:.3g} \\times {L_plus_a:.3g}}}{{{L_main:.3g}}} = \\frac{{{P*L_plus_a:.3g}}}{{{L_main:.3g}}} = {RB:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_A = P - R_B = {P:.3g} - {RB:.3g} = {RA:.3g}\\, \\text{{kN}}$$  \n
Note: $R_A$ is negative (downward) when the overhang load creates upward reaction at B.  \n\n
**4) Result**  \n
$R_A = {RA:.3g}\\, \\text{{kN}}$ (downward), $R_B = {RB:.3g}\\, \\text{{kN}}$ (upward).
"""

    # STEP 2 – Reactions (expandable)
    step2_summary_exists = False
    try:
        _ = step2_summary
        step2_summary_exists = True
    except NameError:
        pass
    
    if step2_md and step2_summary_exists:
        step2_uid = EQ_SLS_UID["step2"]
        # Remove any summary line from details if present
        step2_details = step2_md
        if "*Two-line summary:*" in step2_details or "**Step 2 – Reactions from equilibrium**" in step2_details.split("\n")[0]:
            lines = step2_details.split("\n")
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if "*Two-line summary:*" in line or (i == 0 and "**Step 2" in line):
                    skip_next = True
                    continue
                if skip_next and line.strip() == "":
                    skip_next = False
                    continue
                if not skip_next:
                    new_lines.append(line)
            step2_details = "\n".join(new_lines).strip()
        
        step_expander_calcbox(
            uid=step2_uid,
            summary_line=step2_summary,
            details_md=step2_details,
            status=None,
        )

    # STEP 3 – shear function V(x)
    step3_md = ""

    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        R = results_local.get("R", w * L / 2.0)
        V_at_0 = R
        V_at_L = -R
        
        step3_summary = f"Step 3 – Shear function $V(x)$ | UDL $w = {w:.1f}$ kN/m: $V(0) = {V_at_0:.1f}$ kN, $V(L) = {V_at_L:.1f}$ kN, zero at midspan"
        step3_md = f"""
**1) Inputs**  \n
- Reactions: $R_1 = R_2 = {R:.3g}\\, \\text{{kN}}$  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\frac{{\\mathrm{{d}}V}}{{\\mathrm{{d}}x}} = -w(x)$  \n
- For UDL: $V(x) = R_1 - wx$  \n\n
**3) Substitute / derive**  \n
Taking sections from the left:  \n
$$V(x) = R_1 - wx = {R:.3g} - {w:.3g} x, \\quad 0 \\le x \\le L$$  \n
At $x = 0$: $V(0) = {R:.3g} - 0 = {V_at_0:.3g}\\, \\text{{kN}}$  \n
At $x = L$: $V(L) = {R:.3g} - {w:.3g} \\times {L:.3g} = {R:.3g} - {w*L:.3g} = {V_at_L:.3g}\\, \\text{{kN}}$  \n
Zero crossing at: $x = \\frac{{R_1}}{{w}} = \\frac{{{R:.3g}}}{{{w:.3g}}} = {R/w:.3g}\\, \\text{{m}}$ (midspan)  \n\n
**4) Result**  \n
$V(x) = {R:.3g} - {w:.3g}x$ for $0 \\le x \\le L$. Linear diagram crossing zero at midspan.
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
        a_val = params.get("a")
        if a_val is None:
            a_val = L / 3
        else:
            a_val = float(a_val)
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

    # STEP 3 – Shear function (expandable)
    step3_summary_exists = False
    try:
        _ = step3_summary
        step3_summary_exists = True
    except NameError:
        # Fallback summary if not set
        step3_summary = "Step 3 – Shear function $V(x)$ | Build $V(x)$ from left to right using sign convention and loading"
        step3_summary_exists = True
    
    if step3_md and step3_summary_exists:
        step3_uid = EQ_SLS_UID["step3"]
        # Remove any summary line from details if present
        step3_details = step3_md
        if "*Two-line summary:*" in step3_details or "**Step 3 – Shear function" in step3_details.split("\n")[0]:
            lines = step3_details.split("\n")
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if "*Two-line summary:*" in line or (i == 0 and "**Step 3" in line):
                    skip_next = True
                    continue
                if skip_next and line.strip() == "":
                    skip_next = False
                    continue
                if not skip_next:
                    new_lines.append(line)
            step3_details = "\n".join(new_lines).strip()
        
        step_expander_calcbox(
            uid=step3_uid,
            summary_line=step3_summary,
            details_md=step3_details,
            status=None,
        )

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
        a_val = params.get("a")
        if a_val is None:
            a_val = L / 3
        else:
            a_val = float(a_val)
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

    # STEP 4 – Moment function (expandable)
    step4_summary_exists = False
    try:
        _ = step4_summary
        step4_summary_exists = True
    except NameError:
        # Fallback summary if not set
        step4_summary = "Step 4 – Moment function $M(x)$ | Integrate shear to obtain $M(x)$ and apply boundary conditions"
        step4_summary_exists = True
    
    if step4_md and step4_summary_exists:
        step4_uid = EQ_SLS_UID["step4"]
        # Remove any summary line from details if present
        step4_details = step4_md
        if "*Two-line summary:*" in step4_details or "**Step 4 – Moment function" in step4_details.split("\n")[0]:
            lines = step4_details.split("\n")
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if "*Two-line summary:*" in line or (i == 0 and "**Step 4" in line):
                    skip_next = True
                    continue
                if skip_next and line.strip() == "":
                    skip_next = False
                    continue
                if not skip_next:
                    new_lines.append(line)
            step4_details = "\n".join(new_lines).strip()
        
        step_expander_calcbox(
            uid=step4_uid,
            summary_line=step4_summary,
            details_md=step4_details,
            status=None,
        )

    # Push SFD/BMD results into shared state
    # (use key names expected by Inputs page)
    update_results(
        span_L_m=float(L),              # generic span
        sfd_span_L_m=float(L),          # span as seen by SFD/deflection pages
        sfd_case=case,                  # store current teaching case
        sfd_Mmax_abs_kNm=float(M_max_abs),
        sfd_Vmax_abs_kN=float(V_max_abs),
    )

    # ---------------------------------------------------
    # Show SFD & BMD
    # ---------------------------------------------------
    page_divider()
    st.subheader("Shear force and bending moment diagrams")

    fig_sfd, fig_bmd = plot_sfd_bmd_plotly(x, V, M)
    col_sfd, col_bmd = st.columns(2)

    with col_sfd:
        st.plotly_chart(fig_sfd, width="stretch")

    with col_bmd:
        st.plotly_chart(fig_bmd, width="stretch")

    # Bind JS click/scroll after all steps render
    bind_summary_clicks()

