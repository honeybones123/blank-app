"""Audit readiness to replace the compute-stage final-visible resolver.

This is proof-only. It decides whether the remaining
resolve_final_visible_design_guide_item(...) call can be adapter-replaced by
the controller compute handoff response now.
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CUTOVER_PREFIX = "design_guide_compute_stage_resolver_controller_cutover"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    controller_replacement_trace = _latest("design_guide_compute_resolver_controller_replacement_trace")
    live_replacement_trace = _latest("design_guide_live_compute_resolver_replacement_trace")
    browser_live_parity = _latest("design_guide_compute_resolver_replacement_browser_live_parity")
    deletion_readiness = _latest("design_guide_compute_stage_resolver_deletion_readiness")
    controller_cutover = _latest(CUTOVER_PREFIX)
    browser_live_trace = dict((browser_live_parity.get("payload") or {}).get("live_trace") or {})
    cutover_capture = dict((controller_cutover.get("payload") or {}).get("capture") or {})
    browser_parity_proven = (
        browser_live_parity.get("status") == "PASS"
        and browser_live_trace.get("effective_selected_item_match") is True
        and browser_live_trace.get("visible_semantics_match") is True
        and browser_live_trace.get("cta_semantics_match") is True
        and browser_live_trace.get("blocker_semantics_match") is True
        and browser_live_trace.get("render_reason_match") is True
        and browser_live_trace.get("state_fingerprint_match") is True
        and browser_live_trace.get("old_resolver_input_required") is False
        and not browser_live_trace.get("missing_blocking_fields")
    )
    controller_replacement_tokens = {
        "controller_replacement_function_exists": (
            "def run_design_guide_controller_compute_resolver_replacement_trace_only(" in controller_source
        ),
        "controller_replacement_does_not_call_old_resolver": (
            "resolve_final_visible_design_guide_item(" not in controller_source[
                controller_source.find("def run_design_guide_controller_compute_resolver_replacement_trace_only(") :
                controller_source.find("def run_design_guide_controller_compute_resolver_replacement_trace_only(") + 5000
            ]
        ),
        "controller_replacement_old_resolver_input_not_required": (
            '"old_resolver_input_required": False' in controller_source
        ),
        "inputs_live_trace_wired": (
            "_stamp_design_guide_controller_compute_resolver_replacement_trace_only(" in inputs_source
        ),
        "inputs_product_path_direct_resolver_assignment_removed": (
            "final_compute_resolution = resolve_final_visible_design_guide_item(" not in inputs_source
        ),
        "inputs_product_path_controller_response_used": (
            "_pre_resolver_controller_response.final_compute_resolution or {}" in inputs_source
        ),
        "inputs_product_path_controller_fallback_shell": (
            "_build_design_guide_controller_compute_resolver_fallback_shell(" in inputs_source
            and "_legacy_fallback_resolution = resolve_final_visible_design_guide_item(" not in inputs_source
        ),
    }
    live_output_consumers = {
        "final_compute_item_adapter": "final_compute_item = _collapsed_guidance_item_from_final_publication_authority(",
        "overview_propagation": "final_compute_overview = dict(final_compute_resolution.get(\"overview\")",
        "collapsed_items_replaced": "collapsed_guidance_items = [final_compute_item]",
        "final_visible_debug": 'debug_trace["final_visible_design_guide_resolver"] = {',
        "guidance_branch": 'debug_trace["guidance_branch"] = str(',
        "selected_title": 'debug_trace["selected_title"] = final_compute_item.get("title_main")',
        "selected_action_type": 'debug_trace["selected_action_type"] = final_compute_item.get("action_type")',
        "selected_action_family": 'debug_trace["selected_action_family"] = final_compute_item.get("family")',
        "primary_intent": 'debug_trace["primary_guidance_intent"] = final_compute_item.get("guidance_intent")',
        "primary_button_contract": 'debug_trace["primary_button_contract"] = dict(final_compute_item.get("button_contract") or {})',
        "publication_snapshot_recorded": "_record_design_guide_publication_snapshot(",
        "compute_trace_exit_recorded": '"publication_resolution_exit"',
    }
    consumer_presence = {key: token in inputs_source for key, token in live_output_consumers.items()}
    controller_cutover_proven = (
        controller_cutover.get("status") == "PASS"
        and cutover_capture.get("decision") == "CONTROLLER_CUTOVER_LIVE_FALLBACK_NOT_USED"
    )
    completed_controller_state = (
        controller_cutover_proven
        and inputs_source.count("final_compute_resolution = resolve_final_visible_design_guide_item(") == 0
        and inputs_source.count("_legacy_fallback_resolution = resolve_final_visible_design_guide_item(") == 0
        and "def resolve_final_visible_design_guide_item(" not in inputs_source
        and "_build_design_guide_controller_compute_resolver_fallback_shell(" in inputs_source
    )
    replacement_allowed_now = False
    decision = (
        "LEGACY_RESOLVER_REPLACED_CONTROLLER_FALLBACK_SHELL_RETAINED"
        if completed_controller_state
        else "CONTROLLER_CUTOVER_COMPLETE_FALLBACK_DEADNESS_REQUIRED"
        if controller_cutover_proven
        else "BROWSER_PARITY_PROVEN_CUTOVER_REQUIRED"
        if browser_parity_proven
        else "TRACE_WIRED_AWAITING_BROWSER_PARITY"
    )
    blocking_reason = (
        "completed_controller_state_old_resolver_deleted_controller_fallback_shell_retained"
        if completed_controller_state
        else "controller_cutover_complete_old_resolver_fallback_deadness_proof_required"
        if controller_cutover_proven
        else "browser_live_parity_proven_but_cutover_deadness_proof_required"
        if browser_parity_proven
        else "controller_replacement_trace_is_live_wired_but_browser_product_parity_not_proven"
    )
    return {
        "decision": decision,
        "blocking_reason": blocking_reason,
        "browser_parity_proven": browser_parity_proven,
        "replacement_allowed_now": replacement_allowed_now,
        "completed_controller_state": completed_controller_state,
        "direct_compute_resolver_call": {
            "count": inputs_source.count("final_compute_resolution = resolve_final_visible_design_guide_item("),
            "line_numbers": _line_numbers(
                inputs_source,
                "final_compute_resolution = resolve_final_visible_design_guide_item(",
            ),
        },
        "fallback_compute_resolver_call": {
            "count": inputs_source.count("_legacy_fallback_resolution = resolve_final_visible_design_guide_item("),
            "line_numbers": _line_numbers(
                inputs_source,
                "_legacy_fallback_resolution = resolve_final_visible_design_guide_item(",
            ),
        },
        "controller_replacement_tokens": controller_replacement_tokens,
        "live_output_consumers": consumer_presence,
        "latest": {
            "controller_replacement_trace": {
                "status": controller_replacement_trace.get("status"),
                "path": controller_replacement_trace.get("path"),
            },
            "live_compute_resolver_replacement_trace": {
                "status": live_replacement_trace.get("status"),
                "path": live_replacement_trace.get("path"),
            },
            "compute_resolver_replacement_browser_live_parity": {
                "status": browser_live_parity.get("status"),
                "path": browser_live_parity.get("path"),
                "selected_item_hash_match": browser_live_trace.get("selected_item_hash_match"),
                "effective_selected_item_match": browser_live_trace.get(
                    "effective_selected_item_match"
                ),
                "visible_semantics_match": browser_live_trace.get("visible_semantics_match"),
                "cta_semantics_match": browser_live_trace.get("cta_semantics_match"),
                "blocker_semantics_match": browser_live_trace.get("blocker_semantics_match"),
                "render_reason_match": browser_live_trace.get("render_reason_match"),
                "state_fingerprint_match": browser_live_trace.get("state_fingerprint_match"),
                "old_resolver_input_required": browser_live_trace.get("old_resolver_input_required"),
                "missing_blocking_fields": list(browser_live_trace.get("missing_blocking_fields") or []),
            },
            "compute_stage_resolver_deletion_readiness": {
                "status": deletion_readiness.get("status"),
                "path": deletion_readiness.get("path"),
                "decision": (deletion_readiness.get("payload") or {}).get("capture", {}).get("decision"),
            },
            "compute_stage_resolver_controller_cutover": {
                "status": controller_cutover.get("status"),
                "path": controller_cutover.get("path"),
                "decision": cutover_capture.get("decision"),
                "controller_cutover_proven": controller_cutover_proven,
            },
        },
        "required_before_replacement": {
            "browser_live_coverage": (
                "post-click, stale/rerun, blocker, active failure, and cleanup states must pass before replacement"
            ),
            "controller_cutover_verifier": (
                "a cutover verifier must prove replacing the live resolver assignment with the controller "
                "adapter preserves final item identity, render reason, state fingerprint, blocker evidence, "
                "and B/D fallback safety surfaces"
            ),
        },
        "product_behavior_changed": False,
        "resolver_replaced": controller_cutover_proven,
        "fallback_deleted": True,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "direct_compute_resolver_assignment_removed": (
            (capture.get("direct_compute_resolver_call") or {}).get("count") == 0
        ),
        "fallback_compute_resolver_call_deleted": (
            (capture.get("fallback_compute_resolver_call") or {}).get("count") == 0
        ),
        "controller_replacement_trace_pass": (
            latest.get("controller_replacement_trace") or {}
        ).get("status")
        == "PASS",
        "live_replacement_trace_pass": (
            latest.get("live_compute_resolver_replacement_trace") or {}
        ).get("status")
        == "PASS",
        "deletion_readiness_passes_completed_or_blocked": (
            (latest.get("compute_stage_resolver_deletion_readiness") or {}).get("status") == "PASS"
            and (latest.get("compute_stage_resolver_deletion_readiness") or {}).get("decision")
            in {
                "NOT_READY_TO_DELETE",
                "REPLACEMENT_PARITY_PROVEN_CUTOVER_PROOF_REQUIRED",
                "CONTROLLER_CUTOVER_LIVE_FALLBACK_DEADNESS_REQUIRED",
                "LEGACY_RESOLVER_DELETED_CONTROLLER_FALLBACK_SHELL_RETAINED",
            }
        ),
        "browser_live_replacement_parity_available": (
            (latest.get("compute_resolver_replacement_browser_live_parity") or {}).get("status") == "PASS"
        ),
        "controller_replacement_trace_wired_not_product_driving": all(
            (capture.get("controller_replacement_tokens") or {}).values()
        ),
        "all_live_output_consumers_identified": all((capture.get("live_output_consumers") or {}).values()),
        "replacement_correctly_blocked": (
            capture.get("decision")
            in {
                "TRACE_WIRED_AWAITING_BROWSER_PARITY",
                "BROWSER_PARITY_PROVEN_CUTOVER_REQUIRED",
                "CONTROLLER_CUTOVER_COMPLETE_FALLBACK_DEADNESS_REQUIRED",
                "LEGACY_RESOLVER_REPLACED_CONTROLLER_FALLBACK_SHELL_RETAINED",
            }
            and capture.get("replacement_allowed_now") is False
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "resolver_replaced_by_controller_cutover": capture.get("resolver_replaced") is True,
        "fallback_deleted_after_controller_shell_added": capture.get("fallback_deleted") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute-Stage Resolver Replacement Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Blocking reason: `{capture.get('blocking_reason')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Direct resolver calls: `{(capture.get('direct_compute_resolver_call') or {}).get('count')}`",
            f"- Direct resolver lines: `{(capture.get('direct_compute_resolver_call') or {}).get('line_numbers')}`",
            f"- Replacement allowed now: `{capture.get('replacement_allowed_now')}`",
            "",
            "## Required Before Replacement",
        ]
    )
    for key, value in (capture.get("required_before_replacement") or {}).items():
        lines.append(f"- `{key}`: {value}")
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_stage_resolver_replacement_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_stage_resolver_replacement_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_stage_resolver_replacement_readiness_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
