from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


FAMILIES = {
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "runtime.py",
        "delegate": ROOT / "design_brain" / "families" / "combined_bending_shear_fail.py",
        "expected_status": "FIX_VERIFIED",
    },
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "bending_fail_shear_overdesign_governs" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "bending_fail_shear_overdesign_governs" / "runtime.py",
        "expected_status": "FIX_VERIFIED",
    },
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "shear_fail_bending_overdesign_governs" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "shear_fail_bending_overdesign_governs" / "runtime.py",
        "expected_status": "FIX_VERIFIED",
    },
    "COMBINED_OVERDESIGN_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "bending_and_shear_overdesign_govern" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "bending_and_shear_overdesign_govern" / "runtime.py",
        "expected_status": "FIX_VERIFIED",
    },
    "BENDING_FAIL_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "bending_fail_governs" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "bending_fail_governs" / "runtime.py",
        "expected_status": "SINGLE_DOMAIN_LADDER_VERIFIED",
    },
    "SHEAR_FAIL_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "shear_fail_governs" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py",
        "delegate": ROOT / "design_brain" / "families" / "shear_fail_governs" / "repair_ladder.py",
        "expected_status": "SINGLE_DOMAIN_LADDER_VERIFIED",
    },
    "BENDING_OVERDESIGN_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "runtime.py",
        "expected_status": "SINGLE_DOMAIN_LADDER_VERIFIED",
    },
    "SHEAR_OVERDESIGN_GOVERNS": {
        "contract": ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "contract.json",
        "runtime": ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "runtime.py",
        "expected_status": "SINGLE_DOMAIN_LADDER_VERIFIED",
    },
}


def _read(path: Path | None) -> str:
    if not path:
        return ""
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(command: list[str], *, timeout: int = 120) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "command": command,
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _has_explicit_lane(contract: dict[str, Any], source_text: str) -> bool:
    target = contract.get("target_band") or {}
    source = contract.get("candidate_source_contract") or {}
    policies = contract.get("lane_proof_policies") or {}
    return bool(
        isinstance(target, dict)
        and target.get("candidate_lane")
        or isinstance(source, dict)
        and source.get("target_band_refinement_lane")
        or isinstance(policies, dict)
        and policies.get("target_band_refinement")
        or "target_band_refinement_proof" in source_text
    )


