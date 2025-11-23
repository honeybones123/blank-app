import math
import pandas as pd
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
)

# One shared callbacks dict for all widgets
_sync = get_sync_callbacks()


def _crack_limit_for_exposure(exposure: str) -> float:
    """
    Map exposure class to allowable crack width (mm).
    Adjust as needed to match your AS 3600 tables.
    """
    exposure = (exposure or "").upper()
    limits = {
        "A1": 0.30,
        "A2": 0.30,
        "B1": 0.25,
        "B2": 0.20,
        "C": 0.20,
        "U": 0.10,
    }
    return limits.get(exposure, 0.20)


def render_crack_control():
    st.title("Crack Control (Flexural)")

    st.markdown(
        """
        This page checks **flexural crack width** at SLS using shared
        geometry, materials and reinforcement plus:

        - Exposure classification (A1, A2, B1, B2, C, U)  
        - Bottom bar spacing for crack calculations  

        Results are pushed back to shared state via `update_results()` as:

        - `crack_width` (mm)  
        - `crack_utilisation` (w / w_lim)
        """
    )

    st.markdown("---")

    # --------------------------------------------------
    # INPUTS (linked to shared via TAB_KEYS + sync callbacks)
    # --------------------------------------------------
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Geometry & materials (shared)")

        st.number_input(
            "b – width (mm)",
            min_value=100.0,
            max_value=3000.0,
            value=float(get_param("b", 400.0)),
            step=10.0,
            key="crack_b",
            on_change=_sync["crack_b"],
        )

        st.number_input(
            "D – overall depth (mm)",
            min_value=100.0,
            max_value=3000.0,
            value=float(get_param("D", 600.0)),
            step=10.0,
            key="crack_D",
            on_change=_sync["crack_D"],
        )

        st.number_input(
            "L – span (mm)",
            min_value=1000.0,
            max_value=30000.0,
            value=float(get_param("L", 3000.0)),
            step=100.0,
            key="crack_L",
            on_change=_sync["crack_L"],
        )

        st.number_input(
            "f'c – concrete strength (MPa)",
            min_value=20.0,
            max_value=80.0,
            value=float(get_param("fc", 40.0)),
            step=1.0,
            key="crack_fc",
            on_change=_sync["crack_fc"],
        )

        st.number_input(
            "fsy – steel yield (MPa)",
            min_value=300.0,
            max_value=600.0,
            value=float(get_param("fsy", 500.0)),
            step=10.0,
            key="crack_fsy",
            on_change=_sync["crack_fsy"],
        )

        st.number_input(
            "Ec – concrete modulus (MPa)",
            min_value=15000.0,
            max_value=45000.0,
            value=float(get_param("Ec", 30000.0)),
            step=500.0,
            key="crack_Ec",
            on_change=_sync["crack_Ec"],
        )

        st.number_input(
            "Es – steel modulus (MPa)",
            min_value=150000.0,
            max_value=220000.0,
            value=float(get_param("Es", 200000.0)),
            step=5000.0,
            key="crack_Es",
            on_change=_sync["crack_Es"],
        )

        st.number_input(
            "Service moment M* (kNm)",
            min_value=0.0,
            max_value=5000.0,
            value=float(get_param("Mu_star", 500.0)),
            step=10.0,
            key="crack_Mu_star",
            on_change=_sync["crack_Mu_star"],
        )

    with col_right:
        st.subheader("Reinforcement & crack inputs")

        st.number_input(
            "Bottom bars – number",
            min_value=1,
            max_value=20,
            value=int(get_param("nb_bot", 4)),
            step=1,
            key="crack_nb_bot",
            on_change=_sync["crack_nb_bot"],
        )

        st.number_input(
            "Bottom bar diameter db,bot (mm)",
            min_value=8.0,
            max_value=40.0,
            value=float(get_param("db_bot", 20.0)),
            step=1.0,
            key="crack_db_bot",
            on_change=_sync["crack_db_bot"],
        )

        st.number_input(
            "Top bars – number",
            min_value=0,
            max_value=20,
            value=int(get_param("nb_top", 2)),
            step=1,
            key="crack_nb_top",
            on_change=_sync["crack_nb_top"],
        )

        st.number_input(
            "Top bar diameter db,top (mm)",
            min_value=8.0,
            max_value=40.0,
            value=float(get_param("db_top", 16.0)),
            step=1.0,
            key="crack_db_top",
            on_change=_sync["crack_db_top"],
        )

        st.number_input(
            "Bottom cover to bar (mm)",
            min_value=15.0,
            max_value=100.0,
            value=float(get_param("cover_bot", 40.0)),
            step=5.0,
            key="crack_cover_bot",
            on_change=_sync["crack_cover_bot"],
        )

        st.number_input(
            "Top cover to bar (mm)",
            min_value=15.0,
            max_value=100.0,
            value=float(get_param("cover_top", 40.0)),
            step=5.0,
            key="crack_cover_top",
            on_change=_sync["crack_cover_top"],
        )

        exposure_default = str(get_param("exposure_class", "B1")).upper()
        options = ["A1", "A2", "B1", "B2", "C", "U"]
        if exposure_default not in options:
            exposure_default = "B1"

        exposure = st.selectbox(
            "Exposure classification",
            options=options,
            index=options.index(exposure_default),
            key="crack_exposure_class",
            on_change=_sync["crack_exposure_class"],
        )

        st.number_input(
            "Bottom bar spacing s (mm)",
            min_value=50.0,
            max_value=400.0,
            value=float(get_param("s_bar_bot", 200.0)),
            step=10.0,
            key="crack_s_bar_bot",
            on_change=_sync["crack_s_bar_bot"],
        )

    st.markdown("---")

    # --------------------------------------------------
    # CALCULATIONS (read from shared state via get_param)
    # --------------------------------------------------
    b = get_param("b", 400.0)
    D = get_param("D", 600.0)
    d = get_param("d", D - get_param("cover_bot", 40.0) - get_param("db_bot", 20.0) / 2.0)

    Mu_star = get_param("Mu_star", 500.0)  # kNm (treated as SLS here)
    Es = get_param("Es", 200000.0)

    nb_bot = get_param("nb_bot", 4)
    db_bot = get_param("db_bot", 20.0)
    Ast_bot = get_param("Ast_bot", nb_bot * math.pi * db_bot**2 / 4.0)

    cover_bot = get_param("cover_bot", 40.0)
    s_bar = get_param("s_bar_bot", 200.0)

    exposure_class = get_param("exposure_class", exposure_default)
    w_lim = _crack_limit_for_exposure(exposure_class)

    # Steel stress at SLS from simple rectangular cracked section
    M_Nmm = Mu_star * 1e6
    z = 0.9 * d if d > 0 else 1.0
    T_s = M_Nmm / z if z > 0 else 0.0
    f_s = T_s / Ast_bot if Ast_bot > 0 else 0.0  # MPa

    eps_s = f_s / Es if Es > 0 else 0.0

    # Shrinkage strain from Shrinkage page (if present)
    eps_sh_micro = st.session_state.get("shrinkage_eps_design", 0.0)
    eps_sh = eps_sh_micro / 1e6

    # Effective spacing (very rough)
    s_eff = min(2.5 * cover_bot + 0.5 * s_bar, 2.0 * s_bar)

    # Crack widths
    k_t = 0.5
    eps_eff_long = max(0.0, eps_s + k_t * eps_sh)

    w_long = eps_eff_long * s_eff  # mm

    utilisation = w_long / w_lim if w_lim > 0 else 0.0

    # --------------------------------------------------
    # Write results
    # --------------------------------------------------
    update_results(
        crack_width=w_long,
        crack_utilisation=utilisation,
    )

    # --------------------------------------------------
    # Summary table
    # --------------------------------------------------
    st.subheader("Crack Control Summary")

    data = {
        "Quantity": [
            "Exposure class",
            "Crack width limit w_lim",
            "Steel stress f_s",
            "Steel strain ε_s",
            "Shrinkage strain ε_sh",
            "Effective spacing s_eff",
            "Long-term crack width w",
            "Utilisation w / w_lim",
        ],
        "Value": [
            exposure_class,
            f"{w_lim:.3f} mm",
            f"{f_s:.1f} MPa",
            f"{eps_s*1e3:.3f} ‰",
            f"{eps_sh*1e3:.3f} ‰",
            f"{s_eff:.1f} mm",
            f"{w_long:.3f} mm",
            f"{utilisation:.2f}",
        ],
    }
    df = pd.DataFrame(data)
    st.table(df)

    st.markdown(
        """
        Notes:
        - This is a simplified teaching model, not a literal AS 3600 implementation.
        - You can adjust the crack-width formula and w_lim values to match your own sheet.
        """
    )
