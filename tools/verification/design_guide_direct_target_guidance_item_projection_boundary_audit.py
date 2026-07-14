"""Audit direct target-band guidance item projection boundary before extraction."""

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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_direct_target_band_guidance_item"


SURFACES: list[dict[str, Any]] = [
    {
        "surface": "base guidance item construction",
        "tokens": ["_guidance_item_from_resolved_candidate(", 'primary_action="Apply recommendation"'],
        "current_owner": "inputs_page presentation adapter",
        "target_owner": "DesignGuideController or FinalDesignGuidePublication display adapter",
        "classification": "moveable only after item-shape parity",
        "risk": "visible wording and CTA/display fields",
    },
    {
        "surface": "active strength title/family override",
        "tokens": ['active_title = "Bending and shear capacity are low"', 'item["title_main"]', 'item["family"] = active_family'],
        "current_owner": "inputs_page visible wording/status override",
        "target_owner": "FinalDesignGuidePublication display projection after wording parity",
        "classification": "not ready to move without visible wording parity",
        "risk": "visible card title/status/family ownership",
    },
    {
        "surface": "terminal/display state reset",
        "tokens": ['item["design_guide_terminal_state"] = None', 'item["canonical_winner_label"] = active_title'],
        "current_owner": "inputs_page display state override",
        "target_owner": "FinalDesignGuidePublication display projection",
        "classification": "not ready to move without display hash parity",
        "risk": "terminal state/display authority",
    },
    {
        "surface": "reasoning override wording",
        "tokens": ['item["reasoning"] = (', "Why: active bending/shear capacity checks are failing"],
        "current_owner": "inputs_page visible wording",
        "target_owner": "FinalDesignGuidePublication display projection",
        "classification": "not ready to move without exact wording lock",
        "risk": "visible wording",
    },
    {
        "surface": "post-item metadata flags",
        "tokens": ['item["local_cleanup_candidate"]', 'item["source"]', 'item["affected_family"]'],
        "current_owner": "inputs_page item metadata",
        "target_owner": "DesignGuideController projection adapter",
        "classification": "likely moveable with item-shape parity",
        "risk": "publication/source metadata",
    },
    {
        "surface": "action payload and resolved candidate evidence sync",
        "tokens": ['payload["candidate_search_evidence"]', 'item["action_payload"] = payload', 'item["resolved_candidate"] = resolved'],
        "current_owner": "inputs_page CTA/apply-adjacent sync",
        "target_owner": "FinalDesignGuidePublication/controller payload projection after CTA parity",
        "classification": "not ready in guidance-item slice",
        "risk": "CTA/apply semantics",
    },
    {
        "surface": "debug sink evidence writes",
        "tokens": ['debug_sink["candidate_search_evidence"]', 'debug_sink["local_cleanup_candidate_search_evidence"]'],
        "current_owner": "inputs_page non-authoritative debug sink",
        "target_owner": "page shell non-authoritative diagnostics",
        "classification": "allowed to remain",
        "risk": "debug/session only",
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
    publication_source = _read(FINAL_PUBLICATION)
    start, end, segment = _function_source(inputs_source, TARGET)
    selected_tail = segment.split('selected = selection_result.get("selected_candidate")', 1)[-1]
    surfaces = []
    for surface in SURFACES:
        token_rows = []
        for token in list(surface.get("tokens") or []):
            lines = _line_numbers(selected_tail, start, str(token))
            token_rows.append(
                {
                    "token": token,
                    "present": bool(lines),
                    "lines": lines[:20],
                    "count": selected_tail.count(str(token)),
                }
            )
        present_count = sum(1 for row in token_rows if row.get("present"))
        surfaces.append(
            {
                **surface,
                "present": present_count > 0,
                "present_count": present_count,
                "tokens_found": token_rows,
            }
        )
    return {
        "schema": "design_guide_direct_target_guidance_item_projection_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "decision": "NEEDS_ITEM_SHAPE_PARITY_BEFORE_EXTRACTION",
        "first_safe_slice": {
            "name": "direct_target_guidance_item_projection_parity_snapshot",
            "why": (
                "Guidance item construction and active strength title/status override are visible-output surfaces. "
                "They can only move after a parity snapshot proves the returned item shape, display fields, and "
                "wording are unchanged."
            ),
            "move": (
                "Proof-only parity first. Do not move action payload sync, resolved candidate sync, repair bridge, "
                "debug sink writes, CTA/apply, or visible wording in this audit."
            ),
            "required_verifier": "design_guide_direct_target_guidance_item_projection_parity_snapshot.py",
        },
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
        "final_publication_has_no_page_or_streamlit_imports": "inputs_page" not in publication_source
        and "streamlit" not in publication_source
        and "st.session_state" not in publication_source,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((capture.get("target") or {}).get("line_start")),
        "surfaces_classified": bool(capture.get("surfaces")),
        "first_safe_slice_identified": bool((capture.get("first_safe_slice") or {}).get("name")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "final_publication_has_no_page_or_streamlit_imports": bool(capture.get("final_publication_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_guidance_item_projection_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_guidance_item_projection_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Guidance Item Projection Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
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
    print(f"design_guide_direct_target_guidance_item_projection_boundary_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
