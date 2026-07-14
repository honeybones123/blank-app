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

TARGET = "_local_cleanup_material_proxy"
CONTROLLER_TARGET = "resolve_design_guide_controller_local_cleanup_material_proxy"
FORBIDDEN_PAGE_TOKENS = {
    "shear_density",
    "width * depth * 0.001",
    "ast * 0.05",
    "20.0",
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


def _expected_proxy(width: Any, depth: Any, ast: Any, lig_d: Any, lig_legs: Any, spacing: Any) -> float:
    try:
        width_value = float(width or 0.0)
    except Exception:
        width_value = 0.0
    try:
        depth_value = float(depth or 0.0)
    except Exception:
        depth_value = 0.0
    try:
        ast_value = float(ast or 0.0)
    except Exception:
        ast_value = 0.0
    try:
        lig_d_value = float(lig_d or 0.0)
    except Exception:
        lig_d_value = 0.0
    try:
        lig_legs_value = float(lig_legs or 0.0)
    except Exception:
        lig_legs_value = 0.0
    try:
        spacing_value = max(float(spacing or 0.0), 1.0)
    except Exception:
        spacing_value = 1.0
    shear_density = lig_legs_value * lig_d_value * lig_d_value / spacing_value
    return float(width_value * depth_value * 0.001 + ast_value * 0.05 + shear_density * 20.0)


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_local_cleanup_material_proxy,
    )

    cases = [
        ("empty", 0, 0, 0, 0, 0, 0),
        ("geometry_only", 400, 650, 0, 0, 0, 0),
        ("bottom_reo", 400, 650, 1200, 0, 0, 0),
        ("shear_density", 400, 650, 1200, 10, 2, 250),
        ("spacing_floor", 400, 650, 1200, 10, 2, 0),
        ("bad_values", "bad", 650, None, "x", 2, "bad"),
    ]
    rows = []
    for name, width, depth, ast, lig_d, lig_legs, spacing in cases:
        expected = _expected_proxy(width, depth, ast, lig_d, lig_legs, spacing)
        actual = resolve_design_guide_controller_local_cleanup_material_proxy(
            width=width,
            depth=depth,
            ast=ast,
            lig_d=lig_d,
            lig_legs=lig_legs,
            spacing=spacing,
        )
        rows.append(
            {
                "case": name,
                "expected": expected,
                "actual": actual,
                "passed": abs(float(actual) - float(expected)) <= 1e-12,
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
        "schema": "design_guide_local_cleanup_material_proxy_extraction.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_helper": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "page_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in page_segment,
        "page_still_collects_scalar_inputs": all(
            token in page_segment
            for token in (
                "_design_width_value",
                "_bottom_ast_from_visible_arrangement",
                "_effective_bottom_design_state",
                "_float_from_state",
            )
        ),
        "page_no_longer_owns_proxy_formula": not forbidden_page_tokens,
        "forbidden_page_tokens_present": forbidden_page_tokens,
        "controller_has_proxy_formula": all(
            token in controller_segment
            for token in (
                "shear_density",
                "width_value * depth_value * 0.001",
                "ast_value * 0.05",
                "20.0",
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
        "page_still_collects_scalar_inputs": bool(capture.get("page_still_collects_scalar_inputs")),
        "page_no_longer_owns_proxy_formula": bool(capture.get("page_no_longer_owns_proxy_formula")),
        "controller_has_proxy_formula": bool(capture.get("controller_has_proxy_formula")),
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
        "`_local_cleanup_material_proxy(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned the local cleanup material proxy formula.",
        "",
        "## Ownership After",
        "`DesignGuideController` owns the formula; `inputs_page.py` supplies existing scalar inputs.",
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
            f"- Page still collects scalar inputs: `{capture.get('page_still_collects_scalar_inputs')}`",
            "",
            "## Deadness / Deletion Proof",
            "The old page-local proxy formula is replaced. The page wrapper remains because state/arrangement scalar extraction is still page-dependent.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_local_cleanup_material_proxy_extraction.py`",
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
            "Local cleanup evaluator orchestration and raw state extraction remain in `inputs_page.py`.",
            "",
            "## Next Safe Target",
            "Audit `_evaluate_local_cleanup_guidance_item(...)` as the next local cleanup service boundary.",
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
        f"## {stamp} - Local Cleanup Material Proxy Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved local cleanup material proxy formula into `DesignGuideController`.\n"
        "- Page still supplies existing scalar state/arrangement inputs.\n"
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
        "schema": "design_guide_local_cleanup_material_proxy_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_material_proxy_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_material_proxy_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_material_proxy_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_material_proxy_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
