"""Cutover plan verifier for SERVICEABILITY_GOVERNS."""

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

from design_brain.families.serviceability_governs.runtime import (  # noqa: E402
    ServiceabilityGovernsResult,
    run_serviceability_governs_ladder_runtime,
)
from design_brain.families.serviceability_governs.contract import (  # noqa: E402
    serviceability_contract_lane_order,
)


EXPECTED_CONTRACT_ORDER = (
    "BOTTOM_REINFORCEMENT_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
)
REQUIRED_RESULT_FIELDS = {
    "status",
    "selected_strategy_lane",
    "selected_recommendation",
    "candidate_repairs",
    "exhausted_reason",
    "evidence",
    "ladder_trace",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "ranking_evidence",
    "exact_stop_proof",
    "exhausted_proof",
    "ownership_proof",
    "ladder_hash",
}
CUTOVER_PLAN = {
    "replacement_target": "design_brain.families.serviceability_governs.evaluate_serviceability_governs",
    "new_authority": "run_serviceability_governs_ladder_runtime",
    "planned_family_owned": [
        "contract lane order",
        "serviceability candidate generation",
        "candidate ranking",
        "exact stop proof",
        "exhausted proof",
        "blocker evidence",
        "selected recommendation proof",
    ],
    "planned_shared_owned": [
        "family selection",
        "candidate evaluation calls",
        "publication",
        "CTA generation",
        "CTA rendering",
        "apply routing",
        "one-click orchestration",
        "visible wording",
        "UI/session/debug",
        "source precedence",
    ],
    "planned_files_for_cutover": [
        "design_brain/families/serviceability_governs/__init__.py",
        "design_brain/families/serviceability.py",
    ],
    "explicitly_not_touched": [
        "inputs_page.py",
        "design_brain/families/bending_fail_governs/",
        "design_brain/families/shear_fail_governs/",
        "design_brain/families/combined_overdesign_governs/",
    ],
}
FORBIDDEN_OWNERSHIP_MOVES = {
    "family selection",
    "publication",
    "CTA generation",
    "CTA rendering",
    "apply routing",
    "one-click orchestration",
    "visible wording",
    "UI/session/debug",
    "source precedence",
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _has_function(source: str, function_name: str) -> bool:
    tree = ast.parse(source)
    return any(isinstance(node, ast.FunctionDef) and node.name == function_name for node in ast.walk(tree))


def _contains_all(source: str, needles: list[str]) -> dict[str, bool]:
    return {needle: needle in source for needle in needles}


def _planned_cross_family_files() -> list[str]:
    blocked_tokens = ("bending_fail", "shear_fail", "combined_overdesign", "combined_bending_shear")
    return [
        path
        for path in CUTOVER_PLAN["planned_files_for_cutover"]
        if any(token in str(path).replace("\\", "/").lower() for token in blocked_tokens)
    ]


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_cutover_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SERVICEABILITY_GOVERNS Cutover Plan",
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
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in snapshot["checks"].items())
    lines.extend(["", "## Shared-Owned During Cutover", ""])
    lines.extend(f"- {item}" for item in snapshot["cutover_plan"]["planned_shared_owned"])
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    package_source = _read("design_brain/families/serviceability_governs/__init__.py")
    family_source = _read("design_brain/families/serviceability.py")
    registry_source = _read("design_brain/families/registry.py")
    chooser_source = _read("design_brain/family_chooser.py")
    runtime_source = _read("design_brain/families/serviceability_governs/runtime.py")

    package_api_found = _has_function(package_source, "evaluate_serviceability_governs")
    package_api_scaffolded = "NotImplementedError" in package_source
    family_shell_found = "class ServiceabilityFamily" in family_source and "SERVICEABILITY_GOVERNS" in family_source
    registry_found = '"SERVICEABILITY_GOVERNS": ServiceabilityFamily' in registry_source
    chooser_surface = _contains_all(
        chooser_source,
        [
            '"SERVICEABILITY_GOVERNS"',
            '"serviceability_fail"',
            '"geometry_detailing_fail"',
        ],
    )
    new_authority_found = callable(run_serviceability_governs_ladder_runtime) and (
        "def run_serviceability_governs_ladder_runtime" in runtime_source
    )
    result_fields = {field.name for field in fields(ServiceabilityGovernsResult)}
    forbidden_family_owned_moves = [
        item
        for item in CUTOVER_PLAN["planned_family_owned"]
        if item in FORBIDDEN_OWNERSHIP_MOVES
    ]
    cross_family_files = _planned_cross_family_files()

    checks = {
        "replacement_target_is_package_api": package_api_found,
        "package_api_no_longer_scaffolded_after_cutover": not package_api_scaffolded,
        "family_shell_and_registry_exist": family_shell_found and registry_found,
        "selection_boundary_exists_outside_runtime": all(chooser_surface.values()),
        "new_authority_is_runtime": new_authority_found,
        "contract_order_unchanged": serviceability_contract_lane_order() == EXPECTED_CONTRACT_ORDER,
        "required_runtime_fields_present": REQUIRED_RESULT_FIELDS.issubset(result_fields),
        "cutover_does_not_move_shared_ownership": not forbidden_family_owned_moves,
        "inputs_page_not_required_for_cutover_plan": "inputs_page.py" not in CUTOVER_PLAN["planned_files_for_cutover"],
        "no_other_locked_family_files_in_cutover_plan": not cross_family_files,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "serviceability_governs_cutover_plan.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "source_findings": {
            "package_api_found": package_api_found,
            "package_api_scaffolded": package_api_scaffolded,
            "family_shell_found": family_shell_found,
            "registry_found": registry_found,
            "chooser_surface": chooser_surface,
            "new_authority_found": new_authority_found,
        },
        "cutover_plan": CUTOVER_PLAN,
        "contract_lane_order": list(serviceability_contract_lane_order()),
        "expected_contract_order": list(EXPECTED_CONTRACT_ORDER),
        "required_runtime_fields": sorted(REQUIRED_RESULT_FIELDS),
        "actual_runtime_fields": sorted(result_fields),
        "forbidden_family_owned_moves": forbidden_family_owned_moves,
        "cross_family_files": cross_family_files,
        "scope_limits": {
            "changes_product_routing": False,
            "moves_family_selection": False,
            "moves_publication": False,
            "moves_cta": False,
            "moves_apply_routing": False,
            "moves_one_click": False,
            "moves_visible_wording": False,
            "moves_ui_session_debug": False,
            "touches_other_locked_families": False,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    print(f"{snapshot['result']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
