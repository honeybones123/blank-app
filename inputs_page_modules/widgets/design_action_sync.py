"""Design-action widget/session synchronization coordination."""

from __future__ import annotations

from typing import Any, Callable

from calculations.design_actions import resolve_design_actions_from_state
from inputs_page_modules.fragments import rerun_inputs_current_scope


def _record_design_action_state_transition(
    st_module: Any,
    event: str,
    **data: Any,
) -> None:
    """Keep a bounded callback/hydration trace for focused browser diagnosis."""
    try:
        trace = list(
            st_module.session_state.get("_design_action_state_transition_trace")
            or []
        )
        trace.append({"event": str(event), **data})
        st_module.session_state["_design_action_state_transition_trace"] = trace[-40:]
    except Exception:
        pass


def design_action_widget_specs(selected_prefix: str) -> list[dict]:
    return [
        {
            "label": "Positive design moment Mu*+ (kNm)",
            "widget_key": "inputs_load_Mstar_pos_proxy",
            "shared_key": f"{selected_prefix}_Mstar_pos_manual",
            "proxy_key": "load_Mstar_pos_proxy",
            "help_text": "Sagging bending demand magnitude (top in compression, bottom in tension).",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Negative design moment Mu*- (kNm)",
            "widget_key": "inputs_load_Mstar_neg_proxy",
            "shared_key": f"{selected_prefix}_Mstar_neg_manual",
            "proxy_key": "load_Mstar_neg_proxy",
            "help_text": "Hogging bending demand magnitude (top in tension, bottom in compression). Enter as positive.",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Applied prestress P* (kN)",
            "widget_key": "inputs_P_star",
            "shared_key": "P_star",
            "proxy_key": None,
            "help_text": "Net prestress force at the section (compression positive).",
            "disabled_in_design_mode": False,
        },
        {
            "label": "Design torsion Tu* (kNm)",
            "widget_key": "inputs_Tu_star",
            "shared_key": "Tu_star",
            "proxy_key": None,
            "help_text": "Factored torsion; used on torsion page (placeholder here).",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Design shear Vu* (kN)",
            "widget_key": "inputs_load_Vstar_proxy",
            "shared_key": f"{selected_prefix}_Vstar",
            "proxy_key": "load_Vstar_proxy",
            "help_text": "Factored design shear at the critical section.",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Axial force N* (kN)",
            "widget_key": "inputs_load_Nstar_proxy",
            "shared_key": f"{selected_prefix}_Nstar",
            "proxy_key": "load_Nstar_proxy",
            "help_text": "Axial action at the section (+compression / \u2212tension).",
            "disabled_in_design_mode": True,
        },
    ]


def render_design_action_number_row(
    *,
    st_module: Any,
    label: str,
    widget_key: str,
    help_text: str,
    on_change,
    disabled: bool = False,
    col_label=None,
    col_input=None,
    label_with_hover_fn: Callable[..., None],
    register_rendered_key_fn: Callable[[str], None],
) -> float:
    if col_label is None or col_input is None:
        col1, col2 = st_module.columns([1, 2], gap="medium")
    else:
        col1, col2 = col_label, col_input
    with col1:
        label_with_hover_fn(label, help_text, required=False)
    with col2:
        register_rendered_key_fn(widget_key)
        return float(
            st_module.number_input(
                label,
                key=widget_key,
                format="%.1f",
                step=1.0,
                label_visibility="collapsed",
                on_change=on_change,
                disabled=disabled,
            )
            or 0.0
        )


def debug_check_design_action_consistency(
    state: dict,
    *,
    st_module: Any,
    debug_design_guidance_probe: bool,
    resolve_design_actions_from_state_fn: Callable[[dict], dict],
    agent_debug_log_fn: Callable[..., None],
) -> None:
    if not debug_design_guidance_probe:
        return
    if str(st_module.session_state.get("loads_edit_mode", "ULS") or "ULS").upper() != "ULS":
        return
    actions = resolve_design_actions_from_state_fn(state)
    payload = {
        "widget_M_pos": st_module.session_state.get("inputs_load_Mstar_pos_proxy"),
        "widget_M_neg": st_module.session_state.get("inputs_load_Mstar_neg_proxy"),
        "widget_V": st_module.session_state.get("inputs_load_Vstar_proxy"),
        "shared_uls_M": st_module.session_state.get("uls_Mstar"),
        "shared_uls_M_pos": st_module.session_state.get("uls_Mstar_pos_manual"),
        "shared_uls_M_neg": st_module.session_state.get("uls_Mstar_neg_manual"),
        "shared_uls_V": st_module.session_state.get("uls_Vstar"),
        "resolved_M": actions.get("Mu"),
        "resolved_V": actions.get("Vu"),
    }
    agent_debug_log_fn(
        "Design action consistency check",
        payload,
        location="inputs_page.py:_debug_check_design_action_consistency",
        hypothesis_id="H51",
    )


