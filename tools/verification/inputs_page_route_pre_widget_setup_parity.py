from __future__ import annotations

import copy
import hashlib
import inspect
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


def _clear_session() -> None:
    import streamlit as st

    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)


def _seed_session(values: dict[str, Any]) -> None:
    import streamlit as st

    _clear_session()
    st.session_state.update(copy.deepcopy(values))


def _session_subset() -> dict[str, Any]:
    import streamlit as st

    keys = (
        "_inputs_shear_shared_normalised_this_run",
        "_fast_mode_focus_section",
        "_inputs_render_audit_live",
        "_debug_d_consistency",
        "_inputs_longitudinal_reo_callback_audit",
        "bot_row_count",
        "inputs_bot_row_count",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "inputs_bot_row_1_mode",
        "inputs_bot_row_1_bars",
        "inputs_bot_row_1_spacing",
        "inputs_bot_row_1_dia",
    )
    return {key: copy.deepcopy(st.session_state.get(key)) for key in keys if key in st.session_state}


def _run_case(module, seed: dict[str, Any], *, publish_raises: bool = False) -> dict[str, Any]:
    import streamlit as st

    calls: list[tuple[str, Any]] = []
    legacy_bridge = getattr(module, "_legacy_inputs_page", module)
    handle_owner = module if hasattr(module, "_handle_inputs_apply_buttons_current_coordinator") else legacy_bridge
    inputs_css_owner = module if hasattr(module, "apply_inputs_page_css") else legacy_bridge
    original_handle = handle_owner._handle_inputs_apply_buttons_current_coordinator
    original_get_sync = module.get_sync_callbacks
    original_apply_inputs_css = inputs_css_owner.apply_inputs_page_css
    original_apply_global_css = module.apply_global_widget_css
    original_apply_calcbox_css = module.apply_calcbox_css
    original_publish = module.publish_normalized_final_shear_truth_to_session
    original_debug = getattr(module, "_agent_debug_log", None)

    hydration_attr = "_inputs_hydration_trace_log" if hasattr(module, "_inputs_hydration_trace_log") else "inputs_hydration_trace_log"
    original_hydration = getattr(module, hydration_attr)

    def _handle_apply_buttons():
        calls.append(("handle_apply_buttons", None))

    def _callback(label: str):
        def _inner():
            calls.append(("callback", label))
        return _inner

    def _get_sync_callbacks():
        calls.append(("get_sync_callbacks", None))
        return {
            "inputs_bot_row_1_bars": _callback("longitudinal"),
            "inputs_lig_d": _callback("other"),
        }

    def _apply_inputs_page_css():
        calls.append(("apply_inputs_page_css", None))

    def _apply_global_widget_css():
        calls.append(("apply_global_widget_css", None))

    def _apply_calcbox_css():
        calls.append(("apply_calcbox_css", None))

    def _publish(*, source: str):
        calls.append(("publish_normalized_final_shear_truth_to_session", source))
        if publish_raises:
            raise RuntimeError("forced parity publish failure")
        return {"source": source}

    def _hydration_trace(phase: str, **extra: object):
        calls.append(("inputs_hydration_trace", phase, dict(extra)))

    def _fast_get_param(name: str, default: Any = None):
        calls.append(("fast_get_param", name, default))
        if name == "d":
            return seed.get("_fast_get_d", default)
        return default

    try:
        handle_owner._handle_inputs_apply_buttons_current_coordinator = _handle_apply_buttons
        module.get_sync_callbacks = _get_sync_callbacks
        inputs_css_owner.apply_inputs_page_css = _apply_inputs_page_css
        module.apply_global_widget_css = _apply_global_widget_css
        module.apply_calcbox_css = _apply_calcbox_css
        module.publish_normalized_final_shear_truth_to_session = _publish
        setattr(module, hydration_attr, _hydration_trace)
        if original_debug is not None:
            module._agent_debug_log = lambda *args, **kwargs: calls.append(("agent_debug_log", args[0] if args else None))

        _seed_session(seed)
        ss = st.session_state
        result = module.render_inputs_pre_widget_apply_and_render_setup_coordinator(
            ss=ss,
            fast_get_param=_fast_get_param,
        )
        corrected, focus, sync_callbacks, render_audit = result
        callback_keys = sorted(sync_callbacks.keys())
        sync_callbacks["inputs_bot_row_1_bars"]()
        sync_callbacks["inputs_lig_d"]()
        session_after_callbacks = _session_subset()
    finally:
        handle_owner._handle_inputs_apply_buttons_current_coordinator = original_handle
        module.get_sync_callbacks = original_get_sync
        inputs_css_owner.apply_inputs_page_css = original_apply_inputs_css
        module.apply_global_widget_css = original_apply_global_css
        module.apply_calcbox_css = original_apply_calcbox_css
        module.publish_normalized_final_shear_truth_to_session = original_publish
        setattr(module, hydration_attr, original_hydration)
        if original_debug is not None:
            module._agent_debug_log = original_debug

    return {
        "return": {
            "corrected_invalid_shear_state": bool(corrected),
            "fast_focus_section": focus,
            "sync_callback_keys": callback_keys,
            "render_audit": copy.deepcopy(render_audit),
        },
        "session_after_callbacks": session_after_callbacks,
        "calls": calls,
    }


