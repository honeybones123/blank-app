import os
import streamlit as st
from supabase import create_client


def get_supabase_admin():
    url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not service_key:
        return None
    return create_client(url, service_key)


def resolve_user_from_query_param():
    token = st.query_params.get("sb_access_token")
    if not token:
        return None

    sb = get_supabase_admin()
    if sb is None:
        return None

    try:
        resp = sb.auth.get_user(token)
        return getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
    except Exception:
        return None


def ensure_logged_in_state():
    if st.session_state.get("sb_user") is not None:
        return

    user = resolve_user_from_query_param()
    st.session_state["sb_user"] = user
    if user:
        user_id = user.id if hasattr(user, "id") else user.get("id", "")
        if user_id:
            st.session_state["user_id"] = user_id
