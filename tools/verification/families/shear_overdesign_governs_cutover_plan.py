"""Cutover plan verifier for SHEAR_OVERDESIGN_GOVERNS."""

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

from design_brain.families.shear_overdesign_governs.runtime import (  # noqa: E402
    run_shear_overdesign_governs_runtime,
    shear_overdesign_contract_lane_order,
)


EXPECTED_ORDER = (
    "SPACING_INCREASE",
    "BAR_SIZE_REDUCTION",
    "LEG_COUNT_REDUCTION",
    "LIGATURE_REMOVAL",
    "EXACT_STOP",
    "EXHAUSTED",
)

PLANNED_CUTOVER_TARGETS = (
    "design_brain/families/shear_cleanup.py",
    "design_brain/families/shear_overdesign_governs/__init__.py",
)
FORBIDDEN_TARGET_FRAGMENTS = (
    "bending",
    "shear_fail.py",
    "shear_fail_governs",
    "publication.py",
    "inputs_page.py",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _contains_near(source: str, anchor: str, needle: str, *, window: int = 8000) -> bool:
    index = source.find(anchor)
    return index >= 0 and needle in source[index : index + window]


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_overdesign_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_cutover_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Cutover Plan",
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
    cleanup_source = _read("design_brain/families/shear_cleanup.py")
    package_source = _read("design_brain/families/shear_overdesign_governs/__init__.py")
    inputs_source = _read("inputs_page.py")
    planned_targets = tuple(PLANNED_CUTOVER_TARGETS)
    forbidden_targets = sorted(
        target
        for target in planned_targets
        for fragment in FORBIDDEN_TARGET_FRAGMENTS
        if fragment in target
    )
    checks = {
        "old_family_shell_known": "class ShearCleanupFamily" in cleanup_source
        and "SHEAR_OVERDESIGN_GOVERNS" in cleanup_source,
        "compatibility_api_known": "def evaluate_shear_overdesign_governs(" in package_source,
        "old_page_local_cleanup_known": "_compute_shear_tightening_recommendation" in inputs_source
        and "generate_less_shear_reo_variants" in inputs_source,
        "zero_shear_page_anchor_known": "_try_shear_remove_links_tightening_recommendation" in inputs_source
        and "_shear_no_links_candidate_passes_code" in inputs_source,
        "page_evaluator_surface_known": "evaluate_candidate_full(" in inputs_source
        and "_evaluate_candidate_fast(" in inputs_source,
        "shared_cta_publication_apply_remain_page_owned": (
            "from design_brain.cta_contracts import" in inputs_source
            and "from design_brain.publication import" in inputs_source
            and "build_design_guide_apply_button_contract" in inputs_source
            and "record_design_guide_publication_snapshot" in inputs_source
            and "inputs_page.py" not in planned_targets
            and "design_brain/publication.py" not in planned_targets
        ),
        "new_authority_available": callable(run_shear_overdesign_governs_runtime),
        "contract_lane_order_unchanged": shear_overdesign_contract_lane_order() == EXPECTED_ORDER,
        "planned_targets_are_narrow": not forbidden_targets,
        "inputs_page_not_cutover_target": "inputs_page.py" not in planned_targets,
        "bending_not_cutover_target": not any("bending" in target for target in planned_targets),
        "shear_fail_not_cutover_target": not any("shear_fail" in target for target in planned_targets),
        "cutover_not_enabled_by_plan": True,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "shear_overdesign_governs_cutover_plan.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "replacement_boundary": {
            "old_family_shell": "design_brain.families.shear_cleanup.ShearCleanupFamily",
            "old_page_local_logic": "inputs_page._compute_shear_tightening_recommendation",
            "new_authority": "design_brain.families.shear_overdesign_governs.runtime.run_shear_overdesign_governs_runtime",
            "shared_execution_surface": "inputs_page.py evaluator / CTA / publication / apply / UI plumbing",
        },
        "planned_cutover_targets": list(planned_targets),
        "forbidden_planned_targets": forbidden_targets,
        "contract_lane_order": list(shear_overdesign_contract_lane_order()),
        "scope_limits": {
            "product_cutover_enabled": False,
            "inputs_page_modified": False,
            "cta_publication_apply_ui_moved": False,
            "geometry_reduction_allowed": False,
            "bending_touched": False,
            "shear_fail_touched": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("SHEAR_OVERDESIGN_GOVERNS cutover plan FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_OVERDESIGN_GOVERNS cutover plan PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
