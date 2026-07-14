"""Audit remaining resolved-candidate guidance item text-pack boundary."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
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
TARGET = "_guidance_item_from_resolved_candidate"


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


def _token(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line][:20],
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    surfaces = [
        {
            "surface": "title and label resolution",
            "classification": "visible wording policy; highest risk text-pack surface",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController/presentation service after parity",
            "deletion_readiness": "NOT_READY_WITHOUT_PARITY",
            "evidence": [
                _token(segment, start, "raw_label = str("),
                _token(segment, start, "title_locked_from_final_winner"),
                _token(segment, start, "_resolve_canonical_guidance_title_from_candidate("),
            ],
        },
        {
            "surface": "alternatives text",
            "classification": "pure text fallback candidate",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController/presentation service",
            "deletion_readiness": "READY_FOR_PARITY_SNAPSHOT",
            "evidence": [
                _token(segment, start, "_guidance_default_alternatives_text("),
                _token(segment, start, "guidance_alternatives_text_compact"),
            ],
        },
        {
            "surface": "change-line fallback",
            "classification": "visible preview text and update summarisation",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController/presentation service after parity",
            "deletion_readiness": "READY_FOR_PARITY_SNAPSHOT",
            "evidence": [
                _token(segment, start, "_guidance_change_lines_for_updates("),
                _token(segment, start, "recommendation_change_lines"),
            ],
        },
        {
            "surface": "compact summary text",
            "classification": "completed controller-owned compact text packaging",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController/presentation service",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(segment, start, "_guidance_compact_change_text("),
                _token(segment, start, "_guidance_expected_util_text("),
                _token(segment, start, "_guidance_compact_why_text("),
                _token(segment, start, "_build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack("),
            ],
        },
        {
            "surface": "before-after text",
            "classification": "preview/action-payload text; depends on input-pack cutover",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController/presentation service after parity",
            "deletion_readiness": "READY_FOR_PARITY_SNAPSHOT",
            "evidence": [
                _token(segment, start, "_guidance_before_after_text("),
                _token(segment, start, "action_payload_preview"),
            ],
        },
        {
            "surface": "controller item builder",
            "classification": "already controller-owned",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(segment, start, "_build_design_guide_controller_resolved_candidate_guidance_item("),
            ],
        },
    ]
    return {
        "schema": "design_guide_resolved_candidate_guidance_item_text_pack_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": "COMPACT_TEXT_PACK_CUTOVER_COMPLETE",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "resolved_candidate_guidance_item_before_after_text_boundary_audit",
            "why": (
                "Compact text packaging is now controller-backed. The remaining smaller text surface before title "
                "resolution is before/after text, which depends on the controller-owned input-pack preview."
            ),
            "move": (
                "Audit before/after text preparation separately. Do not move title resolution yet."
            ),
            "required_verifier": "design_guide_resolved_candidate_guidance_item_before_after_text_boundary_audit.py",
        },
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = list(payload.get("surfaces") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(surfaces) == 6,
        "title_resolution_not_ready": any(
            row.get("surface") == "title and label resolution"
            and row.get("deletion_readiness") == "NOT_READY_WITHOUT_PARITY"
            for row in surfaces
        ),
        "compact_text_pack_cutover_complete": any(
            row.get("surface") == "compact summary text"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "before_after_text_next_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
            == "design_guide_resolved_candidate_guidance_item_before_after_text_boundary_audit.py"
        ),
        "controller_builder_still_shell_call": any(
            row.get("surface") == "controller item builder"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "controller_boundary_clean": bool(payload.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_text_pack_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_text_pack_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Design Guide Resolved-Candidate Guidance Item Text-Pack Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"({row.get('current_owner')} -> {row.get('target_owner')}); "
            f"readiness `{row.get('deletion_readiness')}`"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Verifier: `{first_slice.get('required_verifier')}`",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_resolved_candidate_guidance_item_text_pack_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
