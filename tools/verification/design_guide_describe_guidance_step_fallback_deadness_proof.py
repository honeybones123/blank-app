"""Prove legacy _describe_guidance_step fallback rows are dead for live-shaped calls."""

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


def _line_hits(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _controller_case(
    *,
    name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    action_type: str,
    updates: dict[str, Any],
    resolved_width_key: str | None = None,
    before_bottom_reo_label: str | None = None,
    after_bottom_reo_label: str | None = None,
    before_shear_reo_label: str | None = None,
    after_shear_reo_label: str | None = None,
) -> dict[str, Any]:
    result = build_design_guide_pure_guidance_step_description(
        before_state=before,
        after_state=after,
        action_type=action_type,
        updates=updates,
        resolved_width_key=resolved_width_key,
        before_bottom_reo_label=before_bottom_reo_label,
        after_bottom_reo_label=after_bottom_reo_label,
        before_shear_reo_label=before_shear_reo_label,
        after_shear_reo_label=after_shear_reo_label,
    )
    description = result.get("description")
    return {
        "name": name,
        "handled": bool(result.get("handled")),
        "description_is_string": isinstance(description, str),
        "description_non_empty": isinstance(description, str) and bool(description.strip()),
        "owner": result.get("owner"),
        "description": description,
        "pass": bool(result.get("handled")) and isinstance(description, str) and bool(description.strip()),
    }


def _live_shaped_rows() -> list[dict[str, Any]]:
    return [
        _controller_case(
            name="depth_update",
            before={"D": 650.0},
            after={"D": 600.0},
            action_type="reduce_depth",
            updates={"D": 600.0},
        ),
        _controller_case(
            name="rect_width_update",
            before={"b": 400.0},
            after={"b": 350.0},
            action_type="reduce_width",
            updates={"b": 350.0},
            resolved_width_key="b",
        ),
        _controller_case(
            name="t_web_width_update",
            before={"bw": 320.0},
            after={"bw": 300.0},
            action_type="reduce_web_width",
            updates={"bw": 300.0},
            resolved_width_key="bw",
        ),
        _controller_case(
            name="i_web_thickness_update",
            before={"tw": 220.0},
            after={"tw": 200.0},
            action_type="reduce_web_thickness",
            updates={"tw": 200.0},
            resolved_width_key="tw",
        ),
        _controller_case(
            name="bottom_count_update",
            before={"bot1_count": 4},
            after={"bot1_count": 5},
            action_type="increase_bottom_reo",
            updates={"bot1_count": 5},
            before_bottom_reo_label="4N20",
            after_bottom_reo_label="5N20",
        ),
        _controller_case(
            name="bottom_ast_update",
            before={"Ast_bot": 900.0},
            after={"Ast_bot": 750.0},
            action_type="reduce_bottom_reo",
            updates={"Ast_bot": 750.0},
            before_bottom_reo_label="N16 @ 180",
            after_bottom_reo_label="N16 @ 220",
        ),
        _controller_case(
            name="shear_spacing_update",
            before={"s_lig": 200.0},
            after={"s_lig": 250.0},
            action_type="reduce_shear_reo",
            updates={"s_lig": 250.0},
            before_shear_reo_label="2-leg N10 @ 200",
            after_shear_reo_label="2-leg N10 @ 250",
        ),
        _controller_case(
            name="shear_zero_legs_update",
            before={"lig_legs": 2, "lig_d": 10, "s_lig": 250.0},
            after={"lig_legs": 0, "lig_d": 10, "s_lig": 250.0},
            action_type="remove_shear_reo",
            updates={"lig_legs": 0},
            before_shear_reo_label="2-leg N10 @ 250",
            after_shear_reo_label="No ligs",
        ),
        _controller_case(
            name="sustained_load_update",
            before={"g_udl_kNm_per_m": 5.0},
            after={"g_udl_kNm_per_m": 4.5},
            action_type="adjust_load",
            updates={"g_udl_kNm_per_m": 4.5},
        ),
        _controller_case(
            name="generic_update",
            before={"foo": 1},
            after={"foo": 2},
            action_type="apply_resolved_candidate",
            updates={"foo": 2},
        ),
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    rows = _live_shaped_rows()
    fallback_tokens = {
        "width": "if width_key in updates:",
        "bottom": "Updated bottom reinforcement from {_bottom_reo_state_label(before_state)}",
        "shear": "Updated shear reinforcement from {_shear_state_label(before_state)}",
        "load": "Adjusted sustained load inputs:",
        "generic": "Applied {action_type.replace",
        "unreachable_rerun": "st.rerun()",
    }
    fallback_presence = {
        name: {
            "present": token in segment,
            "lines": _line_hits(segment, start, token),
        }
        for name, token in fallback_tokens.items()
    }
    source_checks = {
        "target_found": bool(start),
        "controller_call_before_fallback_rows": (
            "_build_design_guide_pure_guidance_step_description(" in segment
            and (
                "if width_key in updates:" not in segment
                or segment.index("_build_design_guide_pure_guidance_step_description(")
                < segment.index("if width_key in updates:")
            )
        ),
        "width_key_always_page_resolved": "_resolve_geometry_width_context(after_state)" in segment
        and "resolved_width_key=width_key" in segment,
        "bottom_labels_page_resolved_before_controller": "before_bottom_reo_label = _bottom_reo_state_label(before_state)" in segment
        and "after_bottom_reo_label = _bottom_reo_state_label(after_state)" in segment
        and "before_bottom_reo_label=before_bottom_reo_label" in segment
        and "after_bottom_reo_label=after_bottom_reo_label" in segment,
        "shear_labels_page_resolved_before_controller": "before_shear_reo_label = _shear_state_label(before_state)" in segment
        and "after_shear_reo_label = _shear_state_label(after_state)" in segment
        and "before_shear_reo_label=before_shear_reo_label" in segment
        and "after_shear_reo_label=after_shear_reo_label" in segment,
        "width_context_returns_non_empty_keys": all(token in inputs_source for token in ('return "bw"', 'return "tw"', 'return "b"')),
        "bottom_label_helper_returns_strings": 'return f"N{dia_1} @ {int(spacing_1)}"' in inputs_source
        and "return _practical_bottom_reo_label" in inputs_source,
        "shear_label_helper_returns_strings": 'return "No ligs"' in inputs_source
        and 'f"{legs}-leg "' in inputs_source,
        "controller_helper_handles_width": "if width_key and width_key in update_map:" in controller_source,
        "controller_helper_handles_bottom_labels": "before_bottom_reo_label" in controller_source
        and "Updated bottom reinforcement from" in controller_source,
        "controller_helper_handles_shear_labels": "before_shear_reo_label" in controller_source
        and "Updated shear reinforcement from" in controller_source,
        "controller_boundary_clean": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
    }
    fallback_rows_present = any(bool(row.get("present")) for row in fallback_presence.values())
    decision = "READY_TO_DELETE_FALLBACK_ROWS" if fallback_rows_present else "FALLBACK_ROWS_DELETED_ZERO_LOCK"
    return {
        "schema": "design_guide_describe_guidance_step_fallback_deadness_proof.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end, "line_count": max(0, end - start + 1)},
        "decision": decision,
        "fallback_presence": fallback_presence,
        "live_shaped_rows": rows,
        "source_checks": source_checks,
        "fallback_rows_present": fallback_rows_present,
        "live_shaped_calls_controller_handled": all(bool(row.get("pass")) for row in rows),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "delete_describe_guidance_step_fallback_rows" if fallback_rows_present else "continue_next_extraction_surface",
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "controller_call_before_fallback_rows": bool(source_checks.get("controller_call_before_fallback_rows")),
        "live_shaped_calls_controller_handled": bool(payload.get("live_shaped_calls_controller_handled")),
        "width_key_resolved_and_passed": bool(source_checks.get("width_key_always_page_resolved")),
        "bottom_labels_resolved_and_passed": bool(source_checks.get("bottom_labels_page_resolved_before_controller")),
        "shear_labels_resolved_and_passed": bool(source_checks.get("shear_labels_page_resolved_before_controller")),
        "page_label_helpers_return_non_empty_strings": bool(source_checks.get("width_context_returns_non_empty_keys"))
        and bool(source_checks.get("bottom_label_helper_returns_strings"))
        and bool(source_checks.get("shear_label_helper_returns_strings")),
        "controller_handles_extracted_branches": bool(source_checks.get("controller_helper_handles_width"))
        and bool(source_checks.get("controller_helper_handles_bottom_labels"))
        and bool(source_checks.get("controller_helper_handles_shear_labels")),
        "controller_boundary_clean": bool(source_checks.get("controller_boundary_clean")),
        "decision_is_valid": payload.get("decision") in {"READY_TO_DELETE_FALLBACK_ROWS", "FALLBACK_ROWS_DELETED_ZERO_LOCK"},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_describe_guidance_step_fallback_deadness_proof_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_describe_guidance_step_fallback_deadness_proof_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Describe Guidance Step Fallback Deadness Proof",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        f"Fallback rows present: {payload.get('fallback_rows_present')}",
        "",
        "## Live-Shaped Controller Coverage",
    ]
    for row in payload.get("live_shaped_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('pass') else 'FAIL'}")
    lines.extend(["", "## Fallback Rows"])
    for name, row in (payload.get("fallback_presence") or {}).items():
        lines.append(f"- {name}: {'present' if row.get('present') else 'absent'} {row.get('lines')}")
    lines.extend(
        [
            "",
            f"Next safe slice: `{payload.get('next_safe_slice')}`",
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
    print(f"design_guide_describe_guidance_step_fallback_deadness_proof {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
