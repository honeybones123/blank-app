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


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_governs_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_governs_cutover_plan_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN Cutover Plan",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "- Replacement target: `ShearFailBendingOverdesignFamily.contracted_mixed_ladder_result(...)`",
                "- New authority: `run_shear_fail_bending_overdesign_runtime(...)`",
                "- Shared evaluator/CTA/publication/apply/UI stays outside the family.",
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
    family_source = _read("design_brain/families/shear_fail_bending_overdesign.py")
    runtime_source = _read("design_brain/families/shear_fail_bending_overdesign_governs/runtime.py")
    inputs_source = _read("inputs_page.py")
    checks = {
        "family_shell_exists": "class ShearFailBendingOverdesignFamily" in family_source,
        "cutover_method_named": "def contracted_mixed_ladder_result" in family_source,
        "new_runtime_authority_named": "run_shear_fail_bending_overdesign_runtime" in family_source,
        "runtime_does_not_import_inputs_page": "inputs_page" not in runtime_source,
        "runtime_does_not_own_cta_publication_apply_ui": all(
            term not in runtime_source.lower()
            for term in ("button_contract", "publication", "apply_routing", "one_click", "st.session_state")
        ),
        "inputs_page_keeps_evaluator_loop": "def _evaluate(" in inputs_source and "_evaluate_auto_design_candidate(" in inputs_source,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "shear_fail_bending_overdesign_governs_cutover_plan.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "scope": {
            "replace_target": "ShearFailBendingOverdesignFamily.contracted_mixed_ladder_result",
            "new_authority": "run_shear_fail_bending_overdesign_runtime",
            "shared_surfaces_moved": False,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS cutover plan FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS cutover plan PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
