from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

BLOCKER_FAMILIES = (
    "MIN_BENDING_REO_GOVERNS",
    "MIN_SHEAR_REO_GOVERNS",
    "GEOMETRY_DETAILING_GOVERNS",
)

ACTIVE_FAMILY_COVERAGE: dict[str, dict[str, dict[str, Any]]] = {
    "MIN_BENDING_REO_GOVERNS": {
        "BENDING_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/bending_overdesign_governs/contract.json",
                "design_brain/families/bending_overdesign_governs/runtime.py",
            ),
            "terms_any": ("minimum reinforcement", "minimum_reinforcement", "minimum_reinforcement_proof"),
        },
        "COMBINED_OVERDESIGN": {
            "paths": (
                "design_brain/families/bending_and_shear_overdesign_govern/contract.json",
                "design_brain/families/bending_and_shear_overdesign_govern/runtime.py",
            ),
            "terms_any": ("minimum reinforcement", "minimum_reinforcement_protection", "candidate violates minimum reinforcement"),
        },
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/shear_fail_bending_overdesign_governs/contract.json",
                "design_brain/families/shear_fail_bending_overdesign_governs/runtime.py",
            ),
            "terms_any": ("minimum reinforcement", "bending optimisation blocker", "specific blocker"),
        },
    },
    "MIN_SHEAR_REO_GOVERNS": {
        "SHEAR_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/shear_overdesign_governs/contract.json",
                "design_brain/families/shear_overdesign_governs/runtime.py",
            ),
            "terms_any": ("minimum reinforcement", "spacing_detailing_blocked", "geometry_reduction_prohibited"),
        },
        "COMBINED_OVERDESIGN": {
            "paths": (
                "design_brain/families/bending_and_shear_overdesign_govern/contract.json",
                "design_brain/families/bending_and_shear_overdesign_govern/runtime.py",
            ),
            "terms_any": ("minimum reinforcement", "minimum_reinforcement_protection", "candidate violates minimum reinforcement"),
        },
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/bending_fail_shear_overdesign_governs/contract.json",
                "design_brain/families/bending_fail_shear_overdesign_governs/runtime.py",
            ),
            "terms_any": ("minimum reinforcement", "shear optimisation blocker", "specific blocker"),
        },
    },
    "GEOMETRY_DETAILING_GOVERNS": {
        "BENDING_FAIL_GOVERNS": {
            "paths": (
                "design_brain/families/bending_fail_governs/contract.json",
                "design_brain/families/bending_fail_governs/runtime.py",
            ),
            "terms_any": ("geometry", "detailing", "spacing", "constructability"),
        },
        "SHEAR_FAIL_GOVERNS": {
            "paths": (
                "design_brain/families/shear_fail_governs/contract.json",
                "design_brain/families/shear_fail_governs/runtime.py",
            ),
            "terms_any": ("geometry", "detailing", "spacing", "constructability"),
        },
        "COMBINED_BENDING_SHEAR_FAIL": {
            "paths": (
                "design_brain/families/bending_and_shear_fail_govern/contract.json",
                "design_brain/families/bending_and_shear_fail_govern/runtime.py",
            ),
            "terms_any": ("geometry", "detailing", "constructability"),
        },
        "BENDING_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/bending_overdesign_governs/contract.json",
                "design_brain/families/bending_overdesign_governs/runtime.py",
            ),
            "terms_any": ("geometry", "constructability", "geometry_compliance_proof"),
        },
        "SHEAR_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/shear_overdesign_governs/contract.json",
                "design_brain/families/shear_overdesign_governs/runtime.py",
            ),
            "terms_any": ("geometry", "detailing", "constructability"),
        },
        "COMBINED_OVERDESIGN": {
            "paths": (
                "design_brain/families/bending_and_shear_overdesign_govern/contract.json",
                "design_brain/families/bending_and_shear_overdesign_govern/runtime.py",
            ),
            "terms_any": ("geometry", "constructability", "geometry_interaction"),
        },
        "SERVICEABILITY_GOVERNS": {
            "paths": (
                "design_brain/families/serviceability_governs/contract.json",
                "design_brain/families/serviceability_governs/runtime.py",
            ),
            "terms_any": ("geometry", "constructability", "blocker"),
        },
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/bending_fail_shear_overdesign_governs/contract.json",
                "design_brain/families/bending_fail_shear_overdesign_governs/runtime.py",
            ),
            "terms_any": ("geometry", "constructability", "specific blocker"),
        },
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": {
            "paths": (
                "design_brain/families/shear_fail_bending_overdesign_governs/contract.json",
                "design_brain/families/shear_fail_bending_overdesign_governs/runtime.py",
            ),
            "terms_any": ("geometry", "constructability", "specific blocker"),
        },
    },
}


def _read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8", errors="replace")


def _contains(path: str, family_id: str) -> bool:
    return family_id in _read(path)


def _classification_contract() -> dict[str, Any]:
    return json.loads(_read("design_brain/contracts/family_classification_contract.json"))


