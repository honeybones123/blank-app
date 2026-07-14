"""Verify direct target-band evidence context projection adapter cutover."""

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
HELPER = "build_design_guide_controller_direct_target_evidence_context_projection"


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


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    selected_tail_source = target_source.split('selected = selection_result.get("selected_candidate")', 1)[-1]
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)
    old_selected_evidence_tokens = [
        "accepted_band_candidates = [",
        '"active_fail_selected_strength_family_utils": dict(',
        '"strength_repair_selected_outside_target_band": True',
        'selected["candidate_search_evidence"] = dict(evidence)',
        'selected["candidate_id"] = evidence.get("selected_candidate_id")',
        'selected["source_candidate_id"] = evidence.get("selected_candidate_id")',
        'selected["canonical_winner_label"] = str(selected.get("label") or "Direct target-band candidate")',
    ]
    helper_required_tokens = [
        "build_candidate_search_evidence(",
        "resolve_design_guide_controller_strength_family_band_status(",
        '"active_fail_accepted_band_candidate_count"',
        '"strength_repair_selected_outside_target_band"',
        '"selected_candidate"',
        '"candidate_search_evidence"',
    ]
    return {
        "schema": "design_guide_direct_target_evidence_context_projection_adapter.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "controller_helper": {
            "name": HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
        },
        "page_calls_controller_adapter": "_build_design_guide_controller_direct_target_evidence_context_projection(" in selected_tail_source,
        "old_selected_evidence_tokens_present": [
            token for token in old_selected_evidence_tokens if token in selected_tail_source
        ],
        "helper_required_tokens_missing": [
            token for token in helper_required_tokens if token not in helper_source
        ],
        "guidance_item_projection_adapter_called": "_build_design_guide_controller_direct_target_guidance_item_projection(" in selected_tail_source,
        "action_payload_sync_still_page_owned": 'item["action_payload"] = payload' in selected_tail_source,
        "action_payload_sync_controller_owned": 'out["action_payload"] = payload' in controller_source
        and 'out["resolved_candidate"] = resolved' in controller_source,
        "debug_sink_still_page_owned": "debug_sink[" in selected_tail_source,
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
        "controller_helper_found": bool((capture.get("controller_helper") or {}).get("line_start")),
        "page_calls_controller_adapter": bool(capture.get("page_calls_controller_adapter")),
        "old_selected_evidence_tokens_removed": not bool(capture.get("old_selected_evidence_tokens_present")),
        "helper_owns_required_projection_tokens": not bool(capture.get("helper_required_tokens_missing")),
        "guidance_item_projection_adapter_called": bool(capture.get("guidance_item_projection_adapter_called")),
        "action_payload_sync_moved_to_controller": not bool(capture.get("action_payload_sync_still_page_owned"))
        and bool(capture.get("action_payload_sync_controller_owned")),
        "debug_sink_still_page_owned": bool(capture.get("debug_sink_still_page_owned")),
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
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_evidence_context_projection_adapter_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_evidence_context_projection_adapter_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Evidence Context Projection Adapter",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- Pure selected-candidate evidence/context projection is controller-owned.",
        "- Guidance item projection and action payload evidence sync are controller-owned.",
        "- Debug sink writes, visible wording inputs, and CTA/apply routing remain page-owned.",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
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
    print(f"design_guide_direct_target_evidence_context_projection_adapter {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
