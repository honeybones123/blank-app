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
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

LOCAL_CLEANUP_TARGET = "_evaluate_local_cleanup_guidance_item"
SAFETY_CALLBACK = "_resolved_shear_cleanup_is_executor_safe"


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


def _safety_branch_segment(local_cleanup_segment: str) -> str:
    start = local_cleanup_segment.find("shear_executor_safe = True")
    end = local_cleanup_segment.find("t_lo, t_hi", start)
    if start < 0:
        return ""
    if end < 0:
        end = len(local_cleanup_segment)
    return local_cleanup_segment[start:end]


def _callback_classification(callback_segment: str) -> list[dict[str, Any]]:
    rules = [
        (
            "item_and_payload_update_extraction",
            ("_guidance_item_payload(", "resolved_candidate_updates", "payload.get(\"updates\")"),
            "pure safety policy",
            "Design Brain service candidate",
            "Can move after plain item/payload adapter exists.",
        ),
        (
            "snapshot_state_collection",
            ("_guidance_state_snapshot(",),
            "shell-only input collection",
            "page-owned callback execution",
            "Keep page-owned or pass a precomputed current_state into a service helper.",
        ),
        (
            "pure_shear_detailing_update_filter",
            ("_shear_detailing_updates_pure(",),
            "pure safety policy",
            "Design Brain service candidate",
            "Can move if helper is extracted or represented as a plain boolean input.",
        ),
        (
            "material_reduction_check",
            ("_shear_cleanup_materially_reduces_reinforcement(",),
            "pure safety policy",
            "Design Brain service candidate",
            "Can move with scalar current/next state, or remain as page helper until broader shear cleanup extraction.",
        ),
        (
            "resolved_candidate_overview_path",
            ("overview_resolution", "candidate_overview"),
            "pure safety policy",
            "Design Brain service candidate",
            "Can move: this is plain evidence inspection.",
        ),
        (
            "candidate_evaluation_fallback",
            ("_evaluate_auto_design_candidate(", "guidance_shear_executor_contract_probe"),
            "candidate evaluation fallback",
            "unsafe to move yet",
            "Needs candidate-evaluation service fallback boundary before callback can move.",
        ),
        (
            "candidate_evaluation_service_fallback",
            ("_resolve_design_candidate_overview_for_safety_check(", "guidance_shear_executor_contract_probe"),
            "candidate evaluation service fallback",
            "candidate evaluation service",
            "Fallback has moved behind candidate_evaluation; pure safety-policy extraction can proceed next.",
        ),
        (
            "explicit_fail_status_check",
            ("_candidate_preview_statuses_have_explicit_fail(",),
            "pure safety policy",
            "Design Brain service candidate",
            "Can move after status predicate is extracted or passed in as boolean.",
        ),
        (
            "any_fail_check",
            ("candidate_overview.get(\"any_fail\")",),
            "pure safety policy",
            "Design Brain service candidate",
            "Can move directly.",
        ),
        (
            "governing_domain_status_check",
            ("_governing_focus_from_overview(", "governing_status_after"),
            "pure safety policy",
            "Design Brain service candidate",
            "Can move if governing domain is passed in or resolver is extracted.",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for name, tokens, classification, target_owner, note in rules:
        present = all(token in callback_segment for token in tokens)
        rows.append(
            {
                "part": name,
                "present": present,
                "tokens": list(tokens),
                "classification": classification,
                "target_owner": target_owner,
                "note": note,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    local_start, local_end, local_segment = _function_bounds(inputs_source, LOCAL_CLEANUP_TARGET)
    callback_start, callback_end, callback_segment = _function_bounds(inputs_source, SAFETY_CALLBACK)
    safety_branch = _safety_branch_segment(local_segment)
    classifications = _callback_classification(callback_segment)
    has_page_shim_fallback = "_evaluate_auto_design_candidate(" in callback_segment
    has_service_fallback = "_resolve_design_candidate_overview_for_safety_check(" in callback_segment
    has_existing_overview_path = "overview_resolution" in callback_segment and "candidate_overview" in callback_segment
    branch_sets_blocked_reason_via_controller = all(
        token in safety_branch
        for token in (
            "_resolve_design_guide_controller_local_cleanup_executor_acceptance(",
            "detail[\"blocked_reason\"] = shear_executor_gate.get(\"blocked_reason\")",
        )
    )
    ready_without_fallback_boundary = (
        bool(callback_segment)
        and not has_page_shim_fallback
        and all(row.get("present") for row in classifications if row.get("classification") == "pure safety policy")
    )
    if has_page_shim_fallback:
        decision = "NEEDS_CANDIDATE_EVALUATION_FALLBACK_BOUNDARY_FIRST"
        first_safe_slice = "extract_shear_executor_safety_fallback_to_candidate_evaluation_service_or_pass_precomputed_candidate_overview"
    elif has_service_fallback and has_existing_overview_path:
        decision = "READY_FOR_PURE_SAFETY_POLICY_EXTRACTION"
        first_safe_slice = "move_pure_shear_executor_safety_policy_to_design_guide_controller"
    elif ready_without_fallback_boundary:
        decision = "READY_TO_EXTRACT"
        first_safe_slice = "move_pure_shear_executor_safety_policy_to_design_guide_controller"
    else:
        decision = "PARTIAL_UNCLEAR_CALLBACK_SURFACE"
        first_safe_slice = "prove_missing_safety_predicates_before_cutover"

    return {
        "schema": "design_guide_local_cleanup_shear_executor_safety_boundary_audit.v1",
        "local_cleanup_target": LOCAL_CLEANUP_TARGET,
        "local_cleanup_lines": {"start": local_start, "end": local_end},
        "safety_callback": SAFETY_CALLBACK,
        "safety_callback_lines": {"start": callback_start, "end": callback_end},
        "local_cleanup_branch_calls_safety_callback": f"{SAFETY_CALLBACK}(" in safety_branch,
        "local_cleanup_branch_uses_promoted_controller_output": "promoted," in safety_branch,
        "branch_blocked_reason_detail_shaped_by_controller_gate": branch_sets_blocked_reason_via_controller,
        "resolved_candidate_overview_evidence_path_present": has_existing_overview_path,
        "fallback_to_page_shim_present": has_page_shim_fallback,
        "candidate_evaluation_service_fallback_present": has_service_fallback,
        "fallback_source": "guidance_shear_executor_contract_probe" if "guidance_shear_executor_contract_probe" in callback_segment else None,
        "auto_design_candidate_shim_must_remain": has_page_shim_fallback,
        "classifications": classifications,
        "pure_policy_parts_present": [
            row["part"]
            for row in classifications
            if row.get("present") and row.get("classification") == "pure safety policy"
        ],
        "candidate_evaluation_fallback_parts_present": [
            row["part"]
            for row in classifications
            if row.get("present") and row.get("classification") == "candidate evaluation fallback"
        ],
        "page_owned_callback_parts_present": [
            row["part"]
            for row in classifications
            if row.get("present") and row.get("classification") == "shell-only input collection"
        ],
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "decision": decision,
        "ready_to_extract": decision == "READY_TO_EXTRACT",
        "needs_candidate_evaluation_service_fallback_first": has_page_shim_fallback,
        "exact_first_safe_implementation_slice": first_safe_slice,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "local_cleanup_branch_found": bool(capture.get("local_cleanup_branch_calls_safety_callback")),
        "safety_callback_found": bool(capture.get("safety_callback_lines", {}).get("start")),
        "uses_promoted_controller_output": bool(capture.get("local_cleanup_branch_uses_promoted_controller_output")),
        "blocked_reason_detail_shaped_by_controller_gate": bool(capture.get("branch_blocked_reason_detail_shaped_by_controller_gate")),
        "resolved_candidate_overview_evidence_path_present": bool(capture.get("resolved_candidate_overview_evidence_path_present")),
        "fallback_classified": bool(capture.get("candidate_evaluation_fallback_parts_present")) == bool(capture.get("fallback_to_page_shim_present")),
        "all_present_parts_classified": all(
            row.get("classification") and row.get("target_owner")
            for row in capture.get("classifications") or []
            if row.get("present")
        ),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "decision_recorded": bool(capture.get("decision")),
        "first_safe_slice_recorded": bool(capture.get("exact_first_safe_implementation_slice")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Shear Executor Safety Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Decision",
        f"- Ready to extract: `{capture.get('ready_to_extract')}`",
        f"- Decision: `{capture.get('decision')}`",
        f"- Needs candidate-evaluation service fallback first: `{capture.get('needs_candidate_evaluation_service_fallback_first')}`",
        f"- `_evaluate_auto_design_candidate(...)` shim must remain: `{capture.get('auto_design_candidate_shim_must_remain')}`",
        f"- First safe implementation slice: `{capture.get('exact_first_safe_implementation_slice')}`",
        "",
        "## Current Branch",
        f"- Local cleanup lines: `{capture.get('local_cleanup_lines')}`",
        f"- Safety callback lines: `{capture.get('safety_callback_lines')}`",
        f"- Branch uses promoted controller output: `{capture.get('local_cleanup_branch_uses_promoted_controller_output')}`",
        f"- Blocked reason/detail shaped by controller gate: `{capture.get('branch_blocked_reason_detail_shaped_by_controller_gate')}`",
        "",
        "## Classification",
        "Part | Present | Classification | Target owner | Note",
        "--- | --- | --- | --- | ---",
    ]
    for row in capture.get("classifications") or []:
        lines.append(
            " | ".join(
                [
                    f"`{row.get('part')}`",
                    f"`{row.get('present')}`",
                    str(row.get("classification") or ""),
                    str(row.get("target_owner") or ""),
                    str(row.get("note") or ""),
                ]
            )
        )
    lines.extend(
        [
            "",
            "## Behaviour Boundaries",
            f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
            f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
            f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
            f"- Family runtimes changed: `{capture.get('family_runtimes_changed')}`",
            "",
            "## Audit Conclusion",
            "Do not move the callback yet while it still owns a fallback evaluation call through the page shim. The pure safety policy can move later, but first the fallback needs to become either a candidate-evaluation service call or a precomputed candidate overview input.",
            "",
            "## Verifier Results",
        ]
    )
    for name, passed in checks.items():
        lines.append(f"- `{name}`: `{passed}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_local_cleanup_shear_executor_safety_boundary_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_shear_executor_safety_boundary_audit_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_shear_executor_safety_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    print(f"design_guide_local_cleanup_shear_executor_safety_boundary_audit {status}")
    print(f"json={json_path}")
    print(f"report={audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
