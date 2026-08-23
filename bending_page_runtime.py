# bending_page_runtime.py
# ============================
# BENDING PAGE
# ============================

import math
import streamlit as st

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
    update_results,
    recalc_derived_values,
    resolve_design_actions,
    render_timing_mark,
)
from widgets_helpers import (
    apply_result_page_css,
    apply_step_expander_css,
    info_i_button,
    render_lazy_expander,
    render_page_explainer_expander,
    render_section_title,
    render_result_page_title,
    render_plotly_diagram,
    render_pyplot_diagram,
)
from bending_core import (
    _fmt,
    _compute_bending_capacity,
    _stress_strain_state,
    compute_sls_bending_values_from_state,
    hogging_tension_effective_depth_mm,
    solve_bending_capacity,
)
from bending_checks_helpers import build_bending_check_rows_from_state
from inputs_application.authoritative_check_packs import current_authoritative_family
from calculations.bending import (
    bottom_tension_effective_depth_fallback_mm,
)
from ui_seamless_steps import (
    inject_seamless_steps_css,
    bind_summary_clicks,
    step_card,
)
from engineering_page_sections.stable_tabs import (
    render_stable_tabs,
)
from engineering_page_sections.bending_page_context import (
    BendingCaseSnapshot,
    build_bending_page_snapshot,
)
from engineering_page_sections.bending_page_shell import BendingPageShell
from engineering_page_sections.bending_summary import (
    apply_bending_summary_navigation,
    render_bending_summary,
)
from engineering_page_sections.bending_inputs import (
    render_bending_inputs,
)
from engineering_page_sections.bending_checks_context import (
    build_bending_checks_snapshot,
)
from engineering_page_sections.bending_checks import render_bending_checks


def _plot_stress_strain_profiles(*args, **kwargs):
    from bending_diagrams import _plot_stress_strain_profiles as renderer

    return renderer(*args, **kwargs)


def _plot_material_stress_strain_curves(*args, **kwargs):
    from bending_diagrams import _plot_material_stress_strain_curves as renderer

    return renderer(*args, **kwargs)


def figure_bmd_from_state(*args, **kwargs):
    from ui.diagrams.moment_shear_diagram import figure_bmd_from_state as builder

    return builder(*args, **kwargs)

def _overlay_authoritative_bending_result(target, bending, ductility, default_depth):
    """Project the published V2 result into the existing detail-renderer shape."""

    if not bending:
        return
    target.update({
        "_authoritative_uls": True,
        "phi_Mu_cap": float(bending.get("phi_Mu_kNm", 0.0) or 0.0),
        "phi_Mu_kNm": float(bending.get("phi_Mu_kNm", 0.0) or 0.0),
        "Mu_util": float(bending.get("util", 0.0) or 0.0),
        "util": float(bending.get("util", 0.0) or 0.0),
        "Mu_nom": float(bending.get("Mu_nom_kNm", 0.0) or 0.0),
        "Mu_nom_kNm": float(bending.get("Mu_nom_kNm", 0.0) or 0.0),
        "phi": float(bending.get("phi", 0.65) or 0.65),
        "ku": float(bending.get("ku", 0.0) or 0.0),
        "c": float(bending.get("dn_mm", 0.0) or 0.0),
        "dn_mm": float(bending.get("dn_mm", 0.0) or 0.0),
        "a": float(bending.get("block_depth_mm", 0.0) or 0.0),
        "z": float(bending.get("resultant_lever_arm_mm", 0.0) or 0.0),
        "d": float(bending.get("d_mm", default_depth) or default_depth),
        "d_mm": float(bending.get("d_mm", default_depth) or default_depth),
        "alpha2": float(bending.get("alpha2", 0.0) or 0.0),
        "gamma": float(bending.get("gamma", 0.0) or 0.0),
        "section_shape": str(bending.get("section_shape", "RECT") or "RECT"),
        "T_N": float(bending.get("tension_force_n", 0.0) or 0.0),
        "C_concrete_N": float(bending.get("concrete_force_n", 0.0) or 0.0),
        "C_steel_N": float(bending.get("compression_steel_force_n", 0.0) or 0.0),
        "compression_concrete_area_mm2": float(bending.get("compression_concrete_area_mm2", 0.0) or 0.0),
        "concrete_centroid_mm": float(bending.get("concrete_centroid_mm", 0.0) or 0.0),
        "equilibrium_residual_n": float(bending.get("equilibrium_residual_n", 0.0) or 0.0),
        "neutral_axis_iteration_trace": tuple(bending.get("neutral_axis_iteration_trace", ()) or ()),
        "steel_layer_stresses_mpa": tuple(bending.get("steel_layer_stresses_mpa", ()) or ()),
        "steel_layer_areas_mm2": tuple(bending.get("steel_layer_areas_mm2", ()) or ()),
        "steel_layer_labels": tuple(bending.get("steel_layer_labels", ()) or ()),
        "steel_layer_faces": tuple(bending.get("steel_layer_faces", ()) or ()),
        "steel_layer_forces_n": tuple(bending.get("steel_layer_forces_n", ()) or ()),
        # Preserve the authoritative reinforcement coordinates as well as the
        # forces/stresses.  The detail cards must not relabel effective depth
        # ``d`` as the steel-layer coordinate ``y_s``.
        "steel_layer_depths_mm": tuple(bending.get("steel_layer_depths_mm", ()) or ()),
        "sls_cracked_section": dict(bending.get("sls_cracked_section", {}) or {}),
        "sls_cracked_section_ignore_compression": dict(
            bending.get("sls_cracked_section_ignore_compression", {}) or {}
        ),
    })
    if ductility:
        target.update({
            "ductility_status": str(ductility.get("status", "NOT RUN")),
            "ductility_limit": float(ductility.get("limit", 0.36) or 0.36),
            "clause_815_triggered": bool(ductility.get("conditional_triggered", False)),
            "clause_815_satisfied": bool(ductility.get("conditional_requirements_satisfied", False)),
            "clause_815_failed_requirements": tuple(ductility.get("failed_requirements", ()) or ()),
        })


