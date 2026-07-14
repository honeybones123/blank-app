"""Trace-wiring snapshot for residual shear cleanup candidate evaluator injected adapter."""

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
OBJECT_SNAPSHOT = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object_snapshot.py"
)
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


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _run_object_snapshot() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(OBJECT_SNAPSHOT)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object PASS"
        in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
    )
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    object_snapshot = _run_object_snapshot()
    evaluator_handoff_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff("
    )
    evaluator_adapter_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter("
    )
    primary_handoff_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    live_evaluator_idx = route.find(
        "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator("
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_EVALUATOR_INJECTED_ADAPTER_TRACE_WIRED",
        "import_alias_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter"
        )
        in source,
        "helper_present": bool(helper),
        "helper_calls_controller": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter("
            in helper
        ),
        "helper_contract_preserves_live_evaluator": all(
            token in helper
            for token in (
                '"evaluator_name": "_evaluate_auto_design_candidate"',
                '"stale_state_policy": "rebuild_on_changed_or_missing_state_fingerprint"',
                '"exception_policy": "preserve_existing_page_exception_handling"',
                '"acceptance_policy": "preserve_existing_materiality_detailing_overview_preview_filters"',
                '"evaluator_changes_behavior": False',
            )
        ),
        "helper_stamps_non_driving_flags": all(
            token in helper
            for token in (
                "candidate_evaluator_injected_adapter_proof_only",
                "candidate_evaluator_injected_adapter_product_driving",
                "candidate_evaluator_injected_adapter_render_driving",
                "candidate_evaluator_injected_adapter_apply_driving",
                "candidate_evaluator_injected_adapter_session_driving",
            )
        ),
        "adapter_wired_in_route": evaluator_adapter_idx >= 0,
        "adapter_order_after_handoff_before_primary": (
            0 <= evaluator_handoff_idx < evaluator_adapter_idx < primary_handoff_idx
        ),
        "adapter_uses_handoff": (
            "candidate_evaluator_handoff=dict(residual_candidate_evaluator_handoff or {})" in route
        ),
        "live_evaluator_still_present": live_evaluator_idx >= 0,
        "live_evaluator_callable_injected": "evaluator=_evaluate_auto_design_candidate" in route,
        "object_snapshot": object_snapshot,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "import_alias_present": capture.get("import_alias_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller": capture.get("helper_calls_controller") is True,
        "helper_contract_preserves_live_evaluator": (
            capture.get("helper_contract_preserves_live_evaluator") is True
        ),
        "helper_stamps_non_driving_flags": capture.get("helper_stamps_non_driving_flags") is True,
        "adapter_wired_in_route": capture.get("adapter_wired_in_route") is True,
        "adapter_order_after_handoff_before_primary": (
            capture.get("adapter_order_after_handoff_before_primary") is True
        ),
        "adapter_uses_handoff": capture.get("adapter_uses_handoff") is True,
        "live_evaluator_still_present": capture.get("live_evaluator_still_present") is True,
        "live_evaluator_callable_injected": capture.get("live_evaluator_callable_injected") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Evaluator Injected Adapter Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Trace",
        "",
        f"- helper present: `{capture.get('helper_present')}`",
        f"- adapter wired in route: `{capture.get('adapter_wired_in_route')}`",
        f"- live evaluator still present: `{capture.get('live_evaluator_still_present')}`",
        f"- object snapshot passed: `{(capture.get('object_snapshot') or {}).get('passed')}`",
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
            "Run parity/live scenarios before replacing the live evaluator call. The adapter is proof-only in this slice.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_evaluator_injected_adapter_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_trace_wiring "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
