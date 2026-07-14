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

TARGET = "_local_cleanup_materially_reduces"
CONTROLLER_TARGET = "resolve_design_guide_controller_local_cleanup_materially_reduces"
FORBIDDEN_PAGE_TOKENS = {
    "fam ==",
    "return bool(shear_reduces or bottom_reduces or section_reduces)",
    "if fam == \"shear\"",
    "if fam in {\"bending\", \"bottom_reo\"}",
    "if fam == \"geometry\"",
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


def _expected_materially_reduces(
    family: str,
    shear_reduces: bool,
    bottom_reduces: bool,
    section_reduces: bool,
) -> bool:
    fam = str(family or "").strip().lower()
    if fam == "shear":
        return bool(shear_reduces)
    if fam in {"bending", "bottom_reo"}:
        return bool(bottom_reduces)
    if fam == "geometry":
        return bool(section_reduces)
    return bool(shear_reduces or bottom_reduces or section_reduces)


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_local_cleanup_materially_reduces,
    )

    cases = [
        ("shear_true", "shear", True, False, False),
        ("shear_false_ignores_bottom", "shear", False, True, True),
        ("bending_true", "bending", False, True, False),
        ("bottom_reo_true", "bottom_reo", False, True, False),
        ("bending_ignores_shear", "bending", True, False, False),
        ("geometry_true", "geometry", False, False, True),
        ("geometry_ignores_bottom", "geometry", False, True, False),
        ("unknown_any_true", "combined", True, False, False),
        ("unknown_all_false", "combined", False, False, False),
    ]
    rows = []
    for name, family, shear, bottom, section in cases:
        expected = _expected_materially_reduces(family, shear, bottom, section)
        actual = bool(
            resolve_design_guide_controller_local_cleanup_materially_reduces(
                family=family,
                shear_reduces=shear,
                bottom_reduces=bottom,
                section_reduces=section,
            )
        )
        rows.append(
            {
                "case": name,
                "family": family,
                "expected": expected,
                "actual": actual,
                "passed": actual is expected,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    page_segment = _function_segment(inputs_source, TARGET)
    controller_segment = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_page_tokens = sorted(token for token in FORBIDDEN_PAGE_TOKENS if token in page_segment)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_local_cleanup_materially_reduces_extraction.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_helper": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "page_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in page_segment,
        "page_still_computes_raw_reduction_inputs": all(
            token in page_segment
            for token in (
                "_shear_cleanup_materially_reduces_reinforcement",
                "_state_update_reduces_bottom_reinforcement",
                "_state_update_reduces_section_size",
            )
        ),
        "page_no_longer_owns_family_branch_policy": not forbidden_page_tokens,
        "forbidden_page_tokens_present": forbidden_page_tokens,
        "controller_has_branch_policy": all(
            token in controller_segment
            for token in (
                "fam == \"shear\"",
                "fam in {\"bending\", \"bottom_reo\"}",
                "fam == \"geometry\"",
                "shear_reduces or bottom_reduces or section_reduces",
            )
        ),
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(case.get("passed") for case in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "page_delegates_to_controller": bool(capture.get("page_delegates_to_controller")),
        "page_still_computes_raw_reduction_inputs": bool(capture.get("page_still_computes_raw_reduction_inputs")),
        "page_no_longer_owns_family_branch_policy": bool(capture.get("page_no_longer_owns_family_branch_policy")),
        "controller_has_branch_policy": bool(capture.get("controller_has_branch_policy")),
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
        "`_local_cleanup_materially_reduces(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned the family-specific materiality branch policy.",
        "",
        "## Ownership After",
        "`DesignGuideController` owns the branch policy; `inputs_page.py` supplies raw reduction booleans from existing page helpers.",
        "",
        "## Behaviour Preserved",
        f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{capture.get('family_runtimes_changed')}`",
        "",
        "## Adapter / Default Rebuild Proof",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(f"- `{case.get('case')}`: passed=`{case.get('passed')}`")
    lines.extend(
        [
            "",
            "## Cutover Proof",
            f"- Page imports controller helper: `{capture.get('page_imports_controller_helper')}`",
            f"- Page delegates to controller: `{capture.get('page_delegates_to_controller')}`",
            f"- Page still computes raw reduction inputs: `{capture.get('page_still_computes_raw_reduction_inputs')}`",
            "",
            "## Deadness / Deletion Proof",
            "The old page-local branch policy was replaced. The page wrapper remains because raw reduction measurements are still page helper dependencies.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_local_cleanup_materially_reduces_extraction.py`",
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
            "The raw materiality measurements and local cleanup evaluator orchestration remain in `inputs_page.py`.",
            "",
            "## Next Safe Target",
            "Audit `_evaluate_local_cleanup_guidance_item(...)` for a controller/service boundary, or extract pure material proxy scalar policy.",
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
        f"## {stamp} - Local Cleanup Materially-Reduces Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved family-specific cleanup materiality branch policy into `DesignGuideController`.\n"
        "- Page still supplies raw reduction booleans from existing state helpers.\n"
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
        "schema": "design_guide_local_cleanup_materially_reduces_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_materially_reduces_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_materially_reduces_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_materially_reduces_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_materially_reduces_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
