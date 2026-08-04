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
MODULE_PATH = ROOT / "inputs_page_modules" / "diagrams" / "source_projection.py"
ROUTE_PATH = ROOT / "inputs_page_route_coordinators.py"


def _run_case(name: str, session_state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_route_coordinators as route
    from inputs_page_modules.diagrams.source_projection import build_section_outline_points_and_bbox

    original_st = route.st
    original_get_param = route.get_param
    try:
        route.st = SimpleNamespace(session_state=copy.deepcopy(session_state))
        route.get_param = lambda key, default=None: copy.deepcopy(params.get(key, default))
        route_value = route._get_outline_points_and_bbox()
    finally:
        route.st = original_st
        route.get_param = original_get_param

    sec_shape = session_state.get("sec_shape", "RECT")
    if sec_shape not in ("RECT", "T", "I"):
        sec_shape = "RECT"
    module_value = build_section_outline_points_and_bbox(
        sec_shape=sec_shape,
        b=float(params.get("b", 400.0)),
        D=float(params.get("D", 600.0)),
        bf=float(params.get("bf", 600.0)),
        tf=float(params.get("tf", 120.0)),
        bw=float(params.get("bw", 300.0)),
        tw=float(params.get("tw", 200.0)),
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
        "section_layout",
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
    marker = "def _get_outline_points_and_bbox():"
    start = source.index(marker)
    next_def = source.index("\ndef ", start + len(marker))
    segment = source[start:next_def]
    return (
        "build_section_outline_points_and_bbox_module(" in segment
        and "x_web0" not in segment
        and "y_bot_flange_top" not in segment
        and "return pts" not in segment
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = {
        "rect": _run_case("rect", {"sec_shape": "RECT"}, {"b": 450, "D": 700}),
        "t_section_clamps": _run_case(
            "t_section_clamps",
            {"sec_shape": "T"},
            {"bf": 600, "tf": 900, "bw": 900, "D": 650},
        ),
        "i_section_clamps": _run_case(
            "i_section_clamps",
            {"sec_shape": "I"},
            {"bf": 620, "tf": 500, "tw": 900, "D": 700},
        ),
        "invalid_shape_defaults_rect": _run_case(
            "invalid_shape_defaults_rect",
            {"sec_shape": "WEIRD"},
            {"b": 390, "D": 610},
        ),
    }
    clean_imports = _module_imports_are_clean()
    checks = {
        "all_cases_match_route_wrapper": all(case["match"] for case in cases.values()),
        "rect_has_closed_five_point_polygon": len(cases["rect"]["route"][0]) == 5
        and cases["rect"]["route"][0][0] == cases["rect"]["route"][0][-1],
        "t_section_returns_flange_width": cases["t_section_clamps"]["route"][1] == 600.0,
        "i_section_returns_flange_width": cases["i_section_clamps"]["route"][1] == 620.0,
        "module_imports_are_clean": clean_imports["clean"],
        "route_wrapper_delegates_to_module": _route_wrapper_delegates_to_module(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_diagram_outline_projection_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "module_imports": clean_imports,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_diagram_outline_projection_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_diagram_outline_projection_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Diagram Outline Projection Parity",
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
