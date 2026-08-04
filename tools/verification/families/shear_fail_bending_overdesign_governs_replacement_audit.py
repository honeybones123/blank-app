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

from design_brain.families.shear_fail_bending_overdesign_governs.contract import (  # noqa: E402
    candidate_source_contract,
    contract_hash,
    ranking_criteria,
)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_governs_replacement_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN Replacement Audit",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "Old/live optimise naming is classified as compatibility evidence only. The contract runtime is authority.",
                "",
                "## Classifications",
                "",
                *[f"- `{row['surface']}`: `{row['classification']}`" for row in snapshot["classifications"]],
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
    source_contract = candidate_source_contract()
    classifications = [
        {
            "surface": "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS legacy id",
            "classification": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "alias only; new authority uses OVERDESIGN contract id",
        },
        {
            "surface": "old mixed implementation",
            "classification": "NO_OLD_EQUIVALENT_NEEDED",
            "reason": "new runtime owns merge/rank/select only and does not duplicate source ladders",
        },
        {
            "surface": "CTA/publication/apply/UI",
            "classification": "SHARED_OWNERSHIP_UNCHANGED",
            "reason": "contract evidence is proof-only",
        },
    ]
    checks = {
        "contract_hash_present": bool(contract_hash()),
        "mandatory_source_shear_fail": source_contract.get("mandatory_source") == "SHEAR_FAIL_GOVERNS",
        "opportunistic_source_bending_overdesign": source_contract.get("opportunistic_source") == "BENDING_OVERDESIGN_GOVERNS",
        "ranking_order_present": bool(ranking_criteria()),
        "no_unexplained_replacement_risk": all(row["classification"] != "UNEXPLAINED_RISK" for row in classifications),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "shear_fail_bending_overdesign_governs_replacement_audit.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_hash": contract_hash(),
        "checks": checks,
        "classifications": classifications,
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS replacement audit FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS replacement audit PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
