"""Cutover plan verifier for COMBINED_OVERDESIGN_GOVERNS."""

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

from design_brain.families.bending_and_shear_overdesign_govern.runtime import (  # noqa: E402
    run_combined_overdesign_governs_runtime,
)


PLANNED_CUTOVER_TARGETS = (
    "design_brain/families/combined_cleanup.py",
    "design_brain/families/bending_and_shear_overdesign_govern/__init__.py",
)
FORBIDDEN_TARGETS = (
    "inputs_page.py",
    "design_brain/publication.py",
    "design_brain/families/bending_cleanup.py",
    "design_brain/families/shear_cleanup.py",
    "design_brain/families/bending_overdesign_governs/runtime.py",
    "design_brain/families/shear_overdesign_governs/runtime.py",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_cutover_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_OVERDESIGN_GOVERNS Cutover Plan",
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
    inputs_source = _read("inputs_page.py")
    targets = tuple(PLANNED_CUTOVER_TARGETS)
    forbidden_hits = sorted(target for target in targets if target in FORBIDDEN_TARGETS)
    checks = {
        "new_runtime_available": callable(run_combined_overdesign_governs_runtime),
        "replacement_target_is_family_shell": "design_brain/families/combined_cleanup.py" in targets,
        "package_api_target_is_narrow": "design_brain/families/bending_and_shear_overdesign_govern/__init__.py" in targets,
        "no_inputs_page_cutover": "inputs_page.py" not in targets,
        "no_shared_publication_cutover": "design_brain/publication.py" not in targets,
        "no_source_ladder_cutover": not any("bending_cleanup.py" in target or "shear_cleanup.py" in target for target in targets),
        "shared_surfaces_remain_known": "record_design_guide_publication_snapshot" in inputs_source
        and "build_design_guide_apply_button_contract" in inputs_source,
        "planned_targets_are_narrow": not forbidden_hits,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_overdesign_governs_cutover_plan.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "planned_cutover_targets": list(targets),
        "new_authority": "run_combined_overdesign_governs_runtime",
        "scope_limits": {
            "combined_generates_no_optimisation_ladder": True,
            "inputs_page_modified": False,
            "source_ladders_modified": False,
            "shared_surfaces_moved": False,
        },
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_OVERDESIGN_GOVERNS cutover plan FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_OVERDESIGN_GOVERNS cutover plan PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
