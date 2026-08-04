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


def _sample_states() -> list[dict[str, Any]]:
    return [
        {},
        {
            "design_optimisation_goal": "balanced",
            "sec_shape": "RECT",
            "b": 300,
            "D": 600,
            "fc": 40,
            "fsy": 500,
            "uls_Mstar": 250,
            "uls_Vstar": 150,
            "uls_Nstar": 0,
            "Tu_star": 0,
            "bot_row_count": 1,
            "bot1_count": 3,
            "db_bot_1": 20,
            "bot2_count": 0,
            "db_bot_2": 0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 200,
        },
        {
            "design_optimisation_goal": "shallower_beam",
            "sec_shape": "T",
            "b": 450,
            "D": 500,
            "fc": 50,
            "fsy": 500,
            "uls_Mstar": 420,
            "uls_Vstar": 240,
            "uls_Nstar": -100,
            "Tu_star": 20,
            "bot_row_count": 2,
            "bot1_count": 4,
            "db_bot_1": 24,
            "bot2_count": 2,
            "db_bot_2": 20,
            "lig_d": 12,
            "lig_legs": 4,
            "s_lig": 150,
            "actions_uls": {"Vu": 240, "Tu": 20},
        },
        {
            "design_optimisation_goal": "unsupported_goal_falls_back",
            "sec_shape": "I",
            "b": "350",
            "D": "700",
            "fc": "32",
            "fsy": "500",
            "uls_Mstar": "300",
            "uls_Vstar": "180",
            "uls_Nstar": "10",
            "Tu_star": "5",
            "bot_row_count": "1",
            "bot1_count": "3",
            "db_bot_1": "20",
            "bot2_count": "",
            "db_bot_2": "",
            "lig_d": "10",
            "lig_legs": "2",
            "s_lig": "175",
        },
    ]


def main() -> int:
    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide.fingerprint import build_design_guide_fingerprint

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, state in enumerate(_sample_states()):
        legacy_fp = bridge._get_design_guide_fp(dict(state))
        bridge_fp = build_design_guide_fingerprint(dict(state))
        match = legacy_fp == bridge_fp
        rows.append(
            {
                "index": index,
                "match": match,
                "legacy": repr(legacy_fp),
                "bridge": repr(bridge_fp),
            }
        )
        if not match:
            failures.append(f"sample_{index}_fingerprint_mismatch")

    payload = {
        "audit": "inputs_page_app_bridge_design_guide_fp_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "samples": rows,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_design_guide_fp_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_design_guide_fp_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Design Guide Fingerprint Parity",
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
