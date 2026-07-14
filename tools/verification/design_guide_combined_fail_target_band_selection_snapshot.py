"""Snapshot for combined active-fail target-band selection.

The combined active-fail family may accept safe repairs only as candidates for
ranking. Final selection must prefer a candidate that places both bending and
shear in the target band over an earlier ladder candidate that merely makes the
beam safe but highly under-utilised.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
COMBINED_FAMILY = ROOT / "design_brain" / "families" / "combined_bending_shear_fail.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment
    raise RuntimeError(f"function not found: {function_name}")


def _run_compile() -> dict[str, Any]:
    paths = [
        "inputs_page.py",
        "design_brain/design_guide_controller.py",
        "design_brain/families/combined_bending_shear_fail.py",
        "tools/verification/design_guide_combined_fail_target_band_selection_snapshot.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *paths],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": f"python -m py_compile {' '.join(paths)}",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _build_snapshot() -> dict[str, Any]:
    from design_brain.families.combined_bending_shear_fail import CombinedBendingShearFailFamily
    from design_brain.families.bending_and_shear_fail_govern.contract import target_band, target_band_refinement_lane

    family = CombinedBendingShearFailFamily()
    candidates = [
        {
            "label": "first safe but below band",
            "combined_fail_ladder_index": 1,
            "updates": {"b": 400.0, "D": 650.0, "bot1_count": 5, "db_bot_1": 24, "lig_d": 12, "lig_legs": 4, "s_lig": 125.0},
            "overview": {"utils": {"bending": 0.38, "shear": 0.09}, "all_key_pass": True, "any_fail": False},
            "is_compliant": True,
        },
        {
            "label": "second safe in target band",
            "combined_fail_ladder_index": 2,
            "updates": {"b": 325.0, "D": 525.0, "bot1_count": 4, "db_bot_1": 20, "lig_d": 10, "lig_legs": 2, "s_lig": 150.0},
            "overview": {"utils": {"bending": 0.90, "shear": 0.91}, "all_key_pass": True, "any_fail": False},
            "is_compliant": True,
        },
        {
            "label": "third safe but only bending in band",
            "combined_fail_ladder_index": 3,
            "updates": {"b": 350.0, "D": 575.0, "bot1_count": 4, "db_bot_1": 24, "lig_d": 12, "lig_legs": 2, "s_lig": 175.0},
            "overview": {"utils": {"bending": 0.92, "shear": 0.62}, "all_key_pass": True, "any_fail": False},
            "is_compliant": True,
        },
    ]
    selection = family.select_repair_candidate_from_ladder(candidates, target_low=0.85, target_high=1.0)
    selected = dict(selection.get("selected") or {})
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    combined_source = COMBINED_FAMILY.read_text(encoding="utf-8")
    active_repair_source = controller_source
    combined_evidence_function = _function_source(
        controller_source,
        "build_design_guide_controller_active_fail_executor_candidate_search_evidence",
    )
    combined_evidence_marker = "if combined_family_ladder_attempted:"
    combined_evidence_start = combined_evidence_function.find(combined_evidence_marker)
    combined_evidence_end = combined_evidence_function.find("if bending_family_ladder_attempted:", combined_evidence_start)
    combined_evidence_source = (
        combined_evidence_function[combined_evidence_start:combined_evidence_end]
        if combined_evidence_start >= 0 and combined_evidence_end > combined_evidence_start
        else ""
    )
    selector_source = _function_source(combined_source, "select_repair_candidate_from_ladder")
    contract_target_band = target_band()
    refinement_lane = target_band_refinement_lane()
    checks = {
        "contract_declares_target_band_candidate_lane": (
            contract_target_band.get("candidate_lane") == "APPROVED_COMBINED_TARGET_BAND_REFINEMENT"
            and refinement_lane.get("lane_id") == "APPROVED_COMBINED_TARGET_BAND_REFINEMENT"
        ),
        "family_exposes_target_band_refinement_candidate_supplier": (
            "def build_target_band_refinement_candidates" in combined_source
            and "APPROVED_COMBINED_TARGET_BAND_REFINEMENT" in combined_source
        ),
        "controller_requests_family_target_band_refinement_candidates": (
            "build_target_band_refinement_candidates" in active_repair_source
            and "approved_candidates.extend" in active_repair_source
        ),
        "inputs_does_not_stop_combined_search_at_first_safe_seed": (
            "combined_family_ladder_found_safe = True\n                    break" not in active_repair_source
        ),
        "family_selector_exists": "def select_repair_candidate_from_ladder" in combined_source,
        "family_selector_chose_target_band_candidate": selected.get("combined_fail_ladder_index") == 2,
        "family_selector_not_first_safe_candidate": selected.get("combined_fail_ladder_index") != 1,
        "selected_has_both_domains_in_band": selection.get("selected_in_target_band_count") == 2,
        "controller_delegates_combined_selection_to_family": (
            'combined_family_strategy.select_repair_candidate_from_ladder(' in active_repair_source
        ),
        "controller_fallback_still_prefers_target_band_before_ladder_index": (
            "-_active_fail_executor_candidate_in_band_count(cand, float(low), float(high))" in active_repair_source
        ),
        "selector_uses_overview_utils": (
            "_combined_repair_candidate_rank_key" in selector_source
            and "_candidate_family_utils" in combined_source
            and "overview" in combined_source
            and "utils" in combined_source
        ),
        "controller_evidence_no_longer_claims_first_safe_selection": (
            "contract_family_target_band_ranked_candidate" in combined_evidence_source
            and "first_compliant_candidate_in_contract_ladder_order" not in combined_evidence_source
        ),
        "inputs_no_longer_owns_combined_selection_policy": (
            "combined_family_strategy.select_repair_candidate_from_ladder(" not in inputs_source
            and "approved_combined_merge_candidates.extend" not in inputs_source
        ),
    }
    payload = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "selection": selection,
        "candidate_labels": [candidate["label"] for candidate in candidates],
        "selected_label": selected.get("label"),
        "contract_alignment": {
            "family": "COMBINED_BENDING_SHEAR_FAIL",
            "ranking_owner": "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily",
            "rule": "both bending and shear inside target band outranks first safe ladder candidate",
            "candidate_lane": refinement_lane.get("lane_id"),
        },
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    return payload


def _write_artifacts(payload: dict[str, Any], compile_result: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_combined_fail_target_band_selection_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_fail_target_band_selection_{stamp}.md"
    json_path.write_text(_stable_json({"compile": compile_result, **payload}) + "\n", encoding="utf-8")
    checks = payload.get("checks") or {}
    report = [
        "# Design Guide Combined Fail Target-Band Selection Snapshot",
        "",
        f"Result: `{payload.get('status')}`",
        "",
        "## Selected Candidate",
        f"`{payload.get('selected_label')}`",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in sorted(checks.items())],
        "",
        "## Contract Alignment",
        _stable_json(payload.get("contract_alignment") or {}),
        "",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    compile_result = _run_compile()
    payload = _build_snapshot()
    if not compile_result["passed"]:
        payload["status"] = "FAIL"
    json_path, report_path = _write_artifacts(payload, compile_result)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if payload["status"] == "PASS" and compile_result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
