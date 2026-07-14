"""Focused family contract compliance verifier for MIN_SHEAR_REO_GOVERNS."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.families.min_shear_reo_contract import (  # noqa: E402
    contract_hash,
    load_min_shear_reo_contract,
)


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def _latest(prefix: str) -> Path:
    candidates = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(prefix)
    return candidates[0]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    json_path = ARTIFACT_DIR / f"design_brain_family_contract_compliance_min_shear_reo_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_family_contract_compliance_min_shear_reo_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# MIN_SHEAR_REO_GOVERNS Family Contract Compliance",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    chooser_run = _run("tools/verification/family_chooser_classification_regression.py")
    mapping_run = _run("tools/verification/blocker_family_selected_state_mapping_snapshot.py")
    shear_owner_run = _run("tools/verification/families/shear_overdesign_governs_lock_verifier.py")
    combined_owner_run = _run("tools/verification/design_brain_family_contract_compliance_combined_overdesign.py")
    proof_chain = [chooser_run, mapping_run, shear_owner_run, combined_owner_run]

    contract = load_min_shear_reo_contract()
    classification_contract = _read_json(ROOT / "design_brain" / "contracts" / "family_classification_contract.json")
    mapping_artifact = _latest("blocker_family_selected_state_mapping")
    mapping_payload = _read_json(mapping_artifact)
    mapping_case = next(
        (
            case
            for case in mapping_payload.get("old_selected_states_found") or []
            if case.get("case_id") == "old_min_shear_reo_selected"
        ),
        {},
    )
    mapping_coverage = next(
        (
            row
            for row in mapping_payload.get("active_family_evidence_coverage") or []
            if row.get("case_id") == "old_min_shear_reo_selected"
        ),
        {},
    )

    chooser = classify_family_from_raw_flags(
        {"min_shear_reo_fail": True},
        evidence={"case_id": "minimum_shear_reo_maps_to_shear_overdesign_owner"},
    )
    selected_owner = chooser.get("selected_family_id")
    allowed_ids = set(classification_contract.get("allowed_family_ids") or [])
    priority_ids = set(classification_contract.get("classification_priority_order") or [])
    rules = set((classification_contract.get("classification_rules") or {}).keys())
    coverage_rows = list(mapping_coverage.get("active_family_evidence") or [])
    checks = {
        "compatibility_contract_loads": contract.get("contract_identity", {}).get("family_id") == "MIN_SHEAR_REO_GOVERNS",
        "compatibility_contract_hash_present": bool(contract_hash()),
        "classification_contract_excludes_legacy_family_id": (
            "MIN_SHEAR_REO_GOVERNS" not in allowed_ids
            and "MIN_SHEAR_REO_GOVERNS" not in priority_ids
            and "MIN_SHEAR_REO_GOVERNS" not in rules
        ),
        "chooser_maps_min_signal_to_owner_family": selected_owner == "SHEAR_OVERDESIGN_GOVERNS",
        "mapping_snapshot_records_legacy_to_owner_mapping": mapping_case.get("legacy_old_selected_state_mapped") is True,
        "mapping_snapshot_owner_evidence_complete": bool(coverage_rows)
        and all(row.get("evidence_exists") and row.get("cta_equivalent") for row in coverage_rows),
        "owner_families_match_contract": set(contract.get("final_selection_contract", {}).get("selected_owner_families") or [])
        == {"SHEAR_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN"},
        "shear_overdesign_owner_lock_pass": shear_owner_run["passed"],
        "combined_overdesign_owner_compliance_pass": combined_owner_run["passed"],
        "legacy_shell_not_product_driving": contract.get("product_driving") is False,
        "cta_and_final_output_owned_by_selected_owner": (
            contract.get("publication_contract", {}).get("cta_owner") == "selected_owner_family"
            and contract.get("publication_contract", {}).get("final_visible_output_owner") == "selected_owner_family"
        ),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_brain_family_contract_compliance_min_shear_reo.v1",
        "result": "PASS" if not failures else "FAIL",
        "family_id": "MIN_SHEAR_REO_GOVERNS",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "mapping_artifact": str(mapping_artifact),
        "selected_owner_family": selected_owner,
        "owner_coverage": coverage_rows,
        "product_behaviour_changed": False,
    }
    json_path, md_path = _write(snapshot)
    print(f"design_brain_family_contract_compliance_min_shear_reo {snapshot['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
