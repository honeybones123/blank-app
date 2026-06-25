"""Lock verifier for the contract-driven Design Brain family classifier."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_classification import load_family_classification_contract  # noqa: E402
from design_brain.family_classification_runtime import classify_family_from_whole_beam_evidence  # noqa: E402
import design_brain.family_chooser as family_chooser  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _case(
    case_id: str,
    *,
    expected_legacy: str,
    expected_contract: str,
    flags: dict[str, Any],
    evidence: dict[str, Any],
    accepted_migration: bool = False,
) -> dict[str, Any]:
    raw_flags = dict(BASE_FLAGS)
    raw_flags.update(flags)
    whole_beam = dict(BASE_EVIDENCE)
    whole_beam.update(evidence)
    return {
        "case_id": case_id,
        "expected_legacy": expected_legacy,
        "expected_contract": expected_contract,
        "accepted_migration": accepted_migration,
        "raw_flags": raw_flags,
        "whole_beam_evidence": whole_beam,
    }


CASES = [
    _case(
        "bending_fail_only",
        expected_legacy="BENDING_FAIL_GOVERNS",
        expected_contract="BENDING_FAIL_GOVERNS",
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
        expected_legacy="SHEAR_FAIL_GOVERNS",
        expected_contract="SHEAR_FAIL_GOVERNS",
        flags={"shear_fail": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 0.94,
            "shear_utilisation": 1.16,
            "shear_state": "FAIL",
            "can_strengthen_shear": True,
        },
    ),
    _case(
        "combined_fail_alias",
        expected_legacy="COMBINED_BENDING_SHEAR_FAIL",
        expected_contract="BENDING_AND_SHEAR_FAIL_GOVERN",
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
        expected_legacy="BENDING_FAIL_GOVERNS",
        expected_contract="BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS",
        flags={"bending_fail": True, "shear_overdesigned": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 1.13,
            "shear_utilisation": 0.72,
            "bending_state": "FAIL",
            "shear_state": "OVERDESIGNED",
            "can_strengthen_bending": True,
            "can_optimise_shear_without_hurting_bending": True,
        },
        accepted_migration=True,
    ),
    _case(
        "shear_fail_bending_optimise",
        expected_legacy="SHEAR_FAIL_GOVERNS",
        expected_contract="SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
        flags={"shear_fail": True, "bending_overdesigned": True, "legal_repair_exists": True},
        evidence={
            "bending_utilisation": 0.74,
            "shear_utilisation": 1.15,
            "bending_state": "OVERDESIGNED",
            "shear_state": "FAIL",
            "can_strengthen_shear": True,
            "can_optimise_bending_without_hurting_shear": True,
        },
        accepted_migration=True,
    ),
    _case(
        "locked_priority",
        expected_legacy="LOCKED_NO_REPAIR",
        expected_contract="LOCKED_NO_REPAIR",
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
        "exact_stop_priority",
        expected_legacy="EXACT_STOP_PROVEN",
        expected_contract="EXACT_STOP_PROVEN",
        flags={"exact_stop_proven": True},
        evidence={
            "bending_utilisation": 0.98,
            "shear_utilisation": 0.97,
            "exact_stop_available": True,
        },
    ),
]


def _with_noise(evidence: dict[str, Any]) -> dict[str, Any]:
    out = dict(evidence)
    out.update(
        {
            "cta_rendering": {"enabled": False, "label": "noise"},
            "publication": {"selected_family_id": "SHEAR_FAIL_GOVERNS"},
            "apply_routing": {"family": "BENDING_FAIL_GOVERNS"},
            "one_click": {"fallback": True},
            "visible_wording": "not a classifier input",
            "ui": {"session": "noise"},
            "debug": {"inactive_family_evidence": {"TARGET_BAND_REACHED": {"eligible": True}}},
            "inactive_family_evidence": {
                "TARGET_BAND_REACHED": {"eligible": True, "selected_family_id": "TARGET_BAND_REACHED"}
            },
        }
    )
    return out


def _verify_no_forbidden_imports() -> list[str]:
    failures: list[str] = []
    for module_name in (
        "design_brain.family_classification",
        "design_brain.family_classification_runtime",
        "design_brain.family_chooser",
    ):
        importlib.import_module(module_name)
    if "inputs_page" in sys.modules:
        failures.append("classifier_import_loaded_inputs_page")
    if "streamlit" in sys.modules:
        failures.append("classifier_import_loaded_streamlit")
    for path in (
        ROOT / "design_brain" / "family_classification.py",
        ROOT / "design_brain" / "family_classification_runtime.py",
    ):
        source = path.read_text(encoding="utf-8", errors="replace")
        if "inputs_page" in source:
            failures.append(f"{path.name}:mentions_inputs_page")
        if "streamlit" in source or "import st" in source:
            failures.append(f"{path.name}:mentions_streamlit")
    return failures


def _write_report(output: dict[str, Any], path: Path) -> None:
    lines = [
        "# Family Classification Lock Verifier",
        "",
        f"Status: {output['status']}",
        "",
        "## Summary",
        "",
        f"- case count: {output['case_count']}",
        f"- accepted migration cases: {len(output['accepted_migration_cases'])}",
        f"- artifact: `{output['artifact']}`",
        "",
        "## Checks",
        "",
        "- contract loads successfully",
        "- default flag-false path preserves legacy live classifier outputs",
        "- flag-true path uses contract runtime output",
        "- classification hash is stable across repeat runs",
        "- priority conflicts resolve to the contract-priority family",
        "- CTA/publication/render/apply/one-click/wording/UI/debug noise does not alter selected family or hash",
        "- inactive-family evidence supplied as noise cannot become selected-family output",
        "- Design Brain classifier imports do not load `inputs_page.py` or Streamlit",
        "",
        "## Failures",
        "",
    ]
    lines.extend([f"- {failure}" for failure in output["failures"]] or ["- none"])
    lines.extend(["", "## Cases", ""])
    for case in output["cases"]:
        lines.append(
            f"- `{case['case_id']}`: legacy `{case['legacy_selected_family']}`, "
            f"contract `{case['contract_selected_family']}`, hash `{case['classification_hash']}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_implementation_report(output: dict[str, Any], path: Path) -> None:
    lines = [
        "# Contract Family Classifier Live-Gate Implementation",
        "",
        "Status: implemented behind `USE_CONTRACT_FAMILY_CLASSIFIER = False`",
        "",
        "## What Changed",
        "",
        "- `design_brain.family_chooser` now has a default-false feature flag.",
        "- When false, the existing live classifier path remains active.",
        "- When true, the existing chooser API delegates to `design_brain.family_classification_runtime`.",
        "- The contract path returns legacy-compatible selection fields plus contract fields.",
        "",
        "## What Did Not Move",
        "",
        "- family ladder logic",
        "- CTA rendering/source precedence",
        "- publication/apply/one-click routing",
        "- visible wording/output rendering",
        "- UI/session/debug ownership",
        "",
        "## Verification",
        "",
        f"- lock verifier status: {output['status']}",
        f"- lock artifact: `{output['artifact']}`",
        f"- lock report: `{output['report']}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    failures: list[str] = []
    case_results: list[dict[str, Any]] = []
    accepted_migration_cases: list[str] = []

    contract = load_family_classification_contract()
    if not contract.get("classification_priority_order"):
        failures.append("contract_priority_order_missing")

    failures.extend(_verify_no_forbidden_imports())
    original_flag = family_chooser.USE_CONTRACT_FAMILY_CLASSIFIER
    try:
        for case in CASES:
            family_chooser.USE_CONTRACT_FAMILY_CLASSIFIER = False
            legacy = family_chooser.classify_family_from_raw_flags(
                case["raw_flags"],
                evidence={"whole_beam_evidence": case["whole_beam_evidence"], "case_id": case["case_id"]},
            )
            legacy_family = str(legacy.get("selected_family_id") or "")
            if legacy_family != case["expected_legacy"]:
                failures.append(f"{case['case_id']}:legacy_selected_family_mismatch:{legacy_family}")

            family_chooser.USE_CONTRACT_FAMILY_CLASSIFIER = True
            gated = family_chooser.classify_family_from_raw_flags(
                case["raw_flags"],
                evidence={"whole_beam_evidence": case["whole_beam_evidence"], "case_id": case["case_id"]},
            )
            direct_one = classify_family_from_whole_beam_evidence(case["whole_beam_evidence"])
            direct_two = classify_family_from_whole_beam_evidence(case["whole_beam_evidence"])
            noisy = classify_family_from_whole_beam_evidence(_with_noise(case["whole_beam_evidence"]))
            contract_family = str(gated.get("selected_family_id") or "")
            if contract_family != case["expected_contract"]:
                failures.append(f"{case['case_id']}:contract_selected_family_mismatch:{contract_family}")
            if contract_family != str(direct_one.get("selected_family_id") or ""):
                failures.append(f"{case['case_id']}:gated_result_differs_from_direct_runtime")
            if direct_one.get("classification_hash") != direct_two.get("classification_hash"):
                failures.append(f"{case['case_id']}:classification_hash_unstable")
            if direct_one.get("classification_hash") != noisy.get("classification_hash"):
                failures.append(f"{case['case_id']}:noise_changed_classification_hash")
            if direct_one.get("selected_family_id") != noisy.get("selected_family_id"):
                failures.append(f"{case['case_id']}:noise_changed_selected_family")
            selected_inactive = (direct_one.get("inactive_family_evidence") or {}).get(direct_one.get("selected_family_id")) or {}
            if not selected_inactive.get("eligible"):
                failures.append(f"{case['case_id']}:selected_family_not_eligible_in_inactive_evidence")
            if case["accepted_migration"]:
                accepted_migration_cases.append(case["case_id"])
            case_results.append(
                {
                    "case_id": case["case_id"],
                    "legacy_selected_family": legacy_family,
                    "contract_selected_family": contract_family,
                    "classification_priority": gated.get("classification_priority"),
                    "classification_hash": gated.get("classification_hash"),
                    "repeat_hash": direct_two.get("classification_hash"),
                    "noise_hash": noisy.get("classification_hash"),
                    "accepted_migration": bool(case["accepted_migration"]),
                    "case_hash": _stable_hash(
                        {
                            "case_id": case["case_id"],
                            "legacy_selected_family": legacy_family,
                            "contract_selected_family": contract_family,
                            "classification_hash": gated.get("classification_hash"),
                            "accepted_migration": bool(case["accepted_migration"]),
                        }
                    ),
                }
            )
    finally:
        family_chooser.USE_CONTRACT_FAMILY_CLASSIFIER = original_flag

    status = "PASS" if not failures else "FAIL"
    artifact_path = ARTIFACT_DIR / f"family_classification_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"family_classification_lock_verifier_{stamp}.md"
    implementation_path = AUDIT_DIR / f"family_classification_contract_live_gate_implementation_{stamp}.md"
    output = {
        "schema": "family_classification_lock_verifier.v1",
        "status": status,
        "generated_at": stamp,
        "artifact": str(artifact_path),
        "report": str(report_path),
        "implementation_report": str(implementation_path),
        "case_count": len(CASES),
        "accepted_migration_cases": accepted_migration_cases,
        "cases": case_results,
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(output, report_path)
    _write_implementation_report(output, implementation_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "implementation_report": str(implementation_path),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
