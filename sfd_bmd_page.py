# sfd_bmd_page.py
# ==========================================
# SFD & BMD teaching page for beam app
# ==========================================

import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from state_and_helpers import get_sync_callbacks, update_results
from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row


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
def plot_load_diagram(case, L, params):
    """
    Draw the qualitative load diagram (supports + loads).
    L is the total beam length shown along the x-axis.
    """
    fig, ax = plt.subplots(figsize=(6, 2.5))

    # Draw the beam line
    ax.plot([0, L], [0, 0], "k", linewidth=2)

    # ---- Supports / fixed ends ----
    if case.startswith("Simple beam"):
        # pinned supports at 0 and L
        draw_support(ax, 0.0, kind="pinned")
        draw_support(ax, L, kind="pinned")

    elif case.startswith("Cantilever"):
        # fixed at left, free at right
        draw_support(ax, 0.0, kind="fixed")

    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = params.get("L_main", L)
        draw_support(ax, 0.0, kind="pinned")
        draw_support(ax, L_main, kind="pinned")
        # right end (L_main + a_over) is free (no symbol)

    # ---- Loads ----
    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        ax.fill_between([0, L], [0.3, 0.3], [0, 0], alpha=0.3)
        n_arrows = 7
        xs = np.linspace(0.1 * L, 0.9 * L, n_arrows)
        for xi in xs:
            ax.arrow(
                xi, 0.4, 0, -0.25,
                head_width=0.08, head_length=0.05,
                length_includes_head=True
            )
        ax.text(L * 0.5, 0.45, f"w = {w:.2f} kN/m", ha="center", va="bottom")

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params["w"]
        a = params["a_udl"]
        a = max(0.0, min(a, L))
        ax.fill_between([0, a], [0.3, 0.3], [0, 0], alpha=0.3)
        xs = np.linspace(0.1 * a, 0.9 * a, 5)
        for xi in xs:
            ax.arrow(
                xi, 0.4, 0, -0.25,
                head_width=0.08, head_length=0.05,
                length_includes_head=True
            )
        ax.text(a / 2, 0.45, f"w = {w:.2f} kN/m", ha="center", va="bottom")
        ax.annotate(
            "", xy=(0, -0.2), xytext=(a, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(a / 2, -0.25, "a", ha="center", va="top")
        ax.annotate(
            "", xy=(a, -0.2), xytext=(L, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text((a + L) / 2, -0.25, "L - a", ha="center", va="top")

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        a = L / 2
        ax.arrow(
            a, 0.4, 0, -0.35,
            head_width=0.08, head_length=0.05,
            length_includes_head=True
        )
        ax.text(a, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate(
            "", xy=(0, -0.2), xytext=(a, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(a / 2, -0.25, "L/2", ha="center", va="top")
        ax.annotate(
            "", xy=(a, -0.2), xytext=(L, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text((a + L) / 2, -0.25, "L/2", ha="center", va="top")

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a = params["a"]
        a = max(0.0, min(a, L))
        ax.arrow(
            a, 0.4, 0, -0.35,
            head_width=0.08, head_length=0.05,
            length_includes_head=True
        )
        ax.text(a, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate(
            "", xy=(0, -0.2), xytext=(a, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(a / 2, -0.25, "a", ha="center", va="top")
        ax.annotate(
            "", xy=(a, -0.2), xytext=(L, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text((a + L) / 2, -0.25, "b = L - a", ha="center", va="top")

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        ax.arrow(
            L, 0.4, 0, -0.35,
            head_width=0.08, head_length=0.05,
            length_includes_head=True
        )
        ax.text(L, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate(
            "", xy=(0, -0.2), xytext=(L, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(L / 2, -0.25, "L", ha="center", va="top")

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a = params["a_cant"]
        a = max(0.0, min(a, L))
        ax.arrow(
            a, 0.4, 0, -0.35,
            head_width=0.08, head_length=0.05,
            length_includes_head=True
        )
        ax.text(a, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate(
            "", xy=(0, -0.2), xytext=(a, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(a / 2, -0.25, "a", ha="center", va="top")
        ax.annotate(
            "", xy=(a, -0.2), xytext=(L, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text((a + L) / 2, -0.25, "L - a", ha="center", va="top")

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        ax.fill_between([0, L], [0.3, 0.3], [0, 0], alpha=0.3)
        n_arrows = 7
        xs = np.linspace(0.1 * L, 0.9 * L, n_arrows)
        for xi in xs:
            ax.arrow(
                xi, 0.4, 0, -0.25,
                head_width=0.08, head_length=0.05,
                length_includes_head=True
            )
        ax.text(L * 0.5, 0.45, f"w = {w:.2f} kN/m", ha="center", va="bottom")
        ax.annotate(
            "", xy=(0, -0.2), xytext=(L, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(L / 2, -0.25, "L", ha="center", va="top")

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params["P"]
        L_main = params["L_main"]
        a_over = params["a_overhang"]
        L_total = L_main + a_over
        ax.arrow(
            L_total, 0.4, 0, -0.35,
            head_width=0.08, head_length=0.05,
            length_includes_head=True
        )
        ax.text(L_total, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate(
            "", xy=(0, -0.2), xytext=(L_main, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(L_main / 2, -0.25, "L", ha="center", va="top")
        ax.annotate(
            "", xy=(L_main, -0.2), xytext=(L_total, -0.2),
            arrowprops=dict(arrowstyle="<->")
        )
        ax.text(L_main + a_over / 2, -0.25, "a", ha="center", va="top")

    ax.set_xlim(-0.3, L + 0.3)
    ax.set_ylim(-0.9, 0.9)
    ax.axis("off")
    return fig


# ---------------------------------------------------
# Helper: plot SFD and BMD
# ---------------------------------------------------
def plot_sfd_bmd(x, V, M):
    # SFD
    fig_sfd, ax_sfd = plt.subplots(figsize=(6, 3))
    ax_sfd.axhline(0, color="k", linewidth=0.8)
    ax_sfd.plot(x, V, linewidth=2)
    ax_sfd.set_xlabel("x (m)")
    ax_sfd.set_ylabel("V (kN)")
    ax_sfd.set_title("Shear Force Diagram (SFD)")
    ax_sfd.grid(True, alpha=0.3)

    # BMD
    fig_bmd, ax_bmd = plt.subplots(figsize=(6, 3))
    ax_bmd.axhline(0, color="k", linewidth=0.8)
    ax_bmd.plot(x, M, linewidth=2)
    ax_bmd.set_xlabel("x (m)")
    ax_bmd.set_ylabel("M (kNm)")
    ax_bmd.set_title("Bending Moment Diagram (BMD)")
    ax_bmd.grid(True, alpha=0.3)

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
            R = results["R"]
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - wL \cdot \frac{L}{2} = 0")
            st.latex(r"R_2 = \frac{wL}{2}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - wL = 0")
            st.latex(r"R_1 = \frac{wL}{2}")
            st.markdown(f"Numerically, R₁ = R₂ = `{R:.3g}` kN")

        elif case == "Simple beam – partial UDL from left (length a)":
            w = params["w"]
            a = params["a_udl"]
            a = max(0.0, min(a, L))
            R1 = results["R1"]
            R2 = results["R2"]
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
            R1 = results["R1"]
            R2 = results["R2"]
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
            RA = results["RA"]
            RB = results["RB"]
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
    Standalone SFD/BMD teaching page in the main beam app.

    - No set_page_config, no sidebar
    - Follows same styling helpers as other pages
    - Publishes span + |M|max to results via update_results(...)
      so Deflection page can read sfd_span_L_m and sfd_Mmax_abs_kNm.
    """
    apply_global_widget_css()
    apply_calcbox_css()
    sync_callbacks = get_sync_callbacks()

    st.title("Shear and Bending Moment Diagrams")

    st.markdown(
        """
Interactive teaching module for classic statically determinate beams.

**Sign convention (for diagrams):**
- Shear \(V(x)\): **upward positive**
- Bending moment \(M(x)\): **sagging positive** (cantilever hogging will appear negative)
"""
    )

    # ---------------------------------------------------
    # Layout: Inputs vs key formulas
    # ---------------------------------------------------
    col_inputs, col_formulas = st.columns([1.3, 1.0])

    with col_inputs:
        st.markdown("#### Beam & loading")

        case = st.selectbox(
            "Loading case",
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
            key="sfd_case",
        )

        params = {}
        results = {}

        # Length inputs
        if case == "Overhanging beam – right overhang with point load at free end":
            L_main = st.number_input(
                "Span between supports L (m)",
                min_value=0.1, value=4.0, step=0.5, key="sfd_L_main"
            )
            a_over = st.number_input(
                "Overhang length a (m)",
                min_value=0.0, value=2.0, step=0.5, key="sfd_a_overhang"
            )
            L = L_main + a_over  # total for plotting
            params["L_main"] = L_main
            params["a_overhang"] = a_over
        else:
            L = st.number_input(
                "Span L (m)",
                min_value=0.1, value=6.0, step=0.5, key="sfd_L"
            )

        # Load inputs
        if case in [
            "Simple beam – UDL over entire span",
            "Simple beam – partial UDL from left (length a)",
            "Cantilever – UDL over entire span",
        ]:
            default_w = 20.0 if "Simple beam" in case else 10.0
            params["w"] = st.number_input(
                "UDL w (kN/m)",
                min_value=0.0, value=default_w, step=1.0, key="sfd_w"
            )

        if case in [
            "Simple beam – point load at centre",
            "Simple beam – point load at distance a from left",
            "Cantilever – point load at free end",
            "Cantilever – point load at distance a from fixed end",
            "Overhanging beam – right overhang with point load at free end",
        ]:
            default_P = 100.0 if "Simple beam" in case else 50.0
            params["P"] = st.number_input(
                "Point load P (kN)",
                min_value=0.0, value=default_P, step=5.0, key="sfd_P"
            )

        if case == "Simple beam – point load at distance a from left":
            params["a"] = st.number_input(
                "Distance a from left support (m)",
                min_value=0.0, value=L / 3, step=0.1, key="sfd_a"
            )

        if case == "Simple beam – partial UDL from left (length a)":
            params["a_udl"] = st.number_input(
                "UDL length a from left (m)",
                min_value=0.0, value=L / 2, step=0.1, key="sfd_a_udl"
            )

        if case == "Cantilever – point load at distance a from fixed end":
            params["a_cant"] = st.number_input(
                "Distance a from fixed end (m)",
                min_value=0.0, value=L / 2, step=0.1, key="sfd_a_cant"
            )

    # ---------------------------------------------------
    # Compute V(x) and M(x) by case
    # ---------------------------------------------------
    x = None
    V = None
    M = None
    beam_length = L
    M_max_abs = 0.0

    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        x = np.linspace(0, L, 400)
        R = w * L / 2.0
        V = R - w * x
        M = R * x - 0.5 * w * x**2
        results["R"] = R
        M_max_abs = float(np.max(np.abs(M)))

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
        results["R1"] = R1
        results["R2"] = R2
        M_max_abs = float(np.max(np.abs(M)))

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
        results["R1"] = R1
        results["R2"] = R2
        M_max_abs = float(np.max(np.abs(M)))

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a = float(params["a"])
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
        results["R1"] = R1
        results["R2"] = R2
        M_max_abs = float(np.max(np.abs(M)))

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        x = np.linspace(0, L, 400)
        V = -P * np.ones_like(x)
        M = -P * (L - x)
        M_max_abs = float(np.max(np.abs(M)))

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
        M_max_abs = float(np.max(np.abs(M)))

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        x = np.linspace(0, L, 400)
        V = -w * (L - x)
        M = -0.5 * w * (L - x) ** 2
        M_max_abs = float(np.max(np.abs(M)))

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
        results["RA"] = RA
        results["RB"] = RB
        M_max_abs = float(np.max(np.abs(M)))

    # ---------------------------------------------------
    # Key formulas + publish to results
    # ---------------------------------------------------
    with col_formulas:
        st.markdown("#### Key formulas")

        if case == "Simple beam – UDL over entire span":
            st.latex(r"R_1 = R_2 = \frac{wL}{2}")
            st.latex(r"V(x) = R_1 - wx")
            st.latex(r"M(x) = R_1 x - \frac{w x^2}{2}")

        elif case == "Simple beam – partial UDL from left (length a)":
            st.latex(r"R_2 = \dfrac{w a^2}{2L}, \quad R_1 = w a - R_2")
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 - w x & 0 \le x \le a \\"
                r"R_1 - w a & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x - \dfrac{w x^2}{2} & 0 \le x \le a \\[6pt]"
                r"R_1 x - w a\left(x - \dfrac{a}{2}\right) & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at centre":
            st.latex(r"a = \frac{L}{2}, \quad R_1 = R_2 = \frac{P}{2}")
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 & 0 \le x < a \\"
                r"R_1 - P & a < x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x & 0 \le x \le a \\"
                r"R_1 x - P(x-a) & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at distance a from left":
            st.latex(r"b = L-a,\quad R_1 = \frac{Pb}{L},\; R_2 = \frac{Pa}{L}")
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 & 0 \le x < a \\"
                r"R_1 - P & a < x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x & 0 \le x \le a \\"
                r"R_1 x - P(x-a) & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Cantilever – point load at free end":
            st.latex(r"V(x) = -P,\quad 0 \le x \le L")
            st.latex(r"M(x) = -P(L-x)")

        elif case == "Cantilever – point load at distance a from fixed end":
            st.latex(
                r"V(x) = \begin{cases}"
                r"-P & 0 \le x \le a \\"
                r"0 & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M(x) = \begin{cases}"
                r"-P(a-x) & 0 \le x \le a \\"
                r"0 & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Cantilever – UDL over entire span":
            st.latex(r"V(x) = -w(L-x),\quad 0 \le x \le L")
            st.latex(r"M(x) = -\frac{w}{2}(L-x)^2")

        elif case == "Overhanging beam – right overhang with point load at free end":
            st.latex(r"\text{Span between supports} = L,\quad \text{overhang} = a")
            st.latex(r"R_A = -\frac{Pa}{L},\quad R_B = \frac{P(L+a)}{L}")
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_A & 0 \le x < L \\"
                r"R_A + R_B & L < x \le L+a"
                r"\end{cases}"
            )
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_A x & 0 \le x \le L \\"
                r"R_A x + R_B(x-L) & L \le x \le L+a"
                r"\end{cases}"
            )

        st.markdown(f"**Maximum bending moment (|M|)** ≈ `{M_max_abs:.3g}` kNm")

        # Push into shared results so the Deflection page can use it
        update_results(
            {
                "sfd_case": case,
                "sfd_span_L_m": float(L),
                "sfd_Mmax_abs_kNm": float(M_max_abs),
            }
        )
        st.caption(
            "These values are now available to the Deflection page as "
            "`sfd_span_L_m` and `sfd_Mmax_abs_kNm` in results."
        )

    # ---------------------------------------------------
    # Load diagram + derivation
    # ---------------------------------------------------
    st.markdown("---")
    col_load, col_deriv = st.columns([1.2, 1.0])

    with col_load:
        st.subheader("Load diagram (with support types)")
        fig_load = plot_load_diagram(case, beam_length, params)
        st.pyplot(fig_load)

    with col_deriv:
        render_derivation(case, L, params, results)

    # ---------------------------------------------------
    # Show SFD & BMD
    # ---------------------------------------------------
    st.markdown("---")
    st.subheader("Shear Force and Bending Moment Diagrams")

    fig_sfd, fig_bmd = plot_sfd_bmd(x, V, M)
    col_sfd, col_bmd = st.columns(2)

    with col_sfd:
        st.pyplot(fig_sfd)

    with col_bmd:
        st.pyplot(fig_bmd)
