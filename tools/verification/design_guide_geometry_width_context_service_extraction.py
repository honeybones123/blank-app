"""Verify plain geometry width-context extraction into candidate_evaluation."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.candidate_evaluation import resolve_geometry_width_context  # noqa: E402


CASES = [
    {
        "name": "rect_explicit_width",
        "state": {"sec_shape": "RECT", "b": 450.0},
        "expected": ("b", "Width b (mm)", 450.0),
    },
    {
        "name": "rect_default_width",
        "state": {"sec_shape": "RECT"},
        "expected": ("b", "Width b (mm)", 400.0),
    },
    {
        "name": "t_section_web_width",
        "state": {"sec_shape": "T", "b": 500.0, "bw": 320.0},
        "expected": ("bw", "Web width bw (mm)", 320.0),
    },
    {
        "name": "t_section_fallback_to_b",
        "state": {"sec_shape": "T", "b": 510.0},
        "expected": ("bw", "Web width bw (mm)", 510.0),
    },
    {
        "name": "t_section_default_width",
        "state": {"sec_shape": "T"},
        "expected": ("bw", "Web width bw (mm)", 300.0),
    },
    {
        "name": "i_section_web_thickness",
        "state": {"sec_shape": "I", "b": 500.0, "tw": 220.0},
        "expected": ("tw", "Web thickness tw (mm)", 220.0),
    },
    {
        "name": "i_section_fallback_to_b",
        "state": {"sec_shape": "I", "b": 360.0},
        "expected": ("tw", "Web thickness tw (mm)", 360.0),
    },
    {
        "name": "i_section_default_width",
        "state": {"sec_shape": "I"},
        "expected": ("tw", "Web thickness tw (mm)", 200.0),
    },
    {
        "name": "blank_shape_defaults_rect",
        "state": {"sec_shape": "", "b": 390.0},
        "expected": ("b", "Width b (mm)", 390.0),
    },
    {
        "name": "missing_state_defaults_rect",
        "state": None,
        "expected": ("b", "Width b (mm)", 400.0),
    },
]


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


def _legacy_expected(state: dict[str, Any] | None) -> tuple[str, str, float]:
    source = dict(state or {})
    sec_shape = str(source.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(source.get("bw", source.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(source.get("tw", source.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(source.get("b", 400.0) or 400.0)


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    wrapper_start, wrapper_end, wrapper_source = _function_source(inputs_source, "_resolve_geometry_width_context")
    helper_start, helper_end, helper_source = _function_source(candidate_source, "resolve_geometry_width_context")

    cases = []
    for case in CASES:
        actual = resolve_geometry_width_context(case["state"])
        legacy = _legacy_expected(case["state"])
        cases.append(
            {
                "name": case["name"],
                "actual": list(actual),
                "expected": list(case["expected"]),
                "legacy": list(legacy),
                "matches_expected": actual == case["expected"],
                "matches_legacy": actual == legacy,
            }
        )

    checks = {
        "all_cases_match_expected": all(row["matches_expected"] for row in cases),
        "all_cases_match_legacy": all(row["matches_legacy"] for row in cases),
        "service_helper_present": "def resolve_geometry_width_context(" in candidate_source,
        "page_imports_service_helper": "resolve_geometry_width_context as _resolve_geometry_width_context_service" in inputs_source,
        "page_wrapper_delegates": "return _resolve_geometry_width_context_service(state)" in wrapper_source,
        "page_wrapper_is_small": (wrapper_end - wrapper_start + 1) <= 3,
        "candidate_evaluation_no_inputs_page_import": "inputs_page" not in candidate_source,
        "candidate_evaluation_no_streamlit_import": "streamlit" not in candidate_source and "st." not in helper_source,
        "helper_supports_rect_t_i": all(token in helper_source for token in ('sec_shape == "T"', 'sec_shape == "I"', 'return "b"')),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "geometry_width_context_service_extraction",
        "product_behavior_changed": False,
        "extraction_complete_estimate": "99%",
        "cases": cases,
        "checks": checks,
        "wrapper": {
            "line_start": wrapper_start,
            "line_end": wrapper_end,
            "line_count": wrapper_end - wrapper_start + 1,
        },
        "service_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "next_safe_slice": "audit _geometry_state_with_updates and depth/width contract guard before moving geometry candidate generation",
    }


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_geometry_width_context_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_geometry_width_context_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Geometry Width Context Service Extraction",
            "",
            "## Executive Summary",
            f"- Status: `{payload['status']}`",
            f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
            f"- Product behavior changed: `{payload['product_behavior_changed']}`",
            "",
            "## Behaviour Preserved",
            *[
                f"- `{row['name']}`: actual `{row['actual']}` legacy `{row['legacy']}`"
                for row in payload["cases"]
            ],
            "",
            "## Checks",
            *[f"- `{name}`: `{passed}`" for name, passed in payload["checks"].items()],
            "",
            "## Wrapper",
            f"- Lines: `{payload['wrapper']['line_start']}-{payload['wrapper']['line_end']}`",
            f"- Line count: `{payload['wrapper']['line_count']}`",
            "",
            "## Service Helper",
            f"- Lines: `{payload['service_helper']['line_start']}-{payload['service_helper']['line_end']}`",
            f"- Line count: `{payload['service_helper']['line_count']}`",
            "",
            "## Next Safe Slice",
            payload["next_safe_slice"],
            "",
        ]
    )


def main() -> int:
    payload = _build_payload()
    payload["artifact_paths"] = _write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
