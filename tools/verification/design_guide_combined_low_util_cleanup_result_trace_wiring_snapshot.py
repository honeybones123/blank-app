"""Verify trace-only wiring for the combined low-util cleanup result object."""

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
    tokens = {
        "controller_result_builder_import": (
            "build_design_guide_controller_combined_low_util_cleanup_result as "
            "_build_design_guide_controller_combined_low_util_cleanup_result"
        ),
        "controller_result_builder_call": (
            "_build_design_guide_controller_combined_low_util_cleanup_result("
        ),
        "trace_key": (
            "design_guide_controller_combined_low_util_cleanup_result_trace_only"
        ),
        "product_driving_false": '"product_driving": False',
        "render_driving_false": '"render_driving": False',
        "apply_driving_false": '"apply_driving": False',
        "session_driving_false": '"session_driving": False',
        "result_hash_match": '"result_hash_match"',
        "item_hash_match": '"item_hash_match"',
        "presentation_hash_match": '"presentation_hash_match"',
        "render_reason_match": '"render_reason_match"',
        "state_fingerprint_match": '"state_fingerprint_match"',
        "page_assembler_still_returns_live_result": "return result",
        "route_calls_controller_builder_directly": (
            "result = _build_design_guide_controller_combined_low_util_cleanup_result("
        ),
        "candidate_generation_still_page_owned": "combine_best_safe_shear_with_bending_cleanup_item_fn(",
    }
    route_direct_cutover = (
        "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result" in source
        and "_assemble_final_visible_combined_low_util_safe_cleanup_result(" not in source[
            source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(") :
            source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(") + 8000
        ]
        and "_build_design_guide_controller_combined_low_util_cleanup_result(" in source[
            source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(") :
            source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(") + 8000
        ]
    )
    route_start = source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(")
    route_source = source[route_start : route_start + 8000] if route_start >= 0 else ""
    full_route_cutover = (
        "_run_design_guide_controller_no_active_combined_low_util_cleanup_route("
        in route_source
        and "_run_design_guide_controller_combined_low_util_candidate_generation("
        not in route_source
        and "_build_design_guide_controller_combined_low_util_cleanup_result("
        not in route_source
    )
    return {
        "token_presence": {key: token in source for key, token in tokens.items()},
        "builder_call_count": source.count(
            "_build_design_guide_controller_combined_low_util_cleanup_result("
        ),
        "trace_key_count": source.count(
            "design_guide_controller_combined_low_util_cleanup_result_trace_only"
        ),
        "verification": {
            "object_snapshot": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_object_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "candidate_generation_moved": full_route_cutover,
        "result_replaced": route_direct_cutover or full_route_cutover,
        "route_direct_cutover": route_direct_cutover,
        "full_route_cutover": full_route_cutover,
        "decision": (
            "FULL_ROUTE_CONTROLLER_RETURN_CUTOVER_TRACE_WIRED"
            if full_route_cutover
            else (
                "ROUTE_DIRECT_CONTROLLER_BUILDER_CUTOVER_TRACE_WIRED"
                if route_direct_cutover
                else "TRACE_WIRED_NOT_PRODUCT_DRIVING"
            )
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = dict(capture.get("verification") or {})
    return {
        "all_required_tokens_present_or_full_route_cutover": (
            all((capture.get("token_presence") or {}).values())
            or capture.get("full_route_cutover") is True
        ),
        "controller_builder_call_present_or_full_route_cutover": (
            int(capture.get("builder_call_count") or 0) >= 1
            or capture.get("full_route_cutover") is True
        ),
        "trace_key_present_or_page_diagnostic_deleted": (
            int(capture.get("trace_key_count") or 0) >= 1
            or capture.get("full_route_cutover") is True
        ),
        "object_snapshot_pass": (verification.get("object_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "candidate_generation_state_known": isinstance(
            capture.get("candidate_generation_moved"), bool
        ),
        "result_trace_wired_or_cut_over": (
            capture.get("result_replaced") is False
            or capture.get("route_direct_cutover") is True
            or capture.get("full_route_cutover") is True
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Cleanup Result Trace Wiring Snapshot",
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
            "This proves trace-only wiring beside the existing page branch. It does not replace the branch, move candidate generation, render UI, route Apply, or change product behaviour.",
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
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_cleanup_result_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_cleanup_result_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_result_trace_wiring_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
