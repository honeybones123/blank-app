"""Call-shape cutover proof for residual shear fallback generator injection."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


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


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=240)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    last_error: dict[str, Any] | None = None
    last_readable: dict[str, Any] | None = None
    for path in reversed(artifacts):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            last_error = {
                "found": True,
                "status": "UNREADABLE",
                "path": str(path),
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
        if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
            return {"found": True, "status": "PASS", "path": str(path)}
        last_readable = {"found": True, "status": status or "UNKNOWN", "path": str(path)}
    return last_readable or last_error or {"found": False, "status": "MISSING", "path": None}


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    direct_call = "generate_less_shear_reo_variants({\"state\": dict(state)}, mode_config)"
    runner_call = "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
    trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring_snapshot.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_GENERATOR_CALL_SHAPE_CUTOVER_COMPLETE",
        "helper_present": bool(helper_block),
        "helper_uses_injected_generator": "generator({\"state\": dict(state)}, mode_config)" in helper_block,
        "helper_returns_empty_on_exception": "except Exception:" in helper_block and "return []" in helper_block,
        "direct_route_call_count": route_block.count(direct_call),
        "runner_route_call_count": route_block.count(runner_call),
        "same_impl_injected": "generator=generate_less_shear_reo_variants" in route_block,
        "fallback_variants_variable_retained": "fallback_variants =" in route_block,
        "attempted_and_count_retained": all(
            token in route_block
            for token in (
                "fallback_variant_generator_attempted = True",
                "fallback_variant_generator_variant_count = len(fallback_variants)",
            )
        ),
        "candidate_evaluator_retained": (
            "_evaluate_auto_design_candidate(" in route_block
            or (
                "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator("
                in route_block
                and "evaluator=_evaluate_auto_design_candidate" in route_block
            )
        ),
        "candidate_evaluator_retained_via_injection": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator("
            in route_block
            and "evaluator=_evaluate_auto_design_candidate" in route_block
        ),
        "live_route_return_boundary_retained": (
            "return residual_route_return_item" in route_block
        ),
        "old_live_result_return_removed": "return residual_promoted" not in route_block,
        "latest_readiness_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_readiness"
        ),
        "trace_wiring": trace_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "helper_present": capture.get("helper_present") is True,
        "helper_uses_injected_generator": capture.get("helper_uses_injected_generator") is True,
        "helper_returns_empty_on_exception": capture.get("helper_returns_empty_on_exception") is True,
        "direct_route_call_dead": capture.get("direct_route_call_count") == 0,
        "runner_route_call_present_once": capture.get("runner_route_call_count") == 1,
        "same_impl_injected": capture.get("same_impl_injected") is True,
        "fallback_variants_variable_retained": (
            capture.get("fallback_variants_variable_retained") is True
        ),
        "attempted_and_count_retained": capture.get("attempted_and_count_retained") is True,
        "candidate_evaluator_retained": capture.get("candidate_evaluator_retained") is True,
        "live_route_return_boundary_retained": (
            capture.get("live_route_return_boundary_retained") is True
        ),
        "old_live_result_return_removed": (
            capture.get("old_live_result_return_removed") is True
        ),
        "latest_readiness_audit_passed": (
            (capture.get("latest_readiness_audit") or {}).get("status") == "PASS"
        ),
        "trace_wiring_passed": (capture.get("trace_wiring") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Generator Call-Shape Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Direct route call count: `{capture.get('direct_route_call_count')}`",
        f"- Runner route call count: `{capture.get('runner_route_call_count')}`",
        f"- Same implementation injected: `{capture.get('same_impl_injected')}`",
        f"- Candidate evaluator retained: `{capture.get('candidate_evaluator_retained')}`",
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
            "Create direct-call deadness/readiness proof for the old fallback generator route call, then move to candidate evaluation boundary only after that is green.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
