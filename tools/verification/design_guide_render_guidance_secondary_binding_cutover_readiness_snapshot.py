"""Cutover-readiness proof for the render-guidance secondary primary binding.

This snapshot composes ownership, trace wiring, and adapter parity for the
render_guidance_secondary_primary_binding restamper callsite. It does not move
behaviour; it only declares whether a future narrow adapter-backed replacement
is ready to implement.
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

CALLSITE_ID = "render_guidance_secondary_primary_binding"
RESTAMPER_CALL = "item = _publish_final_visible_design_guide_contract_binding("
TRACE_CALL = "_stamp_final_visible_final_visible_output_bridge_proof("
CONTRACT_RENDER_CALL = "_apply_design_brain_publication_contract_for_render("


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


def _target_window() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    marker = f'callsite_id="{CALLSITE_ID}"'
    idx = source.find(marker)
    if idx < 0:
        return {"found": False, "line": None, "window": ""}
    start = max(0, idx - 1500)
    end = min(len(source), idx + 4200)
    line = source[:idx].count("\n") + 1
    return {"found": True, "line": line, "window": source[start:end]}


def _capture() -> dict[str, Any]:
    window_info = _target_window()
    window = str(window_info.get("window") or "")
    latest = {
        "ownership": _latest("design_guide_render_guidance_secondary_binding_ownership"),
        "trace_wiring": _latest("design_guide_render_guidance_secondary_binding_trace_wiring"),
        "adapter_parity": _latest("design_guide_render_guidance_secondary_binding_adapter_parity"),
        "post_render_readiness": _latest("design_guide_post_render_bridge_restamper_readiness"),
        "restamper_inventory": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    window_checks = {
        "callsite_found": bool(window_info.get("found")),
        "restamper_call_present": RESTAMPER_CALL in window,
        "trace_call_present": TRACE_CALL in window,
        "contract_render_call_after_binding": CONTRACT_RENDER_CALL in window,
        "binding_result_reassigned_to_guidance_items": "guidance_items[idx] = item" in window,
        "button_contract_recomputed_from_item": "button_contract = dict(item.get(\"button_contract\") or {})" in window,
        "old_binding_still_live": RESTAMPER_CALL in window,
    }
    readiness_inputs_pass = all(
        (latest.get(key) or {}).get("status") == "PASS"
        for key in (
            "ownership",
            "trace_wiring",
            "adapter_parity",
            "post_render_readiness",
            "render_bridge_lock",
            "compute_bridge_lock",
            "independence_lock",
        )
    )
    return {
        "decision": (
            "READY_FOR_NARROW_ADAPTER_BACKED_CUTOVER"
            if readiness_inputs_pass and all(window_checks.values())
            else "NOT_READY_FOR_CUTOVER"
        ),
        "callsite_id": CALLSITE_ID,
        "callsite_line": window_info.get("line"),
        "window_checks": window_checks,
        "latest": latest,
        "safe_to_replace_next": bool(readiness_inputs_pass and all(window_checks.values())),
        "safe_to_delete_now": False,
        "replacement_scope": "single render_guidance_secondary_primary_binding callsite only",
        "must_preserve": [
            "publication contract render enforcement",
            "button contract recomputation",
            "guidance_items item update",
            "CTA/apply semantics",
            "visible wording",
            "render ownership",
            "session/debug ownership",
        ],
        "recommended_next_slice": (
            "Replace only this restamper callsite with an adapter-backed output "
            "when the adapter output hash matches the live bound item. Keep the "
            "publication-contract render enforcement and downstream card logic live."
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
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "trace_wiring_latest_pass": (latest.get("trace_wiring") or {}).get("status") == "PASS",
        "adapter_parity_latest_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "post_render_readiness_latest_pass": (
            latest.get("post_render_readiness") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "safe_to_replace_next": capture.get("safe_to_replace_next") is True,
        "safe_to_delete_now_false": capture.get("safe_to_delete_now") is False,
        "decision_ready": capture.get("decision") == "READY_FOR_NARROW_ADAPTER_BACKED_CUTOVER",
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
        "# Render Guidance Secondary Binding Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scope",
        "",
        f"- Callsite: `{capture.get('callsite_id')}`",
        f"- Callsite line: `{capture.get('callsite_line')}`",
        f"- Replacement scope: `{capture.get('replacement_scope')}`",
        f"- Safe to replace next: `{capture.get('safe_to_replace_next')}`",
        f"- Safe to delete now: `{capture.get('safe_to_delete_now')}`",
        "",
        "## Window Checks",
        "",
    ]
    for key, value in (capture.get("window_checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
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
            "tools/verification/design_guide_render_guidance_secondary_binding_cutover_readiness_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_binding_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_binding_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_binding_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_guidance_secondary_binding_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
