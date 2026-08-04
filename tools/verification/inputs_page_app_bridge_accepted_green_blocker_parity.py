from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _valid_blocker() -> dict[str, Any]:
    return {
        "family": "shear",
        "current_util": 0.62,
        "threshold": 0.85,
        "attempted_candidate_count": 3,
        "best_rejected_candidate_id": "local_cleanup:shear:abc",
        "attempted_updates": {"s_lig": 250},
        "failed_check_name": "shear capacity",
        "failed_check_status": "FAIL",
        "failed_check_util": 1.04,
        "failed_check_demand": 180,
        "failed_check_capacity_or_limit": 173,
        "reason": "Reducing links below this point fails shear capacity.",
    }


def _sample_blockers() -> list[Any]:
    valid = _valid_blocker()
    alias_capacity = dict(valid)
    alias_capacity.pop("failed_check_demand")
    alias_capacity.pop("failed_check_capacity_or_limit")
    alias_capacity["demand"] = 180
    alias_capacity["capacity_or_limit"] = 173

    missing_reason = dict(valid)
    missing_reason["reason"] = ""

    generic_reason = dict(valid)
    generic_reason["reason"] = "candidate failed"

    missing_updates = dict(valid)
    missing_updates["attempted_updates"] = {}

    alt_reason_field = dict(valid)
    alt_reason_field.pop("reason")
    alt_reason_field["why_reduction_would_hurt_other_design_elements"] = (
        "Capacity would fall below demand."
    )

    return [
        None,
        {},
        valid,
        alias_capacity,
        missing_reason,
        generic_reason,
        missing_updates,
        alt_reason_field,
    ]


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, blocker in enumerate(_sample_blockers()):
        legacy_value = bool(legacy_inputs_page._accepted_green_exact_blocker_is_valid(blocker))
        bridge_value = bool(bridge._accepted_green_exact_blocker_is_valid(blocker))
        match = legacy_value == bridge_value
        rows.append(
            {
                "index": index,
                "match": match,
                "legacy": legacy_value,
                "bridge": bridge_value,
            }
        )
        if not match:
            failures.append(f"sample_{index}_accepted_green_blocker_mismatch")

    payload = {
        "audit": "inputs_page_app_bridge_accepted_green_blocker_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "samples": rows,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_accepted_green_blocker_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_accepted_green_blocker_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Accepted Green Blocker Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Samples",
                "",
                *(f"- sample `{row['index']}` match: `{row['match']}`" for row in rows),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
