"""Verify app bridge auto-candidate evaluation no longer calls the old page shim."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _base_state() -> dict[str, Any]:
    return {
        "sec_shape": "RECT",
        "b": 300.0,
        "D": 600.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "Es": 200000.0,
        "Ec": 30000.0,
        "cover_bot": 40.0,
        "cover_side": 40.0,
        "rowgap_bot": 60.0,
        "uls_Mstar": 210.0,
        "uls_Vstar": 260.0,
        "sls_Mstar": 150.0,
        "sls_Vstar": 120.0,
        "bot1_count": 4,
        "bot2_count": 0,
        "db_bot_1": 20,
        "db_bot_2": 20,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
        "phi_b": 0.8,
        "phi_shear": 0.75,
        "d_g": 20.0,
        "k_v_method": "General epsilonx-based (Cl. 8.2.4.2)",
        "k_d_option": "None (no ducts in web)",
        "wmax_char_limit": 0.3,
        "crack_member_type": "Primarily flexure",
        "crack_k1": 0.8,
        "crack_k2": 0.5,
        "eps_cs_total_micro": 300.0,
        "span_L_m": 6.0,
        "defl_limit_ratio": 250.0,
        "g_udl_kNm_per_m": 10.0,
        "q_udl_kNm_per_m": 5.0,
        "psi_udl": 0.4,
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "seed",
            "state": _base_state(),
            "updates": None,
            "source": "app_bridge_candidate_seed",
            "label": None,
            "action_type": None,
        },
        {
            "name": "geometry_update",
            "state": _base_state(),
            "updates": {"D": 650.0, "b": 350.0},
            "source": "app_bridge_candidate_geometry",
            "label": "Geometry trial",
            "action_type": "increase_depth",
        },
        {
            "name": "shear_update",
            "state": _base_state(),
            "updates": {"s_lig": 150.0},
            "source": "app_bridge_candidate_shear",
            "label": "Shear trial",
            "action_type": "reduce_link_spacing",
        },
    ]


def _reset_cache() -> None:
    try:
        from state_and_helpers import reset_rerun_pure_caches

        reset_rerun_pure_caches()
    except Exception:
        pass


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    import inputs_page
    import inputs_page_app_contract_bridge as bridge

    _reset_cache()
    old = inputs_page._evaluate_auto_design_candidate(
        dict(case["state"]),
        updates=None if case["updates"] is None else dict(case["updates"]),
        source=case["source"],
        label=case["label"],
        action_type=case["action_type"],
    )
    _reset_cache()
    new = bridge._evaluate_auto_design_candidate_for_app_bridge(
        dict(case["state"]),
        updates=None if case["updates"] is None else dict(case["updates"]),
        source=case["source"],
        label=case["label"],
        action_type=case["action_type"],
    )
    return {
        "name": case["name"],
        "old": old,
        "new": new,
        "matches": _stable(old) == _stable(new),
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    bridge_source = BRIDGE_PATH.read_text(encoding="utf-8", errors="replace")
    cases = [_run_case(case) for case in _cases()]
    checks = {
        "bridge_helper_found": "def _evaluate_auto_design_candidate_for_app_bridge(" in bridge_source,
        "legacy_page_candidate_bridge_removed": "_legacy_inputs_page._evaluate_auto_design_candidate(" not in bridge_source,
        "all_cases_match": all(case["matches"] for case in cases),
    }
    payload = {
        "schema": "inputs_page_app_bridge_auto_candidate_evaluation_cutover.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "cases": [
            {
                "name": case["name"],
                "matches": case["matches"],
                "old_summary": {
                    "source": (case["old"] or {}).get("source") if isinstance(case["old"], dict) else None,
                    "label": (case["old"] or {}).get("label") if isinstance(case["old"], dict) else None,
                    "action_type": (case["old"] or {}).get("action_type") if isinstance(case["old"], dict) else None,
                    "is_compliant": (case["old"] or {}).get("is_compliant") if isinstance(case["old"], dict) else None,
                    "worst_util": (case["old"] or {}).get("worst_util") if isinstance(case["old"], dict) else None,
                    "fail_count": (case["old"] or {}).get("fail_count") if isinstance(case["old"], dict) else None,
                },
                "new_summary": {
                    "source": (case["new"] or {}).get("source") if isinstance(case["new"], dict) else None,
                    "label": (case["new"] or {}).get("label") if isinstance(case["new"], dict) else None,
                    "action_type": (case["new"] or {}).get("action_type") if isinstance(case["new"], dict) else None,
                    "is_compliant": (case["new"] or {}).get("is_compliant") if isinstance(case["new"], dict) else None,
                    "worst_util": (case["new"] or {}).get("worst_util") if isinstance(case["new"], dict) else None,
                    "fail_count": (case["new"] or {}).get("fail_count") if isinstance(case["new"], dict) else None,
                },
            }
            for case in cases
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_auto_candidate_evaluation_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_auto_candidate_evaluation_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Auto Candidate Evaluation Cutover",
                "",
                f"Status: {payload['status']}",
                "",
                "## Checks",
                *[f"- `{name}`: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "## Decision",
                (
                    "APP_BRIDGE_AUTO_CANDIDATE_EVALUATION_CUTOVER_PROVEN"
                    if payload["status"] == "PASS"
                    else "APP_BRIDGE_AUTO_CANDIDATE_EVALUATION_CUTOVER_NOT_PROVEN"
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["status"] != "PASS":
        failed = [name for name, passed in checks.items() if not passed]
        print("failed_checks=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
