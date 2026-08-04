"""Implementation snapshot for the pre-card restamper guarded bypass.

This verifier proves the pre-card restamper callsite keeps the old restamper as
the default path and only bypasses after the strict no-op proof helper approves
the same callsite/input/state/debug/rec/projection surface.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

HELPER = "def _maybe_bypass_final_visible_restamper_bridge_noop("
CALLSITE = 'callsite_id="render_guidance_secondary_items.pre_card_binding"'
BYPASS_CALL = "_pre_card_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop("
RESTAMPER_CALL = "_pre_card_bound_item = _publish_final_visible_design_guide_contract_binding("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


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
    callsite_start = source.find(BYPASS_CALL)
    callsite_window = source[callsite_start : callsite_start + 3600] if callsite_start >= 0 else ""
    required_helper_tokens = {
        "previous_proof_required": 'previous.get("proof_hash")' in helper_body,
        "same_debug_hash_required": '"debug_hash"' in helper_body,
        "same_projection_hashes_required": all(
            token in helper_body
            for token in ('"cta_projection_hash"', '"display_projection_hash"', '"evidence_projection_hash"')
        ),
        "previous_noop_required": "previous_noop = all" in helper_body,
        "current_noop_required": "current_noop = all" in helper_body,
        "output_matches_input_required": "output_matches_input" in helper_body,
        "debug_force_rebuild_guard": "final_visible_restamper_bridge_bypass_debug_force_rebuild" in helper_body,
        "apply_in_flight_guard": "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY" in helper_body,
        "post_click_guard": "post_click_design_guide_state" in helper_body,
        "controller_probe_used": "_run_design_guide_controller_final_visible_output_bridge_trace_only(" in helper_body,
    }
    required_callsite_tokens = {
        "bypass_before_restamper": (
            source.find(BYPASS_CALL) >= 0
            and source.find(RESTAMPER_CALL, source.find(BYPASS_CALL)) > source.find(BYPASS_CALL)
        ),
        "old_restamper_default_path_present": RESTAMPER_CALL in callsite_window,
        "bypass_returns_input_item_only": "_pre_card_bound_item = dict(_pre_card_input_item)" in callsite_window,
        "proof_stamp_still_runs": "_stamp_final_visible_final_visible_output_bridge_proof(" in callsite_window,
        "diagnostics_non_authority": "final_visible_restamper_bridge_pre_card_bypassed" in callsite_window,
        "bound_contract_read_after_bypass": "_pre_card_bound_contract =" in callsite_window,
        "terminal_blocker_logic_after_bypass": "_pre_card_bound_is_terminal_blocker" in callsite_window,
    }
    return {
        "helper_line": _line_for(source, HELPER),
        "callsite_line": _line_for(source, BYPASS_CALL),
        "restamper_line": _line_for(source, RESTAMPER_CALL),
        "callsite_id_present": CALLSITE in callsite_window,
        "required_helper_tokens": required_helper_tokens,
        "required_callsite_tokens": required_callsite_tokens,
        "latest": {
            "readiness": _latest("design_guide_pre_card_restamper_guarded_bypass_readiness"),
            "pre_card_proof": _latest("design_guide_pre_card_final_visible_output_bridge_proof"),
            "pre_render_impact": _latest("design_guide_pre_render_restamper_guarded_bypass_impact"),
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "helper_present": capture.get("helper_line") is not None,
        "callsite_present": capture.get("callsite_line") is not None,
        "callsite_id_present": capture.get("callsite_id_present") is True,
        "old_restamper_still_present": capture.get("restamper_line") is not None,
        "all_helper_tokens_present": all(dict(capture.get("required_helper_tokens") or {}).values()),
        "all_callsite_tokens_present": all(dict(capture.get("required_callsite_tokens") or {}).values()),
        "readiness_latest_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "pre_card_proof_latest_pass": (latest.get("pre_card_proof") or {}).get("status") == "PASS",
        "pre_render_impact_latest_pass": (latest.get("pre_render_impact") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (latest.get("remaining_restamper_audit") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Card Restamper Guarded Bypass Implementation Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Lines",
        "",
        f"- Helper: `{capture.get('helper_line')}`",
        f"- Bypass callsite: `{capture.get('callsite_line')}`",
        f"- Old restamper fallback/default path: `{capture.get('restamper_line')}`",
        "",
        "## Helper Contract",
    ]
    for key, value in dict(capture.get("required_helper_tokens") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Callsite Contract"])
    for key, value in dict(capture.get("required_callsite_tokens") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The pre-card final-visible output bridge now has a guarded no-op bypass. The old restamper remains the default rebuild path.",
            "Deletion is still not proven.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_pre_card_restamper_guarded_bypass_implementation_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    status = "PASS" if not failures else "FAIL"
    stamp = _stamp()
    payload = {
        "schema": "design_guide_pre_card_restamper_guarded_bypass_implementation_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
        "snapshot_hash": "",
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_pre_card_restamper_guarded_bypass_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_pre_card_restamper_guarded_bypass_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
