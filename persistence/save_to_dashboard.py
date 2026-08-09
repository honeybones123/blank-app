import json
import streamlit as st

from ui.streamlit_iframe import render_trusted_iframe

from state_and_helpers import (
    SHARED_DEFAULTS,
    build_beam_project_payload,
    load_beam_project_payload,
    persist_active_beam_from_shared,
    reset_beam_project_to_single_default_if_missing,
    update_active_beam_summary_from_results,
)


def _qp(name: str) -> str:
    value = st.query_params.get(name, "")
    return (value[0] if isinstance(value, list) and value else str(value or "")).strip()


def _set_project_qp(project_id: str):
    st.query_params["project"] = project_id


def get_context():
    project_id = _qp("project")
    token = _qp("token")
    module = _qp("module") or "Beam"
    return project_id, token, module


def export_state_for_saving() -> dict:
    """
    Export ONLY canonical shared inputs.
    Do NOT persist widget keys (inputs_*, bending_*, etc) or derived/results keys.
    Those must be rehydrated/recomputed from shared inputs after load.
    """
    import streamlit as st
    from state_and_helpers import SHARED_DEFAULTS

    # Explicit save must capture the latest active-beam inputs before building the project payload.
    persist_active_beam_from_shared()
    update_active_beam_summary_from_results()

    shared = {}
    for k, default_v in SHARED_DEFAULTS.items():
        shared[k] = st.session_state.get(k, default_v)

    return {
        "schema_version": 2,
        "shared": shared,
        "beam_project": build_beam_project_payload(),
        "ui_state": {
            "last_active_page": str(
                st.session_state.get("_last_design_page_slug")
                or st.session_state.get("page_slug")
                or "inputs"
            ),
        },
    }


def _clear_non_shared_session_keys():
    """
    Remove all non-shared keys so old project payloads can't override
    computed results/caches in the current version.
    """
    shared_keys = set(SHARED_DEFAULTS.keys())

    # Allowlist keys you *never* want wiped (navigation, auth, etc.)
    allow_prefixes = ("nav_", "auth_", "page_")
    allow_keys = {
        "page_slug",
        "nav_page_slug",
        "active_project_id",
        "active_project_name",
        "_active_project_loaded_id",
        "_active_page_slug",
        "sb_user",
        "user_id",
        "module",
    }

    for k in list(st.session_state.keys()):
        if k in shared_keys:
            continue
        if k in allow_keys:
            continue
        if any(k.startswith(p) for p in allow_prefixes):
            continue
        # wipe everything else (results, derived, bending_*, shear_*, etc.)
        del st.session_state[k]


def apply_project_payload(payload: dict) -> None:
    """
    Apply project payload into shared keys only.

    Supports:
    - New format: {"schema_version": 2, "shared": {...}, "beam_project": {...}}
    - Old format: {"schema_version": 1, "shared": {...}}
    - Legacy format: {<shared_key>: value, ...}
    """
    import streamlit as st
    from state_and_helpers import (
        SHARED_DEFAULTS,
        WORKSPACE_IDENTITY_KEY,
        WORKSPACE_ORIGIN_KEY,
        WORKSPACE_ORIGIN_LOADED_FILE,
        set_shared,
    )

    if not isinstance(payload, dict):
        return

    src = payload.get("shared") if isinstance(payload.get("shared"), dict) else payload

    for k, default_v in SHARED_DEFAULTS.items():
        if k in src:
            set_shared(k, src[k], source="project_load")
        elif k not in st.session_state:
            set_shared(k, default_v, source="project_load_default")

    beam_project_payload = payload.get("beam_project")
    if isinstance(beam_project_payload, dict):
        load_beam_project_payload(beam_project_payload)
    else:
        reset_beam_project_to_single_default_if_missing()

    ui_state = payload.get("ui_state")
    if isinstance(ui_state, dict):
        last_active_page = str(ui_state.get("last_active_page") or "").strip().lower()
        if last_active_page in {
            "inputs", "design", "bending", "shear", "creep",
            "shrinkage", "crack", "deflection",
        }:
            st.session_state["_last_design_page_slug"] = last_active_page
            st.session_state["_pending_nav_page_slug"] = last_active_page

    st.session_state.pop(WORKSPACE_IDENTITY_KEY, None)
    st.session_state[WORKSPACE_ORIGIN_KEY] = WORKSPACE_ORIGIN_LOADED_FILE


def redirect_parent_to_project(project_id: str):
    """
    If Streamlit is embedded in a parent Next.js page, this updates the parent URL
    to include ?project=<id> so future saves target the same project.
    Safe no-op if not embedded.
    """
    render_trusted_iframe(st,
        f"""
        <script>
          try {{
            const p = window.parent;
            if (p && p.location) {{
              const u = new URL(p.location.href);
              u.searchParams.set('project', '{project_id}');
              p.location.href = u.toString();
            }}
          }} catch (e) {{}}
        </script>
        """,
        height=0,
    )
    _set_project_qp(project_id)
