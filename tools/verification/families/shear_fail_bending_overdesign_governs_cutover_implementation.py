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

from design_brain.families.registry import family_strategy_for, normalise_governing_family  # noqa: E402
from design_brain.families.shear_fail_bending_overdesign_governs import (  # noqa: E402
    evaluate_shear_fail_bending_overdesign_governs,
)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_governs_cutover_implementation_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN Cutover Implementation",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Runtime Call",
                "",
                f"- family result hash: `{snapshot['family_call'].get('runtime_hash')}`",
                f"- public API status: `{snapshot['public_api'].get('status')}`",
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
    strategy = family_strategy_for("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS")
    family_call = strategy.contracted_mixed_ladder_result(  # type: ignore[union-attr]
        {"Vstar": 260.0, "phiVu": 210.0, "Mstar": 180.0, "phiMu": 360.0},
        shear_fail_candidates=(
            {"source_family_id": "SHEAR_FAIL_GOVERNS", "candidate_id": "shear_repair", "updates": {"s_lig": 125}},
        ),
        bending_overdesign_candidates=(
            {"source_family_id": "BENDING_OVERDESIGN_GOVERNS", "candidate_id": "bending_cleanup", "updates": {"bot1_count": 4}},
        ),
    )
    public_api = evaluate_shear_fail_bending_overdesign_governs(
        {
            "selected_family_id": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            "state": {"Vstar": 260.0, "phiVu": 210.0, "Mstar": 180.0, "phiMu": 360.0},
        }
    )
    checks = {
        "registry_returns_strategy": strategy is not None,
        "legacy_alias_normalises": normalise_governing_family("SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS")
        == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "family_call_runtime_driven": family_call.get("contract_runtime_driven") is True,
        "family_call_authority_matches": family_call.get("contract_runtime_authority")
        == "run_shear_fail_bending_overdesign_runtime",
        "family_call_has_runtime_hash": bool(family_call.get("runtime_hash")),
        "family_call_has_runtime_evidence": bool(family_call.get("candidate_source_proof"))
        and bool(family_call.get("ranking_evidence"))
        and bool(family_call.get("ownership_proof")),
        "public_api_runtime_authority": (
            (public_api.evidence or {}).get("contract_runtime_authority")
            == "run_shear_fail_bending_overdesign_runtime"
        ),
        "public_api_lock_proof": (public_api.lock_proof or {}).get("runtime_authority")
        == "run_shear_fail_bending_overdesign_runtime",
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "shear_fail_bending_overdesign_governs_cutover_implementation.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "family_call": family_call,
        "public_api": {
            "family_id": public_api.family_id,
            "status": public_api.status,
            "lock_proof": public_api.lock_proof,
            "evidence": public_api.evidence,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS cutover implementation FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True, default=str))
        return 1
    print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS cutover implementation PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
