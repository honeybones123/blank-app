from __future__ import annotations

import ast
import copy
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
MODULE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "state_projection.py"
ROUTE_PATH = ROOT / "inputs_page_route_coordinators.py"


def _run_case(name: str, source_state: dict[str, Any] | None) -> dict[str, Any]:
    import inputs_page_route_coordinators as route
    from inputs_page_modules.design_guide.state_projection import (
        build_auto_design_governing_fingerprint,
    )

    actions = {
        "Mu": 101.5,
        "Vu": 44.2,
        "Nu": -8.0,
        "SLS_M": 21.0,
        "SLS_V": 9.5,
        "source": "test_resolver",
    }
    shared_state = {
        "design_optimisation_goal": "balanced",
        "optimisation_lock_geometry": True,
        "sec_shape": "T",
        "b": 500,
        "bw": 300,
        "D": 650,
        "fc": 50,
        "bot_row_1_bars": 4,
    }
    calls: list[tuple[str, dict[str, Any]]] = []

    original_shared_snapshot = route._shared_state_snapshot
    original_resolve_actions = route._resolve_design_actions_from_state
    try:
        route._shared_state_snapshot = lambda: copy.deepcopy(shared_state)

        def _resolve_actions(state: dict[str, Any]) -> dict[str, Any]:
            calls.append(("resolve_design_actions", copy.deepcopy(state)))
            return copy.deepcopy(actions)

        route._resolve_design_actions_from_state = _resolve_actions
        route_value = route._auto_design_governing_fingerprint(copy.deepcopy(source_state))
    finally:
        route._shared_state_snapshot = original_shared_snapshot
        route._resolve_design_actions_from_state = original_resolve_actions

    expected_source = source_state or shared_state
    module_value = build_auto_design_governing_fingerprint(
        copy.deepcopy(expected_source),
        actions=copy.deepcopy(actions),
    )
    return {
        "name": name,
        "match": route_value == module_value,
        "route": route_value,
        "module": module_value,
        "calls": calls,
        "used_shared_source": calls == [("resolve_design_actions", expected_source)],
    }


def _module_imports_are_clean() -> dict[str, Any]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden_prefixes = (
        "streamlit",
        "inputs_page",
        "inputs_page_route_coordinators",
        "inputs_page_app_contract_bridge",
        "state_and_helpers",
    )
    forbidden = [
        imported
        for imported in imports
        if imported == "streamlit"
        or any(imported.startswith(prefix + ".") for prefix in forbidden_prefixes)
        or imported in forbidden_prefixes
    ]
    return {
        "imports": imports,
        "forbidden": forbidden,
        "clean": not forbidden,
    }


def _route_wrapper_delegates_to_module() -> bool:
    source = ROUTE_PATH.read_text(encoding="utf-8", errors="replace")
    marker = "def _auto_design_governing_fingerprint(state: dict | None = None) -> tuple:"
    start = source.index(marker)
    next_def = source.index("\ndef ", start + len(marker))
    segment = source[start:next_def]
    return (
        "build_auto_design_governing_fingerprint_module(" in segment
        and "governing_keys" not in segment
        and "fingerprint.extend" not in segment
        and "resolved_Mu" not in segment
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = {
        "explicit_state": _run_case(
            "explicit_state",
            {
                "design_optimisation_goal": "shallow",
                "optimisation_lock_geometry": False,
                "sec_shape": "Rectangular",
                "b": 350,
                "D": 580,
                "fc": 40,
                "bot_row_1_bars": 3,
            },
        ),
        "none_uses_shared_state": _run_case("none_uses_shared_state", None),
        "empty_dict_uses_shared_state": _run_case("empty_dict_uses_shared_state", {}),
    }
    clean_imports = _module_imports_are_clean()
    explicit_fingerprint = dict(cases["explicit_state"]["route"])
    checks = {
        "all_cases_match_route_wrapper": all(case["match"] for case in cases.values()),
        "none_uses_shared_state": cases["none_uses_shared_state"]["used_shared_source"],
        "empty_dict_uses_shared_state": cases["empty_dict_uses_shared_state"]["used_shared_source"],
        "action_values_are_included": all(
            key in explicit_fingerprint
            for key in (
                "resolved_Mu",
                "resolved_Vu",
                "resolved_Nu",
                "resolved_SLS_M",
                "resolved_SLS_V",
                "resolved_source",
            )
        ),
        "module_imports_are_clean": clean_imports["clean"],
        "route_wrapper_delegates_to_module": _route_wrapper_delegates_to_module(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_auto_design_fingerprint_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "module_imports": clean_imports,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_auto_design_fingerprint_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_auto_design_fingerprint_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Auto Design Fingerprint Parity",
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
