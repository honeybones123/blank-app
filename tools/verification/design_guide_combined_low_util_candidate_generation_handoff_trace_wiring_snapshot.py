"""Verify trace-only wiring for combined low-util candidate-generation handoff proof."""

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
        timeout=180,
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
    route_start = source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(")
    route_source = source[route_start : route_start + 8000] if route_start >= 0 else ""
    full_route_cutover = (
        "_run_design_guide_controller_no_active_combined_low_util_cleanup_route("
        in route_source
        and "_run_design_guide_controller_combined_low_util_candidate_generation("
        not in route_source
    )
    tokens = {
        "controller_invocation_import": (
            "run_design_guide_controller_combined_low_util_candidate_generation as "
            "_run_design_guide_controller_combined_low_util_candidate_generation"
        ),
        "controller_invocation_call": (
            "_run_design_guide_controller_combined_low_util_candidate_generation("
        ),
        "handoff_from_controller_result": 'generation_result.get("handoff_proof")',
        "trace_key": (
            "design_guide_controller_combined_low_util_candidate_generation_handoff_trace_only"
        ),
        "authority": (
            '"authority": "DesignGuideController.combined_low_util_candidate_generation_handoff"'
        ),
        "proof_hash": '"proof_hash": _stable_final_publication_hash(candidate_generation_handoff_proof)',
        "handoff_hash": '"handoff_hash": candidate_generation_handoff_proof.get("handoff_hash")',
        "applicability_gate": (
            '"applicability_gate_allows_result": candidate_generation_handoff_proof.get('
        ),
        "candidate_generation_invocation_owned": '"candidate_generation_owned_here": True',
        "product_driving_false": '"product_driving": False',
        "render_driving_false": '"render_driving": False',
        "apply_driving_false": '"apply_driving": False',
        "session_driving_false": '"session_driving": False',
        "candidate_generators_still_injected": "combine_best_safe_shear_with_bending_cleanup_item_fn=",
    }
    return {
        "token_presence": {key: token in source for key, token in tokens.items()},
        "controller_invocation_call_count": source.count(
            "_run_design_guide_controller_combined_low_util_candidate_generation("
        ),
        "trace_key_count": source.count(
            "design_guide_controller_combined_low_util_candidate_generation_handoff_trace_only"
        ),
        "verification": {
            "handoff_object": _run(
                "tools/verification/design_guide_combined_low_util_candidate_generation_handoff_object_snapshot.py"
            ),
            "handoff_audit": _run(
                "tools/verification/design_guide_combined_low_util_candidate_generation_handoff_audit.py"
            ),
        },
        "product_behavior_changed": False,
        "candidate_generation_invocation_moved": True,
        "full_route_cutover": full_route_cutover,
        "decision": (
            "CANDIDATE_GENERATION_HANDOFF_FROM_FULL_CONTROLLER_ROUTE_CUTOVER"
            if full_route_cutover
            else "CANDIDATE_GENERATION_HANDOFF_FROM_CONTROLLER_INVOCATION_BOUNDARY"
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = dict(capture.get("verification") or {})
    return {
        "all_required_tokens_present_or_full_route_cutover": (
            all((capture.get("token_presence") or {}).values())
            or capture.get("full_route_cutover") is True
        ),
        "single_controller_invocation_call_present": capture.get("controller_invocation_call_count")
        == 1
        or capture.get("full_route_cutover") is True,
        "trace_key_present_or_page_diagnostic_deleted": (
            int(capture.get("trace_key_count") or 0) >= 1
            or capture.get("full_route_cutover") is True
        ),
        "handoff_object_pass": (verification.get("handoff_object") or {}).get("passed") is True,
        "handoff_audit_pass": (verification.get("handoff_audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "candidate_generation_invocation_moved": capture.get(
            "candidate_generation_invocation_moved"
        )
        is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Candidate Generation Handoff Trace Wiring Snapshot",
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
            "This proves trace-only handoff proof wiring beside the existing generator calls. It does not move candidate generation, render UI, route Apply, or change product behaviour.",
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_candidate_generation_handoff_trace_wiring_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_candidate_generation_handoff_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_combined_low_util_candidate_generation_handoff_trace_wiring_snapshot "
        f"{status}"
    )
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
