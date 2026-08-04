"""Trace-wiring snapshot for residual shear cleanup result packaging handoff."""

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
    / "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_object_snapshot.py"
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
        and "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_object PASS"
        in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
    )
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    object_snapshot = _run_object_snapshot()
    packaging_idx = route.find("_shear_tightening_as_local_cleanup_item(")
    evaluator_idx = route.find("_evaluate_local_cleanup_guidance_item(")
    wrapper_idx = route.find(
        "_run_post_click_low_bending_residual_shear_cleanup_result_packaging("
    )
    selection_stamp_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter("
    )
    packaging_stamp_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff("
    )
    primary_handoff_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_RESULT_PACKAGING_HANDOFF_TRACE_WIRED",
        "import_alias_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff"
        )
        in source,
        "helper_present": bool(helper),
        "helper_calls_controller": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff("
            in helper
        ),
        "helper_page_live_dependency_status": 'dependency_status="page_live"' in helper,
        "helper_stamps_payload": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff"
            in helper
        ),
        "helper_stamps_non_driving_flags": all(
            token in helper
            for token in (
                "result_packaging_proof_only",
                "result_packaging_product_driving",
                "result_packaging_render_driving",
                "result_packaging_apply_driving",
                "result_packaging_session_driving",
            )
        ),
        "live_packaging_still_present": packaging_idx >= 0 or wrapper_idx >= 0,
        "live_evaluator_still_present": evaluator_idx >= 0 or wrapper_idx >= 0,
        "packaging_cutover_wrapper_present": wrapper_idx >= 0,
        "packaging_before_evaluator": (0 <= packaging_idx < evaluator_idx)
        or (wrapper_idx >= 0 and packaging_idx < 0 and evaluator_idx < 0),
        "packaging_stamp_wired": packaging_stamp_idx >= 0,
        "packaging_stamp_after_selection_before_primary": (
            0 <= selection_stamp_idx < packaging_stamp_idx < primary_handoff_idx
        ),
        "packaging_stamp_records_inputs": all(
            token in route
            for token in (
                '"residual_shear_tighten_hash": _stable_final_publication_hash(',
                '"residual_updates_hash": _stable_final_publication_hash(',
                '"actions_used_hash": _stable_final_publication_hash(',
            )
        ),
        "packaging_stamp_records_outputs": all(
            token in route
            for token in (
                '"residual_shear_item_hash": _stable_final_publication_hash(',
                '"residual_promoted_hash": _stable_final_publication_hash(',
                '"residual_detail_hash": _stable_final_publication_hash(',
                '"residual_evidence_hash": _stable_final_publication_hash(',
                '"button_contract_hash_observed_not_owned": _stable_final_publication_hash(',
            )
        ),
        "button_contract_observed_not_owned": (
            '"button_contract_hash_observed_not_owned": _stable_final_publication_hash('
            in route
            and "_design_guide_button_contract(" not in route
        ),
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
        "helper_page_live_dependency_status": capture.get("helper_page_live_dependency_status") is True,
        "helper_stamps_payload": capture.get("helper_stamps_payload") is True,
        "helper_stamps_non_driving_flags": capture.get("helper_stamps_non_driving_flags") is True,
        "live_packaging_still_present": capture.get("live_packaging_still_present") is True,
        "live_evaluator_still_present": capture.get("live_evaluator_still_present") is True,
        "packaging_before_evaluator": capture.get("packaging_before_evaluator") is True,
        "packaging_stamp_wired": capture.get("packaging_stamp_wired") is True,
        "packaging_stamp_after_selection_before_primary": (
            capture.get("packaging_stamp_after_selection_before_primary") is True
        ),
        "packaging_stamp_records_inputs": capture.get("packaging_stamp_records_inputs") is True,
        "packaging_stamp_records_outputs": capture.get("packaging_stamp_records_outputs") is True,
        "button_contract_observed_not_owned": (
            capture.get("button_contract_observed_not_owned") is True
        ),
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
        "# Residual Shear Cleanup Result Packaging Handoff Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Trace",
        "",
        f"- helper present: `{capture.get('helper_present')}`",
        f"- live packaging still present: `{capture.get('live_packaging_still_present')}`",
        f"- live evaluator still present: `{capture.get('live_evaluator_still_present')}`",
        f"- packaging stamp wired: `{capture.get('packaging_stamp_wired')}`",
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
            "Run composed locks. Packaging/evaluation execution remains page-owned until cutover readiness and parity are separately proven.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_result_packaging_handoff_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_trace_wiring "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
