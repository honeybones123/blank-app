import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib
import streamlit as st

st.set_page_config(
    page_title="Concrete Beam Design",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from widgets_helpers import apply_global_widget_css, apply_calcbox_css, info_i_button
from state_and_helpers import hc_try

hc_try("css.apply_global_widget_css", apply_global_widget_css)
hc_try("css.apply_calcbox_css", apply_calcbox_css)

from state_and_helpers import (
    init_shared_session_state,
    derive_design_actions,
    load_active_beam_into_shared,
    load_proxies_from_active_set,
    recalc_derived_values,
    update_results,
    compute_all_results,
    assert_shared_state_alive,
    hydrate_active_page_widgets_from_shared,
    begin_render_cycle,
    persist_state_snapshot,
    SHARED_DEFAULTS,
    TAB_KEYS,
    DERIVED_KEYS,
    RESULT_KEYS,
    tripwire_no_falsy_defaulting,
    clear_user_edit_marker_each_run,
    end_of_render_cleanup,
)
import time
from persistence.save_to_dashboard import (
    get_context,
    export_state_for_saving,
    apply_project_payload,
    redirect_parent_to_project,
)
from projects_store import create_project, update_project, load_project
from auth_bridge import ensure_logged_in_state

# 🔁 Import modules, not individual functions
import inputs_page
import bending_page
import shear_page
import creep
import shrinkage
import deflection
import crack_page
import sfd_bmd_page


def _render_deflection_page():
    renderer = getattr(deflection, "render_deflection", None)
    if callable(renderer):
        return renderer()

    # Hot-reload can occasionally leave a stale partial module object around.
    refreshed_module = importlib.reload(deflection)
    refreshed_renderer = getattr(refreshed_module, "render_deflection", None)
    if callable(refreshed_renderer):
        return refreshed_renderer()

    raise AttributeError("module 'deflection' has no attribute 'render_deflection'")

# ---- page registry ----
PAGES = {
    "inputs": ("Inputs", inputs_page.render_inputs),
    "design": ("Design", sfd_bmd_page.render_sfd_bmd_page),
    "bending": ("Bending", bending_page.render_bending),
    "shear": ("Shear", shear_page.render_shear),
    "creep": ("Creep", creep.render_creep),
    "shrinkage": ("Shrinkage", shrinkage.render_shrinkage),
    "crack": ("Crack Control", crack_page.render_crack_control),
    "deflection": ("Deflection", _render_deflection_page),
}

SLUGS = list(PAGES.keys())
LABELS = [PAGES[s][0] for s in SLUGS]

NAV_KEY = "nav_page_slug"  # stores the slug, e.g. "shear"
LAST_QP_KEY = "last_qp_page_seen"   # local-only UI state


def set_query_params_merge(**updates):
    """Update query params without clearing (avoids session/connection resets)."""
    # Apply updates
    for k, v in updates.items():
        if v is None:
            # remove if present
            try:
                del st.query_params[k]
            except Exception:
                pass
        else:
            st.query_params[k] = v


def _get_user_id() -> str:
    ensure_logged_in_state()
    user = st.session_state.get("sb_user")
    if user:
        return user.id if hasattr(user, "id") else user.get("id", "")
    try:
        from auth_streamlit import get_user_id_from_token
    except Exception:
        return ""
    return get_user_id_from_token()


def _render_create_project_form(user_id: str, module: str):
    name = st.text_input(
        "Project name",
        placeholder="e.g. SRL East – RC Beam over Station Box",
    )
    st.caption("This creates a project so you can open it later from your dashboard.")
    cA, cB = st.columns([1, 1])
    with cA:
        if st.button("Cancel", use_container_width=True):
            st.session_state["_show_save_modal"] = False
            st.rerun()
    with cB:
        if st.button("Create & Save", type="primary", use_container_width=True):
            if not user_id:
                st.error("You must be logged in to save projects.")
                return
            if not name.strip():
                st.error("Project name is required.")
            else:
                try:
                    payload = export_state_for_saving()
                    row = create_project(
                        user_id=user_id,
                        name=name.strip(),
                        payload=payload,
                        meta={"module": module},
                    )
                    new_id = row.get("id")

                    # Ensure future saves use this project and the parent URL has ?project=<id>
                    if new_id:
                        redirect_parent_to_project(new_id)
                        st.session_state["active_project_id"] = new_id
                        st.session_state["active_project_name"] = name.strip()

                    st.session_state["_show_save_modal"] = False
                    st.toast("Project created and saved", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Create/save failed: {e}")


def main():
    # --- ARCHITECTURE LOCK: dev mode flag ---
    st.session_state.setdefault("_dev_mode", True)
    ensure_logged_in_state()

    # --- CSS styling for top navigation (make radio look like Streamlit tabs) ---
    st.markdown("""
<style>
/* ==========================================================
   TOP PAGE NAV ONLY (matches Streamlit st.tabs style)
   Scoped to the container that contains #page-nav-anchor
   ========================================================== */

div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"]{
  display:flex !important;
  align-items:center !important;
  gap:18px !important;
  border-bottom: 1px solid rgba(49,51,63,0.20) !important;
  padding-bottom: 4px !important;
  margin-bottom: 0.15rem !important;
}

/* tab label */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label{
  margin:0 !important;
  padding: 6px 2px !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  cursor: pointer !important;
  font-weight: 500 !important;
}

/* remove the radio circle/control (robust across Streamlit builds) */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label svg,
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label [role="img"],
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label input[type="radio"],
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label > div:first-child,
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label > span:first-child{
  display:none !important;
}

/* active underline (tab selected) */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label:has(input:checked),
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label[aria-checked="true"]{
  border-bottom: 2px solid #ff4b4b !important;
  font-weight: 600 !important;
}

/* prevent "button hover" feel */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label:hover{
  background: transparent !important;
}

/* tighten inner wrappers */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label *{
  margin:0 !important;
  padding:0 !important;
}
</style>
""", unsafe_allow_html=True)

    def _render_project_header_compact():
        name = st.session_state.get("active_project_name") or "Unsaved / New project"
        st.caption(f"**Project:** {name}")

    # ------------------------------------------------------------
    # Header row: title (left) + Save button (right)
    # ------------------------------------------------------------
    project_id, token, module = get_context()
    user_id = _get_user_id()
    if project_id:
        st.session_state["active_project_id"] = project_id

    if project_id and user_id:
        needs_name = not st.session_state.get("active_project_name")
        loaded_for_id = st.session_state.get("_active_project_loaded_id")
        if needs_name or loaded_for_id != project_id:
            try:
                project_row = load_project(project_id=project_id, user_id=user_id)
                st.session_state["active_project_id"] = project_row.get("id") or project_id
                st.session_state["active_project_name"] = project_row.get("name") or "Untitled project"
                st.session_state["_active_project_loaded_id"] = project_row.get("id") or project_id
                try:
                    payload = project_row.get("payload") or {}
                    # 🔒 Prevent snapshot restore from overwriting loaded project state
                    from state_and_helpers import (
                        DISABLE_SNAPSHOT_RESTORE_KEY,
                        clear_cached_and_widget_restore_keys,
                    )

                    st.session_state[DISABLE_SNAPSHOT_RESTORE_KEY] = True
                    clear_cached_and_widget_restore_keys()

                    apply_project_payload(payload)

                    # After applying a project payload, snapshot is now “dirty” state.
                    st.session_state["_dirty"] = True
                    st.session_state["_dirty_reason"] = "Loaded project payload"
                    # Recompute outputs from shared inputs (never trust saved results)
                    recalc_derived_values()
                    update_results()
                except Exception:
                    pass
            except Exception:
                st.session_state["_active_project_loaded_id"] = project_id

    _render_project_header_compact()

    header_left, header_right = st.columns([0.65, 0.35], vertical_alignment="center")

    with header_left:
        st.title("Beam design")

    with header_right:
        # --- Top right actions row (Save + Generate PDF on same level) ---
        left, right = st.columns([1.0, 9.0], gap="large")

        with right:
            st.session_state.setdefault("report_mode", "standard")
            report_mode = str(st.session_state.get("report_mode", "standard")).strip().lower()
            if report_mode not in {"standard", "detailed"}:
                report_mode = "standard"
                st.session_state["report_mode"] = report_mode

            # Equal width for Save and PDF; trailing spacer keeps both slightly narrower
            # than filling the full row (same share as the original Save-only column).
            c_save, c_pdf, c_pdf_opts, _ = st.columns([3.0, 3.0, 0.6, 2.8], gap="small")

            with c_save:
                if st.button("💾 Save", type="primary", use_container_width=True):
                    if not user_id:
                        st.error("You must be logged in to save projects.")
                        st.stop()
                    else:
                        if project_id:
                            try:
                                payload = export_state_for_saving()
                                update_project(
                                    project_id=project_id,
                                    user_id=user_id,
                                    payload=payload,
                                    meta={"module": module},
                                )
                                st.toast("Saved", icon="✅")
                            except Exception as e:
                                st.error(f"Save failed: {e}")
                        else:
                            st.session_state["_show_save_modal"] = True

            with c_pdf:
                from reporting.example_integration import render_pdf_button
                render_pdf_button(detail_level=report_mode)

            with c_pdf_opts:
                with info_i_button(help_text="Report options") if hasattr(st, "popover") else st.expander("i", expanded=False):
                    st.selectbox(
                        "Report mode",
                        options=["standard", "detailed"],
                        key="report_mode",
                        format_func=lambda mode: "Standard Report" if mode == "standard" else "Detailed Report",
                    )
                    st.text_input(
                        "Company name (optional)",
                        key="report_company_name",
                        placeholder="Your company name",
                    )
                    report_logo = st.file_uploader(
                        "Upload company logo (optional)",
                        type=["png", "jpg", "jpeg"],
                        key="report_company_logo_upload",
                        help="Used for the current report session only. Not saved to the project.",
                    )
                    if report_logo is not None:
                        st.session_state["report_company_logo_bytes"] = report_logo.getvalue()
                        st.session_state["report_company_logo_name"] = report_logo.name
                        st.session_state["report_company_logo_type"] = report_logo.type
                        st.image(report_logo, width=120)
                    else:
                        st.session_state["report_company_logo_bytes"] = None
                        st.session_state["report_company_logo_name"] = None
                        st.session_state["report_company_logo_type"] = None

    # Modal for first-time save (no project id yet)
    if st.session_state.get("_show_save_modal", False):
        # --- Create project UI (compatible with Streamlit versions without st.modal) ---
        if hasattr(st, "modal"):
            with st.modal("Create project to save"):
                _render_create_project_form(user_id, module)
        else:
            with st.expander("Create project to save", expanded=True):
                _render_create_project_form(user_id, module)

    

    # --- 1) Read URL param (page) and pre-set nav state BEFORE widget renders
    qp_page = st.query_params.get("page")
    if isinstance(qp_page, list):
        qp_page = qp_page[0] if qp_page else None

    # ✅ Adopt URL -> nav when the URL page slug changed since last sync, OR when
    # ?jump= is present and nav still disagrees (summary link landed while radio lagged).
    # Never adopt on nav_slug != qp_page alone: after a tab change the widget updates
    # before step 3 rewrites ?page=, and we'd overwrite the new selection with the old URL.
    if qp_page in PAGES:
        last_seen = st.session_state.get(LAST_QP_KEY)
        nav_slug = st.session_state.get(NAV_KEY)
        jump_pending = "jump" in st.query_params
        if last_seen != qp_page or (jump_pending and nav_slug != qp_page):
            st.session_state[NAV_KEY] = qp_page
            st.session_state[LAST_QP_KEY] = qp_page

    # ✅ If no valid page in URL, still ensure defaults exist
    if NAV_KEY not in st.session_state:
        st.session_state[NAV_KEY] = "inputs"

    # --- 2) TOP "tabs" (same logic, just container + anchor for CSS targeting)
    nav_container = st.container()
    with nav_container:
        st.markdown('<div id="page-nav-anchor"></div>', unsafe_allow_html=True)

        selected_slug = st.radio(
            "Navigation",
            options=SLUGS,
            horizontal=True,
            key=NAV_KEY,
            format_func=lambda s: PAGES[s][0],  # Display label but store slug
            label_visibility="collapsed",
        )
        st.session_state["_active_page_slug"] = selected_slug

    # --- 3) Sync URL ONLY if it differs (prevents "stuck on bending" loops)
    # ✅ If a jump is present, DO NOT touch query params at all.
    if "jump" not in st.query_params:
        if st.query_params.get("page") != selected_slug:
            set_query_params_merge(page=selected_slug)
            st.session_state[LAST_QP_KEY] = selected_slug

    # ============================================================
    # PHASE 1: ROUTER-OWNED LIFECYCLE (matches State Lab ordering)
    # ============================================================
    # Enforce exact render pipeline order:
    # 1. init_shared_session_state()
    # 2. set current slug into st.session_state["page_slug"]
    # 3. hydrate_active_page_widgets_from_shared(selected_slug)
    # 4. begin_render_cycle()
    # 5. render page function
    # 6. persist_state_snapshot()
    # ============================================================

    # Step 1: Initialize shared state (restores any dropped widget keys from cache or shared keys)
    # Note: migrate_time_defaults_once() is called inside init_shared_session_state() after snapshot restore
    init_shared_session_state()
    # Apply stored active-beam params into shared before design resolution and widget hydration.
    load_active_beam_into_shared()
    load_proxies_from_active_set()
    derive_design_actions()
    
    # --- 4) Regression tripwire: verify shared state is alive (AFTER init)
    assert_shared_state_alive()
    tripwire_no_falsy_defaulting()
    
    
    # Force-hydrate time widgets from shared BEFORE any page widgets render
    from state_and_helpers import force_hydrate_time_widgets_from_shared
    st.session_state["_sync_lock"] = True
    try:
        force_hydrate_time_widgets_from_shared()
    finally:
        st.session_state["_sync_lock"] = False
    
    # Clear user edit markers at start of each rerun (prevents stale exemptions)
    clear_user_edit_marker_each_run()
    
    
    # Step 2: Set current slug into session state (for hydration and tracking)
    st.session_state["page_slug"] = selected_slug
    st.session_state["_active_page_slug"] = selected_slug  # Keep for backward compatibility
    
    
    # ============================================================
    # SHARED INPUT MUTATION GUARD (prevents pages from stomping shared inputs during render)
    # ============================================================
    # --- DEBUG/SAFETY: track shared INPUT mutations during render ---
    shared_before = {k: st.session_state.get(k) for k in SHARED_DEFAULTS.keys()}
    last_ts = float(st.session_state.get("_last_user_edit_ts") or 0.0)
    last_shared = st.session_state.get("_last_user_shared_key")
    recent_user_edit = (time.time() - last_ts) < 0.5
    wipe_mode = bool(st.session_state.get("_wipe_recovery_mode"))
    
    prev = st.session_state.get("_prev_page_slug")
    page_changed = (prev is not None and prev != selected_slug)
    st.session_state["_prev_page_slug"] = selected_slug

    # Hydrate BEFORE any widgets render (prevents stale widget keys from clobbering shared)
    st.session_state["_sync_lock"] = True
    try:
        hydrate_active_page_widgets_from_shared(
            selected_slug,
            force_on_restore=True,
            force_on_page_change=page_changed,
        )
    finally:
        st.session_state["_sync_lock"] = False

    # ============================================================
    # GLOBAL COMPUTE PIPELINE (runs BEFORE page render)
    # ============================================================
    # Ensures diagrams + calc boxes are correct immediately, without visiting other pages.
    if "_computed_once" not in st.session_state:
        st.session_state["_computed_once"] = False

    if st.session_state.get("_dirty") or not st.session_state["_computed_once"]:
        st.session_state["_dirty"] = False
        st.session_state["_computed_once"] = True
        try:
            compute_all_results()
        except Exception:
            # Never break UI due to compute; debug can inspect results keys
            pass

    # Step 4: Begin render cycle (ensures rendered widget tracking is per-run)
    from widgets_helpers import clear_rendered_widget_keys
    clear_rendered_widget_keys()
    begin_render_cycle()
    
    # Step 5: Render selected page (widgets register themselves during render)
    # Pages must NOT call init_shared_session_state() or hydrate themselves
    # (See state_and_helpers.py banner: "PAGE FILE RULES (router-owned lifecycle)")
    PAGES[selected_slug][1]()
    end_of_render_cleanup()

    # Debug guard: verify design-mode actions stay in sync with SFD/BMD outputs
    if st.session_state.get("actions_mode", "manual") == "design":
        sfd_M = st.session_state.get("sfd_Mmax_abs_kNm")
        sfd_V = st.session_state.get("sfd_Vmax_abs_kN")
        mu = st.session_state.get("Mu_star")
        mu_kNm = st.session_state.get("Mu_star_kNm")
        vu = st.session_state.get("Vu_star")
        mismatch = {}
        if sfd_M is not None and mu is not None and abs(float(mu) - float(sfd_M)) > 1e-6:
            mismatch["Mu_star"] = {"expected": sfd_M, "actual": mu}
        if sfd_M is not None and mu_kNm is not None and abs(float(mu_kNm) - float(sfd_M)) > 1e-6:
            mismatch["Mu_star_kNm"] = {"expected": sfd_M, "actual": mu_kNm}
        if sfd_V is not None and vu is not None and abs(float(vu) - float(sfd_V)) > 1e-6:
            mismatch["Vu_star"] = {"expected": sfd_V, "actual": vu}
        st.session_state["_debug_design_actions_mismatch"] = mismatch
    
    # Immediately after render_fn(): detect shared-input changes
    shared_after = {k: st.session_state.get(k) for k in SHARED_DEFAULTS.keys()}
    
    changed_shared = {
        k: (shared_before.get(k), shared_after.get(k))
        for k in SHARED_DEFAULTS.keys()
        if shared_before.get(k) != shared_after.get(k)
    }

    # Show what changed (debug)
    st.session_state["_debug_changed_shared_inputs"] = changed_shared
    
    # Stricter guard: only allow shared-input changes if:
    # - wipe recovery mode, OR
    # - the change set is small (≤ 2 keys), AND
    # - the changed key matches _last_user_shared_key, AND
    # - it happened very recently (< 0.5s)
    allowed_due_to_user = False
    if recent_user_edit and last_shared:
        # Allow only the shared key the user actually edited (plus maybe one derived "paired" input)
        allowed_keys = {last_shared}
        changed_keys = set(changed_shared.keys())
        if changed_keys.issubset(allowed_keys) and len(changed_keys) <= 2:
            allowed_due_to_user = True
    
    # Block illegal render-time writes to shared INPUTS
    _shared_input_guard_reverted = bool(
        changed_shared and (not wipe_mode) and (not allowed_due_to_user)
    )
    if _shared_input_guard_reverted:
        # revert the illegal changes
        for k, (old, _new) in changed_shared.items():
            if k in TAB_KEYS:
                continue
            st.session_state[k] = old
        st.session_state["_debug_reverted_shared_inputs"] = changed_shared
        st.session_state["_debug_last_revert_tag"] = f"REVERTED {len(changed_shared)} keys on {selected_slug}"
        try:
            from state_and_helpers import _write_sync_trace_line
            _write_sync_trace_line(
                f"ROUTER_REVERT page={selected_slug} keys={list(changed_shared.keys())[:20]} count={len(changed_shared)}"
            )
        except Exception:
            pass

    # Tripwire: detect shared keys that got zeroed during render

    # Step 6: Persist snapshot after page render so future wipes can recover
    persist_state_snapshot(reset_manual_action_touch_latch=True)

    
    # IMPORTANT: Do NOT do app-level widget→shared syncing.
    # Shared state must only update via on_change callbacks.
    # App-level syncing can copy stale navigation zeros into shared and wipe inputs.
    
    # NOTE: compute_all_results() already handles derived + results updates.


if __name__ == "__main__":
    main()
