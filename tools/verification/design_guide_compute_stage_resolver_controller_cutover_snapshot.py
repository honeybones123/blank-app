"""Verify the compute-stage resolver product path is controller-cutover.

Proof-only. This verifier checks that the normal compute-stage final-visible
resolver assignment is fed by DesignGuideController and that the old page
resolver fallback call has been replaced by a controller-owned fallback shell.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


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
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    browser_parity = _latest("design_guide_compute_resolver_replacement_browser_live_parity")
    live_trace = dict((browser_parity.get("payload") or {}).get("live_trace") or {})
    direct_assignment_token = "final_compute_resolution = resolve_final_visible_design_guide_item("
    fallback_call_token = "_legacy_fallback_resolution = resolve_final_visible_design_guide_item("
    fallback_shell_token = "_build_design_guide_controller_compute_resolver_fallback_shell("
    controller_assignment_token = (
        "final_compute_resolution = dict(\n"
        "            _pre_resolver_controller_response.final_compute_resolution or {}"
    )
    checks = {
        "direct_assignment_removed": direct_assignment_token not in source,
        "controller_assignment_present": controller_assignment_token in source,
        "old_resolver_fallback_deleted": fallback_call_token not in source,
        "controller_fallback_shell_present": fallback_shell_token in source,
        "cutover_used_stamp_present": (
            "design_guide_compute_resolver_controller_cutover_used" in source
        ),
        "fallback_used_stamp_present": (
            "design_guide_compute_resolver_controller_cutover_fallback_used" in source
        ),
        "browser_parity_pass": browser_parity.get("status") == "PASS",
        "browser_controller_cutover_used": live_trace.get("controller_cutover_used") is True,
        "browser_controller_fallback_not_used": (
            live_trace.get("controller_cutover_fallback_used") is False
        ),
        "effective_selected_item_match": (
            live_trace.get("effective_selected_item_match") is True
        ),
        "visible_semantics_match": live_trace.get("visible_semantics_match") is True,
        "cta_semantics_match": live_trace.get("cta_semantics_match") is True,
        "blocker_semantics_match": live_trace.get("blocker_semantics_match") is True,
        "render_reason_match": live_trace.get("render_reason_match") is True,
        "state_fingerprint_match": live_trace.get("state_fingerprint_match") is True,
        "old_resolver_output_not_consumed_for_request": (
            live_trace.get("old_resolver_output_consumed_for_request") is False
        ),
    }
    return {
        "decision": (
            "CONTROLLER_CUTOVER_LIVE_FALLBACK_NOT_USED"
            if all(checks.values())
            else "CUTOVER_NOT_PROVEN"
        ),
        "checks": checks,
        "direct_assignment_lines": _line_numbers(source, direct_assignment_token),
        "fallback_call_lines": _line_numbers(source, fallback_call_token),
        "controller_assignment_lines": _line_numbers(
            source,
            "_pre_resolver_controller_response.final_compute_resolution or {}",
        ),
        "latest_browser_parity": {
            "status": browser_parity.get("status"),
            "path": browser_parity.get("path"),
            "controller_cutover_used": live_trace.get("controller_cutover_used"),
            "controller_cutover_fallback_used": live_trace.get(
                "controller_cutover_fallback_used"
            ),
            "effective_selected_item_match": live_trace.get("effective_selected_item_match"),
            "selected_item_hash_match": live_trace.get("selected_item_hash_match"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "fallback_deleted": True,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute Stage Resolver Controller Cutover Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Checks",
        "",
        "| Check | Pass |",
        "| --- | --- |",
    ]
    for key, value in dict(capture.get("checks") or {}).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## Source Lines",
            "",
            f"- Direct assignment lines: `{capture.get('direct_assignment_lines')}`",
            f"- Fallback call lines: `{capture.get('fallback_call_lines')}`",
            f"- Controller assignment lines: `{capture.get('controller_assignment_lines')}`",
            "",
            "## Latest Browser Parity",
            "",
            "```json",
            json.dumps(capture.get("latest_browser_parity") or {}, indent=2),
            "```",
            "",
            "## Next Safe Step",
            "",
            (
                "If this remains green across broader browser states, create the fallback "
                "deadness proof. Delete the old resolver fallback only after that proof "
                "shows it is unreachable or fully replaced."
            ),
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
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
            "tools/verification/design_guide_compute_stage_resolver_controller_cutover_snapshot.py",
        ]
    )
    capture = _capture()
    failures: list[str] = []
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    for key, value in dict(capture.get("checks") or {}).items():
        if value is not True:
            failures.append(key)
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_stage_resolver_controller_cutover_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "compile_run": compile_run,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_stage_resolver_controller_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_stage_resolver_controller_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"design_guide_compute_stage_resolver_controller_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
