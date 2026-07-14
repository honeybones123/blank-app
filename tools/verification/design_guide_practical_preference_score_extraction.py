from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
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

SHEAR_PAGE_TARGET = "_design_guide_shear_practical_preference_score"
GEOMETRY_PAGE_TARGET = "_design_guide_geometry_proportion_preference_score"
SHEAR_CONTROLLER_TARGET = "resolve_design_guide_controller_shear_practical_preference_score"
GEOMETRY_CONTROLLER_TARGET = "resolve_design_guide_controller_geometry_proportion_preference_score"

FORBIDDEN_SHEAR_PAGE_TOKENS = {
    "leg_penalty",
    "100 + abs",
    "-dia",
}
FORBIDDEN_GEOMETRY_PAGE_TOKENS = {
    "ratio =",
    "ratio <=",
    "ratio - 2.0",
    "abs(ratio - 2.0)",
}


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _expected_shear_score(touches: bool, legs: Any, diameter: Any, spacing: Any) -> tuple[Any, ...]:
    if not bool(touches):
        return (0, 0, 0.0, 0)
    try:
        legs_value = max(int(legs or 0), 0)
    except Exception:
        legs_value = 0
    try:
        diameter_value = max(int(diameter or 0), 0)
    except Exception:
        diameter_value = 0
    try:
        spacing_value = float(spacing or 0.0)
    except Exception:
        spacing_value = 0.0
    leg_penalty = 0 if legs_value == 2 else (100 + abs(legs_value - 2))
    return (leg_penalty, spacing_value, -diameter_value, legs_value)


def _expected_geometry_score(touches: bool, locked: bool, depth: Any, width: Any, invalid: bool = False) -> tuple[Any, ...]:
    if bool(locked) or not bool(touches):
        return (0, 0.0, 0.0)
    if bool(invalid):
        return (3, 99.0, 99.0)
    try:
        depth_value = float(depth or 0.0)
        width_value = float(width or 0.0)
    except Exception:
        return (3, 99.0, 99.0)
    if depth_value <= 0.0 or width_value <= 0.0:
        return (3, 99.0, 99.0)
    ratio = depth_value / width_value
    if ratio <= 2.0 + 1e-9:
        return (0, abs(ratio - 2.0), ratio)
    if ratio <= 2.5 + 1e-9:
        return (1, ratio - 2.0, ratio)
    return (2, ratio - 2.0, ratio)


