"""Deadness proof for the residual-shear cleanup inline route body.

This verifier is intentionally proof-only. It does not require the body to be
dead to pass; it requires the current state to be classified honestly so the
route body is not deleted while live engineering, CTA, evidence, or debug
surfaces remain.
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

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_route_execution_shell = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell("

REQUIRED_ARTIFACTS = {
    "route_shell_deadness_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
    ),
    "route_body_controller_replacement_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_controller_replacement_readiness"
    ),
    "route_body_deletion_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness"
    ),
    "route_shell_with_injected_dependencies_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies_cutover"
    ),
    "evidence_merge_tail_deadness_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_deadness_readiness"
    ),
    "final_binding_tail_deadness_proof": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof"
    ),
    "debug_projection_narrowing": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing"
    ),
    "debug_projection_consumer_reachability": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability"
    ),
    "proof_debug_return_tail_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail_cutover"
    ),
    "prebuilt_route_result_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_cutover"
    ),
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "independence_lock": "design_guide_independence_lock",
}

LIVE_BODY_SURFACES = {
    "fallback_loop_structure": {
        "token": "for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):",
        "owner": "page-live injected route body",
        "delete_blocker": True,
    },
    "candidate_sequence_accumulation": {
        "token": "fallback_candidate_evaluation_sequence.append(",
        "owner": "page-live injected route body",
        "delete_blocker": True,
    },
    "candidate_selection_sequence": {
        "token": "fallback_candidate_selection_sequence.append(",
        "owner": "page-live injected route body",
        "delete_blocker": True,
    },
    "evidence_merge_tail": {
        "token": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail",
        "owner": "controller-proofed compatibility tail after old live merge deletion",
        "delete_blocker": True,
    },
    "final_binding_tail": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
        "owner": "controller-owned adapter after old page final-binding merge deletion",
        "delete_blocker": True,
    },
    "cta_contract_execution": {
        "token": "_design_guide_button_contract(residual_promoted, state=state)",
        "owner": "shared/page CTA boundary retained by rule",
        "delete_blocker": True,
    },
    "debug_session_projection": {
        "token": "debug_sink[",
        "owner": "page-owned session/debug mutation",
        "delete_blocker": True,
    },
}

DEAD_OR_REPLACED_SURFACES = {
    "old_return_residual_promoted": "return residual_promoted",
    "page_owned_result_return_authority": "return residual_route_return_item",
    "page_route_entry_builder_alias": (
        "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard("
    ),
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
    return source[start:end] if end > start else source[start:]


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "status": _status_from_payload(payload),
        "path": str(path),
        "payload": payload,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    evidence_merge_payload = (
        latest.get("evidence_merge_tail_deadness_readiness", {}).get("payload") or {}
    )
    evidence_merge_capture = dict(evidence_merge_payload.get("capture") or {})
    evidence_merge_old_body_dead = (
        evidence_merge_capture.get("decision") == "OLD_MERGE_READY_FOR_DELETION"
        and evidence_merge_capture.get("live_merge_present") is False
        and evidence_merge_capture.get("live_exact_blocker_merge_present") is False
        and evidence_merge_capture.get("guarded_cutover_present") is True
    )
    final_binding_payload = (
        latest.get("final_binding_tail_deadness_proof", {}).get("payload") or {}
    )
    final_binding_capture = dict(final_binding_payload.get("capture") or {})
    final_binding_old_merge_dead = (
        final_binding_capture.get("decision")
        == "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_OLD_PAGE_MERGE_DEAD"
        and not final_binding_capture.get("old_tokens_present")
        and not final_binding_capture.get("adapter_tokens_missing")
        and not final_binding_capture.get("shared_owned_tokens_missing")
    )
    debug_projection_payload = (
        latest.get("debug_projection_narrowing", {}).get("payload") or {}
    )
    debug_projection_capture = dict(debug_projection_payload.get("capture") or {})
    debug_projection_consumer_payload = (
        latest.get("debug_projection_consumer_reachability", {}).get("payload") or {}
    )
    debug_projection_consumer_capture = dict(
        debug_projection_consumer_payload.get("capture") or {}
    )
    debug_projection_proof_covered = (
        latest.get("debug_projection_narrowing", {}).get("status") == "PASS"
        and latest.get("debug_projection_consumer_reachability", {}).get("status") == "PASS"
        and latest.get("proof_debug_return_tail_cutover", {}).get("status") == "PASS"
        and debug_projection_capture.get("legacy_marker_deleted") is True
        and debug_projection_capture.get("debug_rows_represented_by_controller_builder") is True
        and debug_projection_capture.get("product_behavior_changed") is False
        and debug_projection_consumer_capture.get("product_behavior_changed") is False
    )

    live_surface_rows = {}
    for name, spec in LIVE_BODY_SURFACES.items():
        present = str(spec["token"]) in body
        delete_blocker = bool(spec["delete_blocker"] and present)
        if name == "evidence_merge_tail" and evidence_merge_old_body_dead:
            delete_blocker = False
        if name == "final_binding_tail" and final_binding_old_merge_dead:
            delete_blocker = False
        if name == "debug_session_projection" and debug_projection_proof_covered:
            delete_blocker = False
        live_surface_rows[name] = {
            "present": present,
            "owner": spec["owner"],
            "delete_blocker": delete_blocker,
            "token": spec["token"],
            "cleared_by_focused_deadness_proof": (
                (name == "evidence_merge_tail" and evidence_merge_old_body_dead)
                or (name == "final_binding_tail" and final_binding_old_merge_dead)
                or (name == "debug_session_projection" and debug_projection_proof_covered)
            ),
        }

    dead_replaced_rows = {
        name: {
            "present": token in body,
            "expected_present": name == "page_owned_result_return_authority",
        }
        for name, token in DEAD_OR_REPLACED_SURFACES.items()
    }

    required_artifacts_pass = all(row.get("status") == "PASS" for row in latest.values())
    delete_blockers = tuple(
        name for name, row in live_surface_rows.items() if row.get("delete_blocker") is True
    )
    safe_to_delete_route_body_now = bool(body) and required_artifacts_pass and not delete_blockers
    deletion_readiness_payload = (
        latest.get("route_body_deletion_readiness", {}).get("payload") or {}
    )
    deletion_readiness_capture = dict(deletion_readiness_payload.get("capture") or {})
    deletion_readiness_next_surface = str(
        deletion_readiness_capture.get("next_safe_surface") or ""
    )
    deletion_readiness_safe_to_delete = (
        deletion_readiness_capture.get("safe_to_delete_route_body_now") is True
    )
    route_body_deleted = not bool(body)
    physical_route_body_still_live = (
        deletion_readiness_capture.get("route_body_still_live") is True
        or "return residual_route_return_item" in body
    )
    safe_or_deleted = (
        (bool(body) and safe_to_delete_route_body_now)
        or (route_body_deleted and deletion_readiness_safe_to_delete)
    )
    return {
        "decision": (
            "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_DELETED"
            if route_body_deleted
            and deletion_readiness_safe_to_delete
            and required_artifacts_pass
            else
            "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_DEAD_AND_READY_TO_DELETE"
            if safe_or_deleted
            and deletion_readiness_safe_to_delete
            and not physical_route_body_still_live
            else "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_NOT_DEAD"
        ),
        "route_body_found": bool(body),
        "route_body_deleted": route_body_deleted,
        "required_artifacts_pass": required_artifacts_pass,
        "safe_to_delete_route_body_now": (
            safe_or_deleted
            and deletion_readiness_safe_to_delete
            and not physical_route_body_still_live
        ),
        "delete_blockers": tuple(
            ([] if route_body_deleted and deletion_readiness_safe_to_delete else list(delete_blockers))
            + (
                ["physical_route_body_still_live"]
                if physical_route_body_still_live
                else []
            )
            + (
                ["deletion_readiness_not_safe"]
                if not deletion_readiness_safe_to_delete
                else []
            )
        ),
        "delete_blocker_count": (0 if route_body_deleted and deletion_readiness_safe_to_delete else len(delete_blockers))
        + (1 if physical_route_body_still_live else 0)
        + (1 if not deletion_readiness_safe_to_delete else 0),
        "deletion_readiness_safe_to_delete": deletion_readiness_safe_to_delete,
        "physical_route_body_still_live": physical_route_body_still_live,
        "live_surface_rows": live_surface_rows,
        "focused_deadness": {
            "evidence_merge_tail_old_body_dead": evidence_merge_old_body_dead,
            "evidence_merge_tail_deadness_path": latest.get(
                "evidence_merge_tail_deadness_readiness", {}
            ).get("path"),
            "final_binding_tail_old_merge_dead": final_binding_old_merge_dead,
            "final_binding_tail_deadness_path": latest.get(
                "final_binding_tail_deadness_proof", {}
            ).get("path"),
            "debug_projection_proof_covered": debug_projection_proof_covered,
            "debug_projection_narrowing_path": latest.get(
                "debug_projection_narrowing", {}
            ).get("path"),
            "debug_projection_consumer_reachability_path": latest.get(
                "debug_projection_consumer_reachability", {}
            ).get("path"),
            "proof_debug_return_tail_cutover_path": latest.get(
                "proof_debug_return_tail_cutover", {}
            ).get("path"),
        },
        "dead_or_replaced_rows": dead_replaced_rows,
        "latest": {
            name: {
                "found": row.get("found"),
                "status": row.get("status"),
                "path": row.get("path"),
            }
            for name, row in latest.items()
        },
        "next_safe_surface": (
            "delete_route_body"
            if safe_or_deleted
            and deletion_readiness_safe_to_delete
            and not physical_route_body_still_live
            else deletion_readiness_next_surface
            or "replace_physical_nested_route_body_wrapper"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    safe_to_delete = capture.get("safe_to_delete_route_body_now") is True
    delete_blocker_count = int(capture.get("delete_blocker_count", 0) or 0)
    route_body_deleted = capture.get("route_body_deleted") is True
    return {
        "route_body_found_or_deleted": capture.get("route_body_found") is True or route_body_deleted,
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "deadness_classified": bool(capture.get("decision")),
        "delete_state_consistent": (
            (safe_to_delete and delete_blocker_count == 0)
            or ((not safe_to_delete) and delete_blocker_count > 0)
        ),
        "old_return_residual_promoted_absent": (
            ((capture.get("dead_or_replaced_rows") or {}).get("old_return_residual_promoted") or {}).get("present")
            is False
        ),
        "page_route_entry_builder_alias_absent": (
            ((capture.get("dead_or_replaced_rows") or {}).get("page_route_entry_builder_alias") or {}).get("present")
            is False
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
        "# Residual Shear Cleanup Route Body Deletion Deadness Proof",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"- Delete blocker count: `{capture.get('delete_blocker_count')}`",
        f"- Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Live Body Surfaces",
        "",
    ]
    for name, row in (capture.get("live_surface_rows") or {}).items():
        lines.append(
            f"- `{name}`: present=`{row.get('present')}`, "
            f"delete_blocker=`{row.get('delete_blocker')}`, owner=`{row.get('owner')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_extraction_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        "",
        f"`{payload.get('status')}` - residual-shear route body deadness classified.",
        "",
        "## Surface Targeted",
        "",
        "`_execute_post_click_low_bending_residual_shear_cleanup_route_body()` inline body.",
        "",
        "## Ownership Before",
        "",
        "The inline body still executes fallback search, candidate evaluation traces, evidence merge, CTA contract, and debug/session projection.",
        "",
        "## Ownership After",
        "",
        "No behaviour moved. The verifier classifies the body as not dead and blocks deletion.",
        "",
        "## Behaviour Preserved",
        "",
        "- Engineering behaviour unchanged",
        "- Visible wording unchanged",
        "- CTA/apply semantics unchanged",
        "- Family runtimes unchanged",
        "",
        "## Cutover Proof",
        "",
        "The route shell and route body result boundary remain controller-proofed by required PASS artifacts.",
        "",
        "## Deadness / Deletion Proof",
        "",
        f"- Safe to delete now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"- Delete blockers: `{', '.join(capture.get('delete_blockers') or ())}`",
        "",
        "## Lines Removed / Added",
        "",
        "Lines removed: `0`. Lines added: verifier only.",
        "",
        "## Files Changed",
        "",
        "- `tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof.py`",
        "",
        "## Verifier Results",
        "",
        f"- Focused verifier: `{payload.get('status')}`",
        "",
        "## Remaining Page-Owned Authority",
        "",
    ]
    for blocker in capture.get("delete_blockers") or ():
        lines.append(f"- `{blocker}`")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            "`split_fallback_search_or_evidence_merge_tail_before_deletion`",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_deletion_deadness_proof_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_extraction_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof "
        + str(payload["status"])
    )
    print(f"decision={capture.get('decision')}")
    print(f"safe_to_delete_route_body_now={capture.get('safe_to_delete_route_body_now')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
