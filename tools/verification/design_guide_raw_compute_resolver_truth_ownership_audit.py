"""Raw compute resolver/rebound truth ownership audit.

This audit classifies the remaining raw truth fields for the three compute-stage
Design Guide class-C authority paths. It is audit-only: no narrowing, deletion,
or product-behaviour change.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
import os
from pathlib import Path
from typing import Any

try:
    from tools.verification.verification_run_manifest import current_run_artifact
except ModuleNotFoundError:
    from verification_run_manifest import current_run_artifact


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

CLASS_A = "A. should move into FinalDesignGuidePublication evidence"
CLASS_B = "B. should remain compute-only pre-publication input"
CLASS_C = "C. should become compatibility/debug-only"
CLASS_D = "D. should remain fallback/safety logic"
CLASS_E = "E. unsafe / unclear"

FIELD_OWNERSHIP = {
    "compute_stage_final_visible_resolver": [
        {
            "field": "raw_final_compute_resolution.item",
            "classification": CLASS_B,
            "truth_kind": "pre-publication selected item input",
            "real_engineering_or_publication_truth": True,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": True,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The compute resolver still chooses the item that becomes the input to "
                "FinalDesignGuidePublication. The final object can represent it after the adapter, "
                "but it does not yet own the pre-publication selection."
            ),
            "required_proof_before_narrowing": (
                "Prove a publication-derived compute selected item can replace the raw resolver item, "
                "or move compute selection into a Design Brain publication boundary."
            ),
        },
        {
            "field": "raw_final_compute_resolution.render_reason",
            "classification": CLASS_A,
            "truth_kind": "publication reason",
            "real_engineering_or_publication_truth": True,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": False,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The render reason is final publication reason truth. It is already passed into "
                "the publication adapter, but its raw source is still owned by compute resolver logic."
            ),
            "required_proof_before_narrowing": (
                "Make the publication reason a direct FinalDesignGuidePublication evidence/source field "
                "for the compute handoff."
            ),
        },
        {
            "field": "raw_final_compute_resolution.state_fingerprint",
            "classification": CLASS_A,
            "truth_kind": "publication identity/freshness fingerprint",
            "real_engineering_or_publication_truth": True,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": False,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The fingerprint is publication identity/freshness evidence, not rendering logic. "
                "It should be owned by FinalDesignGuidePublication evidence/verifier payload."
            ),
            "required_proof_before_narrowing": (
                "Prove state_fingerprint parity with FinalDesignGuidePublication source/publication hash."
            ),
        },
        {
            "field": "debug_trace.selected_title/action/family restamp",
            "classification": CLASS_C,
            "truth_kind": "legacy debug/session compatibility metadata",
            "real_engineering_or_publication_truth": False,
            "debug_or_restamp_metadata": True,
            "needed_before_final_publication_exists": False,
            "blocks_compatibility_only_narrowing": False,
            "rationale": (
                "These fields mirror the adapted final item for legacy debug/session consumers. "
                "They should become compatibility/debug-only once the raw selected item is no longer "
                "compute-owned."
            ),
            "required_proof_before_narrowing": "Same-object debug/session stamp proof at compute handoff.",
        },
    ],
    "compute_late_evidence_contract_rebound": [
        {
            "field": "late_evidence_update_acceptance_condition",
            "classification": CLASS_D,
            "truth_kind": "pre-publication safety/reconciliation guard",
            "real_engineering_or_publication_truth": False,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": True,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The condition decides whether stale or mismatched late evidence should rebound "
                "before final publication. It is safety logic, not final visible truth."
            ),
            "required_proof_before_narrowing": (
                "Capture this guard as a proof-only compute rebound decision before narrowing the restamp."
            ),
        },
        {
            "field": "raw_late_rebound_contract.enabled",
            "classification": CLASS_A,
            "truth_kind": "CTA/action availability source",
            "real_engineering_or_publication_truth": True,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": False,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The raw rebound contract enabled state decides whether the rebound is accepted and "
                "feeds final CTA authority. It should be represented by FinalDesignGuidePublication "
                "CTA/evidence before the restamp becomes compatibility-only."
            ),
            "required_proof_before_narrowing": (
                "Prove raw rebound enabled parity with FinalDesignGuidePublication.cta enabled/actionable evidence."
            ),
        },
        {
            "field": "raw_late_rebound_contract.updates",
            "classification": CLASS_A,
            "truth_kind": "apply payload/update identity",
            "real_engineering_or_publication_truth": True,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": False,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The raw rebound updates are apply payload identity. FinalDesignGuidePublication.cta "
                "can represent the fingerprint after adaptation, but the raw source still sits in "
                "compute rebound logic."
            ),
            "required_proof_before_narrowing": (
                "Prove rebound updates hash equals FinalDesignGuidePublication.cta apply payload fingerprint."
            ),
        },
        {
            "field": "debug_trace.selected_action_updates/action_type/family restamp",
            "classification": CLASS_C,
            "truth_kind": "legacy debug/session compatibility metadata",
            "real_engineering_or_publication_truth": False,
            "debug_or_restamp_metadata": True,
            "needed_before_final_publication_exists": False,
            "blocks_compatibility_only_narrowing": False,
            "rationale": (
                "These debug selected-action fields duplicate the accepted rebound contract for legacy "
                "consumers and should become compatibility/debug-only."
            ),
            "required_proof_before_narrowing": "Same-object debug/session selected-action stamp proof.",
        },
    ],
    "post_core_evidence_rebound": [
        {
            "field": "post_core_evidence_update_mismatch_condition",
            "classification": CLASS_D,
            "truth_kind": "pre-publication safety/reconciliation guard",
            "real_engineering_or_publication_truth": False,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": True,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The mismatch condition protects post-core evidence consistency before final publication. "
                "It should remain safety logic until a proof object records the guard outcome."
            ),
            "required_proof_before_narrowing": (
                "Capture accepted/skipped post-core rebound guard outcome as compute rebound proof."
            ),
        },
        {
            "field": "raw_post_evidence_rebound.item",
            "classification": CLASS_B,
            "truth_kind": "pre-publication selected item input",
            "real_engineering_or_publication_truth": True,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": True,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "The raw rebound item rewrites the primary collapsed item before the compute resolver. "
                "The final publication object can represent the adapted result later, but this mutation "
                "is still pre-publication item authority."
            ),
            "required_proof_before_narrowing": (
                "Prove post-core rebound item identity equals a publication-derived compute input, "
                "or move rebound-item normalization into a Design Brain proof boundary."
            ),
        },
        {
            "field": "post_evidence_cleanup_contract_rebound enabled flag",
            "classification": CLASS_C,
            "truth_kind": "legacy debug/probe metadata",
            "real_engineering_or_publication_truth": False,
            "debug_or_restamp_metadata": True,
            "needed_before_final_publication_exists": False,
            "blocks_compatibility_only_narrowing": False,
            "rationale": (
                "The flag records whether the post-core rebound contract ended enabled. It is a trace/debug "
                "reflection once CTA evidence is represented by FinalDesignGuidePublication."
            ),
            "required_proof_before_narrowing": "Same-object post-core rebound debug flag proof.",
        },
        {
            "field": "collapsed_guidance_items[0] pre-resolver mutation",
            "classification": CLASS_B,
            "truth_kind": "pre-publication selected item list mutation",
            "real_engineering_or_publication_truth": True,
            "debug_or_restamp_metadata": False,
            "needed_before_final_publication_exists": True,
            "blocks_compatibility_only_narrowing": True,
            "rationale": (
                "This mutation controls the item list that the compute resolver consumes. It is still "
                "pre-publication input authority, not a compatibility-only restamp."
            ),
            "required_proof_before_narrowing": (
                "Prove compute resolver can consume a FinalDesignGuidePublication-derived item list."
            ),
        },
    ],
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        path, snapshot = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "snapshot": {}, "passed": False, "current_run": True}
        return {"found": True, "path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS", "current_run": True}
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = matches[-1]
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


def _source_token_checks(source: str) -> dict[str, bool]:
    return {
        "compute_resolver_call_present": "final_compute_resolution = {" in source and "DesignGuideController.compute_selection" in source,
        "compute_resolver_publication_adapter_present": "run_design_guide_controller_compute_publication_handoff_trace_only(" in source,
        "late_rebound_call_present": "resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision(" in source,
        "late_rebound_publication_adapter_present": "rebound_contract" in source and "run_design_guide_controller_compute_publication_handoff_trace_only(" in source,
        "post_core_rebound_call_present": "run_design_guide_controller_compute_rebound_publication_item_trace_only(" in source,
        "post_core_rebound_publication_adapter_present": "build_collapsed_guidance_item_from_final_publication(" in source,
    }


def _count_fields(classification: str) -> int:
    return sum(
        1
        for fields in FIELD_OWNERSHIP.values()
        for field in fields
        if field["classification"] == classification
    )


def _blocking_fields() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path_id, fields in FIELD_OWNERSHIP.items():
        for field in fields:
            if field["blocks_compatibility_only_narrowing"]:
                out.append({"path_id": path_id, **field})
    return out


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Raw Compute Resolver/Rebound Truth Ownership Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Paths audited: `{len(payload['paths'])}`",
        f"- Fields audited: `{payload['field_count']}`",
        f"- Blocking fields: `{len(payload['blocking_fields'])}`",
        f"- Unsafe/unclear fields: `{payload['classification_counts'].get(CLASS_E, 0)}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key in (CLASS_A, CLASS_B, CLASS_C, CLASS_D, CLASS_E):
        lines.append(f"- `{key}`: `{payload['classification_counts'].get(key, 0)}`")
    lines.extend(["", "## Path Details", ""])
    for path_id, fields in payload["paths"].items():
        lines.extend(
            [
                f"### `{path_id}`",
                "",
                "| Field | Class | Truth kind | Blocks narrowing | Required proof |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for field in fields:
            lines.append(
                "| {field} | `{classification}` | {truth_kind} | `{blocks}` | {proof} |".format(
                    field=str(field["field"]).replace("|", "\\|"),
                    classification=str(field["classification"]).replace("|", "\\|"),
                    truth_kind=str(field["truth_kind"]).replace("|", "\\|"),
                    blocks=field["blocks_compatibility_only_narrowing"],
                    proof=str(field["required_proof_before_narrowing"]).replace("|", "\\|"),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Answers",
            "",
            f"- Real engineering/publication truth: `{payload['answers']['real_engineering_publication_truth_fields']}`",
            f"- Debug/restamp metadata: `{payload['answers']['debug_restamp_metadata_fields']}`",
            f"- Needed before final publication exists: `{payload['answers']['pre_publication_input_fields']}`",
            f"- Fields blocking compatibility-only narrowing: `{payload['answers']['blocking_fields']}`",
            "",
            "## Recommendation",
            "",
            payload["smallest_safe_next_implementation_slice"],
            "",
            "## Verification",
            "",
        ]
    )
    for name, result in payload["verification"].items():
        lines.append(f"- `{name}`: `{result['passed']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    same_object_run = _run("tools/verification/design_guide_compute_stage_resolver_same_object_snapshot.py")
    same_object_artifact = _latest("design_guide_compute_stage_resolver_same_object")
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, CONTROLLER, FINAL_PUBLICATION)
        if path.exists()
    )
    token_checks = _source_token_checks(source)

    verification = {
        "compute_stage_same_object_snapshot": {
            **same_object_run,
            "artifact_path": same_object_artifact.get("path"),
            "artifact_passed": same_object_artifact.get("passed") is True,
        },
    }
    classifications = {
        CLASS_A: _count_fields(CLASS_A),
        CLASS_B: _count_fields(CLASS_B),
        CLASS_C: _count_fields(CLASS_C),
        CLASS_D: _count_fields(CLASS_D),
        CLASS_E: _count_fields(CLASS_E),
    }
    blocking = _blocking_fields()
    all_fields = [field for fields in FIELD_OWNERSHIP.values() for field in fields]

    failures: list[str] = []
    if not same_object_run["passed"] or same_object_artifact.get("passed") is not True:
        failures.append("compute_stage_same_object_snapshot_not_passed")
    for token, present in token_checks.items():
        if not present:
            failures.append(f"missing_source_token_{token}")
    if classifications.get(CLASS_E, 0):
        failures.append("unsafe_or_unclear_fields_present")
    if len(FIELD_OWNERSHIP) != 3:
        failures.append(f"expected_3_paths_found_{len(FIELD_OWNERSHIP)}")
    if len(all_fields) != 12:
        failures.append(f"expected_12_fields_found_{len(all_fields)}")

    payload = {
        "schema": "design_guide_raw_compute_resolver_truth_ownership_audit.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "paths": FIELD_OWNERSHIP,
        "field_count": len(all_fields),
        "classification_counts": classifications,
        "blocking_fields": blocking,
        "source_token_checks": token_checks,
        "source_same_object_artifact": same_object_artifact.get("path"),
        "verification": verification,
        "answers": {
            "real_engineering_publication_truth_fields": [
                field["field"] for field in all_fields if field["real_engineering_or_publication_truth"]
            ],
            "debug_restamp_metadata_fields": [
                field["field"] for field in all_fields if field["debug_or_restamp_metadata"]
            ],
            "pre_publication_input_fields": [
                field["field"] for field in all_fields if field["needed_before_final_publication_exists"]
            ],
            "blocking_fields": [field["field"] for field in blocking],
        },
        "smallest_safe_next_implementation_slice": (
            "Add a proof-only compute publication handoff/rebound decision object that records raw resolver "
            "item identity, render reason, state fingerprint, rebound guard outcomes, rebound contract "
            "enabled/updates hashes, and post-core item mutation identity. Keep live compute logic in place; "
            "only after that proof passes should any of the three class-C paths be narrowed."
        ),
        "product_behavior_changed": False,
        "audit_hash": _stable_hash(
            {
                "paths": FIELD_OWNERSHIP,
                "token_checks": token_checks,
                "source_same_object_artifact": same_object_artifact.get("path"),
            }
        ),
    }
    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_raw_compute_resolver_truth_ownership_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_raw_compute_resolver_truth_ownership_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_raw_compute_resolver_truth_ownership_audit {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print("classification_counts:", json.dumps(classifications, sort_keys=True))
    print(f"blocking_fields={len(blocking)}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
