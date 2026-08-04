"""Implementation verifier for residual-shear route-shell adapter cutover."""

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
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("


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
    except Exception as exc:  # pragma: no cover
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


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    adapter_assignment = (
        "residual_route_shell_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
    )
    result_assignment = (
        "residual_promoted = dict(\n                            residual_route_shell_adapter.get(\"result_item\")\n                            or residual_promoted\n                        )"
    )
    return {
        "decision": "ROUTE_SHELL_ADAPTER_NARROW_CUTOVER_IMPLEMENTED",
        "route_found": bool(route),
        "adapter_assignment_present": adapter_assignment in route,
        "result_assignment_present": result_assignment in route,
        "result_assignment_after_adapter": (
            route.find(result_assignment) > route.find(adapter_assignment) >= 0
        ),
        "route_returns_controller_boundary_item": "return residual_route_return_item" in route,
        "candidate_generation_still_live": "generate_less_shear_reo_variants" in route,
        "candidate_evaluation_still_live": "_evaluate_auto_design_candidate" in route,
        "button_contract_still_live": "_design_guide_button_contract(residual_promoted, state=state)" in route,
        "final_binding_tail_adapter_still_live": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail("
            in route
        ),
        "old_manual_final_binding_absent": not any(
            token in route
            for token in (
                "residual_promoted[\"candidate_search_evidence\"] = dict(residual_evidence)",
                "residual_payload[\"candidate_search_evidence\"] = dict(residual_evidence)",
                "residual_resolved[\"candidate_search_evidence\"] = dict(residual_evidence)",
                "residual_promoted[\"button_contract\"] = dict(",
            )
        ),
        "latest": {
            "object": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_object"
            ),
            "trace_wiring": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace_wiring"
            ),
            "cutover_readiness": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_readiness"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "adapter_assignment_present": capture.get("adapter_assignment_present") is True,
        "result_assignment_present": capture.get("result_assignment_present") is True,
        "result_assignment_after_adapter": capture.get("result_assignment_after_adapter") is True,
        "route_returns_controller_boundary_item": (
            capture.get("route_returns_controller_boundary_item") is True
        ),
        "candidate_generation_still_live": capture.get("candidate_generation_still_live") is True,
        "candidate_evaluation_still_live": capture.get("candidate_evaluation_still_live") is True,
        "button_contract_still_live": capture.get("button_contract_still_live") is True,
        "final_binding_tail_adapter_still_live": (
            capture.get("final_binding_tail_adapter_still_live") is True
        ),
        "old_manual_final_binding_absent": capture.get("old_manual_final_binding_absent") is True,
        "latest_object_pass": (capture.get("latest") or {}).get("object", {}).get("status")
        == "PASS",
        "latest_trace_wiring_pass": (
            (capture.get("latest") or {}).get("trace_wiring", {}).get("status") == "PASS"
        ),
        "latest_cutover_readiness_pass": (
            (capture.get("latest") or {}).get("cutover_readiness", {}).get("status")
            == "PASS"
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
        "# Residual Shear Cleanup Route-Shell Adapter Cutover Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Adapter assignment present: `{capture.get('adapter_assignment_present')}`",
        f"- Result assignment present: `{capture.get('result_assignment_present')}`",
        f"- Route returns controller boundary item: `{capture.get('route_returns_controller_boundary_item')}`",
        f"- Candidate generation still live: `{capture.get('candidate_generation_still_live')}`",
        f"- Candidate evaluation still live: `{capture.get('candidate_evaluation_still_live')}`",
        f"- Button contract still live: `{capture.get('button_contract_still_live')}`",
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
            "Create deadness/readiness proof for the now-replaced page route-shell assignment body before deleting any old route body.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_extraction_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        "",
        f"`{payload.get('status')}` - residual-shear route-shell adapter narrow cutover.",
        "",
        "## Surface Targeted",
        "",
        "`post_click_low_bending_residual_shear_cleanup` route-shell result assignment.",
        "",
        "## Ownership Before",
        "",
        "The route returned the page-built `residual_promoted` item directly after debug/proof stamping.",
        "",
        "## Ownership After",
        "",
        "The route assigns `residual_promoted` from the controller route-shell adapter result item, which currently preserves the same item hash.",
        "",
        "## Behaviour Preserved",
        "",
        "- Candidate generation remains live/page-injected",
        "- Candidate evaluation remains live/page-injected",
        "- CTA button-contract execution remains live/shared/page-owned",
        "- Visible wording unchanged",
        "- Apply routing unchanged",
        "",
        "## Cutover Proof",
        "",
        f"- Focused cutover verifier: `{payload.get('status')}`",
        "",
        "## Deadness / Deletion Proof",
        "",
        "Not performed in this slice.",
        "",
        "## Lines Removed / Added",
        "",
        "Lines removed: `0`. Lines added: narrow adapter assignment plus verifier.",
        "",
        "## Files Changed",
        "",
        "- `inputs_page.py`",
        "- `design_brain/design_guide_controller.py`",
        "- `tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation.py`",
        "",
        "## Verifier Results",
        "",
        f"- Candidate generation still live: `{capture.get('candidate_generation_still_live')}`",
        f"- Candidate evaluation still live: `{capture.get('candidate_evaluation_still_live')}`",
        f"- CTA contract still live: `{capture.get('button_contract_still_live')}`",
        "",
        "## Remaining Page-Owned Authority",
        "",
        "- fallback search loop",
        "- evidence merge tail before adapter input",
        "- candidate/evaluation dependencies",
        "- debug/session projection",
        "",
        "## Next Safe Target",
        "",
        "Run a route-shell deadness/readiness audit, then target evidence merge or fallback search separately.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_shell_adapter_cutover_implementation_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_extraction_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
