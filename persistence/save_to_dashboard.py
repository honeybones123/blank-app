import os
import json
import requests
import streamlit as st
import streamlit.components.v1 as components


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


def next_base_url() -> str:
    # Set this in your Streamlit env for prod; default works for local Next dev
    return os.environ.get("NEXT_BASE_URL", "http://localhost:3000").rstrip("/")


def export_state_for_saving() -> dict:
    """
    Export ONLY JSON-serializable session_state keys.
    Later you can tighten this to just SHARED_DEFAULTS + module inputs.
    """
    out = {}
    for k, v in st.session_state.items():
        if str(k).startswith("_"):  # skip internal app/router keys
            continue
        try:
            json.dumps(v)
            out[k] = v
        except Exception:
            pass
    return out


def api_create_project(token: str, name: str, module: str) -> str:
    r = requests.post(
        f"{next_base_url()}/api/project/create",
        json={"name": name, "module": module},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["projectId"]


def api_save_state(token: str, project_id: str, state: dict, schema_version: int = 1):
    r = requests.post(
        f"{next_base_url()}/api/project/save",
        json={"project": project_id, "state": state, "schema_version": schema_version},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json() if r.content else {}


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
