from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.blocker_family_retirement_readiness_snapshot import (  # noqa: E402
    _compatibility_snapshot,
    _coverage_snapshot,
    _old_selectability_snapshot,
)
from tools.verification.blocker_family_selected_state_mapping_snapshot import (  # noqa: E402
    _build_snapshot as _build_selected_state_mapping_snapshot,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

OLD_BLOCKER_IDS = (
    "MIN_BENDING_REO_GOVERNS",
    "MIN_SHEAR_REO_GOVERNS",
    "GEOMETRY_DETAILING_GOVERNS",
)

REPLACEMENT_OWNERS = {
    "MIN_BENDING_REO_GOVERNS": (
        "BENDING_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
    ),
    "MIN_SHEAR_REO_GOVERNS": (
        "SHEAR_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
    ),
    "GEOMETRY_DETAILING_GOVERNS": (
        "active_family_whose_ladder_or_optimisation_was_blocked",
    ),
}

UNSAFE_SELECTABILITY_PATHS = (
    {
        "path": "design_brain/family_chooser.py",
        "reason": "final chooser selectability and legacy final-family predicates",
        "required_change": "remove blocker-only IDs from final selectable family IDs and predicates",
    },
    {
        "path": "design_brain/family_classification_runtime.py",
        "reason": "contract runtime can still return blocker-only IDs as selected family",
        "required_change": "remap blocker-only predicate outcomes to active owner families with blocker evidence",
    },
    {
        "path": "design_brain/contracts/family_classification_contract.json",
        "reason": "classification contract still lists blocker-only IDs as allowed/priority/rule outputs",
        "required_change": "remove blocker-only IDs from new final selectable contract expectations",
    },
    {
        "path": "tools/verification/family_classification_contract_check.py",
        "reason": "contract verifier still expects blocker-only IDs as final family IDs",
        "required_change": "update expected final family ID set and keep aliases separately",
    },
    {
        "path": "tools/verification/family_chooser_classification_regression.py",
        "reason": "chooser regression still expects GEOMETRY_DETAILING_GOVERNS as selected family",
        "required_change": "update selected-family expectation to active owner plus blocker evidence proof",
    },
)

SAFE_COMPATIBILITY_PATHS = (
    {
        "path": "design_brain/families/registry.py",
        "reason": "registry entries and aliases may remain temporarily for migration compatibility",
    },
    {
        "path": "design_brain/families/min_bending_reo.py",
        "reason": "legacy diagnostic shell may remain until snapshots no longer require the name",
    },
    {
        "path": "design_brain/families/min_shear_reo.py",
        "reason": "legacy diagnostic shell may remain until snapshots no longer require the name",
    },
    {
        "path": "design_brain/families/geometry_detailing.py",
        "reason": "legacy diagnostic shell may remain until snapshots no longer require the name",
    },
    {
        "path": "design_brain/governing_state.py",
        "reason": "legacy state adapter may retain old names behind compatibility aliases during migration",
    },
    {
        "path": "inputs_page.py",
        "reason": "current mentions are rejected-family evidence/display compatibility, not final CTA/apply ownership",
    },
    {
        "path": "tools/governing_family_adapter_audit.py",
        "reason": "historical adapter audit may reference old names while reporting migration state",
    },
    {
        "path": "tools/verification/bending_fail_governs_strategy_ladder_contract_snapshot.py",
        "reason": "legacy snapshot reference may remain until that snapshot is retargeted",
    },
    {
        "path": "tools/verification/blocker_family_retirement_readiness_snapshot.py",
        "reason": "readiness verifier intentionally tracks old names until retirement completes",
    },
    {
        "path": "tools/verification/blocker_family_selected_state_mapping_snapshot.py",
        "reason": "mapping verifier intentionally proves old-to-active-family replacement",
    },
)

CTA_PUBLICATION_OWNERSHIP_PATHS = (
    "design_brain/publication.py",
    "design_brain/output_formatting.py",
    "tools/verification/cta_button_contract_check.py",
    "tools/verification/design_guide_output_formatting_usage_snapshot.py",
)


def _read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8", errors="replace")


def _contains_old_id(path: str) -> bool:
    text = _read(path)
    return any(old_id in text for old_id in OLD_BLOCKER_IDS)


def _unsafe_references() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in UNSAFE_SELECTABILITY_PATHS:
        old_ids = [old_id for old_id in OLD_BLOCKER_IDS if old_id in _read(item["path"])]
        if old_ids:
            rows.append(
                {
                    **item,
                    "old_ids": old_ids,
                    "category": "must_change_before_selectability_removal",
                }
            )
    return rows


def _safe_compatibility_references() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in SAFE_COMPATIBILITY_PATHS:
        old_ids = [old_id for old_id in OLD_BLOCKER_IDS if old_id in _read(item["path"])]
        if old_ids:
            rows.append(
                {
                    **item,
                    "old_ids": old_ids,
                    "category": "may_remain_temporarily_as_compatibility_alias",
                }
            )
    return rows


def _publication_cta_dependency_scan() -> dict[str, Any]:
    scanned = []
    old_id_hits = []
    for path in CTA_PUBLICATION_OWNERSHIP_PATHS:
        hit = _contains_old_id(path)
        scanned.append({"path": path, "mentions_old_blocker_id": hit})
        if hit:
            old_id_hits.append(path)
    inputs_page = _read("inputs_page.py")
    inputs_hits_are_rejected_evidence = all(
        phrase in inputs_page
        for phrase in (
            '"GEOMETRY_DETAILING_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched"',
            '"MIN_BENDING_REO_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched"',
            '"MIN_SHEAR_REO_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched"',
        )
    )
    return {
        "scanned_paths": scanned,
        "old_id_hits_in_cta_publication_ownership_paths": old_id_hits,
        "inputs_page_old_id_mentions_classified_as_rejected_family_evidence": inputs_hits_are_rejected_evidence,
        "publication_safe": not old_id_hits,
        "cta_apply_safe": not old_id_hits and inputs_hits_are_rejected_evidence,
    }


def _readiness_snapshot() -> dict[str, Any]:
    selectability = _old_selectability_snapshot()
    coverage = _coverage_snapshot()
    compatibility = _compatibility_snapshot()
    hard_stops: list[str] = []
    for family_id, row in selectability.items():
        if any(row.values()):
            hard_stops.append(f"{family_id}:still_referenced_by_selectability_contract_registry_or_tests")
    for blocker, row in coverage.items():
        if not row["all_required_coverage_present"]:
            hard_stops.append(f"{blocker}:missing_active_family_coverage")
    missing_evidence = [item for item in hard_stops if item.endswith(":missing_active_family_coverage")]
    selectable_only_expected = bool(hard_stops) and not missing_evidence
    return {
        "result": "PASS",
        "readiness_status": "READY" if not hard_stops else "NOT_READY",
        "hard_stop_conditions": hard_stops,
        "selectability_or_compatibility_only_not_ready": selectable_only_expected,
        "missing_active_family_evidence": missing_evidence,
        "old_selectability": selectability,
        "active_family_coverage": coverage,
        "compatibility": compatibility,
        "compatibility_aliases_retained": any(compatibility.values()),
    }


def _old_id_plan_rows(mapping: dict[str, Any], unsafe_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage_by_old_id: dict[str, list[dict[str, Any]]] = {}
    for case in mapping["active_family_evidence_coverage"]:
        old_family = str(case["old_family"])
        coverage_by_old_id.setdefault(old_family, []).extend(list(case["active_family_evidence"]))

    rows: list[dict[str, Any]] = []
    for old_id in OLD_BLOCKER_IDS:
        relevant_unsafe = [row for row in unsafe_refs if old_id in row["old_ids"]]
        coverage = coverage_by_old_id.get(old_id, [])
        evidence_ok = bool(coverage) and all(row.get("evidence_exists") for row in coverage)
        cta_ok = bool(coverage) and all(row.get("cta_equivalent") for row in coverage)
        rows.append(
            {
                "old_id": old_id,
                "current_selectable_path": [row["path"] for row in relevant_unsafe],
                "replacement_owner": list(REPLACEMENT_OWNERS[old_id]),
                "evidence_coverage": "covered" if evidence_ok else "missing",
                "cta_safe": cta_ok,
                "publication_safe": evidence_ok,
                "alias_retained": True,
                "status": "READY_FOR_SELECTABILITY_REMOVAL_PLAN" if evidence_ok and cta_ok else "BLOCKED",
                "required_chooser_expectation_update": "old ID must no longer be returned as final selected family",
                "required_contract_expectation_update": "old ID must move from final selectable family IDs to compatibility alias/evidence mapping",
                "required_tests_snapshots_to_update": [
                    "family_classification_contract_check",
                    "family_chooser_classification_regression",
                    "blocker_family_retirement_readiness_snapshot",
                ],
                "compatibility_aliases_to_keep": [
                    "registry aliases",
                    "legacy diagnostic shell",
                    "historical reports/snapshots until retargeted",
                ],
                "hard_stop_risks": [] if evidence_ok and cta_ok else ["active-family evidence or CTA equivalence missing"],
            }
        )
    return rows


def _build_snapshot() -> dict[str, Any]:
    mapping = _build_selected_state_mapping_snapshot()
    readiness = _readiness_snapshot()
    unsafe_refs = _unsafe_references()
    safe_refs = _safe_compatibility_references()
    cta_publication = _publication_cta_dependency_scan()
    plan_rows = _old_id_plan_rows(mapping, unsafe_refs)

    hard_stops: list[str] = []
    if mapping.get("result") != "PASS" or not mapping.get("mapping_proven"):
        hard_stops.append("mapping_proof_missing_or_failing")
    if readiness["missing_active_family_evidence"]:
        hard_stops.extend(readiness["missing_active_family_evidence"])
    if not cta_publication["publication_safe"]:
        hard_stops.append("publication_depends_on_old_blocker_family_id")
    if not cta_publication["cta_apply_safe"]:
        hard_stops.append("cta_apply_depends_on_old_blocker_family_id")
    if any(row["status"] == "BLOCKED" for row in plan_rows):
        hard_stops.append("one_or_more_old_ids_lack_replacement_plan")

    selectability_removal_ready = not hard_stops and (
        readiness["readiness_status"] == "READY"
        or readiness["selectability_or_compatibility_only_not_ready"]
    )
    status = "PASS" if selectability_removal_ready else ("PARTIAL" if not hard_stops else "FAIL")
    return {
        "schema": "blocker_family_selectability_removal_plan.v1",
        "result": status,
        "selectability_removal_readiness": (
            "READY_FOR_SELECTABILITY_REMOVAL" if selectability_removal_ready else "NOT_READY"
        ),
        "product_behavior_changed": False,
        "chooser_changed": False,
        "registry_changed": False,
        "publication_changed": False,
        "cta_apply_changed": False,
        "mapping_proof": {
            "result": mapping.get("result"),
            "retirement_readiness_impact": mapping.get("retirement_readiness_impact"),
            "gaps": list(mapping.get("gaps") or []),
        },
        "retirement_readiness": readiness,
        "old_id_plan": plan_rows,
        "unsafe_references": unsafe_refs,
        "safe_compatibility_references": safe_refs,
        "publication_cta_apply_scan": cta_publication,
        "hard_stop_risks": hard_stops,
        "required_implementation_steps": [
            "Update chooser final selectability expectations.",
            "Update classification/contract expected family IDs.",
            "Route old blocker selected states to active family owners.",
            "Preserve old IDs as compatibility aliases only.",
            "Re-run readiness snapshot.",
        ],
        "next_step_recommendation": (
            "The next pass may remove final selectability, preserving old IDs as compatibility aliases."
            if selectability_removal_ready
            else "Do not remove selectability until hard stop risks are resolved."
        ),
    }


def _table_rows(plan_rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "Old ID | Current selectable path | Replacement owner | Evidence coverage | CTA safe | Publication safe | Alias retained | Status",
        "--- | --- | --- | --- | --- | --- | --- | ---",
    ]
    for row in plan_rows:
        lines.append(
            " | ".join(
                (
                    f"`{row['old_id']}`",
                    ", ".join(f"`{path}`" for path in row["current_selectable_path"]) or "`none`",
                    ", ".join(f"`{owner}`" for owner in row["replacement_owner"]),
                    f"`{row['evidence_coverage']}`",
                    "`yes`" if row["cta_safe"] else "`no`",
                    "`yes`" if row["publication_safe"] else "`no`",
                    "`yes`" if row["alias_retained"] else "`no`",
                    f"`{row['status']}`",
                )
            )
        )
    return lines


def _report(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Blocker Family Selectability Removal Plan",
        "",
        "## Executive Summary",
        snapshot["result"],
        "",
        "## Readiness State",
        f"Current retirement readiness: `{snapshot['retirement_readiness']['readiness_status']}`",
        f"Mapping proof: `{snapshot['mapping_proof']['result']}`",
        f"Selectability removal readiness: `{snapshot['selectability_removal_readiness']}`",
        "",
        "## Old ID Plan Table",
        *_table_rows(list(snapshot["old_id_plan"])),
        "",
        "## Unsafe References",
    ]
    if snapshot["unsafe_references"]:
        for row in snapshot["unsafe_references"]:
            lines.append(
                f"- `{row['path']}`: {row['reason']}; old IDs `{', '.join(row['old_ids'])}`; "
                f"change: {row['required_change']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Safe Compatibility References"])
    if snapshot["safe_compatibility_references"]:
        for row in snapshot["safe_compatibility_references"]:
            lines.append(f"- `{row['path']}`: {row['reason']}; old IDs `{', '.join(row['old_ids'])}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Required Implementation Steps"])
    for index, step in enumerate(snapshot["required_implementation_steps"], start=1):
        lines.append(f"{index}. {step}")
    lines.extend(["", "## Hard Stop Risks"])
    if snapshot["hard_stop_risks"]:
        lines.extend(f"- `{risk}`" for risk in snapshot["hard_stop_risks"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Step Recommendation",
            snapshot["next_step_recommendation"],
            "",
            "## No Product Changes",
            "- chooser behaviour unchanged",
            "- registry unchanged",
            "- publication unchanged",
            "- CTA/apply routing unchanged",
            "- visible behaviour unchanged",
            "",
        ]
    )
    return "\n".join(lines)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"blocker_family_selectability_removal_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"blocker_family_selectability_removal_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_report(snapshot), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    snapshot = _build_snapshot()
    json_path, report_path = _write(snapshot)
    print(f"Blocker family selectability removal plan {snapshot['result']}")
    print(f"Readiness: {snapshot['selectability_removal_readiness']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if snapshot["hard_stop_risks"]:
        print("Hard stop risks:")
        for risk in snapshot["hard_stop_risks"]:
            print(f"- {risk}")
    return 0 if snapshot["result"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
