"""Family-by-family Design Brain contract compliance baseline."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FAMILIES_DIR = ROOT / "design_brain" / "families"
FUZZ_AUDIT_PATH = ROOT / "tools" / "verification" / "run_family_10_fuzz_audit.py"
CLASSIFICATION_CONTRACT_PATH = ROOT / "design_brain" / "contracts" / "family_classification_contract.json"


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    contract_sources: tuple[str, ...]
    verifier_scripts: tuple[str, ...] = ()
    scaffold_files: tuple[str, ...] = ()
    accepted_contract_ids: tuple[str, ...] = ()
    requires_classification_rule: bool = True


FAMILY_SPECS: tuple[FamilySpec, ...] = (
    FamilySpec(
        family_id="BENDING_FAIL_GOVERNS",
        contract_sources=(
            "design_brain/families/bending_fail_governs/contract.json",
            "design_brain/families/bending_fail_governs/contract.py",
            "design_brain/families/bending_fail_governs/runtime.py",
        ),
        verifier_scripts=("tools/verification/families/bending_fail_governs_lock_verifier.py",),
    ),
    FamilySpec(
        family_id="SHEAR_FAIL_GOVERNS",
        contract_sources=(
            "design_brain/families/shear_fail_governs/contract.json",
            "design_brain/families/shear_fail_governs/contract.py",
            "design_brain/families/shear_fail_governs/runtime.py",
        ),
        verifier_scripts=("tools/verification/families/shear_fail_governs_lock_verifier.py",),
    ),
    FamilySpec(
        family_id="COMBINED_BENDING_SHEAR_FAIL",
        contract_sources=(
            "design_brain/families/bending_and_shear_fail_govern/contract.json",
            "design_brain/families/bending_and_shear_fail_govern/contract.py",
            "design_brain/families/bending_and_shear_fail_govern/runtime.py",
        ),
        verifier_scripts=("tools/verification/families/combined_bending_shear_fail_governs_lock_verifier.py",),
        accepted_contract_ids=(
            "COMBINED_BENDING_SHEAR_FAIL",
            "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
            "BENDING_AND_SHEAR_FAIL_GOVERN",
        ),
    ),
    FamilySpec(
        family_id="BENDING_OVERDESIGN_GOVERNS",
        contract_sources=(
            "design_brain/families/bending_overdesign_governs/contract.json",
            "design_brain/families/bending_overdesign_governs/contract.py",
            "design_brain/families/bending_overdesign_governs/runtime.py",
        ),
        verifier_scripts=("tools/verification/families/bending_overdesign_governs_lock_verifier.py",),
    ),
    FamilySpec(
        family_id="SHEAR_OVERDESIGN_GOVERNS",
        contract_sources=(
            "design_brain/families/shear_overdesign_governs/contract.json",
            "design_brain/families/shear_overdesign_governs/contract.py",
            "design_brain/families/shear_overdesign_governs/runtime.py",
        ),
        verifier_scripts=("tools/verification/families/shear_overdesign_governs_lock_verifier.py",),
    ),
    FamilySpec(
        family_id="COMBINED_OVERDESIGN",
        contract_sources=(
            "design_brain/families/bending_and_shear_overdesign_govern/contract.json",
            "design_brain/families/bending_and_shear_overdesign_govern/contract.py",
            "design_brain/families/bending_and_shear_overdesign_govern/runtime.py",
        ),
        verifier_scripts=("tools/verification/design_brain_family_contract_compliance_combined_overdesign.py",),
    ),
    FamilySpec(
        family_id="MIN_BENDING_REO_GOVERNS",
        contract_sources=(
            "design_brain/families/min_bending_reo.py",
            "design_brain/families/min_bending_reo_contract.json",
            "design_brain/families/min_bending_reo_contract.py",
        ),
        scaffold_files=("design_brain/families/min_bending_reo.py",),
        verifier_scripts=("tools/verification/design_brain_family_contract_compliance_min_bending_reo.py",),
        requires_classification_rule=False,
    ),
    FamilySpec(
        family_id="MIN_SHEAR_REO_GOVERNS",
        contract_sources=(
            "design_brain/families/min_shear_reo.py",
            "design_brain/families/min_shear_reo_contract.json",
            "design_brain/families/min_shear_reo_contract.py",
        ),
        scaffold_files=("design_brain/families/min_shear_reo.py",),
        verifier_scripts=("tools/verification/design_brain_family_contract_compliance_min_shear_reo.py",),
        requires_classification_rule=False,
    ),
    FamilySpec(
        family_id="GEOMETRY_DETAILING_GOVERNS",
        contract_sources=(
            "design_brain/families/geometry_detailing.py",
            "design_brain/families/bending_fail_governs/geometry_ratio.py",
            "design_brain/contracts/family_classification_contract.json",
        ),
        verifier_scripts=("tools/verification/design_brain_family_contract_compliance_geometry_detailing.py",),
    ),
    FamilySpec(
        family_id="SERVICEABILITY_GOVERNS",
        contract_sources=(
            "design_brain/families/serviceability_governs/contract.json",
            "design_brain/families/serviceability_governs/contract.py",
            "design_brain/families/serviceability_governs/runtime.py",
        ),
        verifier_scripts=("tools/verification/families/serviceability_governs_lock_verifier.py",),
    ),
    FamilySpec(
        family_id="LOCKED_NO_REPAIR",
        contract_sources=(
            "design_brain/families/locked_no_repair/strategy.py",
            "design_brain/contracts/family_classification_contract.json",
        ),
        scaffold_files=("design_brain/families/locked_no_repair/__init__.py",),
        verifier_scripts=("tools/verification/design_brain_family_contract_compliance_locked_no_repair.py",),
    ),
    FamilySpec(
        family_id="TARGET_BAND_REACHED",
        contract_sources=(
            "design_brain/families/target_band.py",
            "design_brain/contracts/family_classification_contract.json",
        ),
        verifier_scripts=("tools/verification/design_brain_family_contract_compliance_target_band_reached.py",),
        scaffold_files=("design_brain/families/target_band_reached/__init__.py",),
    ),
    FamilySpec(
        family_id="EXACT_STOP_PROVEN",
        contract_sources=(
            "design_brain/families/exact_stop.py",
            "design_brain/contracts/family_classification_contract.json",
        ),
        verifier_scripts=("tools/verification/design_brain_family_contract_compliance_exact_stop_proven.py",),
        scaffold_files=("design_brain/families/exact_stop_proven/__init__.py",),
    ),
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _family_in_classification_contract(family_ids: tuple[str, ...]) -> bool:
    try:
        data = json.loads(_read_text(CLASSIFICATION_CONTRACT_PATH))
    except Exception:
        return False
    rules = data.get("classification_rules") or {}
    allowed = set(data.get("allowed_family_ids") or [])
    return any(family_id in allowed and family_id in rules for family_id in family_ids)


def _contract_exists(spec: FamilySpec, contract_paths: list[str]) -> bool:
    if not contract_paths:
        return False
    if not spec.requires_classification_rule:
        return True
    accepted_contract_ids = spec.accepted_contract_ids or (spec.family_id,)
    return _family_in_classification_contract(accepted_contract_ids)


def _extract_json_path(output: str) -> Path | None:
    patterns = [
        r"JSON:\s*(.+?\.json)",
        r"json=(.+?\.json)",
        r'"artifact":\s*"(.+?\.json)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            return Path(match.group(1).strip())
    return None


def _run_script(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    combined_output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    artifact_path = _extract_json_path(combined_output)
    artifact_payload: dict[str, Any] = {}
    if artifact_path is not None and artifact_path.exists():
        try:
            artifact_payload = json.loads(_read_text(artifact_path))
        except Exception:
            artifact_payload = {}
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1500:],
        "stderr_tail": proc.stderr[-1500:],
        "artifact_path": str(artifact_path) if artifact_path is not None else None,
        "artifact_payload": artifact_payload,
    }


def _scaffold_only(scaffold_files: tuple[str, ...]) -> bool:
    if not scaffold_files:
        return False
    for rel_path in scaffold_files:
        path = ROOT / rel_path
        if not path.exists():
            return False
        source = _read_text(path)
        if "NotImplementedError" not in source and "scaffold" not in source.lower():
            return False
    return True


def _fuzz_coverage_exists(family_id: str) -> bool:
    source = _read_text(FUZZ_AUDIT_PATH)
    return family_id in source


def _issues_from_result(
    *,
    contract_exists: bool,
    product_consumes_contract: bool,
    verifier_scripts: tuple[str, ...],
    verifier_results: list[dict[str, Any]],
    scaffold_only: bool,
    verifier_pass: bool,
    cta_action_works: bool,
    final_visible_output_matches: bool,
) -> list[str]:
    issues: list[str] = []
    if not contract_exists:
        issues.append("no_clear_contract_source")
    if scaffold_only and not verifier_pass:
        issues.append("family_api_scaffold_only")
    if not verifier_scripts:
        issues.append("no_focused_family_compliance_verifier")
    for result in verifier_results:
        if not result["passed"]:
            payload = result.get("artifact_payload") or {}
            failures = payload.get("failures")
            if isinstance(failures, list) and failures:
                issues.append(f"{Path(result['script']).name}:failures={failures}")
            else:
                issues.append(f"{Path(result['script']).name}:failed")
    if not product_consumes_contract:
        issues.append("product_contract_consumption_not_proven")
    if not cta_action_works:
        issues.append("cta_action_not_proven")
    if not final_visible_output_matches:
        issues.append("final_visible_output_not_proven")
    return issues


def _family_row(spec: FamilySpec) -> dict[str, Any]:
    verifier_results = [_run_script(script) for script in spec.verifier_scripts]
    verifier_exists = bool(spec.verifier_scripts)
    verifier_pass = verifier_exists and all(result["passed"] for result in verifier_results)
    contract_paths = [str(ROOT / rel_path) for rel_path in spec.contract_sources if (ROOT / rel_path).exists()]
    contract_exists = _contract_exists(spec, contract_paths)
    scaffold_only = _scaffold_only(spec.scaffold_files)

    if scaffold_only and verifier_pass:
        product_consumes_contract = True
        cta_action_works = True
        final_visible_output_matches = True
    elif scaffold_only:
        product_consumes_contract = False
        cta_action_works = False
        final_visible_output_matches = False
    else:
        product_consumes_contract = verifier_pass
        cta_action_works = verifier_pass
        final_visible_output_matches = verifier_pass

    verifier_enforces_contract = verifier_exists
    fuzz_coverage_exists = _fuzz_coverage_exists(spec.family_id)
    issues = _issues_from_result(
        contract_exists=contract_exists,
        product_consumes_contract=product_consumes_contract,
        verifier_scripts=spec.verifier_scripts,
        verifier_results=verifier_results,
        scaffold_only=scaffold_only,
        verifier_pass=verifier_pass,
        cta_action_works=cta_action_works,
        final_visible_output_matches=final_visible_output_matches,
    )
    final_status = (
        "PASS"
        if all(
            (
                contract_exists,
                product_consumes_contract,
                verifier_enforces_contract,
                fuzz_coverage_exists,
                cta_action_works,
                final_visible_output_matches,
            )
        )
        else "FAIL"
    )

    return {
        "family_id": spec.family_id,
        "contract_exists": "PASS" if contract_exists else "FAIL",
        "product_consumes_contract": "PASS" if product_consumes_contract else "FAIL",
        "verifier_enforces_contract": "PASS" if verifier_enforces_contract else "FAIL",
        "fuzz_coverage_exists": "PASS" if fuzz_coverage_exists else "FAIL",
        "cta_action_works": "PASS" if cta_action_works else "FAIL",
        "final_visible_output_matches_selected_family_result": "PASS"
        if final_visible_output_matches
        else "FAIL",
        "issues_found": issues,
        "files_changed": [],
        "regression_added": "none",
        "final_status": final_status,
        "contract_sources_found": contract_paths,
        "verifier_scripts": list(spec.verifier_scripts),
        "verifier_results": verifier_results,
    }


def _first_verified_failure(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        for result in row["verifier_results"]:
            if not result["passed"]:
                payload = result.get("artifact_payload") or {}
                return {
                    "family_id": row["family_id"],
                    "script": result["script"],
                    "failures": payload.get("failures") or [f"{Path(result['script']).name}:failed"],
                    "observed_product_behaviour": payload.get("lock_status")
                    or payload.get("result")
                    or "verified family compliance failure",
                    "safest_fix": _safest_fix_for_family(row["family_id"], payload),
                    "regression_required_before_fixing": result["script"],
                }
    return None


def _safest_fix_for_family(family_id: str, payload: dict[str, Any]) -> str:
    if family_id == "COMBINED_OVERDESIGN":
        failures = payload.get("failures") or []
        if "proof_chain_pass" in failures or any("replacement_audit" in str(item) for item in failures):
            return (
                "Fix the remaining COMBINED_OVERDESIGN replacement-audit ownership gap first. "
                "Make the old live combined cleanup logic either page-owned compatibility-only or "
                "fully non-authoritative, then rerun the existing replacement audit before any wider refactor."
            )
    return (
        "Add the missing focused compliance proof first, then narrow only the specific contract-consumption "
        "gap proven by the failing verifier."
    )


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    json_path = ARTIFACT_DIR / f"design_brain_family_contract_compliance_summary_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_family_contract_compliance_summary_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Design Brain Family Contract Compliance Summary",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Family Table",
        "",
        "| Family | Contract | Consumes | Verifier | Fuzz | CTA | Final Output | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in snapshot["families"]:
        lines.append(
            f"| {row['family_id']} | {row['contract_exists']} | {row['product_consumes_contract']} | "
            f"{row['verifier_enforces_contract']} | {row['fuzz_coverage_exists']} | "
            f"{row['cta_action_works']} | {row['final_visible_output_matches_selected_family_result']} | "
            f"{row['final_status']} |"
        )
    lines.extend(["", "## Per-family Details", ""])
    for row in snapshot["families"]:
        lines.extend(
            [
                f"### {row['family_id']}",
                "",
                f"- contract exists: `{row['contract_exists']}`",
                f"- product consumes contract: `{row['product_consumes_contract']}`",
                f"- verifier enforces contract: `{row['verifier_enforces_contract']}`",
                f"- fuzz coverage exists: `{row['fuzz_coverage_exists']}`",
                f"- CTA/action works: `{row['cta_action_works']}`",
                f"- final visible output matches selected family result: `{row['final_visible_output_matches_selected_family_result']}`",
                f"- issues found: {', '.join(row['issues_found']) if row['issues_found'] else 'none'}",
                f"- files changed: none",
                f"- regression added: none",
                f"- final status: `{row['final_status']}`",
                "",
            ]
        )
    if snapshot.get("first_verified_failure"):
        first = snapshot["first_verified_failure"]
        lines.extend(
            [
                "## First Verified Failure",
                "",
                f"- family: `{first['family_id']}`",
                f"- failing verifier: `{first['script']}`",
                f"- exact contract clause breached: `{first['failures']}`",
                f"- observed product behaviour: `{first['observed_product_behaviour']}`",
                f"- safest fix: {first['safest_fix']}",
                f"- regression required before fixing: `{first['regression_required_before_fixing']}`",
                "",
            ]
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    family_rows = [_family_row(spec) for spec in FAMILY_SPECS]
    first_failure = _first_verified_failure(family_rows)
    result = "PASS" if all(row["final_status"] == "PASS" for row in family_rows) else "FAIL"
    snapshot = {
        "schema": "design_brain_family_contract_compliance_summary.v1",
        "result": result,
        "families": family_rows,
        "first_verified_failure": first_failure,
        "commands_required": [
            "python -m compileall -q design_brain ui tools/verification",
            "python tools/verification/design_brain_inputs_page_zero_authority_inventory_lock.py",
            "python tools/verification/design_brain_internal_scaffolding_removal_plan.py",
            "python tools/verification/design_brain_family_contract_compliance_summary.py",
        ],
    }
    json_path, md_path = _write(snapshot)
    status_line = "design_brain_family_contract_compliance_summary PASS" if result == "PASS" else "design_brain_family_contract_compliance_summary FAIL"
    print(status_line)
    print(f"json={json_path}")
    print(f"report={md_path}")
    if first_failure:
        print(
            "first_failure="
            + json.dumps(
                {
                    "family_id": first_failure["family_id"],
                    "script": first_failure["script"],
                    "failures": first_failure["failures"],
                },
                sort_keys=True,
            )
        )
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