def _old_selectability_snapshot() -> dict[str, dict[str, bool]]:
    contract = _classification_contract()
    allowed = {str(value) for value in contract.get("allowed_family_ids") or ()}
    priority = {str(value) for value in contract.get("classification_priority_order") or ()}
    rules = set((contract.get("classification_rules") or {}).keys())
    return {
        family_id: {
            "in_family_chooser": _contains("design_brain/family_chooser.py", family_id),
            "in_classification_runtime": _contains("design_brain/family_classification_runtime.py", family_id),
            "in_classification_contract_allowed_ids": family_id in allowed,
            "in_classification_contract_priority_order": family_id in priority,
            "has_classification_contract_rule": family_id in rules,
            "expected_by_contract_check": _contains("tools/verification/family_classification_contract_check.py", family_id),
        }
        for family_id in BLOCKER_FAMILIES
    }


def _coverage_snapshot() -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for blocker, family_rules in ACTIVE_FAMILY_COVERAGE.items():
        rows: dict[str, Any] = {}
        for family_id, rule in family_rules.items():
            combined_source = "\n".join(_read(path).lower() for path in rule["paths"])
            matched_terms = [term for term in rule["terms_any"] if term.lower() in combined_source]
            rows[family_id] = {
                "paths": list(rule["paths"]),
                "terms_any": list(rule["terms_any"]),
                "matched_terms": matched_terms,
                "coverage_present": bool(matched_terms),
            }
        coverage[blocker] = {
            "required_active_families": rows,
            "missing_active_family_coverage": [
                family_id for family_id, row in rows.items() if not row["coverage_present"]
            ],
            "all_required_coverage_present": all(row["coverage_present"] for row in rows.values()),
        }
    return coverage


def _compatibility_snapshot() -> dict[str, Any]:
    return {
        "family_chooser_regression_expects_geometry_detailing": _contains(
            "tools/verification/family_chooser_classification_regression.py",
            "GEOMETRY_DETAILING_GOVERNS",
        ),
        "governing_state_maps_constraints_to_old_ids": any(
            _contains("design_brain/governing_state.py", family_id)
            for family_id in BLOCKER_FAMILIES
        ),
        "registry_has_geometry_aliases": all(
            _contains("design_brain/families/registry.py", alias)
            for alias in (
                "GEOMETRY_DETAILING_FAIL_GOVERNS",
                "GEOMETRY_GOVERNS_OPTIMISATION_STOP",
                "SPACING_DETAILING_GOVERNS_OPTIMISATION_STOP",
            )
        ),
        "inputs_page_mentions_old_ids": any(_contains("inputs_page.py", family_id) for family_id in BLOCKER_FAMILIES),
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"blocker_family_retirement_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"blocker_family_retirement_readiness_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Blocker-Family Retirement Readiness Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                f"Readiness: `{snapshot['readiness_status']}`",
                "",
                "## Decision",
                "",
                snapshot["decision"],
                "",
                "## Hard Stops",
                "",
                *([f"- `{item}`" for item in snapshot["hard_stop_conditions"]] or ["- none"]),
                "",
                "## Missing Active-Family Coverage",
                "",
                *[
                    f"- `{blocker}`: `{', '.join(row['missing_active_family_coverage']) or 'none'}`"
                    for blocker, row in snapshot["active_family_coverage"].items()
                ],
                "",
                "## Required Before Retirement",
                "",
                *[f"- {item}" for item in snapshot["required_before_retirement"]],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
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

    retirement_ready = not hard_stops
    snapshot = {
        "schema": "blocker_family_retirement_readiness_snapshot.v1",
        "result": "PASS",
        "readiness_status": "READY" if retirement_ready else "NOT_READY",
        "retirement_ready": retirement_ready,
        "decision": (
            "Blocker-family chooser/registry retirement is ready."
            if retirement_ready
            else "Blocker-family chooser/registry retirement is blocked; keep compatibility ids and add replacement ownership proofs first."
        ),
        "blocker_families": list(BLOCKER_FAMILIES),
        "old_selectability": selectability,
        "active_family_coverage": coverage,
        "compatibility": compatibility,
        "compatibility_aliases_retained": any(compatibility.values()),
        "hard_stop_conditions": hard_stops,
        "required_before_retirement": [
            "prove old selected blocker-family states map to active-family blocker evidence",
            "update family classification contract and checker expectations",
            "update chooser regression expectations",
            "remove final chooser selectability only after replacement evidence passes",
            "keep compatibility aliases until publication and product replay snapshots pass",
        ],
        "scope": {
            "product_behavior_changed": False,
            "chooser_changed": False,
            "registry_changed": False,
            "classification_contract_changed": False,
        },
    }
    json_path, report_path = _write(snapshot)
    print(f"Blocker-family retirement readiness {snapshot['readiness_status']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if hard_stops:
        print("Hard stops:")
        for item in hard_stops:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
