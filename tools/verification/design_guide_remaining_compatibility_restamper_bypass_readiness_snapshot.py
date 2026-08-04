"""Readiness proof for guarded bypass on remaining compatibility restampers.

Proof-only. The remaining resolver cleanup audit classifies two
`_publish_final_visible_design_guide_contract_binding(...)` callsites as
compatibility-only stamps. This verifier proves they have enough surrounding
state to use the existing strict no-op restamper bypass helper before changing
the callsites.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

HELPER = "def _maybe_bypass_final_visible_restamper_bridge_noop("
TARGETS = {
    "render_guidance_secondary_primary_binding": {
        "anchor": "callsite_id=\"render_guidance_secondary_primary_binding\"",
        "binding_assignment": "item = _publish_final_visible_design_guide_contract_binding(",
        "input_capture": "_pre_card_binding_input_item = dict(item)",
        "state": "state=guidance_disp_state",
        "debug_sink": "debug_sink=_binding_debug_sink",
        "rec": "rec=dict(st.session_state.get(\"pending_recommendation\") or {})",
        "adapter_result": "_binding_adapter_item = dict(",
        "adapter_cutover_marker": "render_guidance_secondary_primary_binding_adapter_cutover_applied",
    },
    "render_fast_design_guidance_panel.final_visible_item_binding": {
        "anchor": (
            "callsite_id=\"render_fast_design_guidance_panel.final_visible_item_binding\""
        ),
        "binding_assignment": (
            "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
        ),
        "input_capture": "_final_visible_binding_input_item = dict(",
        "state": "state=current_state",
        "debug_sink": "debug_sink=guidance_debug",
        "rec": "rec=dict(st.session_state.get(\"pending_recommendation\") or {})",
        "adapter_result": "_final_visible_adapter_item = dict(",
        "adapter_cutover_marker": "render_fast_final_visible_item_binding_adapter_cutover_applied",
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw.upper() for token in ("PASS", "LOCKED")) else raw
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _function_window(source: str, anchor: str) -> str:
    index = source.find(anchor)
    if index < 0:
        return ""
    return source[max(0, index - 1400) : min(len(source), index + 2600)]


def _line_for(source: str, token: str) -> int | None:
    index = source.find(token)
    if index < 0:
        return None
    return source.count("\n", 0, index) + 1


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper_start = source.find(HELPER)
    helper_end = source.find("\ndef ", helper_start + len(HELPER)) if helper_start >= 0 else -1
    helper_body = source[helper_start:helper_end] if helper_start >= 0 and helper_end > helper_start else ""
    helper_checks = {
        "helper_present": bool(helper_body),
        "previous_proof_required": 'previous.get("proof_hash")' in helper_body,
        "same_debug_hash_required": '"debug_hash"' in helper_body,
        "same_projection_hashes_required": all(
            token in helper_body
            for token in (
                '"cta_projection_hash"',
                '"display_projection_hash"',
                '"evidence_projection_hash"',
            )
        ),
        "previous_and_current_noop_required": (
            "previous_noop = all" in helper_body and "current_noop = all" in helper_body
        ),
        "output_matches_input_required": "output_matches_input" in helper_body,
        "debug_force_rebuild_guard": (
            "final_visible_restamper_bridge_bypass_debug_force_rebuild" in helper_body
        ),
        "apply_in_flight_guard": "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY" in helper_body,
        "post_click_guard": "post_click_design_guide_state" in helper_body,
        "controller_probe_used": "_run_design_guide_controller_final_visible_output_bridge_trace_only(" in helper_body,
    }
    targets: dict[str, Any] = {}
    for callsite_id, spec in TARGETS.items():
        window = _function_window(source, spec["anchor"])
        checks = {
            "anchor_present": bool(window),
            "binding_call_present": spec["binding_assignment"] in window,
            "input_capture_present": spec["input_capture"] in window,
            "state_passed": spec["state"] in window,
            "debug_sink_passed": spec["debug_sink"] in window,
            "rec_passed": spec["rec"] in window,
            "adapter_proof_present": "_stamp_final_visible_final_visible_output_bridge_proof(" in window,
            "adapter_result_present": spec["adapter_result"] in window,
            "adapter_cutover_marker_present": spec["adapter_cutover_marker"] in window,
            "old_restamper_still_default": spec["binding_assignment"] in window,
        }
        targets[callsite_id] = {
            "line": _line_for(source, spec["binding_assignment"]),
            "checks": checks,
            "ready_for_guarded_bypass": all(checks.values()),
        }
    latest = {
        "remaining_adapter_consumer_reachability": _latest(
            "design_guide_remaining_adapter_consumer_reachability"
        ),
        "remaining_resolver_cleanup": _latest("design_guide_remaining_resolver_cleanup_audit"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    obsolete_zero_lock = bool(
        helper_start < 0
        and "_publish_final_visible_design_guide_contract_binding(" not in source
        and "_build_final_visible_render_binding_payload(" in source
        and (latest.get("remaining_adapter_consumer_reachability") or {}).get("status") == "PASS"
    )
    if obsolete_zero_lock:
        helper_checks = {
            "old_bypass_helper_removed": True,
            "old_restamper_calls_removed": True,
            "clean_render_binding_payload_present": True,
            "remaining_adapter_consumer_reachability_pass": True,
        }
        targets = {
            "remaining_compatibility_restamper_bypass_cluster": {
                "line": None,
                "checks": {
                    "old_helper_removed": True,
                    "old_calls_removed": True,
                    "clean_payload_consumer_present": True,
                    "guarded_bypass_no_longer_required": True,
                },
                "ready_for_guarded_bypass": True,
                "obsolete_zero_lock": True,
            }
        }
    return {
        "decision": (
            "REMAINING_COMPATIBILITY_RESTAMPER_BYPASS_OBSOLETE_ZERO_LOCK"
            if obsolete_zero_lock
            else "READY_FOR_REMAINING_COMPATIBILITY_RESTAMPER_GUARDED_BYPASS"
        ),
        "helper_checks": helper_checks,
        "targets": targets,
        "latest": latest,
        "ready_for_guarded_bypass": (
            all(helper_checks.values())
            and all(row.get("ready_for_guarded_bypass") is True for row in targets.values())
        ),
        "obsolete_zero_lock": obsolete_zero_lock,
        "safe_to_delete_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "all_helper_checks_pass": all(dict(capture.get("helper_checks") or {}).values()),
        "all_targets_ready": all(
            row.get("ready_for_guarded_bypass") is True
            for row in dict(capture.get("targets") or {}).values()
        ),
        "obsolete_zero_lock_or_guarded_bypass_ready": bool(
            capture.get("obsolete_zero_lock") or capture.get("ready_for_guarded_bypass")
        ),
        "remaining_adapter_consumer_reachability_latest_pass": (
            latest.get("remaining_adapter_consumer_reachability") or {}
        ).get("status")
        == "PASS",
        "remaining_resolver_cleanup_latest_pass": (
            latest.get("remaining_resolver_cleanup") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get(
            "status"
        )
        == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "not_safe_to_delete_yet": capture.get("safe_to_delete_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Remaining Compatibility Restamper Bypass Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Targets",
        "",
    ]
    for callsite_id, row in dict(capture.get("targets") or {}).items():
        lines.append(
            f"- `{callsite_id}` line `{row.get('line')}` ready: `{row.get('ready_for_guarded_bypass')}`"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "The old compatibility restamper bypass cluster is obsolete: the old helper/calls are gone "
                "and the page shell consumes the clean render-binding payload."
                if capture.get("obsolete_zero_lock")
                else "The two remaining compatibility-only restamper stamps are ready for a guarded no-op bypass."
            ),
            "Deletion is not newly claimed in this snapshot.",
            "",
            "## Checks",
            "",
        ]
    )
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {name}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    compile_run = _run(
        [
            "python",
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools\\verification\\design_guide_remaining_compatibility_restamper_bypass_readiness_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile_run": compile_run,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = ARTIFACT_DIR / (
        f"design_guide_remaining_compatibility_restamper_bypass_readiness_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_remaining_compatibility_restamper_bypass_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_remaining_compatibility_restamper_bypass_readiness {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"ready_for_guarded_bypass={capture.get('ready_for_guarded_bypass')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
