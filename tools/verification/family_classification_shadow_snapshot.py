"""Shadow snapshot for the Design Brain family-classification contract runtime.

The snapshot compares the current live family chooser with the contract runtime
without using the contract result to drive product behaviour.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.family_classification_runtime import (  # noqa: E402
    classify_family_from_whole_beam_evidence,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

CANONICAL_LIVE_FAMILY_ALIASES = {
    "COMBINED_BENDING_SHEAR_FAIL": "BENDING_AND_SHEAR_FAIL_GOVERN",
}

ACCEPTED_PRODUCT_MIGRATION_DRIFTS = {
    "shear_fail_bending_optimise": {
        "live_family": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "contract_family": "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
        "reason": "contract uses the accepted optimise naming while legacy live chooser still emits the overdesign alias",
    },
}


BASE_FLAGS = {
    "geometry_detailing_fail": False,
    "serviceability_fail": False,
    "bending_fail": False,
    "shear_fail": False,
    "min_bending_reo_fail": False,
    "min_shear_reo_fail": False,
    "bending_overdesigned": False,
    "shear_overdesigned": False,
    "bending_within_target_band": False,
    "shear_within_target_band": False,
    "locked_repair_blocked": False,
    "legal_repair_exists": False,
    "repair_required": False,
    "exact_stop_proven": False,
    "bending_acceptable": False,
    "shear_acceptable": False,
}

BASE_EVIDENCE = {
    "bending_utilisation": 0.9,
    "shear_utilisation": 0.9,
    "bending_state": "TARGET",
    "shear_state": "TARGET",
    "serviceability_state": "PASS",
    "geometry_detailing_state": "PASS",
    "minimum_bending_reo_state": "PASS",
    "minimum_shear_reo_state": "PASS",
    "geometry_locked": False,
    "reo_locked": False,
    "can_strengthen_bending": False,
    "can_strengthen_shear": False,
    "can_optimise_bending_without_hurting_shear": False,
    "can_optimise_shear_without_hurting_bending": False,
    "exact_stop_available": False,
    "no_valid_repair_available": False,
}


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _case(case_id: str, *, flags: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    raw_flags = dict(BASE_FLAGS)
    raw_flags.update(flags)
    whole_beam = dict(BASE_EVIDENCE)
    whole_beam.update(evidence)
    return {
        "case_id": case_id,
        "raw_flags": raw_flags,
        "whole_beam_evidence": whole_beam,
    }


CASES = [
    _case(
        "bending_fail_only",
        flags={"bending_fail": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 1.12,
            "shear_utilisation": 0.93,
            "bending_state": "FAIL",
            "can_strengthen_bending": True,
        },
    ),
    _case(
        "shear_fail_only",
        flags={"shear_fail": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 0.94,
            "shear_utilisation": 1.16,
            "shear_state": "FAIL",
            "can_strengthen_shear": True,
        },
    ),
    _case(
        "combined_fail",
        flags={"bending_fail": True, "shear_fail": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 1.11,
            "shear_utilisation": 1.18,
            "bending_state": "FAIL",
            "shear_state": "FAIL",
            "can_strengthen_bending": True,
            "can_strengthen_shear": True,
        },
    ),
    _case(
        "bending_fail_shear_optimise",
        flags={"bending_fail": True, "shear_overdesigned": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 1.13,
            "shear_utilisation": 0.72,
            "bending_state": "FAIL",
            "shear_state": "OVERDESIGNED",
            "can_strengthen_bending": True,
            "can_optimise_shear_without_hurting_bending": True,
        },
    ),
    _case(
        "shear_fail_bending_optimise",
        flags={"shear_fail": True, "bending_overdesigned": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 0.74,
            "shear_utilisation": 1.15,
            "bending_state": "OVERDESIGNED",
            "shear_state": "FAIL",
            "can_strengthen_shear": True,
            "can_optimise_bending_without_hurting_shear": True,
        },
    ),
    _case(
        "combined_overdesign",
        flags={"bending_overdesigned": True, "shear_overdesigned": True},
        evidence={
            "bending_utilisation": 0.72,
            "shear_utilisation": 0.76,
            "bending_state": "OVERDESIGNED",
            "shear_state": "OVERDESIGNED",
            "can_optimise_bending_without_hurting_shear": True,
            "can_optimise_shear_without_hurting_bending": True,
        },
    ),
    _case(
        "bending_overdesign",
        flags={"bending_overdesigned": True, "shear_within_target_band": True, "shear_acceptable": True},
        evidence={
            "bending_utilisation": 0.76,
            "shear_utilisation": 0.91,
            "bending_state": "OVERDESIGNED",
            "can_optimise_bending_without_hurting_shear": True,
        },
    ),
    _case(
        "shear_overdesign",
        flags={"shear_overdesigned": True, "bending_within_target_band": True, "bending_acceptable": True},
        evidence={
            "bending_utilisation": 0.91,
            "shear_utilisation": 0.76,
            "shear_state": "OVERDESIGNED",
            "can_optimise_shear_without_hurting_bending": True,
        },
    ),
    _case(
        "target_band_reached",
        flags={"bending_within_target_band": True, "shear_within_target_band": True},
        evidence={"bending_utilisation": 0.92, "shear_utilisation": 0.95},
    ),
    _case(
        "locked_no_repair",
        flags={"shear_fail": True, "repair_required": True, "locked_repair_blocked": True},
        evidence={
            "bending_utilisation": 0.94,
            "shear_utilisation": 1.18,
            "shear_state": "FAIL",
            "reo_locked": True,
            "no_valid_repair_available": True,
        },
    ),
    _case(
        "exact_stop",
        flags={"exact_stop_proven": True},
        evidence={
            "bending_utilisation": 0.98,
            "shear_utilisation": 0.97,
            "exact_stop_available": True,
        },
    ),
    _case(
        "serviceability",
        flags={"serviceability_fail": True},
        evidence={
            "bending_utilisation": 0.96,
            "shear_utilisation": 0.95,
            "serviceability_state": "FAIL",
        },
    ),
    _case(
        "geometry_detailing",
        flags={"geometry_detailing_fail": True},
        evidence={
            "bending_utilisation": 0.94,
            "shear_utilisation": 0.96,
            "geometry_detailing_state": "BLOCKED",
        },
    ),
]


def _explain_drift(case: dict[str, Any], live: str, contract: str) -> dict[str, str]:
    reason = "live selected family differs from contract-selected family"
    if live == "COMBINED_BENDING_SHEAR_FAIL" and contract == "BENDING_AND_SHEAR_FAIL_GOVERN":
        reason = "combined-fail family ID/name differs between legacy live chooser and new contract"
    elif contract in {"BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS", "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS"}:
        reason = "new contract has mixed strengthen-and-optimise family that legacy live chooser does not expose"
    elif case["case_id"] in {"exact_stop", "target_band_reached"}:
        reason = "terminal exact-stop/target-band priority differs or overlaps in legacy live chooser"
    return {
        "scenario": case["case_id"],
        "live_family": live,
        "contract_family": contract,
        "reason": reason,
        "which_is_correct": "requires owner decision before cutover",
        "required_contract_update": "none unless contract priority/ID is intentionally changed",
        "required_product_update": "update live classification only after shadow parity decision and product gates",
    }


def _canonical_live_family(family_id: str) -> str:
    family = str(family_id or "").strip()
    return CANONICAL_LIVE_FAMILY_ALIASES.get(family, family)


def _accepted_product_migration_drift(case_id: str, live: str, contract: str) -> dict[str, str] | None:
    expected = ACCEPTED_PRODUCT_MIGRATION_DRIFTS.get(case_id)
    if not expected:
        return None
    if expected["live_family"] != live or expected["contract_family"] != contract:
        return None
    return {
        "scenario": case_id,
        "live_family": live,
        "contract_family": contract,
        "reason": expected["reason"],
        "which_is_correct": "contract family is accepted; live product migration still required",
        "required_contract_update": "none",
        "required_product_update": "add live support for the mixed governing family without changing CTA/publication/apply/wording ownership",
    }


def _write_drift_audit(
    *,
    accepted_aliases: list[dict[str, Any]],
    accepted_product_drifts: list[dict[str, Any]],
    unexpected_drifts: list[dict[str, Any]],
    path: Path,
) -> None:
    status = "UNEXPECTED_DRIFT" if unexpected_drifts else "ACCEPTED_MIGRATION_DRIFT"
    lines = [
        "# Family Classification Contract Drift Audit",
        "",
        f"Status: {status}",
        "",
        "The contract runtime was executed in shadow mode only. Product-selected family behaviour was not changed.",
        "",
        "## Accepted Naming Aliases",
        "",
    ]
    if not accepted_aliases:
        lines.append("- none")
    for alias in accepted_aliases:
        lines.extend(
            [
                f"### {alias['scenario']}",
                "",
                f"- live family: `{alias['live_family']}`",
                f"- canonical live family: `{alias['canonical_live_family']}`",
                f"- contract family: `{alias['contract_family']}`",
                "- decision: legacy combined-fail runtime name is treated as an accepted alias for the contract family ID",
                "- required product update: migrate runtime/publication references later under dedicated product gates",
                "",
            ]
        )
    lines.extend(["", "## Accepted Product-Migration Drifts", ""])
    if not accepted_product_drifts:
        lines.append("- none")
    for drift in accepted_product_drifts:
        lines.extend(
            [
                f"### {drift['scenario']}",
                "",
                f"- live family: `{drift['live_family']}`",
                f"- contract family: `{drift['contract_family']}`",
                f"- reason: {drift['reason']}",
                f"- which is correct: {drift['which_is_correct']}",
                f"- required contract update: {drift['required_contract_update']}",
                f"- required product update: {drift['required_product_update']}",
                "",
            ]
        )
    lines.extend(["", "## Unexpected Drifts", ""])
    if not unexpected_drifts:
        lines.append("- none")
    for drift in unexpected_drifts:
        lines.extend(
            [
                f"### {drift['scenario']}",
                "",
                f"- live family: `{drift['live_family']}`",
                f"- contract family: `{drift['contract_family']}`",
                f"- reason: {drift['reason']}",
                f"- which is correct: {drift['which_is_correct']}",
                f"- required contract update: {drift['required_contract_update']}",
                f"- required product update: {drift['required_product_update']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_report(output: dict[str, Any], path: Path) -> None:
    lines = [
        "# Family Classification Shadow Snapshot",
        "",
        f"Status: {output['status']}",
        "",
        "## Summary",
        "",
        f"- case count: {output['case_count']}",
        f"- true parity count: {output['true_parity_count']}",
        f"- accepted naming alias count: {len(output['accepted_naming_aliases'])}",
        f"- accepted product-migration drift count: {len(output['accepted_product_migration_drifts'])}",
        f"- unexpected drift count: {len(output['unexpected_drifts'])}",
        f"- artifact: `{output['artifact']}`",
    ]
    if output.get("drift_audit"):
        lines.append(f"- drift audit: `{output['drift_audit']}`")
    lines.extend(["", "## Cases", ""])
    for case in output["cases"]:
        marker = "PASS" if case["parity_status"] != "unexpected_drift" else "FAIL"
        lines.append(
            f"- {marker} `{case['case_id']}` ({case['parity_status']}): "
            f"live `{case['live_selected_family']}`, canonical `{case['live_selected_family_canonical']}`, "
            f"contract `{case['contract_selected_family']}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    case_results: list[dict[str, Any]] = []
    accepted_aliases: list[dict[str, Any]] = []
    accepted_product_drifts: list[dict[str, Any]] = []
    unexpected_drifts: list[dict[str, Any]] = []
    true_parity_count = 0

    for case in CASES:
        live = classify_family_from_raw_flags(case["raw_flags"], evidence={"case_id": case["case_id"]})
        contract = classify_family_from_whole_beam_evidence(case["whole_beam_evidence"])
        live_family = str(live.get("selected_family_id") or "")
        canonical_live_family = _canonical_live_family(live_family)
        contract_family = str(contract.get("selected_family_id") or "")
        family_match = canonical_live_family == contract_family
        parity_status = "true_parity"
        accepted = None
        if family_match and live_family == contract_family:
            true_parity_count += 1
        elif family_match:
            parity_status = "accepted_naming_alias"
            accepted_aliases.append(
                {
                    "scenario": case["case_id"],
                    "live_family": live_family,
                    "canonical_live_family": canonical_live_family,
                    "contract_family": contract_family,
                }
            )
        else:
            accepted = _accepted_product_migration_drift(case["case_id"], live_family, contract_family)
            if accepted:
                parity_status = "accepted_product_migration_drift"
                accepted_product_drifts.append(accepted)
            else:
                parity_status = "unexpected_drift"
                unexpected_drifts.append(_explain_drift(case, live_family, contract_family))
        result = {
            "case_id": case["case_id"],
            "live_selected_family": live_family,
            "live_selected_family_canonical": canonical_live_family,
            "contract_selected_family": contract_family,
            "classification_reason": contract.get("classification_reason"),
            "priority_matched": family_match,
            "family_match": family_match,
            "parity_status": parity_status,
            "whole_beam_state": contract.get("whole_beam_state"),
            "classification_hash": contract.get("classification_hash"),
            "live_raw_flags": live.get("raw_state_flags"),
            "live_matched_family_ids": live.get("matched_family_ids"),
            "contract_matched_family_ids": contract.get("matched_family_ids"),
        }
        result["shadow_case_hash"] = _stable_hash(result)
        case_results.append(result)

    status = "PASS" if not unexpected_drifts else "FAIL"
    artifact_path = ARTIFACT_DIR / f"family_classification_shadow_snapshot_{stamp}.json"
    report_path = AUDIT_DIR / f"family_classification_shadow_snapshot_{stamp}.md"
    drift_path = AUDIT_DIR / "family_classification_contract_drift_audit.md"
    _write_drift_audit(
        accepted_aliases=accepted_aliases,
        accepted_product_drifts=accepted_product_drifts,
        unexpected_drifts=unexpected_drifts,
        path=drift_path,
    )
    output = {
        "schema": "family_classification_shadow_snapshot.v1",
        "status": status,
        "generated_at": stamp,
        "artifact": str(artifact_path),
        "report": str(report_path),
        "drift_audit": str(drift_path),
        "case_count": len(CASES),
        "true_parity_count": true_parity_count,
        "accepted_naming_aliases": accepted_aliases,
        "accepted_product_migration_drifts": accepted_product_drifts,
        "unexpected_drifts": unexpected_drifts,
        "mismatches": unexpected_drifts,
        "cases": case_results,
    }
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(output, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "drift_audit": str(drift_path),
                "accepted_naming_alias_count": len(accepted_aliases),
                "accepted_product_migration_drift_count": len(accepted_product_drifts),
                "unexpected_drift_count": len(unexpected_drifts),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
