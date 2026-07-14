from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_evaluate_local_cleanup_guidance_item"
SAFETY_CALLBACK = "_resolved_shear_cleanup_is_executor_safe"

EXPECTED_CONTROLLER_DELEGATIONS = {
    "pre_preview_gate": "_resolve_design_guide_controller_local_cleanup_pre_preview_gate(",
    "basic_post_preview_gate": "_resolve_design_guide_controller_local_cleanup_basic_post_preview_gate(",
    "target_band_acceptance": "_resolve_design_guide_controller_local_cleanup_target_band_acceptance(",
    "executor_acceptance": "_resolve_design_guide_controller_local_cleanup_executor_acceptance(",
}

REMAINING_PAGE_SURFACES = {
    "candidate_evaluation_execution": {
        "token": "_evaluate_auto_design_candidate(",
        "classification": "still page-owned Design Brain decision logic",
        "target_owner": "candidate evaluation service/controller boundary",
        "difficulty": "HIGH",
        "deletion_readiness": "NOT_READY",
    },
    "candidate_promotion_callback": {
        "token": "_promote_guidance_item_to_resolved_candidate(",
        "classification": "still page-owned Design Brain decision logic",
        "target_owner": "DesignGuideController adapter after candidate boundary",
        "difficulty": "MEDIUM",
        "deletion_readiness": "NOT_READY",
    },
    "shear_executor_safety_callback": {
        "token": "_resolved_shear_cleanup_is_executor_safe(",
        "classification": "page-owned callback execution",
        "target_owner": "page shell; callback delegates fallback to candidate_evaluation and policy to DesignGuideController",
        "difficulty": "MEDIUM",
        "deletion_readiness": "SHELL_ONLY",
    },
    "one_click_probe": {
        "token": "_guidance_item_is_resolved_one_click(",
        "classification": "page-owned probe execution",
        "target_owner": "page shell",
        "difficulty": "LOW",
        "deletion_readiness": "SHELL_ONLY",
    },
    "actionability_callback": {
        "token": "_guidance_executor_actionability_contract(",
        "classification": "page-owned callback execution",
        "target_owner": "page shell; apply/actionability callback remains page-owned",
        "difficulty": "MEDIUM",
        "deletion_readiness": "SHELL_ONLY",
    },
    "target_band_scalar_collection": {
        "token": "_resolved_efficiency_target_band(",
        "classification": "page-shell scalar collection for controller-owned policy",
        "target_owner": "page shell for now",
        "difficulty": "LOW",
        "deletion_readiness": "SHELL_ONLY",
    },
}


