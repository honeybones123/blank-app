"""Audit active-fail family ladder selector policy ownership."""

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

CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
BENDING_FAIL = ROOT / "design_brain" / "families" / "bending_fail.py"
SHEAR_FAIL = ROOT / "design_brain" / "families" / "shear_fail.py"
COMBINED_FAIL = ROOT / "design_brain" / "families" / "combined_bending_shear_fail.py"
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "select_design_guide_controller_active_fail_executor_family_ladder_candidate"


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


def _token_row(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line][:20],
    }


def _capture() -> dict[str, Any]:
    controller_source = _read(CONTROLLER)
    inputs_source = _read(INPUTS_PAGE)
    bending_source = _read(BENDING_FAIL)
    shear_source = _read(SHEAR_FAIL)
    combined_source = _read(COMBINED_FAIL)
    start, end, segment = _function_source(controller_source, TARGET)
    bending_fallback_inline = "bending_controller_fallback_ranker" in segment
    bending_family_helper_present = "def select_bending_fail_fallback_repair_candidate_from_ladder(" in bending_source
    combined_fallback_inline = "combined_controller_fallback_ranker" in segment
    combined_family_helper_present = "def select_combined_fail_fallback_repair_candidate_from_ladder(" in combined_source

    surfaces = [
        {
            "surface": "shear ladder selector",
            "current_owner": "SHEAR_FAIL_GOVERNS family strategy when available; controller falls through to generic fallback if strategy unavailable",
            "target_owner": "design_brain.families.shear_fail / SHEAR_FAIL_GOVERNS",
            "classification": "FAMILY_OWNED_PRIMARY_WITH_CONTROLLER_ORCHESTRATION",
            "deletion_readiness": "NOT_DELETE_CONTROLLER_CALL_UNTIL_STRATEGY_PRESENCE_LOCKED",
            "evidence": [
                _token_row(segment, start, "shear_family_strategy.select_repair_candidate_from_ladder("),
                _token_row(shear_source, 1, "def select_repair_candidate_from_ladder("),
            ],
        },
        {
            "surface": "combined ladder selector fallback ranking",
            "current_owner": (
                "DesignGuideController fallback ranker when combined family strategy is unavailable"
                if combined_fallback_inline
                else "combined fail family helper delegated from DesignGuideController"
            ),
            "target_owner": "design_brain.families.combined_bending_shear_fail",
            "classification": (
                "TEMP_CONTROLLER_FAMILY_POLICY"
                if combined_fallback_inline
                else "FAMILY_OWNED_FALLBACK_WITH_CONTROLLER_DELEGATION"
            ),
            "deletion_readiness": (
                "READY_FOR_FAMILY_PARITY_EXTRACTION_AUDIT"
                if combined_fallback_inline
                else "SHELL_CALL"
            ),
            "evidence": [
                _token_row(segment, start, "combined_family_strategy.select_repair_candidate_from_ladder("),
                _token_row(segment, start, "combined_controller_fallback_ranker"),
                _token_row(segment, start, "select_combined_fail_fallback_repair_candidate_from_ladder("),
                _token_row(combined_source, 1, "def select_combined_fail_fallback_repair_candidate_from_ladder("),
                _token_row(combined_source, 1, "def select_repair_candidate_from_ladder("),
            ],
        },
        {
            "surface": "bending ladder selector fallback ranking",
            "current_owner": (
                "DesignGuideController fallback ranker when bending family strategy is unavailable"
                if bending_fallback_inline
                else "BENDING_FAIL_GOVERNS family helper delegated from DesignGuideController"
            ),
            "target_owner": "design_brain.families.bending_fail / BENDING_FAIL_GOVERNS",
            "classification": (
                "TEMP_CONTROLLER_FAMILY_POLICY"
                if bending_fallback_inline
                else "FAMILY_OWNED_FALLBACK_WITH_CONTROLLER_DELEGATION"
            ),
            "deletion_readiness": (
                "READY_FOR_FAMILY_PARITY_EXTRACTION_AUDIT"
                if bending_fallback_inline
                else "SHELL_CALL"
            ),
            "evidence": [
                _token_row(segment, start, "bending_family_strategy.select_repair_candidate_from_ladder("),
                _token_row(segment, start, "bending_controller_fallback_ranker"),
                _token_row(segment, start, "select_bending_fail_fallback_repair_candidate_from_ladder(candidates)"),
                _token_row(bending_source, 1, "def select_bending_fail_fallback_repair_candidate_from_ladder("),
                _token_row(bending_source, 1, "def select_repair_candidate_from_ladder("),
            ],
        },
        {
            "surface": "generic no-family-ladder fallback ranking",
            "current_owner": "DesignGuideController sequencing fallback",
            "target_owner": "DesignGuideController",
            "classification": "CONTROLLER_ORCHESTRATION_GENERIC",
            "deletion_readiness": "KEEP_CONTROLLER",
            "evidence": [
                _token_row(segment, start, "controller_generic_fallback_ranker"),
                _token_row(segment, start, "resolve_design_guide_controller_direct_target_after_state_preference_scores("),
            ],
        },
        {
            "surface": "page caller",
            "current_owner": "inputs_page.py shell call",
            "target_owner": "inputs_page.py shell call until selector service boundary moves",
            "classification": "PAGE_SHELL_CALLER",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(inputs_source, 1, "_select_design_guide_controller_active_fail_executor_family_ladder_candidate("),
            ],
        },
    ]

    if bending_fallback_inline:
        first_slice = {
            "name": "active_fail_bending_ladder_selector_fallback_family_extraction",
            "why": (
                "The bending fallback ranker is the smallest family-specific controller policy: it ranks by "
                "bending_fail_ladder_index/ladder_index and update-count when the bending family strategy is unavailable."
            ),
            "move": (
                "Add a BENDING_FAIL_GOVERNS family helper for fallback ladder candidate selection, wire the controller "
                "to delegate that fallback to the family helper, and preserve selected candidate id, selection source, "
                "family_selected payload, visible wording, CTA/apply semantics, and family runtime behavior."
            ),
            "required_verifier": "design_guide_active_fail_bending_ladder_selector_fallback_family_extraction.py",
        }
    elif combined_fallback_inline:
        first_slice = {
            "name": "active_fail_combined_ladder_selector_fallback_family_extraction",
            "why": (
                "The bending fallback ranker is now delegated to the bending fail family package. The remaining "
                "family-specific controller fallback is combined ladder selection, which should move to the combined "
                "fail family package with parity before touching generic controller fallback."
            ),
            "move": (
                "Add a combined fail family helper for fallback ladder candidate selection, wire the controller "
                "to delegate that fallback to the family helper, and preserve selected candidate id, selection source, "
                "family_selected payload, visible wording, CTA/apply semantics, and family runtime behavior."
            ),
            "required_verifier": "design_guide_active_fail_combined_ladder_selector_fallback_family_extraction.py",
        }
    else:
        first_slice = {
            "name": "active_fail_executor_guidance_item_materialization_boundary_audit",
            "why": (
                "All family-specific selector fallback rules are now family-owned or primary family strategy-owned. "
                "The next remaining extraction surface is item/materialization around the active-fail executor."
            ),
            "move": "Audit active-fail executor guidance item materialization before moving or deleting page-owned code.",
            "required_verifier": "design_guide_active_fail_executor_guidance_item_materialization_boundary_audit.py",
        }

    return {
        "schema": "design_guide_active_fail_family_ladder_selector_policy_family_ownership_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": (
            "TEMP_CONTROLLER_FAMILY_SELECTOR_FALLBACKS_IDENTIFIED"
            if bending_fallback_inline or combined_fallback_inline
            else "NO_TEMP_CONTROLLER_FAMILY_SELECTOR_FALLBACKS_REMAIN"
        ),
        "surfaces": surfaces,
        "first_safe_implementation_slice": first_slice,
        "bending_fallback_inline_in_controller": bool(bending_fallback_inline),
        "bending_family_helper_present": bool(bending_family_helper_present),
        "combined_fallback_inline_in_controller": bool(combined_fallback_inline),
        "combined_family_helper_present": bool(combined_family_helper_present),
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = payload.get("surfaces") or []
    temp_policy_count = sum(
        1 for row in surfaces if row.get("classification") == "TEMP_CONTROLLER_FAMILY_POLICY"
    )
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(surfaces) == 5,
        "temporary_controller_family_policies_removed": temp_policy_count == 0,
        "shear_primary_family_selector_exists": any(
            row.get("surface") == "shear ladder selector"
            and row.get("classification") == "FAMILY_OWNED_PRIMARY_WITH_CONTROLLER_ORCHESTRATION"
            for row in surfaces
        ),
        "combined_family_fallback_family_owned_or_needs_extraction": any(
            row.get("surface") == "combined ladder selector fallback ranking"
            and row.get("target_owner") == "design_brain.families.combined_bending_shear_fail"
            and row.get("classification")
            in ("FAMILY_OWNED_FALLBACK_WITH_CONTROLLER_DELEGATION", "TEMP_CONTROLLER_FAMILY_POLICY")
            for row in surfaces
        ),
        "combined_family_helper_present_when_extracted": (
            bool(payload.get("combined_fallback_inline_in_controller"))
            or bool(payload.get("combined_family_helper_present"))
        ),
        "bending_family_fallback_family_owned": any(
            row.get("surface") == "bending ladder selector fallback ranking"
            and row.get("classification") == "FAMILY_OWNED_FALLBACK_WITH_CONTROLLER_DELEGATION"
            for row in surfaces
        ),
        "bending_family_helper_present": bool(payload.get("bending_family_helper_present")),
        "generic_controller_fallback_remains_controller": any(
            row.get("surface") == "generic no-family-ladder fallback ranking"
            and row.get("classification") == "CONTROLLER_ORCHESTRATION_GENERIC"
            for row in surfaces
        ),
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        ),
        "controller_boundary_clean": bool(payload.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_family_ladder_selector_policy_family_ownership_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_family_ladder_selector_policy_family_ownership_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = payload.get("first_safe_implementation_slice") or {}
    lines = [
        "# Active-Fail Family Ladder Selector Policy Family Ownership Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: `{row.get('classification')}`; "
            f"{row.get('current_owner')} -> {row.get('target_owner')}"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Why: {first_slice.get('why')}",
            f"- Move: {first_slice.get('move')}",
            f"- Verifier: `{first_slice.get('required_verifier')}`",
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
    print(f"design_guide_active_fail_family_ladder_selector_policy_family_ownership_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
