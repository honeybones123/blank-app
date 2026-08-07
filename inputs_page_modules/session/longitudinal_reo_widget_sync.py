"""Longitudinal reinforcement widget mirror coordination."""

from __future__ import annotations

from typing import Any, Callable


_AUDIT_ROWS = (1, 2)
_RESEED_ROWS = (1, 2, 3, 4)
_ROW_FIELDS = ("mode", "bars", "spacing", "dia")


def is_inputs_longitudinal_reo_widget_key(widget_key: str | None) -> bool:
    wk = str(widget_key or "").strip()
    if wk in {"inputs_bot_row_count", "inputs_top_row_count"}:
        return True
    return wk.startswith(("inputs_bot_row_", "inputs_top_row_"))


def longitudinal_reo_widget_audit_snapshot(
    *,
    state: dict,
    label: str,
    copy_deepcopy_fn: Callable[[Any], Any],
    agent_debug_log_fn: Callable[..., None],
) -> dict:
    shared_row_model: dict[str, object] = {}
    legacy_mirror: dict[str, object] = {}
    inputs_widget_mirror: dict[str, object] = {}

    for section in ("bot", "top"):
        shared_row_model[f"{section}_row_count"] = state.get(f"{section}_row_count")
        inputs_widget_mirror[f"inputs_{section}_row_count"] = state.get(f"inputs_{section}_row_count")
        for row_idx in _AUDIT_ROWS:
            for field in _ROW_FIELDS:
                shared_key = f"{section}_row_{row_idx}_{field}"
                widget_key = f"inputs_{section}_row_{row_idx}_{field}"
                shared_row_model[shared_key] = state.get(shared_key)
                inputs_widget_mirror[widget_key] = state.get(widget_key)

    for key in (
        "bot1_count", "db_bot_1", "bot2_count", "db_bot_2",
        "top1_count", "db_top_1", "top2_count", "db_top_2",
        "nb_bot", "nb_top", "Ast_bot", "Ast_top",
    ):
        legacy_mirror[key] = state.get(key)

    drift_keys: list[str] = []
    for section in ("bot", "top"):
        shared_count_key = f"{section}_row_count"
        widget_count_key = f"inputs_{section}_row_count"
        if shared_row_model.get(shared_count_key) != inputs_widget_mirror.get(widget_count_key):
            drift_keys.append(shared_count_key)
        for row_idx in _AUDIT_ROWS:
            for field in _ROW_FIELDS:
                shared_key = f"{section}_row_{row_idx}_{field}"
                widget_key = f"inputs_{section}_row_{row_idx}_{field}"
                if shared_row_model.get(shared_key) != inputs_widget_mirror.get(widget_key):
                    drift_keys.append(shared_key)

    snapshot = {
        "label": str(label or "").strip() or "unlabelled",
        "page_slug": str(state.get("page_slug") or ""),
        "active_beam_id": str(state.get("active_beam_id") or "") or None,
        "shared_row_model": shared_row_model,
        "legacy_mirror": legacy_mirror,
        "inputs_widget_mirror": inputs_widget_mirror,
        "diff_summary": {
            "drift_detected": bool(drift_keys),
            "drift_keys": list(drift_keys),
            "drift_count": len(drift_keys),
        },
    }

    audit_store = dict(state.get("_inputs_longitudinal_reo_audit") or {})
    history = list(audit_store.get("history") or [])
    history.append(copy_deepcopy_fn(snapshot))
    if len(history) > 24:
        history = history[-24:]
    audit_store["latest"] = copy_deepcopy_fn(snapshot)
    audit_store["history"] = history
    state["_inputs_longitudinal_reo_audit"] = audit_store
    state["inputs_longitudinal_reo_widget_drift_detected"] = bool(drift_keys)
    state["inputs_longitudinal_reo_widget_drift_keys"] = list(drift_keys)

    try:
        agent_debug_log_fn(
            "Inputs longitudinal reo widget audit snapshot",
            snapshot,
            location="inputs_page.py:_longitudinal_reo_widget_audit_snapshot",
            hypothesis_id="H_INPUTS_LONGITUDINAL_WIDGET_AUDIT",
        )
    except Exception:
        pass
    return snapshot


