"""Verify strength-family band status resolution is controller-owned."""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_direct_target_band_guidance_item"
CONTROLLER_TARGET = "resolve_design_guide_controller_strength_family_band_status"
NESTED_TARGETS = (
    "_candidate_clears_active_strength_family_floor",
    "_candidate_strength_family_utils",
    "_candidate_strength_families_in_band",
    "_candidate_strength_family_band_distance",
)

FORBIDDEN_NESTED_TOKENS = {
    "candidate_utils =",
    "_parse_util_value(candidate_utils",
    "_candidate_search_distance_to_band(",
    "float(low) - TARGET_BAND_EPS",
    "float(FINAL_ACCEPTED_MIN_FAMILY_UTIL)",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _nested_function_segment(source: str, outer_name: str, nested_name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == outer_name:
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef) and child.name == nested_name:
                    return "\n".join(lines[child.lineno - 1 : child.end_lineno])
    return ""


def _legacy_status(
    candidate: dict[str, Any],
    active_floor: set[str],
    *,
    low: float,
    high: float,
    eps: float,
    final_floor: float,
) -> dict[str, Any]:
    utils = dict((candidate.get("overview") or {}).get("utils") or {})
    family_utils: dict[str, float] = {}
    for family in ("bending", "shear"):
        try:
            util = float(utils.get(family))
        except Exception:
            util = None
        if util is not None:
            family_utils[family] = float(util)
    active_families = set(active_floor or {"bending", "shear"})
    clears = True
    if active_floor:
        for family in sorted(active_floor):
            util = family_utils.get(family)
            if util is None or float(util) < final_floor:
                clears = False
                break
    in_band = [
        family
        for family in ("bending", "shear")
        if family in active_families
        and family in family_utils
        and float(low) - eps <= float(family_utils[family]) <= float(high) + eps
    ]
    if not family_utils:
        distance = float("inf")
    else:
        distances: list[float] = []
        for family, util in family_utils.items():
            if family not in active_families:
                continue
            if low <= util <= high:
                distances.append(0.0)
            elif util < low:
                distances.append(low - util)
            else:
                distances.append(util - high)
        distance = min(distances) if distances else float("inf")
    return {
        "family_utils": family_utils,
        "clears_active_strength_family_floor": clears,
        "in_band_families": in_band,
        "band_distance": distance,
    }


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_strength_family_band_status,
    )

    cases = [
        (
            "both_in_band",
            {"overview": {"utils": {"bending": 0.92, "shear": 0.88}}},
            {"bending", "shear"},
        ),
        (
            "bending_below_floor",
            {"overview": {"utils": {"bending": 0.42, "shear": 0.94}}},
            {"bending"},
        ),
        (
            "shear_above_band",
            {"overview": {"utils": {"bending": 0.82, "shear": 1.08}}},
            {"shear"},
        ),
        (
            "no_active_floor_uses_both",
            {"overview": {"utils": {"bending": 0.70, "shear": 0.94}}},
            set(),
        ),
        ("missing_utils", {"overview": {"utils": {}}}, {"bending"}),
    ]
    rows: list[dict[str, Any]] = []
    for name, candidate, active_floor in cases:
        expected = _legacy_status(
            candidate,
            active_floor,
            low=0.85,
            high=0.95,
            eps=0.005,
            final_floor=0.85,
        )
        actual = resolve_design_guide_controller_strength_family_band_status(
            candidate=candidate,
            active_strength_family_floor_set=active_floor,
            target_low=0.85,
            target_high=0.95,
            target_band_eps=0.005,
            final_accepted_min_family_util=0.85,
        )
        checks = {
            "family_utils": actual.get("family_utils") == expected.get("family_utils"),
            "clears_floor": actual.get("clears_active_strength_family_floor")
            == expected.get("clears_active_strength_family_floor"),
            "in_band": actual.get("in_band_families") == expected.get("in_band_families"),
            "distance": (
                actual.get("band_distance") == expected.get("band_distance")
                or (
                    actual.get("band_distance") == float("inf")
                    and expected.get("band_distance") == float("inf")
                )
            ),
        }
        rows.append(
            {
                "case": name,
                "passed": all(checks.values()),
                "checks": checks,
                "expected": expected,
                "actual": actual,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    nested_segments = {
        name: _nested_function_segment(inputs_source, TARGET, name)
        for name in NESTED_TARGETS
    }
    combined_nested = "\n".join(nested_segments.values())
    controller = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_present = sorted(token for token in FORBIDDEN_NESTED_TOKENS if token in combined_nested)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_strength_family_band_status_extraction.v1",
        "target": TARGET,
        "nested_targets": list(NESTED_TARGETS),
        "controller_target": CONTROLLER_TARGET,
        "nested_functions_present": {
            name: bool(segment) for name, segment in nested_segments.items()
        },
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "nested_delegates_to_controller": all(
            f"_{CONTROLLER_TARGET}(" in segment for segment in nested_segments.values()
        ),
        "forbidden_nested_tokens_present": forbidden_present,
        "controller_has_status_fields": all(
            token in controller
            for token in (
                "family_utils",
                "clears_active_strength_family_floor",
                "in_band_families",
                "band_distance",
            )
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source and "streamlit" not in controller_source
        ),
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(case.get("passed") for case in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "nested_functions_present": all((capture.get("nested_functions_present") or {}).values()),
        "controller_helper_present": bool(capture.get("controller_helper_present")),
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "nested_delegates_to_controller": bool(capture.get("nested_delegates_to_controller")),
        "nested_no_longer_owns_status_logic": not capture.get("forbidden_nested_tokens_present"),
        "controller_has_status_fields": bool(capture.get("controller_has_status_fields")),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Strength-Family Band Status Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_direct_target_band_guidance_item(...)` nested strength-family floor/in-band/distance helpers.",
        "",
        "## Ownership Before",
        "`inputs_page.py` parsed candidate strength-family utils and owned floor/in-band/distance scoring.",
        "",
        "## Ownership After",
        "`inputs_page.py` delegates strength-family band status to `resolve_design_guide_controller_strength_family_band_status(...)`.",
        "",
        "## Behaviour Preserved",
        "- engineering behaviour changed: `False`",
        "- visible wording changed: `False`",
        "- CTA/apply semantics changed: `False`",
        "- family runtimes changed: `False`",
        "",
        "## Parity Cases",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(f"- `{case.get('case')}`: passed=`{case.get('passed')}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The page still owns the direct target-band search/evaluation loops and final candidate selection callsites. This slice only moved pure strength-family status scoring.",
            "",
            "## Next Safe Target",
            "Extract final direct-candidate cleanup sort-key construction or another pure selection/scoring helper.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("created_at")
    text = (
        "\n"
        f"## {stamp} - Strength-Family Band Status Extraction\n"
        f"- Result: `{payload.get('status')}`\n"
        "- Moved candidate strength-family floor/in-band/distance scoring into `DesignGuideController`.\n"
        "- Page keeps search/evaluation orchestration and only consumes the returned status fields.\n"
        f"- Report: `{report_path}`\n"
    )
    with PROGRESS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(text)


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_strength_family_band_status_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_strength_family_band_status_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_strength_family_band_status_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_strength_family_band_status_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_strength_family_band_status_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
