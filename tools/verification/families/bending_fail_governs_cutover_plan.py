"""Cutover plan verifier for BENDING_FAIL_GOVERNS.

This is a planning gate only. It proves the replacement boundary is known and
narrow before product routing is changed.
"""

from __future__ import annotations

import ast
import json
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_fail_governs.runtime import (  # noqa: E402
    BendingFailGovernsResult,
    bending_fail_governs_contract_lane_order,
    run_bending_fail_governs_ladder_runtime,
)


EXPECTED_CONTRACT_ORDER = (
    "GEOMETRY_SANITY",
    "DEPTH_INCREASE",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "WIDTH_INCREASE",
    "MULTI_LAYER_REO",
    "EXACT_STOP",
    "NO_VALID_STRATEGY",
)

REQUIRED_RESULT_FIELDS = {
    "selected_strategy_lane",
    "ladder_trace",
    "selected_recommendation",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "repair_reason_proof",
    "blocked_reason",
    "cta_intent_proof",
    "ladder_hash",
}

OLD_SURFACES = {
    "legacy_ladder_owner": "design_brain/families/bending_fail.py:BendingFailFamily.contracted_repair_ladder_specs",
    "runtime_package_export": "design_brain/families/bending_fail_governs/__init__.py:run_bending_fail_governs_ladder_runtime",
    "page_dispatch": 'inputs_page.py:family_strategy_for("BENDING_FAIL_GOVERNS")',
    "page_ladder_call": "inputs_page.py:contracted_repair_ladder_specs(...)",
    "page_evaluation_loop": "inputs_page.py:_evaluate(...)",
}

CUTOVER_PLAN = {
    "replacement_target": "BendingFailFamily.contracted_repair_ladder_specs",
    "new_authority": "run_bending_fail_governs_ladder_runtime",
    "planned_family_owned": [
        "contract lane order",
        "strategy lane decision",
        "ladder trace",
        "accepted/rejected lane evidence",
        "selected recommendation proof",
        "repair/blocked reason proof",
        "CTA intent proof only",
    ],
    "planned_page_shared_owned": [
        "candidate evaluation calls",
        "CTA rendering",
        "publication",
        "apply routing",
        "visible wording",
        "UI/session/debug",
    ],
    "planned_files_for_cutover": [
        "inputs_page.py",
        "design_brain/families/bending_fail_governs/__init__.py",
    ],
    "explicitly_not_touched": [
        "design_brain/families/shear_fail.py",
        "design_brain/families/shear_fail_governs/",
        "design_brain/families/shear_overdesign_governs/",
        "design_brain/families/shear_fail_bending_overdesign_governs/",
    ],
}

