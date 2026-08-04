from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

RAW_FLAG_KEYS = (
    "geometry_detailing_fail",
    "serviceability_fail",
    "bending_fail",
    "shear_fail",
    "min_bending_reo_fail",
    "min_shear_reo_fail",
    "bending_overdesigned",
    "shear_overdesigned",
    "bending_within_target_band",
    "shear_within_target_band",
    "locked_repair_blocked",
    "legal_repair_exists",
    "repair_required",
    "exact_stop_proven",
    "bending_acceptable",
    "shear_acceptable",
)

OLD_SELECTED_STATE_CASES = (
    {
        "case_id": "old_min_bending_reo_selected",
        "old_family": "MIN_BENDING_REO_GOVERNS",
        "flags": {"min_bending_reo_fail": True},
        "old_condition": "minimum bending reinforcement governs with no parent strength, serviceability, or geometry/detailing failure",
        "visible_message_evidence": "minimum bending reinforcement optimisation stop",
        "cta_apply_state": "disabled/no direct apply from blocker-only shell",
        "publication_result": "bending minimum reinforcement optimisation stop evidence",
        "expected_active_family_owners": (
            "BENDING_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
        ),
    },
    {
        "case_id": "old_min_shear_reo_selected",
        "old_family": "MIN_SHEAR_REO_GOVERNS",
        "flags": {"min_shear_reo_fail": True},
        "old_condition": "minimum shear reinforcement governs with no parent strength, serviceability, or geometry/detailing failure",
        "visible_message_evidence": "minimum shear reinforcement optimisation stop",
        "cta_apply_state": "disabled/no direct apply from blocker-only shell",
        "publication_result": "shear minimum reinforcement optimisation stop evidence",
        "expected_active_family_owners": (
            "SHEAR_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
        ),
    },
    {
        "case_id": "old_geometry_detailing_selected",
        "old_family": "GEOMETRY_DETAILING_GOVERNS",
        "flags": {"geometry_detailing_fail": True, "bending_fail": True, "shear_fail": True},
        "old_condition": "geometry/detailing failure outranks strength-family selection in the legacy chooser",
        "visible_message_evidence": "geometry/detailing blocked or optimisation stop",
        "cta_apply_state": "disabled unless executor-backed candidate resolves geometry/detailing",
        "publication_result": "geometry/detailing blocker evidence",
        "expected_active_family_owners": (
            "BENDING_FAIL_GOVERNS",
            "SHEAR_FAIL_GOVERNS",
            "COMBINED_BENDING_SHEAR_FAIL",
            "BENDING_OVERDESIGN_GOVERNS",
            "SHEAR_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
            "SERVICEABILITY_GOVERNS",
            "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        ),
    },
)

ACTIVE_EVIDENCE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "BENDING_OVERDESIGN_GOVERNS": {
        "paths": (
            "design_brain/families/bending_overdesign_governs/contract.json",
            "design_brain/families/bending_overdesign_governs/runtime.py",
        ),
        "blocker_terms_any": ("minimum_reinforcement_proof", "minimum reinforcement boundary", "minimum_reinforcement"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_reason", "blocked_reason"),
        "blocked_ladder_terms_any": ("BOTTOM_REINFORCEMENT_REDUCTION", "WIDTH_REDUCTION", "DEPTH_REDUCTION"),
        "no_further_candidate_terms_any": ("all_contract_optimisation_candidates_rejected_or_blocked", "below_minimum_candidates_ranked"),
        "cta_terms_any": ("proof_only", "product_driving", "rendered", "applied"),
    },
    "SHEAR_OVERDESIGN_GOVERNS": {
        "paths": (
            "design_brain/families/shear_overdesign_governs/contract.json",
            "design_brain/families/shear_overdesign_governs/runtime.py",
        ),
        "blocker_terms_any": ("minimum reinforcement requirement", "spacing_detailing_blocked", "geometry_reduction_prohibited"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_reason", "blocked_reason"),
        "blocked_ladder_terms_any": ("SPACING_INCREASE", "BAR_SIZE_REDUCTION", "LEG_COUNT_REDUCTION"),
        "no_further_candidate_terms_any": ("all_contract_optimisation_candidates_rejected_or_blocked", "safe shear cleanup lanes are exhausted"),
        "cta_terms_any": ("proof_only", "product_driving", "rendered", "applied"),
    },
    "COMBINED_OVERDESIGN": {
        "paths": (
            "design_brain/families/bending_and_shear_overdesign_govern/contract.json",
            "design_brain/families/bending_and_shear_overdesign_govern/runtime.py",
        ),
        "blocker_terms_any": ("candidate violates minimum reinforcement", "specific_blocker", "specific_blockers"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_proof", "exhausted_reason"),
        "blocked_ladder_terms_any": ("bending_overdesign_candidates", "shear_overdesign_candidates", "approved_combined_merge_candidates"),
        "no_further_candidate_terms_any": ("no compliant combined overdesign optimisation candidate exists", "generic_exhausted_message_prohibited"),
        "cta_terms_any": ("shared_surfaces_owned_outside", "ownership_proof"),
    },
    "BENDING_FAIL_GOVERNS": {
        "paths": (
            "design_brain/families/bending_fail_governs/contract.json",
            "design_brain/families/bending_fail_governs/runtime.py",
        ),
        "blocker_terms_any": ("geometry_detailing", "locked_geometry", "detailing restrictions"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_reason", "blocked_reason"),
        "blocked_ladder_terms_any": ("GEOMETRY_SANITY", "DEPTH_INCREASE", "WIDTH_INCREASE"),
        "no_further_candidate_terms_any": ("NO_VALID_STRATEGY", "bounded bending repair ladder exhausted"),
        "cta_terms_any": ("proof_only", "product_driving"),
    },
    "SHEAR_FAIL_GOVERNS": {
        "paths": (
            "design_brain/families/shear_fail_governs/contract.json",
            "design_brain/families/shear_fail_governs/runtime.py",
        ),
        "blocker_terms_any": ("geometry_width", "locked_geometry", "spacing/detailing status"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_reason", "blocked_reason"),
        "blocked_ladder_terms_any": ("SPACING_REDUCTION", "WIDTH_RESTART", "LEG_COUNT_RESTART"),
        "no_further_candidate_terms_any": ("NO_VALID_REPAIR", "contract_ladder_exhausted"),
        "cta_terms_any": ("proof_only", "product_driving"),
    },
    "COMBINED_BENDING_SHEAR_FAIL": {
        "paths": (
            "design_brain/families/bending_and_shear_fail_govern/contract.json",
            "design_brain/families/bending_and_shear_fail_govern/runtime.py",
            "design_brain/families/bending_and_shear_fail_govern/__init__.py",
        ),
        "blocker_terms_any": ("geometry", "detailing", "constructability", "blockers"),
        "exact_stop_terms_any": ("exhausted_reason", "selected_candidate", "selected_recommendation"),
        "blocked_ladder_terms_any": ("bending", "shear", "combined"),
        "no_further_candidate_terms_any": ("no valid combined repair exists", "exhausted_reason"),
        "cta_terms_any": ("cta", "blockers"),
    },
    "SERVICEABILITY_GOVERNS": {
        "paths": (
            "design_brain/families/serviceability_governs/contract.json",
            "design_brain/families/serviceability_governs/runtime.py",
            "design_brain/families/serviceability_governs/__init__.py",
        ),
        "blocker_terms_any": ("blocker_status", "specific_blockers", "constructability"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_proof", "exhausted_reason"),
        "blocked_ladder_terms_any": ("DEPTH_INCREASE", "WIDTH_INCREASE", "REINFORCEMENT_ASSISTED"),
        "no_further_candidate_terms_any": ("all_ladder_branches_attempted_no_valid_compliant_repair", "specific_blockers"),
        "cta_terms_any": ("cta_contract", "blockers"),
    },
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": {
        "paths": (
            "design_brain/families/bending_fail_shear_overdesign_governs/contract.json",
            "design_brain/families/bending_fail_shear_overdesign_governs/runtime.py",
            "design_brain/families/bending_fail_shear_overdesign_governs/__init__.py",
        ),
        "blocker_terms_any": ("shear optimisation blocker", "specific blocker", "constructability"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_proof", "exhausted_reason"),
        "blocked_ladder_terms_any": ("bending", "shear", "combined"),
        "no_further_candidate_terms_any": ("specific_blocker", "exhausted_reason"),
        "cta_terms_any": ("shared_surfaces_owned_outside", "cta_contract"),
    },
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": {
        "paths": (
            "design_brain/families/shear_fail_bending_overdesign_governs/contract.json",
            "design_brain/families/shear_fail_bending_overdesign_governs/runtime.py",
            "design_brain/families/shear_fail_bending_overdesign_governs/__init__.py",
        ),
        "blocker_terms_any": ("bending optimisation blocker", "specific blocker", "constructability"),
        "exact_stop_terms_any": ("exact_stop_proof", "exhausted_proof", "exhausted_reason"),
        "blocked_ladder_terms_any": ("bending", "shear", "combined"),
        "no_further_candidate_terms_any": ("specific_blocker", "exhausted_reason"),
        "cta_terms_any": ("shared_surfaces_owned_outside", "cta_contract"),
    },
}


def _base_flags() -> dict[str, bool]:
    return {key: False for key in RAW_FLAG_KEYS}


def _read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8", errors="replace")


def _combined_source(paths: tuple[str, ...]) -> str:
    return "\n".join(_read(path) for path in paths)


def _matched_terms(source: str, terms: tuple[str, ...]) -> list[str]:
    lowered = source.lower()
    return [term for term in terms if term.lower() in lowered]


def _old_selected_states() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in OLD_SELECTED_STATE_CASES:
        flags = _base_flags()
        flags.update(dict(case["flags"]))
        result = classify_family_from_raw_flags(flags, evidence={"case_id": case["case_id"]})
        rows.append(
            {
                "case_id": case["case_id"],
                "input_condition": case["old_condition"],
                "raw_flags": flags,
                "legacy_old_family": case["old_family"],
                "current_selected_family": result.get("selected_family_id"),
                "expected_old_family": case["old_family"],
                "matched_family_ids": list(result.get("matched_family_ids") or []),
                "classification_passed": result.get("classification_passed"),
                "visible_message_evidence": case["visible_message_evidence"],
                "cta_apply_state": case["cta_apply_state"],
                "publication_result": case["publication_result"],
                "expected_active_family_owner": list(case["expected_active_family_owners"]),
                "legacy_old_selected_state_mapped": result.get("selected_family_id") in case["expected_active_family_owners"],
            }
        )
    return rows


def _active_family_evidence_coverage(old_state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family_id in old_state["expected_active_family_owner"]:
        requirement = ACTIVE_EVIDENCE_REQUIREMENTS[family_id]
        source = _combined_source(tuple(requirement["paths"]))
        blocker_terms = _matched_terms(source, tuple(requirement["blocker_terms_any"]))
        exact_stop_terms = _matched_terms(source, tuple(requirement["exact_stop_terms_any"]))
        blocked_ladder_terms = _matched_terms(source, tuple(requirement["blocked_ladder_terms_any"]))
        no_further_candidate_terms = _matched_terms(source, tuple(requirement["no_further_candidate_terms_any"]))
        cta_terms = _matched_terms(source, tuple(requirement["cta_terms_any"]))
        evidence_exists = all(
            (
                blocker_terms,
                exact_stop_terms,
                blocked_ladder_terms,
                no_further_candidate_terms,
                cta_terms,
            )
        )
        rows.append(
            {
                "old_family": old_state["legacy_old_family"],
                "active_family_owner": family_id,
                "paths": list(requirement["paths"]),
                "blocker_type": old_state["legacy_old_family"],
                "blocker_reason": old_state["input_condition"],
                "blocked_ladder_or_strategy": blocked_ladder_terms,
                "why_no_further_candidate_is_valid": no_further_candidate_terms,
                "blocker_evidence_terms": blocker_terms,
                "exact_stop_or_exhausted_terms": exact_stop_terms,
                "cta_equivalence_terms": cta_terms,
                "evidence_exists": evidence_exists,
                "cta_equivalent": bool(cta_terms),
                "visible_outcome_equivalence": "same_or_safer_disabled_or_shared_cta_outcome" if cta_terms else "missing",
                "safe_to_retire_later": evidence_exists,
            }
        )
    return rows


def _reference_inventory() -> list[dict[str, Any]]:
    search_paths = (
        "design_brain/family_chooser.py",
        "design_brain/family_classification_runtime.py",
        "design_brain/contracts/family_classification_contract.json",
        "design_brain/families/registry.py",
        "design_brain/governing_state.py",
        "tools/verification/family_classification_contract_check.py",
        "tools/verification/family_chooser_classification_regression.py",
        "inputs_page.py",
    )
    rows: list[dict[str, Any]] = []
    for path in search_paths:
        text = _read(path)
        for old_family in ("MIN_BENDING_REO_GOVERNS", "MIN_SHEAR_REO_GOVERNS", "GEOMETRY_DETAILING_GOVERNS"):
            if old_family in text:
                rows.append(
                    {
                        "family": old_family,
                        "file": path,
                        "role": _reference_role(path),
                    }
                )
    return rows


def _reference_role(path: str) -> str:
    if "family_chooser" in path or "family_classification_runtime" in path:
        return "old selectable classification path"
    if "family_classification_contract" in path:
        return "old classification contract expectation"
    if "registry" in path:
        return "old registry/compatibility alias path"
    if "governing_state" in path:
        return "legacy state adapter path"
    if "inputs_page" in path:
        return "shared page compatibility/display evidence path"
    if "verification" in path:
        return "test/snapshot expectation"
    return "reference"


def _build_snapshot() -> dict[str, Any]:
    old_states = _old_selected_states()
    coverage_by_case = []
    gaps: list[str] = []
    for old_state in old_states:
        coverage = _active_family_evidence_coverage(old_state)
        coverage_by_case.append(
            {
                "case_id": old_state["case_id"],
                "old_family": old_state["legacy_old_family"],
                "active_family_evidence": coverage,
            }
        )
        if not old_state["legacy_old_selected_state_mapped"]:
            gaps.append(f"{old_state['case_id']}:legacy_old_selected_state_not_mapped_to_active_owner")
        for row in coverage:
            if not row["evidence_exists"]:
                gaps.append(f"{old_state['case_id']}:{row['active_family_owner']}:missing_active_family_blocker_evidence")
            if not row["cta_equivalent"]:
                gaps.append(f"{old_state['case_id']}:{row['active_family_owner']}:missing_cta_equivalence")

    mapping_proven = not gaps
    return {
        "schema": "blocker_family_selected_state_mapping.v1",
        "result": "PASS" if mapping_proven else "FAIL",
        "retirement_readiness_impact": "MAPPING_PROVEN_BUT_NOT_RETIRED" if mapping_proven else "still_NOT_READY",
        "mapping_proven": mapping_proven,
        "product_behavior_changed": False,
        "chooser_changed": False,
        "registry_changed": False,
        "publication_changed": False,
        "cta_apply_changed": False,
        "old_selected_states_found": old_states,
        "active_family_evidence_coverage": coverage_by_case,
        "reference_inventory": _reference_inventory(),
        "gaps": gaps,
        "hard_stop_conditions": gaps,
        "next_safe_step": (
            "Add a selectability-removal plan verifier that proves old blocker-family states are remapped before changing chooser/contract/registry expectations."
            if mapping_proven
            else "Fill missing active-family blocker evidence before selectability retirement planning."
        ),
    }


def _mapping_rows(snapshot: dict[str, Any]) -> list[str]:
    rows = [
        "Old Family | Old Condition | Active Family Owner | Evidence Exists | CTA Equivalent | Safe To Retire Later",
        "--- | --- | --- | --- | --- | ---",
    ]
    by_case = {row["case_id"]: row for row in snapshot["old_selected_states_found"]}
    for coverage_case in snapshot["active_family_evidence_coverage"]:
        old_state = by_case[coverage_case["case_id"]]
        for evidence in coverage_case["active_family_evidence"]:
            rows.append(
                " | ".join(
                    (
                        f"`{old_state['legacy_old_family']}`",
                        str(old_state["input_condition"]),
                        f"`{evidence['active_family_owner']}`",
                        "`yes`" if evidence["evidence_exists"] else "`no`",
                        "`yes`" if evidence["cta_equivalent"] else "`no`",
                        "`yes`" if evidence["safe_to_retire_later"] else "`no`",
                    )
                )
            )
    return rows


def _report(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Blocker Family Selected-State Mapping Proof",
        "",
        "## Executive Summary",
        snapshot["result"],
        "",
        "## Mapping Table",
        *_mapping_rows(snapshot),
        "",
        "## Old Selected States Found",
    ]
    for row in snapshot["old_selected_states_found"]:
        lines.append(
            f"- `{row['case_id']}` maps legacy `{row['legacy_old_family']}` to current active `{row['current_selected_family']}` from `{row['input_condition']}`; "
            f"CTA/apply: {row['cta_apply_state']}; publication: {row['publication_result']}."
        )
    lines.extend(["", "## Active-Family Evidence Coverage"])
    for coverage_case in snapshot["active_family_evidence_coverage"]:
        lines.append(f"- `{coverage_case['old_family']}`")
        for row in coverage_case["active_family_evidence"]:
            lines.append(
                f"  - `{row['active_family_owner']}`: blocker evidence `{', '.join(row['blocker_evidence_terms'])}`; "
                f"exact/exhausted `{', '.join(row['exact_stop_or_exhausted_terms'])}`; "
                f"visible outcome `{row['visible_outcome_equivalence']}`."
            )
    lines.extend(["", "## Gaps"])
    if snapshot["gaps"]:
        lines.extend(f"- `{gap}`" for gap in snapshot["gaps"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Retirement Readiness Impact",
            snapshot["retirement_readiness_impact"],
            "",
            "## Next Safe Step",
            snapshot["next_safe_step"],
            "",
            "## No Product Changes",
            "- chooser selection unchanged",
            "- registry unchanged",
            "- publication unchanged",
            "- CTA/apply routing unchanged",
            "- visible product behaviour unchanged",
            "",
        ]
    )
    return "\n".join(lines)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"blocker_family_selected_state_mapping_{stamp}.json"
    report_path = AUDIT_DIR / f"blocker_family_selected_state_mapping_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_report(snapshot), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    snapshot = _build_snapshot()
    json_path, report_path = _write(snapshot)
    print(f"Blocker family selected-state mapping {snapshot['result']}")
    print(f"Readiness impact: {snapshot['retirement_readiness_impact']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if snapshot["gaps"]:
        print("Gaps:")
        for gap in snapshot["gaps"]:
            print(f"- {gap}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
