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
from widgets_helpers import (
    apply_global_widget_css,
    apply_result_page_css,
    number_row,
    calcbox,
    render_jumpable_step,
    apply_step_summary_expander_css,
    page_divider,
    show_reo_message,
    label_with_hover,
    select_row,
    seed_widget_from_shared,
    render_page_explainer_expander,
    render_section_title,
    render_result_page_title,
    render_longitudinal_reo_rows,
    info_i_button,
    render_longitudinal_reo_row_config_controls,
    main_longitudinal_reo_pair_labels,
)
from ui_seamless_steps import inject_seamless_steps_css, render_clickable_summary_table, bind_summary_clicks
from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row
from crack_side_view_diagram import (
    _resolve_crack_diagram_window,
    render_crack_moment_tab_plotly,
    render_crack_side_view_diagram,
)

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
    render_section_title(text)


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
    apply_result_page_css()
    _inject_calcbox_css()
    apply_step_summary_expander_css()
    inject_seamless_steps_css()
    sync_callbacks = get_sync_callbacks()  # keeps contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    def _render_crack_explainer() -> None:
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

You can:

- **See behaviour (cracks)** in the side-view diagram once results are available
- **Inspect cause (moment)** in the moment diagram—SLS bending moment, using the same cached data as Beam Actions when that page has been run
"""
        )

    render_result_page_title("Crack width – AS 3600:2018")

    # --------------------------------------------------------
    # Reserve space for top summary then diagram (filled after calculations)
    # --------------------------------------------------------
    summary_placeholder = st.empty()
    diagram_placeholder = st.empty()

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

        fc = number_row(
            "Concrete strength f'c (MPa)",
            "crack_fc",
            fc_seed,
            sync_callbacks,
            help_text="Characteristic compressive strength of concrete at 28 days.",
        )
        Ec = float(get_param("Ec", 30000.0) or 30000.0)
        Es = float(get_param("Es", 200000.0) or 200000.0)
        
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

    # --- Bottom (web) longitudinal reinforcement ---
    with top_c2:
        _cr_sec_shape_ui = str(get_param("sec_shape", "RECT") or "RECT")
        _cr_bot_heading, _ = main_longitudinal_reo_pair_labels(_cr_sec_shape_ui, variant="sentence_lower")
        w_rowgap_bot = get_widget_key_for_shared("rowgap_bot", prefix="crack_") or "crack_rowgap_bot"
        seed_widget_from_shared(w_rowgap_bot, "rowgap_bot", 60.0)
        rowgap_bot_val = float(st.session_state.get(w_rowgap_bot, get_param("rowgap_bot", 60.0)))

        _crack_bot_title_col, _crack_bot_info_col = st.columns([0.92, 0.08], vertical_alignment="center")
        with _crack_bot_title_col:
            _col_heading(_cr_bot_heading.title())
        with _crack_bot_info_col:
            with info_i_button(help_text="Row count and vertical gap between reinforcement layers."):
                render_longitudinal_reo_row_config_controls(
                    page_prefix="crack",
                    section="bot",
                    sync_callbacks=sync_callbacks,
                    rowgap_widget_key=w_rowgap_bot,
                    rowgap_default=rowgap_bot_val,
                    rowgap_help_text="Clear vertical gap between reinforcement rows (mm).",
                    sec_shape=_cr_sec_shape_ui,
                )

        render_longitudinal_reo_rows(
            page_prefix="crack",
            section="bot",
            sync_callbacks=sync_callbacks,
            layout_modes=REO_LAYOUT_MODE,
            count_options=REO_COUNTS_0_12,
            spacing_options=REO_SPACINGS,
            dia_options=REO_BAR_DIAS,
            single_column=True,
            sec_shape=_cr_sec_shape_ui,
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

    # --------------------------------------------------------
    # Adopted values for crack checks (derived / linked; sources in calc steps below)
    # --------------------------------------------------------
    Ast = _seed_from_param("Ast_bot", 3 * math.pi * 20.0**2 / 4.0)
    db = _get_bottom_bar_diameter()
    spacing = _get_bottom_spacing()
    fct_default = 0.6 * math.sqrt(max(get_param("fc", 40.0), 1.0))
    fct_eff = float(fct_default)

    if spacing is None:
        spacing = 200.0

    # σ_sr from bending page (SLS steel stress)
    # Contract-safe: if missing, trigger bending compute (publishes via update_results only)
    results = st.session_state.get("results", {})
    sec_shape = str(get_param("sec_shape", "RECT") or "RECT")
    # T/I crack checks should use canonical resolved active-bar outputs from crack_core.
    if sec_shape in ("T", "I"):
        Ast = float(st.session_state.get("crack_Ast_active_mm2", Ast) or Ast)
        dias = list(st.session_state.get("crack_active_bar_dias", []) or [])
        db = float(max(dias) if dias else db or 0.0)
        spacing_vals = list(st.session_state.get("crack_active_bar_spacing_mm", []) or [])
        if spacing_vals:
            spacing = float(sum(float(v) for v in spacing_vals) / max(len(spacing_vals), 1))
        b = float(st.session_state.get("crack_tension_width_mm", b) or b)
        tension_face = str(st.session_state.get("crack_tension_face", "bottom") or "bottom")
        c = float(get_param("cover_top" if tension_face == "top" else "cover_bot", c) or c)

    sigma_sr_raw = results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", None))

    if sigma_sr_raw is None:
        try:
            from bending_page import compute_bending_results

            compute_bending_results(publish=True)  # publishes sigma_s_sls via update_results
        except Exception:
            pass

    sigma_sr = float(results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", 0.0)))

    if results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", None)) is None:
        st.warning(
            "Crack page could not auto-load SLS steel stress (sigma_s_sls). "
            "Check bending compute pipeline (compute_bending_results / update_results)."
        )

    phi_ce = float(st.session_state.get("phi_cc_t") or 0.0)
    eps_cs_micro = float(st.session_state.get("eps_cs_total_micro") or 0.0)
    eps_cs = eps_cs_micro * 1e-6

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
    # fct_eff, k1, k2 adopted above; modular ratio for effective stiffness
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
        # Same top-of-summary pattern as creep.py: explainer row, then table.
        render_page_explainer_expander(_render_crack_explainer)

        crack_pack = build_crack_check_rows_from_state(st.session_state)
        rows = []
        for r in (crack_pack.get("rows") or []):
            status = r.get("status", "—")
            is_info = bool(r.get("is_informational", False))
            stu = str(status).upper()
            if is_info or stu == "INFO":
                ok = None
            else:
                ok = True if status == "PASS" else False if status == "FAIL" else None
            rows.append({
                "uid": r.get("uid", "crk_step_3"),
                "title": r.get("title", ""),
                "capacity": r.get("capacity", r.get("value", "")),
                "action": r.get("action", r.get("limit", "")),
                "value": r.get("value", ""),
                "limit": r.get("limit", ""),
                "util": r.get("util", ""),
                "status": status,
                "ok": ok,
                "is_informational": is_info,
                "is_primary": False,
            })
        gov = pick_governing_check_row(rows)
        gov_uid = (gov or {}).get("uid")
        for r in rows:
            r["is_primary"] = bool(gov_uid and r.get("uid") == gov_uid)
        update_results("crack", {"rows": rows})
        
        clicked_uid = render_clickable_summary_table(rows, key_prefix="crack_summary")
        
        # Handle clicked summary row: expand step and set pending scroll
        if clicked_uid:
            open_key = f"step_open_{clicked_uid}"
            st.session_state[open_key] = True
        
        bind_summary_clicks()

    with diagram_placeholder.container():
        st.markdown(
            """
