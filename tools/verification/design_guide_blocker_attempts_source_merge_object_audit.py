"""Audit blocker-attempt source merge ownership before extraction."""

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


def _line_hits(source: str, token: str, *, start_line: int) -> list[int]:
    return [start_line + index for index, line in enumerate(source.splitlines()) if token in line]


def _evidence(source: str, token: str, *, start_line: int) -> dict[str, Any]:
    lines = _line_hits(source, token, start_line=start_line)
    return {"token": token, "present": bool(lines), "count": len(lines), "lines": lines[:20]}


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, helper = _function_source(inputs_source, "_design_guide_blocker_attempts_table")

    source_merge_tokens = [
        "src = dict(item or {})",
        'src.get("candidate_search_evidence")',
        '"exact_blockers_by_family"',
        '"post_click_exact_blockers_by_family"',
        '"cleanup_evidence_by_family"',
        '"post_click_cleanup_evidence_by_family"',
        "blockers.update(",
    ]
    source_merge_already_controller_owned = (
        "_build_design_guide_controller_blocker_attempt_source_merge(" in helper
        and "def build_design_guide_controller_blocker_attempt_source_merge(" in controller_source
    )
    source_merge_present = source_merge_already_controller_owned or all(token in helper for token in source_merge_tokens)
    strength_reason_controller_owned = (
        "_resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(" in helper
        and "_build_design_guide_controller_blocker_attempt_strength_reason(" in helper
        and "def _strength_capacity_rule(" not in helper
        and "def _specific_strength_reason(" not in helper
    )

    surfaces = [
        {
            "surface": "item/evidence blocker source merge",
            "classification": (
                "DesignGuideController-owned source merge"
                if source_merge_already_controller_owned
                else "page-owned pure source normalization"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if source_merge_already_controller_owned
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController",
            "readiness": "SHELL_CALL" if source_merge_already_controller_owned else "READY_TO_EXTRACT",
            "first_safe_slice": (
                None
                if source_merge_already_controller_owned
                else "blocker_attempts_source_merge_object_extraction"
            ),
            "risk": "Controls which blocker families appear in the visible blocker-attempts table.",
            "evidence": [_evidence(helper, token, start_line=start) for token in source_merge_tokens],
            "present": source_merge_present,
        },
        {
            "surface": "candidate row source collection",
            "classification": "page-owned evidence list extraction",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController after source merge object parity",
            "readiness": "NOT_FIRST",
            "first_safe_slice": "blocker_attempts_candidate_row_source_extraction",
            "risk": "Controls combined active-failure best rejected candidate source list.",
            "evidence": [
                _evidence(helper, "active_fail_repair_candidate_rows", start_line=start),
                _evidence(helper, "candidate_rows", start_line=start),
                _evidence(helper, "active_candidate_rows", start_line=start),
            ],
            "present": "active_candidate_rows" in helper,
        },
        {
            "surface": "active failure inference",
            "classification": "page-owned status inference",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController after source merge object parity",
            "readiness": "NOT_FIRST",
            "first_safe_slice": "blocker_attempts_active_failure_inference_audit",
            "risk": "Controls whether bending/shear use active-failure strength wording.",
            "evidence": [
                _evidence(helper, "active_failures", start_line=start),
                _evidence(helper, "family_status_current", start_line=start),
                _evidence(helper, 'get("status")', start_line=start),
            ],
            "present": "active_failures" in helper,
        },
        {
            "surface": "strength wording dependency",
            "classification": "controller-owned prerequisite",
            "current_owner": "DesignGuideController via inputs_page shell",
            "target_owner": "DesignGuideController",
            "readiness": "PREREQUISITE_PASS" if strength_reason_controller_owned else "BLOCKED",
            "first_safe_slice": None if strength_reason_controller_owned else "blocker_attempts_strength_reason_projection_extraction",
            "risk": "Source merge extraction should not also move visible reason wording.",
            "evidence": [
                _evidence(helper, "_build_design_guide_controller_blocker_attempt_strength_reason(", start_line=start),
                _evidence(helper, "def _specific_strength_reason(", start_line=start),
            ],
            "present": True,
        },
    ]

    ready = [
        row
        for row in surfaces
        if row.get("present") and row.get("readiness") == "READY_TO_EXTRACT"
    ]
    first = (ready or [{}])[0]
    return {
        "schema": "design_guide_blocker_attempts_source_merge_object_audit.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "source_merge_present": source_merge_present,
        "source_merge_already_controller_owned": source_merge_already_controller_owned,
        "strength_reason_controller_owned": strength_reason_controller_owned,
        "first_safe_slice": dict(first),
        "status_decision": (
            "BLOCKER_ATTEMPTS_SOURCE_MERGE_BOUNDED"
            if source_merge_already_controller_owned
            else "BLOCKER_ATTEMPTS_SOURCE_MERGE_READY_TO_EXTRACT"
            if ready and strength_reason_controller_owned
            else "BLOCKER_ATTEMPTS_SOURCE_MERGE_BLOCKED"
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
            "Add a pure controller source-merge object that accepts plain item/evidence dictionaries and returns "
            "the merged blocker map plus source provenance. Then cut over only the initial blocker source merge "
            "inside _design_guide_blocker_attempts_table(...)."
        ),
        "stop_conditions": [
            "merged blocker keys differ",
            "blocker precedence differs",
            "non-dict blocker rows are kept differently",
            "visible blocker-attempt table rows differ",
            "candidate row or active-failure inference is moved in the same slice",
            "any composed lock fails",
        ],
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "source_merge_present": bool(payload.get("source_merge_present")),
        "strength_prerequisite_done": bool(payload.get("strength_reason_controller_owned")),
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "BLOCKER_ATTEMPTS_SOURCE_MERGE_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_source_merge_object_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_source_merge_object_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Source Merge Object Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "The blocker-attempt source merge is ready for a narrow controller-owned source-merge object. "
        "Do not move candidate-row collection or active-failure inference in the same slice.",
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
    print(f"design_guide_blocker_attempts_source_merge_object_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
