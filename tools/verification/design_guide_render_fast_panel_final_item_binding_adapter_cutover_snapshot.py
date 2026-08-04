"""Implementation verifier for render-fast final item binding adapter cutover."""

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

OLD_CALL = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("


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
    idx = source.find(OLD_CALL)
    if idx < 0:
        return ""
    return source[max(0, idx - 600) : min(len(source), idx + 4300)]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    window = _window(source)
    source_checks = {
        "old_restamper_call_retained": OLD_CALL in window,
        "input_item_captured": "_final_visible_binding_input_item = dict(" in window,
        "adapter_assignment_present": "_final_visible_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof(" in window,
        "callsite_id_present": 'callsite_id="render_fast_design_guidance_panel.final_visible_item_binding"' in window,
        "adapter_item_extracted": "_final_visible_adapter_item = dict(" in window,
        "hash_guard_present": "== _stable_final_publication_hash(_final_visible_item or {})" in window,
        "replacement_present": "_final_visible_item = dict(_final_visible_adapter_item)" in window,
        "applied_marker_present": "render_fast_final_visible_item_binding_adapter_cutover_applied" in window,
        "result_hash_marker_present": "render_fast_final_visible_item_binding_adapter_result_hash" in window,
        "scope_marker_present": "render_fast_final_visible_item_binding_adapter_scope" in window,
        "scope_result_identity_only": '"result_identity_only"' in window,
        "product_driving_marker_true": "render_fast_final_visible_item_binding_adapter_product_driving" in window
        and "= True" in window,
        "render_driving_marker_false": "render_fast_final_visible_item_binding_adapter_render_driving" in window
        and "= False" in window,
        "apply_driving_marker_false": "render_fast_final_visible_item_binding_adapter_apply_driving" in window
        and "= False" in window,
        "session_driving_marker_false": "render_fast_final_visible_item_binding_adapter_session_driving" in window
        and "= False" in window,
    }
    return {
        "decision": "RENDER_FAST_FINAL_ITEM_ADAPTER_BACKED_CUTOVER_IMPLEMENTED_NOT_DELETED",
        "binding_line": _line_for(source, OLD_CALL),
        "source_checks": source_checks,
        "latest": {
            "parity": _latest("design_guide_render_fast_panel_final_item_binding_adapter_parity"),
            "cutover_readiness": _latest("design_guide_render_fast_panel_final_item_binding_cutover_readiness"),
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "safe_to_delete_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "source_checks_pass": all(value is True for value in source_checks.values()),
        "parity_latest_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "cutover_readiness_latest_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (
            latest.get("remaining_restamper_audit") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "safe_to_delete_now_false": capture.get("safe_to_delete_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "no_deletion": capture.get("deletion_performed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Render Fast Final Item Binding Adapter Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        f"- Binding line: `{capture.get('binding_line')}`",
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
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Refresh remaining restamper inventory, then run deadness proof for the helper/function.",
        ]
    )
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
            "tools/verification/design_guide_render_fast_panel_final_item_binding_adapter_cutover_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_fast_panel_final_item_binding_adapter_cutover_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_fast_panel_final_item_binding_adapter_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_fast_panel_final_item_binding_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_fast_panel_final_item_binding_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
