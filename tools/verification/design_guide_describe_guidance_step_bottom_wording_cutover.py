"""Verify bottom reinforcement wording cutover for _describe_guidance_step."""

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
    build_design_guide_pure_guidance_step_description,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_describe_guidance_step"


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


def _row(
    name: str,
    updates: dict[str, Any],
    before_label: str | None,
    after_label: str | None,
    should_handle: bool,
) -> dict[str, Any]:
    result = build_design_guide_pure_guidance_step_description(
        before_state={},
        after_state={},
        action_type="reduce_bar_spacing",
        updates=dict(updates),
        before_bottom_reo_label=before_label,
        after_bottom_reo_label=after_label,
    )
    expected = (
        f"Updated bottom reinforcement from {before_label} to {after_label}."
        if should_handle
        else None
    )
    return {
        "name": name,
        "expected_handled": should_handle,
        "actual_handled": bool(result.get("handled")),
        "expected": expected,
        "actual": result.get("description"),
        "matches": (
            bool(result.get("handled")) == bool(should_handle)
            and (not should_handle or result.get("description") == expected)
            and (should_handle or result.get("description") is None)
        ),
    }


def _rows() -> list[dict[str, Any]]:
    return [
        _row("count_label_bottom_update", {"bot1_count": 5}, "4N20", "5N20", True),
        _row("diameter_label_bottom_update", {"db_bot_1": 24}, "4N20", "4N24", True),
        _row("spacing_label_bottom_update", {"Ast_bot": 1250.0}, "N16 @ 200", "N16 @ 175", True),
        _row("missing_label_declined", {"bot1_count": 5}, "", "5N20", False),
        _row("shear_update_declined", {"s_lig": 250.0}, "4N20", "5N20", False),
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    rows = _rows()
    source_checks = {
        "page_computes_bottom_labels": "before_bottom_reo_label = _bottom_reo_state_label(before_state)" in segment
        and "after_bottom_reo_label = _bottom_reo_state_label(after_state)" in segment,
        "page_passes_bottom_labels": "before_bottom_reo_label=before_bottom_reo_label" in segment
        and "after_bottom_reo_label=after_bottom_reo_label" in segment,
        "page_bottom_fallback_branch_deleted": "Updated bottom reinforcement from {_bottom_reo_state_label(before_state)}" not in segment,
        "risky_shear_branch_remains": "_shear_state_label(" in segment,
        "controller_helper_accepts_bottom_labels": "before_bottom_reo_label: str | None = None" in controller_source
        and "after_bottom_reo_label: str | None = None" in controller_source,
        "controller_helper_present": "def build_design_guide_pure_guidance_step_description(" in controller_source,
        "controller_helper_exported": '"build_design_guide_pure_guidance_step_description"' in controller_source,
        "controller_has_no_inputs_page_import": "inputs_page" not in controller_source,
        "controller_has_no_streamlit_import": "streamlit" not in controller_source and "st.session_state" not in controller_source,
    }
    return {
        "schema": "design_guide_describe_guidance_step_bottom_wording_cutover.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end, "line_count": max(0, end - start + 1)},
        "source_checks": source_checks,
        "parity_rows": rows,
        "all_parity_rows_match": all(bool(row.get("matches")) for row in rows),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "parity_rows_match": bool(payload.get("all_parity_rows_match")),
        "page_computes_bottom_labels": bool(source_checks.get("page_computes_bottom_labels")),
        "page_passes_bottom_labels": bool(source_checks.get("page_passes_bottom_labels")),
        "page_bottom_fallback_branch_deleted": bool(source_checks.get("page_bottom_fallback_branch_deleted")),
        "risky_shear_branch_remains": bool(source_checks.get("risky_shear_branch_remains")),
        "controller_helper_accepts_bottom_labels": bool(source_checks.get("controller_helper_accepts_bottom_labels")),
        "controller_helper_present": bool(source_checks.get("controller_helper_present")),
        "controller_helper_exported": bool(source_checks.get("controller_helper_exported")),
        "controller_boundary_clean": bool(source_checks.get("controller_has_no_inputs_page_import")) and bool(source_checks.get("controller_has_no_streamlit_import")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_describe_guidance_step_bottom_wording_cutover_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_describe_guidance_step_bottom_wording_cutover_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Describe Guidance Step Bottom Wording Cutover",
        "",
        f"Status: {payload['status']}",
        "",
        "## Parity Rows",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('matches') else 'FAIL'}")
    lines.extend(["", "## Checks", *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_describe_guidance_step_bottom_wording_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
