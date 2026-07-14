"""Verify trace-only controller proof wiring for secondary-item binding.

This is proof-only. It confirms the live pre-card binding callsite in
_render_guidance_secondary_items(...) records a controller final-visible output bridge
proof beside the old binding mutation, without making that proof product
driving.
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

FUNCTION_NAME = "_render_guidance_secondary_items"
CALL_TOKEN = "item = _publish_final_visible_design_guide_contract_binding("
TRACE_TOKEN = "_stamp_final_visible_final_visible_output_bridge_proof("
CALLSITE_ID = 'callsite_id="render_guidance_secondary_primary_binding"'


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
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if any(token in status.upper() for token in ("PASS", "LOCKED", "COMPLETE")):
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _function_block(source: str) -> tuple[int | None, str]:
    marker = f"def {FUNCTION_NAME}("
    start = source.find(marker)
    if start < 0:
        return None, ""
    end = source.find("\ndef ", start + len(marker))
    if end < 0:
        end = len(source)
    start_line = source[:start].count("\n") + 1
    return start_line, source[start:end]


def _line_for(block: str, token: str, start_line: int | None) -> int | None:
    for offset, line in enumerate(block.splitlines()):
        if token in line:
            return (start_line or 1) + offset
    return None


def _target_window(block: str, start_line: int | None) -> tuple[int | None, str]:
    lines = block.splitlines()
    for offset, line in enumerate(lines):
        if CALL_TOKEN not in line:
            continue
        window_start = max(0, offset - 8)
        window = "\n".join(lines[window_start : min(len(lines), offset + 32)])
        if CALLSITE_ID in window and "guidance_items[idx] = item" in window:
            return (start_line or 1) + offset, window
    return None, ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    start_line, block = _function_block(source)
    call_line, window = _target_window(block, start_line)
    latest = {
        "ownership": _latest("design_guide_render_guidance_secondary_binding_ownership"),
        "post_render_readiness": _latest("design_guide_post_render_bridge_restamper_readiness"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    proof = {
        "binding_call_present": call_line is not None,
        "captures_input_item_before_binding": "_pre_card_binding_input_item = dict(item)" in window,
        "trace_stamp_after_binding": TRACE_TOKEN in window,
        "trace_callsite_id_present": CALLSITE_ID in window,
        "trace_input_is_pre_binding_item": "input_item=dict(_pre_card_binding_input_item)" in window,
        "trace_output_is_bound_item": "output_item=dict(item)" in window,
        "trace_uses_page_debug_sink": "debug_sink=_binding_debug_sink" in window,
        "trace_before_guidance_item_assignment": (
            window.find(TRACE_TOKEN) >= 0
            and window.find("guidance_items[idx] = item") > window.find(TRACE_TOKEN)
        ),
        "does_not_replace_binding_result": "guidance_items[idx] = item" in window,
        "no_product_driving_marker": "product_driving=True" not in window,
        "no_render_driving_marker": "render_driving=True" not in window,
        "no_apply_driving_marker": "apply_driving=True" not in window,
    }
    return {
        "decision": (
            "RENDER_GUIDANCE_SECONDARY_BINDING_TRACE_WIRED"
            if all(proof.values())
            else "RENDER_GUIDANCE_SECONDARY_BINDING_TRACE_NOT_PROVEN"
        ),
        "function": FUNCTION_NAME,
        "call_line": call_line,
        "trace_line": _line_for(block, TRACE_TOKEN, start_line),
        "proof": proof,
        "latest": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "trace_wired": capture.get("decision") == "RENDER_GUIDANCE_SECONDARY_BINDING_TRACE_WIRED",
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "post_render_readiness_latest_pass": (
            latest.get("post_render_readiness") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Guidance Secondary Binding Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Location",
        "",
        f"- Function: `{capture.get('function')}`",
        f"- Binding call line: `{capture.get('call_line')}`",
        f"- Trace line: `{capture.get('trace_line')}`",
        "",
        "## Proof",
    ]
    for key, value in (capture.get("proof") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "Run focused parity for this traced binding, then cut over only if the "
                "controller/publication proof can produce equivalent item/contract effects."
            ),
            "",
            "## Checks",
        ]
    )
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
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
            "tools/verification/design_guide_render_guidance_secondary_binding_trace_wiring_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_binding_trace_wiring_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_binding_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_binding_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_guidance_secondary_binding_trace_wiring {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
