"""Explicit session-state operations for the Inputs one-click transaction."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from datetime import datetime

from inputs_application.recommendation_store import RecommendationStore


class OneClickSessionStore:
    """Typed boundary for one-click feedback and solver-latch state."""

    def __init__(self, session_state: MutableMapping[str, object]) -> None:
        self._state = session_state

    def set_run_feedback(
        self,
        *,
        status: str,
        reason: str | None,
        winning_label: str | None = None,
        winning_action_type: str | None = None,
        pre_commit_worst_util: float | None = None,
        extra_payload: dict | None = None,
        debug_target: dict | None = None,
    ) -> None:
        payload = {
            "status": str(status or "").strip() or "blocked",
            "reason": str(reason or "").strip() or "unknown",
            "winning_label": str(winning_label or "").strip() or None,
            "winning_action_type": str(winning_action_type or "").strip() or None,
            "pre_commit_worst_util": pre_commit_worst_util,
        }
        if isinstance(extra_payload, dict):
            payload.update(dict(extra_payload))
        self._state["_one_click_run_feedback"] = payload
        if isinstance(debug_target, dict):
            debug_target["one_click_run_feedback_status"] = payload["status"]
            debug_target["one_click_run_feedback_reason"] = payload["reason"]

    def clear_run_feedback(self) -> None:
        self._state.pop("_one_click_run_feedback", None)

    def clear_auto_design_runtime_latches(self, reason: str) -> dict:
        before = {
            "_solver_running": bool(self._state.get("_solver_running", False)),
            "_compute_in_progress": bool(self._state.get("_compute_in_progress", False)),
            "auto_design_latch_owner": str(self._state.get("auto_design_latch_owner") or ""),
            "auto_design_invoke_consumed": bool(self._state.get("auto_design_invoke_consumed", False)),
        }
        self._state["_solver_running"] = False
        self._state["_compute_in_progress"] = False
        self._state["auto_design_latch_owner"] = ""
        self._state["auto_design_invoke_consumed"] = False
        payload = {
            "reason": str(reason or ""),
            "before": before,
            "after": {
                "_solver_running": False,
                "_compute_in_progress": False,
                "auto_design_latch_owner": "",
                "auto_design_invoke_consumed": False,
            },
        }
        self._state["_auto_design_latch_clear_latest"] = dict(payload)
        return payload

    def consume_auto_design_invoke(
        self,
        *,
        auto_invoke_key: str,
        request_timestamp_key: str,
        request_source_key: str,
    ) -> None:
        had_invoke = bool(self._state.get(auto_invoke_key, False))
        if had_invoke:
            for key in (
                auto_invoke_key,
                request_timestamp_key,
                request_source_key,
                "auto_design_request_source",
            ):
                self._state.pop(key, None)
        self._state["auto_design_invoke_consumed"] = bool(had_invoke)
        self._state["auto_design_invoke_pending"] = False
        self._state.pop("_auto_design_idle_reason", None)
        self._state.pop("auto_design_idle_reason", None)

    def should_run_auto_design(self, auto_invoke_key: str) -> bool:
        return bool(
            self._state.get("_force_auto_redesign", False)
            or self._state.get(auto_invoke_key, False)
        )

    def invalidate_after_design_state_change(
        self,
        *,
        current_fingerprint: object,
        transient_keys: Sequence[str],
    ) -> bool:
        """Invalidate a pending auto-design run when governing inputs change."""
        previous = self._state.get("_auto_design_last_fingerprint")
        if previous is None:
            self._state["_auto_design_last_fingerprint"] = current_fingerprint
            return False
        if current_fingerprint == previous:
            return False
        self._state["_auto_design_invalidated"] = True
        self._state["_auto_design_last_fingerprint"] = current_fingerprint
        for key in transient_keys:
            self._state.pop(str(key), None)
        self.clear_auto_design_runtime_latches("design_state_changed")
        return True

    def record_shear_publish_audit(
        self,
        *,
        stage: str,
        source: str,
        candidate_updates: dict | None,
        publish_attempted: bool,
        publish_blocked: bool,
    ) -> None:
        updates = dict(candidate_updates or {})
        relevant = {
            key: updates.get(key)
            for key in ("lig_legs", "lig_d", "s_lig")
            if key in updates
        }
        if not relevant:
            return
        entry = {
            "stage": str(stage or ""),
            "source": str(source or ""),
            "candidate_shear": dict(relevant),
            "publish_attempted": bool(publish_attempted),
            "publish_blocked": bool(publish_blocked),
            "shared_shear_snapshot": {
                "s_lig": self._state.get("s_lig"),
                "lig_d": self._state.get("lig_d"),
                "lig_legs": self._state.get("lig_legs"),
            },
        }
        audit = list(self._state.get("_one_click_shear_publish_audit") or [])
        audit.append(entry)
        self._state["_one_click_shear_publish_audit"] = audit[-20:]

    def set_live_breadcrumb(self, label: str, extra: dict | None = None) -> None:
        try:
            self._state["_dg_live_breadcrumb"] = {
                "label": str(label),
                "extra": dict(extra or {}),
                "ts": datetime.now().isoformat(timespec="seconds"),
            }
        except Exception:
            pass


def sanitize_shared_update_bundle(
    updates: dict | None,
    *,
    source: str,
    shared_defaults: Mapping[str, object],
) -> tuple[dict, dict]:
    raw = dict(updates or {})
    sanitized: dict[str, object] = {}
    dropped_nonshared: list[str] = []
    dropped_private: list[str] = []
    for key, value in raw.items():
        normalized = str(key or "")
        if not normalized:
            continue
        if normalized.startswith("_"):
            dropped_private.append(normalized)
            continue
        if normalized not in shared_defaults:
            dropped_nonshared.append(normalized)
            continue
        sanitized[normalized] = value
    return sanitized, {
        "source": str(source or ""),
        "input_key_count": len(raw),
        "sanitized_key_count": len(sanitized),
        "dropped_nonshared_keys": sorted(set(dropped_nonshared)),
        "dropped_private_keys": sorted(set(dropped_private)),
    }


def set_one_click_run_feedback(
    *,
    session_state: MutableMapping[str, object],
    status: str,
    reason: str | None,
    winning_label: str | None = None,
    winning_action_type: str | None = None,
    pre_commit_worst_util: float | None = None,
    extra_payload: dict | None = None,
    debug_target: dict | None = None,
) -> None:
    OneClickSessionStore(session_state).set_run_feedback(
        status=status,
        reason=reason,
        winning_label=winning_label,
        winning_action_type=winning_action_type,
        pre_commit_worst_util=pre_commit_worst_util,
        extra_payload=extra_payload,
        debug_target=debug_target,
    )


def clear_auto_design_runtime_latches(
    reason: str,
    *,
    session_state: MutableMapping[str, object],
) -> dict:
    return OneClickSessionStore(session_state).clear_auto_design_runtime_latches(reason)


def consume_auto_design_invoke_after_solver_entry_confirmed(
    *,
    session_state: MutableMapping[str, object],
    auto_invoke_key: str,
    request_timestamp_key: str,
    request_source_key: str,
) -> None:
    OneClickSessionStore(session_state).consume_auto_design_invoke(
        auto_invoke_key=auto_invoke_key,
        request_timestamp_key=request_timestamp_key,
        request_source_key=request_source_key,
    )


def should_run_auto_design(
    *,
    session_state: Mapping[str, object],
    auto_invoke_key: str,
) -> bool:
    return OneClickSessionStore(session_state).should_run_auto_design(auto_invoke_key)


def normalise_invalid_shear_state_updates(
    base_state: dict,
    updates: dict,
    *,
    source: str,
    canonical_no_shear_spacing: float,
    reo_bar_diameters: Sequence[int],
    reo_spacings: Sequence[float],
    int_from_state: Callable[..., int],
    float_from_state: Callable[..., float],
    dev_mode_enabled: Callable[[], bool],
) -> dict:
    _ = source
    resolved_state = dict(base_state or {})
    normalised_updates = dict(updates or {})
    resolved_state.update(normalised_updates)
    lig_legs = int_from_state(resolved_state, "lig_legs", 0)
    lig_d = int_from_state(resolved_state, "lig_d", 0)
    if lig_legs <= 0:
        normalised_updates["lig_legs"] = 0
        normalised_updates["lig_d"] = 0
        spacing = float(canonical_no_shear_spacing)
        current_spacing = float_from_state(
            resolved_state,
            "s_lig",
            spacing,
        )
        if abs(float(current_spacing) - spacing) > 1e-9:
            normalised_updates["s_lig"] = spacing
        return normalised_updates
    if lig_legs >= 2 and lig_d <= 0:
        current_diameter = int_from_state(resolved_state, "lig_d", 0)
        if current_diameter > 0:
            starter_diameter = int(current_diameter)
        else:
            practical = [
                diameter
                for diameter in reo_bar_diameters
                if diameter <= 16
            ]
            starter_diameter = int(practical[0] if practical else 10)
        if dev_mode_enabled():
            assert starter_diameter > 0, (
                "Invalid shear state: ligatures active but diameter is zero"
            )
        normalised_updates["lig_d"] = starter_diameter
    current_spacing = float_from_state(
        resolved_state,
        "s_lig",
        0.0,
    )
    if lig_legs >= 2 and current_spacing <= 0.0:
        if current_spacing > 0.0 and reo_spacings:
            starter_spacing = float(
                min(
                    reo_spacings,
                    key=lambda value: abs(
                        float(value) - current_spacing
                    ),
                )
            )
        elif 200 in reo_spacings:
            starter_spacing = 200.0
        else:
            starter_spacing = float(
                reo_spacings[
                    min(
                        len(reo_spacings) - 1,
                        len(reo_spacings) // 2,
                    )
                ]
                if reo_spacings
                else 200.0
            )
        normalised_updates["s_lig"] = starter_spacing
    return normalised_updates


def pop_inputs_widget_keys_for_shared_updates(
    updates: dict,
    *,
    session_state: MutableMapping[str, object],
) -> set[str]:
    if not updates:
        return set()
    alias_widget_keys: dict[str, list[str]] = {
        "db_bot_1": ["inputs_db_bot_1", "inputs_nb_or_s_bot_1"],
        "db_bot_2": ["inputs_db_bot_2", "inputs_nb_or_s_bot_2"],
        "db_top_1": ["inputs_db_top_1", "inputs_nb_or_s_top_1"],
        "db_top_2": ["inputs_db_top_2", "inputs_nb_or_s_top_2"],
        "bot1_layout_mode": ["inputs_bot1_layout_mode"],
        "bot1_count": ["inputs_bot1_count"],
        "bot1_spacing": ["inputs_bot1_spacing"],
        "bot2_layout_mode": ["inputs_bot2_layout_mode"],
        "bot2_count": ["inputs_bot2_count"],
        "bot2_spacing": ["inputs_bot2_spacing"],
        "top1_layout_mode": ["inputs_top1_layout_mode"],
        "top1_count": ["inputs_top1_count"],
        "top1_spacing": ["inputs_top1_spacing"],
        "top2_layout_mode": ["inputs_top2_layout_mode"],
        "top2_count": ["inputs_top2_count"],
        "top2_spacing": ["inputs_top2_spacing"],
    }
    shear_widget_trio = {
        "inputs_s_lig",
        "inputs_lig_d",
        "inputs_lig_legs",
    }
    cleared: set[str] = set()
    hydrated_map = session_state.get("_hydrated_from_shared_map")
    clear_shear_trio = any(
        key in {"s_lig", "lig_d", "lig_legs"}
        for key in list(updates.keys())
    )
    for key in list(updates.keys()):
        widget_keys = [f"inputs_{key}"]
        widget_keys.extend(alias_widget_keys.get(key, []))
        if clear_shear_trio:
            widget_keys.extend(sorted(shear_widget_trio))
        if key.startswith(("bot_row_", "top_row_")):
            widget_keys.append(f"inputs_{key}")
        for widget_key in widget_keys:
            session_state.pop(widget_key, None)
            session_state.pop(f"_cached_{widget_key}", None)
            cleared.add(widget_key)
    if isinstance(hydrated_map, dict):
        for key in updates:
            hydrated_map.pop(f"inputs_{key}", None)
            for widget_key in alias_widget_keys.get(key, []):
                hydrated_map.pop(widget_key, None)
        for widget_key in cleared:
            hydrated_map.pop(widget_key, None)
    for key in list(updates.keys()):
        session_state.pop(f"_cached_inputs_{key}", None)
    return cleared


def record_one_click_shear_publish_audit(
    *,
    session_state: MutableMapping[str, object],
    stage: str,
    source: str,
    candidate_updates: dict | None,
    publish_attempted: bool,
    publish_blocked: bool,
) -> None:
    OneClickSessionStore(session_state).record_shear_publish_audit(
        stage=stage,
        source=source,
        candidate_updates=candidate_updates,
        publish_attempted=publish_attempted,
        publish_blocked=publish_blocked,
    )


def restore_shared_state_snapshot(
    snapshot: dict,
    *,
    source: str,
    shared_defaults: Mapping[str, object],
    set_shared: Callable[..., None],
    normalise_invalid_shear_state_in_shared: Callable[..., bool],
    refresh_canonical_shear_widgets: Callable[..., None],
    apply_canonical_convenience_resync_to_shared: Callable[..., dict],
) -> None:
    snap = dict(snapshot or {})
    for key, default in shared_defaults.items():
        set_shared(key, snap.get(key, default), source=source)
    normalise_invalid_shear_state_in_shared(
        source=f"{source}:shear_shared_normalise"
    )
    refresh_canonical_shear_widgets(
        source=f"{source}:shear_widget_refresh"
    )
    apply_canonical_convenience_resync_to_shared(
        source=f"{source}:canonical_convenience"
    )


def set_shared_updates(
    updates: dict,
    *,
    source: str,
    session_state: MutableMapping[str, object],
    sanitize_updates: Callable[..., tuple[dict, dict]],
    append_trace: Callable[..., None],
    set_shared: Callable[..., None],
    normalise_invalid_shear_state_in_shared: Callable[..., bool],
    refresh_canonical_shear_widgets: Callable[..., None],
    apply_canonical_convenience_resync_to_shared: Callable[..., dict],
) -> None:
    sanitized_updates, sanitize_meta = sanitize_updates(
        updates,
        source=source,
    )
    session_state["_last_shared_update_sanitize_meta"] = dict(
        sanitize_meta
    )
    session_state["_nonshared_update_drop_audit"] = {
        "source": sanitize_meta["source"],
        "dropped_nonshared_keys": list(
            sanitize_meta.get("dropped_nonshared_keys") or []
        ),
        "dropped_private_keys": list(
            sanitize_meta.get("dropped_private_keys") or []
        ),
        "raw_key_count": sanitize_meta.get("input_key_count"),
        "sanitized_key_count": sanitize_meta.get(
            "sanitized_key_count"
        ),
    }
    try:
        append_trace(
            "shared_update_sanitize",
            dict(sanitize_meta),
            source=str(source or ""),
        )
    except Exception:
        pass
    if not sanitized_updates:
        return
    for shared_key, value in sanitized_updates.items():
        set_shared(shared_key, value, source=source)
    if any(
        key in {"lig_d", "lig_legs", "s_lig"}
        for key in sanitized_updates
    ):
        normalise_invalid_shear_state_in_shared(
            source=f"{source}:shear_shared_normalise"
        )
        refresh_canonical_shear_widgets(
            source=f"{source}:shear_widget_refresh"
        )
    apply_canonical_convenience_resync_to_shared(
        source=f"{source}:canonical_convenience"
    )


def set_design_guide_live_breadcrumb(
    label: str,
    extra: dict | None = None,
    *,
    session_state: MutableMapping[str, object],
) -> None:
    OneClickSessionStore(session_state).set_live_breadcrumb(label, extra)


def invalidate_design_guide_caches(
    *,
    reason: str,
    updated_keys: list[str] | None = None,
    preserve_apply_banner: bool = False,
    session_state: MutableMapping[str, object],
    clear_transient_ui_state: Callable[..., object],
    agent_debug_log: Callable[..., None],
) -> list[str]:
    removed: list[str] = []
    clear_transient_ui_state(
        session_state,
        clear_history=False,
        preserve_apply_banner=preserve_apply_banner,
    )
    removed.extend(RecommendationStore(session_state).clear_all())
    if bool(session_state.get("_dev_mode")):
        agent_debug_log(
            "Invalidated design guide caches",
            {
                "reason": reason,
                "updated_keys": list(updated_keys or []),
                "removed_cache_keys": removed,
            },
            location="inputs_page.py:_invalidate_design_guide_caches",
            hypothesis_id="H301",
        )
    return removed


__all__ = [
    "OneClickSessionStore",
    "clear_auto_design_runtime_latches",
    "consume_auto_design_invoke_after_solver_entry_confirmed",
    "normalise_invalid_shear_state_updates",
    "invalidate_design_guide_caches",
    "pop_inputs_widget_keys_for_shared_updates",
    "record_one_click_shear_publish_audit",
    "restore_shared_state_snapshot",
    "sanitize_shared_update_bundle",
    "set_one_click_run_feedback",
    "set_shared_updates",
    "set_design_guide_live_breadcrumb",
    "should_run_auto_design",
]
