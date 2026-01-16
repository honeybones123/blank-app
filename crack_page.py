# crack_page.py
# ============================
# CRACK WIDTH – AS 3600:2018 Cl. 8.6.2
# ============================

import math
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
    get_widget_key_for_shared,
    TAB_KEYS,
)
from widgets_helpers import apply_global_widget_css, number_row, calcbox, render_jumpable_step, apply_step_summary_expander_css, page_divider, show_reo_message, label_with_hover, select_row, seed_widget_from_shared
from ui_seamless_steps import inject_seamless_steps_css, render_clickable_summary_table, bind_summary_clicks

# Safe option lists for reinforcement inputs (same as inputs_page)
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))  # 0..12 inclusive
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


# ------------------------------------------------------------
#  Small helpers / shared styling (same pattern as creep/shrinkage)
# ------------------------------------------------------------
def _seed_from_param(name: str, fallback: float) -> float:
    """Seed default widget values from shared state, with safe fallback."""
    try:
        v = get_param(name)
    except TypeError:
        v = None

    try:
        if v is None:
            return float(fallback)
        v = float(v)
        if math.isnan(v):
            return float(fallback)
        return v
    except Exception:
        return float(fallback)


def _get_bottom_bar_diameter():
    """
    Get bottom bar diameter from session state.
    Prefer Layer 1, fall back to Layer 2 if Layer 1 is absent.
    Returns None if no bottom reinforcement is defined.
    """
    # Prefer Layer 1
    if st.session_state.get("nb_or_s_bot_1", 0.0) > 0:
        return float(st.session_state.get("db_bot_1", 20.0))
    # Fall back to Layer 2
    if st.session_state.get("nb_or_s_bot_2", 0.0) > 0:
        return float(st.session_state.get("db_bot_2", 20.0))
    # Fall back to derived db_bot
    db_bot = st.session_state.get("db_bot")
    if db_bot is not None and db_bot > 0:
        return float(db_bot)
    return None


def _get_bottom_bar_count():
    """
    Get total bottom bar count from session state.
    Returns None if no bottom reinforcement is defined.
    """
    nb_bot = st.session_state.get("nb_bot")
    if nb_bot is not None and nb_bot > 0:
        return int(nb_bot)
    return None


def _get_bottom_spacing():
    """
    Get bottom bar spacing from session state (derived from layout).
    Returns None if spacing is not available (e.g., single bar).
    """
    s_bot = st.session_state.get("s_bot")
    if s_bot is not None and s_bot > 0:
        return float(s_bot)
    return None


def _col_heading(text: str):
    """Consistent column heading style."""
    st.markdown(f"### {text}")
    st.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)


def _render_readonly_value(label: str, value, unit: str, help_text: str | None = None):
    """
    Render a read-only value with label and optional help text.
    Uses the same styling as other read-only inputs.
    """
    col1, col2 = st.columns([1, 2])
    with col1:
        label_with_hover(label, help_text)
    with col2:
        if value is None:
            display_value = "—"
            color_style = "color: #999;"
        else:
            if isinstance(value, float):
                if unit == "mm":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "mm²":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "MPa":
                    display_value = f"{value:.2f} {unit}"
                else:
                    display_value = f"{value:.1f} {unit}"
            else:
                display_value = f"{value} {unit}" if unit else str(value)
            color_style = ""
        
        st.markdown(
            f"""
<div class="readonly-param" style="padding: 0.5rem 0.75rem; margin: 0;">
  <div class="readonly-param-value" style="font-size: 1rem; margin: 0; {color_style}">{display_value}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _inject_calcbox_css():
    """Style markdown blockquotes & readonly chips (same feel as shear/deflection)."""
    st.markdown(
        """
<style>
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 0.35rem 0.35rem 0 !important;
  color: #1a1a1a !important;
  opacity: 1 !important;
  font-size: 0.9rem !important;
  line-height: 1.35 !important;
}
blockquote * {
  color: #1a1a1a !important;
  opacity: 1 !important;
}
blockquote p {
  margin-bottom: 0.5rem !important;
}
blockquote p:last-child {
  margin-bottom: 0 !important;
}

