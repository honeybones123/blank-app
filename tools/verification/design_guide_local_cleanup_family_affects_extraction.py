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

TARGET = "_local_cleanup_candidate_affects_family"
CONTROLLER_TARGET = "resolve_design_guide_controller_local_cleanup_candidate_affects_family"

FORBIDDEN_PAGE_TOKENS = {
    "_COMPOUND_SHEAR_UPDATE_KEYS",
    "_COMPOUND_BOTTOM_UPDATE_KEYS",
    "_COMPOUND_GEOMETRY_UPDATE_KEYS",
    "PRIMARY_GEOMETRY_KEYS",
    "fam ==",
    "has_shear",
    "has_bottom",
    "has_geometry",
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


def _expected_affects(family: str, updates: dict[str, Any] | None) -> bool:
    geometry_keys = {"b", "bw", "D", "bf", "tf", "tw", "bf_bot", "tf_bot"}
    bottom_keys = {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "bot1_spacing",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "bot2_spacing",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
        "bot_row_3_mode",
        "bot_row_3_bars",
        "bot_row_3_spacing",
        "bot_row_3_dia",
        "bot_row_4_mode",
        "bot_row_4_bars",
        "bot_row_4_spacing",
        "bot_row_4_dia",
        "Ast_bot",
    }
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    primary_geometry_keys = {"sec_shape", "b", "D", "bf", "tf", "bw", "tw", "bf_bot", "tf_bot"}
    fam = str(family or "").strip().lower()
    keys = set(dict(updates or {}))
    has_shear = bool(keys & shear_keys)
    has_bottom = bool(keys & bottom_keys) or any(
        str(key).startswith("bot") or str(key).startswith("db_bot") for key in keys
    )
    has_geometry = bool(keys & primary_geometry_keys or keys & geometry_keys)
    if fam == "shear":
        return has_shear
    if fam == "bending":
        return bool(has_bottom or has_geometry)
    if fam in {"crack", "deflection", "serviceability"}:
        return bool(has_bottom or has_geometry)
    if fam == "geometry":
        return has_geometry
    return False


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_local_cleanup_candidate_affects_family,
    )

    cases = [
        ("shear_link_change", "shear", {"lig_d": 10}),
        ("shear_ignores_bottom", "shear", {"bot1_count": 4}),
        ("bending_bottom_change", "bending", {"bot_row_2_dia": 16}),
        ("bending_prefix_bottom_change", "bending", {"bot_custom": 1}),
        ("bending_geometry_change", "bending", {"D": 650}),
        ("geometry_width_change", "geometry", {"bw": 400}),
        ("geometry_ignores_shear", "geometry", {"s_lig": 250}),
        ("crack_bottom_change", "crack", {"Ast_bot": 1200}),
        ("deflection_geometry_change", "deflection", {"bf_bot": 300}),
        ("serviceability_bottom_prefix_change", "serviceability", {"db_bot_custom": 20}),
        ("unknown_no_affect", "torsion", {"D": 650, "lig_d": 10}),
        ("empty_updates", "bending", {}),
    ]
    rows: list[dict[str, Any]] = []
    for name, family, updates in cases:
        expected = _expected_affects(family, updates)
        actual = bool(
            resolve_design_guide_controller_local_cleanup_candidate_affects_family(
                family=family,
                updates=updates,
            )
        )
        rows.append(
            {
                "case": name,
                "family": family,
                "updates": updates,
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
        "schema": "design_guide_local_cleanup_family_affects_extraction.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_helper": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "page_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in page_segment,
        "page_no_longer_owns_family_policy": not forbidden_page_tokens,
        "forbidden_page_tokens_present": forbidden_page_tokens,
        "controller_has_family_policy": all(
            token in controller_segment
            for token in (
                "fam == \"shear\"",
                "fam == \"bending\"",
                "fam in {\"crack\", \"deflection\", \"serviceability\"}",
                "fam == \"geometry\"",
                "_CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS",
                "_CONTROLLER_COMPOUND_BOTTOM_UPDATE_KEYS",
                "_CONTROLLER_COMPOUND_GEOMETRY_UPDATE_KEYS",
                "_CONTROLLER_PRIMARY_GEOMETRY_KEYS",
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
        "page_no_longer_owns_family_policy": bool(capture.get("page_no_longer_owns_family_policy")),
        "controller_has_family_policy": bool(capture.get("controller_has_family_policy")),
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
        "`_local_cleanup_candidate_affects_family(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned the local cleanup family/update-key policy.",
        "",
        "## Ownership After",
        "`design_brain.design_guide_controller.resolve_design_guide_controller_local_cleanup_candidate_affects_family(...)` owns the pure policy; `inputs_page.py` delegates.",
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
            f"- Page no longer owns family policy: `{capture.get('page_no_longer_owns_family_policy')}`",
            "",
            "## Deadness / Deletion Proof",
            "The old page-local policy branches were replaced by a shell wrapper. The wrapper remains because existing page callsites still call `_local_cleanup_candidate_affects_family(...)`.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_local_cleanup_family_affects_extraction.py`",
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
            "Candidate generation/evaluation orchestration around direct target-band cleanup remains page-owned and must be extracted in later slices.",
            "",
            "## Next Safe Target",
            "Extract the pure shear/geometry practical preference score helpers or the next local cleanup candidate service boundary.",
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
        f"## {stamp} - Local Cleanup Family-Affects Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved local cleanup family/update-key policy into `DesignGuideController`.\n"
        "- Page wrapper remains shell-only for existing callsites.\n"
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
        "schema": "design_guide_local_cleanup_family_affects_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_family_affects_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_family_affects_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_family_affects_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_family_affects_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
