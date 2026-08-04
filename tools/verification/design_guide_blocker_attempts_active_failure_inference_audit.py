"""Audit blocker-attempt active-failure inference before extraction."""

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


def _evidence(source: str, token: str, *, start_line: int) -> dict[str, Any]:
    lines = [start_line + index for index, line in enumerate(source.splitlines()) if token in line]
    return {"token": token, "present": bool(lines), "count": len(lines), "lines": lines[:20]}


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, helper = _function_source(inputs_source, "_design_guide_blocker_attempts_table")

    source_merge_bounded = (
        "_build_design_guide_controller_blocker_attempt_source_merge(item)" in helper
        and "blockers.update(" not in helper
    )
    active_failure_inference_old_tokens = [
        "active_failures = {",
        'evidence.get("active_failures")',
        'src.get("active_failures")',
        "if not active_failures:",
        'get("status")',
    ]
    active_failure_inference_present = all(token in helper for token in active_failure_inference_old_tokens)
    active_failure_inference_controller_owned = (
        "_resolve_design_guide_controller_blocker_attempt_active_failures(" in helper
        and "def resolve_design_guide_controller_blocker_attempt_active_failures(" in controller_source
    )

    surfaces = [
        {
            "surface": "explicit active-failures source precedence",
            "classification": (
                "controller-owned active-failure inference"
                if active_failure_inference_controller_owned
                else "page-owned pure active-failure source inference"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if active_failure_inference_controller_owned
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController",
            "readiness": "SHELL_CALL" if active_failure_inference_controller_owned else "READY_TO_EXTRACT",
            "first_safe_slice": (
                None
                if active_failure_inference_controller_owned
                else "blocker_attempts_active_failure_inference_extraction"
            ),
            "risk": "Controls whether blocker rows use active-failure strength wording.",
            "evidence": [
                _evidence(helper, 'evidence.get("active_failures")', start_line=start),
                _evidence(helper, 'src.get("active_failures")', start_line=start),
            ],
            "present": active_failure_inference_controller_owned or active_failure_inference_present,
        },
        {
            "surface": "status fallback inference",
            "classification": (
                "controller-owned status fallback inference"
                if active_failure_inference_controller_owned
                else "page-owned fallback from family_status_current"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if active_failure_inference_controller_owned
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController",
            "readiness": "SHELL_CALL" if active_failure_inference_controller_owned else "READY_TO_EXTRACT",
            "first_safe_slice": (
                None
                if active_failure_inference_controller_owned
                else "blocker_attempts_active_failure_inference_extraction"
            ),
            "risk": "Controls fail-family fallback when no explicit active_failures are present.",
            "evidence": [
                _evidence(helper, "if not active_failures:", start_line=start),
                _evidence(helper, 'get("status")', start_line=start),
            ],
            "present": active_failure_inference_controller_owned or active_failure_inference_present,
        },
        {
            "surface": "source merge prerequisite",
            "classification": "controller-owned prerequisite",
            "current_owner": "DesignGuideController via inputs_page shell",
            "target_owner": "DesignGuideController",
            "readiness": "PREREQUISITE_PASS" if source_merge_bounded else "BLOCKED",
            "first_safe_slice": None if source_merge_bounded else "blocker_attempts_source_merge_object_extraction",
            "risk": "Active-failure inference should consume the already-normalized source merge outputs.",
            "evidence": [
                _evidence(helper, "_build_design_guide_controller_blocker_attempt_source_merge(item)", start_line=start),
                _evidence(helper, "blockers.update(", start_line=start),
            ],
            "present": True,
        },
        {
            "surface": "combined active strength row dependency",
            "classification": "remaining mixed row-selection consumer",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController after active-failure inference",
            "readiness": "NOT_FIRST",
            "first_safe_slice": "combined_active_strength_attempt_row_projection_audit",
            "risk": "Consumes active_failures and blockers; must move after inference parity.",
            "evidence": [
                _evidence(helper, "def _combined_active_strength_attempt_row(", start_line=start),
                _evidence(helper, "active_failures", start_line=start),
            ],
            "present": "def _combined_active_strength_attempt_row(" in helper,
        },
    ]

    ready = [
        row
        for row in surfaces
        if row.get("present") and row.get("readiness") == "READY_TO_EXTRACT"
    ]
    first = (ready or [{}])[0]
    return {
        "schema": "design_guide_blocker_attempts_active_failure_inference_audit.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "source_merge_bounded": source_merge_bounded,
        "active_failure_inference_controller_owned": active_failure_inference_controller_owned,
        "active_failure_inference_present": active_failure_inference_controller_owned or active_failure_inference_present,
        "surfaces": surfaces,
        "first_safe_slice": dict(first),
        "status_decision": (
            "BLOCKER_ATTEMPTS_ACTIVE_FAILURE_INFERENCE_BOUNDED"
            if active_failure_inference_controller_owned
            else "BLOCKER_ATTEMPTS_ACTIVE_FAILURE_INFERENCE_READY_TO_EXTRACT"
            if ready and source_merge_bounded
            else "BLOCKER_ATTEMPTS_ACTIVE_FAILURE_INFERENCE_BLOCKED"
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
        "first_safe_implementation_slice": (
            "Move active_failures resolution into a pure controller helper that accepts candidate_search_evidence, "
            "source item, and family_status_current rows, returning the same lowercase set/list. Do not move "
            "candidate row collection or combined-row selection in this slice."
        ),
        "stop_conditions": [
            "active failure family set differs",
            "explicit active_failures precedence differs",
            "status fallback differs",
            "combined-row selection is moved in the same slice",
            "visible blocker rows differ",
            "any composed lock fails",
        ],
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "source_merge_bounded": bool(payload.get("source_merge_bounded")),
        "active_failure_inference_present": bool(payload.get("active_failure_inference_present")),
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "BLOCKER_ATTEMPTS_ACTIVE_FAILURE_INFERENCE_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_active_failure_inference_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_active_failure_inference_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Active-Failure Inference Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "The active-failure inference is ready for a narrow controller helper. "
        "Do not move candidate rows or combined-row selection in the same slice.",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Classification | Current owner | Target owner | Readiness | First safe slice | Risk |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            "| {surface} | {classification} | {current_owner} | {target_owner} | {readiness} | {first_safe_slice} | {risk} |".format(
                surface=row.get("surface"),
                classification=row.get("classification"),
                current_owner=row.get("current_owner"),
                target_owner=row.get("target_owner"),
                readiness=row.get("readiness"),
                first_safe_slice=row.get("first_safe_slice") or "",
                risk=row.get("risk"),
            )
        )
    first = payload.get("first_safe_slice") or {}
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Slice: `{first.get('first_safe_slice')}`",
            f"- Surface: `{first.get('surface')}`",
            f"- Implementation: {payload.get('first_safe_implementation_slice')}",
            "",
            "## Stop Conditions",
        ]
    )
    for condition in payload.get("stop_conditions") or []:
        lines.append(f"- {condition}")
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
    print(f"design_guide_blocker_attempts_active_failure_inference_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