from engineering_page_sections import bending_diagrams as _bending_diagrams_section
from engineering_page_sections import bending_diagram_bundle as _bending_diagram_bundle

_bending_diagram_runtime = _bending_diagram_bundle.BendingDiagramRuntime(
    st=st,
    get_param=get_param,
    render_timing_mark=render_timing_mark,
    plot_stress_strain_profiles=_plot_stress_strain_profiles,
    plot_material_stress_strain_curves=_plot_material_stress_strain_curves,
    figure_bmd_from_state=figure_bmd_from_state,
    render_plotly_diagram=render_plotly_diagram,
    render_section_title=render_section_title,
    render_stable_tabs=render_stable_tabs,
    render_lazy_expander=render_lazy_expander,
)


def _render_bending_diagram_bundle_panel_impl(**kwargs):
    return _bending_diagram_bundle.render_bending_diagram_bundle_panel(
        runtime=_bending_diagram_runtime,
        **kwargs,
    )


_render_bending_diagram_bundle_panel = st.fragment(
    _render_bending_diagram_bundle_panel_impl
)


# Conditional caching: bypass in debug mode, cache in production





from engineering_page_sections.bending_calculations import (
    _compute_sls_bending_values,
    _get_bending_inputs_from_shared_state,
    compute_bending_results,
    get_bending_inputs_from_shared_state,
    make_bending_sig_from_shared_state,
)









