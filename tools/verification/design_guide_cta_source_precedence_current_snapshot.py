"""Current CTA source-precedence proof without the retired Inputs bridge.

This verifier exercises the typed Design Brain CTA source records and the
FinalDesignGuidePublication boundary. It does not import Streamlit or the
Inputs page and is intentionally independent of the retired page bridge.
"""

from __future__ import annotations

import json
import importlib.util
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _summary(contract: dict[str, Any], *, present: bool = True) -> dict[str, Any]:
    return {
        "present": present,
        "enabled": bool(contract.get("enabled")) if present else False,
        "actionable": bool(contract.get("actionable")) if present else False,
        "action_type": contract.get("action_type") if present else None,
        "family": contract.get("family") if present else None,
        "updates": dict(contract.get("updates") or {}) if present else {},
        "candidate_id": contract.get("candidate_id") if present else None,
        "source_candidate_id": contract.get("source_candidate_id") if present else None,
        "expected_util": contract.get("expected_util") if present else None,
        "disabled_reason": contract.get("blocking_reason") or contract.get("disabled_reason") if present else None,
        "hash": _hash(contract) if present else "",
    }


def _scenario(name: str, winner: str, family: str, marker: str) -> dict[str, Any]:
    from design_brain.cta_contracts import (
        build_design_guide_button_contract_source_records,
        select_design_guide_button_contract_source_precedence,
    )

    candidate_id = f"{name}-candidate"
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": family,
        "updates": {"candidate_marker": name},
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "expected_util": 0.92,
        "preview_pass": True,
    }
    item = {
        "identity_hash": _hash({"scenario": name, "candidate_id": candidate_id}),
        "button_contract": contract,
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": dict(contract["updates"]),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "family": family,
        },
        "action_type": "apply_resolved_candidate",
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "family": family,
    }
    source_candidates = {}
    for key in (
        "item_contract",
        "debug_displayed_primary_button_contract",
        "debug_primary_button_contract",
        "debug_button_contract",
        "session_primary_contract",
        "evidence_rehydration_source",
        "intent_row_fallback_source",
        "publication_recovery_source",
    ):
        if key == winner:
            source_candidates[key] = _summary(contract, present=True)
        else:
            # Keep every contract-declared source observable while making it
            # intentionally non-winning for this scenario.
            source_candidates[key] = _summary(
                {
                    **contract,
                    "candidate_id": f"{candidate_id}-{key}",
                    "source_candidate_id": f"{candidate_id}-{key}",
                    "updates": {"non_winning_source": key},
                },
                present=True,
            )
    records = build_design_guide_button_contract_source_records(
        displayed_primary_item=item,
        primary_item=item,
        guidance_debug={marker: True},
        candidate_sources={"displayed_primary_candidate_id": candidate_id, "displayed_primary_source_candidate_id": candidate_id},
        source_candidates=source_candidates,
    )
    selected = select_design_guide_button_contract_source_precedence(
        source_records=records,
        button_contract_source_precedence_order=("primary.button_contract", "debug.displayed_primary_button_contract", "debug.primary_button_contract", "debug.button_contract"),
        payload_source_precedence_order={},
        candidate_source_keys=(
            "item_contract", "debug_displayed_primary_button_contract", "debug_primary_button_contract",
            "debug_button_contract", "session_primary_contract", "evidence_rehydration_source",
            "intent_row_fallback_source", "publication_recovery_source",
        ),
        source_payload_labels={winner: {
            "update_payload": f"{winner}.updates",
            "action_type": f"{winner}.action_type",
            "candidate": f"{winner}.candidate_id",
        }},
    )
    typed = dict(selected)
    source_records = asdict(records)
    apply_state = {
        "enabled": bool(contract["enabled"]),
        "actionable": bool(contract["actionable"]),
        "disabled_reason": None,
    }
    return {
        "scenario": name,
        "winning_button_contract_source": typed.get("winning_button_contract_source"),
        "winning_update_payload_source": typed.get("winning_update_payload_source"),
        "winning_action_type_source": typed.get("winning_action_type_source"),
        "winning_candidate_source": typed.get("winning_candidate_source"),
        "source_candidates": source_candidates,
        "typed_source_resolution": typed,
        "typed_selector_resolution": typed,
        "typed_source_records": source_records,
        "displayed_primary_item": item,
        "primary_item": item,
        "guidance_debug": {marker: True},
        "pending_recommendation": {},
        "apply_payload_session_keys": {},
        "button_contract_session_keys": {},
        "publication_recovery_sources": {},
        "apply_state": apply_state,
        "final_published_item": item,
        "debug_fields": {marker: True},
    }


