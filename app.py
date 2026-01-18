import streamlit as st

from state_and_helpers import (
    init_shared_session_state,
    recalc_derived_values,
    update_results,
    compute_all_results,
    assert_shared_state_alive,
    hydrate_active_page_widgets_from_shared,
    begin_render_cycle,
    persist_state_snapshot,
    _shared_zero_tripwire,
    SHARED_DEFAULTS,
    DERIVED_KEYS,
    RESULT_KEYS,
    clear_user_edit_marker_each_run,
    end_of_render_cleanup,
    debug_tripwire_hook,
    watch_shared_key_writes,
    DEBUG_MODE,
)
import time
from persistence.save_to_dashboard import (
    get_context,
    export_state_for_saving,
    api_create_project,
    api_save_state,
    redirect_parent_to_project,
)

# 🔁 Import modules, not individual functions
import inputs_page
import bending_page
import shear_page
import creep
import shrinkage
import deflection
import crack_page
import sfd_bmd_page

# ---- page registry ----
PAGES = {
    "inputs": ("Inputs", inputs_page.render_inputs),
    "bending": ("Bending", bending_page.render_bending),
    "shear": ("Shear", shear_page.render_shear),
    "creep": ("Creep", creep.render_creep),
    "shrinkage": ("Shrinkage", shrinkage.render_shrinkage),
    "crack": ("Crack Control", crack_page.render_crack_control),
    "design": ("Design", sfd_bmd_page.render_sfd_bmd_page),
    "deflection": ("Deflection", deflection.render_deflection),
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


def main():
    # --- ARCHITECTURE LOCK: dev mode flag ---
    st.session_state.setdefault("_dev_mode", True)
    
    st.set_page_config(
        page_title="Concrete Beam Design",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

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
  padding-bottom: 6px !important;
  margin-bottom: 1rem !important;
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

    # ------------------------------------------------------------
    # Header row: title (left) + Save button (right)
    # ------------------------------------------------------------
    project_id, token, module = get_context()

    header_left, header_right = st.columns([0.7, 0.3], vertical_alignment="center")

    with header_left:
        st.title("Beam design")

    with header_right:
        actions_left, actions_right = st.columns([1, 1], vertical_alignment="center")

        with actions_left:
            if st.button("💾 Save", type="primary", use_container_width=True):
                if not token:
                    st.error("Open this page from the website so your login token is available.")
                else:
                    if project_id:
                        try:
                            payload = export_state_for_saving()
                            api_save_state(token, project_id, payload, schema_version=1)
                            st.toast("Saved", icon="✅")
                        except Exception as e:
                            st.error(f"Save failed: {e}")
                    else:
                        st.session_state["_show_save_modal"] = True

        with actions_right:
            from reporting.example_integration import render_pdf_button
            render_pdf_button()

    # Modal for first-time save (no project id yet)
    if st.session_state.get("_show_save_modal", False):
        with st.modal("Create project to save"):
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
                    if not name.strip():
                        st.error("Project name is required.")
                    else:
                        try:
                            new_id = api_create_project(token, name.strip(), module)
                            payload = export_state_for_saving()
                            api_save_state(token, new_id, payload, schema_version=1)

                            # Ensure future saves use this project and the parent URL has ?project=<id>
                            redirect_parent_to_project(new_id)

                            st.session_state["_show_save_modal"] = False
                            st.toast("Project created and saved", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Create/save failed: {e}")

    # Session restart banner (debug only)
    if DEBUG_MODE:
        if "_app_boot_count" not in st.session_state:
            st.session_state["_app_boot_count"] = 0
        st.session_state["_app_boot_count"] += 1
        
        if st.session_state["_app_boot_count"] == 1:
            st.warning("Session boot (fresh). If this appears mid-use, your session restarted.")
        
        # Debug mode toggle (only shown if env var is set)
        try:
            from src.debug.debug_flags import show_debug_toggle
            show_debug_toggle()
            
            # Cache control (only shown when debug mode enabled)
            from src.debug.cache_control import show_cache_control
            show_cache_control()
        except ImportError:
            # Debug module not available, skip
            pass
        
        # Debug checkpoints (track state changes)
        try:
            from src.debug.state_debug import snapshot_state, diff_snapshots, is_debug_enabled
            from state_and_helpers import DERIVED_KEYS, RESULT_KEYS
            if is_debug_enabled():
                # Checkpoint: after init_shared_session_state
                if "_debug_last_checkpoint" not in st.session_state:
                    st.session_state["_debug_last_checkpoint"] = {}
                checkpoint_keys = list(DERIVED_KEYS | RESULT_KEYS)[:20]  # Limit to first 20 keys
                current_snapshot = snapshot_state("after_init", checkpoint_keys)
                if st.session_state["_debug_last_checkpoint"]:
                    diff = diff_snapshots(st.session_state["_debug_last_checkpoint"], current_snapshot)
                    if diff:
                        if "_debug_checkpoints" not in st.session_state:
                            st.session_state["_debug_checkpoints"] = []
                        st.session_state["_debug_checkpoints"].append({
                            "label": "After init_shared_session_state",
                            "diff": diff,
                        })
                st.session_state["_debug_last_checkpoint"] = current_snapshot
        except (ImportError, NameError):
            # Debug module not available, skip
            pass
    

    # --- 1) Read URL param (page) and pre-set nav state BEFORE widget renders
    qp_page = st.query_params.get("page")
    if isinstance(qp_page, list):
        qp_page = qp_page[0] if qp_page else None

    # ✅ Only adopt URL -> nav when the URL page actually changes
    if qp_page in PAGES and st.session_state.get(LAST_QP_KEY) != qp_page:
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
            "",
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

    # Sidebar info (debug only)
    if DEBUG_MODE:
        st.sidebar.title("Session state")
        st.sidebar.markdown(
            "- Shared params via `init_shared_session_state()`\n"
            "- Widgets use TAB_KEYS + sync callbacks\n"
            "- Creep & shrinkage feed Deflection / Crack via `st.session_state`"
        )
        
        # DEBUG: Tripwire toggle (temporary - remove after fixing zero issue)
        debug_tripwire = st.sidebar.checkbox("DEBUG: Tripwire", value=True)
        if debug_tripwire:
            tripwire_data = st.session_state.get("_tripwire_last", {})
            st.sidebar.write("**Tripwire:**", tripwire_data)
        
        # DEBUG: Shared input mutations (show what changed and what was reverted)
        if st.sidebar.checkbox("DEBUG: Shared input mutations", value=True):
            changed = st.session_state.get("_debug_changed_shared_inputs", {})
            if changed:
                st.sidebar.write("**Changed shared inputs:**", changed)
            reverted = st.session_state.get("_debug_reverted_shared_inputs")
            if reverted:
                st.sidebar.error("⚠️ Reverted illegal render-time shared writes")
                st.sidebar.write(reverted)
            
            # Mass zeroing detector
            zeroed_count = st.session_state.get("_debug_zeroed_shared_count", 0)
            zeroed_sample = st.session_state.get("_debug_zeroed_shared_sample", [])
            if zeroed_count > 0:
                st.sidebar.error(f"⚠️ Mass zeroing detected: {zeroed_count} keys zeroed")
                st.sidebar.write("**Zeroed keys (sample):**", zeroed_sample)
        
        # DEBUG: Shared write audit trail
        if st.sidebar.checkbox("DEBUG: Shared write audit", value=False):
            audit_tail = st.session_state.get("_shared_write_audit", [])
            st.sidebar.write("**Shared write audit (last 20):**")
            st.sidebar.write(audit_tail[-20:])
        
        # DEBUG: Last sync attempt (prove TAB_KEYS mismatch)
        if st.sidebar.checkbox("DEBUG: Last sync attempt", value=False):
            last_sync = st.session_state.get("_debug_last_sync")
            if last_sync:
                st.sidebar.write("**Last sync attempt:**")
                st.sidebar.write(last_sync)
                if not last_sync.get("widget_present", True):
                    st.sidebar.error("⚠️ Widget missing during sync!")
        
        # DEBUG: Boot status (prove snapshot restore works)
        st.sidebar.markdown("### Boot Status")
        boot_id = st.session_state.get("_boot_id", "N/A")
        fresh_boot = st.session_state.get("_fresh_boot", False)
        restored_from_snapshot = st.session_state.get("_restored_from_snapshot", False)
        st.sidebar.write(f"**Boot ID:** `{boot_id[:8]}...`")
        st.sidebar.write(f"**Fresh Boot:** {fresh_boot}")
        st.sidebar.write(f"**Restored from Snapshot:** {restored_from_snapshot}")
        if fresh_boot and restored_from_snapshot:
            st.sidebar.success("✅ Snapshot restored on boot")
        elif fresh_boot and not restored_from_snapshot:
            st.sidebar.warning("⚠️ Fresh boot but no snapshot found")
        
        # DEBUG: Action keys verification (prove RESULT_KEYS contains action keys at runtime)
        actions_keys_ok = st.session_state.get("_debug_actions_keys_in_RESULT_KEYS", None)
        if actions_keys_ok is not None:
            if actions_keys_ok:
                st.sidebar.success("✅ Action keys in RESULT_KEYS")
            else:
                st.sidebar.error("❌ Action keys MISSING from RESULT_KEYS")
        
        # Debug State Inspector panel (only shown if debug mode is enabled)
        try:
            from src.debug.debug_panel import render_state_inspector
            render_state_inspector()
        except ImportError:
            # Debug module not available, skip
            pass

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
    st.session_state["_debug_state_tripwire"] = bool(DEBUG_MODE)
    # Startup probe removed: it was mutating shared state and causing widget resets.
    # debug_tripwire_hook(tag="STARTUP_PROBE_READONLY", page="app_start")
    if DEBUG_MODE:
        watch_shared_key_writes(tag="AFTER_INIT", page="app_start")
    
    # --- 4) Regression tripwire: verify shared state is alive (AFTER init)
    assert_shared_state_alive()
    
    # Debug: run invariant checks
    if DEBUG_MODE:
        try:
            from src.debug.state_debug import assert_invariants
            assert_invariants()
        except ImportError:
            # Debug module not available, skip
            pass
    
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
    
    if DEBUG_MODE and st.session_state.get("_debug_state_tripwire", False):
        from state_and_helpers import _append_debug_log
        _append_debug_log(f"RENDER boot={st.session_state.get('_boot_id')} page={selected_slug}")
    
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
    if DEBUG_MODE:
        debug_tripwire_hook(tag="AFTER_PAGE_RENDER", page=selected_slug)
        watch_shared_key_writes(tag="AFTER_PAGE_RENDER", page=selected_slug)
        try:
            from state_and_helpers import write_final_session_state_check
            write_final_session_state_check("final_session_state_check.json")
        except Exception:
            pass
        
        # Write widget contract audit to debug file automatically
        try:
            from state_and_helpers import write_widget_contract_audit_to_file, get_sync_callbacks
            sync_callbacks = get_sync_callbacks()
            audit_file = write_widget_contract_audit_to_file(sync_callbacks, filename=f"widget_contract_audit_{selected_slug}.txt")
            # Store file path in session state for reference (optional)
            st.session_state["_last_audit_file"] = audit_file
        except Exception:
            # Don't break the app if audit writing fails
            pass
    
    # Immediately after render_fn(): detect shared-input changes
    shared_after = {k: st.session_state.get(k) for k in SHARED_DEFAULTS.keys()}
    
    changed_shared = {
        k: (shared_before.get(k), shared_after.get(k))
        for k in SHARED_DEFAULTS.keys()
        if shared_before.get(k) != shared_after.get(k)
    }
    
    # Mass zeroing detector
    zeroed = [
        k for k, (old, new) in changed_shared.items()
        if (old not in (0, 0.0, None, "")) and (new in (0, 0.0))
    ]
    st.session_state["_debug_zeroed_shared_count"] = len(zeroed)
    st.session_state["_debug_zeroed_shared_sample"] = zeroed[:30]
    
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
    if changed_shared and (not wipe_mode) and (not allowed_due_to_user):
        # revert the illegal changes
        for k, (old, _new) in changed_shared.items():
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
    if DEBUG_MODE:
        _shared_zero_tripwire("AFTER render_fn")
    
    # Step 6: Persist snapshot after page render so future wipes can recover
    persist_state_snapshot()

    
    # IMPORTANT: Do NOT do app-level widget→shared syncing.
    # Shared state must only update via on_change callbacks.
    # App-level syncing can copy stale navigation zeros into shared and wipe inputs.
    
    # NOTE: compute_all_results() already handles derived + results updates.


if __name__ == "__main__":
    main()
