from __future__ import annotations

import copy
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
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
    spec = importlib.util.spec_from_file_location("_archived_legacy_inputs_page_for_longitudinal_reo", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load archived legacy inputs_page reference: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _interesting_state(state: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "_hydrated_from_shared_map",
        "_inputs_longitudinal_reo_audit",
        "inputs_longitudinal_reo_widget_drift_detected",
        "inputs_longitudinal_reo_widget_drift_keys",
        "inputs_longitudinal_reo_reseed_applied",
        "inputs_longitudinal_reo_reseed_reason",
        "inputs_longitudinal_reo_reseed_changed_keys",
    ]
    keys.extend(f"inputs_{section}_row_count" for section in ("bot", "top"))
    for section in ("bot", "top"):
        for row_idx in range(1, 5):
            for field in ("mode", "bars", "spacing", "dia"):
                keys.append(f"inputs_{section}_row_{row_idx}_{field}")
                keys.append(f"_cached_inputs_{section}_row_{row_idx}_{field}")
    keys.extend(f"_cached_inputs_{section}_row_count" for section in ("bot", "top"))
    return {key: copy.deepcopy(state.get(key)) for key in keys if key in state}


def _seed() -> dict[str, Any]:
    state: dict[str, Any] = {
        "page_slug": "inputs",
        "active_beam_id": "B1",
        "bot_row_count": 2,
        "top_row_count": 1,
        "inputs_bot_row_count": 1,
        "inputs_top_row_count": 2,
        "_hydrated_from_shared_map": {
            "inputs_bot_row_count": True,
            "inputs_bot_row_1_bars": True,
            "inputs_top_row_1_dia": True,
            "untouched": True,
        },
        "_cached_inputs_bot_row_count": "old",
        "_cached_inputs_top_row_count": "old",
        "bot1_count": 3,
        "db_bot_1": 20,
        "bot2_count": 2,
        "db_bot_2": 16,
        "top1_count": 2,
        "db_top_1": 20,
        "top2_count": 0,
        "db_top_2": 0,
        "nb_bot": 5,
        "nb_top": 2,
        "Ast_bot": 1570,
        "Ast_top": 628,
    }
    for section in ("bot", "top"):
        for row_idx in range(1, 5):
            state[f"{section}_row_{row_idx}_mode"] = "Count"
            state[f"{section}_row_{row_idx}_bars"] = row_idx + (10 if section == "top" else 0)
            state[f"{section}_row_{row_idx}_spacing"] = 100 + row_idx
            state[f"{section}_row_{row_idx}_dia"] = 12 + row_idx
            state[f"inputs_{section}_row_{row_idx}_mode"] = "Spacing"
            state[f"inputs_{section}_row_{row_idx}_bars"] = 99
            state[f"inputs_{section}_row_{row_idx}_spacing"] = 999
            state[f"inputs_{section}_row_{row_idx}_dia"] = 99
            state[f"_cached_inputs_{section}_row_{row_idx}_mode"] = "cached"
            state[f"_cached_inputs_{section}_row_{row_idx}_bars"] = "cached"
            state[f"_cached_inputs_{section}_row_{row_idx}_spacing"] = "cached"
            state[f"_cached_inputs_{section}_row_{row_idx}_dia"] = "cached"
    return state


def _run_side(module: Any, operation: str, seed: dict[str, Any], *, now: float = 100.0) -> dict[str, Any]:
    state = copy.deepcopy(seed)
    debug_calls: list[tuple[Any, ...]] = []
    originals = {
        "st": module.st,
        "time": module.time,
        "debug": getattr(module, "_agent_debug_log", None),
    }
    try:
        module.st = SimpleNamespace(session_state=state)
        module.time = SimpleNamespace(time=lambda: now, perf_counter=getattr(module.time, "perf_counter", lambda: now))
        module._agent_debug_log = lambda *args, **kwargs: debug_calls.append((args, kwargs))
        if operation == "audit":
            result = module._longitudinal_reo_widget_audit_snapshot("parity_audit")
        elif operation == "reseed":
            result = module._reseed_inputs_longitudinal_reo_widgets_from_shared("parity_reseed")
        elif operation == "reseed_force":
            result = module._reseed_inputs_longitudinal_reo_widgets_from_shared("parity_force", force=True)
        else:
            raise AssertionError(operation)
        return {
            "result": _jsonable(result),
            "state": _jsonable(_interesting_state(state)),
            "debug_calls": _jsonable(debug_calls),
        }
    finally:
        module.st = originals["st"]
        module.time = originals["time"]
        if originals["debug"] is not None:
            module._agent_debug_log = originals["debug"]


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_route_longitudinal_reo_widget_sync_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_longitudinal_reo_widget_sync_parity_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    legacy = _load_archived_legacy_inputs_page()
    import inputs_page_route_coordinators as route

    failures: list[str] = []
    comparisons: dict[str, dict[str, Any]] = {}

    key_cases = [
        None,
        "",
        "inputs_bot_row_count",
        "inputs_top_row_1_bars",
        "inputs_top_row_4_dia",
        "bot_row_1_bars",
        "inputs_lig_d",
    ]
    legacy_keys = [legacy._is_inputs_longitudinal_reo_widget_key(key) for key in key_cases]
    route_keys = [route._is_inputs_longitudinal_reo_widget_key(key) for key in key_cases]
    comparisons["key_classification"] = {"legacy": legacy_keys, "route": route_keys}
    if legacy_keys != route_keys:
        failures.append("key_classification_changed")

    base_seed = _seed()
    active_seed = _seed()
    active_seed["_last_user_widget_key"] = "inputs_bot_row_1_bars"
    active_seed["_last_user_edit_ts"] = 99.25

    for operation, seed in (
        ("audit", base_seed),
        ("reseed", base_seed),
        ("reseed", active_seed),
        ("reseed_force", active_seed),
    ):
        label = f"{operation}_{'active' if seed is active_seed else 'base'}"
        legacy_result = _run_side(legacy, operation, seed)
        route_result = _run_side(route, operation, seed)
        comparisons[label] = {"legacy": legacy_result, "route": route_result}
        if legacy_result != route_result:
            failures.append(f"{label}_changed")

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    module_source = (
        ROOT / "inputs_page_modules" / "session" / "longitudinal_reo_widget_sync.py"
    ).read_text(encoding="utf-8", errors="ignore")
    if "longitudinal_reo_widget_audit_snapshot_module(" not in route_source:
        failures.append("route_audit_wrapper_missing_module_delegate")
    if "reseed_inputs_longitudinal_reo_widgets_from_shared_module(" not in route_source:
        failures.append("route_reseed_wrapper_missing_module_delegate")
    for forbidden in ("import streamlit", "from streamlit", "import inputs_page", "from inputs_page", "st."):
        if forbidden in module_source:
            failures.append(f"module_forbidden_{forbidden}")

    payload = {
        "verifier": "inputs_page_route_longitudinal_reo_widget_sync_parity",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "comparisons": comparisons,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Longitudinal Reo Widget Sync Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Failures: `{len(failures)}`",
                "",
                "## Cases",
                "",
                *(f"- `{name}`" for name in comparisons),
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
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
