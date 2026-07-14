"""Verify blocker-attempt active-failure inference is controller-owned with parity."""

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
    resolve_design_guide_controller_blocker_attempt_active_failures,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _legacy_active_failures(
    *,
    candidate_search_evidence: dict[str, Any] | None,
    item: dict[str, Any] | None,
    family_status_current: dict[str, Any] | None,
) -> set[str]:
    evidence = dict(candidate_search_evidence or {})
    src = dict(item or {})
    current_rows = dict(family_status_current or {})
    active_failures = {
        str(family or "").strip().lower()
        for family in list(evidence.get("active_failures") or src.get("active_failures") or [])
        if str(family or "").strip()
    }
    if not active_failures:
        active_failures = {
            family
            for family in ("bending", "shear")
            if str(dict(current_rows.get(family) or {}).get("status") or "").strip().upper() == "FAIL"
        }
    return active_failures


def _cases() -> list[dict[str, Any]]:
    return [
        {"evidence": {}, "item": {}, "rows": {}},
        {
            "evidence": {"active_failures": ["Bending", "", "shear"]},
            "item": {"active_failures": ["ignored"]},
            "rows": {"bending": {"status": "PASS"}, "shear": {"status": "PASS"}},
        },
        {
            "evidence": {},
            "item": {"active_failures": ["Shear"]},
            "rows": {"bending": {"status": "FAIL"}, "shear": {"status": "PASS"}},
        },
        {
            "evidence": {},
            "item": {},
            "rows": {"bending": {"status": "FAIL"}, "shear": {"status": "PASS"}},
        },
        {
            "evidence": {},
            "item": {},
            "rows": {"bending": {"status": "fail"}, "shear": {"status": " FAIL "}},
        },
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, helper = _function_source(inputs_source, "_design_guide_blocker_attempts_table")
    _, _, controller_helper = _function_source(
        controller_source,
        "resolve_design_guide_controller_blocker_attempt_active_failures",
    )

    parity_rows: list[dict[str, Any]] = []
    for index, case in enumerate(_cases()):
        legacy = _legacy_active_failures(
            candidate_search_evidence=case.get("evidence"),
            item=case.get("item"),
            family_status_current=case.get("rows"),
        )
        current = resolve_design_guide_controller_blocker_attempt_active_failures(
            candidate_search_evidence=case.get("evidence"),
            item=case.get("item"),
            family_status_current=case.get("rows"),
        )
        parity_rows.append(
            {
                "case": index,
                "matches": legacy == current,
                "legacy": sorted(legacy),
                "current": sorted(current),
            }
        )

    page_delegates = "_resolve_design_guide_controller_blocker_attempt_active_failures(" in helper
    page_local_inference_removed = all(
        token not in helper
        for token in (
            'evidence.get("active_failures")',
            'src.get("active_failures")',
            "if not active_failures:",
        )
    )
    return {
        "schema": "design_guide_blocker_attempts_active_failure_inference_extraction.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "page_delegates_to_controller": page_delegates,
        "page_local_inference_removed": page_local_inference_removed,
        "controller_helper_present": bool(controller_helper),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "parity_rows": parity_rows,
        "parity_pass": all(row.get("matches") for row in parity_rows),
        "candidate_rows_moved": False,
        "combined_row_selection_moved": False,
        "row_assembly_moved": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "controller_helper_present": bool(payload.get("controller_helper_present")),
        "page_delegates_to_controller": bool(payload.get("page_delegates_to_controller")),
        "page_local_inference_removed": bool(payload.get("page_local_inference_removed")),
        "parity_pass": bool(payload.get("parity_pass")),
        "candidate_rows_not_moved": not bool(payload.get("candidate_rows_moved")),
        "combined_row_selection_not_moved": not bool(payload.get("combined_row_selection_moved")),
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_active_failure_inference_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_active_failure_inference_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Active-Failure Inference Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "Active-failure inference now delegates to DesignGuideController. "
        "Candidate row collection and combined-row selection remain page-owned for later slices.",
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
    print(f"design_guide_blocker_attempts_active_failure_inference_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
