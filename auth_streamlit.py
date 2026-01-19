import os
import streamlit as st
from supabase import create_client


def get_user_id_from_token() -> str:
    """
    Reads Supabase access token from URL query params and returns user.id.
    Stores result in st.session_state["user_id"].
    """
    if st.session_state.get("user_id"):
        return st.session_state["user_id"]

    # Streamlit query params (new API)
    qp = st.query_params
    token = qp.get("sb_access_token", "")
    if not token:
        return ""

    url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not anon_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY env vars.")

    sb = create_client(url, anon_key)

    # Validate token and fetch user
    res = sb.auth.get_user(token)
    user = getattr(res, "user", None) or (res.get("user") if isinstance(res, dict) else None)
    if not user:
        return ""

    user_id = user.id if hasattr(user, "id") else user.get("id", "")
    st.session_state["user_id"] = user_id
    return user_id
