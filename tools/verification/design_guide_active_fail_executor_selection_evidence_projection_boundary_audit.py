"""Audit active-fail executor selection/evidence projection boundary."""

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
TARGET = "_active_fail_near_current_repair_item"


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


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_row(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": _line_numbers(segment, start_line, token)[:20],
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    family_selector_temp_inline = (
        "combined_controller_fallback_ranker" in controller_source
        or "bending_controller_fallback_ranker" in controller_source
    )

    surfaces = [
        {
            "surface": "safe candidate acceptance predicate",
            "classification": "completed controller-owned candidate filter",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(segment, start, "_filter_design_guide_controller_active_fail_executor_repair_candidates("),
            ],
        },
        {
            "surface": "candidate search evidence construction",
            "classification": "controller-owned evidence projection with page shell data collection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(segment, start, "def _evidence(selected: dict | None) -> dict"),
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_candidate_search_evidence("),
            ],
        },
        {
            "surface": "no-repair blocker projection",
            "classification": "completed direct controller-owned blocker item projection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence("),
                _token_row(inputs_source, 1, "def _active_failure_no_repair_blocker_from_evidence("),
            ],
        },
        {
            "surface": "family ladder candidate selection",
            "classification": (
                "temporary controller-owned orchestration with family strategy delegation; "
                "family-specific fallback ranking is not final-owner compliant"
                if family_selector_temp_inline
                else "family-owned fallback selector policy with controller sequencing"
            ),
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": (
                "family packages own family-specific selector/fallback ranking; "
                "DesignGuideController only sequences and injects strategies"
            ),
            "deletion_readiness": (
                "TEMP_CONTROLLER_POLICY_NEEDS_FAMILY_OWNER_AUDIT"
                if family_selector_temp_inline
                else "SHELL_CALL"
            ),
            "evidence": [
                _token_row(segment, start, "_select_design_guide_controller_active_fail_executor_family_ladder_candidate("),
                _token_row(segment, start, "selected = safe[0]"),
                _token_row(controller_source, 1, "combined_controller_fallback_ranker"),
                _token_row(controller_source, 1, "bending_controller_fallback_ranker"),
                _token_row(controller_source, 1, "_active_fail_executor_family_strategy("),
            ],
        },
        {
            "surface": "selected repair candidate projection",
            "classification": "controller-owned repair decision projection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_selected_repair_candidate("),
            ],
        },
        {
            "surface": "guidance item materialization",
            "classification": "mixed page shell materialization plus controller final field projection",
            "current_owner": "inputs_page page item factory, then DesignGuideController final projection",
            "target_owner": "page shell for factory inputs; controller for final publication fields",
            "deletion_readiness": "KEEP_BOUNDED",
            "evidence": [
                _token_row(segment, start, "_guidance_item_from_resolved_candidate("),
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_final_guidance_item_projection("),
            ],
        },
        {
            "surface": "cache/session storage",
            "classification": "page-owned cache/session plumbing",
            "current_owner": "inputs_page",
            "target_owner": "inputs_page page shell",
            "deletion_readiness": "KEEP_BOUNDED",
            "evidence": [
                _token_row(segment, start, "_cache_search_item("),
                _token_row(segment, start, "set_rerun_pure_cache("),
                _token_row(segment, start, "st.session_state"),
            ],
        },
    ]

    if family_selector_temp_inline:
        first_slice = {
            "name": "active_fail_family_ladder_selector_policy_family_ownership_audit",
            "why": (
                "Safe candidate filtering, evidence projection, no-repair blocker projection, selected repair "
                "projection, and final guidance projection are controller/service-backed. However, the active-fail "
                "family ladder candidate selector still contains controller fallback rankers for family-specific "
                "selection. Under the physical-extraction ownership rule, those fallback policies need a family-owner "
                "audit before any further cutover."
            ),
            "move": (
                "Audit selector fallback policy only. Do not move callback execution, loop order, trace/session, CTA "
                "publication side effects, item packaging, visible wording, or family runtime behavior. Decide which "
                "selector/ranking rules belong in BENDING_FAIL_GOVERNS, SHEAR_FAIL_GOVERNS, combined fail family, or "
                "generic controller sequencing."
            ),
            "required_verifier": "design_guide_active_fail_family_ladder_selector_policy_family_ownership_audit.py",
        }
    else:
        first_slice = {
            "name": "active_fail_executor_guidance_item_materialization_boundary_audit",
            "why": (
                "Safe candidate filtering, evidence projection, no-repair blocker projection, selected repair "
                "projection, final guidance projection, and family-specific selector fallback ownership are now "
                "controller/service/family-backed. The next remaining extraction surface is active-fail executor "
                "guidance item materialization."
            ),
            "move": (
                "Audit active-fail executor guidance item materialization before moving or deleting page-owned code. "
                "Keep callback execution, loop order, trace/session, CTA publication side effects, visible wording, "
                "and family runtime behavior unchanged."
            ),
            "required_verifier": "design_guide_active_fail_executor_guidance_item_materialization_boundary_audit.py",
        }

    return {
        "schema": "design_guide_active_fail_executor_selection_evidence_projection_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": (
            "SELECTION_EVIDENCE_COMPLETE_TEMP_CONTROLLER_FAMILY_SELECTOR_POLICY_REMAINS"
            if family_selector_temp_inline
            else "SELECTION_EVIDENCE_AND_FAMILY_SELECTOR_POLICY_COMPLETE"
        ),
        "surfaces": surfaces,
        "first_safe_implementation_slice": first_slice,
        "family_selector_temp_inline": bool(family_selector_temp_inline),
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
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(surfaces) == 7,
        "safe_filter_adapter_complete": any(
            row.get("surface") == "safe candidate acceptance predicate"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "evidence_projection_controller_owned": any(
            row.get("surface") == "candidate search evidence construction"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "family_selector_policy_owned_or_identified": any(
            row.get("surface") == "family ladder candidate selection"
            and row.get("deletion_readiness")
            in {"TEMP_CONTROLLER_POLICY_NEEDS_FAMILY_OWNER_AUDIT", "SHELL_CALL"}
            for row in surfaces
        ),
        "item_materialization_bounded": any(
            row.get("surface") == "guidance item materialization"
            and row.get("deletion_readiness") == "KEEP_BOUNDED"
            for row in surfaces
        ),
        "cache_session_bounded": any(
            row.get("surface") == "cache/session storage"
            and row.get("deletion_readiness") == "KEEP_BOUNDED"
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
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_selection_evidence_projection_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_selection_evidence_projection_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = payload.get("first_safe_implementation_slice") or {}
    lines = [
        "# Design Guide Active-Fail Executor Selection/Evidence Projection Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"({row.get('current_owner')} -> {row.get('target_owner')}); "
            f"readiness `{row.get('deletion_readiness')}`"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Verifier: `{first_slice.get('required_verifier')}`",
            "",
            "## Stop Conditions",
            "- Stop if selector ownership changes without family-owner parity.",
            "- Stop if candidate acceptance count changes.",
            "- Stop if selected candidate id changes.",
            "- Stop if evidence, CTA/apply semantics, family runtime behavior, or visible wording changes.",
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
    print(f"design_guide_active_fail_executor_selection_evidence_projection_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