def render_bending():
    # Reserve the page-top result container before invisible CSS/style elements
    # so its heading aligns with the other engineering pages.
    bending_page_shell = BendingPageShell.create(st)
    top_container = bending_page_shell.top
    render_timing_mark("bending_page.runtime.start")
    # NOTE: init_shared_session_state() is called by app.py router before this function runs.
    # Pages must NOT call init/hydrate themselves - the router owns the lifecycle.

    from state_and_helpers import _write_sync_trace_line
    _write_sync_trace_line("\n=== PAGE RENDER: bending ===")
    # Widget callbacks update the live row-model keys before this rerun. Recompute
    # derived summaries here so the top summary and diagrams use the current reo layout
    # even when the global structural recompute is not running.
    recalc_derived_values()

    # Handle cross-page navigation from Inputs page
    from jump_nav import JUMP_NAV_TAB_KEY, get_jump_uid

    get_jump_uid()
    # Optional canonical row uid (?jump_row=) disambiguates pos/neg rows that share one calc id.
    _jr = st.query_params.get("jump_row")
    if isinstance(_jr, list):
        _jr = _jr[0] if _jr else None
    if _jr:
        _jrs = str(_jr).strip()
        if _jrs == "bend_strength_pos":
            st.session_state["bending_detail_view"] = "positive"
        elif _jrs == "bend_strength_neg":
            st.session_state["bending_detail_view"] = "negative"
        try:
            del st.query_params["jump_row"]
        except Exception:
            pass
    _jt = st.session_state.get("jump_to")
    if _jt:
        _sid = str(_jt)
        if _sid.startswith("bending_sls_"):
            st.session_state[JUMP_NAV_TAB_KEY] = "SLS Checks"
            st.session_state["bending_check_tab"] = "SLS Checks"
        elif _sid.startswith("bending_min_"):
            st.session_state[JUMP_NAV_TAB_KEY] = "Minimum strength checks"
            st.session_state["bending_check_tab"] = "Minimum strength checks"
        else:
            st.session_state[JUMP_NAV_TAB_KEY] = "ULS Checks"
            st.session_state["bending_check_tab"] = "ULS Checks"

    sync_callbacks = get_sync_callbacks()
    apply_result_page_css()

    # Inject seamless steps CSS (for summary table + calc details)
    inject_seamless_steps_css()


    # Initialize page-local active mode state (UI-only, not in shared state)
    if "bending_active_mode" not in st.session_state:
        st.session_state["bending_active_mode"] = "ULS"

    from inputs_application.active_beam_engineering_state import (
        resolve_active_beam_engineering_state,
    )

    page_engineering_state = dict(
        resolve_active_beam_engineering_state(st.session_state).values
    )


    # Remove green background from inline math (Streamlit wraps math in code tags)
    # But preserve katex rendering by only targeting background, not font styling
    st.markdown(
        """
<style>
/* Remove green background from code elements in markdown paragraphs (these contain math) */
/* But don't override font-family so katex can render properly */
.stMarkdown p code {
    background-color: transparent !important;
    border: none !important;
    padding: 0 !important;
}
/* Ensure katex elements render properly */
.stMarkdown p code .katex,
.stMarkdown p .katex {
    font-family: KaTeX_Main, "Times New Roman", serif !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


    # ---------------- Sidebar glossary ----------------
    with st.sidebar.expander("📘 Glossary – Bending terms", expanded=False):
        st.markdown(
            """
            **Mu*** – Factored design bending moment at the critical section (kNm).
            **b** – Beam/web width (mm).
            **D** – Overall section depth (mm).
            **d** – Effective depth to **centroid of tension steel** (mm).
            **Ast,bot** – Area of bottom (tension) reinforcement (mm²).
            **As_min** – Minimum required tensile steel for ductile behaviour.
            **f'c** – Concrete cylinder strength (MPa).
            **fsy** – Steel yield strength (MPa).
            **Ec, Es** – Elastic moduli of concrete and steel (MPa).

            **c** – Neutral axis depth from the top fibre (mm).
            **a = γc** – Equivalent rectangular stress block depth (mm).
            **kᵤ = c/d** – Neutral axis depth ratio (ductility indicator).
            **α₂, γ** – AS 3600-style stress block factors.
            **ϕ** – Strength reduction factor for bending.

            **M_cr** – Cracking moment (kNm) based on f_ct,f and gross section.
            **M_u** – Nominal flexural capacity (kNm).
            **ϕM_u,cap** – Design flexural capacity (kNm).
            **Utilisation** – M_u* / ϕM_u,cap → should be ≤ 1.0.
            """
        )

    # Sync ULS load to Mu_star (contract-compliant via update_results)
    # Skip in design-driven mode to avoid overwriting SFD/BMD actions.
    if get_param("actions_mode", "manual") != "design":
        Mu_star_uls_val = get_param("uls_Mstar")
        if Mu_star_uls_val is not None:
            update_results(
                Mu_star=float(abs(Mu_star_uls_val)),
                Mu_star_kNm=float(abs(Mu_star_uls_val)),
                Mu_star_kNm_signed=float(Mu_star_uls_val),
            )

    render_timing_mark("bending_page.runtime.summary_compute.start")
    # ---------------- Top result summary (+ shared 3D NA view data) ----------------
    top_results = _compute_bending_capacity()
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")
    # Compute SLS values before summary / tabs (publishes sigma_s_sls, bending_sls_fs_outer, etc.)
    _compute_sls_bending_values()

    actions_signed = resolve_design_actions()
    has_sagging_case = bool(actions_signed.get("has_sagging_case", False))
    has_hogging_case = bool(actions_signed.get("has_hogging_case", False))
    Mu_pos_star = float(actions_signed.get("Mu_pos", 0.0) or 0.0)
    Mu_neg_star = float(actions_signed.get("Mu_neg", 0.0) or 0.0)
    Ms_pos_star = float(actions_signed.get("SLS_M_pos", 0.0) or 0.0)
    Ms_neg_star = float(actions_signed.get("SLS_M_neg", 0.0) or 0.0)

    D_val = float(get_param("D") or 0.0)
    do_val = float(get_param("do") or 0.0)
    d_pos_val = float(get_param("d") or 0.0)
    d_neg_val = hogging_tension_effective_depth_mm(D_val, do_val)
    common_bending_inputs = {
        "b": get_param("b"),
        "D": get_param("D"),
        "fc": get_param("fc"),
        "fsy": get_param("fsy"),
        "phi_bend": get_param("phi_bend"),
        "Ast_bot": get_param("Ast_bot"),
        "Ast_top": get_param("Ast_top"),
        "d": d_pos_val,
        "do": do_val,
    }
    top_results_pos = solve_bending_capacity("positive", Mu_pos_star, common_bending_inputs)
    top_results_neg = solve_bending_capacity("negative", Mu_neg_star, common_bending_inputs)
    authoritative_bending = current_authoritative_family(st.session_state, "bending")
    authoritative_ductility = current_authoritative_family(st.session_state, "ductility")
    _overlay_authoritative_bending_result(
        top_results_pos,
        authoritative_bending,
        authoritative_ductility,
        d_pos_val,
    )

    # The section layout and every stress-state projection must share one
    # revision-bound input object.  Reading ``get_param`` here previously let
    # old widget mirrors survive Design Brain Apply while the calculation
    # cards already displayed the new authoritative result.
    from section_layout import compute_section_layout

    cached_layout = compute_section_layout(page_engineering_state)
    c_top = top_results["c"]

    # Canonical bending state shared by 3D & bottom radios (ULS / SLS / Uncracked)
    state_options = ["ULS", "SLS (cracked)", "Uncracked"]
    canonical_state = st.session_state.get("bending_state", "ULS")
    if canonical_state not in state_options:
        canonical_state = "ULS"

    bend_pack = build_bending_check_rows_from_state(st.session_state)
    if not top_results_pos.get("_authoritative_uls"):
        _overlay_authoritative_bending_result(
            top_results_pos,
            bend_pack.get("authoritative_family") or {},
            bend_pack.get("authoritative_ductility_family") or {},
            d_pos_val,
        )
    has_sagging_case = bool(bend_pack.get("has_sagging_case", has_sagging_case))
    has_hogging_case = bool(bend_pack.get("has_hogging_case", has_hogging_case))
    has_positive_bending_case = has_sagging_case
    has_negative_bending_case = has_hogging_case
    _valid_bending_views = [
        v
        for v, ok in (
            ("positive", has_positive_bending_case),
            ("negative", has_negative_bending_case),
        )
        if ok
    ]
    if not st.session_state.get("_bending_detail_view_seeded"):
        st.session_state["_bending_detail_view_seeded"] = True
        if has_negative_bending_case and not has_positive_bending_case:
            st.session_state["bending_detail_view"] = "negative"
        elif has_positive_bending_case and not has_negative_bending_case:
            st.session_state["bending_detail_view"] = "positive"
        elif has_positive_bending_case and has_negative_bending_case:
            u_p = float(top_results_pos.get("util", 0.0) or 0.0)
            u_n = float(top_results_neg.get("util", 0.0) or 0.0)
            st.session_state["bending_detail_view"] = (
                "negative" if u_n > u_p else "positive"
            )
    _bdv = st.session_state.get("bending_detail_view", "positive")
    if _bdv not in _valid_bending_views and _valid_bending_views:
        st.session_state["bending_detail_view"] = _valid_bending_views[0]

    bending_page_snapshot = build_bending_page_snapshot(
        engineering_state=page_engineering_state,
        check_pack=bend_pack,
        authoritative_bending=authoritative_bending,
        authoritative_ductility=authoritative_ductility,
        section_layout=cached_layout,
        positive_case=BendingCaseSnapshot(
            moment_sign="positive",
            has_case=has_sagging_case,
            uls_demand_kNm=Mu_pos_star,
            sls_demand_kNm=Ms_pos_star,
            reinforcement_area_mm2=float(Ast or 0.0),
            effective_depth_mm=d_pos_val,
            results=top_results_pos,
        ),
        negative_case=BendingCaseSnapshot(
            moment_sign="negative",
            has_case=has_hogging_case,
            uls_demand_kNm=Mu_neg_star,
            sls_demand_kNm=Ms_neg_star,
            reinforcement_area_mm2=float(common_bending_inputs["Ast_top"] or 0.0),
            effective_depth_mm=d_neg_val,
            results=top_results_neg,
        ),
        selected_detail_view=st.session_state.get(
            "bending_detail_view", "positive"
        ),
        valid_detail_views=_valid_bending_views,
        selected_diagram_state=canonical_state,
    )

    render_timing_mark("bending_page.runtime.summary_compute.end")

    render_timing_mark("bending_page.runtime.presentation.start")
    # ---------------- TOP CONTAINER – Title + summary + explainer ----------------
    with top_container:
        def _on_bending_sign_change():
            v = st.session_state.get("_bending_sign_radio")
            st.session_state["bending_detail_view"] = (
                "negative" if v == "Hogging" else "positive"
            )

        if len(_valid_bending_views) == 2:
            _lab = (
                "Hogging"
                if st.session_state.get("bending_detail_view") == "negative"
                else "Sagging"
            )
            _opts = ["Sagging", "Hogging"]
            st.radio(
                "Bending check (detail)",
                _opts,
                horizontal=True,
                index=_opts.index(_lab) if _lab in _opts else 0,
                key="_bending_sign_radio",
                on_change=_on_bending_sign_change,
            )
        elif len(_valid_bending_views) == 1:
            st.session_state["bending_detail_view"] = _valid_bending_views[0]

        selected_bending_sign = bending_page_snapshot.view.selected_detail_view
        st.session_state["_bending_page_selected_sign"] = selected_bending_sign

        if has_sagging_case and has_hogging_case:
            _bend_page_title = (
                "Hogging bending capacity"
                if selected_bending_sign == "negative"
                else "Sagging bending capacity"
            )
        elif has_hogging_case:
            _bend_page_title = "Hogging bending capacity"
        elif has_sagging_case:
            _bend_page_title = "Sagging bending capacity"
        else:
            _bend_page_title = "Bending capacity"
        # The app shell owns the active page heading. Keep this fallback only
        # for direct renderer use, otherwise the shell and page would both
        # render the same title on every rerun.
        if not st.session_state.get("_shared_page_title_owned_by_shell", False):
            render_result_page_title(_bend_page_title)

        def _render_bending_explainer() -> None:
            render_timing_mark("bending_page.runtime.explainer.body.start")
            top_left, top_right = st.columns([0.58, 0.42])
            sign = st.session_state.get("_bending_page_selected_sign", "positive")
            hog = sign == "negative"

            with top_left:
                mode = "hogging (negative)" if hog else "sagging (positive)"
                st.markdown(
                    f"""
This page computes **ultimate flexural capacity**, **strain compatibility**, and
**service-stress outputs** in accordance with **AS 3600:2018 Clause 8**, including:

**Detail view:** **{mode}** bending — compression and tension zones match this selection.
"""
                )

                st.markdown(r"""
- **Ultimate moment capacity** (Cl. 8.1.3)
    $$\phi M_{u,\mathrm{cap}} = \phi\,T\,(d - 0.5\,\gamma x_u)$$

- **Steel stress at serviceability**, used in crack-width and deflection checks.
    $$f_{s,\mathrm{ser}} = E_s\,\varepsilon_s$$
""")

            with top_right:
                st.markdown("")

                from curved_beam_diagram import render_curved_beam_fig

                try:
                    inputs = get_bending_inputs_from_shared_state()
                    L_m = inputs["L"] / 1000.0
                    D_mm = float(inputs["D"])
                    D_m = D_mm / 1000.0
                    b_m = inputs["b"] / 1000.0
                    if hog:
                        c_mm = float(top_results_neg.get("dn_mm", float("nan")))
                        if c_mm == c_mm and not math.isnan(c_mm) and D_mm > 0:
                            dn_uls_m = max(0.0, (D_mm - c_mm) / 1000.0)
                        else:
                            dn_uls_m = 0.21 * D_m
                        curv = -0.4
                    else:
                        c_mm = float(
                            top_results_pos.get("dn_mm", c_top or float("nan"))
                        )
                        if c_mm == c_mm and not math.isnan(c_mm):
                            dn_uls_m = float(c_mm) / 1000.0
                        elif c_top is not None and not (
                            isinstance(c_top, float) and math.isnan(c_top)
                        ):
                            dn_uls_m = float(c_top) / 1000.0
                        else:
                            dn_uls_m = 0.21 * D_m
                        curv = 0.4

                    if D_m > 0 and L_m > 0 and dn_uls_m > 0:
                        fig_beam = render_curved_beam_fig(
                            L=L_m,
                            D=D_m,
                            b=b_m,
                            dn_uls=dn_uls_m,
                            ts_centroid_y=None,
                            curvature=curv,
                            title=None,
                        )
                        render_pyplot_diagram(
                            fig_beam,
                            key="bending_curved_beam_diagram",
                            title="Curved beam view",
                            clear_figure=True,
                        )
                    else:
                        st.info(
                            "Curved beam view will appear once geometry and moment capacity are defined."
                        )
                except Exception:
                    st.warning(
                        "3D view failed to render (browser/graphics). Try refreshing the page."
                    )
            render_timing_mark("bending_page.runtime.explainer.body.end")

        debug_mode = st.sidebar.checkbox(
            "Debug session state",
            key=f"debug_state_toggle_{st.session_state.get('page_slug','page')}"
        )
        if debug_mode:
            st.sidebar.markdown("### Debug session state")

            debug_keys = [
                "page_slug",
                "actions_source",
                "inputs_actions_source",
                "loads_edit_mode",

                # load proxies
                "load_Mstar_proxy",
                "load_Vstar_proxy",
                "load_Nstar_proxy",

                # shared actions
                "uls_Mstar",
                "uls_Vstar",
                "uls_Nstar",

                # bending derived
                "Mu_star",
                "Mu_star_kNm",

                # shear derived
                "Vu_star",

                # SFD/BMD outputs
                "sfd_Mmax_abs_kNm",
                "sfd_Vmax_abs_kN",
            ]

            st.sidebar.json({
                k: st.session_state.get(k)
                for k in debug_keys
            })

        # Render the engineering summary before lower-priority explanatory
        # content. The summary module owns row projection and click intent;
        # this coordinator retains the presentation-state mutation boundary.
        summary_result = render_bending_summary(
            bend_pack.get("rows") or [],
            publish_rows=lambda rows: update_results("bending", {"rows": rows}),
        )
        render_timing_mark("bending_page.runtime.summary_table.rendered")

        # Reserve the explainer's exact page position, but defer its collapsed
        # widget payload until after the two visible loading regions stream.
        explainer_placeholder = st.empty()

        apply_bending_summary_navigation(
            st.session_state,
            summary_result.interaction,
            jump_tab_key=JUMP_NAV_TAB_KEY,
        )

        diagram_shell_generation = int(
            st.session_state.get("_bending_diagram_shell_generation", 0) or 0
        ) + 1
        st.session_state["_bending_diagram_shell_generation"] = diagram_shell_generation
        shell_content = bending_page_shell.reserve_content(st)
        diagram_options_placeholder = shell_content.diagram_options
        diagram_section_placeholder = shell_content.diagram_section
        inputs_placeholder = shell_content.inputs
        calc_blocks_container = shell_content.calculations
        # Both target containers already have their final page positions.
        # Publish their contents back-to-back only after those positions are
        # allocated so the intervening placeholders cannot split the visible
        # shell across two browser paint windows.
        _bending_diagrams_section.render_bending_calculation_loading_shell(
            calc_blocks_container
        )
        with diagram_options_placeholder.container():
            if "concrete_stress_model" not in st.session_state:
                st.session_state["concrete_stress_model"] = "rectangular"
            _, col_info = st.columns([0.95, 0.05])
            with col_info:
                with info_i_button(help_text="Concrete stress model options"):
                    st.markdown("**Concrete stress model**")
                    use_parabolic = st.checkbox(
                        "Use parabolic (non-linear) stress block",
                        value=(
                            st.session_state["concrete_stress_model"] == "parabolic"
                        ),
                        key="bending_parabolic_toggle",
                    )
                    st.session_state["concrete_stress_model"] = (
                        "parabolic" if use_parabolic else "rectangular"
                    )
                    st.markdown(
                        """
                        **Rectangular (AS 3600):** Standard simplified stress
                        block used in AS 3600 design.

                        **Parabolic (non-linear):** More accurate concrete
                        stress distribution for presentation.
                        """
                    )

        initial_mu_uls = bending_page_snapshot.active_case.uls_demand_kNm
        with diagram_section_placeholder.container():
            _render_bending_diagram_bundle_panel(
                cached_layout=cached_layout,
                mu_uls_active=initial_mu_uls,
                diagram_shell_generation=diagram_shell_generation,
            )
        with explainer_placeholder:
            render_timing_mark("bending_page.runtime.explainer.start")
            render_page_explainer_expander(_render_bending_explainer)
            render_timing_mark("bending_page.runtime.explainer.end")
        # Browser-only summary navigation does not participate in the first
        # visible Bending shell. Install it after both reserved regions have
        # streamed so its component iframe cannot delay those milestones.
        bind_summary_clicks()

        # Keep the Bending page on one spacing rhythm across major headings,
        # tabs, diagrams, and the calculation-card stack.
        st.markdown(
            """
            <style>
            /* Stable-tab scroll hooks are zero-height iframes; remove their
               Streamlit element-wrapper contribution to vertical spacing. */
            div[data-testid="stElementContainer"]:has(iframe[height="0"]),
            div[data-testid="stElementContainer"]:has(iframe[style*="height: 0px"]) {
                display: none !important;
                height: 0 !important;
                min-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            /* The deferred Bending summary binder must execute, so keep its
               iframe mounted while cancelling only the flex-row gap that its
               zero-height wrapper would otherwise add at the page tail. */
            div[data-testid="stElementContainer"]:has(
                iframe[srcdoc*="Try to find Streamlit tabs"]
            ) {
                height: 0 !important;
                min-height: 0 !important;
                margin: 0 0 -10.328125px !important;
                padding: 0 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        render_timing_mark("bending_page.runtime.presentation.summary.end")

    # Persist canonical bending state for the rest of the page (and next rerun)
    st.session_state["bending_state"] = canonical_state

    d = top_results["d"]

    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")

    cover_bot_local = cover_bot if cover_bot is not None else 40.0
    db_bot_local = db_bot if db_bot is not None else 20.0
    D_local = D if D is not None else 600.0

    d_eff = d
    if d_eff is None or (isinstance(d_eff, float) and math.isnan(d_eff)):
        d_eff = bottom_tension_effective_depth_fallback_mm(
            D_local,
            cover_bot_local,
            db_bot_local,
        )

    with inputs_placeholder.container():
        render_bending_inputs(
            st=st,
            engineering_state=page_engineering_state,
            mu_pos_star_kNm=Mu_pos_star,
            mu_neg_star_kNm=Mu_neg_star,
            sync_callbacks=sync_callbacks,
        )
    render_timing_mark("bending_page.runtime.presentation.inputs.end")

    with st.container(key="bending_post_inputs_calculation_stage"):
        with st.container():
            checks_snapshot = build_bending_checks_snapshot(
                page_snapshot=bending_page_snapshot,
                base_results=top_results,
                width_mm=b,
                overall_depth_mm=D,
                concrete_strength_mpa=fc,
                steel_yield_strength_mpa=fsy,
                concrete_modulus_mpa=Ec,
                steel_modulus_mpa=Es,
                positive_effective_depth_mm=d_eff,
            )

            with calc_blocks_container:
                render_bending_checks(st_module=st, checks=checks_snapshot)

            # --------------------------------------------------
            # Material stress–strain curves (concrete + steel), rendered below
            # the section diagrams together with the state selector.
            # --------------------------------------------------

    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()

# ============================
# MAIN GUARD
# ============================
if __name__ == "__main__":
    render_bending()