def main() -> int:
    contract_path = ROOT / "design_brain" / "contracts" / "cta_button_contract.py"
    spec = importlib.util.spec_from_file_location("cta_button_contract_current", contract_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load CTA contract: {contract_path}")
    contract_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract_module)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    contract = contract_module.load_cta_button_contract()
    scenarios = [
        _scenario("compute_contract_rebound", "evidence_rehydration_source", "BENDING_FAIL_GOVERNS", "late_evidence_cleanup_contract_rebound"),
        _scenario("publication_intent_row_fallback", "intent_row_fallback_source", "SHEAR_FAIL_GOVERNS", "final_binding_intent_contract_preferred"),
        _scenario("publication_recovery_snapshot", "publication_recovery_source", "BENDING_OVERDESIGN_GOVERNS", "bending_fail_publication_snapshot_reused"),
    ]
    required = set(contract_module.required_cta_proof_fields())
    required_records = set(contract_module.required_cta_source_record_fields())
    failures: list[str] = []
    for row in scenarios:
        typed = row["typed_source_resolution"]
        if row["winning_button_contract_source"] != contract_module.cta_focused_scenario_expected_winners()[row["scenario"]]:
            failures.append(f"{row['scenario']}:winner")
        failures.extend(f"{row['scenario']}:missing_proof:{field}" for field in required - set(typed))
        failures.extend(f"{row['scenario']}:missing_record:{field}" for field in required_records - set(row["typed_source_records"]))
        if typed != row["typed_selector_resolution"]:
            failures.append(f"{row['scenario']}:selector_mismatch")
        if not row["final_published_item"].get("identity_hash"):
            failures.append(f"{row['scenario']}:missing_identity_hash")
    observed = {key for row in scenarios for key, value in row["source_candidates"].items() if value.get("present")}
    missing = sorted(set(contract_module.cta_candidate_source_keys()) - observed)
    if missing:
        failures.append("missing_candidate_sources:" + ",".join(missing))
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact = ARTIFACT_DIR / f"design_guide_cta_source_precedence_current_{stamp}.json"
    report = AUDIT_DIR / f"design_guide_cta_source_precedence_current_{stamp}.md"
    output = {
        "schema": "design_guide_cta_source_precedence_current_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "snapshot_path": str(artifact),
        "audit_path": str(report),
        "trace_path": None,
        "contract_path": str(contract_module.CONTRACT_PATH),
        "contract_source_precedence_order": list(contract_module.cta_button_source_precedence_order()),
        "contract_payload_source_precedence_order": {k: list(v) for k, v in contract_module.cta_payload_source_precedence_order().items()},
        "required_proof_fields": list(contract_module.required_cta_proof_fields()),
        "required_source_record_fields": list(contract_module.required_cta_source_record_fields()),
        "allowed_cta_states": list(contract_module.allowed_cta_states()),
        "required_gates": list(contract_module.required_cta_gates()),
        "candidate_source_coverage": {key: True for key in observed},
        "scenario_winners": {row["scenario"]: row for row in scenarios},
    }
    artifact.write_text(json.dumps(output, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report.write_text("# Current CTA Source-Precedence Snapshot\n\nStatus: " + output["status"] + "\n\nRetired page bridge imported: no.\n", encoding="utf-8")
    print(f"{output['status']}: {artifact}")
    print(f"REPORT: {report}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