/* Read-only linked-parameter chips */
.readonly-param {
  border-left: 4px solid #6c757d;
  background-color: rgba(108, 117, 125, 0.08);
  padding: 0.4rem 0.6rem;
  margin-bottom: 0.4rem;
  border-radius: 0 0.35rem 0.35rem 0;
  font-size: 0.85rem;
}
.readonly-param-title {
  font-weight: 600;
}
.readonly-param-value {
  font-weight: 500;
}
.readonly-param-source {
  font-size: 0.78rem;
  opacity: 0.8;
}
</style>
""",
        unsafe_allow_html=True,
    )




# ------------------------------------------------------------
#  Tables – AS 3600:2018 8.6.2.2(A) & (B)
# ------------------------------------------------------------
# TABLE 8.6.2.2(A) – Maximum steel stress for tension or flexure
# Structure: {db_mm: {wmax_mm: sigma_max_MPa}}
_TABLE_8_6_2_2A = {
    10: {0.2: 190, 0.3: 265, 0.4: 335},
    12: {0.2: 175, 0.3: 245, 0.4: 305},
    16: {0.2: 155, 0.3: 215, 0.4: 270},
    20: {0.2: 140, 0.3: 195, 0.4: 240},
    24: {0.2: 125, 0.3: 175, 0.4: 215},
    28: {0.2: 115, 0.3: 160, 0.4: 200},
    32: {0.2: 105, 0.3: 150, 0.4: 185},
    36: {0.2: 100, 0.3: 140, 0.4: 175},
    40: {0.2: 90,  0.3: 130, 0.4: 165},
}

# TABLE 8.6.2.2(B) – Maximum steel stress for flexure vs spacing
# Structure: {spacing_mm: {wmax_mm: sigma_max_MPa}}
_TABLE_8_6_2_2B = {
    50:  {0.2: 200, 0.3: 300, 0.4: 400},
    100: {0.2: 170, 0.3: 270, 0.4: 360},
    150: {0.2: 155, 0.3: 245, 0.4: 330},
    200: {0.2: 145, 0.3: 225, 0.4: 300},
    250: {0.2: 135, 0.3: 210, 0.4: 280},
    300: {0.2: 125, 0.3: 200, 0.4: 260},
}


def _nearest_key(mapping: dict, value: float) -> int:
    """Return integer key in mapping closest to value."""
    keys = sorted(mapping.keys())
    return min(keys, key=lambda k: abs(k - value))


def table_sigma_max_A(db_mm: float, wmax_mm: float) -> float:
    """Lookup σ_s,max from Table 8.6.2.2(A) (nearest db, w'max)."""
    wopt = min([0.2, 0.3, 0.4], key=lambda x: abs(x - wmax_mm))
    db_key = _nearest_key(_TABLE_8_6_2_2A, db_mm)
    return _TABLE_8_6_2_2A[db_key][wopt]


def table_sigma_max_B(spacing_mm: float, wmax_mm: float) -> float:
    """Lookup σ_s,max from Table 8.6.2.2(B) (nearest spacing, w'max)."""
    wopt = min([0.2, 0.3, 0.4], key=lambda x: abs(x - wmax_mm))
    s_key = _nearest_key(_TABLE_8_6_2_2B, spacing_mm)
    return _TABLE_8_6_2_2B[s_key][wopt]


# ------------------------------------------------------------
#  Direct calculation helpers – 8.6.2.3
# ------------------------------------------------------------
def calc_eps_diff(
    sigma_sr: float,
    Es: float,
    fct_eff: float,
    rho_eff: float,
    ne: float,
    eps_cs: float,
) -> float:
    """
    ε_sm − ε_cm from 8.6.2.3(2):

      ε_sm − ε_cm = σ_sr / Es − 0.6 f_ct,eff / (Es ρ_eff) (1 + n_e ρ_eff) + ε_cs
                  ≥ 0.6 σ_sr / Es

    All strains are dimensionless.
    """
    if rho_eff <= 0:
        return 0.0

    term1 = sigma_sr / Es
    term2 = 0.6 * fct_eff / (Es * rho_eff) * (1.0 + ne * rho_eff)
    eps_diff = term1 - term2 + eps_cs

    # Lower bound 0.6 σ_sr / Es
    eps_min = 0.6 * sigma_sr / Es
    return max(eps_diff, eps_min)


def calc_sr_max(c_mm: float, db_mm: float, rho_eff: float, k1: float, k2: float) -> float:
    """
    Maximum crack spacing  s_r,max  from 8.6.2.3(3):

        s_r,max = 3.4 c + 0.3 k1 k2 d_b / ρ_eff

    Returns s_r,max in mm.
    """
    if rho_eff <= 0:
        return 0.0
    return 3.4 * c_mm + 0.3 * k1 * k2 * db_mm / rho_eff


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_crack():
    # Hydrate widget keys from shared BEFORE rendering widgets (prevents 0/default after restore)
    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()
    
    apply_global_widget_css()
    _inject_calcbox_css()
    apply_step_summary_expander_css()
    inject_seamless_steps_css()
    sync_callbacks = get_sync_callbacks()  # keeps contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    st.title("Crack width – AS 3600:2018")

    # --------------------------------------------------------
    # Page description (directly under title)
    # --------------------------------------------------------
    st.markdown(
        """
This page checks flexural crack control in reinforced concrete beams in accordance with **AS 3600:2018 Clause 8.6.2**, using:

- **Table method (no direct crack width)** — limiting steel stress from Tables 8.6.2.2(A)–(B)
- **Direct crack-width calculation** — per Clause 8.6.2.3:
"""
    )
    
    st.latex(r"w = s_{r,\max}\left(\varepsilon_{sm}-\varepsilon_{cm}\right)\le w'_{\max}")
    
    st.markdown(
        """
The aim is to verify that cracking is **controlled** so that durability and appearance are not impaired.
"""
    )

    # --------------------------------------------------------
    # Reserve space for top summary (will be filled after calculations)
    # --------------------------------------------------------
    summary_placeholder = st.empty()

    # --------------------------------------------------------
    # Inputs
    # --------------------------------------------------------
    page_divider()

    # Top row: 3 columns
    top_c1, top_c2, top_c3 = st.columns(3, gap="large")

    # --- Materials & Geometry ---
    with top_c1:
        _col_heading("Materials & Geometry")
        
        # Materials first
        fc_seed = _seed_from_param("fc", 32.0)
        Ec_seed = _seed_from_param("Ec", 30000.0)

        fc = number_row(
            "Concrete strength f'c (MPa)",
            "crack_fc",
            fc_seed,
            sync_callbacks,
            help_text="Characteristic compressive strength of concrete at 28 days.",
        )
        Ec = number_row(
            "Concrete modulus E_c (MPa)",
            "crack_Ec",
            Ec_seed,
            sync_callbacks,
            help_text="Elastic modulus of concrete (E_c), typically calculated from f'c per AS 3600.",
        )
        Es = number_row(
            "Steel modulus E_s (MPa)",
            "crack_Es",
            200000.0,
            sync_callbacks,
            help_text="Elastic modulus of reinforcing steel (E_s), typically 200,000 MPa for standard reinforcement.",
        )
        
        # Then Geometry
        b_seed = _seed_from_param("b", 300.0)
        D_seed = _seed_from_param("D", 600.0)
        cover_seed = _seed_from_param("cover_bot", 40.0)

        b = number_row(
            "Section width b (mm)",
            "crack_b",
            b_seed,
            sync_callbacks,
            help_text="Section width (cross-section dimension perpendicular to bending axis).",
        )
        D = number_row(
            "Overall depth D (mm)",
            "crack_D",
            D_seed,
            sync_callbacks,
            help_text="Overall section depth (cross-section dimension in the direction of loading).",
        )
        c = number_row(
            "Clear cover to tensile bars c (mm)",
            "crack_cover_bot",
            cover_seed,
            sync_callbacks,
            help_text="Clear concrete cover to the centroid of the bottom tensile reinforcement layer.",
        )

    # --- Bottom Longitudinal Reinforcement ---
    with top_c2:
        _col_heading("Bottom longitudinal reinforcement")
        
        # Always seed from shared (single source of truth)
        db_bot_1_val = float(get_param("db_bot_1", 20.0))
        db_bot_2_val = float(get_param("db_bot_2", 20.0))
        rowgap_bot_val = float(get_param("rowgap_bot", 60.0))
    
        # Layer 1 mode
        w_bot1_layout_mode = get_widget_key_for_shared("bot1_layout_mode", prefix="crack_") or "crack_bot1_layout_mode"
        seed_widget_from_shared(w_bot1_layout_mode, "bot1_layout_mode", "Count")
        select_row(
            "Layer 1 layout mode",
            w_bot1_layout_mode,
            REO_LAYOUT_MODE,
            st.session_state.get("bot1_layout_mode", "Count"),
            sync_callbacks,
            help_text="Choose whether Layer 1 is defined by bar count or bar spacing.",
        )

        mode = st.session_state.get(w_bot1_layout_mode, st.session_state.get("bot1_layout_mode", "Count"))

        if mode == "Count":
            w_bot1_count = get_widget_key_for_shared("bot1_count", prefix="crack_") or "crack_bot1_count"
            seed_widget_from_shared(w_bot1_count, "bot1_count", 4)
            select_row(
                "Layer 1 bars (count)",
                w_bot1_count,
                REO_COUNTS_0_12,
                int(st.session_state.get("bot1_count", 4)),
                sync_callbacks,
                help_text="Number of bars in bottom Layer 1 (0–12).",
            )
        else:
            w_bot1_spacing = get_widget_key_for_shared("bot1_spacing", prefix="crack_") or "crack_bot1_spacing"
            seed_widget_from_shared(w_bot1_spacing, "bot1_spacing", 200)
            select_row(
                "Layer 1 bar spacing (mm)",
                w_bot1_spacing,
                REO_SPACINGS,
                int(st.session_state.get("bot1_spacing", 200)),
                sync_callbacks,
                help_text="Centre-to-centre spacing for bottom Layer 1 (mm).",
            )

        w_db_bot_1 = get_widget_key_for_shared("db_bot_1", prefix="crack_") or "crack_db_bot_1"
        seed_widget_from_shared(w_db_bot_1, "db_bot_1", 20.0)
        select_row(
            "Layer 1 bar Ø (mm)",
            w_db_bot_1,
            REO_BAR_DIAS,
            int(db_bot_1_val),
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 1 (mm).",
        )
    
        # Layer 2 mode
        w_bot2_layout_mode = get_widget_key_for_shared("bot2_layout_mode", prefix="crack_") or "crack_bot2_layout_mode"
        seed_widget_from_shared(w_bot2_layout_mode, "bot2_layout_mode", "Count")
        select_row(
            "Layer 2 layout mode",
            w_bot2_layout_mode,
            REO_LAYOUT_MODE,
            st.session_state.get("bot2_layout_mode", "Count"),
            sync_callbacks,
            help_text="Choose whether Layer 2 is defined by bar count or bar spacing.",
        )

        mode2 = st.session_state.get(w_bot2_layout_mode, st.session_state.get("bot2_layout_mode", "Count"))

        if mode2 == "Count":
            w_bot2_count = get_widget_key_for_shared("bot2_count", prefix="crack_") or "crack_bot2_count"
            seed_widget_from_shared(w_bot2_count, "bot2_count", 0)
            select_row(
                "Layer 2 bars (count)",
                w_bot2_count,
                REO_COUNTS_0_12,
                int(st.session_state.get("bot2_count", 0)),
                sync_callbacks,
                help_text="Number of bars in bottom Layer 2 (0–12).",
            )
        else:
            w_bot2_spacing = get_widget_key_for_shared("bot2_spacing", prefix="crack_") or "crack_bot2_spacing"
            seed_widget_from_shared(w_bot2_spacing, "bot2_spacing", 200)
            select_row(
                "Layer 2 bar spacing (mm)",
                w_bot2_spacing,
                REO_SPACINGS,
                int(st.session_state.get("bot2_spacing", 200)),
                sync_callbacks,
                help_text="Centre-to-centre spacing for bottom Layer 2 (mm).",
            )

        w_db_bot_2 = get_widget_key_for_shared("db_bot_2", prefix="crack_") or "crack_db_bot_2"
        seed_widget_from_shared(w_db_bot_2, "db_bot_2", 20.0)
        select_row(
            "Layer 2 bar Ø (mm)",
            w_db_bot_2,
            REO_BAR_DIAS,
            int(db_bot_2_val),
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 2 (mm).",
        )

        w_rowgap_bot = get_widget_key_for_shared("rowgap_bot", prefix="crack_") or "crack_rowgap_bot"
        seed_widget_from_shared(w_rowgap_bot, "rowgap_bot", 60.0)
        number_row(
            "Row gap (mm)",
            w_rowgap_bot,
            rowgap_bot_val,
            sync_callbacks,
            help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
        )

    # --- Crack Criteria ---
    with top_c3:
        _col_heading("Crack criteria")
        
        # Exposure class (shared)
        exp_options = ["A1", "A2", "B1", "B2", "C1", "C2"]
        exp_current = st.session_state.get("exposure_class", "B1")
        if exp_current not in exp_options:
            exp_current = "B1"

        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover(
                "Exposure class",
                "Exposure classification to AS 3600 – controls allowable crack width and durability detailing.",
            )
        with col2:
            st.selectbox(
                "",
                options=exp_options,
                index=exp_options.index(exp_current),
                key="crack_exposure_class",
                on_change=sync_callbacks["crack_exposure_class"],
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover("Resultant action", "Type of loading: primarily flexure (typical beams) or primarily tension (tension members). Affects which table values are used in crack control checks.")
        with col2:
            member_current = st.session_state.get("crack_member_type", "Primarily flexure")
            member_type = st.selectbox(
                "",
                options=["Primarily flexure", "Primarily tension"],
                index=0 if member_current == "Primarily flexure" else 1,
                key="inputs_crack_member_type",
                on_change=sync_callbacks["inputs_crack_member_type"],
                label_visibility="collapsed",
            )
        
        # k1 and k2 parameters (editable, in criteria column)
        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover("k₁ (bond coefficient)", "Bond coefficient: 0.8 for deformed bars, 1.6 for plain bars. Used in crack spacing calculations.")
        with col2:
            k1_val = float(st.session_state.get("crack_k1", 0.8))
            k1_options = [0.8, 1.6]
            k1 = st.selectbox(
                "",
                options=k1_options,
                index=k1_options.index(k1_val) if k1_val in k1_options else 0,
                format_func=lambda x: "Deformed bars (k₁ = 0.8)" if abs(x - 0.8) < 1e-9 else "Plain bars (k₁ = 1.6)",
                key="inputs_crack_k1",
                on_change=sync_callbacks["inputs_crack_k1"],
                label_visibility="collapsed",
            )

        # k2 (strain distribution factor) - default follows member type but only as a seed
        k2_seed = 0.5 if member_type == "Primarily flexure" else 1.0
        k2 = number_row(
            "k₂ (strain distribution factor)",
            "crack_k2",
            float(st.session_state.get("crack_k2", k2_seed)),
            sync_callbacks,
            help_text="Strain distribution factor used in crack spacing/width model. Default 0.5 for typical RC flexural members; adjust only if using a different assumed strain distribution per your chosen method.",
        )

    # Bottom row: 2 columns
    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)
    
    bot_c1, bot_c2 = st.columns(2, gap="large")
    
    # --- Computed (read-only) ---
    with bot_c1:
        _col_heading("Computed (read-only)")
        
        # Get computed values (these are derived from the widgets above)
        Ast = _seed_from_param("Ast_bot", 3 * math.pi * 20.0**2 / 4.0)
        db = _get_bottom_bar_diameter()
        spacing = _get_bottom_spacing()
        nb_bot = _get_bottom_bar_count()
        fct_default = 0.6 * math.sqrt(max(get_param("fc", 32.0), 1.0))
        fct_eff = float(fct_default)
        
        _render_readonly_value(
            "Area of tensile steel A_s,t (mm²)",
            Ast,
            "mm²",
            help_text="Total area of bottom tensile reinforcement, computed from bar layout.",
        )
        
        if spacing is not None:
            _render_readonly_value(
                "Row spacing s_r (mm)",
                spacing,
                "mm",
                help_text="Calculated centre-to-centre spacing of bottom reinforcement bars from layout.",
            )
        else:
            _render_readonly_value(
                "Row spacing s_r (mm)",
                None,
                "",
                help_text="Calculated centre-to-centre spacing of bottom reinforcement bars from layout.",
            )
        
        _render_readonly_value(
            "Effective mean tensile strength f_ct,eff (MPa)",
            fct_eff,
            "MPa",
            help_text="Effective mean axial tensile strength of concrete (f_ct,eff), calculated as 0.6√f'c.",
        )
        
        # Use spacing = 200.0 as fallback if not available (for calculations)
        if spacing is None:
            spacing = 200.0
    
    # --- Linked SLS inputs (read-only) ---
    with bot_c2:
        _col_heading("Linked SLS inputs (read-only)")
        
        # σ_sr from bending page (SLS steel stress)
        # Contract-safe: if missing, trigger bending compute (publishes via update_results only)
        results = st.session_state.get("results", {})
        sigma_sr_raw = results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", None))

        # Only auto-compute if value is missing/None (0 is a valid value!)
        if sigma_sr_raw is None:
            try:
                from bending_page import compute_bending_results
                compute_bending_results(publish=True)   # publishes sigma_s_sls via update_results
            except Exception:
                pass

        sigma_sr = float(results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", 0.0)))

        # Optional: warning only if still missing after attempted compute
        if results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", None)) is None:
            st.warning(
                "Crack page could not auto-load SLS steel stress (sigma_s_sls). "
                "Check bending compute pipeline (compute_bending_results / update_results)."
            )

        st.markdown(
            f"""
<div class="readonly-param">
  <div class="readonly-param-title">Steel stress at SLS σ_sr</div>
  <div class="readonly-param-value">{sigma_sr:.1f} MPa</div>
  <div class="readonly-param-source">Source: Bending page (SLS steel stress)</div>
</div>
""",
            unsafe_allow_html=True,
        )

        # φ_ce from creep page (read directly from results, not via get_param)
        phi_ce = float(st.session_state.get("phi_cc_t") or 0.0)

        st.markdown(
            f"""
<div class="readonly-param">
  <div class="readonly-param-title">Creep coefficient φ_ce</div>
  <div class="readonly-param-value">{phi_ce:.2f}</div>
  <div class="readonly-param-source">Source: Creep page (φ_cc(t))</div>
</div>
""",
            unsafe_allow_html=True,
        )

        # ε_cs from shrinkage page (read directly from results, not via get_param)
        eps_cs_micro = float(st.session_state.get("eps_cs_total_micro") or 0.0)
        eps_cs = eps_cs_micro * 1e-6

        st.markdown(
            f"""
<div class="readonly-param">
  <div class="readonly-param-title">Shrinkage strain ε_cs</div>
  <div class="readonly-param-value">{eps_cs_micro:.1f} μɛ</div>
  <div class="readonly-param-source">Source: Shrinkage page (ε_cs,total)</div>
</div>
""",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Effective area in tension and ρ_eff
    # --------------------------------------------------------
    # Get db for calculations (from helper or fallback)
    if db is None:
        db = 20.0  # Fallback
    d_eff = D - c - db / 2.0
    height_eff = min(2.5 * c, max(D - d_eff, 0.0), D / 2.0)
    Aceff = b * max(height_eff, 1.0)  # mm²
    rho_eff = Ast / Aceff

    # --------------------------------------------------------
    # 8.6.2.2 – Table-based max steel stress
    # --------------------------------------------------------
    # Read wmax_char_limit from shared state (widget removed, but value still in shared state)
    wmax_choice = float(get_param("wmax_char_limit", 0.3))
    sigma_table_A = table_sigma_max_A(db, wmax_choice)
    sigma_table_B = table_sigma_max_B(spacing, wmax_choice)

    if member_type == "Primarily tension":
        sigma_table_combined = sigma_table_A
        table_basis = "Table 8.6.2.2(A) – bar diameter"
    else:
        sigma_table_combined = max(sigma_table_A, sigma_table_B)
        table_basis = (
            "Max of Table 8.6.2.2(A) (bar diameter) "
            "and 8.6.2.2(B) (spacing)"
        )

    fsy_seed = _seed_from_param("fsy", 500.0)
    fsy = fsy_seed
    sigma_08fsy = 0.8 * fsy

    sigma_allow_table = min(sigma_table_combined, sigma_08fsy)
    utilisation_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0 else 0.0
    passes_table = utilisation_table <= 1.0

    # --------------------------------------------------------
    # 8.6.2.3 – Direct crack width calculation
    # --------------------------------------------------------
    # fct_eff is already computed and displayed in the Computed column section above
    # k1 and k2 are already defined in the Criteria column section above
    # Modular ratio for effective stiffness
    ne = (1.0 + phi_ce) * Es / Ec if Ec > 0 else 0.0

    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=ne,
        eps_cs=eps_cs,
    )

    sr_max = calc_sr_max(c_mm=c, db_mm=db, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff  # mm
    utilisation_w = w_calc / wmax_choice if wmax_choice > 0 else 0.0
    passes_w = utilisation_w <= 1.0

    # --------------------------------------------------------
    # TOP SUMMARY TABLE
    # --------------------------------------------------------
    with summary_placeholder.container():
        # Header row with title and INFO button
        sum_left, sum_right = st.columns([8, 1], vertical_alignment="center")
        with sum_left:
            st.markdown("## Summary")
        with sum_right:
            with st.popover("ℹ️ INFO"):
                st.markdown(
                    """
**What this page checks**  
This page checks **flexural crack control** for RC beams per AS 3600 using:
- A **table stress limit** method (Cl. 8.6.2.2 / Tables 8.6.2.2(A)–(B))
- A **direct crack-width** calculation (Cl. 8.6.2.3)

**How to interpret results**  
- The **table method** limits steel stress at SLS.
- The **direct check** compares calculated crack width **w** against the allowable limit **w′max**.
- The governing outcome should reflect your selected compliance rule (e.g., both checks pass).
"""
                )

        rows = [
            {
                "uid": "crk_step_1",
                "title": "Inputs & limits",
                "value": f"w'max = {wmax_choice:.3f} mm",
                "limit": f"Exposure/criteria",
                "util": "",
                "status": "",
                "ok": None,
                "is_primary": True,
            },
            {
                "uid": "crk_step_2",
                "title": "Table method — max steel stress σ_sr",
                "value": f"{sigma_sr:.1f} MPa",
                "limit": f"{sigma_allow_table:.1f} MPa",
                "util": f"{utilisation_table:.2f}",
                "status": "PASS" if passes_table else "FAIL",
                "ok": passes_table,
                "is_primary": True,
            },
            {
                "uid": "crk_step_3",
                "title": "Direct crack width w",
                "value": f"{w_calc:.3f} mm",
                "limit": f"{wmax_choice:.3f} mm",
                "util": f"{utilisation_w:.2f}",
                "status": "PASS" if passes_w else "FAIL",
                "ok": passes_w,
                "is_primary": True,
            },
            {
                "uid": "crk_step_4",
                "title": "Governing result",
                "value": "PASS" if (passes_table and passes_w) else "FAIL",
                "limit": "All checks",
                "util": "",
                "status": "",
                "ok": passes_table and passes_w,
                "is_primary": True,
            },
        ]
        
        clicked_uid = render_clickable_summary_table(rows, key_prefix="crack_summary")
        
        # Handle clicked summary row: expand step and set pending scroll
        if clicked_uid:
            open_key = f"step_open_{clicked_uid}"
            st.session_state[open_key] = True
        
        bind_summary_clicks()

    # --------------------------------------------------------
    # Steps: 4-step format matching bending/shear
    # --------------------------------------------------------
    page_divider()
    
    st.markdown("## Crack Checks")
    
    # Check 1 — Inputs & limits
    limits_md = rf"""
**Crack width limit**

Characteristic crack width limit: \(w'_{{\max}} = {wmax_choice:.3f}\,\text{{mm}}\)

This value is chosen based on:
- Exposure classification
- Surface finish requirements
- Durability considerations

Typical values:
- 0.2 mm for aggressive environments or appearance-critical surfaces
- 0.3 mm for normal exposure
- 0.4 mm for less critical surfaces

**Member type**

Resultant action: **{member_type}**

This affects which table method limits apply (Clause 8.6.2.2).
"""
    
    def step_1_body():
        calcbox(limits_md, status=None)
    
    render_jumpable_step(
        uid="crk_step_1",
        title="Check 1 — Inputs & crack limits",
        summary_md=f"w'max = {wmax_choice:.3f} mm",
        body_fn=step_1_body,
        expanded=bool(st.session_state.get("step_open_crk_step_1", False)),
        status=None,
    )
    
    # Step 2 — Table method (σ_sr check)
    table_details_md = rf"""
**Concept**

Instead of calculating a crack width directly, Clause 8.6.2.2 limits the **steel stress**
on the cracked section:

- For members **primarily in tension**:  
  \[
  \sigma_{{sr}} \le \sigma_{{\text{{max,A}}}} \quad \text{{(Table 8.6.2.2(A))}}
  \]
- For members **primarily in flexure**:  
  \[
  \sigma_{{sr}} \le \max\left(\sigma_{{\text{{max,A}}}}, \sigma_{{\text{{max,B}}}}\right)
  \]
  where \(\sigma_{{\text{{max,B}}}}\) comes from **Table 8.6.2.2(B)**.

Under direct loading, \(\sigma_{{sr,1}} \le 0.8 f_{{sy}}\).

**Current input**

- Bar diameter: \(d_b = {db:.1f}\,\text{{mm}}\)  
- Spacing: \(s = {spacing:.0f}\,\text{{mm}}\)  
- Crack width limit: \(w'_{{\max}} = {wmax_choice:.1f}\,\text{{mm}}\)  
- SLS steel stress: \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}}\)  
- Yield strength: \(f_{{sy}} \approx {fsy:.0f}\,\text{{MPa}}\)

**From tables**

- Table 8.6.2.2(A): \(\sigma_{{\text{{max,A}}}} \approx {sigma_table_A:.1f}\,\text{{MPa}}\)  
- Table 8.6.2.2(B): \(\sigma_{{\text{{max,B}}}} \approx {sigma_table_B:.1f}\,\text{{MPa}}\)  
- Combined table limit ({table_basis}):  
  \[
  \sigma_{{\text{{table}}}} = {sigma_table_combined:.1f}\,\text{{MPa}}
  \]
- 0.8\(f_{{sy}}\) limit:
  \[
  0.8 f_{{sy}} \approx {sigma_08fsy:.1f}\,\text{{MPa}}
  \]

Overall allowable steel stress:

\[
\sigma_{{\text{{allow}}}} = \min\left(\sigma_{{\text{{table}}}},\,0.8 f_{{sy}}\right)
= {sigma_allow_table:.1f}\,\text{{MPa}}
\]

**Check**

\[
\frac{{\sigma_{{sr}}}}{{\sigma_{{\text{{allow}}}}}}
= \frac{{{sigma_sr:.1f}}}{{{sigma_allow_table:.1f}}}
\approx {utilisation_table:.2f}
\quad\Rightarrow\quad
\text{{{"PASS" if passes_table else "FAIL"}}}
"""
    
    def step_2_body():
        calcbox(table_details_md, status="pass" if passes_table else "fail")
    
    render_jumpable_step(
        uid="crk_step_2",
        title="Check 2 — Table method (Cl. 8.6.2.2)",
        summary_md=f"σ_sr = {sigma_sr:.1f} MPa vs {sigma_allow_table:.1f} MPa → {'PASS' if passes_table else 'FAIL'}",
        body_fn=step_2_body,
        expanded=bool(st.session_state.get("step_open_crk_step_2", False)),
            status="pass" if passes_table else "fail",
    )
    
    # Check 3 — Direct crack width
    step1_rho_eff_md = rf"""
**Step 1 – Effective reinforcement ratio**

Effective area in tension (simplified):

\[
A_{{c,\text{{eff}}}} \approx b \, h_{{\text{{eff}}}}
\quad\Rightarrow\quad
A_{{c,\text{{eff}}}} \approx {Aceff:.0f}\,\text{{mm}}^2
\]

\[
\rho_{{\text{{eff}}}} = \frac{{A_{{s,t}}}}{{A_{{c,\text{{eff}}}}}}
= \frac{{{Ast:.0f}}}{{{Aceff:.0f}}}
\approx {rho_eff:.4f}
\]
"""

    step2_eps_md = rf"""
**Step 2 – Difference in mean strain** \(\varepsilon_{{sm}} - \varepsilon_{{cm}}\)

From Cl. 8.6.2.3(2):

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}}
= \frac{{\sigma_{{sr}}}}{{E_s}}
- \frac{{0.6 f_{{ct,\text{{eff}}}}}}{{E_s \rho_{{\text{{eff}}}}}}\left(1 + n_e \rho_{{\text{{eff}}}}\right)
+ \varepsilon_{{cs}}
\ge 0.6 \frac{{\sigma_{{sr}}}}{{E_s}}
\]

With:

- \(f_{{ct,\text{{eff}}}} = {fct_eff:.2f}\,\text{{MPa}}\)  
- \(E_s = {Es:.0f}\,\text{{MPa}},\ E_c = {Ec:.0f}\,\text{{MPa}}\)  
- \(\varphi_{{ce}} = {phi_ce:.2f}\)  
- \(n_e = (1 + \varphi_{{ce}}) E_s/E_c \approx {ne:.2f}\)  
- \(\varepsilon_{{cs}} \approx {eps_cs_micro:.1f}\times 10^{{-6}}\)

This gives:

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}} \approx {eps_diff:.3e}
\]
"""

    step3_srmax_md = rf"""
**Step 3 – Maximum crack spacing**

\[
s_{{r,\max}} = 3.4 c + 0.3 k_1 k_2 \frac{{d_b}}{{\rho_{{\text{{eff}}}}}}
\]

Using:

- \(c = {c:.1f}\,\text{{mm}},\ d_b = {db:.1f}\,\text{{mm}}\)  
- \(k_1 = {k1:.2f},\ k_2 = {k2:.2f}\)

\[
s_{{r,\max}} \approx {sr_max:.1f}\,\text{{mm}}
\]
"""

    step4_w_md = rf"""
**Step 4 – Crack width**

\[
w = s_{{r,\max}}(\varepsilon_{{sm}} - \varepsilon_{{cm}})
\approx {sr_max:.1f} \times {eps_diff:.3e}
\approx {w_calc:.3f}\,\text{{mm}}
\]

Limit:

\[
w'_{{\max}} = {wmax_choice:.1f}\,\text{{mm}}, \quad
\frac{{w}}{{w'_{{\max}}}} \approx {utilisation_w:.2f}
\Rightarrow\ \text{{{"PASS" if passes_w else "FAIL"}}}
"""
    
    def step_3_body():
        calcbox(step1_rho_eff_md, status=None)
        calcbox(step2_eps_md, status=None)
        calcbox(step3_srmax_md, status=None)
        calcbox(step4_w_md, status="pass" if passes_w else "fail")
    
    render_jumpable_step(
        uid="crk_step_3",
        title="Check 3 — Direct crack width (Cl. 8.6.2.3)",
        summary_md=f"w = {w_calc:.3f} mm ≤ {wmax_choice:.3f} mm → {'PASS' if passes_w else 'FAIL'}",
        body_fn=step_3_body,
        expanded=bool(st.session_state.get("step_open_crk_step_3", False)),
            status="pass" if passes_w else "fail",
    )
    
    # Check 4 — Governing result + interpretation
    governing_md = rf"""
**Governing outcome**

Both checks must pass for crack control to be satisfied:

1. **Table method (Cl. 8.6.2.2)**: \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}} \le {sigma_allow_table:.1f}\,\text{{MPa}}\) → **{"PASS" if passes_table else "FAIL"}**

2. **Direct calculation (Cl. 8.6.2.3)**: \(w = {w_calc:.3f}\,\text{{mm}} \le {wmax_choice:.1f}\,\text{{mm}}\) → **{"PASS" if passes_w else "FAIL"}**

**Overall result**: **{"PASS" if (passes_table and passes_w) else "FAIL"}**

Both the table method and direct calculation checks must pass for the crack control requirement to be satisfied.
"""
    
    def step_4_body():
        calcbox(governing_md, status=passes_table and passes_w)
    
    render_jumpable_step(
        uid="crk_step_4",
        title="Check 4 — Governing outcome",
        summary_md="Both checks must pass (table stress + direct width)",
        body_fn=step_4_body,
        expanded=bool(st.session_state.get("step_open_crk_step_4", False)),
        status=passes_table and passes_w,
        )

    # --------------------------------------------------------
    # Publish crack-control results (optional, for dashboards)
    # --------------------------------------------------------
    update_results(
        # keep existing outputs (used by Inputs summary today)
        sigma_allow_table=sigma_allow_table,
        sigma_sr=float(sigma_sr),
        w_calc=w_calc,
        wmax_char=wmax_choice,
        passes_table=passes_table,
        passes_w=passes_w,

        # ALSO publish standardized dashboard keys (already in RESULT_KEYS)
        crack_width=w_calc,
        crack_utilisation=utilisation_w,
    )
    
    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()


# For compatibility with whatever app.py calls
def render_crack_control():
    """Entry point used by app.py – delegates to render_crack()."""
    render_crack()


def render_crack_page():
    """Optional alias if imported elsewhere."""
    render_crack()
