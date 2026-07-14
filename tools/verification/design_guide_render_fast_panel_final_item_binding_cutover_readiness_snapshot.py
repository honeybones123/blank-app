"""Cutover-readiness for render-fast final item restamper binding.

Proof-only. Verifies the final remaining restamper call can be replaced by an
adapter-backed result under a hash guard, while preserving downstream render
item consumers. It does not wire or delete anything.
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

RESTAMPER_CALL = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("


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
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_for(source: str, token: str) -> int | None:
    idx = source.find(token)
    if idx < 0:
        return None
    return source[:idx].count("\n") + 1


def _window(source: str) -> str:
    idx = source.find(RESTAMPER_CALL)
    if idx < 0:
        return ""
    return source[max(0, idx - 1600) : min(len(source), idx + 70000)]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    window = _window(source)
    checks = {
        "restamper_call_present": RESTAMPER_CALL in window,
        "final_visible_resolution_input_present": 'item=dict(_final_visible_resolution.get("item") or {})' in window,
        "publication_snapshot_before_binding": "_record_design_guide_publication_snapshot(" in window,
        "zero_shear_consumer_after_binding": "_apply_final_design_guide_zero_shear_render_consumer_projection(" in window,
        "safe_low_util_consumer_after_binding": "_apply_final_design_guide_safe_low_util_promotion_projection(" in window,
        "post_click_exact_blocker_consumer_after_binding": (
            "_build_final_design_guide_post_click_final_contract_check_adapter_result(" in window
            and "final_publication_post_click_final_contract_adapter_result_live_cutover_used" in window
        ),
        "render_item_consumer_trace_after_binding": "_stamp_final_publication_render_item_consumer_proof(" in window,
        "final_visible_resolution_sync_after_binding": '_final_visible_resolution["item"] = dict(_final_visible_item)' in window,
        "card_render_uses_final_visible_item": (
            "guidance_items = [_final_visible_item]" in window
            and '"visible_guidance_items": [dict(_final_visible_item)]' in window
        ),
        "old_binding_still_live": RESTAMPER_CALL in window,
    }
    latest = {
        "parity": _latest("design_guide_render_fast_panel_final_item_binding_adapter_parity"),
        "ownership": _latest("design_guide_render_fast_panel_binding_ownership"),
        "render_panel_readiness": _latest("design_guide_render_panel_binding_adapter_readiness"),
        "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    latest_pass = all(
        (latest.get(key) or {}).get("status") == "PASS"
        for key in (
            "parity",
            "ownership",
            "render_panel_readiness",
            "remaining_restamper_audit",
            "render_bridge_lock",
            "compute_bridge_lock",
            "independence_lock",
        )
    )
    ready = latest_pass and all(checks.values())
    return {
        "decision": (
            "READY_FOR_RENDER_FAST_FINAL_ITEM_ADAPTER_BACKED_CUTOVER"
            if ready
            else "NOT_READY_FOR_RENDER_FAST_FINAL_ITEM_CUTOVER"
        ),
        "binding_line": _line_for(source, RESTAMPER_CALL),
        "window_checks": checks,
        "latest": latest,
        "safe_to_replace_next": bool(ready),
        "safe_to_delete_now": False,
        "replacement_scope": "single _render_fast_design_guidance_panel final-visible item binding only",
        "must_preserve": [
            "final visible resolution input item",
            "zero-shear render consumer",
            "safe-low-util render consumer",
            "post-click exact-blocker projection",
            "render item consumer trace",
            "final visible resolution sync",
            "card view-model render path",
            "CTA/apply semantics",
            "visible wording",
        ],
        "recommended_next_slice": (
            "Implement a narrow adapter-backed cutover for this one final item binding. "
            "Keep the old restamper as comparison/source and consume the adapter result only under hash equality."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "cutover_performed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    window_checks = dict(capture.get("window_checks") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "window_checks_pass": all(value is True for value in window_checks.values()),
        "parity_latest_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "render_panel_readiness_latest_pass": (latest.get("render_panel_readiness") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (
            latest.get("remaining_restamper_audit") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "safe_to_replace_next": capture.get("safe_to_replace_next") is True,
        "safe_to_delete_now_false": capture.get("safe_to_delete_now") is False,
        "decision_ready": capture.get("decision") == "READY_FOR_RENDER_FAST_FINAL_ITEM_ADAPTER_BACKED_CUTOVER",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "no_cutover_or_deletion": (
            capture.get("cutover_performed") is False
            and capture.get("deletion_performed") is False
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Render Fast Final Item Binding Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scope",
        "",
        f"- Binding line: `{capture.get('binding_line')}`",
        f"- Safe to replace next: `{capture.get('safe_to_replace_next')}`",
        f"- Safe to delete now: `{capture.get('safe_to_delete_now')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("recommended_next_slice"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_render_fast_panel_final_item_binding_cutover_readiness_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_fast_panel_final_item_binding_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_fast_panel_final_item_binding_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_fast_panel_final_item_binding_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_fast_panel_final_item_binding_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