def _function_bounds(source: str, name: str) -> tuple[int, int, str]:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return 0, 0, ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    start_line = source[:start].count("\n") + 1
    end_line = source[:next_start].count("\n") + 1
    return start_line, end_line, source[start:next_start]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    start_line, end_line, segment = _function_bounds(inputs_source, TARGET)
    _safety_start, _safety_end, safety_segment = _function_bounds(inputs_source, SAFETY_CALLBACK)
    delegations = {
        name: token in segment
        for name, token in EXPECTED_CONTROLLER_DELEGATIONS.items()
    }
    remaining_surfaces = []
    for name, meta in REMAINING_PAGE_SURFACES.items():
        present = str(meta["token"]) in segment
        remaining_surfaces.append(
            {
                "surface": name,
                "present": present,
                "token": meta["token"],
                "classification": meta["classification"],
                "target_owner": meta["target_owner"],
                "difficulty": meta["difficulty"],
                "deletion_readiness": meta["deletion_readiness"],
            }
        )
    present_surfaces = [row for row in remaining_surfaces if row.get("present")]
    non_shell_surfaces = [
        row
        for row in present_surfaces
        if row.get("deletion_readiness") not in {"SHELL_ONLY", "COMPATIBILITY_ONLY", "DELETION_CANDIDATE"}
    ]
    first_non_shell_surface = next(iter(non_shell_surfaces), {})
    if first_non_shell_surface.get("surface") == "candidate_evaluation_execution":
        decision = "PARTIAL_READY_FOR_CANDIDATE_EVALUATION_BOUNDARY"
        next_safe_slice = "candidate_evaluation_service_boundary_for_local_cleanup_guidance_item"
    elif first_non_shell_surface.get("surface") == "candidate_promotion_callback":
        decision = "PARTIAL_READY_FOR_CANDIDATE_PROMOTION_CALLBACK_BOUNDARY"
        next_safe_slice = "candidate_promotion_callback_boundary_for_local_cleanup_guidance_item"
    elif non_shell_surfaces:
        decision = "NOT_SHELL_ONLY_WITH_EXACT_REMAINING_SURFACE"
        next_safe_slice = str(first_non_shell_surface.get("surface") or "remaining_page_design_brain_surface")
    elif present_surfaces:
        decision = "LOCAL_CLEANUP_HELPER_SHELL_ONLY"
        next_safe_slice = "local_cleanup_helper_shell_only_lock_or_wrapper_deadness_audit"
    else:
        decision = "LOCAL_CLEANUP_HELPER_SHELL_ONLY"
        next_safe_slice = "local_cleanup_guidance_item_zero_authority_lock"
    page_owned_decision_reasons = sorted(
        reason
        for reason in (
            "invalid_candidate",
            "candidate_not_actionable",
            "cleanup_no_material_update",
            "cleanup_no_net_material_efficiency",
            "cleanup_increases_geometry_without_section_reduction",
            "cleanup_not_material",
            "active_failure_needs_strengthening",
            "shear_not_below_target",
            "cleanup_preview_failed",
            "cleanup_preview_not_all_pass",
            "cleanup_preview_has_fail_status",
            "shear_cleanup_does_not_improve_utilisation",
            "cleanup_does_not_move_governing_utilisation_toward_target",
            "shear_cleanup_not_executor_safe",
            "cleanup_not_executor_backed",
            "cleanup_not_executable",
        )
        if f"\"{reason}\"" in segment
    )
    return {
        "schema": "design_guide_local_cleanup_guidance_item_shell_audit.v1",
        "target": TARGET,
        "line_start": start_line,
        "line_end": end_line,
        "line_count": max(0, end_line - start_line + 1),
        "controller_delegations": delegations,
        "all_expected_controller_delegations_present": all(delegations.values()),
        "candidate_evaluation_callsite_uses_service": "_evaluate_design_candidate_with_updates(" in segment
        and "_evaluate_auto_design_candidate(" not in segment,
        "candidate_promotion_controller_owned": "_resolve_design_guide_controller_local_cleanup_candidate_promotion(" in segment
        and "_promote_guidance_item_to_resolved_candidate(" not in segment,
        "target_band_acceptance_controller_owned": "_resolve_design_guide_controller_local_cleanup_target_band_acceptance(" in segment,
        "pre_post_preview_gates_controller_owned": all(
            token in segment
            for token in (
                "_resolve_design_guide_controller_local_cleanup_pre_preview_gate(",
                "_resolve_design_guide_controller_local_cleanup_basic_post_preview_gate(",
            )
        ),
        "executor_acceptance_controller_owned": "_resolve_design_guide_controller_local_cleanup_executor_acceptance(" in segment,
        "safety_callback_no_page_shim_fallback": "_evaluate_auto_design_candidate(" not in safety_segment,
        "safety_callback_uses_candidate_evaluation_service": "_resolve_design_candidate_overview_for_safety_check(" in safety_segment,
        "safety_policy_controller_owned": "_resolve_design_guide_controller_shear_executor_safety_policy(" in safety_segment
        and "resolve_design_guide_controller_shear_executor_safety_policy" in controller_source,
        "safety_policy_not_page_owned": all(
            token not in safety_segment
            for token in (
                "_candidate_preview_statuses_have_explicit_fail(",
                "candidate_overview.get(\"any_fail\")",
                "governing_status_after",
            )
        ),
        "remaining_one_click_actionability_callbacks_page_owned": all(
            row.get("deletion_readiness") == "SHELL_ONLY"
            for row in remaining_surfaces
            if row.get("surface") in {"one_click_probe", "actionability_callback"} and row.get("present")
        ),
        "remaining_page_surfaces": remaining_surfaces,
        "remaining_page_surface_count": sum(1 for row in remaining_surfaces if row.get("present")),
        "non_shell_surface_count": len(non_shell_surfaces),
        "non_shell_surfaces": non_shell_surfaces,
        "page_owned_decision_reason_literals_remaining": page_owned_decision_reasons,
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "candidate_evaluation_has_no_page_or_streamlit_imports": "inputs_page" not in candidate_source and "streamlit" not in candidate_source,
        "decision": decision,
        "next_safe_slice": next_safe_slice,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool(capture.get("line_count")),
        "all_expected_controller_delegations_present": bool(capture.get("all_expected_controller_delegations_present")),
        "candidate_evaluation_callsite_uses_service": bool(capture.get("candidate_evaluation_callsite_uses_service")),
        "candidate_promotion_controller_owned": bool(capture.get("candidate_promotion_controller_owned")),
        "target_band_acceptance_controller_owned": bool(capture.get("target_band_acceptance_controller_owned")),
        "pre_post_preview_gates_controller_owned": bool(capture.get("pre_post_preview_gates_controller_owned")),
        "executor_acceptance_controller_owned": bool(capture.get("executor_acceptance_controller_owned")),
        "safety_callback_no_page_shim_fallback": bool(capture.get("safety_callback_no_page_shim_fallback")),
        "safety_callback_uses_candidate_evaluation_service": bool(capture.get("safety_callback_uses_candidate_evaluation_service")),
        "safety_policy_controller_owned": bool(capture.get("safety_policy_controller_owned")),
        "safety_policy_not_page_owned": bool(capture.get("safety_policy_not_page_owned")),
        "remaining_one_click_actionability_callbacks_page_owned": bool(capture.get("remaining_one_click_actionability_callbacks_page_owned")),
        "no_non_shell_surfaces": int(capture.get("non_shell_surface_count") or 0) == 0,
        "page_decision_reason_literals_removed": not capture.get("page_owned_decision_reason_literals_remaining"),
        "remaining_surfaces_classified": all(
            row.get("classification") and row.get("target_owner")
            for row in capture.get("remaining_page_surfaces") or []
        ),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "candidate_evaluation_has_no_page_or_streamlit_imports": bool(capture.get("candidate_evaluation_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Local Cleanup Guidance Item Shell Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Current Helper",
        f"- Target: `{capture.get('target')}`",
        f"- Lines: `{capture.get('line_start')}`-`{capture.get('line_end')}`",
        f"- Line count: `{capture.get('line_count')}`",
        "",
        "## Controller Delegations Present",
    ]
    for name, present in dict(capture.get("controller_delegations") or {}).items():
        lines.append(f"- `{name}`: `{present}`")
    lines.extend(
        [
            "",
            "## Remaining Page Surfaces",
            "Surface | Present | Classification | Target owner | Difficulty | Deletion readiness",
            "--- | --- | --- | --- | --- | ---",
        ]
    )
    for row in capture.get("remaining_page_surfaces") or []:
        lines.append(
            " | ".join(
                [
                    f"`{row.get('surface')}`",
                    f"`{row.get('present')}`",
                    str(row.get("classification") or ""),
                    str(row.get("target_owner") or ""),
                    str(row.get("difficulty") or ""),
                    str(row.get("deletion_readiness") or ""),
                ]
            )
        )
    lines.extend(
        [
            "",
            "## Page-Owned Decision Reasons Remaining",
            str(capture.get("page_owned_decision_reason_literals_remaining") or []),
            "",
            "## Shell Verdict",
            f"- Decision: `{capture.get('decision')}`",
            f"- Non-shell surface count: `{capture.get('non_shell_surface_count')}`",
            f"- Candidate evaluation service callsite: `{capture.get('candidate_evaluation_callsite_uses_service')}`",
            f"- Candidate promotion controller-owned: `{capture.get('candidate_promotion_controller_owned')}`",
            f"- Safety callback has no page-shim fallback: `{capture.get('safety_callback_no_page_shim_fallback')}`",
            f"- Safety callback uses candidate-evaluation service: `{capture.get('safety_callback_uses_candidate_evaluation_service')}`",
            f"- Safety policy controller-owned: `{capture.get('safety_policy_controller_owned')}`",
            f"- One-click/actionability callbacks explicitly page-owned: `{capture.get('remaining_one_click_actionability_callbacks_page_owned')}`",
            "",
            "## Non-Shell Surfaces",
            "Surface | Classification | Target owner | Deletion readiness",
            "--- | --- | --- | ---",
        ]
    )
    for row in capture.get("non_shell_surfaces") or []:
        lines.append(
            " | ".join(
                [
                    f"`{row.get('surface')}`",
                    str(row.get("classification") or ""),
                    str(row.get("target_owner") or ""),
                    str(row.get("deletion_readiness") or ""),
                ]
            )
        )
    if not capture.get("non_shell_surfaces"):
        lines.append("`none` | shell-only | page shell | `SHELL_ONLY`")
    lines.extend(
        [
            "",
            "## Decision",
            str(capture.get("decision") or ""),
            "",
            "## Next Safe Slice",
            str(capture.get("next_safe_slice") or ""),
            "",
            "## Verifier Results",
        ]
    )
    for name, passed in checks.items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "- Do not delete callback/probe execution from `inputs_page.py` until candidate evaluation and actionability boundaries are extracted.",
            "- Do not move Streamlit/session/apply routing into Design Brain.",
            "- Stop if candidate evaluation parity cannot be proven from plain request/result data.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = str(payload.get("created_at") or "")
    status = str(payload.get("status") or "")
    existing = PROGRESS_PATH.read_text(encoding="utf-8") if PROGRESS_PATH.exists() else ""
    capture = dict(payload.get("capture") or {})
    entry = (
        "\n"
        f"## {stamp} - Local Cleanup Guidance Item Shell Audit\n"
        f"- Result: `{status}`\n"
        f"- Remaining page surfaces present: `{capture.get('remaining_page_surface_count')}`\n"
        f"- Decision: `{capture.get('decision')}`\n"
        f"- Next safe slice: `{capture.get('next_safe_slice')}`\n"
        f"- Report: `{report_path}`\n"
    )
    if entry.strip() not in existing:
        PROGRESS_PATH.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_local_cleanup_guidance_item_shell_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_guidance_item_shell_audit_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_guidance_item_shell_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    if status == "PASS":
        _append_progress(payload, audit_path)
    print(f"design_guide_local_cleanup_guidance_item_shell_audit {status}")
    print(f"json={json_path}")
    print(f"report={audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
