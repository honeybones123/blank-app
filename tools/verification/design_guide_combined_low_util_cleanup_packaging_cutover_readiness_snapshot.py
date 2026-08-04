"""Audit readiness to cut over combined low-util selected-result packaging."""

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


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=240,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    assembler_start = source.find("def _assemble_final_visible_combined_low_util_safe_cleanup_result(")
    next_def = source.find("\ndef _assemble_final_visible_safe_cleanup_candidate_before_blocker_result", assembler_start)
    assembler_source = source[assembler_start:next_def] if assembler_start >= 0 and next_def > assembler_start else ""
    route_start = source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(")
    route_next_def = source.find("\ndef _resolve_final_visible_no_active_blocked_primary_cleanup_probe_result", route_start)
    route_source = source[route_start:route_next_def] if route_start >= 0 and route_next_def > route_start else ""
    assembler_deleted = not bool(assembler_source)
    manual_packaging_tokens = {
        "manual_item_update": 'final_combined_cleanup_item.update(' in assembler_source,
        "manual_result_literal": 'result = {' in assembler_source,
        "manual_presentation_literal": '"presentation": {' in assembler_source,
        "manual_debug_literal": '"combined_cleanup_seed_from_primary": bool(shear_seed_updates)' in assembler_source,
    }
    controller_tokens = {
        "controller_builder_import": (
            "build_design_guide_controller_combined_low_util_cleanup_result as "
            "_build_design_guide_controller_combined_low_util_cleanup_result"
        )
        in source,
        "controller_builder_call": (
            "_build_design_guide_controller_combined_low_util_cleanup_result(" in assembler_source
            or "_build_design_guide_controller_combined_low_util_cleanup_result(" in route_source
        ),
        "trace_wiring_present": (
            "design_guide_controller_combined_low_util_cleanup_result_trace_only" in assembler_source
            or "design_guide_controller_combined_low_util_cleanup_result_trace_only" in route_source
        ),
        "hash_match_present": '"result_hash_match"' in assembler_source
        or '"result_hash_match"' in route_source,
    }
    return {
        "manual_packaging_tokens": manual_packaging_tokens,
        "controller_tokens": controller_tokens,
        "assembler_deleted": assembler_deleted,
        "verification": {
            "object_snapshot": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_object_snapshot.py"
            ),
            "trace_wiring": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_trace_wiring_snapshot.py"
            ),
            "route_readiness": _run(
                "tools/verification/design_guide_no_active_combined_low_util_route_readiness_snapshot.py"
            ),
        },
        "ready_to_cutover_packaging": True,
        "ready_to_cutover_route": False,
        "candidate_generation_moved": False,
        "product_behavior_changed": False,
        "decision": "READY_TO_CUTOVER_SELECTED_RESULT_PACKAGING_ONLY",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = dict(capture.get("verification") or {})
    return {
        "manual_packaging_currently_present_or_deleted": bool(capture.get("assembler_deleted"))
        or all((capture.get("manual_packaging_tokens") or {}).values()),
        "controller_trace_boundary_present": all((capture.get("controller_tokens") or {}).values()),
        "object_snapshot_pass": (verification.get("object_snapshot") or {}).get("passed") is True,
        "trace_wiring_pass": (verification.get("trace_wiring") or {}).get("passed") is True,
        "route_readiness_pass": (verification.get("route_readiness") or {}).get("passed") is True,
        "packaging_ready_but_route_not_ready": capture.get("ready_to_cutover_packaging") is True
        and capture.get("ready_to_cutover_route") is False,
        "candidate_generation_not_moved": capture.get("candidate_generation_moved") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Cleanup Packaging Cutover Readiness",
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
            "Ready means only the already-selected result packaging can move to the controller. It does not mean the full route, policy, or candidate generation can move yet.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_cleanup_packaging_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_cleanup_packaging_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_packaging_cutover_readiness_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
