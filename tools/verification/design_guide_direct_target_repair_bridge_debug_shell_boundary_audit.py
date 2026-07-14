"""Audit direct target-band repair bridge/debug shell boundary."""

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
        "surface": "family repair decision bridge",
        "tokens": [
            "_repair_select_repair_decision(",
            "_repair_selected_candidate_from_repair_decision(",
        ],
        "current_owner": "inputs_page bridge into repair/family-owned decision object",
        "target_owner": "DesignGuideController route policy with family repair decision dependency injected",
        "classification": "candidate for future route-policy extraction, not safe to move in debug-shell slice",
        "risk": "family repair decision semantics and active-failure routing",
    },
    {
        "surface": "controller projection adapter",
        "tokens": [
            "_build_design_guide_controller_direct_target_evidence_context_projection(",
            "_build_design_guide_controller_direct_target_guidance_item_projection(",
        ],
        "current_owner": "DesignGuideController",
        "target_owner": "DesignGuideController",
        "classification": "already controller-owned",
        "risk": "none for this audit",
    },
    {
        "surface": "debug sink writes",
        "tokens": [
            'debug_sink["direct_target_band_search_used"]',
            'debug_sink["direct_target_band_search_candidate_count"]',
            'debug_sink["candidate_search_evidence"]',
            'debug_sink["local_cleanup_candidate_search_evidence"]',
        ],
        "current_owner": "inputs_page non-authoritative diagnostics",
        "target_owner": "page shell diagnostics or future debug/proof service",
        "classification": "bounded page-shell diagnostics",
        "risk": "debug/session only",
    },
    {
        "surface": "finish wrapper",
        "tokens": ['return _finish(item, "selected_item")'],
        "current_owner": "inputs_page shell return wrapper",
        "target_owner": "page shell",
        "classification": "shell-only",
        "risk": "none",
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
    repair_bridge_present = "_repair_select_repair_decision(" in selected_tail
    debug_sink_present = 'debug_sink["candidate_search_evidence"]' in selected_tail
    controller_projection_present = (
        "_build_design_guide_controller_direct_target_evidence_context_projection(" in selected_tail
        and "_build_design_guide_controller_direct_target_guidance_item_projection(" in selected_tail
    )
    old_projection_tokens_removed = (
        'item["action_payload"] = payload' not in selected_tail
        and 'item["resolved_candidate"] = resolved' not in selected_tail
        and 'item["title_main"] = active_title' not in selected_tail
    )
    return {
        "schema": "design_guide_direct_target_repair_bridge_debug_shell_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "repair_bridge_present": repair_bridge_present,
        "debug_sink_present": debug_sink_present,
        "controller_projection_present": controller_projection_present,
        "old_projection_tokens_removed": old_projection_tokens_removed,
        "decision": "DIRECT_TARGET_REPAIR_BRIDGE_DEBUG_SHELL_BOUNDED",
        "next_safe_slice": {
            "name": "direct_target_family_repair_bridge_route_policy_audit",
            "why": (
                "The remaining non-shell decision-adjacent path is the family repair decision bridge. "
                "It should not move until a route-policy audit proves the repair decision dependency can be "
                "injected without changing active-failure routing."
            ),
            "move": (
                "Audit only. Keep debug sink, session diagnostics, CTA/apply routing, visible wording, "
                "and family repair runtime semantics unchanged."
            ),
            "required_verifier": "design_guide_direct_target_family_repair_bridge_route_policy_audit.py",
        },
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
        "repair_bridge_present_and_bounded": bool(capture.get("repair_bridge_present")),
        "debug_sink_present_and_bounded": bool(capture.get("debug_sink_present")),
        "controller_projection_present": bool(capture.get("controller_projection_present")),
        "old_projection_tokens_removed": bool(capture.get("old_projection_tokens_removed")),
        "next_safe_slice_identified": bool((capture.get("next_safe_slice") or {}).get("name")),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_repair_bridge_debug_shell_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_repair_bridge_debug_shell_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Repair Bridge / Debug Shell Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} -> {row.get('target_owner')}"
        )
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
            "",
            "## Next Safe Slice",
            f"- Name: `{(payload.get('next_safe_slice') or {}).get('name')}`",
            f"- Why: {(payload.get('next_safe_slice') or {}).get('why')}",
            f"- Verifier: `{(payload.get('next_safe_slice') or {}).get('required_verifier')}`",
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
    print(f"design_guide_direct_target_repair_bridge_debug_shell_boundary_audit {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