<style>
div[data-testid="stVerticalBlock"]:has(#crack-diagram-module) [data-testid="stRadio"] {
    margin-top: 0.15rem !important;
    margin-bottom: 0.4rem !important;
}
div[data-testid="stVerticalBlock"]:has(#crack-diagram-module) [data-testid="stPlotlyChart"] {
    margin-bottom: 0.1rem !important;
}
</style>
<div id="crack-diagram-module" style="height:0;width:0;overflow:hidden;" aria-hidden="true"></div>
""",
            unsafe_allow_html=True,
        )
        seed_widget_from_shared("crack_diagram_view", "crack_diagram_panel", "Crack Diagram")
        _gov_col, _spacer = st.columns([2.2, 3.0])
        with _gov_col:
            if bool(_resolve_crack_diagram_window(st.session_state).get("multi")):
                st.markdown(
                    '<p style="margin:0 0 0.35rem 0;font-size:0.82rem;color:#6b7280;">'
                    "Displaying governing span"
                    "</p>",
                    unsafe_allow_html=True,
                )
        st.radio(
            "Diagram view",
            options=["Crack Diagram", "Moment Diagram"],
            horizontal=True,
            key="crack_diagram_view",
            on_change=sync_callbacks["crack_diagram_view"],
            label_visibility="collapsed",
        )
        panel = str(st.session_state.get("crack_diagram_view", "Crack Diagram") or "Crack Diagram")
        if panel == "Moment Diagram":
            render_crack_moment_tab_plotly()
        else:
            render_crack_side_view_diagram(
                st.session_state,
                crack_metrics={
                    "sr_max_mm": float(sr_max),
                    "w_calc_mm": float(w_calc),
                    "wmax_mm": float(wmax_choice),
                },
            )

    # --------------------------------------------------------
    # Steps: 4-step format matching bending/shear
    # --------------------------------------------------------
    page_divider()
    
    render_section_title("Crack Checks")
    
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

- Bar diameter: \(d_b = {db:.1f}\,\text{{mm}}\) — *Derived on Crack page from reinforcement layout (bar diameter).*
- Spacing: \(s = {spacing:.0f}\,\text{{mm}}\) — *Derived on Crack page from reinforcement layout (row spacing \(s_r\)).*
- Crack width limit: \(w'_{{\max}} = {wmax_choice:.1f}\,\text{{mm}}\)  
- SLS steel stress: \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}}\) — *Source: Bending page (SLS steel stress).*
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
        title="Check 2 — Table method",
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

*Source: \(A_{{s,t}} = {Ast:.0f}\,\text{{mm}}^2\) — resolved from active tension reinforcement geometry.*
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

- \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}}\) — *Source: Bending page (SLS steel stress).*
- \(f_{{ct,\text{{eff}}}} = {fct_eff:.2f}\,\text{{MPa}}\) — *Source: \(0.6\sqrt{{f'c}}\) from concrete strength used for crack control.*
- \(E_s = {Es:.0f}\,\text{{MPa}},\ E_c = {Ec:.0f}\,\text{{MPa}}\)  
- \(\varphi_{{ce}} = {phi_ce:.2f}\) — *Source: Creep page (\(\varphi_{{cc}}(t)\)).*
- \(n_e = (1 + \varphi_{{ce}}) E_s/E_c \approx {ne:.2f}\)  
- \(\varepsilon_{{cs}} \approx {eps_cs_micro:.1f}\times 10^{{-6}}\) — *Source: Shrinkage page (\(\varepsilon_{{cs,total}}\)).*

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

- \(c = {c:.1f}\,\text{{mm}},\ d_b = {db:.1f}\,\text{{mm}}\) — *\(d_b\) from Crack page reinforcement layout.*
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

Calculated capacity (allowable crack width):

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
        title="Check 3 — Direct crack width",
        summary_md=f"w = {w_calc:.3f} mm ≤ {wmax_choice:.3f} mm → {'PASS' if passes_w else 'FAIL'}",
        body_fn=step_3_body,
        expanded=bool(st.session_state.get("step_open_crk_step_3", False)),
            status="pass" if passes_w else "fail",
    )
    
    # Check 4 — Governing result + interpretation
    governing_md = rf"""
**Governing outcome**

Both checks must pass for crack control to be satisfied:

1. **Table method**: \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}} \le {sigma_allow_table:.1f}\,\text{{MPa}}\) → **{"PASS" if passes_table else "FAIL"}**

2. **Direct calculation**: \(w = {w_calc:.3f}\,\text{{mm}} \le {wmax_choice:.1f}\,\text{{mm}}\) → **{"PASS" if passes_w else "FAIL"}**

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
        crack_sr_max_mm=float(sr_max),
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
