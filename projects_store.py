from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase_client import get_supabase, projects_table_name
import streamlit as st


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_project(
    *,
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sb = get_supabase()
    table = projects_table_name()

    # --- GUARANTEE projects.module is set (DB column is NOT NULL) ---
    def _resolve_project_module(payload=None, meta=None):
        payload = payload or {}
        meta = meta or {}

        # Prefer explicit module values, fall back to session_state, then Beam
        return (
            payload.get("module")
            or meta.get("module")
            or st.session_state.get("module")
            or "Beam"
        )

    module_value = _resolve_project_module(payload=payload, meta=meta)

    row = {
        "user_id": user_id,
        "name": name,
        "payload": payload,
        "meta": meta or {},
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    # IMPORTANT: enforce module LAST so merges can't overwrite it to None
    row["module"] = module_value
    print("SAVE projects.module =", row.get("module"))

    res = sb.table(table).insert(row).execute()
    if not res.data:
        raise RuntimeError(f"Supabase insert failed: {getattr(res, 'error', None)}")
    return res.data[0]


def update_project(
    *,
    project_id: str,
    user_id: str,
    name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sb = get_supabase()
    table = projects_table_name()

    # --- GUARANTEE projects.module is set (DB column is NOT NULL) ---
    def _resolve_project_module(payload=None, meta=None):
        payload = payload or {}
        meta = meta or {}

        # Prefer explicit module values, fall back to session_state, then Beam
        return (
            payload.get("module")
            or meta.get("module")
            or st.session_state.get("module")
            or "Beam"
        )

    module_value = _resolve_project_module(payload=payload, meta=meta)

    patch = {"updated_at": _now_iso()}
    if name is not None:
        patch["name"] = name
    if payload is not None:
        patch["payload"] = payload
    if meta is not None:
        patch["meta"] = meta
    # IMPORTANT: enforce module LAST so merges can't overwrite it to None
    patch["module"] = module_value
    print("SAVE projects.module =", patch.get("module"))

    res = (
        sb.table(table)
        .update(patch)
        .eq("id", project_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not res.data:
        raise RuntimeError(f"Supabase update failed: {getattr(res, 'error', None)}")
    return res.data[0]


def load_project(*, project_id: str, user_id: str) -> Dict[str, Any]:
    sb = get_supabase()
    table = projects_table_name()

    res = (
        sb.table(table)
        .select("*")
        .eq("id", project_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not res.data:
        raise RuntimeError(f"Supabase load failed: {getattr(res, 'error', None)}")
    return res.data
