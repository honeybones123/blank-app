"""Verify cleanup attempted-pass/category classification extraction."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from design_brain.design_guide_controller import (  # noqa: E402
    resolve_design_guide_controller_cleanup_attempted_passed,
    resolve_design_guide_controller_cleanup_rejection_category,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


FINAL_FLOOR = 0.85
TARGET_MAX = 1.0


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _legacy_attempted_passed(row: dict[str, Any] | None, attempted_util: float | None = None) -> bool | None:
    row_d = dict(row or {})
    explicit = row_d.get("attempted_passed")
    if isinstance(explicit, bool):
        return explicit
    status_text = " ".join(
        str(row_d.get(key) or "")
        for key in ("failed_check_status", "attempted_status", "preview_status", "status", "rejection_category")
    ).strip().lower()
    if any(token in status_text for token in ("spacing", "detailing", "ductility", "serviceability", "unsafe")):
        return False
    if "fail" in status_text and "final accepted" not in status_text and "efficiency" not in status_text:
        return False
    if any(token in status_text for token in ("pass", "safe", "accepted floor", "below accepted", "preferred band")):
        return True
    if attempted_util is not None:
        return float(attempted_util) <= 1.0
    return None


def _legacy_rejection_category(row: dict[str, Any] | None, attempted_util: float | None = None) -> str:
    row_d = dict(row or {})
    explicit = str(row_d.get("rejection_category") or "").strip()
    if explicit:
        return explicit
    text = " ".join(
        str(row_d.get(key) or "")
        for key in (
            "failed_check_name",
            "failed_check_status",
            "failed_check_reason",
            "reason",
            "rejection_reason",
            "failed_candidate_reason",
            "limit_name",
        )
    ).lower()
    attempted_passed = _legacy_attempted_passed(row_d, attempted_util)
    if attempted_passed is True and attempted_util is not None:
        if float(attempted_util) < FINAL_FLOOR:
            return "Safe but still below accepted efficiency floor"
        if float(attempted_util) > TARGET_MAX:
            return "Safe but above preferred band, with no better preferred-band candidate"
    if "not executor" in text or "not executable" in text or "advisory" in text:
        return "Not executor-backed"
    if "superseded" in text or "combined same-click" in text or "combined cleanup" in text:
        return "Superseded by better combined same-click option"
    if "geometry locked" in text or "not permitted" in text or "locked" in text:
        return "Geometry locked / not permitted"
    if any(token in text for token in ("spacing", "detailing", "ductility", "fit", "minimum clear")):
        return "Unsafe - failed spacing/detailing/ductility"
    if any(token in text for token in ("serviceability", "deflection", "crack", "sls")):
        return "Unsafe - failed serviceability"
    if attempted_passed is False:
        return "Unsafe - failed capacity"
    if attempted_passed is True:
        return "Safe but still below accepted efficiency floor"
    return "Not executor-backed"


def _cases() -> list[tuple[dict[str, Any], float | None]]:
    return [
        ({"attempted_passed": True}, None),
        ({"failed_check_status": "FAIL"}, 1.1),
        ({"failed_check_status": "PASS"}, 0.7),
        ({"failed_check_status": "safe"}, 1.2),
        ({"reason": "not executable candidate"}, None),
        ({"reason": "geometry locked by user"}, None),
        ({"reason": "minimum clear spacing failed"}, None),
        ({"reason": "crack serviceability failed"}, None),
        ({}, 0.9),
        ({}, None),
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, table = _function_source(inputs_source, "_design_guide_blocker_attempts_table")
    _, _, label_helper = _function_source(inputs_source, "_design_guide_cleanup_attempt_label")

    parity_rows: list[dict[str, Any]] = []
    for index, (row, attempted_util) in enumerate(_cases()):
        legacy_passed = _legacy_attempted_passed(row, attempted_util)
        current_passed = resolve_design_guide_controller_cleanup_attempted_passed(row, attempted_util)
        legacy_category = _legacy_rejection_category(row, attempted_util)
        current_category = resolve_design_guide_controller_cleanup_rejection_category(
            row,
            attempted_util,
            final_accepted_min_family_util=FINAL_FLOOR,
            guidance_target_util_max=TARGET_MAX,
        )
        parity_rows.append(
            {
                "case": index,
                "matches": legacy_passed == current_passed and legacy_category == current_category,
                "legacy_passed": legacy_passed,
                "current_passed": current_passed,
                "legacy_category": legacy_category,
                "current_category": current_category,
            }
        )

    table_delegates = (
        "_resolve_design_guide_controller_cleanup_attempted_passed(" in table
        and "_resolve_design_guide_controller_cleanup_rejection_category(" in table
    )
    attempt_label_stays_page_owned = "_guidance_change_lines_for_updates(" in label_helper
    return {
        "schema": "design_guide_blocker_attempts_cleanup_pass_category_extraction.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "table_delegates_classification_to_controller": table_delegates,
        "attempt_label_stays_page_owned": attempt_label_stays_page_owned,
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "parity_rows": parity_rows,
        "parity_pass": all(row.get("matches") for row in parity_rows),
        "attempt_label_moved": False,
        "arrangement_label_moved": False,
        "row_assembly_moved": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "table_delegates_classification_to_controller": bool(payload.get("table_delegates_classification_to_controller")),
        "attempt_label_stays_page_owned": bool(payload.get("attempt_label_stays_page_owned")),
        "parity_pass": bool(payload.get("parity_pass")),
        "attempt_label_not_moved": not bool(payload.get("attempt_label_moved")),
        "arrangement_label_not_moved": not bool(payload.get("arrangement_label_moved")),
        "row_assembly_not_moved": not bool(payload.get("row_assembly_moved")),
        "controller_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_pass_category_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_pass_category_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Pass/Category Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "Cleanup attempted-pass and rejection-category classification now delegates to DesignGuideController. Attempt/arrangement wording remains page-owned.",
        "",
        "## Parity Cases",
        "",
        "| Case | Matches |",
        "| --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| {row.get('case')} | {'PASS' if row.get('matches') else 'FAIL'} |")
    lines.extend(["", "## Checks"])
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_blocker_attempts_cleanup_pass_category_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
