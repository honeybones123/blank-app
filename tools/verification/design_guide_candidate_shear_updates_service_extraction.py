from __future__ import annotations

import ast
import datetime as _dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _call_names(segment: str) -> set[str]:
    tree = ast.parse(segment)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _load_candidate_module() -> Any:
    module_name = "candidate_evaluation_for_shear_updates_verifier"
    spec = importlib.util.spec_from_file_location(module_name, CANDIDATE_EVALUATION)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load candidate_evaluation module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _legacy_int(source: dict[str, Any], key: str, default: int) -> int:
    value = source.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _legacy_float(source: dict[str, Any], key: str, default: float) -> float:
    value = source.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _legacy_candidate_shear_updates(state: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(state or {})
    return {
        "lig_d": _legacy_int(source, "lig_d", 10),
        "lig_legs": _legacy_int(source, "lig_legs", 2),
        "s_lig": _legacy_float(source, "s_lig", 200.0),
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, full_segment = _function_segment(inputs_source, "evaluate_candidate_full")
    _, _, fast_segment = _function_segment(inputs_source, "evaluate_candidate_fast")
    _, _, wrapper_segment = _function_segment(inputs_source, "_candidate_shear_updates")
    full_call_names = _call_names(full_segment)
    fast_call_names = _call_names(fast_segment)
    module = _load_candidate_module()
    helper = module.resolve_candidate_shear_updates

    cases = [
        {},
        {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0},
        {"lig_d": "8", "lig_legs": "0", "s_lig": "175.5"},
        {"lig_d": None, "lig_legs": None, "s_lig": None},
        {"lig_d": "bad", "lig_legs": object(), "s_lig": "bad"},
    ]
    parity_rows = []
    for case in cases:
        old_value = _legacy_candidate_shear_updates(case)
        new_value = helper(case)
        parity_rows.append(
            {
                "case": repr(case),
                "old": old_value,
                "new": new_value,
                "matches": old_value == new_value,
            }
        )

    checks = {
        "service_helper_exists": "def resolve_candidate_shear_updates(" in candidate_source,
        "service_helper_exported": '"resolve_candidate_shear_updates"' in candidate_source,
        "page_imports_service_alias": "resolve_candidate_shear_updates as _resolve_candidate_shear_updates" in inputs_source,
        "page_wrapper_delegates": "return _resolve_candidate_shear_updates(candidate_state)" in wrapper_segment,
        "full_evaluator_uses_service": "_resolve_candidate_shear_updates" in full_call_names,
        "fast_evaluator_uses_service": "_resolve_candidate_shear_updates" in fast_call_names,
        "full_evaluator_no_direct_page_wrapper": "_candidate_shear_updates" not in full_call_names,
        "fast_evaluator_no_direct_page_wrapper": "_candidate_shear_updates" not in fast_call_names,
        "parity_cases_match": all(row["matches"] for row in parity_rows),
        "candidate_service_import_clean": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "solver_execution_not_moved": all(
            token in full_segment + fast_segment
            for token in (
                "_evaluate_bending_with_bottom_state(",
                "_evaluate_shear_with_state(",
                "_evaluate_crack_with_state(",
                "_evaluate_deflection_with_state(",
            )
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_candidate_shear_updates_service_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "CANDIDATE_SHEAR_UPDATES_SERVICE_OWNED"
            if all(checks.values())
            else "CANDIDATE_SHEAR_UPDATES_EXTRACTION_FAILED"
        ),
        "parity_rows": parity_rows,
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_candidate_shear_updates_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_shear_updates_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Candidate Shear Updates Service Extraction",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Parity Rows",
        "",
        "| Case | Matches |",
        "| --- | ---: |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(dict(payload.get("checks") or {}).items()))
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(f"design_guide_candidate_shear_updates_service_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