def reseed_inputs_longitudinal_reo_widgets_from_shared(
    *,
    state: dict,
    reason: str,
    force: bool = False,
    time_time_fn: Callable[[], float],
    copy_deepcopy_fn: Callable[[Any], Any],
    is_longitudinal_widget_key_fn: Callable[[str | None], bool],
    agent_debug_log_fn: Callable[..., None],
) -> dict:
    reason_norm = str(reason or "").strip() or "unspecified"
    last_widget_key = str(state.get("_last_user_widget_key") or "").strip()
    last_edit_ts = float(state.get("_last_user_edit_ts", 0.0) or 0.0)
    active_edit_age_s = max(0.0, time_time_fn() - last_edit_ts) if last_edit_ts > 0.0 else float("inf")
    actively_editing_longitudinal_widget = (
        is_longitudinal_widget_key_fn(last_widget_key) and active_edit_age_s < 2.0
    )

    changed_widget_keys: list[str] = []
    if actively_editing_longitudinal_widget and not force:
        payload = {
            "reseed_applied": False,
            "reseed_reason": reason_norm,
            "changed_widget_keys": [],
            "skipped_due_to_active_edit": True,
            "active_edit_widget_key": last_widget_key,
        }
        state["inputs_longitudinal_reo_reseed_applied"] = False
        state["inputs_longitudinal_reo_reseed_reason"] = reason_norm
        state["inputs_longitudinal_reo_reseed_changed_keys"] = []
        try:
            agent_debug_log_fn(
                "Skipped inputs longitudinal reo widget reseed",
                payload,
                location="inputs_page.py:_reseed_inputs_longitudinal_reo_widgets_from_shared",
                hypothesis_id="H_INPUTS_LONGITUDINAL_WIDGET_RESEED",
            )
        except Exception:
            pass
        return payload

    for section in ("bot", "top"):
        count_shared_key = f"{section}_row_count"
        count_widget_key = f"inputs_{section}_row_count"
        if count_shared_key in state:
            shared_value = copy_deepcopy_fn(state.get(count_shared_key))
            if state.get(count_widget_key) != shared_value:
                state[count_widget_key] = shared_value
                changed_widget_keys.append(count_widget_key)
            state.pop(f"_cached_{count_widget_key}", None)
        for row_idx in _RESEED_ROWS:
            for field in _ROW_FIELDS:
                shared_key = f"{section}_row_{row_idx}_{field}"
                widget_key = f"inputs_{section}_row_{row_idx}_{field}"
                if shared_key not in state:
                    continue
                shared_value = copy_deepcopy_fn(state.get(shared_key))
                if state.get(widget_key) != shared_value:
                    state[widget_key] = shared_value
                    changed_widget_keys.append(widget_key)
                state.pop(f"_cached_{widget_key}", None)

    hydrated_map = state.get("_hydrated_from_shared_map")
    if isinstance(hydrated_map, dict):
        for widget_key in changed_widget_keys:
            hydrated_map.pop(widget_key, None)

    payload = {
        "reseed_applied": bool(changed_widget_keys),
        "reseed_reason": reason_norm,
        "changed_widget_keys": list(changed_widget_keys),
        "skipped_due_to_active_edit": False,
        "active_edit_widget_key": last_widget_key or None,
    }
    state["inputs_longitudinal_reo_reseed_applied"] = bool(changed_widget_keys)
    state["inputs_longitudinal_reo_reseed_reason"] = reason_norm
    state["inputs_longitudinal_reo_reseed_changed_keys"] = list(changed_widget_keys)

    try:
        agent_debug_log_fn(
            "Inputs longitudinal reo widget reseed",
            payload,
            location="inputs_page.py:_reseed_inputs_longitudinal_reo_widgets_from_shared",
            hypothesis_id="H_INPUTS_LONGITUDINAL_WIDGET_RESEED",
        )
    except Exception:
        pass
    return payload


