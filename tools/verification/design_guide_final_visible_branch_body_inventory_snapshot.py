"""Inventory remaining enabled/disabled final-visible branch body surfaces.

This is a deletion-planning snapshot after source-output argument/fallback
removal. It locks the obsolete source-output construction count for the
enabled/disabled final-visible branches and separates remaining page-shell
effects from candidate future extraction surfaces.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


BRANCHES = (
    "final_contract_binding.enabled_action_output",
    "final_contract_binding.disabled_output",
)


OBSOLETE_SOURCE_OUTPUT_PATTERNS = {
    "legacy_output_item_old_out": "legacy_output_item=dict(out or {})",
    "return_source_output": "return source_output",
    "source_hash_assignment": "source_hash = _stable_final_publication_hash(source_output)",
    "old_hash_guard": "projected_hash == source_hash",
    "old_out_overlay": "out[key]",
}

PAGE_SHELL_PATTERNS = {
    "primary_button_session_helper": "_set_design_guide_primary_button_contract_session_state(",
    "primary_apply_payload_session_projection_helper": (
        "_record_final_visible_enabled_action_primary_apply_payload_session_projection("
    ),
    "disabled_payload_binding_audit_projection_helper": (
        "_set_final_visible_disabled_primary_payload_binding_audit_projection("
    ),
    "enabled_debug_projection_helper": "_update_final_visible_enabled_action_debug_projection(",
    "disabled_debug_projection_helper": "_update_final_visible_disabled_debug_projection(",
    "family_status_display_projection_helper": "_project_final_visible_family_status_display_payload(",
    "combined_outside_target_blocker_projection_helper": (
        "_apply_final_visible_combined_outside_target_blocker_projection("
    ),
    "cta_authority_projection_helper": "_apply_final_visible_contract_binding_cta_authority_projection(",
}

DIRECT_SESSION_WRITE_PATTERNS = {
    "direct_session_button_contract": "st.session_state[\"design_guide_primary_button_contract\"]",
    "direct_session_button_enabled": "st.session_state[\"design_guide_primary_button_contract_enabled\"]",
    "direct_session_apply_payload_pop": "st.session_state.pop(DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY",
}

DIRECT_APPLY_PAYLOAD_RECORD_PATTERNS = {
    "direct_apply_payload_record": "_record_rendered_design_guide_primary_apply_payload(",
}

DIRECT_CTA_AUTHORITY_STAMP_PATTERNS = {
    "direct_cta_authority_stamp": "_stamp_final_publication_cta_authority(",
}

DIRECT_PAYLOAD_BINDING_AUDIT_PATTERNS = {
    "direct_payload_binding_audit": "_set_design_guide_primary_payload_binding_audit(",
}

DIRECT_DEBUG_UPDATE_PATTERNS = {
    "direct_debug_sink_update": "debug_sink.update(",
}

ADAPTER_PATTERNS = {
    "adapter_cutover_call": "_final_visible_contract_binding_output_cutover(",
    "adapter_overlay_seed": "_adapter_overlay_seed",
    "disabled_adapter_overlay_seed": "_disabled_adapter_overlay_seed",
    "adapter_owned_fallback": 'derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_adapter_fallback.inline"',
    "adapter_validity": "_build_final_visible_contract_binding_output_validity(",
}

FUTURE_EXTRACTION_PATTERNS = {
    "family_status_display_payload": "_attach_family_status_display_payload(",
    "bending_fail_publication_snapshot": "_store_bending_fail_publication_snapshot(",
    "combined_exact_blocker_rebuild": "_visible_cleanup_blocker_from_action(",
    "overview_collection": "_collect_design_overview(",
    "target_band_resolution": "_resolved_efficiency_target_band(",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(_read(path))
    except Exception as exc:
        payload = {"load_error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload}


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def _line_numbers(source: str, token: str) -> list[int]:
    return [idx for idx, line in enumerate(source.splitlines(), start=1) if token in line]


def _branch_window(body: str, branch: str) -> str:
    token = f'callsite_id="{branch}"'
    pos = body.find(token)
    if pos < 0:
        return ""
    if branch.endswith("enabled_action_output"):
        start_marker = "        contract.update("
        start = body.rfind(start_marker, 0, pos)
        end = body.find("        return out", pos)
        return body[start : end + len("        return out")] if start >= 0 and end >= 0 else ""
    start_marker = "    family = str("
    start = body.rfind(start_marker, 0, pos)
    end = body.find("    return out", pos)
    return body[start : end + len("    return out")] if start >= 0 and end >= 0 else ""


def _pattern_hits(window: str, source: str, patterns: dict[str, str]) -> dict[str, Any]:
    hits: dict[str, Any] = {}
    for name, token in patterns.items():
        count = window.count(token)
        hits[name] = {
            "count": count,
            "present": bool(count),
            "source_lines": _line_numbers(source, token) if count else [],
        }
    return hits


def _count_present(hits: dict[str, Any]) -> int:
    return sum(int(row.get("count") or 0) for row in hits.values())


def build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS)
    body = _function_body(source, "_publish_final_visible_design_guide_contract_binding")
    latest_deadness = _latest("design_guide_final_visible_source_output_branch_deadness")
    latest_fallback = _latest("design_guide_final_visible_source_output_fallback_reachability")
    latest_guard = _latest("design_guide_final_visible_source_output_guard_cutover")
    branches: list[dict[str, Any]] = []
    for branch in BRANCHES:
        window = _branch_window(body, branch)
        obsolete_hits = _pattern_hits(window, source, OBSOLETE_SOURCE_OUTPUT_PATTERNS)
        page_shell_hits = _pattern_hits(window, source, PAGE_SHELL_PATTERNS)
        direct_session_hits = _pattern_hits(window, source, DIRECT_SESSION_WRITE_PATTERNS)
        direct_apply_payload_hits = _pattern_hits(
            window,
            source,
            DIRECT_APPLY_PAYLOAD_RECORD_PATTERNS,
        )
        direct_cta_stamp_hits = _pattern_hits(
            window,
            source,
            DIRECT_CTA_AUTHORITY_STAMP_PATTERNS,
        )
        direct_payload_binding_audit_hits = _pattern_hits(
            window,
            source,
            DIRECT_PAYLOAD_BINDING_AUDIT_PATTERNS,
        )
        direct_debug_hits = _pattern_hits(window, source, DIRECT_DEBUG_UPDATE_PATTERNS)
        adapter_hits = _pattern_hits(window, source, ADAPTER_PATTERNS)
        future_hits = _pattern_hits(window, source, FUTURE_EXTRACTION_PATTERNS)
        obsolete_count = _count_present(obsolete_hits)
        page_shell_count = _count_present(page_shell_hits)
        direct_session_count = _count_present(direct_session_hits)
        direct_apply_payload_count = _count_present(direct_apply_payload_hits)
        direct_cta_stamp_count = _count_present(direct_cta_stamp_hits)
        direct_payload_binding_audit_count = _count_present(direct_payload_binding_audit_hits)
        direct_debug_count = _count_present(direct_debug_hits)
        future_count = _count_present(future_hits)
        branches.append(
            {
                "branch": branch,
                "window_found": bool(window),
                "obsolete_source_output_count": obsolete_count,
                "direct_primary_button_session_write_count": direct_session_count,
                "direct_apply_payload_record_count": direct_apply_payload_count,
                "direct_cta_authority_stamp_count": direct_cta_stamp_count,
                "direct_payload_binding_audit_count": direct_payload_binding_audit_count,
                "direct_debug_sink_update_count": direct_debug_count,
                "page_shell_effect_count": page_shell_count,
                "future_extraction_candidate_count": future_count,
                "adapter_pattern_count": _count_present(adapter_hits),
                "safe_to_delete_entire_branch_body_now": bool(
                    window and obsolete_count == 0 and page_shell_count == 0 and future_count == 0
                ),
                "obsolete_source_output_hits": obsolete_hits,
                "direct_primary_button_session_write_hits": direct_session_hits,
                "direct_apply_payload_record_hits": direct_apply_payload_hits,
                "direct_cta_authority_stamp_hits": direct_cta_stamp_hits,
                "direct_payload_binding_audit_hits": direct_payload_binding_audit_hits,
                "direct_debug_sink_update_hits": direct_debug_hits,
                "page_shell_effect_hits": page_shell_hits,
                "adapter_hits": adapter_hits,
                "future_extraction_candidate_hits": future_hits,
            }
        )
    total_obsolete = sum(int(row["obsolete_source_output_count"]) for row in branches)
    total_direct_session = sum(
        int(row["direct_primary_button_session_write_count"]) for row in branches
    )
    total_direct_apply_payload = sum(
        int(row["direct_apply_payload_record_count"]) for row in branches
    )
    total_direct_cta_stamp = sum(int(row["direct_cta_authority_stamp_count"]) for row in branches)
    total_direct_payload_binding_audit = sum(
        int(row["direct_payload_binding_audit_count"]) for row in branches
    )
    total_direct_debug = sum(int(row["direct_debug_sink_update_count"]) for row in branches)
    total_page_shell = sum(int(row["page_shell_effect_count"]) for row in branches)
    total_future = sum(int(row["future_extraction_candidate_count"]) for row in branches)
    latest = {
        "deadness": latest_deadness,
        "fallback_reachability": latest_fallback,
        "guard_cutover": latest_guard,
    }
    latest_pass = {
        name: bool(
            record.get("found")
            and str((record.get("payload") or {}).get("status") or "").upper() == "PASS"
        )
        for name, record in latest.items()
    }
    failures: list[str] = []
    if not body:
        failures.append("final_visible_binding_helper_missing")
    if any(not row["window_found"] for row in branches):
        failures.append("branch_window_missing")
    if total_obsolete != 0:
        failures.append("obsolete_source_output_construction_still_present")
    if total_direct_session != 0:
        failures.append("direct_primary_button_session_writes_still_in_branch_body")
    if total_direct_apply_payload != 0:
        failures.append("direct_apply_payload_record_still_in_branch_body")
    if total_direct_cta_stamp != 0:
        failures.append("direct_cta_authority_stamp_still_in_branch_body")
    if total_direct_payload_binding_audit != 0:
        failures.append("direct_payload_binding_audit_still_in_branch_body")
    if total_direct_debug != 0:
        failures.append("direct_debug_sink_update_still_in_branch_body")
    for name, passed in latest_pass.items():
        if not passed:
            failures.append(f"{name}_not_pass")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_branch_body_inventory_snapshot.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "OBSOLETE_SOURCE_OUTPUT_DIRECT_SESSION_APPLY_CTA_AUDIT_AND_DEBUG_ZERO_BRANCH_BODY_STILL_PAGE_SHELL"
            if status == "PASS"
            else "BRANCH_BODY_INVENTORY_NEEDS_ATTENTION"
        ),
        "branches": branches,
        "totals": {
            "obsolete_source_output_count": total_obsolete,
            "direct_primary_button_session_write_count": total_direct_session,
            "direct_apply_payload_record_count": total_direct_apply_payload,
            "direct_cta_authority_stamp_count": total_direct_cta_stamp,
            "direct_payload_binding_audit_count": total_direct_payload_binding_audit,
            "direct_debug_sink_update_count": total_direct_debug,
            "page_shell_effect_count": total_page_shell,
            "future_extraction_candidate_count": total_future,
            "safe_to_delete_entire_branch_body_now": all(
                row["safe_to_delete_entire_branch_body_now"] for row in branches
            ),
        },
        "latest_required": {
            name: {
                "found": record.get("found"),
                "path": record.get("path"),
                "status": (record.get("payload") or {}).get("status"),
                "decision": (record.get("payload") or {}).get("decision"),
            }
            for name, record in latest.items()
        },
        "latest_required_pass": latest_pass,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "extract or bound page-shell apply/session/debug side effects before deleting entire branch body"
            if (
                total_obsolete == 0
                and total_direct_session == 0
                and total_direct_apply_payload == 0
                and total_direct_cta_stamp == 0
                and total_direct_payload_binding_audit == 0
                and total_direct_debug == 0
            )
            else "remove remaining obsolete source-output construction first"
        ),
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    rows = [
        "| Branch | Obsolete source-output | Direct session writes | Direct apply record | Direct CTA stamp | Direct audit | Direct debug update | Page-shell effects | Future extraction candidates | Delete body now |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for branch in snapshot["branches"]:
        rows.append(
            "| {branch} | {obsolete} | {direct_session} | {direct_apply} | {direct_cta} | {direct_audit} | {direct_debug} | {page_shell} | {future} | {delete} |".format(
                branch=branch["branch"],
                obsolete=branch["obsolete_source_output_count"],
                direct_session=branch["direct_primary_button_session_write_count"],
                direct_apply=branch["direct_apply_payload_record_count"],
                direct_cta=branch["direct_cta_authority_stamp_count"],
                direct_audit=branch["direct_payload_binding_audit_count"],
                direct_debug=branch["direct_debug_sink_update_count"],
                page_shell=branch["page_shell_effect_count"],
                future=branch["future_extraction_candidate_count"],
                delete=branch["safe_to_delete_entire_branch_body_now"],
            )
        )
    report = [
        "# Final Visible Branch Body Inventory Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Summary",
        *rows,
        "",
        "## Totals",
        f"- obsolete source-output count: `{snapshot['totals']['obsolete_source_output_count']}`",
        "- direct primary-button session write count: "
        f"`{snapshot['totals']['direct_primary_button_session_write_count']}`",
        f"- direct apply payload record count: `{snapshot['totals']['direct_apply_payload_record_count']}`",
        f"- direct CTA authority stamp count: `{snapshot['totals']['direct_cta_authority_stamp_count']}`",
        f"- direct payload binding audit count: `{snapshot['totals']['direct_payload_binding_audit_count']}`",
        f"- direct debug sink update count: `{snapshot['totals']['direct_debug_sink_update_count']}`",
        f"- page-shell effect count: `{snapshot['totals']['page_shell_effect_count']}`",
        f"- future extraction candidate count: `{snapshot['totals']['future_extraction_candidate_count']}`",
        "",
        "## Next Safe Step",
        snapshot["next_safe_step"],
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")


def _write_extraction_report(snapshot: dict[str, Any], report_path: Path) -> None:
    report = [
        "# Design Brain Physical Extraction Report",
        "## Executive Summary",
        snapshot["status"],
        "## Surface Targeted",
        "Remaining enabled/disabled final-visible branch body after source-output argument deletion.",
        "## Ownership Before",
        "The body had mixed concerns: adapter calls, page/session/apply side effects, and possible old source-output construction.",
        "## Ownership After",
        "Inventory only. Obsolete source-output construction is locked at zero for this surface; page-shell side effects remain.",
        "## Behaviour Preserved",
        "No product, engineering, visible wording, CTA/apply, session, or family runtime behaviour changed.",
        "## Adapter / Default Rebuild Proof",
        f"Guard cutover status: `{snapshot['latest_required']['guard_cutover']['status']}`.",
        "## Cutover Proof",
        f"Fallback reachability status: `{snapshot['latest_required']['fallback_reachability']['status']}`.",
        "## Deadness / Deletion Proof",
        f"Obsolete source-output count: `{snapshot['totals']['obsolete_source_output_count']}`.",
        "Direct primary-button session write count in branch body: "
        f"`{snapshot['totals']['direct_primary_button_session_write_count']}`.",
        "Direct apply payload record count in branch body: "
        f"`{snapshot['totals']['direct_apply_payload_record_count']}`.",
        "Direct CTA authority stamp count in branch body: "
        f"`{snapshot['totals']['direct_cta_authority_stamp_count']}`.",
        "Direct payload binding audit count in branch body: "
        f"`{snapshot['totals']['direct_payload_binding_audit_count']}`.",
        "Direct debug sink update count in branch body: "
        f"`{snapshot['totals']['direct_debug_sink_update_count']}`.",
        f"Safe to delete entire branch body now: `{snapshot['totals']['safe_to_delete_entire_branch_body_now']}`.",
        "## Lines Removed / Added",
        "No deletion in this inventory slice.",
        "## Files Changed",
        "`tools/verification/design_guide_final_visible_branch_body_inventory_snapshot.py`",
        "## Verifier Results",
        f"`design_guide_final_visible_branch_body_inventory_snapshot.py`: `{snapshot['status']}`.",
        "## Remaining Page-Owned Authority",
        "Page-shell apply/session/debug side effects and future extraction candidates remain in the branch body.",
        "## Next Safe Target",
        snapshot["next_safe_step"],
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_branch_body_inventory_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_branch_body_inventory_{stamp}.md"
    extraction_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_final_visible_branch_body_inventory_{stamp}.md"
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    _write_extraction_report(snapshot, extraction_path)
    print(f"design_guide_final_visible_branch_body_inventory {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(f"extraction_report={extraction_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

