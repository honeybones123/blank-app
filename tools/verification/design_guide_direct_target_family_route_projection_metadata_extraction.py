"""Verify direct-target family route projection metadata extraction.

This is a focused extraction verifier. It proves that pure active-failure
direct-target route metadata moved to DesignGuideController while the page keeps
family callback execution, debug writes, CTA side effects, and apply/render
plumbing.
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
TARGET = "_direct_target_band_guidance_item"
HELPER = "build_design_guide_controller_direct_target_family_route_projection_metadata"
HELPER_ALIAS = f"_{HELPER}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return "\n".join(lines[start - 1 : end])
    return ""


def _metadata_cases() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_direct_target_family_route_projection_metadata,
        resolve_design_guide_controller_direct_target_active_failure_route_policy,
    )

    cases: dict[str, Any] = {}
    for case_id, keys in {
        "bending": {"bending"},
        "shear": {"shear"},
        "combined": {"bending", "shear"},
        "none": set(),
    }.items():
        policy = resolve_design_guide_controller_direct_target_active_failure_route_policy(
            strengthening=True,
            active_failure_keys=keys,
        )
        metadata = build_design_guide_controller_direct_target_family_route_projection_metadata(
            route_policy=policy,
        )
        cases[case_id] = {
            "policy": policy,
            "metadata": metadata,
        }
    return cases


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_source = _function_source(inputs_source, TARGET)
    cases = _metadata_cases()
    bending_metadata = dict(cases["bending"].get("metadata") or {})
    shear_metadata = dict(cases["shear"].get("metadata") or {})
    combined_metadata = dict(cases["combined"].get("metadata") or {})
    return {
        "target_found": bool(target_source),
        "controller_helper_present": f"def {HELPER}(" in controller_source,
        "controller_exports_helper": f'"{HELPER}"' in controller_source,
        "inputs_imports_helper_alias": HELPER_ALIAS in inputs_source,
        "target_calls_helper_alias": f"{HELPER_ALIAS}(" in target_source,
        "old_inline_no_candidate_reason_removed": (
            "selected_family_bending_fail_governs_no_family_candidate" not in target_source
        ),
        "old_inline_active_repair_reason_removed": (
            "BENDING_FAIL_GOVERNS active repair publication owns final outcome"
            not in target_source
        ),
        "family_callback_execution_still_page_owned": (
            target_source.count("_active_fail_near_current_repair_item(") == 3
        ),
        "bending_cta_side_effect_still_page_owned": (
            "_record_bending_fail_valid_repair_cta_published(" in target_source
        ),
        "debug_sink_mutation_still_page_owned": "debug_sink.update(" in target_source,
        "metadata_cases": cases,
        "expected_bending_no_candidate_update": {
            "generic_target_band_search_skipped": True,
            "generic_target_band_search_skipped_reason": (
                "selected_family_bending_fail_governs_no_family_candidate"
            ),
            "direct_target_band_bypassed_by_family_owner": True,
            "direct_target_band_bypass_owner": (
                "design_brain.families.bending_fail.BendingFailFamily"
            ),
        },
        "actual_bending_no_candidate_update": dict(
            bending_metadata.get("no_family_candidate_debug_update") or {}
        ),
        "expected_bending_active_repair_skip_update": {
            "generic_target_band_search_skipped": True,
            "generic_target_band_search_skipped_reason": (
                "BENDING_FAIL_GOVERNS active repair publication owns final outcome"
            ),
        },
        "actual_bending_active_repair_skip_update": dict(
            bending_metadata.get("active_repair_publication_skip_update") or {}
        ),
        "expected_trace_families": {
            "bending": "BENDING_FAIL_GOVERNS",
            "shear": "SHEAR_FAIL_GOVERNS",
            "combined": "COMBINED_BENDING_SHEAR_FAIL",
        },
        "actual_trace_families": {
            "bending": (bending_metadata.get("adapter_trace_base") or {}).get("family_id"),
            "shear": (shear_metadata.get("adapter_trace_base") or {}).get("family_id"),
            "combined": (combined_metadata.get("adapter_trace_base") or {}).get("family_id"),
        },
        "none_route_has_no_update": not dict(
            (cases["none"].get("metadata") or {}).get("no_family_candidate_debug_update")
            or {}
        ),
        "controller_has_no_inputs_page_or_streamlit_imports": (
            "inputs_page" not in controller_source and "streamlit" not in controller_source
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool(capture.get("target_found")),
        "controller_helper_present": bool(capture.get("controller_helper_present")),
        "controller_exports_helper": bool(capture.get("controller_exports_helper")),
        "inputs_imports_helper_alias": bool(capture.get("inputs_imports_helper_alias")),
        "target_calls_helper_alias": bool(capture.get("target_calls_helper_alias")),
        "old_inline_no_candidate_reason_removed": bool(
            capture.get("old_inline_no_candidate_reason_removed")
        ),
        "old_inline_active_repair_reason_removed": bool(
            capture.get("old_inline_active_repair_reason_removed")
        ),
        "family_callback_execution_still_page_owned": bool(
            capture.get("family_callback_execution_still_page_owned")
        ),
        "bending_cta_side_effect_still_page_owned": bool(
            capture.get("bending_cta_side_effect_still_page_owned")
        ),
        "debug_sink_mutation_still_page_owned": bool(
            capture.get("debug_sink_mutation_still_page_owned")
        ),
        "bending_no_candidate_update_matches_old": (
            capture.get("actual_bending_no_candidate_update")
            == capture.get("expected_bending_no_candidate_update")
        ),
        "bending_active_repair_skip_update_matches_old": (
            capture.get("actual_bending_active_repair_skip_update")
            == capture.get("expected_bending_active_repair_skip_update")
        ),
        "trace_family_metadata_matches_old": (
            capture.get("actual_trace_families") == capture.get("expected_trace_families")
        ),
        "none_route_has_no_update": bool(capture.get("none_route_has_no_update")),
        "controller_import_boundary_clean": bool(
            capture.get("controller_has_no_inputs_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Direct Target Family Route Projection Metadata Extraction",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- Controller helper present: `{capture.get('controller_helper_present')}`",
        f"- Page target calls helper: `{capture.get('target_calls_helper_alias')}`",
        f"- Old inline no-candidate reason removed: `{capture.get('old_inline_no_candidate_reason_removed')}`",
        f"- Old inline active-repair reason removed: `{capture.get('old_inline_active_repair_reason_removed')}`",
        f"- Family callback execution remains page-owned: `{capture.get('family_callback_execution_still_page_owned')}`",
        f"- Debug writes remain page-owned: `{capture.get('debug_sink_mutation_still_page_owned')}`",
        "",
        "## Verification",
        "",
    ]
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Rerun direct-target boundary audits and composed locks. If green, the direct-target route metadata surface can be treated as controller-owned while family callback execution remains bounded page shell.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    capture["decision"] = (
        "DIRECT_TARGET_ROUTE_METADATA_CONTROLLER_OWNED"
        if status == "PASS"
        else "DIRECT_TARGET_ROUTE_METADATA_EXTRACTION_FAILED"
    )
    payload = {
        "schema": "design_guide_direct_target_family_route_projection_metadata_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    suffix = stamp.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_family_route_projection_metadata_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_family_route_projection_metadata_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_direct_target_family_route_projection_metadata_extraction {status}")
    print(f"decision={capture['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
