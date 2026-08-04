from __future__ import annotations

import json
import importlib.util
import sys
import types
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


def _clear_session() -> None:
    import streamlit as st

    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)


def _seed_session(values: dict[str, Any]) -> None:
    import streamlit as st

    _clear_session()
    st.session_state.update(dict(values))


def _snapshot_session() -> dict[str, Any]:
    import streamlit as st

    keys = (
        "_inputs_longitudinal_reo_force_refresh_processed_this_run",
        "_inputs_shear_force_refresh_processed_this_run",
        "_inputs_pending_refresh_present_before_pop",
        "_force_inputs_widget_reseed_once",
        "_force_inputs_shear_widget_reseed_once",
        "_pending_inputs_apply_refresh",
        "_inputs_apply_refresh_cycle_latest",
        "_pending_shear_widget_seed_from_shared",
        "inputs_shear_widget_seed_requested",
        "inputs_shear_widget_seed_reason",
        "_inputs_shear_widget_seed_latest",
        "inputs_longitudinal_reo_reseed_applied",
        "inputs_longitudinal_reo_reseed_reason",
        "inputs_longitudinal_reo_reseed_changed_keys",
        "inputs_longitudinal_reo_widget_drift_detected",
        "inputs_longitudinal_reo_widget_drift_keys",
    )
    return {key: st.session_state.get(key) for key in keys if key in st.session_state}


def _run_force_cycle(module, seed: dict[str, Any], reason: str) -> dict[str, Any]:
    import streamlit as st

    calls: list[tuple[str, Any]] = []
    original_hydrate = module.hydrate_active_page_widgets_from_shared
    original_debug = getattr(module, "_agent_debug_log", None)

    def _hydrate(slug, *, force_on_page_change=False):
        calls.append(("hydrate", slug, bool(force_on_page_change)))
        st.session_state["_hydrated_from_shared_map"] = {
            "inputs_bot_row_count": True,
            "inputs_lig_d": True,
        }

    try:
        module.hydrate_active_page_widgets_from_shared = _hydrate
        if original_debug is not None:
            module._agent_debug_log = lambda *args, **kwargs: calls.append(("debug", args[0] if args else None))
        _seed_session(seed)
        result = module._force_inputs_apply_refresh_cycle(reason)
        session = _snapshot_session()
    finally:
        module.hydrate_active_page_widgets_from_shared = original_hydrate
        if original_debug is not None:
            module._agent_debug_log = original_debug
    return {"result": result, "session": session, "calls": calls}


