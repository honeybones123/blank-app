import json
import streamlit as st
import streamlit.components.v1 as components

from state_and_helpers import SHARED_DEFAULTS, DERIVED_KEYS, RESULT_KEYS


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

    results_dict = st.session_state.get("results", {})
    try:
        json.dumps(results_dict)
    except Exception:
        results_dict = {}

    return {
        "version": "v1",
        "shared": _safe_subset(SHARED_DEFAULTS.keys()),
        "derived": _safe_subset(DERIVED_KEYS),
        "results": _safe_subset(RESULT_KEYS),
        "results_dict": results_dict,
    }


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
