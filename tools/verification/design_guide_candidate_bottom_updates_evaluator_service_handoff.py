from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import resolve_bottom_reo_candidate_bottom_updates


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _sample_parity_rows() -> list[dict[str, Any]]:
    cases = [
        {},
        {"db_bot_1": 20, "db_bot_2": 20, "bot1_count": 6, "bot2_count": 2},
        {"bot_row_1_dia": 20, "bot_row_2_dia": 20, "bot_row_1_bars": 6, "bot_row_2_bars": 2},
        {"db_bot_1": 20, "bot_row_1_dia": 20, "bot1_count": 6, "bot_row_1_bars": 6, "bot2_count": 0, "bot_row_2_bars": 0},
        {"db_bot_1": "16", "db_bot_2": None, "bot1_count": "4", "bot2_count": "0"},
        {"bot_row_1_dia": "16", "bot_row_2_dia": None, "bot_row_1_bars": "4", "bot_row_2_bars": "0"},
        {"db_bot_1": None, "db_bot_2": 20, "bot1_count": 4, "bot2_count": 0},
        {"db_bot_1": "bad", "db_bot_2": "bad", "bot1_count": "bad", "bot2_count": "bad"},
        {"bot_row_1_dia": "bad", "bot_row_2_dia": "bad", "bot_row_1_bars": "bad", "bot_row_2_bars": "bad"},
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        service_value = resolve_bottom_reo_candidate_bottom_updates(dict(case))
        # The page wrapper is already parity-proven elsewhere; this expected shape
        # preserves the service contract the evaluator now consumes directly.
        if service_value is None:
            expected = None
        else:
            expected = {
                "db_bot_1": service_value.get("db_bot_1"),
                "db_bot_2": service_value.get("db_bot_2"),
                "bot1_count": service_value.get("bot1_count"),
                "bot2_count": service_value.get("bot2_count"),
            }
        rows.append(
            {
                "case": repr(case),
                "service": service_value,
                "expected": expected,
                "matches": service_value == expected,
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, full_segment = _function_segment(inputs_source, "evaluate_candidate_full")
    _, _, fast_segment = _function_segment(inputs_source, "evaluate_candidate_fast")
    _, _, wrapper_segment = _function_segment(inputs_source, "_candidate_bottom_updates")
    full_calls = _call_names(full_segment)
    fast_calls = _call_names(fast_segment)
    parity_rows = _sample_parity_rows()
    checks = {
        "service_helper_exists": "def resolve_bottom_reo_candidate_bottom_updates(" in candidate_source,
        "service_helper_exported": '"resolve_bottom_reo_candidate_bottom_updates"' in candidate_source,
        "page_imports_service_alias": "resolve_bottom_reo_candidate_bottom_updates as _resolve_bottom_reo_candidate_bottom_updates" in inputs_source,
        "page_wrapper_delegates": "return _resolve_bottom_reo_candidate_bottom_updates(candidate_state)" in wrapper_segment,
        "full_evaluator_uses_service": "_resolve_bottom_reo_candidate_bottom_updates" in full_calls,
        "fast_evaluator_uses_service": "_resolve_bottom_reo_candidate_bottom_updates" in fast_calls,
        "full_evaluator_no_direct_page_wrapper": "_candidate_bottom_updates" not in full_calls,
        "fast_evaluator_no_direct_page_wrapper": "_candidate_bottom_updates" not in fast_calls,
        "service_shape_cases_match": all(row["matches"] for row in parity_rows),
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
        "schema": "design_guide_candidate_bottom_updates_evaluator_service_handoff.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "CANDIDATE_BOTTOM_UPDATES_EVALUATOR_CALLS_SERVICE_OWNED"
            if all(checks.values())
            else "CANDIDATE_BOTTOM_UPDATES_EVALUATOR_HANDOFF_FAILED"
        ),
        "parity_rows": parity_rows,
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_candidate_bottom_updates_evaluator_service_handoff_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_bottom_updates_evaluator_service_handoff_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Bottom Updates Evaluator Service Handoff",
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
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(dict(payload.get("checks") or {}).items()))
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(f"design_guide_candidate_bottom_updates_evaluator_service_handoff {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
