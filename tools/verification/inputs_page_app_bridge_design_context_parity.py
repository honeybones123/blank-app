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


def _guidance_snapshot_factory(extra: dict[str, Any] | None = None):
    def guidance_snapshot(state: dict | None = None) -> dict:
        out = {
            "uls_Mstar": 220,
            "uls_Vstar": 110,
            "uls_Nstar": 0,
            "Mu_star": 220,
            "Vu_star": 110,
            "N_star": 0,
            "sls_Mstar": 150,
            "sls_Vstar": 80,
            "Tu_star": 0,
            "P_star": 0,
            "loads_edit_mode": "ULS",
            "actions_source": "Manual design actions (inputs below)",
        }
        out.update(dict(extra or {}))
        out.update(dict(state or {}))
        return out

    return guidance_snapshot


def _run_actions_case(state: dict[str, Any], actions: dict[str, Any] | None) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    guidance_snapshot = _guidance_snapshot_factory()
    originals = {
        "legacy_guidance": legacy_inputs_page._guidance_state_snapshot,
        "bridge_guidance": bridge._guidance_state_snapshot_for_summary_bridge,
    }
    try:
        legacy_inputs_page._guidance_state_snapshot = guidance_snapshot
        bridge._guidance_state_snapshot_for_summary_bridge = guidance_snapshot
        legacy_state = legacy_inputs_page._state_with_resolved_design_actions(dict(state), actions)
        bridge_state = bridge._state_with_resolved_design_actions_for_app_bridge(dict(state), actions)
        legacy_context = legacy_inputs_page._build_design_actions_context(dict(state))
        bridge_context = bridge._build_design_actions_context_for_app_bridge(dict(state))
    finally:
        legacy_inputs_page._guidance_state_snapshot = originals["legacy_guidance"]
        bridge._guidance_state_snapshot_for_summary_bridge = originals["bridge_guidance"]

    return {
        "state_match": legacy_state == bridge_state,
        "context_match": legacy_context == bridge_context,
        "legacy_state": legacy_state,
        "bridge_state": bridge_state,
        "legacy_context": legacy_context,
        "bridge_context": bridge_context,
    }


def _run_truth_case(state: dict[str, Any] | None) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    legacy_value = legacy_inputs_page._stage3_final_published_shear_truth_bundle(state)
    bridge_value = bridge._stage3_final_published_shear_truth_bundle_for_app_bridge(state)
    return {
        "match": legacy_value == bridge_value,
        "legacy": legacy_value,
        "bridge": bridge_value,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    action_cases = {
        "default_actions": _run_actions_case(
            {
                "uls_Mstar": 240,
                "uls_Vstar": 130,
                "sls_Mstar": 155,
                "sls_Vstar": 88,
            },
            None,
        ),
        "explicit_actions": _run_actions_case(
            {
                "uls_Mstar": 240,
                "uls_Vstar": 130,
                "sls_Mstar": 155,
                "sls_Vstar": 88,
                "uls_Mstar_pos_manual": 240,
                "uls_Mstar_neg_manual": 25,
            },
            {
                "Mu": 260,
                "Vu": 140,
                "Nu": 5,
                "SLS_M": 160,
                "SLS_V": 90,
                "Tu": 2,
                "Pu": 3,
                "signature": (("case", "explicit"),),
            },
        ),
    }
    truth_cases = {
        "none_state": _run_truth_case(None),
        "populated_state": _run_truth_case(
            {
                "shear_truth_status": "PASS",
                "shear_truth_reason": "ok",
                "final_shear_truth_resolved": True,
                "published_result_spacing_mm": 200,
                "_final_shear_truth_normalized_source": "test",
                "_final_shear_truth_normalized_latest": {"status": "PASS"},
                "ignored": "not exported",
            }
        ),
    }
    checks = {
        "all_action_states_match_legacy": all(case["state_match"] for case in action_cases.values()),
        "all_action_contexts_match_legacy": all(
            case["context_match"] for case in action_cases.values()
        ),
        "all_truth_bundles_match_legacy": all(case["match"] for case in truth_cases.values()),
    }
    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["design_context_helpers_do_not_delegate_to_old_page"] = all(
        needle not in bridge_source
        for needle in (
            "_legacy_inputs_page._build_design_actions_context",
            "_legacy_inputs_page._state_with_resolved_design_actions",
            "_legacy_inputs_page.build_bending_check_rows_from_state",
            "_legacy_inputs_page.build_shear_check_rows_from_state",
            "_legacy_inputs_page._stage3_final_published_shear_truth_bundle",
        )
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_design_context_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "action_cases": action_cases,
        "truth_cases": truth_cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_design_context_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_design_context_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Design Context Parity",
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
