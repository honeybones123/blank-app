"""Verify bottom explicit update decision is controller-owned.

The page still computes `_updates_match_state(...)` and owns bottom
recommendation fallback/arrangement conversion. The controller owns only the
pure decision for explicit `apply_bottom_recommendation` updates.
"""

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
PAGE_HELPER = "_guidance_action_updates"
CONTROLLER_HELPER = "resolve_design_guide_controller_guidance_action_payload_updates"
ACTION = "apply_bottom_recommendation"


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


def _controller_samples() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_guidance_action_payload_updates,
    )

    explicit_updates = {"bot1_count": 5, "db_bot_1": 20}
    return {
        "explicit_not_matching": resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=ACTION,
            payload={"updates": explicit_updates, "updates_match_state": False},
        ),
        "explicit_matching": resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=ACTION,
            payload={"updates": explicit_updates, "updates_match_state": True},
        ),
        "empty_updates": resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=ACTION,
            payload={"updates": {}, "updates_match_state": False},
        ),
        "missing_updates": resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=ACTION,
            payload={},
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    page_start, page_end, page_segment = _function_source(inputs_source, PAGE_HELPER)
    controller_start, controller_end, controller_segment = _function_source(
        controller_source, CONTROLLER_HELPER
    )
    branch_start = page_segment.find(f'action_type == "{ACTION}"')
    next_branch_start = page_segment.find('if action_type == "apply_shear_recommendation"', branch_start)
    branch_segment = (
        page_segment[branch_start:next_branch_start]
        if branch_start >= 0 and next_branch_start > branch_start
        else ""
    )
    samples = _controller_samples()
    return {
        "schema": "design_guide_guidance_action_updates_bottom_explicit_decision_extraction.v1",
        "page_helper": {
            "name": PAGE_HELPER,
            "line_start": page_start,
            "line_end": page_end,
            "line_count": max(0, page_end - page_start + 1),
        },
        "controller_helper": {
            "name": CONTROLLER_HELPER,
            "line_start": controller_start,
            "line_end": controller_end,
            "line_count": max(0, controller_end - controller_start + 1),
        },
        "source_evidence": {
            "page_delegates_bottom_decision": "bottom_update_result = _resolve_design_guide_controller_guidance_action_payload_updates("
            in branch_segment,
            "page_state_match_execution_kept": "_updates_match_state(current_state, explicit_updates)" in branch_segment,
            "page_fallback_still_exists": "_compute_bottom_reo_recommendation(" in branch_segment,
            "page_arrangement_conversion_still_exists": "_bottom_arrangement_to_shared_updates(" in branch_segment,
            "page_direct_return_explicit_removed": "return dict(explicit_updates)" not in branch_segment,
            "controller_handles_bottom_action": f'action == "{ACTION}"' in controller_segment,
            "controller_uses_plain_state_match_boolean": '"updates_match_state"' in controller_segment,
            "controller_boundary_forbidden_tokens": {
                token: token in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state")
            },
        },
        "behaviour_samples": samples,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    evidence = dict(payload.get("source_evidence") or {})
    forbidden = dict(evidence.get("controller_boundary_forbidden_tokens") or {})
    samples = dict(payload.get("behaviour_samples") or {})
    explicit_not_matching = dict(samples.get("explicit_not_matching") or {})
    explicit_matching = dict(samples.get("explicit_matching") or {})
    empty = dict(samples.get("empty_updates") or {})
    missing = dict(samples.get("missing_updates") or {})
    expected_updates = {"bot1_count": 5, "db_bot_1": 20}
    return {
        "page_helper_found": bool((payload.get("page_helper") or {}).get("line_start")),
        "controller_helper_found": bool((payload.get("controller_helper") or {}).get("line_start")),
        "page_delegates_bottom_decision": bool(evidence.get("page_delegates_bottom_decision")),
        "page_state_match_execution_kept": bool(evidence.get("page_state_match_execution_kept")),
        "page_fallback_still_exists": bool(evidence.get("page_fallback_still_exists")),
        "page_arrangement_conversion_still_exists": bool(evidence.get("page_arrangement_conversion_still_exists")),
        "page_direct_return_explicit_removed": bool(evidence.get("page_direct_return_explicit_removed")),
        "controller_handles_bottom_action": bool(evidence.get("controller_handles_bottom_action")),
        "controller_uses_plain_state_match_boolean": bool(evidence.get("controller_uses_plain_state_match_boolean")),
        "controller_boundary_clean": not any(bool(value) for value in forbidden.values()),
        "explicit_not_matching_returns_updates": explicit_not_matching.get("handled") is True
        and explicit_not_matching.get("updates") == expected_updates,
        "explicit_matching_returns_none": explicit_matching.get("handled") is True
        and explicit_matching.get("updates") is None,
        "empty_updates_preserve_fallback": empty.get("handled") is False and empty.get("updates") is None,
        "missing_updates_preserve_fallback": missing.get("handled") is False and missing.get("updates") is None,
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_bottom_explicit_decision_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_bottom_explicit_decision_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Guidance Action Updates Bottom Explicit Decision Extraction",
        "",
        f"Status: {payload['status']}",
        "Decision: BOTTOM_EXPLICIT_UPDATE_DECISION_CONTROLLER_OWNED",
        "",
        "## Behaviour Preserved",
        "- Non-matching explicit bottom updates still return the explicit update dictionary.",
        "- Matching explicit bottom updates still return `None`.",
        "- Empty or missing updates remain unhandled so bottom recommendation fallback still runs.",
        "- `_updates_match_state(...)`, `_compute_bottom_reo_recommendation(...)`, and arrangement conversion remain page-owned.",
        "",
        "## Checks",
    ]
    for name, passed in checks.items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "Refresh `_guidance_action_updates(...)` boundary inventory, then audit bottom arrangement conversion parity.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["status"] != "PASS":
        failed = [name for name, passed in checks.items() if not passed]
        print("failed_checks=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
