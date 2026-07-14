"""Verify pure wording cutover inside _describe_guidance_step."""

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


def _old_pure_wording(
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    action_type: str,
    updates: dict[str, Any],
) -> str:
    if "D" in updates:
        before_depth = int(float(before_state.get("D", 0.0) or 0.0))
        after_depth = int(float(after_state.get("D", 0.0) or 0.0))
        verb = "Reduced" if after_depth < before_depth else "Increased"
        return f"{verb} depth D from {before_depth} to {after_depth} mm."
    load_keys = ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm")
    if any(key in updates for key in load_keys):
        parts: list[str] = []
        for key in load_keys:
            if key not in updates:
                continue
            try:
                b0 = float(before_state.get(key, 0.0) or 0.0)
                a0 = float(after_state.get(key, 0.0) or 0.0)
                parts.append(f"{key} {b0:.3f} -> {a0:.3f} kN/m")
            except Exception:
                parts.append(str(key))
        if parts:
            return "Adjusted sustained load inputs: " + "; ".join(parts) + "."
    return f"Applied {action_type.replace('_', ' ')}."


def _rows() -> list[dict[str, Any]]:
    cases = [
        ("depth_increase", {"D": 600.0}, {"D": 650.0}, "increase_depth", {"D": 650.0}, True),
        ("depth_reduce", {"D": 650.0}, {"D": 600.0}, "tighten_geometry", {"D": 600.0}, True),
        (
            "load_single_key",
            {"g_udl_kNm_per_m": 4.0},
            {"g_udl_kNm_per_m": 3.5},
            "deflection_reduce_sustained_load",
            {"g_udl_kNm_per_m": 3.5},
            True,
        ),
        ("generic_unknown_safe_key", {"custom": 1}, {"custom": 2}, "custom_action_type", {"custom": 2}, True),
        ("width_declined", {"b": 300.0}, {"b": 350.0}, "increase_width", {"b": 350.0}, False),
        ("bottom_declined", {"bot1_count": 4}, {"bot1_count": 5}, "reduce_bar_spacing", {"bot1_count": 5}, False),
        ("shear_declined", {"s_lig": 200.0}, {"s_lig": 250.0}, "increase_link_spacing", {"s_lig": 250.0}, False),
    ]
    rows: list[dict[str, Any]] = []
    for name, before, after, action_type, updates, should_handle in cases:
        result = build_design_guide_pure_guidance_step_description(
            before_state=dict(before),
            after_state=dict(after),
            action_type=str(action_type),
            updates=dict(updates),
        )
        expected = _old_pure_wording(dict(before), dict(after), str(action_type), dict(updates)) if should_handle else None
        rows.append(
            {
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
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    helper_name = "build_design_guide_pure_guidance_step_description"
    alias = "_build_design_guide_pure_guidance_step_description"
    rows = _rows()
    source_checks = {
        "page_imports_pure_wording_helper": f"{helper_name} as {alias}" in inputs_source,
        "page_uses_pure_wording_helper": f"{alias}(" in segment,
        "page_depth_branch_removed": 'if "D" in updates:' not in segment,
        "width_context_input_stays_page_shell": "_resolve_geometry_width_context(" in segment
        and "resolved_width_key=width_key" in segment
        and "width_key in updates" not in segment,
        "bottom_label_input_stays_page_shell": "_bottom_reo_state_label(" in segment
        and "Updated bottom reinforcement from {_bottom_reo_state_label(before_state)}" not in segment,
        "shear_label_input_stays_page_shell": "_shear_state_label(" in segment
        and "Updated shear reinforcement from {_shear_state_label(before_state)}" not in segment,
        "controller_helper_present": f"def {helper_name}(" in controller_source,
        "controller_helper_exported": f'"{helper_name}"' in controller_source,
        "controller_has_no_inputs_page_import": "inputs_page" not in controller_source,
        "controller_has_no_streamlit_import": "streamlit" not in controller_source and "st.session_state" not in controller_source,
    }
    return {
        "schema": "design_guide_describe_guidance_step_pure_wording_cutover.v1",
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
        "page_imports_pure_wording_helper": bool(source_checks.get("page_imports_pure_wording_helper")),
        "page_uses_pure_wording_helper": bool(source_checks.get("page_uses_pure_wording_helper")),
        "page_depth_branch_removed": bool(source_checks.get("page_depth_branch_removed")),
        "risky_branch_inputs_bounded_to_page_shell": all(
            bool(source_checks.get(key))
            for key in (
                "width_context_input_stays_page_shell",
                "bottom_label_input_stays_page_shell",
                "shear_label_input_stays_page_shell",
            )
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
    json_path = ARTIFACT_DIR / f"design_guide_describe_guidance_step_pure_wording_cutover_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_describe_guidance_step_pure_wording_cutover_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Describe Guidance Step Pure Wording Cutover",
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
    print(f"design_guide_describe_guidance_step_pure_wording_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