def _run_startup_case(
    module,
    seed: dict[str, Any],
    *,
    beam_load_result: bool,
) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    mark_calls: list[str] = []
    original_load = module.load_active_beam_into_shared
    original_debug = getattr(module, "_agent_debug_log", None)
    original_force = module._force_inputs_apply_refresh_cycle

    if hasattr(module, "_apply_canonical_convenience_resync_to_shared"):
        resync_name = "_apply_canonical_convenience_resync_to_shared"
    else:
        resync_name = "_apply_canonical_convenience_resync_to_shared_for_app_bridge"
    original_resync = getattr(module, resync_name)

    fake_ssl = types.SimpleNamespace(
        append_session_state_final_log=lambda name, payload: calls.append(("ssl_append", name, payload)),
        ssl_increment=lambda name, amount: calls.append(("ssl_increment", name, amount)),
        ssl_set_flag=lambda name, value: calls.append(("ssl_set_flag", name, value)),
    )
    previous_ssl = sys.modules.get("session_state_final_log")

    def _load():
        calls.append(("load_active_beam_into_shared", None))
        return bool(beam_load_result)

    def _resync(*, source: str):
        calls.append(("resync", source))
        return {"source": source}

    def _force(reason: str):
        calls.append(("force", reason))
        return {"reason": reason}

    def _mark(label: str):
        mark_calls.append(str(label))

    try:
        sys.modules["session_state_final_log"] = fake_ssl
        module.load_active_beam_into_shared = _load
        setattr(module, resync_name, _resync)
        module._force_inputs_apply_refresh_cycle = _force
        if original_debug is not None:
            module._agent_debug_log = lambda message, data=None, **kwargs: calls.append(("debug", message, data))
        _seed_session(seed)
        module.render_inputs_startup_hydration_coordinator(
            ss=sys.modules["streamlit"].session_state,
            mark=_mark,
        )
        session = _snapshot_session()
    finally:
        if previous_ssl is None:
            sys.modules.pop("session_state_final_log", None)
        else:
            sys.modules["session_state_final_log"] = previous_ssl
        module.load_active_beam_into_shared = original_load
        setattr(module, resync_name, original_resync)
        module._force_inputs_apply_refresh_cycle = original_force
        if original_debug is not None:
            module._agent_debug_log = original_debug
    return {"session": session, "calls": calls, "marks": mark_calls}


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    legacy_inputs_page = _load_archived_legacy_inputs_page()
    import inputs_page_route_coordinators as route

    refresh_seed = {
        "page_slug": "inputs",
        "active_beam_id": "B1",
        "bot_row_count": 2,
        "inputs_bot_row_count": 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 3,
        "bot_row_1_spacing": 0,
        "bot_row_1_dia": 20,
        "inputs_bot_row_1_mode": "Spacing",
        "inputs_bot_row_1_bars": 1,
        "inputs_bot_row_1_spacing": 200,
        "inputs_bot_row_1_dia": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
        "inputs_lig_d": 12,
        "inputs_lig_legs": 4,
        "inputs_s_lig": 150,
        "_hydrated_from_shared_map": {"inputs_bot_row_count": True, "inputs_lig_d": True},
    }
    force_cases = {
        "refresh_cycle": {
            "legacy": _run_force_cycle(legacy_inputs_page, refresh_seed, "parity_refresh"),
            "route": _run_force_cycle(route, refresh_seed, "parity_refresh"),
        }
    }

    startup_seeds = {
        "ordinary": {},
        "explicit_beam": {
            "_force_inputs_widget_reseed_once": True,
            "_force_inputs_shear_widget_reseed_once": True,
        },
        "pending_apply": {
            "_pending_inputs_apply_refresh": {"source": "design_guide_apply"},
            "_force_inputs_widget_reseed_once": True,
            "_force_inputs_shear_widget_reseed_once": True,
        },
        "pending_design_action": {
            "_pending_inputs_apply_refresh": {"source": "design_action_widget_sync"},
            "_force_inputs_widget_reseed_once": True,
            "_force_inputs_shear_widget_reseed_once": True,
        },
        "force_both": {
            "_force_inputs_widget_reseed_once": True,
            "_force_inputs_shear_widget_reseed_once": True,
        },
        "force_shear_only": {
            "_force_inputs_shear_widget_reseed_once": True,
        },
    }
    startup_cases = {}
    for name, seed in startup_seeds.items():
        beam_load = name == "explicit_beam"
        startup_cases[name] = {
            "legacy": _run_startup_case(legacy_inputs_page, seed, beam_load_result=beam_load),
            "route": _run_startup_case(route, seed, beam_load_result=beam_load),
        }

    checks = {
        "force_cycle_matches_legacy": all(case["legacy"] == case["route"] for case in force_cases.values()),
        "startup_cases_match_legacy": all(case["legacy"] == case["route"] for case in startup_cases.values()),
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["startup_hydration_no_old_page_delegate"] = (
        "_legacy_inputs_page.render_inputs_startup_hydration_coordinator" not in route_source
    )
    checks["refresh_cycle_no_old_page_delegate"] = (
        "_legacy_inputs_page._force_inputs_apply_refresh_cycle" not in route_source
        and "_legacy_inputs_page._request_shear_widget_seed_from_shared" not in route_source
        and "_legacy_inputs_page._reseed_inputs_longitudinal_reo_widgets_from_shared" not in route_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_startup_hydration_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "force_cases": force_cases,
        "startup_cases": startup_cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_startup_hydration_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_startup_hydration_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Startup Hydration Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
