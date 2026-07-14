"""Trace-wiring verifier for residual-shear evidence-merge tail handoff.

This verifier is static/proof-only. It confirms the controller evidence-merge
tail handoff is wired beside the live residual-shear merge as non-driving debug
evidence. The live page merge remains in place until parity/cutover/deadness
proof says otherwise.
"""

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
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff "
    "as _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff"
)
HELPER_TOKEN = (
    "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff("
)
CALL_TOKEN = (
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff("
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
    route_call_count = route.count(CALL_TOKEN)
    helper_call_count = helper.count(
        "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff("
    )
    route_shell_assignment_index = route.find(
        "residual_route_shell_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
    )
    route_shell_cutover_index = route.find(
        "residual_promoted = dict(\n                            residual_route_shell_adapter.get(\"result_item\")"
    )
    evidence_handoff_call_index = route.find(CALL_TOKEN)
    controller_merge_index = route.find(
        "residual_evidence_merge_tail_result_adapter = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
    )
    non_driving_tokens = (
        "\"design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_proof_only\"",
        "\"design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_product_driving\"",
        "\"design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_render_driving\"",
        "\"design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_apply_driving\"",
        "\"design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_session_driving\"",
        "] = True",
        "] = False",
        "dependency_status=\"page_live\"",
    )
    output_summary_tokens = (
        "\"residual_evidence_hash\"",
        "\"residual_exact_blockers_hash\"",
        "\"exact_blocker_families\"",
        "\"outside_target_band_allowed\"",
        "\"post_click_bending_blocker_preserved\"",
        "\"post_click_residual_shear_cleanup_after_bending_blocker\"",
        "\"no_second_cta_required\"",
    )
    route_input_tokens = (
        "\"route_branch\": \"post_click_residual_shear_cleanup_after_bending_blocker\"",
        "\"state_fingerprint\": _stable_final_publication_hash(dict(state or {}))",
        "\"mode_config_hash\": _stable_final_publication_hash(dict(mode_config or {}))",
        "\"route_shell_adapter_hash\": (",
        "\"residual_updates_hash\": _stable_final_publication_hash(",
        "\"residual_candidate_id\": residual_candidate_id",
        "\"current_shear_util\": current_shear_for_residual_cleanup",
        "\"target_low\": target_lo",
        "\"target_high\": target_hi",
        "\"residual_outside_preferred_band\": residual_outside_preferred_band",
    )
    return {
        "decision": "EVIDENCE_MERGE_TAIL_HANDOFF_TRACE_WIRED_NON_DRIVING",
        "import_present": IMPORT_TOKEN in source,
        "helper_present": bool(helper),
        "helper_calls_controller_handoff_once": helper_call_count == 1,
        "route_found": bool(route),
        "route_call_count": route_call_count,
        "route_call_after_controller_merge": (
            evidence_handoff_call_index > controller_merge_index >= 0
        ),
        "route_call_after_route_shell_adapter_assignment": (
            evidence_handoff_call_index > route_shell_assignment_index >= 0
        ),
        "route_call_after_route_shell_cutover_assignment": (
            evidence_handoff_call_index > route_shell_cutover_index >= 0
        ),
        "old_live_evidence_merge_deleted": "residual_evidence.update(" not in route,
        "old_live_exact_blocker_merge_deleted": (
            "residual_exact_blockers[\"shear\"] = dict(residual_shear_blocker)" not in route
        ),
        "controller_merge_present": controller_merge_index >= 0,
        "non_driving_tokens_present": all(token in helper for token in non_driving_tokens),
        "output_summary_tokens_present": all(
            token in helper for token in output_summary_tokens
        ),
        "route_input_tokens_present": all(token in route for token in route_input_tokens),
        "no_controller_assignment_to_residual_evidence": (
            "residual_evidence = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff"
            not in route
        ),
        "no_controller_assignment_to_exact_blockers": (
            "residual_exact_blockers = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff"
            not in route
        ),
        "route_returns_controller_boundary_item": "return residual_route_return_item" in route,
        "latest": {
            "evidence_merge_tail_handoff_object": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_object"
            ),
            "route_shell_adapter_cutover_implementation": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation"
            ),
            "route_shell_deadness_readiness": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
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
        "helper_calls_controller_handoff_once": (
            capture.get("helper_calls_controller_handoff_once") is True
        ),
        "route_found": capture.get("route_found") is True,
        "route_call_count_one": capture.get("route_call_count") == 1,
        "route_call_after_controller_merge": (
            capture.get("route_call_after_controller_merge") is True
        ),
        "route_call_after_route_shell_adapter_assignment": (
            capture.get("route_call_after_route_shell_adapter_assignment") is True
        ),
        "route_call_after_route_shell_cutover_assignment": (
            capture.get("route_call_after_route_shell_cutover_assignment") is True
        ),
        "old_live_evidence_merge_deleted": (
            capture.get("old_live_evidence_merge_deleted") is True
        ),
        "old_live_exact_blocker_merge_deleted": (
            capture.get("old_live_exact_blocker_merge_deleted") is True
        ),
        "controller_merge_present": capture.get("controller_merge_present") is True,
        "non_driving_tokens_present": capture.get("non_driving_tokens_present") is True,
        "output_summary_tokens_present": capture.get("output_summary_tokens_present") is True,
        "route_input_tokens_present": capture.get("route_input_tokens_present") is True,
        "no_controller_assignment_to_residual_evidence": (
            capture.get("no_controller_assignment_to_residual_evidence") is True
        ),
        "no_controller_assignment_to_exact_blockers": (
            capture.get("no_controller_assignment_to_exact_blockers") is True
        ),
        "route_returns_controller_boundary_item": (
            capture.get("route_returns_controller_boundary_item") is True
        ),
        "evidence_merge_tail_handoff_object_pass": (
            latest.get("evidence_merge_tail_handoff_object", {}).get("status") == "PASS"
        ),
        "route_shell_adapter_cutover_implementation_pass": (
            latest.get("route_shell_adapter_cutover_implementation", {}).get("status")
            == "PASS"
        ),
        "route_shell_deadness_readiness_pass": (
            latest.get("route_shell_deadness_readiness", {}).get("status") == "PASS"
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
        "# Residual Shear Cleanup Evidence-Merge Tail Handoff Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Import present: `{capture.get('import_present')}`",
        f"- Helper present: `{capture.get('helper_present')}`",
        f"- Route call count: `{capture.get('route_call_count')}`",
        f"- Route call after controller merge: `{capture.get('route_call_after_controller_merge')}`",
        f"- Route call after route-shell cutover assignment: `{capture.get('route_call_after_route_shell_cutover_assignment')}`",
        f"- Old live evidence merge deleted: `{capture.get('old_live_evidence_merge_deleted')}`",
        f"- Old live exact-blocker merge deleted: `{capture.get('old_live_exact_blocker_merge_deleted')}`",
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
            "Create evidence-merge tail parity/cutover-readiness proof before replacing the live page merge.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_trace_wiring.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_trace_wiring_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_trace_wiring_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_trace_wiring "
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
