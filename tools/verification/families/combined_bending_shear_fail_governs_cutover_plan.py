"""Cutover plan verifier for COMBINED_BENDING_SHEAR_FAIL_GOVERNS."""

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

from design_brain.families.bending_and_shear_fail_govern.runtime import run_combined_bending_shear_fail_runtime  # noqa: E402


PLANNED_TARGETS = (
    "design_brain/families/combined_bending_shear_fail.py",
    "design_brain/families/bending_and_shear_fail_govern/__init__.py",
)
FORBIDDEN_TARGET_FRAGMENTS = (
    "inputs_page.py",
    "publication.py",
    "families/bending_fail.py",
    "families/shear_fail.py",
    "families/bending_cleanup.py",
    "families/shear_cleanup.py",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_governs_cutover_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_BENDING_SHEAR_FAIL_GOVERNS Cutover Plan",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    family_source = _read("design_brain/families/combined_bending_shear_fail.py")
    package_source = _read("design_brain/families/bending_and_shear_fail_govern/__init__.py")
    inputs_source = _read("inputs_page.py")
    publication_source = _read("design_brain/publication.py")
    forbidden_targets = sorted(
        target for target in PLANNED_TARGETS for fragment in FORBIDDEN_TARGET_FRAGMENTS if fragment in target
    )
    checks = {
        "old_family_shell_known": "class CombinedBendingShearFailFamily" in family_source,
        "old_bounded_ladder_target_known_or_already_replaced": (
            "def contracted_repair_ladder_specs" in family_source
            and (
                "DEFAULT_DEPTH_STEPS_MM" in family_source
                or "run_combined_bending_shear_fail_runtime" in family_source
            )
        ),
        "compatibility_api_known": "def evaluate_bending_and_shear_fail_govern" in package_source,
        "new_authority_available": callable(run_combined_bending_shear_fail_runtime),
        "planned_targets_are_narrow": not forbidden_targets,
        "inputs_page_not_cutover_target": "inputs_page.py" not in PLANNED_TARGETS,
        "shared_publication_not_cutover_target": "design_brain/publication.py" not in PLANNED_TARGETS,
        "shared_surfaces_exist_and_remain_outside": "combined_fail_contract_ladder" in inputs_source
        and "_route_combined_fail_family_publication" in publication_source,
        "locked_source_families_not_cutover_targets": not any(
            target.endswith(protected)
            for target in PLANNED_TARGETS
            for protected in (
                "families/bending_fail.py",
                "families/shear_fail.py",
                "families/bending_cleanup.py",
                "families/shear_cleanup.py",
            )
        ),
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_bending_shear_fail_governs_cutover_plan.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "planned_targets": list(PLANNED_TARGETS),
        "forbidden_targets": forbidden_targets,
        "replacement_boundary": {
            "old_authority": "CombinedBendingShearFailFamily.contracted_repair_ladder_specs bounded ladder",
            "new_authority": "run_combined_bending_shear_fail_runtime",
            "shared_surfaces": "inputs_page.py and design_brain/publication.py remain shared-owned",
        },
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS cutover plan FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS cutover plan PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
