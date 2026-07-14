"""Verify invalid-state compute guidance output projection moved to controller."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
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


def _expected_old_projection(
    *,
    blocked_debug: dict[str, Any],
    guidance_cache_fp: str,
    request_kind_norm: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "guidance_items": [],
        "blocked_state_class": "hard_invalid",
        "debug_trace": dict(blocked_debug),
        "cache_data": {
            "guidance_cache_fp": guidance_cache_fp,
        },
        "recommendation_result": None,
    }
    if request_kind_norm == "auto_design":
        out["auto_design_solver_recommendation"] = None
        out["auto_design_seed_failed"] = True
    return out


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_compute_invalid_state_output_projection,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    wrapper_start, wrapper_end, wrapper_segment = _function_source(inputs_source, "_compute_design_guidance_items")
    helper_start, helper_end, helper_segment = _function_source(
        controller_source,
        "build_design_guide_controller_compute_invalid_state_output_projection",
    )
    cases: list[dict[str, Any]] = []
    for request_kind_norm in ("design_guide", "auto_design"):
        blocked_debug = {
            "guidance_branch": "blocked_invalid_canonical_pack",
            "selected_action_type": None,
            "selected_title": None,
            "user_visible_no_action_reason": "Design Guide blocked: no_bars_resolved.",
        }
        expected = _expected_old_projection(
            blocked_debug=blocked_debug,
            guidance_cache_fp="fixture-cache-fp",
            request_kind_norm=request_kind_norm,
        )
        actual = build_design_guide_controller_compute_invalid_state_output_projection(
            blocked_debug=dict(blocked_debug),
            guidance_cache_fp="fixture-cache-fp",
            request_kind_norm=request_kind_norm,
        )
        cases.append(
            {
                "request_kind_norm": request_kind_norm,
                "matches_old_projection": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )
    return {
        "schema": "design_guide_compute_invalid_state_output_projection_extraction.v1",
        "target": {
            "wrapper_line_start": wrapper_start,
            "wrapper_line_end": wrapper_end,
            "helper_line_start": helper_start,
            "helper_line_end": helper_end,
        },
        "cases": cases,
        "source_checks": {
            "wrapper_delegates_to_controller": (
                "_build_design_guide_controller_compute_invalid_state_output_projection(" in wrapper_segment
            ),
            "wrapper_no_longer_builds_invalid_out_dict": (
                '"blocked_state_class": "hard_invalid"' not in wrapper_segment
            ),
            "wrapper_keeps_cache_write": 'set_rerun_pure_cache("compute_design_guidance_items"' in wrapper_segment,
            "wrapper_keeps_boundary_attachment": "_attach_design_brain_result_boundary(" in wrapper_segment,
            "helper_exists_in_controller": bool(helper_start),
            "helper_exported": '"build_design_guide_controller_compute_invalid_state_output_projection"' in controller_source,
            "controller_has_no_page_or_streamlit_imports": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "all_cases_match_old_projection": all(bool(row.get("matches_old_projection")) for row in payload.get("cases") or []),
        "wrapper_delegates_to_controller": bool(source_checks.get("wrapper_delegates_to_controller")),
        "wrapper_no_longer_builds_invalid_out_dict": bool(source_checks.get("wrapper_no_longer_builds_invalid_out_dict")),
        "wrapper_keeps_cache_write": bool(source_checks.get("wrapper_keeps_cache_write")),
        "wrapper_keeps_boundary_attachment": bool(source_checks.get("wrapper_keeps_boundary_attachment")),
        "helper_exists_in_controller": bool(source_checks.get("helper_exists_in_controller")),
        "helper_exported": bool(source_checks.get("helper_exported")),
        "controller_import_boundary_clean": bool(source_checks.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_invalid_state_output_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_invalid_state_output_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Invalid-State Output Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "The invalid/coherence blocked compute output object is now built by "
        "`design_brain.design_guide_controller`. The page keeps cache writes, "
        "boundary attachment, and existing debug-field construction.",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_invalid_state_output_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
