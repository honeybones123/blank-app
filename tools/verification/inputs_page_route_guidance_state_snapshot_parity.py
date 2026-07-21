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


def _case_result(name: str, source_state: dict[str, Any] | None) -> dict[str, Any]:
    import inputs_page_route_coordinators as route
    from inputs_page_modules.design_guide.state_projection import build_guidance_state_snapshot

    route_value = route._guidance_state_snapshot(copy.deepcopy(source_state))
    module_value = build_guidance_state_snapshot(
        copy.deepcopy(source_state),
        result_keys=route.RESULT_KEYS,
        shared_defaults=route.SHARED_DEFAULTS,
    )
    return {
        "name": name,
        "match": route_value == module_value,
        "route": route_value,
        "module": module_value,
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
    marker = "def _guidance_state_snapshot(state: dict | None = None) -> dict:"
    start = source.index(marker)
    next_def = source.index("\ndef ", start + len(marker))
    segment = source[start:next_def]
    return (
        "build_guidance_state_snapshot_module(" in segment
        and "stale_solver_keys" not in segment
        and "stale_shear_publication_keys" not in segment
        and "snapshot.pop(" not in segment
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = {
        "none_state_defaults": _case_result("none_state_defaults", None),
        "custom_state_preserved": _case_result(
            "custom_state_preserved",
            {
                "b": 350,
                "custom_key": {"keep": True},
            },
        ),
        "stale_solver_and_shear_keys_removed": _case_result(
            "stale_solver_and_shear_keys_removed",
            {
                "custom_key": "survives",
                "pending_recommendation": {"stale": True},
                "_solver_result": {"stale": True},
                "_one_click_run_feedback": {"stale": True},
                "_bend_pack": {"rows": []},
                "shear_design_status": "STALE",
                "shear_required_spacing_mm": 999,
                "published_result_spacing_mm": 888,
                "final_shear_truth_resolved": False,
            },
        ),
    }
    stale_case = cases["stale_solver_and_shear_keys_removed"]["route"]
    clean_imports = _module_imports_are_clean()
    checks = {
        "all_cases_match_route_wrapper": all(case["match"] for case in cases.values()),
        "stale_keys_removed": all(
            key not in stale_case
            for key in (
                "pending_recommendation",
                "_solver_result",
                "_one_click_run_feedback",
                "_bend_pack",
                "shear_design_status",
                "shear_required_spacing_mm",
                "published_result_spacing_mm",
                "final_shear_truth_resolved",
            )
        ),
        "custom_key_preserved": stale_case.get("custom_key") == "survives",
        "defaults_filled": all(key in cases["none_state_defaults"]["route"] for key in ("b", "D", "fc")),
        "module_imports_are_clean": clean_imports["clean"],
        "route_wrapper_delegates_to_module": _route_wrapper_delegates_to_module(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_guidance_state_snapshot_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "module_imports": clean_imports,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_guidance_state_snapshot_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_guidance_state_snapshot_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Guidance State Snapshot Parity",
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
