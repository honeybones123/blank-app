from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _sample_state() -> dict[str, Any]:
    return {
        "b": 300,
        "D": 600,
        "bot1_count": 3,
        "db_bot_1": 20,
        "bot2_count": 0,
        "db_bot_2": 0,
        "bot_row_count": 1,
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 20,
        "bot_row_2_bars": 0,
        "bot_row_2_dia": 0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }


def main() -> int:
    import inputs_page_app_contract_bridge as bridge
    import inputs_page_app_contracts
    from inputs_page_modules.session.local_cleanup_acceptance import (
        DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
    )

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    state = _sample_state()
    current_fp = bridge._local_cleanup_acceptance_fingerprint(dict(state))
    other_fp = bridge._local_cleanup_acceptance_fingerprint({**dict(state), "s_lig": 250})
    cases = [
        ("empty_session", {}, False),
        ("expected_fp_match", {"_design_guide_post_cleanup_acceptance_fp": current_fp}, True),
        ("accepted_set_match", {"_accepted_fps": {current_fp}}, True),
        ("accepted_set_nonmatch", {"_accepted_fps": {other_fp}}, False),
        ("acceptance_enabled", {"_design_guide_post_cleanup_acceptance_enabled": True}, False),
        (
            "direct_resolved_route",
            {
                inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY: {
                    "apply_direct_resolved_candidate": True
                }
            },
            False,
        ),
        (
            "resolved_payload_route",
            {
                inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY: {
                    "apply_used_resolved_candidate_payload": True
                }
            },
            False,
        ),
        (
            "nonmatching_expected_fp",
            {"_design_guide_post_cleanup_acceptance_fp": other_fp},
            False,
        ),
    ]

    original_bridge_st = bridge.st
    shared_storage_identity_match = bridge._DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS is DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
    original_accepted = set(DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS)
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        for index, (name, session_values, expected) in enumerate(cases):
            session = dict(session_values)
            accepted_fps = set(session.pop("_accepted_fps", set()))
            DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.clear()
            DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.update(accepted_fps)
            fake_st = SimpleNamespace(session_state=session)
            bridge.st = fake_st
            bridge_value = bool(bridge._local_cleanup_post_apply_acceptance_matches(dict(state)))
            rows.append(
                {
                    "index": index,
                    "case": name,
                    "bridge": bridge_value,
                    "expected": expected,
                    "contract_pass": bridge_value is expected,
                }
            )
            if bridge_value is not expected:
                failures.append(
                    f"{name}_local_cleanup_acceptance_contract_drift:"
                    f"expected={expected}:actual={bridge_value}"
                )
    finally:
        bridge.st = original_bridge_st
        DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.clear()
        DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.update(original_accepted)

    if not shared_storage_identity_match:
        failures.append("shared_storage_identity_mismatch")

    payload = {
        "audit": "inputs_page_app_bridge_local_cleanup_acceptance_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "samples": rows,
        "shared_storage_identity_match": shared_storage_identity_match,
        "storage_note": "bridge and old page read the same session-module accepted-fingerprint set",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_local_cleanup_acceptance_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_local_cleanup_acceptance_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Local Cleanup Acceptance Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Samples",
                "",
                *(
                    f"- `{row['case']}` contract: `{row['contract_pass']}` "
                    f"(expected `{row['expected']}`, actual `{row['bridge']}`)"
                    for row in rows
                ),
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