def _classify_family(family_id: str, config: dict[str, Any]) -> dict[str, Any]:
    contract_path = config["contract"]
    runtime_path = config["runtime"]
    delegate_path = config.get("delegate")
    contract = _load_json(contract_path)
    runtime_source = _read(runtime_path)
    delegate_source = _read(delegate_path)
    combined_source = runtime_source + "\n" + delegate_source
    has_target_band = isinstance(contract.get("target_band"), dict)
    is_single_domain_ladder = family_id in {
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_OVERDESIGN_GOVERNS",
    }
    explicit_lane = _has_explicit_lane(contract, combined_source)
    has_strategy_ladder = "strategy_ladder" in contract or "internal_strategy_ladder" in contract
    has_contract_candidate_generator = "_candidate_updates_from_contract" in combined_source or "run_bending_fail_governs_ladder_runtime" in combined_source or "run_shear_fail_governs_ladder_runtime" in combined_source
    runtime_counts_target_candidates = (
        "target_band_candidate_count" in combined_source
        or "target_band_repairs" in combined_source
        or "selected_inside_target_band" in combined_source
        or "target_band_selected" in combined_source
        or "target_band_status" in combined_source
    )
    runtime_has_fallback_reason = "fallback_reason" in combined_source or "specific_blocker" in combined_source
    exact_stop_tied_to_target = (
        "exact_stop = bool(" in combined_source
        and "bending_inside_target_band" in combined_source
        and "shear_inside_target_band" in combined_source
    ) or (
        "selected_inside_bending_band" in combined_source
        and "selected_inside_shear_band" in combined_source
    )
    exact_stop_still_bool_selected = '"no_higher_ranked_candidate_exists": bool(selected)' in combined_source
    single_domain_contract_verified = (
        is_single_domain_ladder
        and has_strategy_ladder
        and has_contract_candidate_generator
        and (runtime_counts_target_candidates or not has_target_band)
    )
    if single_domain_contract_verified:
        family_status = "SINGLE_DOMAIN_LADDER_VERIFIED"
    elif explicit_lane and runtime_counts_target_candidates and runtime_has_fallback_reason and not exact_stop_still_bool_selected:
        family_status = "FIX_VERIFIED"
    else:
        family_status = "REVIEW_NEEDED"
    expected = config.get("expected_status")
    return {
        "family_id": family_id,
        "contract": str(contract_path.relative_to(ROOT)),
        "runtime": str(runtime_path.relative_to(ROOT)),
        "has_target_band": has_target_band,
        "explicit_target_band_candidate_lane": explicit_lane,
        "single_domain_ladder_family": is_single_domain_ladder,
        "contract_strategy_ladder_present": has_strategy_ladder,
        "contract_candidate_generator_present": has_contract_candidate_generator,
        "runtime_counts_target_band_candidates": runtime_counts_target_candidates,
        "runtime_has_fallback_reason_or_specific_blocker": runtime_has_fallback_reason,
        "exact_stop_tied_to_target_band": exact_stop_tied_to_target,
        "exact_stop_still_uses_bool_selected_shortcut": exact_stop_still_bool_selected,
        "classification": family_status,
        "expected_status": expected,
        "expected_status_matches": family_status == expected,
        "target_band": contract.get("target_band") if has_target_band else None,
        "recommended_next_step": (
            "No action for this issue; combined active-fail fix is present."
            if family_status == "FIX_VERIFIED"
            else "Single-domain ladder already owns candidate generation and contract/exact-stop proof; keep in regression set."
            if family_status == "SINGLE_DOMAIN_LADDER_VERIFIED"
            else "Add explicit target-band/refinement proof or fallback proof before changing product behavior."
        ),
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Target-Band Candidate Lane Detailed Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Combined Fix Verification",
        "",
        f"- combined contract check: `{payload['combined_verification']['contract_check']['status']}`",
        f"- rescue seed proof: `{payload['combined_verification']['rescue_seed']['status']}`",
        f"- target-band selection proof: `{payload['combined_verification']['target_band_selection']['status']}`",
        "",
        "## Family Findings",
        "",
        "| Family | Classification | Explicit Lane | Contract Ladder | Counts Target Candidates | Exact Stop Shortcut |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["families"]:
        lines.append(
            "| {family} | {classification} | {lane} | {ladder} | {counts} | {shortcut} |".format(
                family=row["family_id"],
                classification=row["classification"],
                lane=row["explicit_target_band_candidate_lane"],
                ladder=row["contract_strategy_ladder_present"],
                counts=row["runtime_counts_target_band_candidates"],
                shortcut=row["exact_stop_still_uses_bool_selected_shortcut"],
            )
        )
    lines.extend(["", "## Review Needed", ""])
    review = [row for row in payload["families"] if row["classification"] == "REVIEW_NEEDED"]
    lines.extend(
        [
            f"- `{row['family_id']}`: {row['recommended_next_step']}"
            for row in review
        ]
        or ["- none"]
    )
    lines.extend(["", "## Output", "", f"- `{payload['artifact']}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    py_compile = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "design_brain/families/bending_and_shear_fail_govern/runtime.py",
            "design_brain/families/combined_bending_shear_fail.py",
            "design_brain/families/bending_fail_shear_overdesign_governs/runtime.py",
            "design_brain/families/shear_fail_bending_overdesign_governs/runtime.py",
            "design_brain/families/bending_and_shear_overdesign_govern/runtime.py",
            "design_brain/families/bending_fail_governs/runtime.py",
            "design_brain/families/shear_fail_governs/runtime.py",
            "design_brain/families/bending_overdesign_governs/runtime.py",
            "design_brain/families/shear_overdesign_governs/runtime.py",
            "tools/verification/families/target_band_candidate_lane_detailed_audit.py",
        ],
        timeout=60,
    )
    combined_verification = {
        "contract_check": _run([sys.executable, "tools/verification/families/bending_and_shear_fail_govern_contract_check.py"], timeout=60),
        "rescue_seed": _run([sys.executable, "tools/verification/design_guide_active_fail_rescue_seed_tier_snapshot.py"], timeout=90),
        "target_band_selection": _run([sys.executable, "tools/verification/design_guide_combined_fail_target_band_selection_snapshot.py"], timeout=90),
    }
    rows = [_classify_family(family_id, config) for family_id, config in FAMILIES.items()]
    mismatches = [row["family_id"] for row in rows if not row["expected_status_matches"]]
    review_needed = [row["family_id"] for row in rows if row["classification"] == "REVIEW_NEEDED"]
    combined_gates_pass = all(row["status"] == "PASS" for row in combined_verification.values())
    if py_compile["status"] == "PASS" and combined_gates_pass and not mismatches:
        status = "PASS_WITH_REVIEW" if review_needed else "PASS"
    else:
        status = "FAIL"
    artifact_path = ARTIFACT_DIR / f"target_band_candidate_lane_detailed_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"target_band_candidate_lane_detailed_audit_{stamp}.md"
    payload = {
        "schema": "target_band_candidate_lane_detailed_audit.v1",
        "status": status,
        "py_compile": py_compile,
        "combined_verification": combined_verification,
        "families": rows,
        "expected_status_mismatches": mismatches,
        "review_needed_families": review_needed,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status in {"PASS", "PASS_WITH_REVIEW"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
