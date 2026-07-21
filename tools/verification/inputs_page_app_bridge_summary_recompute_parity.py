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


def _run_case(state: dict[str, Any]) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    legacy_value = legacy_inputs_page._recompute_summary_local_derived_fields(dict(state))
    bridge_value = bridge._recompute_summary_local_derived_fields_for_app_bridge(dict(state))
    return {
        "match": legacy_value == bridge_value,
        "legacy": legacy_value,
        "bridge": bridge_value,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    base = {
        "b": 300,
        "D": 600,
        "cover_bot": 40,
        "lig_d": 10,
        "uls_Mstar": 240,
        "uls_Vstar": 120,
        "sls_Mstar": 150,
        "sls_Vstar": 70,
    }
    cases = {
        "no_bottom_rows": _run_case({**base, "db_bot_1": 0, "bot1_count": 0, "bot2_count": 0}),
        "single_row": _run_case({**base, "db_bot_1": 20, "bot1_count": 3, "bot2_count": 0}),
        "two_rows": _run_case(
            {
                **base,
                "db_bot_1": 20,
                "db_bot_2": 16,
                "bot1_count": 3,
                "bot2_count": 2,
                "uls_Mstar_pos_manual": 260,
                "uls_Mstar_neg_manual": 35,
            }
        ),
    }
    checks = {
        "all_recompute_cases_match_legacy": all(case["match"] for case in cases.values()),
        "two_rows_projects_bottom_area": cases["two_rows"]["bridge"].get("Ast_bot") is not None
        or "Ast_bot" in cases["two_rows"]["bridge"],
    }
    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["summary_recompute_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page._recompute_summary_local_derived_fields" not in bridge_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_summary_recompute_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_summary_recompute_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_summary_recompute_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Summary Recompute Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
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
