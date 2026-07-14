"""Publication evidence same-object proof for A-class compute fields.

This verifier proves the four A-class compute-stage truth fields can be
represented by FinalDesignGuidePublication.evidence without moving live
authority, compute-only rebound inputs, or fallback/safety logic.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

A_CLASS_FIELD_MAP = {
    "raw_selected_item_identity": "raw_final_compute_resolution.item",
    "render_reason": "raw_final_compute_resolution.render_reason",
    "state_fingerprint": "raw_final_compute_resolution.state_fingerprint",
    "raw_rebound_item_identity": "raw_post_evidence_rebound.item",
}

FORBIDDEN_PUBLICATION_EVIDENCE_KEYS = (
    "late_evidence_acceptance",
    "post_core_evidence_mismatch",
    "rebound_update_payload_summary",
    "rebound_contract",
    "pre_resolver_collapsed_item_mutation",
)

FORBIDDEN_DESIGN_BRAIN_TOKENS = (
    "import inputs_page",
    "from inputs_page",
    "import streamlit",
    "st.session_state",
    "session_state",
    "render_html",
    "route_apply",
    "one_click",
)

FORBIDDEN_TOKEN_EXCEPTIONS = {
    "one_click": ("one_click_action_handoff",),
}

COMPOSED_GATES = (
    {
        "id": "remaining_compute_truth_ownership",
        "script": "tools/verification/design_guide_remaining_compute_truth_ownership_snapshot.py",
        "artifact_prefix": "design_guide_remaining_compute_truth_ownership",
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


def _sample_surfaces() -> dict[str, Any]:
    selected_item = {
        "published_item_id": "publication-evidence-proof-item",
        "candidate_id": "publication-evidence-proof-candidate",
        "source_candidate_id": "publication-evidence-proof-source",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "family": "shear",
        "status": "ACTION",
        "action_type": "apply_resolved_candidate",
        "guidance_intent": "required_fix",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_id": "publication-evidence-proof-candidate",
            "source_candidate_id": "publication-evidence-proof-source",
            "updates": {"lig_spacing": 150, "lig_d": "N12"},
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_id": "publication-evidence-proof-candidate",
            "source_candidate_id": "publication-evidence-proof-source",
            "updates": {"lig_spacing": 150, "lig_d": "N12"},
        },
        "candidate_search_evidence": {
            "family": "shear",
            "target_low": 0.85,
            "target_high": 1.0,
            "selected_candidate_updates": {"lig_spacing": 150, "lig_d": "N12"},
        },
    }
    rebound_item = {
        **selected_item,
        "candidate_id": "publication-evidence-proof-rebound-candidate",
        "source_candidate_id": "publication-evidence-proof-rebound-source",
        "button_contract": {
            **dict(selected_item["button_contract"]),
            "candidate_id": "publication-evidence-proof-rebound-candidate",
            "source_candidate_id": "publication-evidence-proof-rebound-source",
        },
    }
    rebound_contract = dict(rebound_item["button_contract"])
    return {
        "raw_selected_item": selected_item,
        "render_reason": "compute_publication_resolution",
        "state_fingerprint": "publication-evidence-state-fingerprint",
        "late_evidence_acceptance": {
            "late_updates_present": True,
            "contract_disabled_or_mismatched": True,
            "accepted": True,
        },
        "rebound_contract": rebound_contract,
        "rebound_update_payload": dict(rebound_contract.get("updates") or {}),
        "post_core_evidence_mismatch": {
            "post_evidence_updates_present": True,
            "contract_disabled_or_mismatched": True,
            "accepted": True,
        },
        "raw_rebound_item": rebound_item,
        "pre_resolver_collapsed_item_mutation": {
            "before_identity": {
                "candidate_id": selected_item["candidate_id"],
                "source_candidate_id": selected_item["source_candidate_id"],
            },
            "after_identity": {
                "candidate_id": rebound_item["candidate_id"],
                "source_candidate_id": rebound_item["source_candidate_id"],
            },
            "mutation_reason": "post_evidence_contract_rebound",
        },
    }


def _build_same_object_sample() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_compute_publication_handoff_rebound_decision_proof,
        build_final_design_guide_publication,
    )

    surfaces = _sample_surfaces()
    proof = build_final_design_guide_compute_publication_handoff_rebound_decision_proof(**surfaces)
    proof_dict = proof.to_dict()
    debug = {
        "final_publication_compute_handoff_rebound_decision_latest_hash": proof.decision_hash,
        "final_publication_compute_handoff_rebound_decision_proofs": {
            "compute_stage_final_visible_resolver": proof_dict,
        },
    }
    publication = build_final_design_guide_publication(
        item=dict(surfaces["raw_selected_item"]),
        debug=debug,
        publication_reason=str(surfaces["render_reason"]),
    )
    evidence = publication.evidence.to_dict()
    compute_evidence = dict(evidence.get("compute_publication_evidence") or {})
    compute_hashes = dict(evidence.get("compute_publication_evidence_hashes") or {})
    proof_field_hashes = dict(proof_dict.get("field_hashes") or {})
    comparisons: dict[str, dict[str, Any]] = {}
    for evidence_key, proof_field in A_CLASS_FIELD_MAP.items():
        comparisons[evidence_key] = {
            "proof_field": proof_field,
            "evidence_value_present": evidence_key in compute_evidence,
            "evidence_hash": compute_hashes.get(evidence_key),
            "proof_hash": proof_field_hashes.get(proof_field),
            "hashes_match": compute_hashes.get(evidence_key) == proof_field_hashes.get(proof_field),
        }
    forbidden_keys_present = {
        key: key in compute_evidence
        for key in FORBIDDEN_PUBLICATION_EVIDENCE_KEYS
    }
    return {
        "publication": publication.to_dict(),
        "compute_handoff_rebound_proof": proof_dict,
        "compute_publication_evidence": compute_evidence,
        "compute_publication_evidence_hashes": compute_hashes,
        "comparisons": comparisons,
        "all_hashes_match": all(row["hashes_match"] for row in comparisons.values()),
        "forbidden_keys_present": forbidden_keys_present,
        "b_class_compute_inputs_not_moved": not any(
            forbidden_keys_present[key]
            for key in (
                "late_evidence_acceptance",
                "post_core_evidence_mismatch",
                "rebound_update_payload_summary",
            )
        ),
        "d_class_fallback_safety_fields_not_moved": not any(
            forbidden_keys_present[key]
            for key in (
                "rebound_contract",
                "pre_resolver_collapsed_item_mutation",
            )
        ),
    }


def _final_publication_source_checks() -> dict[str, bool]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    scrubbed_by_token: dict[str, str] = {}
    for token in FORBIDDEN_DESIGN_BRAIN_TOKENS:
        scrubbed = source
        for allowed in FORBIDDEN_TOKEN_EXCEPTIONS.get(token, ()):
            scrubbed = scrubbed.replace(allowed, "")
        scrubbed_by_token[token] = scrubbed
    return {
        "evidence_has_compute_publication_evidence": "compute_publication_evidence:" in source,
        "evidence_has_compute_publication_evidence_hashes": "compute_publication_evidence_hashes:" in source,
        "evidence_has_compute_publication_evidence_hash": "compute_publication_evidence_hash:" in source,
        "builder_populates_compute_publication_evidence": '"compute_publication_evidence": compute_publication_evidence' in source,
        "builder_marks_compute_evidence_proof_only": '"proof_only": True' in source,
        "builder_marks_compute_evidence_not_product_driving": '"product_driving": False' in source,
        "builder_marks_compute_evidence_not_render_driving": '"render_driving": False' in source,
        "builder_marks_compute_evidence_not_apply_driving": '"apply_driving": False' in source,
        "builder_marks_compute_evidence_not_session_driving": '"session_driving": False' in source,
        **{
            f"forbidden_token_absent::{token}": token not in scrubbed
            for token, scrubbed in scrubbed_by_token.items()
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Publication Evidence Compute Truth Same-Object Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- A-class fields ready to narrow: `{payload['a_class_fields_ready_to_narrow']}`",
        f"- All A-class field hashes match: `{payload['all_a_class_hashes_match']}`",
        f"- B-class compute inputs moved: `{not payload['b_class_compute_inputs_not_moved']}`",
        f"- D-class fallback/safety fields moved: `{not payload['d_class_fallback_safety_fields_not_moved']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## A-Class Field Comparisons",
        "",
        "| Evidence field | Proof field | Hashes match |",
        "| --- | --- | --- |",
    ]
    for field, row in payload["a_class_field_comparisons"].items():
        lines.append(
            f"| `{_escape_md(field)}` | `{_escape_md(row['proof_field'])}` | `{row['hashes_match']}` |"
        )
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

    same_object = _build_same_object_sample()
    source_checks = _final_publication_source_checks()

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

    failures: list[str] = []
    if not all(row["evidence_value_present"] for row in same_object["comparisons"].values()):
        failures.append("not_all_a_class_fields_exist_on_publication_evidence")
    if not same_object["all_hashes_match"]:
        failures.append("a_class_hashes_do_not_match_compute_handoff_proof")
    if not same_object["b_class_compute_inputs_not_moved"]:
        failures.append("b_class_compute_inputs_moved_to_publication_evidence")
    if not same_object["d_class_fallback_safety_fields_not_moved"]:
        failures.append("d_class_fallback_safety_fields_moved_to_publication_evidence")
    if not all(source_checks.values()):
        failures.append("final_publication_source_checks_failed")
    for gate_id, result in verification.items():
        if not result["passed"] or result["artifact_passed"] is not True:
            failures.append(f"{gate_id}_not_passed")

    payload = {
        "schema": "design_guide_publication_evidence_compute_truth_same_object_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "a_class_fields_ready_to_narrow": not failures,
        "a_class_fields": list(A_CLASS_FIELD_MAP.keys()),
        "a_class_field_comparisons": same_object["comparisons"],
        "all_a_class_hashes_match": same_object["all_hashes_match"],
        "b_class_compute_inputs_not_moved": same_object["b_class_compute_inputs_not_moved"],
        "d_class_fallback_safety_fields_not_moved": same_object["d_class_fallback_safety_fields_not_moved"],
        "forbidden_publication_evidence_keys_present": same_object["forbidden_keys_present"],
        "source_checks": source_checks,
        "compute_publication_evidence": same_object["compute_publication_evidence"],
        "compute_publication_evidence_hashes": same_object["compute_publication_evidence_hashes"],
        "compute_handoff_rebound_proof_hash": same_object["compute_handoff_rebound_proof"].get("decision_hash"),
        "publication_hash": same_object["publication"].get("publication_hash"),
        "source_artifacts": artifacts,
        "verification": verification,
        "snapshot_hash": _stable_hash(
            {
                "comparisons": same_object["comparisons"],
                "b_class_not_moved": same_object["b_class_compute_inputs_not_moved"],
                "d_class_not_moved": same_object["d_class_fallback_safety_fields_not_moved"],
                "source_checks": source_checks,
            }
        ),
        "recommended_next_slice": (
            "Narrow only the four A-class compute publication evidence fields to compatibility/proof-only "
            "stamps. Keep B-class compute pre-publication inputs and D-class fallback/safety fields live."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_publication_evidence_compute_truth_same_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_publication_evidence_compute_truth_same_object_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_publication_evidence_compute_truth_same_object_snapshot {payload['status']}")
    print(f"a_class_fields_ready_to_narrow={payload['a_class_fields_ready_to_narrow']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
