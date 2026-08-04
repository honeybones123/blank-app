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


def _run_shear_overlay_case(session_values: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    working_legacy = dict(base)
    working_bridge = dict(base)
    overlay_legacy: dict[str, Any] = {}
    overlay_bridge: dict[str, Any] = {}
    originals = {"legacy_st": legacy_inputs_page.st, "bridge_st": bridge.st}
    try:
        legacy_inputs_page.st = SimpleNamespace(session_state=dict(session_values))
        bridge.st = SimpleNamespace(session_state=dict(session_values))
        legacy_return = legacy_inputs_page._apply_active_page_shear_widget_mirror_overlay(
            working_legacy,
            dict(base),
            overlay_legacy,
        )
        bridge_return = bridge._apply_active_page_shear_widget_mirror_overlay_for_app_bridge(
            working_bridge,
            dict(base),
            overlay_bridge,
        )
    finally:
        legacy_inputs_page.st = originals["legacy_st"]
        bridge.st = originals["bridge_st"]
    return {
        "match": (
            legacy_return == bridge_return
            and working_legacy == working_bridge
            and overlay_legacy == overlay_bridge
        ),
        "legacy": {"return": legacy_return, "working": working_legacy, "overlay": overlay_legacy},
        "bridge": {"return": bridge_return, "working": working_bridge, "overlay": overlay_bridge},
    }


def _run_action_overlay_case(session_values: dict[str, Any], working: dict[str, Any]) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    working_legacy = dict(working)
    working_bridge = dict(working)
    overlay_legacy: dict[str, Any] = {}
    overlay_bridge: dict[str, Any] = {}

    def ux_noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    originals = {
        "legacy_ux": legacy_inputs_page.ux_probe_record,
        "bridge_ux": bridge.ux_probe_record,
    }
    try:
        legacy_inputs_page.ux_probe_record = ux_noop
        bridge.ux_probe_record = ux_noop
        legacy_return = legacy_inputs_page._overlay_current_design_action_results_for_summary(
            working_legacy,
            overlay_legacy,
            source_state=dict(session_values),
        )
        bridge_return = bridge._overlay_current_design_action_results_for_summary_for_app_bridge(
            working_bridge,
            overlay_bridge,
            source_state=dict(session_values),
        )
    finally:
        legacy_inputs_page.ux_probe_record = originals["legacy_ux"]
        bridge.ux_probe_record = originals["bridge_ux"]
    return {
        "match": (
            legacy_return == bridge_return
            and working_legacy == working_bridge
            and overlay_legacy == overlay_bridge
        ),
        "legacy": {"return": legacy_return, "working": working_legacy, "overlay": overlay_legacy},
        "bridge": {"return": bridge_return, "working": working_bridge, "overlay": overlay_bridge},
    }


def _run_normalized_truth_case(session_values: dict[str, Any], state: dict[str, Any] | None) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    originals = {"legacy_st": legacy_inputs_page.st, "bridge_st": bridge.st}
    try:
        legacy_inputs_page.st = SimpleNamespace(session_state=dict(session_values))
        bridge.st = SimpleNamespace(session_state=dict(session_values))
        legacy_return = legacy_inputs_page._overlay_current_normalized_shear_truth(state)
        bridge_return = bridge._overlay_current_normalized_shear_truth_for_app_bridge(state)
    finally:
        legacy_inputs_page.st = originals["legacy_st"]
        bridge.st = originals["bridge_st"]
    return {"match": legacy_return == bridge_return, "legacy": legacy_return, "bridge": bridge_return}


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    shear_cases = {
        "inputs_overlay": _run_shear_overlay_case(
            {
                "page_slug": "inputs",
                "inputs_s_lig": 180,
                "inputs_lig_d": 10,
                "inputs_lig_legs": 2,
            },
            {"s_lig": 200, "lig_d": 10, "lig_legs": 2},
        ),
        "inputs_stale_suppressed": _run_shear_overlay_case(
            {
                "page_slug": "inputs",
                "inputs_s_lig": 180,
                "inputs_lig_d": 10,
                "inputs_lig_legs": 2,
            },
            {"s_lig": 200, "lig_d": 0, "lig_legs": 0},
        ),
        "other_page_no_overlay": _run_shear_overlay_case(
            {"page_slug": "bending", "inputs_s_lig": 180},
            {"s_lig": 200, "lig_d": 10, "lig_legs": 2},
        ),
    }
    action_cases = {
        "action_result_overlay": _run_action_overlay_case(
            {"Mu_star": 260, "Vu_star": 140, "ignored": "no"},
            {"Mu_star": 240, "Vu_star": 120},
        ),
    }
    truth_cases = {
        "session_truth_overlay": _run_normalized_truth_case(
            {
                "shear_truth_status": "PASS",
                "final_shear_truth_resolved": True,
                "published_result_spacing_mm": 200,
            },
            {"shear_truth_status": "STALE", "b": 300},
        ),
        "empty_session": _run_normalized_truth_case({}, {"b": 300}),
    }
    checks = {
        "all_shear_overlay_cases_match_legacy": all(case["match"] for case in shear_cases.values()),
        "all_action_overlay_cases_match_legacy": all(
            case["match"] for case in action_cases.values()
        ),
        "all_normalized_truth_cases_match_legacy": all(case["match"] for case in truth_cases.values()),
    }
    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["summary_overlay_helpers_do_not_delegate_to_old_page"] = all(
        needle not in bridge_source
        for needle in (
            "_legacy_inputs_page._apply_active_page_shear_widget_mirror_overlay",
            "_legacy_inputs_page._overlay_current_design_action_results_for_summary",
            "_legacy_inputs_page._overlay_current_normalized_shear_truth",
        )
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_summary_overlay_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "shear_cases": shear_cases,
        "action_cases": action_cases,
        "truth_cases": truth_cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_summary_overlay_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_summary_overlay_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Summary Overlay Parity",
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
