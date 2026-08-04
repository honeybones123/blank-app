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


def _prime_session() -> None:
    import streamlit as st

    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)
    st.session_state["support_type"] = "Simply supported"
    st.session_state["defl_support_type"] = "Simply supported"
    st.session_state["actions_mode"] = "manual"


def _run_case(state: dict[str, Any]) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    _prime_session()
    legacy_crack = legacy_inputs_page._build_crack_pack_from_state(dict(state))
    legacy_deflection = legacy_inputs_page._build_deflection_pack_from_state(dict(state))

    _prime_session()
    bridge_crack = bridge._build_crack_pack_from_state_for_app_bridge(dict(state))
    bridge_deflection = bridge._build_deflection_pack_from_state_for_app_bridge(dict(state))

    return {
        "crack_match": legacy_crack == bridge_crack,
        "deflection_match": legacy_deflection == bridge_deflection,
        "legacy_crack": legacy_crack,
        "bridge_crack": bridge_crack,
        "legacy_deflection": legacy_deflection,
        "bridge_deflection": bridge_deflection,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    base = {
        "sec_shape": "RECT",
        "b": 300,
        "D": 600,
        "cover_bot": 40,
        "cover_side": 40,
        "rowgap_bot": 60,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
        "fc": 32,
        "Ec": 30000,
        "Es": 200000,
        "fsy": 500,
        "Ast_top": 450,
        "sls_Mstar": 145,
        "sls_Vstar": 60,
        "uls_Mstar": 260,
        "g_udl_kNm_per_m": 8,
        "q_udl_kNm_per_m": 5,
        "psi_udl": 0.4,
        "defl_limit_ratio": 250,
        "span_L_m": 6.0,
        "wmax_char_limit": 0.3,
        "crack_member_type": "Primarily flexure",
        "crack_k1": 0.8,
        "crack_k2": 0.5,
    }
    cases = {
        "missing_bottom_reo": _run_case(
            {
                **base,
                "db_bot_1": 0,
                "db_bot_2": 0,
                "bot1_count": 0,
                "bot2_count": 0,
                "Ast_bot": 0,
            }
        ),
        "rect_single_row": _run_case(
            {
                **base,
                "db_bot_1": 20,
                "db_bot_2": 20,
                "bot1_count": 3,
                "bot2_count": 0,
            }
        ),
        "rect_two_rows": _run_case(
            {
                **base,
                "db_bot_1": 20,
                "db_bot_2": 16,
                "bot1_count": 3,
                "bot2_count": 2,
                "sls_Mstar": 190,
                "span_L_m": 7.5,
            }
        ),
        "t_section_width": _run_case(
            {
                **base,
                "sec_shape": "T",
                "b": 700,
                "bw": 250,
                "db_bot_1": 24,
                "db_bot_2": 20,
                "bot1_count": 4,
                "bot2_count": 2,
            }
        ),
    }
    checks = {
        "all_crack_cases_match_legacy": all(case["crack_match"] for case in cases.values()),
        "all_deflection_cases_match_legacy": all(case["deflection_match"] for case in cases.values()),
    }
    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["crack_pack_no_old_page_delegate"] = (
        "_legacy_inputs_page._build_crack_pack_from_state" not in bridge_source
    )
    checks["deflection_pack_no_old_page_delegate"] = (
        "_legacy_inputs_page._build_deflection_pack_from_state" not in bridge_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_candidate_serviceability_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_candidate_serviceability_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_candidate_serviceability_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Candidate Serviceability Parity",
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
