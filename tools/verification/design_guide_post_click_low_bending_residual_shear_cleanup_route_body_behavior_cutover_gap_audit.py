"""Audit the remaining behavior-cutover gap for residual-shear cleanup.

This is proof-only. It does not claim the route body is deletion-ready.
It reconciles the already-green route/body/result/evidence/final-binding
proof chain with the source tokens that still keep behavior live in
``inputs_page.py``.
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
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

REQUIRED_ARTIFACT_PREFIXES = {
    "route_body_replacement_cutover_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness"
    ),
    "route_body_result_identity_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover"
    ),
    "route_body_return_boundary_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_return_boundary_cutover"
    ),
    "route_body_live_execution_shell_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit"
    ),
    "route_body_deletion_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness"
    ),
    "result_construction_deadness_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_construction_deadness_audit"
    ),
    "result_packaging_cutover_implementation": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation"
    ),
    "result_packaging_deadness_reachability": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_deadness_reachability"
    ),
    "evidence_merge_tail_result_adapter_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_implementation"
    ),
    "evidence_merge_tail_deadness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_deadness_readiness"
    ),
    "final_binding_tail_adapter_parity": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_parity"
    ),
    "final_binding_tail_parity_scenarios": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_parity_scenarios"
    ),
    "final_binding_tail_live_cutover_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_live_cutover_readiness"
    ),
    "final_binding_tail_deadness_proof": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof"
    ),
    "button_contract_boundary_cutover_implementation": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_implementation"
    ),
    "debug_projection_narrowing": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing"
    ),
    "debug_projection_consumer_reachability": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability"
    ),
    "independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
}

SURFACE_TOKENS = {
    "route_entry_guard": (
        "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(",
    ),
    "candidate_generation_execution": (
        "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
        "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
    ),
    "candidate_evaluation_execution": (
        "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
    ),
    "materiality_safety_screen_execution": (
        "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    ),
    "candidate_selection_execution": (
        "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
    ),
    "result_packaging_execution": (
        "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
    ),
    "evidence_merge_adapter_output": (
        "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(",
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace(",
    ),
    "residual_payload_extraction": (
        "residual_payload = dict(residual_promoted.get(\"action_payload\") or {})",
    ),
    "residual_resolved_extraction": (
        "residual_resolved = dict(residual_promoted.get(\"resolved_candidate\") or {})",
    ),
    "button_contract_execution": (
        "_design_guide_button_contract(residual_promoted, state=state)",
    ),
    "final_binding_adapter_execution": (
        "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
    ),
    "cta_apply_payload_source_summary_cutover": (
        '"cta_apply_payload_source_summary_cutover": True',
    ),
    "button_contract_source_summary_cutover": (
        '"button_contract_source_summary_cutover": True',
    ),
    "route_body_identity_cutover": (
        "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover_applied",
    ),
    "route_body_return_boundary_cutover": (
        "residual_route_return_boundary = _select_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_return_item(",
        "residual_route_body_result = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
        "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_return_boundary_hash",
    ),
    "debug_projection_compatibility_stamp": (
        "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only(",
    ),
    "route_returns_page_item": ("return residual_route_return_item",),
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


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


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if raw:
        return raw
    return "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": str(exc),
            "payload": {},
        }
    return {
        "found": True,
        "status": _status_from_payload(payload),
        "path": str(path),
        "payload": payload,
    }


def _artifact_accepts_classified_not_ready(name: str, artifact: dict[str, Any]) -> bool:
    if name != "route_body_deletion_readiness":
        return False
    payload = dict(artifact.get("payload") or {})
    capture = dict(payload.get("capture") or {})
    decision = str(capture.get("decision") or payload.get("decision") or "").upper()
    return (
        "NOT_READY_TO_DELETE" in decision
        and capture.get("safe_to_delete_route_body_now") is False
    )


def _surface_present(route: str) -> dict[str, bool]:
    return {
        name: any(token in route for token in tokens)
        for name, tokens in SURFACE_TOKENS.items()
    }


def _classify_surfaces(
    present: dict[str, bool],
    *,
    result_packaging_bounded: bool = False,
    button_contract_bounded: bool = False,
    route_return_boundary_bounded: bool = False,
) -> dict[str, dict[str, Any]]:
    cta_source_summary_cutover = bool(present.get("cta_apply_payload_source_summary_cutover"))
    rows: dict[str, dict[str, Any]] = {
        "route_entry_guard": {
            "category": "page-shell route guard retained",
            "behavior_role": "enters the residual cleanup branch",
            "blocks_behavior_cutover": False,
            "next_action": "keep until whole route body replacement is proven",
        },
        "candidate_generation_execution": {
            "category": "injected execution dependency",
            "behavior_role": "generates or runs shear cleanup candidates",
            "blocks_behavior_cutover": False,
            "next_action": "keep injected until candidate/evaluation authority audit",
        },
        "candidate_evaluation_execution": {
            "category": "injected execution dependency",
            "behavior_role": "evaluates candidate engineering result",
            "blocks_behavior_cutover": False,
            "next_action": "keep injected until candidate/evaluation authority audit",
        },
        "materiality_safety_screen_execution": {
            "category": "injected execution dependency",
            "behavior_role": "screens safe/material candidate result",
            "blocks_behavior_cutover": False,
            "next_action": "keep injected until candidate/evaluation authority audit",
        },
        "candidate_selection_execution": {
            "category": "controller sort-key represented, injected selector retained",
            "behavior_role": "selects best residual cleanup candidate",
            "blocks_behavior_cutover": False,
            "next_action": "keep bounded; selector parity already has focused proof",
        },
        "result_packaging_execution": {
            "category": "bounded injected packaging dependency"
            if result_packaging_bounded
            else "adapter represented but execution still injected",
            "behavior_role": "packages residual cleanup item and evaluates local cleanup card",
            "blocks_behavior_cutover": not result_packaging_bounded,
            "next_action": "result packaging cutover/deadness proofs are green; keep as injected dependency until whole route shell cutover"
            if result_packaging_bounded
            else "do not delete route body while packaging execution is still the live item source",
        },
        "evidence_merge_adapter_output": {
            "category": "controller adapter output",
            "behavior_role": "normalizes residual evidence and exact blockers",
            "blocks_behavior_cutover": False,
            "next_action": "old update-style merge is gone; keep parity guard until body replacement",
        },
        "residual_payload_extraction": {
            "category": "bounded CTA/apply payload source boundary"
            if cta_source_summary_cutover
            else "live CTA/apply payload source",
            "behavior_role": "extracts action payload from the live promoted item",
            "blocks_behavior_cutover": not cta_source_summary_cutover,
            "next_action": "source-summary cutover complete; keep as injected live source until whole route body replacement"
            if cta_source_summary_cutover
            else "create residual CTA/apply payload source boundary proof",
        },
        "residual_resolved_extraction": {
            "category": "bounded resolved-candidate source boundary"
            if cta_source_summary_cutover
            else "live resolved-candidate source",
            "behavior_role": "extracts resolved candidate from the live promoted item",
            "blocks_behavior_cutover": not cta_source_summary_cutover,
            "next_action": "source-summary cutover complete; keep as injected live source until whole route body replacement"
            if cta_source_summary_cutover
            else "include in residual CTA/apply payload source boundary proof",
        },
        "button_contract_execution": {
            "category": "bounded shared button-contract source boundary"
            if button_contract_bounded
            else "shared CTA/button contract execution",
            "behavior_role": "builds executor-backed button contract from item and state",
            "blocks_behavior_cutover": not button_contract_bounded,
            "next_action": "button-contract source-summary cutover complete; shared helper remains injected/live until whole route shell cutover"
            if button_contract_bounded
            else "prove controller can accept the shared contract as an injected boundary without page-owned rebinding",
        },
        "final_binding_adapter_execution": {
            "category": "controller final-binding adapter",
            "behavior_role": "binds evidence/payload/resolved/contract into final item",
            "blocks_behavior_cutover": False,
            "next_action": "adapter is present; remaining blocker is its live inputs",
        },
        "cta_apply_payload_source_summary_cutover": {
            "category": "guarded source-summary cutover",
            "behavior_role": "uses controller boundary hashes as final-binding source summary",
            "blocks_behavior_cutover": False,
            "next_action": "completed; does not move shared button-contract execution or apply routing",
        },
        "button_contract_source_summary_cutover": {
            "category": "guarded button-contract source-summary cutover",
            "behavior_role": "uses controller button-contract boundary hashes as final-binding contract summary",
            "blocks_behavior_cutover": False,
            "next_action": "completed; does not move shared button-contract execution or apply routing",
        },
        "route_body_identity_cutover": {
            "category": "narrow identity cutover applied",
            "behavior_role": "uses controller replacement for item identity only",
            "blocks_behavior_cutover": False,
            "next_action": "keep as proof of route-shape cutover",
        },
        "debug_projection_compatibility_stamp": {
            "category": "compatibility-only debug projection",
            "behavior_role": "stamps non-product debug/session proof",
            "blocks_behavior_cutover": False,
            "next_action": "not a behavior blocker",
        },
        "route_returns_page_item": {
            "category": "controller selector-backed route return boundary"
            if route_return_boundary_bounded
            else "old route body still returns live item",
            "behavior_role": "returns the controller-selected residual cleanup route item"
            if route_return_boundary_bounded
            else "keeps the page route body live until behavior sources are cut over",
            "blocks_behavior_cutover": not route_return_boundary_bounded,
            "next_action": "return authority is controller-owned; keep physical return only until whole route-body deletion proof passes"
            if route_return_boundary_bounded
            else "delete only after payload/contract/packaging sources are replaced or bounded",
        },
        "route_body_return_boundary_cutover": {
            "category": "controller route return selector",
            "behavior_role": "selects route return item by controller-owned boundary hash",
            "blocks_behavior_cutover": False,
            "next_action": "completed; use as proof that the physical return is not page-owned result authority",
        },
    }
    for name, row in rows.items():
        row["present"] = bool(present.get(name))
        if not row["present"]:
            row["blocks_behavior_cutover"] = False
            row["next_action"] = "absent from route window"
    return rows


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACT_PREFIXES.items()}
    present = _surface_present(route)
    result_packaging_bounded = all(
        latest.get(name, {}).get("status") == "PASS"
        for name in (
            "result_packaging_cutover_implementation",
            "result_packaging_deadness_reachability",
        )
    )
    button_contract_bounded = (
        latest.get("button_contract_boundary_cutover_implementation", {}).get("status")
        == "PASS"
        and present.get("button_contract_source_summary_cutover")
    )
    route_return_boundary_bounded = (
        latest.get("route_body_return_boundary_cutover", {}).get("status") == "PASS"
        and present.get("route_body_return_boundary_cutover")
    )
    surface_rows = _classify_surfaces(
        present,
        result_packaging_bounded=result_packaging_bounded,
        button_contract_bounded=button_contract_bounded,
        route_return_boundary_bounded=route_return_boundary_bounded,
    )
    blocking_surfaces = tuple(
        name
        for name, row in surface_rows.items()
        if row.get("present") and row.get("blocks_behavior_cutover")
    )
    artifact_failures = tuple(
        name
        for name, artifact in latest.items()
        if artifact.get("status") != "PASS"
        and not _artifact_accepts_classified_not_ready(name, artifact)
    )
    route_shape_proven = all(
        latest.get(name, {}).get("status") == "PASS"
        for name in (
            "route_body_replacement_cutover_readiness",
            "route_body_result_identity_cutover",
            "route_body_live_execution_shell_audit",
        )
    )
    downstream_tails_proven = all(
        latest.get(name, {}).get("status") == "PASS"
        for name in (
            "result_packaging_cutover_implementation",
            "evidence_merge_tail_result_adapter_cutover",
            "evidence_merge_tail_deadness",
            "final_binding_tail_adapter_parity",
            "final_binding_tail_parity_scenarios",
            "final_binding_tail_live_cutover_readiness",
            "final_binding_tail_deadness_proof",
            "debug_projection_narrowing",
            "debug_projection_consumer_reachability",
        )
    )
    behavior_cutover_ready = bool(route_shape_proven and downstream_tails_proven and not blocking_surfaces)
    safe_to_delete_route_body_now = bool(
        behavior_cutover_ready
        and latest.get("route_body_deletion_readiness", {}).get("status") == "PASS"
        and not present.get("route_returns_page_item")
    )
    next_safe_surface = (
        "residual_cta_apply_payload_source_boundary"
        if any(
            name in blocking_surfaces
            for name in (
                "residual_payload_extraction",
                "residual_resolved_extraction",
                "button_contract_execution",
            )
        )
        and not present.get("cta_apply_payload_source_summary_cutover")
        else "result_packaging_execution_boundary"
        if "result_packaging_execution" in blocking_surfaces
        else "button_contract_execution_boundary"
        if "button_contract_execution" in blocking_surfaces
        else "route_body_return_boundary"
        if "route_returns_page_item" in blocking_surfaces
        else "route_body_deadness_deletion"
        if behavior_cutover_ready
        else "refresh_missing_or_failed_artifacts"
    )
    return {
        "decision": (
            "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_BEHAVIOR_CUTOVER_GAP_CLASSIFIED"
        ),
        "route_found": bool(route),
        "route_shape_proven": route_shape_proven,
        "downstream_tails_proven": downstream_tails_proven,
        "result_packaging_bounded": result_packaging_bounded,
        "button_contract_bounded": button_contract_bounded,
        "route_return_boundary_bounded": route_return_boundary_bounded,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_to_delete_route_body_now": safe_to_delete_route_body_now,
        "next_safe_surface": next_safe_surface,
        "blocking_surfaces": blocking_surfaces,
        "artifact_failures": artifact_failures,
        "surface_rows": surface_rows,
        "required_artifacts": {
            name: {key: value for key, value in artifact.items() if key != "payload"}
            for name, artifact in latest.items()
        },
        "route_window_hash": _stable_hash(route),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    blockers = tuple(capture.get("blocking_surfaces") or ())
    next_surface = str(capture.get("next_safe_surface") or "")
    return {
        "route_found": capture.get("route_found") is True,
        "artifacts_all_pass": not bool(capture.get("artifact_failures")),
        "route_shape_proven": capture.get("route_shape_proven") is True,
        "downstream_tails_proven": capture.get("downstream_tails_proven") is True,
        "behavior_gap_classified": bool(blockers)
        or next_surface == "route_body_deadness_deletion",
        "unsafe_delete_not_claimed": capture.get("safe_to_delete_route_body_now") is False
        or next_surface == "route_body_deadness_deletion",
        "next_surface_selected": bool(capture.get("next_safe_surface")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Body Behavior Cutover Gap Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Route shape proven: `{capture.get('route_shape_proven')}`",
        f"- Downstream tails proven: `{capture.get('downstream_tails_proven')}`",
        f"- Behaviour cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"- Result packaging bounded: `{capture.get('result_packaging_bounded')}`",
        f"- Button contract bounded: `{capture.get('button_contract_bounded')}`",
        f"- Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Blocking Surfaces",
        "",
    ]
    blockers = list(capture.get("blocking_surfaces") or [])
    if blockers:
        lines.extend(f"- `{name}`" for name in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Surface Classification", ""])
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            "- `{}`: present=`{}`, category=`{}`, blocks=`{}`, next=`{}`".format(
                name,
                row.get("present"),
                row.get("category"),
                row.get("blocks_behavior_cutover"),
                row.get("next_action"),
            )
        )
    lines.extend(["", "## Required Artifacts", ""])
    for name, artifact in (capture.get("required_artifacts") or {}).items():
        lines.append(
            f"- `{name}`: status=`{artifact.get('status')}`, path=`{artifact.get('path')}`"
        )
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            (
                "Continue to the first remaining blocking surface shown above. If only "
                "`button_contract_execution` and `route_returns_page_item` remain, create "
                "a shared button-contract execution boundary proof before any route-body deletion."
            ),
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_behavior_cutover_gap_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit "
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
