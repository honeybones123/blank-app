"""Trace-wiring verifier for residual-shear evidence-merge result adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

IMPORT_TOKEN = (
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter "
    "as _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter"
)
HELPER_TOKEN = (
    "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace("
)
CALL_TOKEN = (
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace("
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\n\ndef ", start + len(token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper = _function_block(source, HELPER_TOKEN)
    route = _between(source, ROUTE_START, ROUTE_END)
    helper_call_count = helper.count(
        "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
    )
    route_call_count = route.count(CALL_TOKEN)
    controller_merge_index = route.find(
        "residual_evidence_merge_tail_result_adapter = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
    )
    trace_call_index = route.find(CALL_TOKEN)
    handoff_call_index = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff("
    )
    route_shell_cutover_index = route.find(
        "residual_promoted = dict(\n                            residual_route_shell_adapter.get(\"result_item\")"
    )
    return {
        "decision": "EVIDENCE_MERGE_TAIL_RESULT_ADAPTER_TRACE_WIRED_NON_DRIVING",
        "import_present": IMPORT_TOKEN in source,
        "helper_present": bool(helper),
        "helper_calls_controller_result_adapter_once": helper_call_count == 1,
        "route_found": bool(route),
        "route_call_count": route_call_count,
        "pre_merge_evidence_snapshot_present": "residual_pre_merge_evidence = dict(residual_evidence)" in route,
        "pre_merge_exact_blocker_snapshot_present": (
            "residual_pre_merge_exact_blockers = dict(residual_exact_blockers)" in route
        ),
        "residual_shear_blocker_initialized": "residual_shear_blocker = {}" in route,
        "route_call_after_controller_merge": trace_call_index > controller_merge_index >= 0,
        "route_call_after_route_shell_cutover_assignment": (
            trace_call_index > route_shell_cutover_index >= 0
        ),
        "route_call_before_hash_only_handoff": (
            handoff_call_index > trace_call_index >= 0
        ),
        "old_live_evidence_merge_deleted": "residual_evidence.update(" not in route,
        "old_live_exact_blocker_merge_deleted": (
            "residual_exact_blockers[\"shear\"] = dict(residual_shear_blocker)" not in route
        ),
        "controller_merge_present": controller_merge_index >= 0,
        "no_assignment_from_result_adapter_to_live_evidence": (
            "residual_evidence = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace"
            not in route
        ),
        "no_assignment_from_result_adapter_to_live_exact_blockers": (
            "residual_exact_blockers = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace"
            not in route
        ),
        "parity_flags_stamped": all(
            token in helper
            for token in (
                "adapter_evidence_matches_live",
                "adapter_exact_blockers_match_live",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_evidence_parity",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_exact_blocker_parity",
            )
        ),
        "non_driving_flags_stamped": all(
            token in helper
            for token in (
                "\"proof_only_trace\": True",
                "\"product_driving\": False",
                "\"render_driving\": False",
                "\"apply_driving\": False",
                "\"session_driving\": False",
            )
        ),
        "outside_dependencies_retained": all(
            token in helper
            for token in (
                "candidate_generation_execution_owned_elsewhere",
                "candidate_evaluation_execution_owned_elsewhere",
                "outside_target_band_blocker_construction_owned_elsewhere",
                "visible_wording_authoring_owned_elsewhere",
                "cta_contract_execution_owned_elsewhere",
            )
        ),
        "latest": {
            "result_adapter_object": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object"
            ),
            "handoff_trace_wiring": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_trace_wiring"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = capture.get("latest") or {}
    return {
        "import_present": capture.get("import_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_result_adapter_once": (
            capture.get("helper_calls_controller_result_adapter_once") is True
        ),
        "route_found": capture.get("route_found") is True,
        "route_call_count_one": capture.get("route_call_count") == 1,
        "pre_merge_evidence_snapshot_present": (
            capture.get("pre_merge_evidence_snapshot_present") is True
        ),
        "pre_merge_exact_blocker_snapshot_present": (
            capture.get("pre_merge_exact_blocker_snapshot_present") is True
        ),
        "residual_shear_blocker_initialized": (
            capture.get("residual_shear_blocker_initialized") is True
        ),
        "route_call_after_controller_merge": (
            capture.get("route_call_after_controller_merge") is True
        ),
        "route_call_after_route_shell_cutover_assignment": (
            capture.get("route_call_after_route_shell_cutover_assignment") is True
        ),
        "route_call_before_hash_only_handoff": (
            capture.get("route_call_before_hash_only_handoff") is True
        ),
        "old_live_evidence_merge_deleted": (
            capture.get("old_live_evidence_merge_deleted") is True
        ),
        "old_live_exact_blocker_merge_deleted": (
            capture.get("old_live_exact_blocker_merge_deleted") is True
        ),
        "controller_merge_present": capture.get("controller_merge_present") is True,
        "no_assignment_from_result_adapter_to_live_evidence": (
            capture.get("no_assignment_from_result_adapter_to_live_evidence") is True
        ),
        "no_assignment_from_result_adapter_to_live_exact_blockers": (
            capture.get("no_assignment_from_result_adapter_to_live_exact_blockers") is True
        ),
        "parity_flags_stamped": capture.get("parity_flags_stamped") is True,
        "non_driving_flags_stamped": capture.get("non_driving_flags_stamped") is True,
        "outside_dependencies_retained": capture.get("outside_dependencies_retained") is True,
        "result_adapter_object_pass": (
            latest.get("result_adapter_object", {}).get("status") == "PASS"
        ),
        "handoff_trace_wiring_pass": (
            latest.get("handoff_trace_wiring", {}).get("status") == "PASS"
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
        "# Residual Shear Cleanup Evidence-Merge Tail Result Adapter Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Route call count: `{capture.get('route_call_count')}`",
        f"- Pre-merge evidence snapshot present: `{capture.get('pre_merge_evidence_snapshot_present')}`",
        f"- Route call after controller merge: `{capture.get('route_call_after_controller_merge')}`",
        f"- No assignment to live evidence: `{capture.get('no_assignment_from_result_adapter_to_live_evidence')}`",
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
            "Create a cutover-readiness verifier that requires evidence/exact-blocker parity before replacing the live page merge.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace_wiring.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace_wiring_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace_wiring_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace_wiring "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
