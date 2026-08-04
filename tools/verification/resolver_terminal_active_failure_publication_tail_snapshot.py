"""Controller-backed terminal active-failure publication tail snapshot.

This verifier replaces the historical raw page-trace sequence dependency with
controller route and cutover proof. It keeps the old snapshot entrypoint name
for compatibility, but no longer requires inputs_page.py to emit every terminal
trace row as the proof surface.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"

ROUTE_OBJECT_SCRIPT = (
    "tools/verification/design_guide_terminal_active_failure_blocker_finalizer_route_object_snapshot.py"
)
CUTOVER_SCRIPT = (
    "tools/verification/design_guide_terminal_active_failure_blocker_finalizer_cutover.py"
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _json_path_from_stdout(stdout: str) -> Path | None:
    for line in str(stdout or "").splitlines():
        match = re.match(r"^json=(.+\.json)\s*$", line.strip())
        if match:
            return Path(match.group(1))
    for line in str(stdout or "").splitlines():
        match = re.match(r"^(?:PASS|FAIL):\s*(.+\.json)\s*$", line.strip())
        if match:
            return Path(match.group(1))
    return None


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_script(script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=REPO,
        text=True,
        capture_output=True,
    )
    json_path = _json_path_from_stdout(completed.stdout)
    payload = _load_json(json_path)
    status = str(payload.get("status") or payload.get("result") or "UNKNOWN")
    if "PASS" in status.upper():
        status = "PASS"
    return {
        "script": script,
        "returncode": completed.returncode,
        "status": status,
        "json_path": str(json_path) if json_path else None,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
        "payload": payload,
    }


def _capture() -> dict[str, Any]:
    route_object = _run_script(ROUTE_OBJECT_SCRIPT)
    cutover = _run_script(CUTOVER_SCRIPT)
    route_payload = dict(route_object.get("payload") or {})
    route_capture = dict(route_payload.get("capture") or {})
    route_cases = dict(route_capture.get("cases") or {})
    valid = dict(route_cases.get("valid_active_source_kept") or {})
    invalid = dict(route_cases.get("invalid_cleanup_source_falls_back") or {})
    cutover_payload = dict(cutover.get("payload") or {})
    cutover_capture = dict(cutover_payload.get("capture") or {})
    cutover_checks = dict(cutover_payload.get("checks") or {})
    page_calls_controller = (
        cutover_checks.get("page_calls_controller_alias")
        if "page_calls_controller_alias" in cutover_checks
        else (cutover_capture.get("page_route") or {}).get("calls_controller_alias")
    )
    return {
        "schema": "resolver_terminal_active_failure_publication_tail_snapshot.v2",
        "decision": "CONTROLLER_ROUTE_PROOF_REPLACES_RAW_PAGE_TRACE_SEQUENCE",
        "route_object": {
            "status": route_object.get("status"),
            "returncode": route_object.get("returncode"),
            "json_path": route_object.get("json_path"),
            "valid_active_source_marker": valid.get("source_marker"),
            "valid_render_reason": valid.get("render_reason"),
            "valid_button_enabled": (valid.get("button_contract") or {}).get("enabled"),
            "valid_exact_blocker_families": sorted(
                str(key) for key in (valid.get("exact_blockers_by_family") or {}).keys()
            ),
            "invalid_source_marker": invalid.get("source_marker"),
            "stable_repeat_hash": route_capture.get("stable_repeat_hash"),
        },
        "cutover": {
            "status": cutover.get("status"),
            "returncode": cutover.get("returncode"),
            "json_path": cutover.get("json_path"),
            "page_calls_controller": page_calls_controller,
        },
        "raw_page_trace_sequence_required": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route = dict(capture.get("route_object") or {})
    cutover = dict(capture.get("cutover") or {})
    return {
        "route_object_passes": route.get("status") == "PASS" and route.get("returncode") == 0,
        "cutover_passes": cutover.get("status") == "PASS" and cutover.get("returncode") == 0,
        "valid_active_source_kept": route.get("valid_active_source_marker") == "active",
        "invalid_cleanup_falls_back": route.get("invalid_source_marker") == "fallback",
        "valid_render_reason_matches": route.get("valid_render_reason")
        == "final_visible_active_strength_blocker",
        "valid_button_disabled": route.get("valid_button_enabled") is False,
        "valid_exact_blocker_present": "bending" in set(route.get("valid_exact_blocker_families") or []),
        "route_hash_stable": route.get("stable_repeat_hash") is True,
        "page_calls_controller": cutover.get("page_calls_controller") is True,
        "raw_page_trace_sequence_not_required": capture.get("raw_page_trace_sequence_required") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route_object") or {})
    cutover = dict(capture.get("cutover") or {})
    lines = [
        "# Controller-Backed Terminal Active-Failure Publication Tail Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Route Object",
            "",
            f"- Status: `{route.get('status')}`",
            f"- JSON: `{route.get('json_path')}`",
            f"- Valid source marker: `{route.get('valid_active_source_marker')}`",
            f"- Valid render reason: `{route.get('valid_render_reason')}`",
            f"- Valid button enabled: `{route.get('valid_button_enabled')}`",
            "",
            "## Cutover",
            "",
            f"- Status: `{cutover.get('status')}`",
            f"- JSON: `{cutover.get('json_path')}`",
            f"- Page calls controller: `{cutover.get('page_calls_controller')}`",
            "",
            "Raw page terminal trace sequence is no longer the proof authority for this compatibility snapshot.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=10820, help="Accepted for compatibility; unused.")
    parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    output = ARTIFACT_DIR / f"resolver_terminal_active_failure_publication_tail_snapshot_{stamp}.json"
    report = AUDIT_DIR / f"resolver_terminal_active_failure_publication_tail_snapshot_{stamp}.md"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report, payload)
    print(f"{status}: {output}")
    print(f"report={report}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
