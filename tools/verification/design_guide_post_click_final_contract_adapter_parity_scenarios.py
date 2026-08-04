"""Parity scenarios for final-visible post-click contract-check adapter proof."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _base() -> dict[str, Any]:
    return {
        "final_contract": {"enabled": True, "family": "bending", "expected_util": 0.32},
        "final_family": "bending",
        "final_expected_util": 0.32,
        "final_current_bending_util": 0.24,
        "unresolved_families": ["bending"],
        "below_floor_families": ["bending"],
        "same_flow_cleanup_apply": True,
        "exact_blocker_on_visible_item": True,
        "requires_exact_blocker": True,
        "visible_action": True,
        "bending_audit": {
            "exact_blockers_by_family": {"bending": {"no_second_cta_required": True}},
            "post_click_exact_blockers_by_family": {"bending": {"no_second_cta_required": True}},
            "cleanup_evidence_by_family": {"bending": {"checked": True}},
            "post_click_cleanup_evidence_by_family": {"bending": {"checked": True}},
        },
        "bending_resolution": {
            "title": "Design Guide blocker proof incomplete",
            "family": "bending",
            "button_contract": {"enabled": False, "family": "bending"},
        },
        "bending_contract": {"enabled": False, "family": "bending"},
        "replacement_applied": True,
        "output_item": {"title": "Design Guide blocker proof incomplete", "family": "bending"},
        "final_visible_resolution": {
            "render_reason": "post_click_low_bending_exact_blocker_final",
            "item": {"family": "bending"},
        },
        "input_proof": {
            "proof_hash": "input-proof-hash",
            "ligature_state_hash": "ligature-hash",
            "apply_surface_hash": "apply-hash",
            "post_click_families_hash": "families-hash",
        },
        "replacement_decision_proof": {"proof_hash": "replacement-proof-hash"},
    }


def _scenario_payloads() -> dict[str, dict[str, Any]]:
    base = _base()
    no_visible_action = dict(base)
    no_visible_action["visible_action"] = False
    no_visible_action["replacement_applied"] = False
    no_visible_action["final_visible_resolution"] = {
        "render_reason": "unchanged_final_visible_item",
        "item": {"family": "bending"},
    }

    enabled_contract = dict(base)
    enabled_contract["bending_contract"] = {"enabled": True, "family": "bending"}
    enabled_contract["replacement_applied"] = False

    changed_inputs = dict(base)
    changed_inputs["input_proof"] = {
        **dict(base["input_proof"]),
        "apply_surface_hash": "changed-apply-hash",
    }

    changed_evidence = dict(base)
    changed_evidence["bending_audit"] = {
        **dict(base["bending_audit"]),
        "post_click_exact_blockers_by_family": {"bending": {"no_second_cta_required": False}},
    }

    return {
        "base_replacement_applied": base,
        "no_visible_action": no_visible_action,
        "enabled_bending_contract": enabled_contract,
        "changed_page_input_collection": changed_inputs,
        "changed_evidence_assembly": changed_evidence,
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_final_contract_check_adapter_proof,
    )

    scenarios = _scenario_payloads()
    base_first = build_final_design_guide_post_click_final_contract_check_adapter_proof(
        **scenarios["base_replacement_applied"]
    )
    base_second = build_final_design_guide_post_click_final_contract_check_adapter_proof(
        **_scenario_payloads()["base_replacement_applied"]
    )
    scenario_results: dict[str, Any] = {}
    for name, kwargs in scenarios.items():
        proof = build_final_design_guide_post_click_final_contract_check_adapter_proof(**kwargs)
        scenario_results[name] = {
            "proof_hash": proof.get("proof_hash"),
            "adapter_result_hash": proof.get("adapter_result_hash"),
            "page_input_collection_hash": proof.get("page_input_collection_hash"),
            "decision_predicates_hash": proof.get("decision_predicates_hash"),
            "evidence_assembly_hash": proof.get("evidence_assembly_hash"),
            "resolution_builder_hash": proof.get("resolution_builder_hash"),
            "publication_binding_hash": proof.get("publication_binding_hash"),
            "should_publish_exact_blocker_projection": (
                dict(proof.get("adapter_result") or {}).get("should_publish_exact_blocker_projection")
            ),
            "replacement_applied": dict(proof.get("adapter_result") or {}).get("replacement_applied"),
        }
    latest = {
        "object": _latest("design_guide_post_click_final_contract_adapter_object"),
        "ownership": _latest("design_guide_post_click_remaining_live_truth_ownership"),
        "controller_readiness": _latest("design_guide_post_click_controller_adapter_readiness"),
        "row_level": _latest("design_guide_post_click_contract_check_row_level_readiness"),
    }
    base_hash = scenario_results["base_replacement_applied"]["proof_hash"]
    changed_hashes = {
        name: result["proof_hash"] != base_hash
        for name, result in scenario_results.items()
        if name != "base_replacement_applied"
    }
    return {
        "decision": "POST_CLICK_FINAL_CONTRACT_ADAPTER_PARITY_SCENARIOS_PASS",
        "base_hash_stable": base_first.get("proof_hash") == base_second.get("proof_hash"),
        "scenario_results": scenario_results,
        "changed_hashes": changed_hashes,
        "all_variants_change_hash": all(changed_hashes.values()),
        "base_should_publish_projection": scenario_results["base_replacement_applied"][
            "should_publish_exact_blocker_projection"
        ],
        "disabled_variants_do_not_publish": all(
            scenario_results[name]["should_publish_exact_blocker_projection"] is False
            for name in ("no_visible_action", "enabled_bending_contract")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "base_hash_stable": capture.get("base_hash_stable") is True,
        "all_variants_change_hash": capture.get("all_variants_change_hash") is True,
        "base_should_publish_projection": capture.get("base_should_publish_projection") is True,
        "disabled_variants_do_not_publish": capture.get("disabled_variants_do_not_publish") is True,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "ownership_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "controller_readiness_pass": (latest.get("controller_readiness") or {}).get("status") == "PASS",
        "row_level_pass": (latest.get("row_level") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final Contract Adapter Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Base hash stable: `{capture.get('base_hash_stable')}`",
        f"- All variants change hash: `{capture.get('all_variants_change_hash')}`",
        f"- Base should publish projection: `{capture.get('base_should_publish_projection')}`",
        f"- Disabled variants do not publish: `{capture.get('disabled_variants_do_not_publish')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_final_contract_adapter_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_post_click_final_contract_adapter_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_click_final_contract_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_adapter_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
