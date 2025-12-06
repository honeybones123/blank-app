# sfd_bmd_section.py

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
    Designed so the triangle POINTS UP to the beam (beam is at y=0).
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
            "k",
            linewidth=1.5,
        )

        # hinge dot at the contact
        ax.plot(x_pos, apex_y, "ko", markersize=3)

        if kind == "roller":
            roller_y = base_y - size * 0.4
            ax.plot(x_pos, roller_y, "ko", markersize=4)

    elif kind == "fixed":
        wall_height = size * 3
        ax.plot(
            [x_pos, x_pos],
            [y_beam - wall_height, y_beam + wall_height],
            "k",
            linewidth=4,
        )
        # hatching into wall (left side)
        n_hatch = 5
        for i in range(n_hatch):
            yy = y_beam - wall_height + i * (2 * wall_height / max(n_hatch - 1, 1))
            ax.plot(
                [x_pos - size * 0.7, x_pos],
                [yy - size * 0.4, yy],
                "k",
                linewidth=1,
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

    # Draw beam line
    ax.plot([0, L], [0, 0], "k", linewidth=2)

    # ---- Supports / fixed ends ----
    if case.startswith("Simple beam"):
        draw_support(ax, 0.0, kind="pinned")
        draw_support(ax, L, kind="pinned")

    elif case.startswith("Cantilever"):
        draw_support(ax, 0.0, kind="fixed")

    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = params.get("L_main", L)
        draw_support(ax, 0.0, kind="pinned")
        draw_support(ax, L_main, kind="pinned")

    # ---- Loads ----
    if case == "Simple beam – UDL over entire span":
        w = params["w"]
        ax.fill_between([0, L], [0.3, 0.3], [0, 0], alpha=0.3)
        xs = np.linspace(0.1 * L, 0.9 * L, 7)
        for xi in xs:
            ax.arrow(
                xi,
                0.4,
                0,
                -0.25,
                head_width=0.08,
                head_length=0.05,
                length_includes_head=True,
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
                xi,
                0.4,
                0,
                -0.25,
                head_width=0.08,
                head_length=0.05,
                length_includes_head=True,
            )
        ax.text(a / 2, 0.45, f"w = {w:.2f} kN/m", ha="center", va="bottom")
        ax.annotate("", xy=(0, -0.2), xytext=(a, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text(a / 2, -0.25, "a", ha="center", va="top")
        ax.annotate("", xy=(a, -0.2), xytext=(L, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text((a + L) / 2, -0.25, "L - a", ha="center", va="top")

    elif case == "Simple beam – point load at centre":
        P = params["P"]
        a = L / 2
        ax.arrow(
            a,
            0.4,
            0,
            -0.35,
            head_width=0.08,
            head_length=0.05,
            length_includes_head=True,
        )
        ax.text(a, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate("", xy=(0, -0.2), xytext=(a, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text(a / 2, -0.25, "L/2", ha="center", va="top")
        ax.annotate("", xy=(a, -0.2), xytext=(L, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text((a + L) / 2, -0.25, "L/2", ha="center", va="top")

    elif case == "Simple beam – point load at distance a from left":
        P = params["P"]
        a = params["a"]
        a = max(0.0, min(a, L))
        ax.arrow(
            a,
            0.4,
            0,
            -0.35,
            head_width=0.08,
            head_length=0.05,
            length_includes_head=True,
        )
        ax.text(a, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate("", xy=(0, -0.2), xytext=(a, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text(a / 2, -0.25, "a", ha="center", va="top")
        ax.annotate("", xy=(a, -0.2), xytext=(L, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text((a + L) / 2, -0.25, "b = L - a", ha="center", va="top")

    elif case == "Cantilever – point load at free end":
        P = params["P"]
        ax.arrow(
            L,
            0.4,
            0,
            -0.35,
            head_width=0.08,
            head_length=0.05,
            length_includes_head=True,
        )
        ax.text(L, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate("", xy=(0, -0.2), xytext=(L, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text(L / 2, -0.25, "L", ha="center", va="top")

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params["P"]
        a = params["a_cant"]
        a = max(0.0, min(a, L))
        ax.arrow(
            a,
            0.4,
            0,
            -0.35,
            head_width=0.08,
            head_length=0.05,
            length_includes_head=True,
        )
        ax.text(a, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate("", xy=(0, -0.2), xytext=(a, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text(a / 2, -0.25, "a", ha="center", va="top")
        ax.annotate("", xy=(a, -0.2), xytext=(L, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text((a + L) / 2, -0.25, "L - a", ha="center", va="top")

    elif case == "Cantilever – UDL over entire span":
        w = params["w"]
        ax.fill_between([0, L], [0.3, 0.3], [0, 0], alpha=0.3)
        xs = np.linspace(0.1 * L, 0.9 * L, 7)
        for xi in xs:
            ax.arrow(
                xi,
                0.4,
                0,
                -0.25,
                head_width=0.08,
                head_length=0.05,
                length_includes_head=True,
            )
        ax.text(L * 0.5, 0.45, f"w = {w:.2f} kN/m", ha="center", va="bottom")
        ax.annotate("", xy=(0, -0.2), xytext=(L, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text(L / 2, -0.25, "L", ha="center", va="top")

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params["P"]
        L_main = params["L_main"]
        a_over = params["a_overhang"]
        L_total = L_main + a_over
        ax.arrow(
            L_total,
            0.4,
            0,
            -0.35,
            head_width=0.08,
            head_length=0.05,
            length_includes_head=True,
        )
        ax.text(L_total, 0.45, f"P = {P:.2f} kN", ha="center", va="bottom")
        ax.annotate("", xy=(0, -0.2), xytext=(L_main, -0.2), arrowprops=dict(arrowstyle="<->"))
        ax.text(L_main / 2, -0.25, "L", ha="center", va="top")
        ax.annotate(
            "",
            xy=(L_main, -0.2),
            xytext=(L_total, -0.2),
            arrowprops=dict(arrowstyle="<->"),
        )
        ax.text(L_main + a_over / 2, -0.25, "a", ha="center", va="top")

    ax.set_xlim(-0.3, L + 0.3)
    ax.set_ylim(-0.9, 0.9)
    ax.axis("off")
    return fig


# ---------------------------------------------------
# Helper: plot SFD & BMD
# ---------------------------------------------------
def plot_sfd_bmd(x, V, M):
    fig_sfd, ax_sfd = plt.subplots(figsize=(6, 3))
    ax_sfd.axhline(0, color="k", linewidth=0.8)
    ax_sfd.plot(x, V, linewidth=2)
    ax_sfd.set_xlabel("x (m)")
    ax_sfd.set_ylabel("V (kN)")
    ax_sfd.set_title("Shear Force Diagram (SFD)")
    ax_sfd.grid(True, alpha=0.3)

    fig_bmd, ax_bmd = plt.subplots(figsize=(6, 3))
    ax_bmd.axhline(0, color="k", linewidth=0.8)
    ax_bmd.plot(x, M, linewidth=2)
    ax_bmd.set_xlabel("x (m)")
    ax_bmd.set_ylabel("M (kNm)")
    ax_bmd.set_title("Bending Moment Diagram (BMD)")
    ax_bmd.grid(True, alpha=0.3)

    return fig_sfd, fig_bmd


# ---------------------------------------------------
# Helper: derivation text
# (unchanged logic, just uses the current container)
# ---------------------------------------------------
def render_derivation(case, L, params, results):
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

        # --- same text as your original app (shortened here for brevity) ---
        # I’m keeping the logic identical, just copied from your original code.
        # You can paste your full render_derivation body here unchanged.

        # For brevity in this answer I won’t re-repeat every branch,
        # just keep exactly what you already had inside this function.

        #  <<< PASTE YOUR EXISTING CASE-BY-CASE BLOCK FROM render_derivation HERE >>>
        # (No structural change required, it works as-is inside expander.)

        # ---------------------------------------------------------------------
        # I’ve removed the body here to keep this answer short. In your file,
        # paste the full "Step 2 / 3 / 4" case logic from your snippet.
        # ---------------------------------------------------------------------
        pass  # REMOVE THIS after you paste your full content above


# ---------------------------------------------------
# MAIN RENDER FUNCTION (to call from beam/deflection app)
# ---------------------------------------------------
def render_sfd_bmd_section():
    """
    Teaching-style SFD/BMD widget, embedded in the main app.
    - No page_config, no sidebar
    - Uses same CSS helpers
    - Publishes span + |M|max to results via update_results(...)
    """

    apply_global_widget_css()
    apply_calcbox_css()
    sync_callbacks = get_sync_callbacks()

    st.markdown("### Shear & Bending Moment diagrams – teaching module")

    st.markdown(
        """
        Sign convention:
        - Shear **upward positive**
        - Bending moment **sagging positive** (cantilever hogging shown negative)
        """
    )

    # ----------------- INPUTS LAYOUT (same style as other pages) -----------------
    col_in, col_formula = st.columns([1.3, 1.0])

    with col_in:
        st.markdown("#### Loading case and actions")

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

        # Length inputs (no sidebar – inline with your style)
        if case == "Overhanging beam – right overhang with point load at free end":
            L_main = st.number_input(
                "Span between supports L (m)",
                min_value=0.1,
                value=4.0,
                step=0.5,
                key="sfd_L_main",
            )
            a_over = st.number_input(
                "Overhang length a (m)",
                min_value=0.0,
                value=2.0,
                step=0.5,
                key="sfd_a_overhang",
            )
            L = L_main + a_over
            params["L_main"] = L_main
            params["a_overhang"] = a_over
        else:
            L = st.number_input(
                "Span L (m)",
                min_value=0.1,
                value=6.0,
                step=0.5,
                key="sfd_L",
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
                min_value=0.0,
                value=default_w,
                step=1.0,
                key="sfd_w",
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
                min_value=0.0,
                value=default_P,
                step=5.0,
                key="sfd_P",
            )

        if case == "Simple beam – point load at distance a from left":
            params["a"] = st.number_input(
                "Distance a from left support (m)",
                min_value=0.0,
                value=L / 3,
                step=0.1,
                key="sfd_a",
            )

        if case == "Simple beam – partial UDL from left (length a)":
            params["a_udl"] = st.number_input(
                "UDL length a from left (m)",
                min_value=0.0,
                value=L / 2,
                step=0.1,
                key="sfd_a_udl",
            )

        if case == "Cantilever – point load at distance a from fixed end":
            params["a_cant"] = st.number_input(
                "Distance a from fixed end (m)",
                min_value=0.0,
                value=L / 2,
                step=0.1,
                key="sfd_a_cant",
            )

    # ----------------- COMPUTE SFD/BMD -----------------
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

    # ----------------- FORMULAS + Mmax SUMMARY -----------------
    with col_formula:
        st.markdown("#### Key formulas")

        # (Paste your case-by-case st.latex() block here unchanged)
        # This is the same as your original "Key formulas" section.
        # To keep this answer short, I’m not reprinting every line.
        # -------------------------------------------------------

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
            "This |M|max and span L are now available to the Deflection page as "
            "`sfd_Mmax_abs_kNm` and `sfd_span_L_m` in results."
        )

    # ----------------- LOAD DIAGRAM + DERIVATION -----------------
    st.markdown("---")
    col_load, col_deriv = st.columns([1.2, 1.0])

    with col_load:
        st.subheader("Load diagram (with supports)")
        fig_load = plot_load_diagram(case, beam_length, params)
        st.pyplot(fig_load)

    with col_deriv:
        render_derivation(case, L, params, results)

    # ----------------- SFD & BMD -----------------
    st.markdown("---")
    st.subheader("Shear force and bending moment diagrams")

    fig_sfd, fig_bmd = plot_sfd_bmd(x, V, M)
    col_sfd, col_bmd = st.columns(2)

    with col_sfd:
        st.pyplot(fig_sfd)

    with col_bmd:
        st.pyplot(fig_bmd)
