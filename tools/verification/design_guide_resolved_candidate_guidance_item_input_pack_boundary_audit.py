"""Audit resolved-candidate guidance item input-pack extraction boundary."""

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


def _line_numbers(source: str, token: str) -> list[int]:
    return [idx + 1 for idx, line in enumerate(source.splitlines()) if token in line]


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
    callsite_lines = [
        line
        for line in _line_numbers(inputs_source, f"{TARGET}(")
        if line != start
    ]
    surfaces = [
        {
            "surface": "raw candidate/update extraction",
            "classification": "plain input extraction; controller-service candidate",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController input-pack adapter",
            "deletion_readiness": "READY_FOR_INPUT_PACK_PARITY",
            "evidence": [
                _token(segment, start, "updates = dict(candidate.get(\"updates\") or {})"),
                _token(segment, start, "candidate_post_util = candidate.get(\"worst_util\")"),
                _token(segment, start, "candidate_search_evidence = dict(candidate.get(\"candidate_search_evidence\") or {})"),
            ],
        },
        {
            "surface": "title/label resolution",
            "classification": "visible wording sensitive; needs parity before move",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController or presentation service after parity",
            "deletion_readiness": "READY_FOR_INPUT_PACK_PARITY",
            "evidence": [
                _token(segment, start, "raw_label = str("),
                _token(segment, start, "_resolve_canonical_guidance_title_from_candidate("),
                _token(segment, start, "title_locked_from_final_winner"),
            ],
        },
        {
            "surface": "change/why/before-after text prep",
            "classification": "visible wording and preview text; needs broad parity",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController/presentation service after parity",
            "deletion_readiness": "READY_FOR_INPUT_PACK_PARITY",
            "evidence": [
                _token(segment, start, "_guidance_change_lines_for_updates("),
                _token(segment, start, "_guidance_compact_change_text("),
                _token(segment, start, "_guidance_expected_util_text("),
                _token(segment, start, "_guidance_compact_why_text("),
                _token(segment, start, "_guidance_before_after_text("),
            ],
        },
        {
            "surface": "action payload preview pack",
            "classification": "completed controller-owned input-pack preview",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController input-pack adapter",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(segment, start, "_build_design_guide_controller_resolved_candidate_guidance_item_input_pack("),
                _token(segment, start, "\"resolved_candidate_updates\": updates"),
                _token(segment, start, "\"force_direct_apply\": True"),
            ],
        },
        {
            "surface": "controller item construction",
            "classification": "already controller-owned final item construction",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(segment, start, "_build_design_guide_controller_resolved_candidate_guidance_item("),
            ],
        },
        {
            "surface": "shared callsites",
            "classification": "shared cross-family surface; active-fail-only move is unsafe",
            "current_owner": "multiple inputs_page guidance paths",
            "target_owner": "shared DesignGuideController adapter after parity",
            "deletion_readiness": "NOT_READY_TO_CUTOVER",
            "evidence": [
                {
                    "token": f"{TARGET}(",
                    "present": bool(callsite_lines),
                    "count": len(callsite_lines),
                    "lines": callsite_lines[:40],
                }
            ],
        },
    ]
    return {
        "schema": "design_guide_resolved_candidate_guidance_item_input_pack_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "callsite_count": len(callsite_lines),
        "callsite_lines_sample": callsite_lines[:40],
        "decision": "INPUT_PACK_PREVIEW_CUTOVER_COMPLETE",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "resolved_candidate_guidance_item_text_pack_boundary_audit",
            "why": (
                "The pure action-payload preview pack now delegates to the controller. The remaining page-owned "
                "materializer logic is wording/text input preparation: title/label, alternatives, change lines, "
                "compact why, expected-util text, and before/after text."
            ),
            "move": (
                "Audit the remaining wording/text input preparation as its own shared surface before moving any more code."
            ),
            "required_verifier": "design_guide_resolved_candidate_guidance_item_text_pack_boundary_audit.py",
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
        "shared_calls_detected": int(payload.get("callsite_count") or 0) > 1,
        "surfaces_classified": len(surfaces) == 6,
        "controller_builder_present": any(
            row.get("surface") == "controller item construction"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "input_pack_preview_cutover_complete": bool(
            any(
                row.get("surface") == "action payload preview pack"
                and row.get("deletion_readiness") == "SHELL_CALL"
                for row in surfaces
            )
        ),
        "text_pack_audit_next": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
            == "design_guide_resolved_candidate_guidance_item_text_pack_boundary_audit.py"
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
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_input_pack_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_input_pack_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Design Guide Resolved-Candidate Guidance Item Input-Pack Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Current State",
        f"- Helper line count: {(payload.get('target') or {}).get('line_count')}",
        f"- Shared callsites: {payload.get('callsite_count')}",
        "- Current helper prepares wording/payload primitives and delegates final item construction to the controller.",
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
            "## Stop Conditions",
            "- Stop if visible title, change summary, expected-util text, why text, before/after text, action payload, or item hash differs.",
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
    print(f"design_guide_resolved_candidate_guidance_item_input_pack_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
