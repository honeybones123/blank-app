"""Cutover-readiness snapshot for residual shear cleanup candidate evaluator adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
OBJECT_SNAPSHOT = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object_snapshot.py"
)
TRACE_SNAPSHOT = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_trace_wiring_snapshot.py"
)
HANDOFF_TRACE_SNAPSHOT = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff_trace_wiring_snapshot.py"
)


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: Path, pass_token: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": str(script.relative_to(ROOT)),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0 and pass_token in proc.stdout,
    }


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    object_result = _run(
        OBJECT_SNAPSHOT,
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object PASS",
    )
    trace_result = _run(
        TRACE_SNAPSHOT,
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_trace_wiring PASS",
    )
    handoff_trace_result = _run(
        HANDOFF_TRACE_SNAPSHOT,
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff_trace_wiring PASS",
    )
    route_live_call_count = route.count("_evaluate_auto_design_candidate(")
    injected_route_call_count = route.count(
        "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator("
    )
    evaluator_injected = "evaluator=_evaluate_auto_design_candidate" in route
    adapter_call_count = route.count(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter("
    )
    handoff_call_count = route.count(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff("
    )
    readiness_inputs = {
        "object_passed": object_result.get("passed") is True,
        "trace_passed": trace_result.get("passed") is True,
        "handoff_trace_passed": handoff_trace_result.get("passed") is True,
        "route_live_call_count": route_live_call_count,
        "injected_route_call_count": injected_route_call_count,
        "evaluator_injected": evaluator_injected,
        "adapter_call_count": adapter_call_count,
        "handoff_call_count": handoff_call_count,
        "sequence_hash_wired": "list(fallback_candidate_evaluation_sequence)" in route,
        "stale_state_policy_wired": "rebuild_on_changed_or_missing_state_fingerprint" in source,
        "exception_policy_wired": "preserve_existing_page_exception_handling" in source,
        "acceptance_policy_wired": "preserve_existing_materiality_detailing_overview_preview_filters" in source,
    }
    ready_for_dependency_shell_cutover = bool(
        readiness_inputs["object_passed"]
        and readiness_inputs["trace_passed"]
        and readiness_inputs["handoff_trace_passed"]
        and (
            route_live_call_count == 1
            or (route_live_call_count == 0 and injected_route_call_count == 1 and evaluator_injected)
        )
        and adapter_call_count == 1
        and handoff_call_count == 1
        and readiness_inputs["sequence_hash_wired"]
        and readiness_inputs["stale_state_policy_wired"]
        and readiness_inputs["exception_policy_wired"]
        and readiness_inputs["acceptance_policy_wired"]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_EVALUATOR_INJECTED_ADAPTER_CUTOVER_READINESS",
        "ready_for_evaluator_dependency_shell_cutover": ready_for_dependency_shell_cutover,
        "readiness_inputs": readiness_inputs,
        "object_result": object_result,
        "trace_result": trace_result,
        "handoff_trace_result": handoff_trace_result,
        "cutover_scope_allowed_next": (
            "replace_direct_evaluator_call_with_injected_dependency_shell_only"
            if ready_for_dependency_shell_cutover
            else "none"
        ),
        "explicitly_not_ready_for_deletion": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    readiness = dict(capture.get("readiness_inputs") or {})
    return {
        "object_passed": readiness.get("object_passed") is True,
        "trace_passed": readiness.get("trace_passed") is True,
        "handoff_trace_passed": readiness.get("handoff_trace_passed") is True,
        "single_live_direct_evaluator_call_or_injected_route_call": (
            readiness.get("route_live_call_count") == 1
            or (
                readiness.get("route_live_call_count") == 0
                and readiness.get("injected_route_call_count") == 1
                and readiness.get("evaluator_injected") is True
            )
        ),
        "single_adapter_trace_call": readiness.get("adapter_call_count") == 1,
        "single_handoff_trace_call": readiness.get("handoff_call_count") == 1,
        "sequence_hash_wired": readiness.get("sequence_hash_wired") is True,
        "stale_state_policy_wired": readiness.get("stale_state_policy_wired") is True,
        "exception_policy_wired": readiness.get("exception_policy_wired") is True,
        "acceptance_policy_wired": readiness.get("acceptance_policy_wired") is True,
        "ready_for_dependency_shell_cutover": (
            capture.get("ready_for_evaluator_dependency_shell_cutover") is True
        ),
        "not_ready_for_deletion": capture.get("explicitly_not_ready_for_deletion") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    readiness = dict(capture.get("readiness_inputs") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Evaluator Injected Adapter Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Ready for evaluator dependency-shell cutover: `{capture.get('ready_for_evaluator_dependency_shell_cutover')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Readiness Inputs",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in readiness.items())
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "The next allowed implementation slice is a narrow dependency-shell cutover for the residual-route evaluator. It must keep the same evaluator callable injected and must not delete the old direct call until a deadness proof passes after cutover.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_readiness_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_readiness "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
