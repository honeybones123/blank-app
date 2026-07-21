from __future__ import annotations

import copy
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _load_archived_legacy_inputs_page():
    candidates = sorted((ROOT / "artifacts" / "audits").glob("legacy_inputs_page_removed_*.py"))
    if not candidates:
        raise RuntimeError("No archived legacy inputs_page reference found for parity comparison")
    path = candidates[-1]
    spec = importlib.util.spec_from_file_location("_archived_legacy_inputs_page", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load archived legacy inputs_page reference: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeContext:
    def __init__(self, calls: list[tuple[str, Any]], label: str) -> None:
        self.calls = calls
        self.label = label

    def __enter__(self):
        self.calls.append(("enter", self.label))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.calls.append(("exit", self.label))
        return False


class _FakeStreamlit:
    def __init__(self, session_state: dict[str, Any], calls: list[tuple[str, Any]]) -> None:
        self.session_state = session_state
        self._calls = calls

    def columns(self, spec, *, gap=None, vertical_alignment=None):
        self._calls.append(("columns", list(spec), gap, vertical_alignment))
        return [_FakeContext(self._calls, "col1"), _FakeContext(self._calls, "col2")]

    def number_input(self, label, **kwargs):
        normalized = dict(kwargs)
        normalized["on_change"] = bool(callable(normalized.get("on_change")))
        self._calls.append(("number_input", str(label), normalized))
        return self.session_state.get(str(kwargs.get("key")), 0.0)

    def rerun(self):
        self._calls.append(("rerun", None))
        raise RuntimeError("rerun requested")


def _run_render_number_row(module, *, with_columns: bool) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit({"inputs_load_Vstar_proxy": 123.4}, calls)
    original_st = module.st
    original_label = module.label_with_hover
    original_register = module._register_rendered_key

    def _label_with_hover(label, hover_md=None, *, required=False):
        calls.append(("label_with_hover", str(label), str(hover_md), bool(required)))

    def _register(key: str):
        calls.append(("register_rendered_key", str(key)))

    try:
        module.st = fake_st
        module.label_with_hover = _label_with_hover
        module._register_rendered_key = _register
        kwargs = {}
        if with_columns:
            kwargs = {"col_label": _FakeContext(calls, "provided_label"), "col_input": _FakeContext(calls, "provided_input")}
        result = module._render_design_action_number_row(
            label="Design shear Vu* (kN)",
            widget_key="inputs_load_Vstar_proxy",
            help_text="Factored design shear at the critical section.",
            on_change=lambda: None,
            disabled=True,
            **kwargs,
        )
    finally:
        module.st = original_st
        module.label_with_hover = original_label
        module._register_rendered_key = original_register

    return {"result": result, "calls": calls}


def _run_debug(module, seed: dict[str, Any]) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit(copy.deepcopy(seed), calls)
    original_st = module.st
    original_debug_probe = module.DEBUG_DESIGN_GUIDANCE_PROBE
    original_resolve = module._resolve_design_actions_from_state
    original_agent_debug = module._agent_debug_log

    def _resolve(state: dict):
        calls.append(("resolve_design_actions", dict(state)))
        return {"Mu": 11.0, "Vu": 22.0}

    def _agent_debug_log(message, data=None, **kwargs):
        calls.append(("agent_debug_log", message, dict(data or {}), dict(kwargs)))

    try:
        module.st = fake_st
        module.DEBUG_DESIGN_GUIDANCE_PROBE = True
        module._resolve_design_actions_from_state = _resolve
        module._agent_debug_log = _agent_debug_log
        result = module._debug_check_design_action_consistency({"state": "input"})
    finally:
        module.st = original_st
        module.DEBUG_DESIGN_GUIDANCE_PROBE = original_debug_probe
        module._resolve_design_actions_from_state = original_resolve
        module._agent_debug_log = original_agent_debug

    return {"result": result, "calls": calls}


def _run_callback(module) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    legacy_bridge = getattr(module, "_legacy_inputs_page", module)
    sync_owner = module if hasattr(module, "_sync_design_action_widget_to_shared") else legacy_bridge
    original_sync = sync_owner._sync_design_action_widget_to_shared

    def _sync(widget_key: str, shared_key: str, proxy_key=None, *, trigger_rerun=False):
        calls.append(("sync_design_action_widget_to_shared", widget_key, shared_key, proxy_key, bool(trigger_rerun)))

    try:
        sync_owner._sync_design_action_widget_to_shared = _sync
        callback = module._make_design_action_widget_callback(
            "inputs_load_Vstar_proxy",
            "uls_Vstar",
            "load_Vstar_proxy",
        )
        callback_callable = callable(callback)
        callback()
    finally:
        sync_owner._sync_design_action_widget_to_shared = original_sync

    return {"callback_callable": callback_callable, "calls": calls}


def _run_mirror(module, prefix: str) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    values = {
        f"{prefix}_Mstar_pos_manual": 10.0,
        f"{prefix}_Mstar_neg_manual": 2.0,
        f"{prefix}_Mstar": 8.0,
        f"{prefix}_Vstar": 44.0,
        f"{prefix}_Nstar": -3.0,
    }
    original_get_param = module.get_param
    original_set_shared = module.set_shared

    def _get_param(key, default=None):
        calls.append(("get_param", key, default))
        return values.get(str(key), default)

    def _set_shared(key, value, *, source=""):
        calls.append(("set_shared", key, value, source))

    try:
        module.get_param = _get_param
        module.set_shared = _set_shared
        result = module._mirror_design_action_proxies_from_shared(prefix)
    finally:
        module.get_param = original_get_param
        module.set_shared = original_set_shared

    return {"result": result, "calls": calls}


def _action_values(prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_Mstar_pos_manual": 10.0,
        f"{prefix}_Mstar_neg_manual": 2.0,
        "P_star": 0.0,
        "Tu_star": 0.0,
        f"{prefix}_Vstar": 44.0,
        f"{prefix}_Nstar": -3.0,
        f"{prefix}_Mstar": 8.0,
    }


def _signature_for(module, prefix: str, *, design_controls: bool, values: dict[str, float]) -> tuple:
    return (
        prefix,
        bool(design_controls),
        tuple(
            float(values.get(str(spec["shared_key"]), 0.0) or 0.0)
            for spec in module._design_action_widget_specs(prefix)
        ),
    )


def _run_hydrate(
    module,
    prefix: str,
    seed: dict[str, Any],
    *,
    force: bool,
    design_controls: bool,
) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    values = _action_values(prefix)
    fake_st = _FakeStreamlit(copy.deepcopy(seed), calls)
    original_st = module.st
    original_get_param = module.get_param
    if hasattr(module, "_state_hc_log"):
        log_owner = module
        log_name = "_state_hc_log"
    else:
        log_owner = module
        log_name = "hc_log"
    original_log = getattr(log_owner, log_name)

    def _get_param(key, default=None):
        calls.append(("get_param", key, default))
        return values.get(str(key), default)

    def _log(message, **kwargs):
        calls.append(("hc_log", message, dict(kwargs)))

    try:
        module.st = fake_st
        module.get_param = _get_param
        setattr(log_owner, log_name, _log)
        result = module._hydrate_design_action_widgets_from_shared(
            prefix,
            force=force,
            design_controls=design_controls,
        )
    finally:
        module.st = original_st
        module.get_param = original_get_param
        setattr(log_owner, log_name, original_log)

    widget_keys = [
        "inputs_load_Mstar_pos_proxy",
        "inputs_load_Mstar_neg_proxy",
        "inputs_P_star",
        "inputs_Tu_star",
        "inputs_load_Vstar_proxy",
        "inputs_load_Nstar_proxy",
        "inputs_load_Mstar_proxy",
        "_design_action_widget_signature",
    ]
    return {
        "result": result,
        "session": {key: fake_st.session_state.get(key) for key in widget_keys if key in fake_st.session_state},
        "calls": calls,
    }


def _run_commit(module, prefix: str, present_widget_keys: set[str]) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    session_state = {key: 1.0 for key in present_widget_keys}
    fake_st = _FakeStreamlit(session_state, calls)
    legacy_bridge = getattr(module, "_legacy_inputs_page", module)
    sync_owner = module if hasattr(module, "_sync_design_action_widget_to_shared") else legacy_bridge
    original_st = module.st
    original_sync = sync_owner._sync_design_action_widget_to_shared

    def _sync(widget_key: str, shared_key: str, proxy_key=None, *, trigger_rerun=False):
        calls.append(("sync_design_action_widget_to_shared", widget_key, shared_key, proxy_key, bool(trigger_rerun)))

    try:
        module.st = fake_st
        sync_owner._sync_design_action_widget_to_shared = _sync
        result = module._commit_design_action_widgets_to_shared(prefix)
    finally:
        module.st = original_st
        sync_owner._sync_design_action_widget_to_shared = original_sync

    return {"result": result, "calls": calls}


def _run_reconcile(
    module,
    prefix: str,
    seed: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit(copy.deepcopy(seed), calls)
    legacy_bridge = getattr(module, "_legacy_inputs_page", module)
    sync_owner = module if hasattr(module, "_sync_design_action_widget_to_shared") else legacy_bridge
    trace_owner = module if hasattr(module, "_append_design_guide_trace") else legacy_bridge
    original_st = module.st
    original_get_param = module.get_param
    original_sync = sync_owner._sync_design_action_widget_to_shared
    original_trace = trace_owner._append_design_guide_trace
    original_time = module.time.time

    def _get_param(key, default=None):
        calls.append(("get_param", key, default))
        return values.get(str(key), default)

    def _sync(widget_key: str, shared_key: str, proxy_key=None, *, trigger_rerun=False):
        calls.append(("sync_design_action_widget_to_shared", widget_key, shared_key, proxy_key, bool(trigger_rerun)))

    def _trace(event, payload, *, run_id=None, source=None):
        calls.append(("append_design_guide_trace", event, dict(payload), run_id, source))

    try:
        module.st = fake_st
        module.get_param = _get_param
        sync_owner._sync_design_action_widget_to_shared = _sync
        trace_owner._append_design_guide_trace = _trace
        module.time.time = lambda: 123.456
        result = module._reconcile_design_action_widgets_with_shared(prefix)
    finally:
        module.st = original_st
        module.get_param = original_get_param
        sync_owner._sync_design_action_widget_to_shared = original_sync
        trace_owner._append_design_guide_trace = original_trace
        module.time.time = original_time

    return {"result": result, "calls": calls}


def _owner(module, legacy_bridge, name: str):
    return module if hasattr(module, name) else legacy_bridge


def _run_queue(module, seed: dict[str, Any], *, source: str, keys: list[str], focus_section=None) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit(copy.deepcopy(seed), calls)
    original_st = module.st
    hydration_name = "_inputs_hydration_trace_log" if hasattr(module, "_inputs_hydration_trace_log") else "inputs_hydration_trace_log"
    original_hydration = getattr(module, hydration_name)

    def _hydration(phase: str, **extra):
        calls.append(("hydration_trace", phase, dict(extra)))

    try:
        module.st = fake_st
        setattr(module, hydration_name, _hydration)
        result = module._queue_inputs_refresh(source, list(keys), focus_section=focus_section)
    finally:
        module.st = original_st
        setattr(module, hydration_name, original_hydration)

    session_keys = (
        "_force_inputs_widget_reseed_once",
        "_fast_mode_focus_section",
        "_design_guide_banner_generic_only",
        "_pending_inputs_apply_refresh",
    )
    return {
        "result": result,
        "session": {key: copy.deepcopy(fake_st.session_state.get(key)) for key in session_keys if key in fake_st.session_state},
        "calls": calls,
    }


def _run_sync(
    module,
    seed: dict[str, Any],
    *,
    widget_key: str,
    shared_key: str,
    proxy_key: str | None,
    trigger_rerun: bool = False,
    solver_running: bool = False,
) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit(copy.deepcopy(seed), calls)
    if solver_running:
        fake_st.session_state["_solver_running"] = True
    legacy_bridge = getattr(module, "_legacy_inputs_page", module)
    original_st = module.st
    original_time = module.time.time

    patch_names = (
        "get_param",
        "mark_user_edit",
        "set_shared",
        "_invalidate_inputs_summary_packs",
        "_queue_inputs_refresh",
        "_invalidate_design_guide_caches",
        "_mark_design_guide_dirty",
        "persist_active_beam_from_shared",
        "persist_state_snapshot",
        "_append_design_guide_trace",
        "_debug_resolved_guidance_actions",
        "_sync_auto_design_invalidation",
        "_debug_check_design_action_consistency",
    )
    owners = {name: _owner(module, legacy_bridge, name) for name in patch_names}
    originals = {name: getattr(owners[name], name) for name in patch_names}

    shared_values = {
        shared_key: 5.0,
        proxy_key or "": 6.0,
        "uls_Mstar_pos_manual": 12.0,
        "uls_Mstar_neg_manual": 3.0,
        "sls_Mstar_pos_manual": 7.0,
        "sls_Mstar_neg_manual": 2.0,
    }

    def _get_param(key, default=None):
        calls.append(("get_param", key, default))
        return shared_values.get(str(key), default)

    def _mark_user_edit(widget_key_arg, shared_key_arg):
        calls.append(("mark_user_edit", widget_key_arg, shared_key_arg))

    def _set_shared(key, value, *, source=""):
        calls.append(("set_shared", key, value, source))

    def _invalidate_inputs_summary_packs(*, source: str, updated_keys=None):
        calls.append(("invalidate_inputs_summary_packs", source, list(updated_keys or [])))

    def _queue(source: str, keys: list[str], *, focus_section=None):
        calls.append(("queue_inputs_refresh", source, list(keys), focus_section))

    def _invalidate_design_guide_caches(*, reason: str, updated_keys=None, preserve_apply_banner=False):
        calls.append(("invalidate_design_guide_caches", reason, list(updated_keys or []), bool(preserve_apply_banner)))

    def _mark_dirty():
        calls.append(("mark_design_guide_dirty", None))

    def _persist_active():
        calls.append(("persist_active_beam_from_shared", None))

    def _persist_snapshot(*args, **kwargs):
        calls.append(("persist_state_snapshot", args, kwargs))

    def _trace(event, payload, *, run_id=None, source=None):
        calls.append(("append_design_guide_trace", event, dict(payload), run_id, source))

    def _debug_resolved(state=None):
        calls.append(("debug_resolved_guidance_actions", dict(state or {})))
        return {"resolved": "actions"}

    def _sync_invalidation(state=None):
        calls.append(("sync_auto_design_invalidation", dict(state or {})))

    def _debug_consistency(state):
        calls.append(("debug_check_design_action_consistency", dict(state or {})))

    replacements = {
        "get_param": _get_param,
        "mark_user_edit": _mark_user_edit,
        "set_shared": _set_shared,
        "_invalidate_inputs_summary_packs": _invalidate_inputs_summary_packs,
        "_queue_inputs_refresh": _queue,
        "_invalidate_design_guide_caches": _invalidate_design_guide_caches,
        "_mark_design_guide_dirty": _mark_dirty,
        "persist_active_beam_from_shared": _persist_active,
        "persist_state_snapshot": _persist_snapshot,
        "_append_design_guide_trace": _trace,
        "_debug_resolved_guidance_actions": _debug_resolved,
        "_sync_auto_design_invalidation": _sync_invalidation,
        "_debug_check_design_action_consistency": _debug_consistency,
    }

    rerun = False
    try:
        module.st = fake_st
        module.time.time = lambda: 123.456
        for name, replacement in replacements.items():
            setattr(owners[name], name, replacement)
        try:
            result = module._sync_design_action_widget_to_shared(
                widget_key,
                shared_key,
                proxy_key,
                trigger_rerun=trigger_rerun,
            )
        except RuntimeError as exc:
            if str(exc) != "rerun requested":
                raise
            result = None
            rerun = True
    finally:
        module.st = original_st
        module.time.time = original_time
        for name, original in originals.items():
            setattr(owners[name], name, original)

    session_keys = (
        "_last_user_widget_key",
        "cached_results",
        "_cached_compute_results",
        "_last_compute_fp",
        "pending_recommendation",
        "pending_recommendation_applied_id",
        "_solver_result",
        "_one_click_run_feedback",
        "auto_design_status",
        "auto_design_steps",
        "inputs_dirty",
        "_inputs_dirty",
        "run_design_clicked",
        "_solver_running",
    )
    return {
        "result": result,
        "rerun": rerun,
        "session": {key: copy.deepcopy(fake_st.session_state.get(key)) for key in session_keys if key in fake_st.session_state},
        "calls": calls,
    }


def _run_mark_dirty(module, seed: dict[str, Any]) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit(copy.deepcopy(seed), calls)
    original_st = module.st
    try:
        module.st = fake_st
        result = module._mark_design_guide_dirty()
    finally:
        module.st = original_st
    return {
        "result": result,
        "session": copy.deepcopy(fake_st.session_state),
        "calls": calls,
    }


def _run_guidance_snapshot(module, seed: dict[str, Any]) -> dict[str, Any]:
    seeded = copy.deepcopy(seed)
    result_probe_key = next(iter(getattr(module, "RESULT_KEYS", ("_result_probe_key",))), "_result_probe_key")
    seeded[str(result_probe_key)] = "remove me"
    result = module._guidance_state_snapshot(seeded)
    removed_probe_keys = (
        "pending_recommendation",
        "_solver_result",
        "_one_click_run_feedback",
        "_bend_pack",
        "shear_design_status",
        "shear_required_spacing_mm",
    )
    default_probe_keys = ("b", "D", "fc", "uls_Mstar", "uls_Vstar")
    return {
        "removed_absent": {key: key not in result for key in removed_probe_keys},
        "default_probe": {key: copy.deepcopy(result.get(key)) for key in default_probe_keys},
        "custom_key": copy.deepcopy(result.get("custom_key")),
        "result_key_absent": str(result_probe_key) not in result,
        "key_count": len(result),
    }


def _run_debug_resolved(module, seed: dict[str, Any]) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    original_snapshot = module._guidance_state_snapshot
    original_resolve = module._resolve_design_actions_from_state

    def _snapshot(state=None):
        calls.append(("guidance_state_snapshot", dict(state or {})))
        return {"snapshot": "state", **dict(state or {})}

    def _resolve(state):
        calls.append(("resolve_design_actions", dict(state or {})))
        return {
            "source": "manual",
            "Mu": 11.0,
            "Vu": 22.0,
            "Nu": -3.0,
            "SLS_M": 4.0,
            "SLS_V": 5.0,
            "actions_source": "widgets",
            "actions_mode": "ULS",
            "signature": ["a", "b"],
        }

    try:
        module._guidance_state_snapshot = _snapshot
        module._resolve_design_actions_from_state = _resolve
        result = module._debug_resolved_guidance_actions(seed)
    finally:
        module._guidance_state_snapshot = original_snapshot
        module._resolve_design_actions_from_state = original_resolve
    return {"result": result, "calls": calls}


def _run_auto_invalidation(
    module,
    seed: dict[str, Any],
    *,
    current_fingerprint: tuple,
) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit(copy.deepcopy(seed), calls)
    original_st = module.st
    original_fingerprint = module._auto_design_governing_fingerprint
    original_clear = module._clear_auto_design_runtime_latches

    def _fingerprint(state=None):
        calls.append(("auto_design_governing_fingerprint", dict(state or {})))
        return tuple(current_fingerprint)

    def _clear(reason: str):
        calls.append(("clear_auto_design_runtime_latches", reason))
        fake_st.session_state["_auto_design_latch_clear_latest"] = {"reason": reason}
        return {"reason": reason}

    try:
        module.st = fake_st
        module._auto_design_governing_fingerprint = _fingerprint
        module._clear_auto_design_runtime_latches = _clear
        result = module._sync_auto_design_invalidation({"D": 600.0})
    finally:
        module.st = original_st
        module._auto_design_governing_fingerprint = original_fingerprint
        module._clear_auto_design_runtime_latches = original_clear

    session_keys = (
        "_auto_design_last_fingerprint",
        "_auto_design_invalidated",
        "pending_recommendation",
        "pending_recommendation_applied_id",
        "_solver_result",
        "_one_click_run_feedback",
        "auto_design_status",
        "auto_design_steps",
        "auto_design_request_source",
        "_auto_design_request_source",
        "_auto_design_requested_at_ts",
        "_auto_design_auto_invoke",
        "_inputs_action_run_auto_design",
        "auto_design_invoke_set",
        "auto_design_invoke_pending",
        "auto_design_invoke_consumed",
        "_auto_design_latch_clear_latest",
    )
    return {
        "result": result,
        "session": {key: copy.deepcopy(fake_st.session_state.get(key)) for key in session_keys if key in fake_st.session_state},
        "calls": calls,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    legacy_inputs_page = _load_archived_legacy_inputs_page()
    import inputs_page_route_coordinators as route

    render_cases = {
        "provided_columns": {
            "legacy": _run_render_number_row(legacy_inputs_page, with_columns=True),
            "route": _run_render_number_row(route, with_columns=True),
        },
        "created_columns": {
            "legacy": _run_render_number_row(legacy_inputs_page, with_columns=False),
            "route": _run_render_number_row(route, with_columns=False),
        },
    }
    debug_seed_uls = {
        "loads_edit_mode": "ULS",
        "inputs_load_Mstar_pos_proxy": 30.0,
        "inputs_load_Mstar_neg_proxy": 5.0,
        "inputs_load_Vstar_proxy": 90.0,
        "uls_Mstar": 25.0,
        "uls_Mstar_pos_manual": 30.0,
        "uls_Mstar_neg_manual": 5.0,
        "uls_Vstar": 90.0,
    }
    debug_cases = {
        "uls_logs": {
            "legacy": _run_debug(legacy_inputs_page, debug_seed_uls),
            "route": _run_debug(route, debug_seed_uls),
        },
        "sls_skips": {
            "legacy": _run_debug(legacy_inputs_page, {"loads_edit_mode": "SLS"}),
            "route": _run_debug(route, {"loads_edit_mode": "SLS"}),
        },
    }
    spec_cases = {
        prefix: {
            "legacy": legacy_inputs_page._design_action_widget_specs(prefix),
            "route": route._design_action_widget_specs(prefix),
        }
        for prefix in ("uls", "sls")
    }
    callback_case = {
        "legacy": _run_callback(legacy_inputs_page),
        "route": _run_callback(route),
    }
    mirror_cases = {
        prefix: {
            "legacy": _run_mirror(legacy_inputs_page, prefix),
            "route": _run_mirror(route, prefix),
        }
        for prefix in ("uls", "sls")
    }
    matching_signature = _signature_for(legacy_inputs_page, "uls", design_controls=False, values=_action_values("uls"))
    hydrate_cases = {
        "matching_signature_no_force": {
            "legacy": _run_hydrate(
                legacy_inputs_page,
                "uls",
                {
                    "_design_action_widget_signature": matching_signature,
                    "inputs_load_Mstar_pos_proxy": 99.0,
                    "inputs_load_Mstar_neg_proxy": 98.0,
                    "inputs_P_star": 97.0,
                    "inputs_Tu_star": 96.0,
                    "inputs_load_Vstar_proxy": 95.0,
                    "inputs_load_Nstar_proxy": 94.0,
                },
                force=False,
                design_controls=False,
            ),
            "route": _run_hydrate(
                route,
                "uls",
                {
                    "_design_action_widget_signature": matching_signature,
                    "inputs_load_Mstar_pos_proxy": 99.0,
                    "inputs_load_Mstar_neg_proxy": 98.0,
                    "inputs_P_star": 97.0,
                    "inputs_Tu_star": 96.0,
                    "inputs_load_Vstar_proxy": 95.0,
                    "inputs_load_Nstar_proxy": 94.0,
                },
                force=False,
                design_controls=False,
            ),
        },
        "force_hydrates": {
            "legacy": _run_hydrate(legacy_inputs_page, "uls", {}, force=True, design_controls=False),
            "route": _run_hydrate(route, "uls", {}, force=True, design_controls=False),
        },
        "design_controls_hydrates_and_logs": {
            "legacy": _run_hydrate(
                legacy_inputs_page,
                "sls",
                {
                    "_dev_mode": True,
                    "actions_mode": "design",
                    "inputs_load_Mstar_pos_proxy": 1.0,
                    "inputs_load_Mstar_neg_proxy": 2.0,
                    "inputs_load_Mstar_proxy": 3.0,
                },
                force=False,
                design_controls=True,
            ),
            "route": _run_hydrate(
                route,
                "sls",
                {
                    "_dev_mode": True,
                    "actions_mode": "design",
                    "inputs_load_Mstar_pos_proxy": 1.0,
                    "inputs_load_Mstar_neg_proxy": 2.0,
                    "inputs_load_Mstar_proxy": 3.0,
                },
                force=False,
                design_controls=True,
            ),
        },
    }
    commit_cases = {
        "none_present": {
            "legacy": _run_commit(legacy_inputs_page, "uls", set()),
            "route": _run_commit(route, "uls", set()),
        },
        "partial_present": {
            "legacy": _run_commit(
                legacy_inputs_page,
                "sls",
                {"inputs_load_Mstar_pos_proxy", "inputs_load_Vstar_proxy", "inputs_load_Nstar_proxy"},
            ),
            "route": _run_commit(
                route,
                "sls",
                {"inputs_load_Mstar_pos_proxy", "inputs_load_Vstar_proxy", "inputs_load_Nstar_proxy"},
            ),
        },
    }
    reconcile_values = _action_values("uls")
    reconcile_cases = {
        "all_missing": {
            "legacy": _run_reconcile(legacy_inputs_page, "uls", {}, reconcile_values),
            "route": _run_reconcile(route, "uls", {}, reconcile_values),
        },
        "equal_and_bad": {
            "legacy": _run_reconcile(
                legacy_inputs_page,
                "uls",
                {
                    "inputs_load_Mstar_pos_proxy": 10.0,
                    "inputs_load_Mstar_neg_proxy": "bad",
                    "inputs_P_star": 0.0,
                    "inputs_Tu_star": 0.0,
                    "inputs_load_Vstar_proxy": 44.0,
                    "inputs_load_Nstar_proxy": -3.0,
                },
                reconcile_values,
            ),
            "route": _run_reconcile(
                route,
                "uls",
                {
                    "inputs_load_Mstar_pos_proxy": 10.0,
                    "inputs_load_Mstar_neg_proxy": "bad",
                    "inputs_P_star": 0.0,
                    "inputs_Tu_star": 0.0,
                    "inputs_load_Vstar_proxy": 44.0,
                    "inputs_load_Nstar_proxy": -3.0,
                },
                reconcile_values,
            ),
        },
        "drift_syncs": {
            "legacy": _run_reconcile(
                legacy_inputs_page,
                "uls",
                {
                    "inputs_load_Mstar_pos_proxy": 11.0,
                    "inputs_load_Mstar_neg_proxy": 2.0,
                    "inputs_P_star": 1.0,
                    "inputs_Tu_star": 0.0,
                    "inputs_load_Vstar_proxy": 40.0,
                    "inputs_load_Nstar_proxy": -3.0,
                },
                reconcile_values,
            ),
            "route": _run_reconcile(
                route,
                "uls",
                {
                    "inputs_load_Mstar_pos_proxy": 11.0,
                    "inputs_load_Mstar_neg_proxy": 2.0,
                    "inputs_P_star": 1.0,
                    "inputs_Tu_star": 0.0,
                    "inputs_load_Vstar_proxy": 40.0,
                    "inputs_load_Nstar_proxy": -3.0,
                },
                reconcile_values,
            ),
        },
    }
    queue_cases = {
        "normal": {
            "legacy": _run_queue(
                legacy_inputs_page,
                {"_force_inputs_widget_reseed_once": True},
                source="design_action_widget_sync",
                keys=["uls_Vstar"],
            ),
            "route": _run_queue(
                route,
                {"_force_inputs_widget_reseed_once": True},
                source="design_action_widget_sync",
                keys=["uls_Vstar"],
            ),
        },
        "guidance_focus": {
            "legacy": _run_queue(
                legacy_inputs_page,
                {},
                source="guidance:apply",
                keys=["b"],
                focus_section="model",
            ),
            "route": _run_queue(
                route,
                {},
                source="guidance:apply",
                keys=["b"],
                focus_section="model",
            ),
        },
    }
    sync_cases = {
        "missing_value_returns": {
            "legacy": _run_sync(
                legacy_inputs_page,
                {},
                widget_key="inputs_load_Vstar_proxy",
                shared_key="uls_Vstar",
                proxy_key="load_Vstar_proxy",
            ),
            "route": _run_sync(
                route,
                {},
                widget_key="inputs_load_Vstar_proxy",
                shared_key="uls_Vstar",
                proxy_key="load_Vstar_proxy",
            ),
        },
        "moment_clamps_and_sets_signed": {
            "legacy": _run_sync(
                legacy_inputs_page,
                {"inputs_load_Mstar_pos_proxy": -9.0},
                widget_key="inputs_load_Mstar_pos_proxy",
                shared_key="uls_Mstar_pos_manual",
                proxy_key="load_Mstar_pos_proxy",
            ),
            "route": _run_sync(
                route,
                {"inputs_load_Mstar_pos_proxy": -9.0},
                widget_key="inputs_load_Mstar_pos_proxy",
                shared_key="uls_Mstar_pos_manual",
                proxy_key="load_Mstar_pos_proxy",
            ),
        },
        "axial_sets_n_star": {
            "legacy": _run_sync(
                legacy_inputs_page,
                {"inputs_load_Nstar_proxy": -4.0},
                widget_key="inputs_load_Nstar_proxy",
                shared_key="sls_Nstar",
                proxy_key="load_Nstar_proxy",
            ),
            "route": _run_sync(
                route,
                {"inputs_load_Nstar_proxy": -4.0},
                widget_key="inputs_load_Nstar_proxy",
                shared_key="sls_Nstar",
                proxy_key="load_Nstar_proxy",
            ),
        },
        "rerun_when_requested": {
            "legacy": _run_sync(
                legacy_inputs_page,
                {"inputs_load_Vstar_proxy": 44.0},
                widget_key="inputs_load_Vstar_proxy",
                shared_key="uls_Vstar",
                proxy_key="load_Vstar_proxy",
                trigger_rerun=True,
            ),
            "route": _run_sync(
                route,
                {"inputs_load_Vstar_proxy": 44.0},
                widget_key="inputs_load_Vstar_proxy",
                shared_key="uls_Vstar",
                proxy_key="load_Vstar_proxy",
                trigger_rerun=True,
            ),
        },
        "solver_running_skips_rerun": {
            "legacy": _run_sync(
                legacy_inputs_page,
                {"inputs_load_Vstar_proxy": 44.0},
                widget_key="inputs_load_Vstar_proxy",
                shared_key="uls_Vstar",
                proxy_key="load_Vstar_proxy",
                trigger_rerun=True,
                solver_running=True,
            ),
            "route": _run_sync(
                route,
                {"inputs_load_Vstar_proxy": 44.0},
                widget_key="inputs_load_Vstar_proxy",
                shared_key="uls_Vstar",
                proxy_key="load_Vstar_proxy",
                trigger_rerun=True,
                solver_running=True,
            ),
        },
    }
    mark_dirty_seed = {
        "_design_guide_apply_banner_payload": {"keep": False},
        "_design_guide_apply_banner_meta": {"old": True},
        "_design_guide_cached_fingerprint": ("fp",),
        "_design_guide_cached_items": [{"x": 1}],
        "_design_guide_cached_debug": {"debug": True},
        "_design_guide_fp": ("simple",),
        "_design_guide_cache": [{"simple": True}],
        "_design_guide_pending_step_ctx": {"step": 1},
        "_design_guide_debug_bundle": {"debug": True},
        "_design_guide_reco_trace": ["old"],
        "_design_guide_rank_trace": ["old"],
        "_design_guide_step_history": ["history"],
        "_design_guide_first_target_band_step": {"first": True},
        "_design_guide_history_anchor": "anchor",
    }
    mark_dirty_case = {
        "legacy": _run_mark_dirty(legacy_inputs_page, mark_dirty_seed),
        "route": _run_mark_dirty(route, mark_dirty_seed),
    }
    guidance_snapshot_seed = {
        "custom_key": {"kept": True},
        "pending_recommendation": {"stale": True},
        "_solver_result": {"stale": True},
        "_one_click_run_feedback": {"stale": True},
        "_bend_pack": {"stale": True},
        "shear_design_status": "FAIL",
        "shear_required_spacing_mm": 100.0,
    }
    guidance_snapshot_case = {
        "legacy": _run_guidance_snapshot(legacy_inputs_page, guidance_snapshot_seed),
        "route": _run_guidance_snapshot(route, guidance_snapshot_seed),
    }
    debug_resolved_case = {
        "legacy": _run_debug_resolved(legacy_inputs_page, {"D": 600.0}),
        "route": _run_debug_resolved(route, {"D": 600.0}),
    }
    stale_auto_design_seed = {
        "_auto_design_last_fingerprint": (("old", "fingerprint"),),
        "pending_recommendation": {"stale": True},
        "pending_recommendation_applied_id": "old-id",
        "_solver_result": {"stale": True},
        "_one_click_run_feedback": {"stale": True},
        "auto_design_status": "running",
        "auto_design_steps": [{"step": 1}],
        "auto_design_request_source": "old",
        "_auto_design_request_source": "old",
        "_auto_design_requested_at_ts": 123.0,
        "_auto_design_auto_invoke": True,
        "_inputs_action_run_auto_design": True,
        "auto_design_invoke_set": True,
        "auto_design_invoke_pending": True,
        "auto_design_invoke_consumed": True,
    }
    auto_invalidation_cases = {
        "first_fingerprint_only": {
            "legacy": _run_auto_invalidation(
                legacy_inputs_page,
                {},
                current_fingerprint=(("new", "fingerprint"),),
            ),
            "route": _run_auto_invalidation(
                route,
                {},
                current_fingerprint=(("new", "fingerprint"),),
            ),
        },
        "same_fingerprint_noop": {
            "legacy": _run_auto_invalidation(
                legacy_inputs_page,
                {"_auto_design_last_fingerprint": (("same", "fingerprint"),)},
                current_fingerprint=(("same", "fingerprint"),),
            ),
            "route": _run_auto_invalidation(
                route,
                {"_auto_design_last_fingerprint": (("same", "fingerprint"),)},
                current_fingerprint=(("same", "fingerprint"),),
            ),
        },
        "changed_fingerprint_invalidates": {
            "legacy": _run_auto_invalidation(
                legacy_inputs_page,
                stale_auto_design_seed,
                current_fingerprint=(("new", "fingerprint"),),
            ),
            "route": _run_auto_invalidation(
                route,
                stale_auto_design_seed,
                current_fingerprint=(("new", "fingerprint"),),
            ),
        },
    }

    checks = {
        "all_render_helpers_match_legacy": all(case["legacy"] == case["route"] for case in render_cases.values()),
        "all_debug_helpers_match_legacy": all(case["legacy"] == case["route"] for case in debug_cases.values()),
        "all_widget_specs_match_legacy": all(case["legacy"] == case["route"] for case in spec_cases.values()),
        "callback_factory_matches_legacy": callback_case["legacy"] == callback_case["route"],
        "all_proxy_mirror_cases_match_legacy": all(case["legacy"] == case["route"] for case in mirror_cases.values()),
        "all_hydrate_cases_match_legacy": all(case["legacy"] == case["route"] for case in hydrate_cases.values()),
        "all_commit_cases_match_legacy": all(case["legacy"] == case["route"] for case in commit_cases.values()),
        "all_reconcile_cases_match_legacy": all(case["legacy"] == case["route"] for case in reconcile_cases.values()),
        "all_queue_cases_match_legacy": all(case["legacy"] == case["route"] for case in queue_cases.values()),
        "all_sync_cases_match_legacy": all(case["legacy"] == case["route"] for case in sync_cases.values()),
        "mark_design_guide_dirty_matches_legacy": mark_dirty_case["legacy"] == mark_dirty_case["route"],
        "guidance_state_snapshot_matches_legacy": guidance_snapshot_case["legacy"] == guidance_snapshot_case["route"],
        "debug_resolved_guidance_actions_matches_legacy": debug_resolved_case["legacy"] == debug_resolved_case["route"],
        "all_auto_invalidation_cases_match_legacy": all(case["legacy"] == case["route"] for case in auto_invalidation_cases.values()),
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    checks["route_no_longer_calls_legacy_render_number_row"] = (
        "_legacy_inputs_page._render_design_action_number_row" not in route_source
    )
    checks["route_no_longer_calls_legacy_debug_check"] = (
        "_legacy_inputs_page._debug_check_design_action_consistency" not in route_source
    )
    checks["route_no_longer_calls_legacy_widget_specs"] = (
        "_legacy_inputs_page._design_action_widget_specs" not in route_source
    )
    checks["route_no_longer_calls_legacy_callback_factory"] = (
        "_legacy_inputs_page._make_design_action_widget_callback" not in route_source
    )
    checks["route_no_longer_calls_legacy_proxy_mirror"] = (
        "_legacy_inputs_page._mirror_design_action_proxies_from_shared" not in route_source
    )
    checks["route_no_longer_calls_legacy_hydrate"] = (
        "_legacy_inputs_page._hydrate_design_action_widgets_from_shared" not in route_source
    )
    checks["route_no_longer_calls_legacy_commit"] = (
        "_legacy_inputs_page._commit_design_action_widgets_to_shared" not in route_source
    )
    checks["route_no_longer_calls_legacy_reconcile"] = (
        "_legacy_inputs_page._reconcile_design_action_widgets_with_shared" not in route_source
    )
    checks["route_no_longer_calls_legacy_sync_design_action_widget"] = (
        "_legacy_inputs_page._sync_design_action_widget_to_shared" not in route_source
    )
    checks["route_no_longer_calls_legacy_append_design_guide_trace"] = (
        "_legacy_inputs_page._append_design_guide_trace" not in route_source
    )
    checks["route_no_longer_calls_legacy_invalidate_design_guide_caches"] = (
        "_legacy_inputs_page._invalidate_design_guide_caches" not in route_source
    )
    checks["route_no_longer_calls_legacy_mark_design_guide_dirty"] = (
        "_legacy_inputs_page._mark_design_guide_dirty" not in route_source
    )
    checks["route_no_longer_calls_legacy_debug_resolved_guidance_actions"] = (
        "_legacy_inputs_page._debug_resolved_guidance_actions" not in route_source
    )
    checks["route_no_longer_calls_legacy_sync_auto_design_invalidation"] = (
        "_legacy_inputs_page._sync_auto_design_invalidation" not in route_source
    )

    status = "PASS" if all(checks.values()) else "FAIL"
    artifact = {
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
        "render_cases": render_cases,
        "debug_cases": debug_cases,
        "spec_cases": spec_cases,
        "callback_case": callback_case,
        "mirror_cases": mirror_cases,
        "hydrate_cases": hydrate_cases,
        "commit_cases": commit_cases,
        "reconcile_cases": reconcile_cases,
        "queue_cases": queue_cases,
        "sync_cases": sync_cases,
        "mark_dirty_case": mark_dirty_case,
        "guidance_snapshot_case": guidance_snapshot_case,
        "debug_resolved_case": debug_resolved_case,
        "auto_invalidation_cases": auto_invalidation_cases,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_design_action_helpers_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_route_design_action_helpers_parity_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Design Action Helpers Parity",
                "",
                f"Status: {status}",
                "",
                "## Checks",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "## Scope",
                "- Verifies route-local `_render_design_action_number_row` against legacy with provided and created columns.",
                "- Verifies route-local `_debug_check_design_action_consistency` against legacy for ULS logging and SLS skip behavior.",
                "- Verifies route-local `_design_action_widget_specs` against legacy for ULS and SLS prefixes.",
                "- Verifies route-local `_make_design_action_widget_callback` delegates to the same sync mutation contract.",
                "- Verifies route-local `_mirror_design_action_proxies_from_shared` get/set call order for ULS and SLS.",
                "- Verifies route-local `_hydrate_design_action_widgets_from_shared` signature, force, design-control, missing-widget, and dev-log behavior.",
                "- Verifies route-local `_commit_design_action_widgets_to_shared` skips missing widgets and preserves sync order.",
                "- Verifies route-local `_reconcile_design_action_widgets_with_shared` missing, bad, equal, diff, sync, trace, and return behavior.",
                "- Verifies route-local `_queue_inputs_refresh` session effects and hydration trace call.",
                "- Verifies route-local `_sync_design_action_widget_to_shared` missing, moment, axial, cache invalidation, queue, persistence, trace, dirty, and rerun behavior.",
                "- Verifies route no longer calls old-page Design Guide trace append or cache invalidation from the Design Actions path.",
                "- Verifies route-local Design Guide dirty marking, guidance state snapshot cleanup, resolved-actions debug payload, and auto-design invalidation behavior.",
                "- Verifies route no longer calls old-page Design Guide dirty, debug resolved-actions, or auto-design invalidation helpers from the Design Actions path.",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
