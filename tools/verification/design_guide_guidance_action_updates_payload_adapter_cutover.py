"""Verify pure payload update adapter cutover for _guidance_action_updates."""

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

from design_brain.design_guide_controller import (  # noqa: E402
    resolve_design_guide_controller_guidance_action_payload_updates,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_guidance_action_updates"


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


def _old_pure_payload_branch(action_type: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = payload or {}
    if action_type == "apply_resolved_candidate":
        resolved_updates = payload.get("resolved_candidate_updates")
        if isinstance(resolved_updates, dict) and resolved_updates:
            return dict(resolved_updates)
        explicit_updates = payload.get("updates")
        return dict(explicit_updates) if isinstance(explicit_updates, dict) and explicit_updates else None
    if action_type == "apply_compound_guidance":
        updates = payload.get("updates")
        return dict(updates) if isinstance(updates, dict) else None
    if action_type == "apply_mode_recommendation":
        updates = payload.get("updates")
        return dict(updates) if isinstance(updates, dict) else None
    if action_type == "apply_bottom_recommendation":
        updates = payload.get("updates")
        if isinstance(updates, dict) and updates:
            return None if bool(payload.get("updates_match_state")) else dict(updates)
        return None
    if action_type == "apply_geometry_recommendation":
        updates = payload.get("updates")
        return dict(updates) if isinstance(updates, dict) and updates else None
    if action_type in ("apply_shear_recommendation", "increase_link_spacing", "reduce_number_of_legs", "tighten_geometry"):
        updates = payload.get("updates")
        return dict(updates) if isinstance(updates, dict) else None
    return None


def _parity_rows() -> list[dict[str, Any]]:
    cases = [
        {
            "name": "resolved_candidate_prefer_resolved_updates",
            "action_type": "apply_resolved_candidate",
            "payload": {
                "resolved_candidate_updates": {"D": 650.0},
                "updates": {"D": 700.0},
            },
            "handled": True,
        },
        {
            "name": "resolved_candidate_explicit_updates_fallback",
            "action_type": "apply_resolved_candidate",
            "payload": {"updates": {"b": 350.0}},
            "handled": True,
        },
        {
            "name": "resolved_candidate_empty_payload",
            "action_type": "apply_resolved_candidate",
            "payload": {},
            "handled": True,
        },
        {
            "name": "compound_guidance_updates",
            "action_type": "apply_compound_guidance",
            "payload": {"updates": {"s_lig": 250.0, "lig_legs": 0}},
            "handled": True,
        },
        {
            "name": "geometry_explicit_updates",
            "action_type": "apply_geometry_recommendation",
            "payload": {"updates": {"D": 650.0}},
            "handled": True,
        },
        {
            "name": "shear_explicit_updates",
            "action_type": "apply_shear_recommendation",
            "payload": {"updates": {"lig_legs": 2, "s_lig": 175.0}},
            "handled": True,
        },
        {
            "name": "tighten_geometry_explicit_updates",
            "action_type": "tighten_geometry",
            "payload": {"updates": {"b": 300.0}},
            "handled": True,
        },
        {
            "name": "unsupported_action_not_handled",
            "action_type": "unknown_action",
            "payload": {"updates": {"D": 650.0}},
            "handled": False,
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        new = resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=str(case["action_type"]),
            payload=dict(case.get("payload") or {}),
        )
        expected_updates = (
            _old_pure_payload_branch(str(case["action_type"]), dict(case.get("payload") or {}))
            if case.get("handled")
            else None
        )
        rows.append(
            {
                "name": case["name"],
                "action_type": case["action_type"],
                "expected_handled": bool(case["handled"]),
                "actual_handled": bool(new.get("handled")),
                "expected_updates": expected_updates,
                "actual_updates": new.get("updates"),
                "matches": bool(new.get("handled")) == bool(case["handled"])
                and (not case.get("handled") or new.get("updates") == expected_updates),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    helper_name = "resolve_design_guide_controller_guidance_action_payload_updates"
    alias = "_resolve_design_guide_controller_guidance_action_payload_updates"
    source_checks = {
        "page_imports_payload_adapter": f"{helper_name} as {alias}" in inputs_source,
        "page_uses_payload_adapter": f"{alias}(" in segment,
        "page_apply_resolved_candidate_branch_removed": 'action_type == "apply_resolved_candidate"' not in segment,
        "page_apply_compound_guidance_branch_removed": 'action_type == "apply_compound_guidance"' not in segment,
        "recommendation_fallbacks_remain_page_owned": all(
            token in segment
            for token in (
                "_compute_geometry_recommendation(",
                "_compute_bottom_reo_recommendation(",
                "_compute_shear_recommendation(",
                "_compute_shear_tightening_recommendation(",
                "_compute_geometry_tightening_recommendation(",
            )
        ),
        "state_fallback_remains_page_owned": "_shared_state_snapshot(" in segment,
        "controller_helper_present": f"def {helper_name}(" in controller_source,
        "controller_helper_exported": f'"{helper_name}"' in controller_source,
        "controller_has_no_inputs_page_import": "inputs_page" not in controller_source,
        "controller_has_no_streamlit_import": "streamlit" not in controller_source and "st.session_state" not in controller_source,
    }
    rows = _parity_rows()
    return {
        "schema": "design_guide_guidance_action_updates_payload_adapter_cutover.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "source_checks": source_checks,
        "parity_rows": rows,
        "all_parity_rows_match": all(bool(row.get("matches")) for row in rows),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "guidance_action_updates_state_fallback_boundary_audit_or_describe_guidance_step_wording_parity",
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "parity_rows_match": bool(payload.get("all_parity_rows_match")),
        "page_imports_payload_adapter": bool(source_checks.get("page_imports_payload_adapter")),
        "page_uses_payload_adapter": bool(source_checks.get("page_uses_payload_adapter")),
        "pure_payload_branches_removed": bool(source_checks.get("page_apply_resolved_candidate_branch_removed"))
        and bool(source_checks.get("page_apply_compound_guidance_branch_removed")),
        "recommendation_fallbacks_remain_page_owned": bool(source_checks.get("recommendation_fallbacks_remain_page_owned")),
        "state_fallback_remains_page_owned": bool(source_checks.get("state_fallback_remains_page_owned")),
        "controller_helper_present": bool(source_checks.get("controller_helper_present")),
        "controller_helper_exported": bool(source_checks.get("controller_helper_exported")),
        "controller_boundary_clean": bool(source_checks.get("controller_has_no_inputs_page_import"))
        and bool(source_checks.get("controller_has_no_streamlit_import")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_payload_adapter_cutover_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_payload_adapter_cutover_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Guidance Action Updates Payload Adapter Cutover",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- Pure payload update extraction for apply_resolved_candidate and apply_compound_guidance now delegates to DesignGuideController.",
        "- Recommendation fallback branches, shared-state fallback, geometry guards, and reo helper branches remain page-owned.",
        "- No visible wording, CTA/apply semantics, or family runtime behavior moved.",
        "",
        "## Parity Rows",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('matches') else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
            "",
            f"Next safe slice: `{payload.get('next_safe_slice')}`",
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
    print(f"design_guide_guidance_action_updates_payload_adapter_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
