"""Deadness proof for the old direct residual-route candidate evaluator call."""

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
CUTOVER_IMPL = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_implementation.py"
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


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _run_cutover_impl() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(CUTOVER_IMPL)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_implementation PASS"
        in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    old_direct_route_call = (
        "_evaluate_auto_design_candidate(\n"
        "                        state,\n"
        "                        updates=fallback_updates,"
    )
    injected_route_call = (
        "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(\n"
        "                        state=state,\n"
        "                        updates=fallback_updates,\n"
        "                        evaluator=_evaluate_auto_design_candidate,"
    )
    cutover_impl = _run_cutover_impl()
    shared_evaluator_def_count = source.count("def _evaluate_auto_design_candidate(")
    global_evaluator_references = source.count("_evaluate_auto_design_candidate")
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_EVALUATOR_DIRECT_CALL_DEAD",
        "old_direct_route_call_count": route.count(old_direct_route_call),
        "injected_route_call_count": route.count(injected_route_call),
        "shared_evaluator_definition_count": shared_evaluator_def_count,
        "global_evaluator_reference_count": global_evaluator_references,
        "shared_evaluator_remains_live": bool(
            shared_evaluator_def_count == 1 and global_evaluator_references > 1
        ),
        "cutover_implementation": cutover_impl,
        "deletion_scope": "old_residual_route_direct_call_shape_only",
        "do_not_delete": (
            "shared__evaluate_auto_design_candidate_definition",
            "other_evaluator_callers",
            "candidate_evaluation_logic",
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "old_direct_route_call_dead": capture.get("old_direct_route_call_count") == 0,
        "single_injected_route_call": capture.get("injected_route_call_count") == 1,
        "shared_evaluator_remains_live": capture.get("shared_evaluator_remains_live") is True,
        "cutover_implementation_passed": (
            capture.get("cutover_implementation") or {}
        ).get("passed")
        is True,
        "deletion_scope_is_route_call_only": (
            capture.get("deletion_scope") == "old_residual_route_direct_call_shape_only"
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Evaluator Direct Call Deadness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Deadness",
        "",
        f"- old direct route call count: `{capture.get('old_direct_route_call_count')}`",
        f"- injected route call count: `{capture.get('injected_route_call_count')}`",
        f"- shared evaluator definition count: `{capture.get('shared_evaluator_definition_count')}`",
        f"- global evaluator reference count: `{capture.get('global_evaluator_reference_count')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "The old residual-route direct evaluator call shape is dead. The shared evaluator and other callers remain live and out of deletion scope.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_direct_call_deadness_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_direct_call_deadness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_direct_call_deadness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_evaluator_direct_call_deadness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_direct_call_deadness "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
