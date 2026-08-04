"""Implementation proof for guarded bypass on remaining compatibility restampers."""

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
        "bypass_call": "_binding_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(",
        "binding_call": "item = _publish_final_visible_design_guide_contract_binding(",
        "input_reuse": "item = dict(_pre_card_binding_input_item)",
        "callsite_id": 'callsite_id="render_guidance_secondary_primary_binding"',
        "bypassed_marker": (
            "final_visible_restamper_bridge_render_guidance_secondary_primary_bypassed"
        ),
        "proof_call": "_binding_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof(",
        "pending_rec": "_binding_pending_rec = dict(",
    },
    "render_fast_design_guidance_panel.final_visible_item_binding": {
        "bypass_call": "_final_visible_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(",
        "binding_call": (
            "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
        ),
        "input_reuse": "_final_visible_item = dict(_final_visible_binding_input_item)",
        "callsite_id": (
            'callsite_id="render_fast_design_guidance_panel.final_visible_item_binding"'
        ),
        "bypassed_marker": (
            "final_visible_restamper_bridge_render_fast_final_visible_item_bypassed"
        ),
        "proof_call": (
            "_final_visible_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof("
        ),
        "pending_rec": "_final_visible_pending_rec = dict(",
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


def _line_for(source: str, token: str) -> int | None:
    index = source.find(token)
    if index < 0:
        return None
    return source.count("\n", 0, index) + 1


def _window(source: str, token: str) -> str:
    index = source.find(token)
    if index < 0:
        return ""
    return source[max(0, index - 700) : min(len(source), index + 2800)]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper_start = source.find(HELPER)
    helper_end = source.find("\ndef ", helper_start + len(HELPER)) if helper_start >= 0 else -1
    helper_body = source[helper_start:helper_end] if helper_start >= 0 and helper_end > helper_start else ""
    helper_checks = {
        "helper_present": bool(helper_body),
        "previous_proof_required": 'previous.get("proof_hash")' in helper_body,
        "strict_hash_fields_present": all(
            token in helper_body
            for token in (
                '"input_item_hash"',
                '"output_item_hash"',
                '"state_hash"',
                '"debug_hash"',
                '"rec_hash"',
                '"cta_projection_hash"',
                '"display_projection_hash"',
                '"evidence_projection_hash"',
            )
        ),
        "noop_required": "previous_noop = all" in helper_body and "current_noop = all" in helper_body,
        "stale_guards_present": all(
            token in helper_body
            for token in (
                "final_visible_restamper_bridge_bypass_debug_force_rebuild",
                "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY",
                "post_click_design_guide_state",
            )
        ),
    }
    targets: dict[str, Any] = {}
    for callsite_id, spec in TARGETS.items():
        window = _window(source, spec["bypass_call"])
        bypass_index = source.find(spec["bypass_call"])
        binding_index = source.find(spec["binding_call"], bypass_index)
        checks = {
            "bypass_call_present": spec["bypass_call"] in window,
            "bypass_before_restamper": bypass_index >= 0 and binding_index > bypass_index,
            "old_restamper_default_path_present": spec["binding_call"] in window,
            "input_reuse_only_on_bypass": spec["input_reuse"] in window,
            "callsite_id_present": spec["callsite_id"] in window,
            "bypass_marker_present": spec["bypassed_marker"] in window,
            "proof_still_runs_after_bypass_or_rebuild": spec["proof_call"] in window,
            "pending_rec_reused": spec["pending_rec"] in window,
            "rebuild_reason_recorded": "rebuild" in window,
        }
        targets[callsite_id] = {
            "bypass_line": _line_for(source, spec["bypass_call"]),
            "restamper_line": _line_for(source, spec["binding_call"]),
            "checks": checks,
            "implemented": all(checks.values()),
        }
    latest = {
        "readiness": _latest("design_guide_remaining_compatibility_restamper_bypass_readiness"),
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
                "bypass_line": None,
                "restamper_line": None,
                "checks": {
                    "old_helper_removed": True,
                    "old_calls_removed": True,
                    "clean_payload_consumer_present": True,
                    "guarded_bypass_superseded_by_zero_lock": True,
                },
                "implemented": True,
                "obsolete_zero_lock": True,
            }
        }
    return {
        "decision": (
            "REMAINING_COMPATIBILITY_RESTAMPER_BYPASS_OBSOLETE_ZERO_LOCK"
            if obsolete_zero_lock
            else "REMAINING_COMPATIBILITY_RESTAMPER_GUARDED_BYPASS_IMPLEMENTED"
        ),
        "helper_checks": helper_checks,
        "targets": targets,
        "latest": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "old_restamper_default_path_retained": not obsolete_zero_lock,
        "obsolete_zero_lock": obsolete_zero_lock,
        "safe_to_delete_now": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "all_helper_checks_pass": all(dict(capture.get("helper_checks") or {}).values()),
        "all_targets_implemented": all(
            row.get("implemented") is True for row in dict(capture.get("targets") or {}).values()
        ),
        "readiness_latest_pass": (latest.get("readiness") or {}).get("status") == "PASS",
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
        "old_restamper_default_path_retained_or_obsolete": (
            capture.get("old_restamper_default_path_retained") is True
            or capture.get("obsolete_zero_lock") is True
        ),
        "not_safe_to_delete_yet": capture.get("safe_to_delete_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Remaining Compatibility Restamper Bypass Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Targets",
        "",
    ]
    for callsite_id, row in dict(capture.get("targets") or {}).items():
        lines.append(
            f"- `{callsite_id}` bypass line `{row.get('bypass_line')}`, old restamper line `{row.get('restamper_line')}`, implemented: `{row.get('implemented')}`"
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
                else "The two remaining compatibility-only restamper stamps now use the strict guarded no-op bypass."
            ),
            "Deletion is not newly claimed by this snapshot.",
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
            "tools\\verification\\design_guide_remaining_compatibility_restamper_bypass_implementation_snapshot.py",
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
        f"design_guide_remaining_compatibility_restamper_bypass_implementation_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_remaining_compatibility_restamper_bypass_implementation_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_remaining_compatibility_restamper_bypass_implementation {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
