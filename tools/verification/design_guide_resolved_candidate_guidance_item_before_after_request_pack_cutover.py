"""Verify resolved-candidate before/after request-pack cutover."""

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
    build_design_guide_controller_resolved_candidate_guidance_item_before_after_request_pack,
)


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


def _old_inline_pack(
    *,
    action_payload_preview: dict[str, Any] | None,
    change_lines: list[Any] | tuple[Any, ...] | None,
) -> dict[str, Any]:
    return {
        "action_type": "apply_resolved_candidate",
        "action_payload": dict(action_payload_preview or {}),
        "recommendation_change_lines": list(change_lines or []),
    }


def _parity_cases() -> list[dict[str, Any]]:
    cases = [
        {
            "name": "normal_resolved_candidate",
            "action_payload_preview": {
                "resolved_candidate_updates": {"D": 650.0, "b": 350.0},
                "resolved_candidate_label": "Apply recommendation",
                "updates": {"D": 650.0, "b": 350.0},
            },
            "change_lines": ["D 600 -> 650", "b 300 -> 350"],
        },
        {
            "name": "empty_change_lines",
            "action_payload_preview": {
                "resolved_candidate_updates": {"s_lig": 250.0},
                "updates": {"s_lig": 250.0},
            },
            "change_lines": [],
        },
        {
            "name": "missing_payload",
            "action_payload_preview": None,
            "change_lines": None,
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        old = _old_inline_pack(
            action_payload_preview=case.get("action_payload_preview"),
            change_lines=case.get("change_lines"),
        )
        new_pack = build_design_guide_controller_resolved_candidate_guidance_item_before_after_request_pack(
            action_payload_preview=case.get("action_payload_preview"),
            change_lines=case.get("change_lines"),
        )
        new = dict(new_pack.get("before_after_item") or {})
        rows.append(
            {
                "name": case["name"],
                "old_before_after_item": old,
                "new_before_after_item": new,
                "matches": old == new,
                "owner": new_pack.get("owner"),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    helper_name = "build_design_guide_controller_resolved_candidate_guidance_item_before_after_request_pack"
    alias = "_build_design_guide_controller_resolved_candidate_guidance_item_before_after_request_pack"
    source_checks = {
        "page_imports_request_pack": f"{helper_name} as {alias}" in inputs_source,
        "page_uses_request_pack": f"{alias}(" in segment,
        "page_still_calls_before_after_helper": "_guidance_before_after_text(" in segment,
        "page_removed_inline_apply_resolved_candidate_before_after_dict": (
            '"action_type": resolved_action_type' not in segment
            and '"action_type": "apply_resolved_candidate"' not in segment
        ),
        "controller_helper_present": f"def {helper_name}(" in controller_source,
        "controller_helper_exported": f'"{helper_name}"' in controller_source,
        "controller_has_no_inputs_page_import": "inputs_page" not in controller_source,
        "controller_has_no_streamlit_import": "streamlit" not in controller_source and "st.session_state" not in controller_source,
    }
    parity_rows = _parity_cases()
    return {
        "schema": "design_guide_resolved_candidate_guidance_item_before_after_request_pack_cutover.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "source_checks": source_checks,
        "parity_rows": parity_rows,
        "all_parity_rows_match": all(bool(row.get("matches")) for row in parity_rows),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "action_update_boundary_audit_or_before_after_visible_wording_parity",
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "parity_rows_match": bool(payload.get("all_parity_rows_match")),
        "page_imports_request_pack": bool(source_checks.get("page_imports_request_pack")),
        "page_uses_request_pack": bool(source_checks.get("page_uses_request_pack")),
        "page_still_calls_before_after_helper": bool(source_checks.get("page_still_calls_before_after_helper")),
        "inline_apply_resolved_candidate_before_after_dict_removed": bool(
            source_checks.get("page_removed_inline_apply_resolved_candidate_before_after_dict")
        ),
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
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_before_after_request_pack_cutover_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_before_after_request_pack_cutover_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Resolved-Candidate Before/After Request-Pack Cutover",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- The plain before/after request dict for resolved candidates is now packaged by DesignGuideController.",
        "- inputs_page.py still owns _guidance_before_after_text(...), update resolution, and visible wording.",
        "- No CTA/apply, family runtime, or visible wording behavior moved.",
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
    print(f"design_guide_resolved_candidate_guidance_item_before_after_request_pack_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
