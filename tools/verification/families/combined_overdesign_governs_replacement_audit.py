"""Current-live replacement audit for COMBINED_OVERDESIGN_GOVERNS."""

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

from design_brain.families.bending_and_shear_overdesign_govern.contract import candidate_source_contract  # noqa: E402


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_replacement_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_OVERDESIGN_GOVERNS Replacement Audit",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Classification",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["classification"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    shell = _read("design_brain/families/combined_cleanup.py")
    inputs = _read("inputs_page.py")
    runtime = _read("design_brain/families/bending_and_shear_overdesign_govern/runtime.py")
    controller = _read("design_brain/design_guide_controller.py")
    source_contract = candidate_source_contract()
    legacy_page_helpers_present = (
        "_publishable_safe_combined_cleanup_row_from_evidence" in inputs
        and "_visible_safe_combined_cleanup_action_from_evidence" in inputs
    )
    shared_shell_orchestration_present = (
        "run_design_guide_combined_low_util_orchestration" in controller
        and "build_design_guide_controller_combined_low_util_cleanup_route_policy_proof" in controller
    )
    family_runtime_does_not_absorb_shared_shell_logic = (
        "_publishable_safe_combined_cleanup_row_from_evidence" not in runtime
        and "_visible_safe_combined_cleanup_action_from_evidence" not in runtime
        and "run_design_guide_combined_low_util_orchestration" not in runtime
    )
    classification = {
        "family_shell_runtime_backed": "class CombinedCleanupFamily" in shell
        and "contracted_optimisation_ladder_specs" in shell
        and "run_combined_overdesign_governs_runtime" in shell,
        "old_live_logic_stays_shared_shell_owned": legacy_page_helpers_present
        and shared_shell_orchestration_present
        and family_runtime_does_not_absorb_shared_shell_logic,
        "new_runtime_authority_is_merge_only": "run_combined_overdesign_governs_runtime" in runtime
        and "run_bending_overdesign_governs_runtime" not in runtime
        and "run_shear_overdesign_governs_runtime" not in runtime,
        "new_source_contract_is_expected_replacement": set(source_contract.get("allowed_sources") or [])
        == {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"}
        and source_contract.get("must_not_duplicate_ladders") is True,
        "shared_surfaces_remain_page_owned": "record_design_guide_publication_snapshot" in inputs
        and "build_design_guide_apply_button_contract" in inputs,
    }
    failures = sorted(key for key, passed in classification.items() if not passed)
    snapshot = {
        "schema": "combined_overdesign_governs_replacement_audit.v1",
        "result": "PASS" if not failures else "FAIL",
        "classification": classification,
        "replacement_classification": {
            "old_page_safe_combined_cleanup": "EXPECTED_CONTRACT_REPLACEMENT",
            "old_family_shell_without_runtime": "EXPECTED_CONTRACT_REPLACEMENT",
            "new_merge_runtime": "AUTHORITATIVE_CONTRACT_RUNTIME",
            "bending_shear_source_ladders": "NO_DUPLICATION_ALLOWED",
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_OVERDESIGN_GOVERNS replacement audit FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_OVERDESIGN_GOVERNS replacement audit PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
