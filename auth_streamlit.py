import os
import streamlit as st
from supabase import create_client
from supabase_auth.errors import AuthApiError


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
        return ""

    sb = create_client(url, anon_key)

    # Validate token and fetch user
    try:
        res = sb.auth.get_user(token)
    except AuthApiError as e:
        msg = str(e).lower()
        if "token is expired" in msg or "expired" in msg:
            st.session_state.pop("access_token", None)
            st.session_state.pop("token", None)
            st.warning("Your session expired. Please log in again.")
            st.stop()
        raise
    user = getattr(res, "user", None) or (res.get("user") if isinstance(res, dict) else None)
    if not user:
        return ""

    user_id = user.id if hasattr(user, "id") else user.get("id", "")
    st.session_state["user_id"] = user_id
    return user_id