FORBIDDEN_OWNERSHIP_MOVES = {
    "CTA rendering",
    "publication",
    "apply routing",
    "visible wording",
    "UI/session/debug",
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _has_class_method(source: str, class_name: str, method_name: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(isinstance(child, ast.FunctionDef) and child.name == method_name for child in node.body)
    return False


def _has_function(source: str, function_name: str) -> bool:
    tree = ast.parse(source)
    return any(isinstance(node, ast.FunctionDef) and node.name == function_name for node in ast.walk(tree))


def _contains_all(source: str, needles: list[str]) -> dict[str, bool]:
    return {needle: needle in source for needle in needles}


def _planned_shear_files() -> list[str]:
    planned = [str(path) for path in CUTOVER_PLAN["planned_files_for_cutover"]]
    return [
        path
        for path in planned
        if "shear" in path.replace("\\", "/").lower()
        or "SHEAR_FAIL_GOVERNS" in path
    ]


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_cutover_plan_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_GOVERNS Cutover Plan",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "Purpose: prove the exact cutover boundary is known and narrow.",
                "",
                "## Cutover Boundary",
                "",
                f"- replacement target: `{snapshot['cutover_plan']['replacement_target']}`",
                f"- new authority: `{snapshot['cutover_plan']['new_authority']}`",
                "",
                "## Checks",
                "",
                f"- old replacement target found: `{snapshot['checks']['old_replacement_target_found']}`",
                f"- new authority found: `{snapshot['checks']['new_authority_found']}`",
                f"- contract order unchanged: `{snapshot['checks']['contract_order_unchanged']}`",
                f"- required runtime fields present: `{snapshot['checks']['required_runtime_fields_present']}`",
                f"- page evaluation loop retained: `{snapshot['checks']['page_evaluation_loop_retained']}`",
                f"- no CTA/publication/apply/UI ownership move: `{snapshot['checks']['no_cta_publication_apply_ui_move']}`",
                f"- no SHEAR files planned: `{snapshot['checks']['no_shear_files_planned']}`",
                "",
                "## Contract Order",
                "",
                "```text",
                " -> ".join(snapshot["contract_lane_order"]),
                "```",
                "",
                "## Page-Owned During Cutover",
                "",
                *[f"- {item}" for item in snapshot["cutover_plan"]["planned_page_shared_owned"]],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    bending_fail_source = _read("design_brain/families/bending_fail.py")
    package_source = _read("design_brain/families/bending_fail_governs/__init__.py")
    runtime_source = _read("design_brain/families/bending_fail_governs/runtime.py")
    inputs_source = _read("inputs_page.py")

    old_target_found = _has_class_method(
        bending_fail_source,
        "BendingFailFamily",
        "contracted_repair_ladder_specs",
    )
    compatibility_api_absent = not _has_function(package_source, "evaluate_" + "bending_fail_governs")
    new_authority_found = callable(run_bending_fail_governs_ladder_runtime) and (
        "def run_bending_fail_governs_ladder_runtime" in runtime_source
    )
    package_exports_new_authority = "run_bending_fail_governs_ladder_runtime" in package_source
    inputs_surface = _contains_all(
        inputs_source,
        [
            'family_strategy_for("BENDING_FAIL_GOVERNS")',
            "contracted_repair_ladder_specs(",
            "def _evaluate(",
            "_evaluate_auto_design_candidate(",
            "eval_source = \"bending_fail_contract_ladder\"",
        ],
    )
    page_evaluation_loop_retained = (
        inputs_surface["def _evaluate("]
        and inputs_surface["_evaluate_auto_design_candidate("]
        and not inputs_surface['family_strategy_for("BENDING_FAIL_GOVERNS")']
        and not inputs_surface["contracted_repair_ladder_specs("]
        and not inputs_surface['eval_source = "bending_fail_contract_ladder"']
    )
    contract_order = bending_fail_governs_contract_lane_order()
    result_fields = {field.name for field in fields(BendingFailGovernsResult)}
    planned_shear_files = _planned_shear_files()
    forbidden_family_owned_moves = [
        item
        for item in CUTOVER_PLAN["planned_family_owned"]
        if item in FORBIDDEN_OWNERSHIP_MOVES
    ]

    checks = {
        "old_replacement_target_found": old_target_found,
        "new_authority_found": new_authority_found and package_exports_new_authority,
        "old_compatibility_api_absent": compatibility_api_absent,
        "contract_order_unchanged": contract_order == EXPECTED_CONTRACT_ORDER,
        "required_runtime_fields_present": REQUIRED_RESULT_FIELDS.issubset(result_fields),
        "page_evaluation_loop_retained": page_evaluation_loop_retained,
        "no_cta_publication_apply_ui_move": not forbidden_family_owned_moves,
        "no_shear_files_planned": not planned_shear_files,
    }
    snapshot = {
        "schema": "bending_fail_governs_cutover_plan.v1",
        "result": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "old_surfaces": OLD_SURFACES,
        "source_findings": {
            "old_target_found": old_target_found,
            "old_compatibility_api_absent": compatibility_api_absent,
            "new_authority_found": new_authority_found,
            "package_exports_new_authority": package_exports_new_authority,
            "inputs_page_surfaces": inputs_surface,
        },
        "cutover_plan": CUTOVER_PLAN,
        "contract_lane_order": list(contract_order),
        "expected_contract_order": list(EXPECTED_CONTRACT_ORDER),
        "required_runtime_fields": sorted(REQUIRED_RESULT_FIELDS),
        "actual_runtime_fields": sorted(result_fields),
        "planned_shear_files": planned_shear_files,
        "forbidden_family_owned_moves": forbidden_family_owned_moves,
        "scope_limits": {
            "changes_product_routing": False,
            "moves_cta_rendering": False,
            "moves_publication": False,
            "moves_apply_routing": False,
            "moves_visible_wording": False,
            "moves_ui_session_debug": False,
            "touches_shear_fail_governs": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)

    if snapshot["result"] != "PASS":
        print("cutover plan FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("cutover plan PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
