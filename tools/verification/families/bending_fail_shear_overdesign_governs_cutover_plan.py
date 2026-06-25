from __future__ import annotations

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

from design_brain.families.bending_fail_shear_overdesign_governs.runtime import (  # noqa: E402
    BendingFailShearOverdesignResult,
    run_bending_fail_shear_overdesign_runtime,
)


REQUIRED_RESULT_FIELDS = {
    "status",
    "selected_recommendation",
    "candidate_repairs",
    "exhausted_reason",
    "evidence",
    "selection_boundary",
    "candidate_source_proof",
    "mixed_merge_trace",
    "accepted_candidate_evidence",
    "rejected_candidate_evidence",
    "ranking_evidence",
    "exact_stop_proof",
    "exhausted_proof",
    "ownership_proof",
    "runtime_hash",
}
CUTOVER_PLAN = {
    "replacement_target": "shared family selection plus package public API",
    "new_authority": "run_bending_fail_shear_overdesign_runtime",
    "planned_family_owned": [
        "candidate merge",
        "candidate ranking",
        "recommendation selection",
        "exact stop proof",
        "exhausted proof",
        "mixed evidence",
    ],
    "planned_source_family_owned": [
        "BENDING_FAIL_GOVERNS repair ladder",
        "SHEAR_OVERDESIGN_GOVERNS optimisation ladder",
    ],
    "planned_shared_owned": [
        "family selection",
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
        "design_brain/families/bending_fail_shear_overdesign.py",
        "design_brain/families/bending_fail_shear_overdesign_governs/__init__.py",
        "design_brain/families/registry.py",
        "design_brain/family_chooser.py",
        "design_brain/family_classification_runtime.py",
    ],
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_cutover_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN Cutover Plan",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    chooser = _read("design_brain/family_chooser.py")
    registry = _read("design_brain/families/registry.py")
    package = _read("design_brain/families/bending_fail_shear_overdesign_governs/__init__.py")
    runtime = _read("design_brain/families/bending_fail_shear_overdesign_governs/runtime.py")
    result_fields = {field.name for field in fields(BendingFailShearOverdesignResult)}
    checks = {
        "new_authority_available": callable(run_bending_fail_shear_overdesign_runtime),
        "required_result_fields_present": REQUIRED_RESULT_FIELDS.issubset(result_fields),
        "shared_selection_wiring_present": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS" in chooser
        and "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS" in registry,
        "package_public_api_runtime_driven": "run_bending_fail_shear_overdesign_runtime" in package
        and "NotImplementedError" not in package,
        "runtime_does_not_call_source_ladders": "run_bending_fail_governs_ladder_runtime" not in runtime
        and "run_shear_overdesign_governs_runtime" not in runtime,
        "cutover_does_not_move_shared_app_surfaces": all(
            item not in CUTOVER_PLAN["planned_family_owned"]
            for item in ("publication", "CTA rendering", "apply routing", "UI/session/debug")
        ),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_cutover_plan.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "cutover_plan": CUTOVER_PLAN,
        "required_result_fields": sorted(REQUIRED_RESULT_FIELDS),
        "actual_result_fields": sorted(result_fields),
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    print(f"{snapshot['result']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
