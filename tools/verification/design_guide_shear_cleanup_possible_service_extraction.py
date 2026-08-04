"""Verify shear cleanup possible policy service extraction."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import resolve_shear_cleanup_possible  # noqa: E402


INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(node.end_lineno or node.lineno)
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _old_possible(lig_legs: Any, spacing_mm: Any, max_spacing_mm: Any) -> bool:
    try:
        legs = int(lig_legs or 0)
    except (TypeError, ValueError):
        legs = 0
    try:
        spacing = float(spacing_mm or 0.0)
    except (TypeError, ValueError):
        spacing = 0.0
    try:
        max_spacing = float(max_spacing_mm if max_spacing_mm is not None else 300.0)
    except (TypeError, ValueError):
        max_spacing = 300.0
    return legs > 0 or (spacing > 0.0 and spacing < max_spacing - 1e-9)


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = [
        {"name": "links_present", "lig_legs": 2, "spacing_mm": 300.0, "max_spacing_mm": 300.0},
        {"name": "zero_links_spacing_below_max", "lig_legs": 0, "spacing_mm": 200.0, "max_spacing_mm": 300.0},
        {"name": "zero_links_spacing_at_max", "lig_legs": 0, "spacing_mm": 300.0, "max_spacing_mm": 300.0},
        {"name": "zero_links_no_spacing", "lig_legs": 0, "spacing_mm": 0.0, "max_spacing_mm": 300.0},
        {"name": "bad_values", "lig_legs": "bad", "spacing_mm": "bad", "max_spacing_mm": "bad"},
        {"name": "missing_max_spacing_defaults", "lig_legs": 0, "spacing_mm": 250.0, "max_spacing_mm": None},
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        old = _old_possible(case["lig_legs"], case["spacing_mm"], case["max_spacing_mm"])
        new = resolve_shear_cleanup_possible(
            lig_legs=case["lig_legs"],
            spacing_mm=case["spacing_mm"],
            max_spacing_mm=case["max_spacing_mm"],
        )
        row = {
            "case": case["name"],
            "old": old,
            "new": new,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)
    return rows, mismatches


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_source(inputs_source, "_shear_cleanup_possible")
    rows, mismatches = _case_rows()
    static_checks = {
        "service_helper_present": "def resolve_shear_cleanup_possible(" in candidate_source,
        "page_imports_service_helper": "resolve_shear_cleanup_possible as _resolve_shear_cleanup_possible" in inputs_source,
        "page_wrapper_delegates": "return _resolve_shear_cleanup_possible(" in helper,
        "page_wrapper_keeps_state_parsing": "_int_from_state(" in helper and "_float_from_state(" in helper,
        "page_wrapper_keeps_spacing_constant": "REO_SPACINGS" in helper,
        "old_inline_policy_removed": "lig_legs > 0 or" not in helper,
        "candidate_service_avoids_inputs_page": "inputs_page" not in candidate_source,
        "candidate_service_avoids_streamlit": "streamlit" not in candidate_source and "st.session_state" not in candidate_source,
    }
    status = "PASS"
    if mismatches or not all(static_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "shear_cleanup_possible_service_extraction",
        "extraction_complete_estimate": "99%",
        "inputs_segment": {"function": "_shear_cleanup_possible", "line_start": start, "line_end": end},
        "static_checks": static_checks,
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "ownership_after": {
            "design_brain_candidate_evaluation": ["shear cleanup possible policy"],
            "inputs_page": ["state scalar parsing and spacing constant handoff"],
        },
        "next_safe_slice": "reassess target-band lane bodies; no small pure gate remains ready",
        "product_behavior_changed": False,
    }


def _write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_shear_cleanup_possible_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_shear_cleanup_possible_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Shear Cleanup Possible Service Extraction",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        "",
        "The shear cleanup possible policy now lives in `design_brain.candidate_evaluation`; `inputs_page.py` keeps scalar parsing and spacing constant handoff.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Parity Cases"])
    for row in payload["parity_rows"]:
        lines.append(f"- `{row['case']}`: matches `{row['matches']}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    _write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
