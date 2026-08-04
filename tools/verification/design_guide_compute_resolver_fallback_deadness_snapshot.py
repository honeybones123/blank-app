"""Audit whether the old compute resolver fallback can be deleted.

Proof-only. The normal compute resolver path has been cut over to
DesignGuideController, but the old page resolver remains as a fallback. This
snapshot decides whether that fallback is dead now or still requires a
controller-owned fallback shell before deletion.
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

FALLBACK_CALL = "_legacy_fallback_resolution = resolve_final_visible_design_guide_item("
FALLBACK_USED_KEY = "design_guide_compute_resolver_controller_cutover_fallback_used"
CONTROLLER_USED_KEY = "design_guide_compute_resolver_controller_cutover_used"


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


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    browser = _latest("design_guide_compute_resolver_replacement_browser_live_parity")
    cutover = _latest("design_guide_compute_stage_resolver_controller_cutover")
    deletion = _latest("design_guide_compute_stage_resolver_deletion_readiness")
    replacement = _latest("design_guide_compute_stage_resolver_replacement_readiness")
    live = dict((browser.get("payload") or {}).get("live_trace") or {})
    fallback_call_lines = _line_numbers(source, FALLBACK_CALL)
    fallback_shell_present = (
        "_build_design_guide_controller_compute_resolver_fallback_shell(" in source
        and "DesignGuideController.compute_resolver_fallback_shell" in source
    )
    checks = {
        "old_fallback_call_deleted": len(fallback_call_lines) == 0,
        "controller_fallback_shell_present_or_dead_absent": fallback_shell_present
        or len(fallback_call_lines) == 0,
        "fallback_usage_stamped_or_dead_absent": (
            FALLBACK_USED_KEY in source and CONTROLLER_USED_KEY in source
        )
        or len(fallback_call_lines) == 0,
        "latest_browser_parity_pass": browser.get("status") == "PASS",
        "latest_browser_controller_used": live.get("controller_cutover_used") is True,
        "latest_browser_fallback_not_used": live.get("controller_cutover_fallback_used") is False,
        "cutover_snapshot_pass": cutover.get("status") == "PASS",
        "deletion_readiness_pass_or_completed_state": (
            deletion.get("status") == "PASS"
            or len(fallback_call_lines) == 0
        ),
        "replacement_readiness_pass_or_completed_state": (
            replacement.get("status") == "PASS"
            or len(fallback_call_lines) == 0
        ),
    }
    fallback_dead_now = all(checks.values()) and len(fallback_call_lines) == 0 and not fallback_shell_present
    controller_shell_retained = all(checks.values()) and fallback_shell_present
    return {
        "decision": (
            "FALLBACK_DEAD_DELETE_NEXT"
            if fallback_dead_now
            else "OLD_PAGE_FALLBACK_DELETED_CONTROLLER_SHELL_RETAINED_NON_AUTHORITATIVE"
            if controller_shell_retained
            else "FALLBACK_DELETION_BLOCKED_CONTROLLER_FALLBACK_SHELL_REQUIRED"
        ),
        "fallback_dead_now": bool(fallback_dead_now),
        "controller_shell_retained_non_authoritative": bool(controller_shell_retained),
        "fallback_has_controller_owned_error_shell": bool(fallback_shell_present),
        "checks": checks,
        "fallback_call_lines": fallback_call_lines,
        "latest_browser_parity": {
            "status": browser.get("status"),
            "path": browser.get("path"),
            "controller_cutover_used": live.get("controller_cutover_used"),
            "controller_cutover_fallback_used": live.get("controller_cutover_fallback_used"),
            "effective_selected_item_match": live.get("effective_selected_item_match"),
        },
        "latest_cutover": {
            "status": cutover.get("status"),
            "path": cutover.get("path"),
            "decision": (cutover.get("payload") or {}).get("capture", {}).get("decision"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute Resolver Fallback Deadness Snapshot",
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
            "## Fallback",
            "",
            f"- Fallback call lines: `{capture.get('fallback_call_lines')}`",
            f"- Fallback dead now: `{capture.get('fallback_dead_now')}`",
            f"- Controller-owned fallback shell present: `{capture.get('fallback_has_controller_owned_error_shell')}`",
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
                "If this snapshot and the composed locks remain green, the next cleanup "
                "slice can audit whether the old resolver function body itself still has "
                "live callers or can be decomposed/deleted branch by branch."
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
            "tools/verification/design_guide_compute_resolver_fallback_deadness_snapshot.py",
        ]
    )
    capture = _capture()
    failures: list[str] = []
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    for key, value in dict(capture.get("checks") or {}).items():
        if value is not True:
            failures.append(key)
    if (
        capture.get("fallback_dead_now") is not True
        and capture.get("controller_shell_retained_non_authoritative") is not True
    ):
        failures.append("fallback_deadness_not_proven")
    status = "PASS" if not failures else "PARTIAL"
    payload = {
        "schema": "design_guide_compute_resolver_fallback_deadness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "compile_run": compile_run,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_resolver_fallback_deadness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_resolver_fallback_deadness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"design_guide_compute_resolver_fallback_deadness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
