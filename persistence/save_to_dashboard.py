import json
import streamlit as st
import streamlit.components.v1 as components

from state_and_helpers import SHARED_DEFAULTS


def _qp(name: str) -> str:
    # Streamlit query params API varies by version; support both
    try:
        v = st.query_params.get(name, "")
        return (v[0] if isinstance(v, list) and v else str(v or "")).strip()
    except Exception:
        qp = st.experimental_get_query_params()
        return str(qp.get(name, [""])[0] if name in qp else "").strip()


def _set_project_qp(project_id: str):
    try:
        st.query_params["project"] = project_id
    except Exception:
        st.experimental_set_query_params(project=project_id)


def get_context():
    project_id = _qp("project")
    token = _qp("token")
    module = _qp("module") or "Beam"
    return project_id, token, module


def export_state_for_saving() -> dict:
    """
    Export contract-safe session_state keys for saving.
    """
    def _safe_subset(keys):
        out = {}
        for k in keys:
            v = st.session_state.get(k)
            try:
                json.dumps(v)
                out[k] = v
            except Exception:
                pass
        return out

    return {
        "schema_version": 1,
        "shared": _safe_subset(SHARED_DEFAULTS.keys()),
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


def apply_project_payload(payload: dict):
    """
    Apply a saved project payload to session state (shared keys only).
    Wipes computed/results keys and recomputes derived/results.
    """
    from state_and_helpers import recalc_derived_values, update_results

    # 0) Ensure defaults exist so missing keys don't become None/0
    for k, v in SHARED_DEFAULTS.items():
        st.session_state.setdefault(k, v)

    saved_shared = payload.get("shared", {}) if isinstance(payload, dict) else {}

    # 1) Apply only known shared keys
    for k, v in saved_shared.items():
        if k in SHARED_DEFAULTS:
            st.session_state[k] = v

    # 2) Backfill any new shared keys (for old projects)
    for k, v in SHARED_DEFAULTS.items():
        st.session_state.setdefault(k, v)

    # 3) Wipe computed/results/cache keys so old saves can’t override them
    _clear_non_shared_session_keys()

    # 4) Tripwire (temporary)
    if "results" in st.session_state:
        st.error("Tripwire: results key survived load - should have been wiped")

    # 4) Recompute everything
    recalc_derived_values()
    update_results()

    st.rerun()


def redirect_parent_to_project(project_id: str):
    """
    If Streamlit is embedded in a parent Next.js page, this updates the parent URL
    to include ?project=<id> so future saves target the same project.
    Safe no-op if not embedded.
    """
    components.html(
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