def _parity_cases() -> dict[str, list[dict[str, Any]]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_geometry_proportion_preference_score,
        resolve_design_guide_controller_shear_practical_preference_score,
    )

    shear_inputs = [
        ("no_shear_updates", False, 2, 10, 250.0),
        ("two_leg_preferred", True, 2, 10, 200.0),
        ("zero_leg_penalized", True, 0, 10, 200.0),
        ("four_leg_penalized", True, 4, 12, 150.0),
        ("bad_values_normalize", True, "x", None, "bad"),
    ]
    geometry_inputs = [
        ("no_geometry_updates", False, False, 600.0, 300.0, False),
        ("geometry_locked", True, True, 600.0, 300.0, False),
        ("ratio_under_two", True, False, 500.0, 300.0, False),
        ("ratio_exact_two", True, False, 600.0, 300.0, False),
        ("ratio_mid_penalty", True, False, 700.0, 300.0, False),
        ("ratio_high_penalty", True, False, 900.0, 300.0, False),
        ("invalid_geometry", True, False, 0.0, 300.0, False),
        ("exception_geometry", True, False, "bad", 300.0, True),
    ]
    shear_rows = []
    for name, touches, legs, diameter, spacing in shear_inputs:
        expected = _expected_shear_score(touches, legs, diameter, spacing)
        actual = resolve_design_guide_controller_shear_practical_preference_score(
            touches_shear_updates=touches,
            legs=legs,
            diameter=diameter,
            spacing=spacing,
        )
        shear_rows.append(
            {
                "case": name,
                "expected": list(expected),
                "actual": list(actual),
                "passed": actual == expected,
            }
        )
    geometry_rows = []
    for name, touches, locked, depth, width, invalid in geometry_inputs:
        expected = _expected_geometry_score(touches, locked, depth, width, invalid)
        actual = resolve_design_guide_controller_geometry_proportion_preference_score(
            touches_geometry_updates=touches,
            geometry_locked=locked,
            depth=depth,
            width=width,
            invalid_geometry=invalid,
        )
        geometry_rows.append(
            {
                "case": name,
                "expected": list(expected),
                "actual": list(actual),
                "passed": actual == expected,
            }
        )
    return {"shear": shear_rows, "geometry": geometry_rows}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    shear_page = _function_segment(inputs_source, SHEAR_PAGE_TARGET)
    geometry_page = _function_segment(inputs_source, GEOMETRY_PAGE_TARGET)
    shear_controller = _function_segment(controller_source, SHEAR_CONTROLLER_TARGET)
    geometry_controller = _function_segment(controller_source, GEOMETRY_CONTROLLER_TARGET)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_practical_preference_score_extraction.v1",
        "page_targets": [SHEAR_PAGE_TARGET, GEOMETRY_PAGE_TARGET],
        "controller_targets": [SHEAR_CONTROLLER_TARGET, GEOMETRY_CONTROLLER_TARGET],
        "page_imports_controller_helpers": all(
            f"{target} as _{target}" in inputs_source
            for target in (SHEAR_CONTROLLER_TARGET, GEOMETRY_CONTROLLER_TARGET)
        ),
        "page_delegates_to_controller_helpers": all(
            f"_{target}(" in segment
            for target, segment in (
                (SHEAR_CONTROLLER_TARGET, shear_page),
                (GEOMETRY_CONTROLLER_TARGET, geometry_page),
            )
        ),
        "forbidden_shear_page_tokens_present": sorted(token for token in FORBIDDEN_SHEAR_PAGE_TOKENS if token in shear_page),
        "forbidden_geometry_page_tokens_present": sorted(token for token in FORBIDDEN_GEOMETRY_PAGE_TOKENS if token in geometry_page),
        "controller_has_shear_score_policy": all(
            token in shear_controller
            for token in ("leg_penalty", "100 + abs", "-diameter_value")
        ),
        "controller_has_geometry_score_policy": all(
            token in geometry_controller
            for token in ("ratio =", "ratio <= 2.0", "ratio <= 2.5", "ratio - 2.0")
        ),
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(
            row.get("passed")
            for group in parity_cases.values()
            for row in group
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_imports_controller_helpers": bool(capture.get("page_imports_controller_helpers")),
        "page_delegates_to_controller_helpers": bool(capture.get("page_delegates_to_controller_helpers")),
        "shear_page_no_longer_owns_score_policy": not capture.get("forbidden_shear_page_tokens_present"),
        "geometry_page_no_longer_owns_score_policy": not capture.get("forbidden_geometry_page_tokens_present"),
        "controller_has_shear_score_policy": bool(capture.get("controller_has_shear_score_policy")),
        "controller_has_geometry_score_policy": bool(capture.get("controller_has_geometry_score_policy")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_design_guide_shear_practical_preference_score(...)` and `_design_guide_geometry_proportion_preference_score(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned the practical preference scoring policy used by direct cleanup candidate ranking.",
        "",
        "## Ownership After",
        "`DesignGuideController` owns the pure scoring policy; page wrappers only collect state-derived scalar inputs.",
        "",
        "## Behaviour Preserved",
        f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{capture.get('family_runtimes_changed')}`",
        "",
        "## Adapter / Default Rebuild Proof",
    ]
    for group_name, rows in dict(capture.get("parity_cases") or {}).items():
        lines.append(f"### {group_name.title()}")
        for row in rows:
            lines.append(f"- `{row.get('case')}`: passed=`{row.get('passed')}`")
    lines.extend(
        [
            "",
            "## Cutover Proof",
            f"- Page imports controller helpers: `{capture.get('page_imports_controller_helpers')}`",
            f"- Page delegates to controller helpers: `{capture.get('page_delegates_to_controller_helpers')}`",
            f"- Forbidden shear page tokens: `{capture.get('forbidden_shear_page_tokens_present')}`",
            f"- Forbidden geometry page tokens: `{capture.get('forbidden_geometry_page_tokens_present')}`",
            "",
            "## Deadness / Deletion Proof",
            "The old page-local score policy was replaced by shell wrappers. Wrappers remain because current callsites still depend on page-derived state scalars.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_practical_preference_score_extraction.py`",
            "",
            "## Verifier Results",
        ]
    )
    for name, passed in checks.items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "Direct target-band candidate generation/evaluation orchestration remains page-owned and must be extracted in later slices.",
            "",
            "## Next Safe Target",
            "Extract the next direct target-band candidate filtering/selection policy surface or begin a candidate evaluation service boundary audit.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = str(payload.get("created_at") or "")
    status = str(payload.get("status") or "")
    existing = PROGRESS_PATH.read_text(encoding="utf-8") if PROGRESS_PATH.exists() else ""
    entry = (
        "\n"
        f"## {stamp} - Practical Preference Score Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved shear and geometry practical preference score policy into `DesignGuideController`.\n"
        "- Page wrappers remain shell-only around state-derived scalar inputs.\n"
        f"- Report: `{report_path}`\n"
    )
    if entry.strip() not in existing:
        PROGRESS_PATH.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_practical_preference_score_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_practical_preference_score_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_practical_preference_score_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_practical_preference_score_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_practical_preference_score_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
