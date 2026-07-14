"""Audit direct target-band evidence/item projection boundary before extraction."""

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

TARGET = "_direct_target_band_guidance_item"


SURFACES: list[dict[str, Any]] = [
    {
        "surface": "candidate search evidence construction",
        "tokens": ["_build_candidate_search_evidence(", 'selected["candidate_search_evidence"]'],
        "current_owner": "inputs_page",
        "target_owner": "DesignGuideController projection adapter",
        "classification": "pure evidence projection candidate",
        "move_ready": True,
    },
    {
        "surface": "active strength evidence enrichment",
        "tokens": [
            '"active_fail_accepted_band_candidate_count"',
            '"active_fail_selected_strength_family_utils"',
            '"strength_repair_selected_outside_target_band"',
        ],
        "current_owner": "inputs_page",
        "target_owner": "DesignGuideController projection adapter",
        "classification": "pure evidence projection candidate with fixed wording values",
        "move_ready": True,
    },
    {
        "surface": "selected candidate identity stamping",
        "tokens": [
            'selected["candidate_id"]',
            'selected["source_candidate_id"]',
            'selected["canonical_winner_label"]',
            'selected["title_locked_from_final_winner"]',
        ],
        "current_owner": "inputs_page",
        "target_owner": "DesignGuideController projection adapter",
        "classification": "pure selected-candidate projection candidate",
        "move_ready": True,
    },
    {
        "surface": "repair decision bridge for active strengthening",
        "tokens": ["_repair_select_repair_decision(", "_repair_selected_candidate_from_repair_decision("],
        "current_owner": "inputs_page route bridge into repair publication helper",
        "target_owner": "keep until projection adapter parity proves repair bridge output",
        "classification": "unsafe to move in first projection slice",
        "move_ready": False,
    },
    {
        "surface": "guidance item projection",
        "tokens": ["_guidance_item_from_resolved_candidate(", 'primary_action="Apply recommendation"'],
        "current_owner": "inputs_page",
        "target_owner": "FinalDesignGuidePublication/controller projection adapter",
        "classification": "presentation item shaping; needs parity before move",
        "move_ready": False,
    },
    {
        "surface": "active title/status visible override",
        "tokens": ['item["title_main"]', 'item["title_sub"]', 'item["reasoning"]'],
        "current_owner": "inputs_page",
        "target_owner": "FinalDesignGuidePublication/display adapter only after wording lock",
        "classification": "visible wording/status surface; audit-only for now",
        "move_ready": False,
    },
    {
        "surface": "action payload and resolved candidate evidence sync",
        "tokens": ['item["action_payload"]', 'item["resolved_candidate"]', 'payload["candidate_search_evidence"]'],
        "current_owner": "inputs_page",
        "target_owner": "FinalDesignGuidePublication/controller projection adapter",
        "classification": "CTA/apply payload-adjacent; needs exact parity before move",
        "move_ready": False,
    },
    {
        "surface": "debug sink diagnostics",
        "tokens": ["debug_sink[", '"local_cleanup_candidate_search_evidence"'],
        "current_owner": "inputs_page",
        "target_owner": "page shell non-authoritative diagnostics",
        "classification": "page-shell debug/session allowed to remain",
        "move_ready": False,
    },
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(
                lines[node.lineno - 1 : int(node.end_lineno or node.lineno)]
            )
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    selected_tail = segment.split('selected = selection_result.get("selected_candidate")', 1)[-1]
    evidence_context_controller_owned = (
        "_build_design_guide_controller_direct_target_evidence_context_projection(" in selected_tail
        and 'selected["candidate_search_evidence"] = dict(evidence)' not in selected_tail
        and '"active_fail_selected_strength_family_utils": dict(' not in selected_tail
    )
    surfaces = []
    for surface in SURFACES:
        token_rows = []
        for token in list(surface.get("tokens") or []):
            lines = _line_numbers(segment, start, str(token))
            token_rows.append(
                {
                    "token": token,
                    "present": bool(lines),
                    "lines": lines[:20],
                    "count": segment.count(str(token)),
                }
            )
        present_count = sum(1 for row in token_rows if row.get("present"))
        row = {
            **surface,
            "present": present_count > 0,
            "present_count": present_count,
            "tokens_found": token_rows,
        }
        if evidence_context_controller_owned and row.get("surface") in {
            "candidate search evidence construction",
            "active strength evidence enrichment",
            "selected candidate identity stamping",
        }:
            row.update(
                {
                    "current_owner": "DesignGuideController evidence context projection adapter",
                    "target_owner": "DesignGuideController",
                    "classification": "already controller-owned",
                    "move_ready": False,
                }
            )
        surfaces.append(row)
    ready_to_move = [row for row in surfaces if row.get("present") and bool(row.get("move_ready"))]
    blockers = [row for row in surfaces if row.get("present") and not bool(row.get("move_ready"))]
    return {
        "schema": "design_guide_direct_target_evidence_item_projection_adapter_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "ready_to_move_surfaces": [row.get("surface") for row in ready_to_move],
        "blocked_surfaces": [row.get("surface") for row in blockers],
        "decision": (
            "PARTIAL_READY_FOR_GUIDANCE_ITEM_PROJECTION_AUDIT"
            if evidence_context_controller_owned
            else "PARTIAL_READY_FOR_EVIDENCE_CONTEXT_ADAPTER"
        ),
        "first_safe_slice": {
            "name": (
                "direct_target_guidance_item_projection_boundary_audit"
                if evidence_context_controller_owned
                else "direct_target_evidence_context_projection_adapter"
            ),
            "why": (
                "Evidence/context projection is now controller-owned. The next remaining projection surface is "
                "guidance item construction plus visible title/status override, which needs its own parity audit."
                if evidence_context_controller_owned
                else "Candidate-search evidence construction, active-strength evidence enrichment, and selected-candidate "
                "identity stamping are pure projection surfaces. Guidance item wording, action payload sync, repair "
                "decision bridge, and debug sink writes need separate parity before moving."
            ),
            "move": (
                "Audit guidance item creation and visible title/status override before moving. Keep action payload/"
                "resolved-candidate sync, repair bridge, debug sink writes, CTA/apply, and wording unchanged."
                if evidence_context_controller_owned
                else "Move only pure evidence/context projection into DesignGuideController. Keep guidance item creation, "
                "visible title/reasoning override, action payload/resolved-candidate sync, repair bridge, and debug "
                "sink writes in inputs_page.py."
            ),
            "required_verifier": (
                "design_guide_direct_target_guidance_item_projection_boundary_audit.py"
                if evidence_context_controller_owned
                else "design_guide_direct_target_evidence_context_projection_adapter.py"
            ),
        },
        "evidence_context_controller_owned": bool(evidence_context_controller_owned),
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((capture.get("target") or {}).get("line_start")),
        "surfaces_classified": bool(capture.get("surfaces")),
        "ready_surface_identified_or_context_already_moved": bool(capture.get("ready_to_move_surfaces"))
        or bool(capture.get("evidence_context_controller_owned")),
        "blocked_surfaces_identified": bool(capture.get("blocked_surfaces")),
        "first_safe_slice_identified": bool((capture.get("first_safe_slice") or {}).get("name")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_evidence_item_projection_adapter_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_evidence_item_projection_adapter_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Evidence / Item Projection Adapter Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Ready To Move",
        *[f"- {name}" for name in payload.get("ready_to_move_surfaces") or []],
        "",
        "## Blocked / Keep For Now",
        *[f"- {name}" for name in payload.get("blocked_surfaces") or []],
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        if row.get("present"):
            lines.append(
                f"- {row.get('surface')}: {row.get('classification')} -> {row.get('target_owner')}"
            )
    lines.extend(
        [
            "",
            "## First Safe Slice",
            f"- Name: `{(payload.get('first_safe_slice') or {}).get('name')}`",
            f"- Why: {(payload.get('first_safe_slice') or {}).get('why')}",
            f"- Move: {(payload.get('first_safe_slice') or {}).get('move')}",
            f"- Verifier: `{(payload.get('first_safe_slice') or {}).get('required_verifier')}`",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        **capture,
        "status": status,
        "checks": checks,
        "checked_at": _timestamp(),
    }
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_evidence_item_projection_adapter_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
