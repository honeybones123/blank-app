from __future__ import annotations

import ast
import copy
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
MODULE_PATH = ROOT / "inputs_page_modules" / "widgets" / "shear_widget_seed.py"
ROUTE_PATH = ROOT / "inputs_page_route_coordinators.py"


def _seed_state() -> dict[str, Any]:
    return {
        "lig_d": 10.0,
        "lig_legs": 2,
        "s_lig": 200.0,
        "_cached_inputs_lig_d": "stale",
        "_cached_inputs_lig_legs": "stale",
        "_cached_inputs_s_lig": "stale",
        "_cached_shear_lig_d": "stale",
        "_cached_shear_lig_legs": "stale",
        "_cached_shear_s_lig": "stale",
        "_hydrated_from_shared_map": {
            "inputs_lig_d": True,
            "inputs_lig_legs": True,
            "inputs_s_lig": True,
            "shear_lig_d": True,
            "shear_lig_legs": True,
            "shear_s_lig": True,
            "other_widget": True,
        },
    }


def _run_route(reason: str) -> dict[str, Any]:
    import inputs_page_route_coordinators as route

    state = _seed_state()
    debug_calls: list[dict[str, Any]] = []
    original_st = route.st
    original_debug = route._agent_debug_log
    try:
        route.st = SimpleNamespace(session_state=state)
        route._agent_debug_log = lambda *args, **kwargs: debug_calls.append(
            {"args": list(args), "kwargs": dict(kwargs)}
        )
        payload = route._request_shear_widget_seed_from_shared(reason)
    finally:
        route.st = original_st
        route._agent_debug_log = original_debug
    return {"payload": payload, "state": state, "debug_calls": debug_calls}


def _run_module(reason: str) -> dict[str, Any]:
    from inputs_page_modules.widgets.shear_widget_seed import (
        request_shear_widget_seed_from_shared,
    )

    state = _seed_state()
    debug_calls: list[dict[str, Any]] = []
    payload = request_shear_widget_seed_from_shared(
        state=state,
        reason=reason,
        agent_debug_log_fn=lambda *args, **kwargs: debug_calls.append(
            {"args": list(args), "kwargs": dict(kwargs)}
        ),
    )
    return {"payload": payload, "state": state, "debug_calls": debug_calls}


def _module_imports_are_clean() -> dict[str, Any]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = [
        imported
        for imported in imports
        if imported == "streamlit"
        or imported.startswith("streamlit.")
        or imported == "inputs_page"
        or imported.startswith("inputs_page.")
        or imported == "inputs_page_route_coordinators"
    ]
    source = MODULE_PATH.read_text(encoding="utf-8", errors="replace")
    return {
        "imports": imports,
        "forbidden": forbidden,
        "clean": not forbidden and ".session_state" not in source and "st.session_state" not in source,
    }


def _route_wrapper_delegates_to_module() -> bool:
    source = ROUTE_PATH.read_text(encoding="utf-8", errors="replace")
    marker = "def _request_shear_widget_seed_from_shared(reason: str) -> dict:"
    start = source.index(marker)
    next_def = source.index("\ndef ", start + len(marker))
    segment = source[start:next_def]
    return (
        "request_shear_widget_seed_from_shared_module(" in segment
        and "widget_map =" not in segment
        and "_pending_shear_widget_seed_from_shared" not in segment
        and "_cached_{widget_key}" not in segment
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = {
        "explicit_reason": {
            "route": _run_route("force_inputs_shear_widget_reseed_once"),
            "module": _run_module("force_inputs_shear_widget_reseed_once"),
        },
        "blank_reason": {
            "route": _run_route(""),
            "module": _run_module(""),
        },
    }
    clean_imports = _module_imports_are_clean()
    explicit_state = cases["explicit_reason"]["route"]["state"]
    expected_widget_keys = [
        "inputs_lig_d",
        "inputs_lig_legs",
        "inputs_s_lig",
        "shear_lig_d",
        "shear_lig_legs",
        "shear_s_lig",
    ]
    checks = {
        "all_cases_match_module": all(
            case["route"] == case["module"] for case in cases.values()
        ),
        "pending_seed_payload_written": isinstance(
            explicit_state.get("_pending_shear_widget_seed_from_shared"),
            dict,
        ),
        "seed_flags_written": explicit_state.get("inputs_shear_widget_seed_requested") is True
        and explicit_state.get("inputs_shear_widget_seed_reason")
        == "force_inputs_shear_widget_reseed_once",
        "cached_widget_keys_cleared": all(
            f"_cached_{widget_key}" not in explicit_state
            for widget_key in expected_widget_keys
        ),
        "hydrated_map_entries_cleared": all(
            widget_key not in explicit_state["_hydrated_from_shared_map"]
            for widget_key in expected_widget_keys
        )
        and explicit_state["_hydrated_from_shared_map"].get("other_widget") is True,
        "module_imports_are_clean": clean_imports["clean"],
        "route_wrapper_delegates_to_module": _route_wrapper_delegates_to_module(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_shear_widget_seed_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "module_imports": clean_imports,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_shear_widget_seed_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_shear_widget_seed_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Shear Widget Seed Parity",
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