def hydrate_inputs_longitudinal_reo_widgets_for_revision(
    *,
    state: dict,
    revision: int,
    active_beam_id: str | None = None,
    copy_deepcopy_fn: Callable[[Any], Any],
) -> dict:
    """Keep visible Inputs row widgets aligned with the committed snapshot.

    The Inputs workspace can be rerun as a fragment without running the page
    setup code again.  In that path a callback may have committed a new beam
    snapshot while Streamlit retained the old ``inputs_*`` widget values.  The
    calculation and Design Brain then consume the committed row model, while
    the controls still display the previous diameter/count.  That split is a
    direct parity failure: the user sees one design and V2 evaluates another.

    Call this before the workspace renders any widgets.  A committed input
    revision is the authority, so a changed revision is safe to reseed even if
    the previous rerun was marked as a recent widget edit; the callback has
    already copied that edit into the shared row model before this function is
    reached.
    """

    revision_value = int(revision or 0)
    beam_value = str(active_beam_id or "").strip() or None
    marker = (beam_value, revision_value)
    previous_marker = state.get("_inputs_longitudinal_reo_widget_revision")
    # Apply commits can occur during page setup, after the shell's first
    # hydration pass has already consumed the one-shot reseed flag.  The
    # unified workspace fragment is then the next (and sometimes only) place
    # that can reconcile the visible selectboxes.  Treat that flag as an
    # explicit revision-boundary request, even when the marker was written by
    # an earlier pass in the same app rerun.
    force_reseed = bool(state.pop("_force_inputs_widget_reseed_once", False))
    changed_widget_keys: list[str] = []

    if previous_marker != marker or force_reseed:
        hydrated_map = state.get("_hydrated_from_shared_map")
        if not isinstance(hydrated_map, dict):
            hydrated_map = {}
            state["_hydrated_from_shared_map"] = hydrated_map
        for section in ("bot", "top"):
            shared_count_key = f"{section}_row_count"
            widget_count_key = f"inputs_{section}_row_count"
            if shared_count_key in state:
                shared_value = copy_deepcopy_fn(state.get(shared_count_key))
                if state.get(widget_count_key) != shared_value or force_reseed:
                    # Give select_row an explicit initial index.  Merely
                    # assigning an existing Streamlit widget key can leave
                    # the browser-side selectbox displaying its old value.
                    state.pop(widget_count_key, None)
                    state.pop(f"_cached_{widget_count_key}", None)
                    hydrated_map[widget_count_key] = shared_value
                    changed_widget_keys.append(widget_count_key)
            for row_idx in _RESEED_ROWS:
                for field in _ROW_FIELDS:
                    shared_key = f"{section}_row_{row_idx}_{field}"
                    widget_key = f"inputs_{section}_row_{row_idx}_{field}"
                    if shared_key not in state:
                        continue
                    shared_value = copy_deepcopy_fn(state.get(shared_key))
                    if state.get(widget_key) != shared_value or force_reseed:
                        state.pop(widget_key, None)
                        state.pop(f"_cached_{widget_key}", None)
                        hydrated_map[widget_key] = shared_value
                        changed_widget_keys.append(widget_key)
        state["_inputs_longitudinal_reo_widget_revision"] = marker
        if force_reseed:
            # Streamlit can retain a selectbox's browser-side value even after
            # its session key is cleared during an app rerun.  Bump a stable
            # epoch so the row controls receive a new widget identity exactly
            # at an Apply transaction boundary; ordinary edits keep their
            # existing identities and fast fragment path.
            state["_inputs_longitudinal_reo_widget_epoch"] = int(
                state.get("_inputs_longitudinal_reo_widget_epoch", 0) or 0
            ) + 1

    payload = {
        "revision": revision_value,
        "active_beam_id": beam_value,
        "previous_marker": previous_marker,
        "marker": marker,
        "force_reseed": force_reseed,
        "reseed_applied": bool(changed_widget_keys),
        "changed_widget_keys": list(changed_widget_keys),
    }
    state["_inputs_longitudinal_reo_widget_revision_probe"] = dict(payload)
    return payload


__all__ = [
    "is_inputs_longitudinal_reo_widget_key",
    "longitudinal_reo_widget_audit_snapshot",
    "reseed_inputs_longitudinal_reo_widgets_from_shared",
    "hydrate_inputs_longitudinal_reo_widgets_for_revision",
]
