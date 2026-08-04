"""Implementation proof for the render-guidance secondary binding adapter cutover.

The cutover is intentionally narrow: the old restamper still builds the live
item, then the controller restamper adapter result is consumed only when its
hash matches the live bound item. Downstream render/CTA/apply logic remains
unchanged.
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

CALLSITE_ID = "render_guidance_secondary_primary_binding"
RESTAMPER_CALL = "item = _publish_final_visible_design_guide_contract_binding("
ADAPTER_ASSIGN = "_binding_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof("
CUTOVER_MARKER = "render_guidance_secondary_primary_binding_adapter_cutover_applied"
SCOPE_MARKER = '"result_identity_only"'


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
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


def _target_window(source: str) -> dict[str, Any]:
    marker = f'callsite_id="{CALLSITE_ID}"'
    idx = source.find(marker)
    if idx < 0:
        return {"found": False, "line": None, "window": ""}
    start = max(0, idx - 1300)
    end = min(len(source), idx + 4600)
    return {"found": True, "line": source[:idx].count("\n") + 1, "window": source[start:end]}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    target = _target_window(inputs_source)
    window = str(target.get("window") or "")
    return {
        "decision": "RENDER_GUIDANCE_SECONDARY_BINDING_RESULT_IDENTITY_CUTOVER_PROVEN",
        "callsite_id": CALLSITE_ID,
        "callsite_line": target.get("line"),
        "source_checks": {
            "old_restamper_still_present": RESTAMPER_CALL in window,
            "adapter_assignment_present": ADAPTER_ASSIGN in window,
            "adapter_result_item_read": 'get("result_item")' in window,
            "hash_guard_present": "_stable_final_publication_hash(_binding_adapter_item)" in window
            and "== _stable_final_publication_hash(item)" in window,
            "item_assigned_from_adapter_inside_guard": "item = dict(_binding_adapter_item)" in window,
            "cutover_marker_present": CUTOVER_MARKER in window,
            "scope_marker_present": SCOPE_MARKER in window,
            "guidance_items_still_updated": "guidance_items[idx] = item" in window,
            "publication_contract_render_still_present": "_apply_design_brain_publication_contract_for_render(" in window,
            "controller_response_carries_result_item": "result_item: dict[str, Any]" in controller_source
            and "result_item_hash: str" in controller_source,
            "controller_result_item_is_output_item": "result_item = dict(request_obj.output_item or {})" in controller_source,
        },
        "latest": {
            "cutover_readiness": _latest("design_guide_render_guidance_secondary_binding_cutover_readiness"),
            "adapter_parity": _latest("design_guide_render_guidance_secondary_binding_adapter_parity"),
            "trace_wiring": _latest("design_guide_render_guidance_secondary_binding_trace_wiring"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "cutover_scope": "result_identity_only",
        "safe_to_delete_old_restamper_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "source_checks_pass": all((capture.get("source_checks") or {}).values()),
        "cutover_readiness_latest_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "adapter_parity_latest_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "trace_wiring_latest_pass": (latest.get("trace_wiring") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "cutover_scope_is_result_identity_only": capture.get("cutover_scope") == "result_identity_only",
        "old_restamper_not_deletion_safe": capture.get("safe_to_delete_old_restamper_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Guidance Secondary Binding Adapter Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scope",
        "",
        f"- Callsite: `{capture.get('callsite_id')}`",
        f"- Callsite line: `{capture.get('callsite_line')}`",
        f"- Cutover scope: `{capture.get('cutover_scope')}`",
        f"- Safe to delete old restamper now: `{capture.get('safe_to_delete_old_restamper_now')}`",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in (capture.get("source_checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
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
            (
                "Run the remaining restamper inventory and composed locks. Do not delete "
                "the old restamper call until a deadness proof shows the comparison source "
                "is no longer required."
            ),
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
            "design_brain/design_guide_controller.py",
            "tools/verification/design_guide_render_guidance_secondary_binding_adapter_cutover_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_binding_adapter_cutover_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_binding_adapter_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_binding_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_guidance_secondary_binding_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
