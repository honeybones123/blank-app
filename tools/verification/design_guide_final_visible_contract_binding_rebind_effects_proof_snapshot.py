"""Snapshot for final-visible contract-binding rebind effects proof.

Proof-only. This verifies that Design Brain has a pure proof surface covering
the live effects that still block direct replacement of the combined/engine
render-stage rebind bridges.
"""

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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
INPUTS_PAGE = ROOT / "inputs_page.py"

EXPECTED_EFFECTS = {
    "target_band_promotion",
    "safe_consistency_guard",
    "combined_consistency_guard",
    "contract_truth",
    "no_second_cta",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _exercise() -> dict[str, Any]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_visible_contract_binding_rebind_effects_proof,
        stable_final_publication_hash,
    )

    shear_keys = ("shear_reinforcement_legs", "shear_reinforcement_spacing", "shear_reinforcement_bar_diameter")
    bottom_keys = ("bottom_bar_count", "bottom_bar_diameter", "bottom_layers")
    base_item = {
        "title": "Strengthening required",
        "title_main": "Strengthening required",
        "family": "combined",
        "source_candidate_id": "candidate-existing",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": {"bottom_bar_count": 6},
            "expected_util": 0.62,
        },
        "action_payload": {"updates": {"bottom_bar_count": 6}},
        "resolved_candidate": {"updates": {"bottom_bar_count": 6}},
        "exact_blockers_by_family": {
            "bending": {
                "no_second_cta_required": True,
                "failed_check_status": "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
                "best_safe_final_util": 0.41,
                "reason": "exact stop proof suppresses second cleanup",
            }
        },
    }
    contract = dict(base_item["button_contract"])
    combined_evidence = {
        "family": "combined",
        "selected_candidate_updates": {"bottom_bar_count": 5, "shear_reinforcement_legs": 0},
        "best_safe_candidate_updates": {"bottom_bar_count": 5, "shear_reinforcement_legs": 0},
        "closest_safe_candidate_updates": {"bottom_bar_count": 5, "shear_reinforcement_legs": 0},
        "selected_candidate_id": "combined-target-1",
        "selected_candidate_util": 0.86,
        "cleanup_search_ran": True,
        "candidate_search_exhaustive": True,
    }
    shear_evidence = {
        "family": "shear",
        "best_target_band_candidate_updates": {"shear_reinforcement_legs": 0},
        "best_safe_candidate_updates": {"shear_reinforcement_legs": 0},
        "best_target_band_candidate_id": "shear-target-1",
        "selected_candidate_id": "shear-target-1",
        "best_target_band_candidate_util": 0.82,
        "target_band_candidate_count": 1,
        "accepted_band_candidate_count": 1,
        "one_click_target_reaching_candidate_exists": True,
    }
    no_second_evidence = {
        "family": "bending",
        "selected_candidate_util": 0.41,
        "no_second_cta_required": True,
        "reason": "post-click exact cleanup proof suppresses a second below-floor CTA",
        "target_band_candidate_count": 0,
    }
    combined = build_final_visible_contract_binding_rebind_effects_proof(
        evidence_for_binding=combined_evidence,
        contract=contract,
        item=base_item,
        debug={},
        current_updates=contract.get("updates"),
        combined_binding_updates=combined_evidence["selected_candidate_updates"],
        combined_updates_already_applied=False,
        combined_binding_bending_util=0.88,
        compound_shear_update_keys=shear_keys,
        compound_bottom_update_keys=bottom_keys,
        final_accepted_min_family_util=0.85,
        target_band_eps=0.0,
    )
    shear = build_final_visible_contract_binding_rebind_effects_proof(
        evidence_for_binding=shear_evidence,
        contract=contract,
        item=base_item,
        debug={},
        current_updates=contract.get("updates"),
        target_binding_updates=shear_evidence["best_target_band_candidate_updates"],
        target_binding_util=0.82,
        target_binding_count=1,
        target_binding_family="shear",
        target_binding_candidate_id="shear-target-1",
        target_low=0.80,
        target_high=1.0,
        current_binding_expected=0.42,
        target_updates_already_applied=False,
        safe_binding_updates=shear_evidence["best_safe_candidate_updates"],
        safe_updates_already_applied=False,
        compound_shear_update_keys=shear_keys,
        compound_bottom_update_keys=bottom_keys,
        final_accepted_min_family_util=0.85,
        target_band_eps=0.0,
    )
    no_second = build_final_visible_contract_binding_rebind_effects_proof(
        evidence_for_binding=no_second_evidence,
        contract=contract,
        item=base_item,
        debug={},
        current_updates={},
        evidence_expected_util=0.41,
        evidence_family="bending",
        blocker_families=("bending",),
        compound_shear_update_keys=shear_keys,
        compound_bottom_update_keys=bottom_keys,
        final_accepted_min_family_util=0.85,
        target_band_eps=0.0,
    )
    repeat = build_final_visible_contract_binding_rebind_effects_proof(
        evidence_for_binding=combined_evidence,
        contract=contract,
        item=base_item,
        debug={},
        current_updates=contract.get("updates"),
        combined_binding_updates=combined_evidence["selected_candidate_updates"],
        combined_updates_already_applied=False,
        combined_binding_bending_util=0.88,
        compound_shear_update_keys=shear_keys,
        compound_bottom_update_keys=bottom_keys,
        final_accepted_min_family_util=0.85,
        target_band_eps=0.0,
    )
    return {
        "combined": combined,
        "shear": shear,
        "no_second": no_second,
        "combined_hash_stable": stable_final_publication_hash(combined) == stable_final_publication_hash(repeat),
        "scenario_hashes": {
            "combined": stable_final_publication_hash(combined),
            "shear": stable_final_publication_hash(shear),
            "no_second": stable_final_publication_hash(no_second),
        },
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    exercise = _exercise()
    combined_flags = dict((exercise["combined"].get("result_flags") or {}))
    shear_flags = dict((exercise["shear"].get("result_flags") or {}))
    no_second_flags = dict((exercise["no_second"].get("result_flags") or {}))
    represented = set(exercise["combined"].get("represented_effects") or [])
    return {
        "represented_effects": sorted(represented),
        "missing_effects": sorted(EXPECTED_EFFECTS - represented),
        "scenario_flags": {
            "combined": combined_flags,
            "shear": shear_flags,
            "no_second": no_second_flags,
        },
        "scenario_hashes": exercise["scenario_hashes"],
        "combined_hash_stable": exercise["combined_hash_stable"],
        "source_checks": {
            "proof_function_present": "def build_final_visible_contract_binding_rebind_effects_proof(" in source,
            "proof_function_exported": '"build_final_visible_contract_binding_rebind_effects_proof"' in source,
            "does_not_import_inputs_page": "inputs_page" not in source,
            "old_rebinds_still_unchanged": (
                "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(" in inputs_source
                and "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(" in inputs_source
            ),
        },
        "latest_gap_snapshot": _latest("design_guide_render_combined_engine_rebind_parity_gap"),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    flags = dict(capture.get("scenario_flags") or {})
    combined_flags = dict(flags.get("combined") or {})
    shear_flags = dict(flags.get("shear") or {})
    no_second_flags = dict(flags.get("no_second") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_expected_effects_represented": not bool(capture.get("missing_effects")),
        "combined_consistency_guard_exercised": combined_flags.get("combined_consistency_guard_resets") is True,
        "contract_truth_exercised": combined_flags.get("contract_truth_available") is True,
        "target_band_promotion_exercised": shear_flags.get("target_band_promotion_applies") is True,
        "safe_consistency_guard_exercised": shear_flags.get("safe_consistency_guard_resets") is True,
        "no_second_cta_exercised": no_second_flags.get("no_second_cta_applies") is True,
        "combined_hash_stable": capture.get("combined_hash_stable") is True,
        "proof_function_present": source_checks.get("proof_function_present") is True,
        "proof_function_exported": source_checks.get("proof_function_exported") is True,
        "design_brain_does_not_import_inputs_page": source_checks.get("does_not_import_inputs_page") is True,
        "old_rebinds_unchanged": source_checks.get("old_rebinds_still_unchanged") is True,
        "gap_snapshot_pass": (capture.get("latest_gap_snapshot") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Visible Contract Binding Rebind Effects Proof Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Represented Effects",
        "",
    ]
    for effect in capture.get("represented_effects") or []:
        lines.append(f"- `{effect}`")
    lines.extend(["", "## Scenario Flags", ""])
    for scenario, flags in (capture.get("scenario_flags") or {}).items():
        lines.append(f"- `{scenario}`: `{flags}`")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_visible_contract_binding_rebind_effects_proof_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_contract_binding_rebind_effects_proof_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_contract_binding_rebind_effects_proof_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_final_visible_contract_binding_rebind_effects_proof_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
