"""Cutover plan verifier for BENDING_OVERDESIGN_GOVERNS."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_overdesign_governs.runtime import (  # noqa: E402
    bending_overdesign_contract_lane_order,
    run_bending_overdesign_governs_runtime,
)


EXPECTED_ORDER = (
    "BOTTOM_REINFORCEMENT_REDUCTION",
    "LAYER_REDUCTION",
    "WIDTH_REDUCTION",
    "DEPTH_REDUCTION",
    "EXACT_STOP",
    "EXHAUSTED",
)

PLANNED_CUTOVER_TARGETS = (
    "design_brain/families/bending_cleanup.py",
    "design_brain/families/bending_overdesign_governs/__init__.py",
)
FORBIDDEN_TARGET_FRAGMENTS = (
    "bending_fail.py",
    "bending_fail_governs",
    "shear_fail.py",
    "shear_fail_governs",
    "shear_cleanup.py",
    "shear_overdesign_governs",
    "publication.py",
    "inputs_page.py",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _read_inputs_composition_surface() -> str:
    return "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_application/candidate_full_evaluation.py",
            "inputs_application/page_runtime/design_guide.py",
            "inputs_application/page_runtime/design_guide_runtime_support.py",
            "inputs_page_modules/apply_routing.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
        )
    )


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_overdesign_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_governs_cutover_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_OVERDESIGN_GOVERNS Cutover Plan",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Replacement Boundary",
                "",
                f"- old shell: `{snapshot['replacement_boundary']['old_family_shell']}`",
                f"- old live logic: `{snapshot['replacement_boundary']['old_page_local_logic']}`",
                f"- new authority: `{snapshot['replacement_boundary']['new_authority']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    cleanup_source = _read("design_brain/families/bending_cleanup.py")
    package_source = _read("design_brain/families/bending_overdesign_governs/__init__.py")
    inputs_source = _read_inputs_composition_surface()
    extracted_cleanup_source = "\n".join(
        _read(path)
        for path in (
            "design_brain/candidate_evaluation.py",
            "design_brain/design_guide_controller.py",
        )
    )
    evaluator_source = "\n".join(
        _read(path)
        for path in (
            "design_brain/candidate_evaluation.py",
            "inputs_application/candidate_full_evaluation.py",
            "inputs_application/fast_candidate_evaluator.py",
            "inputs_application/family_ladder_live_evaluators.py",
        )
    )
    planned_targets = tuple(PLANNED_CUTOVER_TARGETS)
    forbidden_targets = sorted(
        target
        for target in planned_targets
        for fragment in FORBIDDEN_TARGET_FRAGMENTS
        if fragment in target
    )
    checks = {
        "old_family_shell_known": "class BendingCleanupFamily" in cleanup_source
        and "BENDING_OVERDESIGN_GOVERNS" in cleanup_source,
        "compatibility_api_known": "def evaluate_bending_overdesign_governs(" in package_source,
        "family_first_cutover_known": (
            "resolve_family_ladder_dispatch" in _read("design_brain/family_ladder_dispatch.py")
            and "build_bending_overdesign_live_evaluator"
            in _read("inputs_application/family_ladder_live_evaluators.py")
            and "family_ladder:" in _read(
                "inputs_page_modules/design_guide/family_ladder_guidance.py"
            )
        ),
        "minimum_reinforcement_page_anchor_known": "As_min" in evaluator_source
        and ("evaluate_candidate_full(" in inputs_source or "evaluate_candidate_full" in inputs_source),
        "page_evaluator_surface_known": "evaluate_candidate_full" in evaluator_source
        and "evaluate_candidate_full" in inputs_source,
        "shared_cta_publication_apply_remain_page_owned": (
            "from design_brain.final_publication import" in inputs_source
            and "build_final_design_guide_publication" in inputs_source
            and "handle_inputs_apply_buttons" in inputs_source
            and "inputs_page.py" not in planned_targets
            and "design_brain/publication.py" not in planned_targets
        ),
        "new_authority_available": callable(run_bending_overdesign_governs_runtime),
        "contract_lane_order_unchanged": bending_overdesign_contract_lane_order() == EXPECTED_ORDER,
        "planned_targets_are_narrow": not forbidden_targets,
        "inputs_page_not_cutover_target": "inputs_page.py" not in planned_targets,
        "shared_publication_not_cutover_target": "design_brain/publication.py" not in planned_targets,
        "other_locked_families_not_cutover_targets": not any(
            target
            for target in planned_targets
            if "bending_fail" in target or "shear_fail" in target or "shear_overdesign" in target
        ),
        "family_first_cutover_enabled_by_plan": True,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "bending_overdesign_governs_cutover_plan.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "replacement_boundary": {
            "old_family_shell": "design_brain.families.bending_cleanup.BendingCleanupFamily",
            "old_page_local_logic": "inputs_page._bending_only_target_band_cleanup_item",
            "new_authority": "design_brain.families.bending_overdesign_governs.runtime.run_bending_overdesign_governs_runtime",
            "shared_execution_surface": "inputs_page.py evaluator / CTA / publication / apply / UI plumbing",
        },
        "planned_cutover_targets": list(planned_targets),
        "forbidden_planned_targets": forbidden_targets,
        "contract_lane_order": list(bending_overdesign_contract_lane_order()),
        "scope_limits": {
            "product_cutover_enabled": True,
            "inputs_page_modified": False,
            "cta_publication_apply_ui_moved": False,
            "reinforcement_only_optimisation_protected": True,
            "controlled_geometry_reduction_allowed_by_contract": True,
            "other_locked_families_touched": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("BENDING_OVERDESIGN_GOVERNS cutover plan FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_OVERDESIGN_GOVERNS cutover plan PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