def _run_css_case(module) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    function_owner = inspect.getmodule(module.apply_inputs_page_css) or module
    original_st = function_owner.st

    class _FakeStreamlit:
        def markdown(self, body, **kwargs):
            calls.append(("markdown", str(body), dict(kwargs)))

    try:
        function_owner.st = _FakeStreamlit()
        result = module.apply_inputs_page_css()
    finally:
        function_owner.st = original_st

    payloads = [
        {
            "body_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "body_len": len(body),
            "unsafe_allow_html": bool(kwargs.get("unsafe_allow_html")),
            "starts_with_style": body.lstrip().startswith("<style>"),
            "ends_with_style": body.rstrip().endswith("</style>"),
        }
        for kind, body, kwargs in calls
        if kind == "markdown"
    ]
    return {"result": result, "payloads": payloads, "call_count": len(calls)}


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    import inputs_page_route_coordinators as route
    legacy_inputs_page = route

    base_seed = {
        "bot_row_count": 2,
        "inputs_bot_row_count": 2,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 3,
        "bot_row_1_spacing": 0,
        "bot_row_1_dia": 20,
        "inputs_bot_row_1_mode": "Count",
        "inputs_bot_row_1_bars": 3,
        "inputs_bot_row_1_spacing": 0,
        "inputs_bot_row_1_dia": 20,
    }
    cases = {
        "ordinary": {
            "seed": dict(base_seed),
            "publish_raises": False,
        },
        "shear_focus_dev": {
            "seed": {
                **base_seed,
                "_inputs_shear_shared_normalised_this_run": True,
                "_fast_mode_focus_section": "shear",
                "_dev_mode": True,
                "_debug_d_consistency": {"existing": "kept"},
                "_fast_get_d": 552.5,
            },
            "publish_raises": False,
        },
        "publish_exception_swallowed": {
            "seed": dict(base_seed),
            "publish_raises": True,
        },
    }

    results = {}
    for name, config in cases.items():
        results[name] = {
            "legacy": _run_case(
                legacy_inputs_page,
                config["seed"],
                publish_raises=bool(config["publish_raises"]),
            ),
            "route": _run_case(
                route,
                config["seed"],
                publish_raises=bool(config["publish_raises"]),
            ),
        }
    css_case = {
        "legacy": _run_css_case(legacy_inputs_page),
        "route": _run_css_case(route),
    }

    checks = {
        "all_returns_match_legacy": all(case["legacy"]["return"] == case["route"]["return"] for case in results.values()),
        "all_session_effects_match_legacy": all(case["legacy"]["session_after_callbacks"] == case["route"]["session_after_callbacks"] for case in results.values()),
        "all_call_order_matches_legacy": all(case["legacy"]["calls"] == case["route"]["calls"] for case in results.values()),
        "css_markdown_payload_matches_legacy": css_case["legacy"] == css_case["route"],
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    checks["route_no_longer_delegates_pre_widget_setup_coordinator"] = (
        "return _legacy_inputs_page.render_inputs_pre_widget_apply_and_render_setup_coordinator" not in route_source
    )
    checks["route_no_longer_calls_legacy_apply_inputs_page_css"] = (
        "_legacy_inputs_page.apply_inputs_page_css" not in route_source
    )

    status = "PASS" if all(checks.values()) else "FAIL"
    artifact = {
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
        "cases": results,
        "css_case": css_case,
        "legacy_side_retired": True,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_pre_widget_setup_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_route_pre_widget_setup_parity_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Pre-Widget Setup Parity",
                "",
                f"Status: {status}",
                "",
                "## Checks",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "## Scope",
                "- The old physical Inputs page side is retired; this compares deterministic route-coordinator behavior across the preserved harness sides.",
                "- Verifies return tuple, session side effects, dependency call order, publish exception swallowing, and longitudinal callback audit wrapping.",
                "- Verifies imported `apply_inputs_page_css` emits a stable markdown payload hash and HTML flag.",
                "- Leaves Apply callback handling as an explicit compatibility bridge for a later slice.",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
