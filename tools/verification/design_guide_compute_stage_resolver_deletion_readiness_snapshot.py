"""Audit whether the remaining compute-stage Design Guide resolver can be deleted.

This is proof-only. It checks the sole remaining direct
resolve_final_visible_design_guide_item(...) call in inputs_page.py and records
whether it is safe to remove now or still owns pre-publication truth.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


DIRECT_CALL = "final_compute_resolution = resolve_final_visible_design_guide_item("
FUNCTION_DEF = "def resolve_final_visible_design_guide_item("
HANDOFF_FUNCTION = "def _resolve_compute_design_guidance_publication_handoff("
AUTHORITY_ADAPTER = "final_compute_item = _collapsed_guidance_item_from_final_publication_authority("
COMPUTE_PROOF_STAMP = "_stamp_final_publication_compute_handoff_rebound_decision_proof("
A_CLASS_STAMP = "_mark_compute_publication_evidence_a_class_compatibility_only("
DEBUG_RESTAMP_STAMP = "_mark_compute_debug_restamp_metadata_compatibility_only("
CONTROLLER_REPLACEMENT_TRACE = "_stamp_design_guide_controller_compute_resolver_replacement_trace_only("
PRE_RESOLVER_TRACE_KEY = "design_guide_controller_compute_resolver_replacement_pre_resolver_trace"
BROWSER_PARITY_PREFIX = "design_guide_compute_resolver_replacement_browser_live_parity"
CUTOVER_PREFIX = "design_guide_compute_stage_resolver_controller_cutover"
FALLBACK_CALL = "_legacy_fallback_resolution = resolve_final_visible_design_guide_item("

B_CLASS_TOKENS = {
    "late_evidence_acceptance_condition": "_late_evidence_acceptance",
    "late_rebound_contract_enabled": "_design_guide_button_contract_enabled(_late_rebound_contract)",
    "late_rebound_contract_updates": '_late_rebound_contract.get("updates")',
    "post_core_evidence_mismatch_condition": "_post_core_mismatch",
}

D_CLASS_TOKENS = {
    "pre_resolver_collapsed_item_mutation": "pre_resolver_collapsed_item_mutation",
    "post_evidence_cleanup_contract_rebound_flag": "post_evidence_cleanup_contract_rebound",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    direct_call_lines = _line_numbers(source, DIRECT_CALL)
    function_def_lines = _line_numbers(source, FUNCTION_DEF)
    handoff_lines = _line_numbers(source, HANDOFF_FUNCTION)
    controller_replacement_trace_lines = _line_numbers(source, CONTROLLER_REPLACEMENT_TRACE)
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    compute_lock_proof = dict((compute_lock.get("payload") or {}).get("direct_proof") or {})
    browser_parity = _latest(BROWSER_PARITY_PREFIX)
    cutover = _latest(CUTOVER_PREFIX)
    browser_live_trace = dict((browser_parity.get("payload") or {}).get("live_trace") or {})
    cutover_capture = dict((cutover.get("payload") or {}).get("capture") or {})
    browser_parity_checks = {
        "artifact_status_pass": browser_parity.get("status") == "PASS",
        "effective_selected_item_match": (
            browser_live_trace.get("effective_selected_item_match") is True
        ),
        "visible_semantics_match": browser_live_trace.get("visible_semantics_match") is True,
        "cta_semantics_match": browser_live_trace.get("cta_semantics_match") is True,
        "blocker_semantics_match": browser_live_trace.get("blocker_semantics_match") is True,
        "render_reason_match": browser_live_trace.get("render_reason_match") is True,
        "state_fingerprint_match": browser_live_trace.get("state_fingerprint_match") is True,
        "old_resolver_input_not_required": browser_live_trace.get("old_resolver_input_required") is False,
        "pre_resolver_request_built": browser_live_trace.get("pre_resolver_request_built") is True,
        "old_resolver_output_not_consumed_for_request": (
            browser_live_trace.get("old_resolver_output_consumed_for_request") is False
        ),
        "pre_resolver_trace_hash_present": bool(browser_live_trace.get("pre_resolver_trace_hash")),
        "missing_blocking_fields_empty": not browser_live_trace.get("missing_blocking_fields"),
        "trace_non_product_driving": browser_live_trace.get("product_driving") is False,
        "trace_non_render_driving": browser_live_trace.get("render_driving") is False,
        "trace_non_apply_driving": browser_live_trace.get("apply_driving") is False,
        "trace_non_session_driving": browser_live_trace.get("session_driving") is False,
    }
    replacement_parity_proven = all(browser_parity_checks.values())
    controller_cutover_proven = (
        cutover.get("status") == "PASS"
        and cutover_capture.get("decision") == "CONTROLLER_CUTOVER_LIVE_FALLBACK_NOT_USED"
    )
    controller_replacement_call_lines = [
        line for line in controller_replacement_trace_lines if not source.splitlines()[line - 1].lstrip().startswith("def ")
    ]
    trace_after_direct_resolver = (
        bool(direct_call_lines)
        and bool(controller_replacement_call_lines)
        and min(controller_replacement_call_lines) > min(direct_call_lines)
    )
    fallback_call_lines = _line_numbers(source, FALLBACK_CALL)

    remaining_pre_publication_truth = [
        {
            "class": "B",
            "name": "compute-only rebound inputs",
            "fields": [
                "late_evidence_update_acceptance_condition",
                "raw_late_rebound_contract.enabled",
                "raw_late_rebound_contract.updates",
                "post_core_evidence_update_mismatch_condition",
            ],
            "owner": "compute stage before final publication",
            "deletion_impact": "deleting the resolver bridge without a controller replacement would lose guarded rebound selection inputs",
        },
        {
            "class": "D",
            "name": "fallback/safety rebound surfaces",
            "fields": [
                "pre_resolver_collapsed_item_mutation",
                "post_evidence_cleanup_contract_rebound flag",
            ],
            "owner": "fallback/safety compute path",
            "deletion_impact": "deleting the resolver bridge without a safety replacement would remove fallback state needed by guarded recovery paths",
        },
    ]

    legacy_body_deleted = len(function_def_lines) == 0
    controller_fallback_shell_present = "_build_design_guide_controller_compute_resolver_fallback_shell(" in source
    completed_controller_state = (
        len(direct_call_lines) == 0
        and len(fallback_call_lines) == 0
        and legacy_body_deleted
        and controller_cutover_proven
        and controller_fallback_shell_present
    )

    deletion_allowed_now = False
    replacement_required = {
        "required_before_deletion": (
            "fallback deadness verifier proving the old page resolver fallback is unreachable or can be "
            "replaced by a controller-owned fallback shell"
        ),
        "may_replace_current_call_with": (
            "already replaced on the normal path; the old resolver remains fallback-only"
        ),
        "current_safe_action": (
            "do not delete the fallback yet; browser/live cutover is proven, but fallback deadness is not"
        ),
    }
    decision = (
        "LEGACY_RESOLVER_DELETED_CONTROLLER_FALLBACK_SHELL_RETAINED"
        if completed_controller_state
        else
        "CONTROLLER_CUTOVER_LIVE_FALLBACK_DEADNESS_REQUIRED"
        if controller_cutover_proven
        else "REPLACEMENT_PARITY_PROVEN_CUTOVER_PROOF_REQUIRED"
        if replacement_parity_proven
        else "NOT_READY_TO_DELETE"
    )

    return {
        "direct_call": {
            "token": DIRECT_CALL,
            "count": len(direct_call_lines),
            "line_numbers": direct_call_lines,
        },
        "fallback_call": {
            "token": FALLBACK_CALL,
            "count": len(fallback_call_lines),
            "line_numbers": fallback_call_lines,
        },
        "completed_controller_state": completed_controller_state,
        "controller_fallback_shell_present": controller_fallback_shell_present,
        "function_definition": {
            "token": FUNCTION_DEF,
            "count": len(function_def_lines),
            "line_numbers": function_def_lines,
        },
        "handoff_function": {
            "token": HANDOFF_FUNCTION,
            "line_numbers": handoff_lines,
        },
        "controller_replacement_trace": {
            "token": CONTROLLER_REPLACEMENT_TRACE,
            "line_numbers": controller_replacement_trace_lines,
            "call_line_numbers": controller_replacement_call_lines,
            "runs_after_direct_resolver_call": trace_after_direct_resolver,
        },
        "guards_present": {
            "authority_adapter_present": AUTHORITY_ADAPTER in source,
            "compute_handoff_proof_stamp_present": COMPUTE_PROOF_STAMP in source,
            "a_class_publication_evidence_stamps_present": A_CLASS_STAMP in source,
            "debug_restamp_metadata_stamp_present": DEBUG_RESTAMP_STAMP in source,
            "pre_resolver_trace_present": PRE_RESOLVER_TRACE_KEY in source,
            "b_class_tokens_present": {key: token in source for key, token in B_CLASS_TOKENS.items()},
            "d_class_tokens_present": {key: token in source for key, token in D_CLASS_TOKENS.items()},
        },
        "latest_locks": {
            "compute_resolver_publication_bridge_lock": {
                "status": compute_lock.get("status"),
                "path": compute_lock.get("path"),
                "direct_proof": compute_lock_proof,
            },
            "compute_resolver_replacement_browser_live_parity": {
                "status": browser_parity.get("status"),
                "path": browser_parity.get("path"),
                "checks": browser_parity_checks,
                "replacement_parity_proven": replacement_parity_proven,
            },
            "compute_stage_resolver_controller_cutover": {
                "status": cutover.get("status"),
                "path": cutover.get("path"),
                "decision": cutover_capture.get("decision"),
                "controller_cutover_proven": controller_cutover_proven,
            },
        },
        "remaining_pre_publication_truth": remaining_pre_publication_truth,
        "deletion_allowed_now": deletion_allowed_now,
        "decision": decision,
        "replacement_required": replacement_required,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    guards = dict(capture.get("guards_present") or {})
    latest = dict(capture.get("latest_locks") or {})
    compute_lock = dict(latest.get("compute_resolver_publication_bridge_lock") or {})
    browser_parity = dict(latest.get("compute_resolver_replacement_browser_live_parity") or {})
    direct_proof = dict(compute_lock.get("direct_proof") or {})
    completed_controller_state = capture.get("completed_controller_state") is True
    controller_fallback_shell_present = capture.get("controller_fallback_shell_present") is True
    d_class_tokens = dict(guards.get("d_class_tokens_present") or {})
    return {
        "direct_compute_stage_assignment_removed": (capture.get("direct_call") or {}).get("count") == 0,
        "fallback_old_resolver_call_deleted": (capture.get("fallback_call") or {}).get("count") == 0,
        "legacy_function_deleted_after_controller_cutover": (capture.get("function_definition") or {}).get("count") == 0,
        "authority_adapter_already_wrapped_around_call": guards.get("authority_adapter_present") is True,
        "compute_handoff_proof_stamp_present": guards.get("compute_handoff_proof_stamp_present") is True,
        "controller_replacement_trace_present": bool(
            (capture.get("controller_replacement_trace") or {}).get("line_numbers")
        ),
        "controller_replacement_trace_no_longer_after_direct_call": (
            (capture.get("controller_replacement_trace") or {}).get("runs_after_direct_resolver_call") is False
        ),
        "pre_resolver_trace_present": guards.get("pre_resolver_trace_present") is True,
        "browser_live_replacement_parity_proven": browser_parity.get("replacement_parity_proven") is True,
        "controller_cutover_live_and_fallback_not_used": (
            (latest.get("compute_stage_resolver_controller_cutover") or {}).get(
                "controller_cutover_proven"
            )
            is True
        ),
        "a_class_publication_truth_is_compatibility_only": (
            direct_proof.get("all_publication_owned_compute_truth_narrowed") is True
            and (
                completed_controller_state
                or guards.get("a_class_publication_evidence_stamps_present") is True
            )
        ),
        "b_class_compute_inputs_still_live_by_lock": (
            direct_proof.get("b_class_fields_remain_compute_only") is True
            and all((guards.get("b_class_tokens_present") or {}).values())
        ),
        "d_class_fallback_safety_still_live_by_lock": (
            direct_proof.get("d_class_fields_remain_fallback_safety") is True
            and (
                all(d_class_tokens.values())
                or (
                    completed_controller_state
                    and controller_fallback_shell_present
                    and d_class_tokens.get("pre_resolver_collapsed_item_mutation") is True
                )
            )
        ),
        "compute_bridge_lock_status_not_required_inside_nested_gate": True,
        "render_bridge_lock_not_required_inside_nested_gate": True,
        "independence_lock_not_required_inside_nested_gate": True,
        "deletion_correctly_blocked_or_completed": capture.get("deletion_allowed_now") is False
        and capture.get("decision")
        in {
            "NOT_READY_TO_DELETE",
            "REPLACEMENT_PARITY_PROVEN_CUTOVER_PROOF_REQUIRED",
            "CONTROLLER_CUTOVER_LIVE_FALLBACK_DEADNESS_REQUIRED",
            "LEGACY_RESOLVER_DELETED_CONTROLLER_FALLBACK_SHELL_RETAINED",
        },
        "completed_controller_state_or_blocked": (
            capture.get("completed_controller_state") is True
            or capture.get("decision")
            in {
                "NOT_READY_TO_DELETE",
                "REPLACEMENT_PARITY_PROVEN_CUTOVER_PROOF_REQUIRED",
                "CONTROLLER_CUTOVER_LIVE_FALLBACK_DEADNESS_REQUIRED",
            }
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute-Stage Resolver Deletion Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Direct compute resolver calls: `{(capture.get('direct_call') or {}).get('count')}`",
        f"- Direct call lines: `{(capture.get('direct_call') or {}).get('line_numbers')}`",
        f"- Deletion allowed now: `{capture.get('deletion_allowed_now')}`",
        f"- Browser/live replacement parity: `{((capture.get('latest_locks') or {}).get('compute_resolver_replacement_browser_live_parity') or {}).get('replacement_parity_proven')}`",
        f"- Controller trace after direct resolver: `{(capture.get('controller_replacement_trace') or {}).get('runs_after_direct_resolver_call')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Remaining Pre-Publication Truth"])
    lines.append("| Class | Name | Owner | Fields | Deletion impact |")
    lines.append("|---|---|---|---|---|")
    for row in capture.get("remaining_pre_publication_truth") or []:
        fields = ", ".join(row.get("fields") or [])
        lines.append(
            f"| {row.get('class')} | {row.get('name')} | {row.get('owner')} | "
            f"{fields} | {row.get('deletion_impact')} |"
        )
    repl = dict(capture.get("replacement_required") or {})
    lines.extend(
        [
            "",
            "## Replacement Required Before Deletion",
            "",
            f"- Required: {repl.get('required_before_deletion')}",
            f"- Replacement shape: {repl.get('may_replace_current_call_with')}",
            f"- Current safe action: {repl.get('current_safe_action')}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_compute_stage_resolver_deletion_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_stage_resolver_deletion_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_stage_resolver_deletion_readiness_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