def make_design_action_widget_callback(
    widget_key: str,
    shared_key: str,
    proxy_key: str | None = None,
    *,
    sync_design_action_widget_to_shared_fn: Callable[..., None],
):
    def _callback() -> None:
        sync_design_action_widget_to_shared_fn(
            widget_key,
            shared_key,
            proxy_key,
            trigger_rerun=False,
        )

    return _callback


def mirror_design_action_proxies_from_shared(
    selected_prefix: str,
    *,
    get_param_fn: Callable[..., Any],
    set_shared_fn: Callable[..., None],
) -> None:
    proxy_pairs = (
        ("load_Mstar_pos_proxy", f"{selected_prefix}_Mstar_pos_manual"),
        ("load_Mstar_neg_proxy", f"{selected_prefix}_Mstar_neg_manual"),
        ("load_Mstar_proxy", f"{selected_prefix}_Mstar"),
        ("load_Vstar_proxy", f"{selected_prefix}_Vstar"),
        ("load_Nstar_proxy", f"{selected_prefix}_Nstar"),
    )
    for proxy_key, shared_key in proxy_pairs:
        set_shared_fn(
            proxy_key,
            float(get_param_fn(shared_key, 0.0) or 0.0),
            source="design_action_proxy_mirror",
        )


def hydrate_design_action_widgets_from_shared(
    selected_prefix: str,
    *,
    st_module: Any,
    get_param_fn: Callable[..., Any],
    state_hc_log_fn: Callable[..., None],
    design_action_widget_specs_fn: Callable[[str], list[dict]],
    force: bool = False,
    design_controls: bool = False,
) -> None:
    specs = design_action_widget_specs_fn(selected_prefix)

    def _display_value(spec: dict) -> float:
        shared_key = str(spec["shared_key"])
        if not design_controls:
            manual_owner_key = {
                "uls_Vstar": "manual_uls_Vstar",
                "uls_Nstar": "manual_uls_Nstar",
                "sls_Vstar": "manual_sls_Vstar",
                "sls_Nstar": "manual_sls_Nstar",
            }.get(shared_key)
            if manual_owner_key in st_module.session_state:
                return float(
                    st_module.session_state.get(manual_owner_key, 0.0) or 0.0
                )
            return float(get_param_fn(shared_key, 0.0) or 0.0)

        # In Load Analysis mode the manual ULS/SLS fields remain untouched.
        # Render the resolved, derived action contract instead of the saved
        # manual fields so switching the source off restores those values.
        resolved = resolve_design_actions_from_state(
            dict(st_module.session_state)
        )
        is_sls = str(selected_prefix).strip().lower() == "sls"
        if shared_key.endswith("_Mstar_pos_manual"):
            key = "SLS_M_pos" if is_sls else "Mu_pos"
            return float(resolved.get(key, 0.0) or 0.0)
        if shared_key.endswith("_Mstar_neg_manual"):
            key = "SLS_M_neg" if is_sls else "Mu_neg"
            return float(resolved.get(key, 0.0) or 0.0)
        if shared_key.endswith("_Vstar"):
            key = "SLS_V" if is_sls else "Vu"
            return float(resolved.get(key, 0.0) or 0.0)
        if shared_key.endswith("_Nstar"):
            return 0.0
        return float(get_param_fn(shared_key, 0.0) or 0.0)

    signature = (
        selected_prefix,
        bool(design_controls),
        tuple(_display_value(spec) for spec in specs),
    )
    # Existing manual widgets are the edit authority.  A signature change can
    # be observed by an older fragment render after a newer edit has already
    # committed; hydrating on that change would repaint the control with stale
    # canonical data even though the latest engineering snapshot is correct.
    # External ownership changes (beam/source/load-set) request ``force``
    # explicitly.  Derived Load Analysis controls remain projection-owned and
    # are therefore refreshed on every render.
    should_hydrate = bool(force or design_controls)
    _record_design_action_state_transition(
        st_module,
        "hydrate_entry",
        selected_prefix=str(selected_prefix),
        force=bool(force),
        design_controls=bool(design_controls),
        should_hydrate=bool(should_hydrate),
        signature_changed=bool(
            st_module.session_state.get("_design_action_widget_signature") != signature
        ),
        shared_uls_Mstar=get_param_fn("uls_Mstar", None),
        shared_uls_Mstar_pos_manual=get_param_fn("uls_Mstar_pos_manual", None),
        shared_uls_Vstar=get_param_fn("uls_Vstar", None),
        widget_M_pos=st_module.session_state.get("inputs_load_Mstar_pos_proxy"),
        widget_V=st_module.session_state.get("inputs_load_Vstar_proxy"),
    )
    dbg_w_pos = st_module.session_state.get("inputs_load_Mstar_pos_proxy")
    dbg_w_neg = st_module.session_state.get("inputs_load_Mstar_neg_proxy")
    dbg_w_signed = st_module.session_state.get("inputs_load_Mstar_proxy")
    for spec in specs:
        widget_key = str(spec["widget_key"])
        shared_key = str(spec["shared_key"])
        if should_hydrate or widget_key not in st_module.session_state:
            shared_value = _display_value(spec)
            old_widget_value = st_module.session_state.get(widget_key)
            if old_widget_value != shared_value:
                st_module.session_state[widget_key] = shared_value
    st_module.session_state["_design_action_widget_signature"] = signature
    _record_design_action_state_transition(
        st_module,
        "hydrate_exit",
        selected_prefix=str(selected_prefix),
        should_hydrate=bool(should_hydrate),
        shared_uls_Mstar=get_param_fn("uls_Mstar", None),
        shared_uls_Mstar_pos_manual=get_param_fn("uls_Mstar_pos_manual", None),
        shared_uls_Vstar=get_param_fn("uls_Vstar", None),
        widget_M_pos=st_module.session_state.get("inputs_load_Mstar_pos_proxy"),
        widget_V=st_module.session_state.get("inputs_load_Vstar_proxy"),
    )

    if bool(st_module.session_state.get("_dev_mode")):
        try:
            state_hc_log_fn(
                "[design_action_hydrate]",
                selected_prefix=selected_prefix,
                actions_mode=st_module.session_state.get("actions_mode"),
                design_controls=bool(design_controls),
                should_hydrate=bool(should_hydrate),
                canonical_pos=float(
                    get_param_fn(f"{selected_prefix}_Mstar_pos_manual", 0.0) or 0.0
                ),
                canonical_neg=float(
                    get_param_fn(f"{selected_prefix}_Mstar_neg_manual", 0.0) or 0.0
                ),
                canonical_signed=float(
                    get_param_fn(f"{selected_prefix}_Mstar", 0.0) or 0.0
                ),
                widget_pos_before=dbg_w_pos,
                widget_neg_before=dbg_w_neg,
                widget_signed_before=dbg_w_signed,
                widget_pos_after_render=st_module.session_state.get("inputs_load_Mstar_pos_proxy"),
                widget_neg_after_render=st_module.session_state.get("inputs_load_Mstar_neg_proxy"),
                widget_signed_after_render=st_module.session_state.get("inputs_load_Mstar_proxy"),
            )
        except Exception:
            pass


