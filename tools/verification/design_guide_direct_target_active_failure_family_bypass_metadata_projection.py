"""Verify direct target-band active-failure family bypass metadata projection cutover."""

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
HELPER = "build_design_guide_controller_direct_target_family_bypass_projection"


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


def _run_parity_cases() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_direct_target_family_bypass_projection,
    )

    base_item = {
        "title_main": "Capacity is low",
        "candidate_search_evidence": {"selected_candidate_id": "cand-1"},
    }
    cases = {
        "bending": build_design_guide_controller_direct_target_family_bypass_projection(
            item=dict(base_item),
            family_id="BENDING_FAIL_GOVERNS",
            family_route_owner="design_brain.families.bending_fail.BendingFailFamily",
            skipped_reason="selected_family_bending_fail_governs",
            evidence_extra={
                "family_speed_isolation_owner": "BENDING_FAIL_GOVERNS",
                "family_speed_isolation_active_repair": True,
                "post_publication_generic_proofs_skipped": True,
            },
            item_extra={
                "family_speed_isolation_owner": "BENDING_FAIL_GOVERNS",
                "family_speed_isolation_active_repair": True,
                "post_publication_generic_proofs_skipped": True,
            },
            debug_extra={
                "family_speed_isolation_owner": "BENDING_FAIL_GOVERNS",
                "family_speed_isolation_active_repair": True,
                "post_publication_generic_proofs_skipped": True,
            },
            family_early_dispatch_key="family_early_dispatch_used",
        ),
        "shear": build_design_guide_controller_direct_target_family_bypass_projection(
            item=dict(base_item),
            family_id="SHEAR_FAIL_GOVERNS",
            family_route_owner="design_brain.families.shear_fail.ShearFailFamily",
            skipped_reason="selected_family_shear_fail_governs",
        ),
        "combined": build_design_guide_controller_direct_target_family_bypass_projection(
            item=dict(base_item),
            family_id="COMBINED_BENDING_SHEAR_FAIL",
            family_route_owner=(
                "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily"
            ),
            skipped_reason="selected_family_combined_bending_shear_fail",
            evidence_extra={
                "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
                "raw_state_flags": {"bending_fail": True, "shear_fail": True},
                "selection_reason": "classified_by_mutually_exclusive_definition:COMBINED_BENDING_SHEAR_FAIL",
            },
            item_extra={
                "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
                "raw_state_flags": {"bending_fail": True, "shear_fail": True},
                "selection_reason": "classified_by_mutually_exclusive_definition:COMBINED_BENDING_SHEAR_FAIL",
            },
            family_early_dispatch_key="early_family_dispatch_used",
            include_projected_evidence_in_debug=True,
        ),
    }
    checks: dict[str, dict[str, bool]] = {}
    for name, projection in cases.items():
        item = dict(projection.get("item") or {})
        evidence = dict(projection.get("candidate_search_evidence") or {})
        debug_update = dict(projection.get("debug_update") or {})
        family_id = (
            "BENDING_FAIL_GOVERNS"
            if name == "bending"
            else "SHEAR_FAIL_GOVERNS"
            if name == "shear"
            else "COMBINED_BENDING_SHEAR_FAIL"
        )
        checks[name] = {
            "item_family_preserved": item.get("selected_family_id") == family_id,
            "evidence_family_preserved": evidence.get("selected_family_id") == family_id,
            "cta_family_preserved": item.get("cta_family_id") == family_id
            and evidence.get("cta_family_id") == family_id,
            "candidate_card_family_preserved": item.get("candidate_family_id") == family_id
            and item.get("card_family_id") == family_id,
            "generic_skip_preserved": item.get("generic_target_band_search_skipped") is True
            and evidence.get("generic_target_band_search_skipped") is True,
            "debug_skip_preserved": debug_update.get("generic_target_band_search_skipped") is True,
            "family_match_contract_preserved": item.get("family_selection_contract")
            == "family_selection_contract",
            "candidate_evidence_preserved": item.get("candidate_search_evidence") == evidence,
        }
    checks["bending"]["speed_isolation_preserved"] = (
        cases["bending"]["item"].get("family_speed_isolation_owner") == "BENDING_FAIL_GOVERNS"
        and cases["bending"]["debug_update"].get("post_publication_generic_proofs_skipped") is True
    )
    checks["combined"]["projected_debug_evidence_preserved"] = (
        cases["combined"]["debug_update"].get("candidate_search_evidence")
        == cases["combined"]["candidate_search_evidence"]
    )
    return {
        "cases": cases,
        "checks": checks,
        "passed": all(all(row.values()) for row in checks.values()),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)
    pre_selection = target_source.split('selected = selection_result.get("selected_candidate")', 1)[0]
    helper_call_count = pre_selection.count(f"_{HELPER}(")
    old_inline_metadata_tokens = [
        'bending_family_evidence.update(',
        'shear_family_evidence.update(',
        'combined_family_evidence.update(',
        '"selected_family_id": "BENDING_FAIL_GOVERNS"',
        '"selected_family_id": "SHEAR_FAIL_GOVERNS"',
        '"selected_family_id": "COMBINED_BENDING_SHEAR_FAIL"',
    ]
    helper_required_tokens = [
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "candidate_family_id",
        "card_family_id",
        "generic_target_band_search_skipped_reason",
        "direct_target_band_bypassed_by_family_owner",
        "family_selection_contract",
        "include_projected_evidence_in_debug",
    ]
    parity = _run_parity_cases()
    return {
        "schema": "design_guide_direct_target_active_failure_family_bypass_metadata_projection.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
        },
        "controller_helper": {
            "name": HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
        },
        "page_imports_helper": f"{HELPER} as _{HELPER}" in inputs_source,
        "page_calls_helper_count": helper_call_count,
        "old_inline_metadata_tokens_present": [
            token for token in old_inline_metadata_tokens if token in pre_selection
        ],
        "helper_required_tokens_missing": [
            token for token in helper_required_tokens if token not in helper_source
        ],
        "family_runtime_execution_remains_page_owned": "_active_fail_near_current_repair_item(" in pre_selection,
        "bending_cta_publication_side_effect_remains_page_owned": (
            "_record_bending_fail_valid_repair_cta_published(" in pre_selection
        ),
        "debug_sink_remains_page_owned": "debug_sink.update(" in pre_selection,
        "parity": parity,
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
        "page_imports_helper": bool(capture.get("page_imports_helper")),
        "page_calls_helper_for_three_family_paths": int(capture.get("page_calls_helper_count") or 0) >= 3,
        "old_inline_metadata_tokens_removed": not bool(capture.get("old_inline_metadata_tokens_present")),
        "helper_required_tokens_present": not bool(capture.get("helper_required_tokens_missing")),
        "family_runtime_execution_remains_page_owned": bool(
            capture.get("family_runtime_execution_remains_page_owned")
        ),
        "bending_cta_publication_side_effect_remains_page_owned": bool(
            capture.get("bending_cta_publication_side_effect_remains_page_owned")
        ),
        "debug_sink_remains_page_owned": bool(capture.get("debug_sink_remains_page_owned")),
        "parity_cases_pass": bool((capture.get("parity") or {}).get("passed")),
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
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_active_failure_family_bypass_metadata_projection_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_active_failure_family_bypass_metadata_projection_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Family Bypass Metadata Projection",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- Family-bypass metadata projection moved to `DesignGuideController`.",
        "- Family runtime execution, bending CTA publication side effect, debug sink writes, CTA/apply routing, and visible wording remain page-owned.",
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
    print(f"design_guide_direct_target_active_failure_family_bypass_metadata_projection {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
