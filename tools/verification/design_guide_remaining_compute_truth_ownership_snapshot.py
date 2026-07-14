"""Remaining compute-stage truth ownership snapshot.

This is proof-only. It classifies the remaining compute-stage resolver/rebound
truth after debug/restamp metadata narrowing. It does not narrow, delete, or
change product behaviour.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

CLASS_A = "A. should move into FinalDesignGuidePublication evidence"
CLASS_B = "B. should remain compute-only pre-publication input"
CLASS_D = "D. should remain fallback/safety logic"
CLASS_E = "E. unsafe / unclear"

REMAINING_OWNERSHIP_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "record_id": "raw_selected_item_identity",
        "field_members": ("raw_final_compute_resolution.item",),
        "classification": CLASS_A,
        "recommended_owner": "FinalDesignGuidePublication.evidence",
        "current_owner": "compute_stage_final_visible_resolver",
        "blocks_narrowing_until": "publication-evidence same-object proof for raw selected item identity",
        "narrowing_recommended_after_proof": True,
        "source_tokens": (
            "final_compute_resolution = resolve_final_visible_design_guide_item(",
            'final_compute_resolution.get("item")',
        ),
    },
    {
        "record_id": "render_reason",
        "field_members": ("raw_final_compute_resolution.render_reason",),
        "classification": CLASS_A,
        "recommended_owner": "FinalDesignGuidePublication.evidence",
        "current_owner": "compute_stage_final_visible_resolver",
        "blocks_narrowing_until": "publication-evidence same-object proof for render reason",
        "narrowing_recommended_after_proof": True,
        "source_tokens": ('final_compute_resolution.get("render_reason")',),
    },
    {
        "record_id": "state_fingerprint",
        "field_members": ("raw_final_compute_resolution.state_fingerprint",),
        "classification": CLASS_A,
        "recommended_owner": "FinalDesignGuidePublication.evidence",
        "current_owner": "compute_stage_final_visible_resolver",
        "blocks_narrowing_until": "publication-evidence same-object proof for state fingerprint",
        "narrowing_recommended_after_proof": True,
        "source_tokens": ('final_compute_resolution.get("state_fingerprint")',),
    },
    {
        "record_id": "raw_rebound_item_identity",
        "field_members": ("raw_post_evidence_rebound.item",),
        "classification": CLASS_A,
        "recommended_owner": "FinalDesignGuidePublication.evidence",
        "current_owner": "post_core_evidence_rebound",
        "blocks_narrowing_until": "publication-evidence same-object proof for raw rebound item identity",
        "narrowing_recommended_after_proof": True,
        "source_tokens": (
            "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
            "raw_rebound_item=dict(_post_evidence_rebound or _post_evidence_primary or {})",
        ),
    },
    {
        "record_id": "compute_pre_publication_rebound_inputs",
        "field_members": (
            "late_evidence_update_acceptance_condition",
            "post_core_evidence_update_mismatch_condition",
            "raw_late_rebound_contract.updates",
        ),
        "classification": CLASS_B,
        "recommended_owner": "compute publication handoff pre-publication input",
        "current_owner": "compute_late_evidence_contract_rebound / post_core_evidence_rebound",
        "blocks_narrowing_until": "should stay compute-owned; only normalized hashes may enter publication evidence",
        "narrowing_recommended_after_proof": False,
        "source_tokens": (
            "_late_evidence_acceptance",
            "_post_core_mismatch",
            '_late_rebound_contract.get("updates")',
        ),
    },
    {
        "record_id": "fallback_safety_rebound_surfaces",
        "field_members": (
            "raw_late_rebound_contract.enabled",
            "collapsed_guidance_items[0] pre-resolver mutation",
        ),
        "classification": CLASS_D,
        "recommended_owner": "compute fallback/safety logic",
        "current_owner": "compute_late_evidence_contract_rebound / post_core_evidence_rebound",
        "blocks_narrowing_until": "should stay safety-owned unless a later fallback freeze moves the guard",
        "narrowing_recommended_after_proof": False,
        "source_tokens": (
            "_design_guide_button_contract_enabled(_late_rebound_contract)",
            "collapsed_guidance_items[0] = dict(_post_evidence_rebound)",
        ),
    },
)

EXPECTED_COMPATIBILITY_ROWS = (
    "compute_stage_selected_title_action_family_restamp",
    "late_evidence_selected_action_restamp",
    "post_evidence_cleanup_contract_rebound_enabled_flag",
)

COMPOSED_GATES = (
    {
        "id": "compute_debug_restamp_metadata_narrowing",
        "script": "tools/verification/design_guide_compute_debug_restamp_metadata_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_compute_debug_restamp_metadata_narrowing",
    },
    {
        "id": "compute_publication_handoff_rebound_parity_scenarios",
        "script": "tools/verification/design_guide_live_compute_publication_handoff_rebound_parity_scenarios.py",
        "artifact_prefix": "design_guide_live_compute_publication_handoff_rebound_parity_scenarios",
    },
    {
        "id": "design_guide_independence_lock",
        "script": "tools/verification/design_guide_independence_lock_verifier.py",
        "artifact_prefix": "design_guide_independence_lock",
    },
    {
        "id": "design_guide_render_bridge_lock",
        "script": "tools/verification/design_guide_render_bridge_lock_verifier.py",
        "artifact_prefix": "design_guide_render_bridge_lock",
    },
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _source_checks(source: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for record in REMAINING_OWNERSHIP_RECORDS:
        token_checks = {token: token in source for token in record["source_tokens"]}
        checks.append(
            {
                "record_id": record["record_id"],
                "classification": record["classification"],
                "recommended_owner": record["recommended_owner"],
                "field_members": list(record["field_members"]),
                "source_tokens_present": token_checks,
                "all_source_tokens_present": all(token_checks.values()),
                "narrowing_recommended_after_proof": record["narrowing_recommended_after_proof"],
            }
        )
    return checks


def _compute_debug_metadata_rows_are_compatibility_only(latest_snapshot: dict[str, Any]) -> bool:
    snapshot = dict(latest_snapshot.get("snapshot") or {})
    if snapshot.get("status") != "PASS":
        return False
    rows = list(snapshot.get("narrowed_rows") or [])
    row_ids = {str(row.get("row_id")) for row in rows}
    if set(EXPECTED_COMPATIBILITY_ROWS) - row_ids:
        return False
    return bool(
        snapshot.get("only_c_class_debug_restamp_rows_narrowed") is True
        and snapshot.get("narrowed_rows_cannot_override_final_publication") is True
        and snapshot.get("remaining_blockers_after_narrowing") == 6
    )


def _final_publication_proof_support() -> dict[str, bool]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    return {
        "compute_proof_type_exists": "class FinalDesignGuideComputePublicationHandoffReboundDecisionProof" in source,
        "raw_selected_identity_field_exists": "raw_selected_item_identity" in source,
        "render_reason_field_exists": "render_reason" in source,
        "state_fingerprint_field_exists": "state_fingerprint" in source,
        "raw_rebound_identity_field_exists": "raw_rebound_item_identity" in source,
        "late_acceptance_field_exists": "late_evidence_acceptance" in source,
        "post_core_mismatch_field_exists": "post_core_evidence_mismatch" in source,
        "rebound_update_summary_field_exists": "rebound_update_payload_summary" in source,
        "fallback_mutation_field_exists": "pre_resolver_collapsed_item_mutation" in source,
        "proof_only_not_product_driving": "product_driving: bool = False" in source,
        "proof_only_not_render_driving": "render_driving: bool = False" in source,
        "proof_only_not_apply_driving": "apply_driving: bool = False" in source,
        "proof_only_not_session_driving": "session_driving: bool = False" in source,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Remaining Compute Truth Ownership Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Remaining ownership records: `{payload['remaining_record_count']}`",
        f"- Publication-evidence move candidates: `{len(payload['publication_evidence_move_candidates'])}`",
        f"- Compute-only records: `{len(payload['compute_only_records'])}`",
        f"- Fallback/safety records: `{len(payload['fallback_safety_records'])}`",
        f"- Unsafe/unclear fields: `{payload['unsafe_unclear_count']}`",
        f"- Compute debug metadata rows compatibility-only: `{payload['compute_debug_metadata_rows_compatibility_only']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Ownership Records",
        "",
        "| Record | Class | Members | Recommended owner | Narrow next |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in payload["records"]:
        lines.append(
            "| `{record}` | `{classification}` | {members} | {owner} | `{narrow}` |".format(
                record=_escape_md(record["record_id"]),
                classification=_escape_md(record["classification"]),
                members=_escape_md(", ".join(record["field_members"])),
                owner=_escape_md(record["recommended_owner"]),
                narrow=record["narrowing_recommended_after_proof"],
            )
        )
    lines.extend(
        [
            "",
            "## Source Checks",
            "",
            "| Record | Tokens present |",
            "| --- | --- |",
        ]
    )
    for check in payload["source_checks"]:
        lines.append(f"| `{_escape_md(check['record_id'])}` | `{check['all_source_tokens_present']}` |")
    lines.extend(["", "## Verification", ""])
    for gate in payload["verification"].values():
        lines.append(f"- `{gate['script']}`: `{gate['passed']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = INPUTS_PAGE.read_text(encoding="utf-8")
    source_checks = _source_checks(source)
    publication_support = _final_publication_proof_support()

    verification: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    for gate in COMPOSED_GATES:
        run = _run(gate["script"])
        latest = _latest(gate["artifact_prefix"])
        verification[gate["id"]] = {
            **run,
            "artifact_path": latest.get("path"),
            "artifact_passed": latest.get("passed") is True,
        }
        artifacts[gate["id"]] = latest.get("path")

    debug_narrowing_artifact = _latest("design_guide_compute_debug_restamp_metadata_narrowing")
    debug_rows_compat = _compute_debug_metadata_rows_are_compatibility_only(debug_narrowing_artifact)

    records = [dict(record) for record in REMAINING_OWNERSHIP_RECORDS]
    publication_candidates = [record for record in records if record["classification"] == CLASS_A]
    compute_only = [record for record in records if record["classification"] == CLASS_B]
    fallback_safety = [record for record in records if record["classification"] == CLASS_D]
    unsafe = [record for record in records if record["classification"] == CLASS_E]

    failures: list[str] = []
    if len(records) != 6:
        failures.append(f"expected_6_remaining_records_found_{len(records)}")
    if len(publication_candidates) != 4:
        failures.append(f"expected_4_publication_evidence_candidates_found_{len(publication_candidates)}")
    if len(compute_only) != 1:
        failures.append(f"expected_1_compute_only_record_found_{len(compute_only)}")
    if len(fallback_safety) != 1:
        failures.append(f"expected_1_fallback_safety_record_found_{len(fallback_safety)}")
    if unsafe:
        failures.append("unsafe_or_unclear_records_present")
    if not all(check["all_source_tokens_present"] for check in source_checks):
        failures.append("source_tokens_missing_for_remaining_records")
    if not all(publication_support.values()):
        failures.append("final_publication_compute_proof_support_missing")
    if not debug_rows_compat:
        failures.append("compute_debug_metadata_rows_not_compatibility_only")
    for gate_id, result in verification.items():
        if not result["passed"] or result["artifact_passed"] is not True:
            failures.append(f"{gate_id}_not_passed")

    payload = {
        "schema": "design_guide_remaining_compute_truth_ownership_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "remaining_record_count": len(records),
        "records": [
            {
                "record_id": record["record_id"],
                "field_members": list(record["field_members"]),
                "classification": record["classification"],
                "recommended_owner": record["recommended_owner"],
                "current_owner": record["current_owner"],
                "blocks_narrowing_until": record["blocks_narrowing_until"],
                "narrowing_recommended_after_proof": record["narrowing_recommended_after_proof"],
            }
            for record in records
        ],
        "publication_evidence_move_candidates": [
            record["record_id"] for record in publication_candidates
        ],
        "compute_only_records": [record["record_id"] for record in compute_only],
        "fallback_safety_records": [record["record_id"] for record in fallback_safety],
        "unsafe_unclear_count": len(unsafe),
        "narrowing_only_recommended_for_publication_evidence_fields": all(
            record["classification"] == CLASS_A
            for record in records
            if record["narrowing_recommended_after_proof"]
        ),
        "compute_debug_metadata_rows_compatibility_only": debug_rows_compat,
        "source_checks": source_checks,
        "final_publication_proof_support": publication_support,
        "source_artifacts": artifacts,
        "verification": verification,
        "ownership_hash": _stable_hash(
            {
                "records": records,
                "source_checks": source_checks,
                "publication_support": publication_support,
                "debug_rows_compat": debug_rows_compat,
            }
        ),
        "recommended_next_slice": (
            "Add a publication-evidence same-object proof for the four A-class records "
            "(`raw_selected_item_identity`, `render_reason`, `state_fingerprint`, and "
            "`raw_rebound_item_identity`). Do not narrow compute-only rebound inputs or "
            "fallback/safety surfaces."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_remaining_compute_truth_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_remaining_compute_truth_ownership_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_remaining_compute_truth_ownership_snapshot {payload['status']}")
    print(f"remaining_record_count={payload['remaining_record_count']}")
    print(f"publication_evidence_move_candidates={len(payload['publication_evidence_move_candidates'])}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