def commit_design_action_widgets_to_shared(
    selected_prefix: str,
    *,
    st_module: Any,
    design_action_widget_specs_fn: Callable[[str], list[dict]],
    sync_design_action_widget_to_shared_fn: Callable[..., None],
) -> None:
    for spec in design_action_widget_specs_fn(selected_prefix):
        widget_key = spec["widget_key"]
        if widget_key not in st_module.session_state:
            continue
        sync_design_action_widget_to_shared_fn(
            widget_key,
            str(spec["shared_key"]),
            spec.get("proxy_key"),
        )


def reconcile_design_action_widgets_with_shared(
    selected_prefix: str,
    *,
    st_module: Any,
    design_action_widget_specs_fn: Callable[[str], list[dict]],
    get_param_fn: Callable[..., Any],
    sync_design_action_widget_to_shared_fn: Callable[..., None],
    debug_design_guidance_probe: bool,
    append_design_guide_trace_fn: Callable[..., None],
    time_ms_fn: Callable[[], int],
) -> list[str]:
    """Fallback sync for live edits when widget state drifted but on_change did not land."""
    changed: list[str] = []
    reconcile_probe: list[dict[str, object]] = []
    for spec in design_action_widget_specs_fn(selected_prefix):
        widget_key = str(spec["widget_key"])
        shared_key = str(spec["shared_key"])
        if widget_key not in st_module.session_state:
            reconcile_probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "missing_widget",
                }
            )
            continue
        try:
            widget_value = float(st_module.session_state.get(widget_key) or 0.0)
        except (TypeError, ValueError):
            reconcile_probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "bad_widget_value",
                    "widget_value_raw": st_module.session_state.get(widget_key),
                }
            )
            continue
        try:
            shared_value = float(get_param_fn(shared_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            shared_value = 0.0
        reconcile_probe.append(
            {
                "widget_key": widget_key,
                "shared_key": shared_key,
                "widget_value": widget_value,
                "shared_value": shared_value,
                "diff": float(widget_value - shared_value),
                "status": "equal" if abs(widget_value - shared_value) <= 1e-9 else "diff",
            }
        )
        if abs(widget_value - shared_value) <= 1e-9:
            continue
        sync_design_action_widget_to_shared_fn(
            widget_key,
            shared_key,
            spec.get("proxy_key"),
        )
        changed.append(shared_key)
    if debug_design_guidance_probe:
        try:
            append_design_guide_trace_fn(
                "design_action_reconcile",
                {
                    "selected_prefix": str(selected_prefix),
                    "changed": list(changed),
                    "probe": reconcile_probe,
                },
                run_id=f"dar_{time_ms_fn()}",
                source="design_action_reconcile",
            )
        except Exception:
            pass
    _record_design_action_state_transition(
        st_module,
        "reconcile_exit",
        selected_prefix=str(selected_prefix),
        changed=list(changed),
        probe=reconcile_probe,
    )
    return changed


def sync_design_action_widget_to_shared(
    widget_key: str,
    shared_key: str,
    proxy_key: str | None = None,
    *,
    trigger_rerun: bool = False,
    st_module: Any,
    debug_design_guidance_probe: bool,
    append_design_guide_trace_fn: Callable[..., None],
    get_param_fn: Callable[..., Any],
    mark_user_edit_fn: Callable[[str, str], None],
    set_shared_fn: Callable[..., None],
    invalidate_inputs_summary_packs_fn: Callable[..., None],
    queue_inputs_refresh_fn: Callable[[str, list[str]], None],
    invalidate_design_guide_caches_fn: Callable[..., None],
    mark_design_guide_dirty_fn: Callable[[], None],
    persist_active_beam_from_shared_fn: Callable[[], None],
    persist_state_snapshot_fn: Callable[[], None],
    debug_resolved_guidance_actions_fn: Callable[[dict], Any],
    shared_state_snapshot_fn: Callable[[], dict],
    sync_auto_design_invalidation_fn: Callable[[dict], None],
    debug_check_design_action_consistency_fn: Callable[[dict], None],
    time_ms_fn: Callable[[], int],
) -> None:
    value = st_module.session_state.get(widget_key)
    if value is None:
        _record_design_action_state_transition(
            st_module,
            "sync_skipped_missing_widget_value",
            widget_key=str(widget_key),
            shared_key=str(shared_key),
        )
        return
    numeric_value = float(value or 0.0)
    if shared_key.endswith("_Mstar_pos_manual") or shared_key.endswith("_Mstar_neg_manual"):
        numeric_value = max(0.0, numeric_value)
    try:
        st_module.session_state["_last_user_widget_key"] = str(widget_key)
    except Exception:
        pass
    _record_design_action_state_transition(
        st_module,
        "sync_entry",
        widget_key=str(widget_key),
        shared_key=str(shared_key),
        proxy_key=str(proxy_key) if proxy_key else None,
        widget_value=value,
        numeric_value=numeric_value,
        shared_before=get_param_fn(shared_key, None),
        proxy_before=get_param_fn(proxy_key, None) if proxy_key else None,
    )
    if debug_design_guidance_probe:
        try:
            append_design_guide_trace_fn(
                "design_action_widget_sync_entry",
                {
                    "widget_key": str(widget_key),
                    "shared_key": str(shared_key),
                    "proxy_key": str(proxy_key) if proxy_key else None,
                    "widget_value_raw": value,
                    "numeric_value": numeric_value,
                    "shared_before": get_param_fn(shared_key, None),
                    "proxy_before": get_param_fn(proxy_key, None) if proxy_key else None,
                },
                run_id=f"daws_{time_ms_fn()}",
                source="design_action_widget_sync",
            )
        except Exception:
            pass
    mark_user_edit_fn(widget_key, shared_key)
    set_shared_fn(shared_key, numeric_value, source="design_action_widget_sync")
    manual_owner_key = {
        "uls_Vstar": "manual_uls_Vstar",
        "uls_Nstar": "manual_uls_Nstar",
        "sls_Vstar": "manual_sls_Vstar",
        "sls_Nstar": "manual_sls_Nstar",
    }.get(shared_key)
    if manual_owner_key:
        set_shared_fn(
            manual_owner_key,
            numeric_value,
            source="design_action_widget_sync",
        )
    if proxy_key:
        set_shared_fn(proxy_key, numeric_value, source="design_action_widget_sync")
    if shared_key.endswith("_Mstar_pos_manual") or shared_key.endswith("_Mstar_neg_manual"):
        prefix = "uls" if shared_key.startswith("uls_") else "sls"
        pos = float(get_param_fn(f"{prefix}_Mstar_pos_manual", 0.0) or 0.0)
        neg = float(get_param_fn(f"{prefix}_Mstar_neg_manual", 0.0) or 0.0)
        set_shared_fn(f"{prefix}_Mstar", float(pos - neg), source="design_action_widget_sync")
        if prefix == "uls":
            set_shared_fn("Mu_star_pos_manual", float(pos), source="design_action_widget_sync")
            set_shared_fn("Mu_star_neg_manual", float(neg), source="design_action_widget_sync")
            set_shared_fn("Mu_star_manual", float(pos - neg), source="design_action_widget_sync")
            set_shared_fn("load_Mstar_proxy", float(pos - neg), source="design_action_widget_sync")
    if shared_key in {"uls_Nstar", "sls_Nstar"}:
        set_shared_fn("N_star", numeric_value, source="design_action_widget_sync")
    affected_keys = [
        key for key in (shared_key, manual_owner_key, proxy_key) if key
    ]
    invalidate_inputs_summary_packs_fn(
        source="design_action_widget_sync",
        updated_keys=affected_keys,
    )
    st_module.session_state["cached_results"] = None
    st_module.session_state["_cached_compute_results"] = None
    st_module.session_state["_last_compute_fp"] = None
    queue_inputs_refresh_fn(
        "design_action_widget_sync",
        affected_keys,
    )
    invalidate_design_guide_caches_fn(
        reason="design_action_widget_sync",
        updated_keys=affected_keys,
        preserve_apply_banner=False,
    )
    st_module.session_state.pop("pending_recommendation", None)
    st_module.session_state.pop("pending_recommendation_applied_id", None)
    st_module.session_state.pop("_solver_result", None)
    st_module.session_state.pop("_one_click_run_feedback", None)
    st_module.session_state.pop("auto_design_status", None)
    st_module.session_state.pop("auto_design_steps", None)
    st_module.session_state["inputs_dirty"] = True
    st_module.session_state["_inputs_dirty"] = True
    st_module.session_state["run_design_clicked"] = True
    mark_design_guide_dirty_fn()
    # Do not persist the beam or the project snapshot from this proxy-widget
    # callback.  The Inputs engineering transaction is the sole owner of the
    # beam revision and publication invalidation.  Persisting here used to
    # update the legacy beam record before that transaction ran; the canonical
    # commit then compared equal and incorrectly returned as a no-op.  The
    # result was a split page where serviceability used the new widget value
    # while the ULS summary and Design Brain publication retained the old one.
    # The owning page transaction consumes the shared values immediately after
    # this callback and performs the single authoritative persistence step.
    _record_design_action_state_transition(
        st_module,
        "sync_exit",
        widget_key=str(widget_key),
        shared_key=str(shared_key),
        proxy_key=str(proxy_key) if proxy_key else None,
        shared_after=get_param_fn(shared_key, None),
        proxy_after=get_param_fn(proxy_key, None) if proxy_key else None,
        pending_refresh=st_module.session_state.get("_pending_inputs_apply_refresh"),
    )
    if debug_design_guidance_probe:
        try:
            append_design_guide_trace_fn(
                "design_action_widget_sync_exit",
                {
                    "widget_key": str(widget_key),
                    "shared_key": str(shared_key),
                    "proxy_key": str(proxy_key) if proxy_key else None,
                    "shared_after": get_param_fn(shared_key, None),
                    "proxy_after": get_param_fn(proxy_key, None) if proxy_key else None,
                    "resolved_actions": debug_resolved_guidance_actions_fn(shared_state_snapshot_fn()),
                },
                run_id=f"daws_{time_ms_fn()}",
                source="design_action_widget_sync",
            )
        except Exception:
            pass
    sync_auto_design_invalidation_fn(shared_state_snapshot_fn())
    if debug_design_guidance_probe:
        debug_check_design_action_consistency_fn(shared_state_snapshot_fn())
    if trigger_rerun and not bool(st_module.session_state.get("_solver_running", False)):
        rerun_inputs_current_scope(st_module)


__all__ = [
    "commit_design_action_widgets_to_shared",
    "debug_check_design_action_consistency",
    "design_action_widget_specs",
    "hydrate_design_action_widgets_from_shared",
    "make_design_action_widget_callback",
    "mirror_design_action_proxies_from_shared",
    "reconcile_design_action_widgets_with_shared",
    "render_design_action_number_row",
    "sync_design_action_widget_to_shared",
]
