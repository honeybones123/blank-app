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


class FakeSession(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def _run_summary_case(
    *,
    name: str,
    session_values: dict[str, Any],
    shared_only: bool,
) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    originals = {
        "legacy_st": legacy_inputs_page.st,
        "bridge_st": bridge.st,
        "legacy_shared": legacy_inputs_page._shared_state_snapshot,
        "bridge_shared": bridge._shared_state_snapshot_for_summary_bridge,
        "legacy_guidance": legacy_inputs_page._guidance_state_snapshot,
        "bridge_guidance": bridge._guidance_state_snapshot_for_summary_bridge,
        "legacy_shared_only": legacy_inputs_page._inputs_summary_should_use_shared_only,
        "bridge_shared_only": bridge._inputs_summary_should_use_shared_only_for_app_bridge,
        "legacy_shear_overlay": legacy_inputs_page._apply_active_page_shear_widget_mirror_overlay,
        "bridge_shear_overlay": bridge._apply_active_page_shear_widget_mirror_overlay_for_app_bridge,
        "legacy_action_overlay": legacy_inputs_page._overlay_current_design_action_results_for_summary,
        "bridge_action_overlay": bridge._overlay_current_design_action_results_for_summary_for_app_bridge,
        "legacy_mirrors": legacy_inputs_page.build_legacy_longitudinal_mirrors_from_rows,
        "bridge_mirrors": bridge._build_legacy_longitudinal_mirrors_from_rows_for_app_bridge,
        "legacy_recompute": legacy_inputs_page._recompute_summary_local_derived_fields,
        "bridge_recompute": bridge._recompute_summary_local_derived_fields_for_app_bridge,
        "legacy_truth": legacy_inputs_page._overlay_current_normalized_shear_truth,
        "bridge_truth": bridge._overlay_current_normalized_shear_truth_for_app_bridge,
        "legacy_ux": legacy_inputs_page.ux_probe_record,
        "bridge_ux": bridge.ux_probe_record,
    }
    base_state = {
        "b": 300,
        "D": 600,
        "fc": 40,
        "fsy": 500,
        "uls_Mstar": 250,
        "uls_Vstar": 120,
        "Tu_star": 0,
        "bot1_count": 3,
        "bot2_count": 0,
        "db_bot_1": 20,
        "db_bot_2": 0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }

    def shared_snapshot() -> dict:
        return dict(base_state)

    def guidance_snapshot(state: dict | None = None) -> dict:
        out = dict(base_state)
        out.update(dict(state or {}))
        return out

    def shared_only_decision() -> tuple[bool, str | None]:
        return bool(shared_only), "test_shared_only" if shared_only else None

    def shear_overlay(working: dict, base: dict, overlay_applied: dict) -> dict:
        working["s_lig"] = session_values.get("inputs_s_lig", working.get("s_lig"))
        overlay_applied["s_lig"] = {"source": "test_overlay"}
        return {
            "shear_widget_overlay_applied": True,
            "shear_widget_overlay_source": "test",
            "overlay_s_lig": working.get("s_lig"),
            "overlay_lig_d": working.get("lig_d"),
            "overlay_lig_legs": working.get("lig_legs"),
        }

    def action_overlay(working: dict, overlay_applied: dict, *, source_state: Any) -> dict:
        _ = overlay_applied
        _ = source_state
        working["uls_Mstar"] = 255
        return {"uls_Mstar": {"source": "test_action"}}

    def mirrors(state: dict) -> dict:
        return {"Ast_bot": 942.0, "row_model_legacy_sync_applied": True}

    def recompute(state: dict) -> dict:
        resolved = dict(state)
        resolved["d"] = 540.0
        return resolved

    def truth(state: dict | None) -> dict:
        resolved = dict(state or {})
        resolved["final_shear_truth_resolved"] = True
        return resolved

    def ux_noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    try:
        legacy_session = FakeSession(session_values)
        bridge_session = FakeSession(session_values)
        legacy_inputs_page.st = SimpleNamespace(session_state=legacy_session)
        bridge.st = SimpleNamespace(session_state=bridge_session)
        legacy_inputs_page._shared_state_snapshot = shared_snapshot
        bridge._shared_state_snapshot_for_summary_bridge = shared_snapshot
        legacy_inputs_page._guidance_state_snapshot = guidance_snapshot
        bridge._guidance_state_snapshot_for_summary_bridge = guidance_snapshot
        legacy_inputs_page._inputs_summary_should_use_shared_only = shared_only_decision
        bridge._inputs_summary_should_use_shared_only_for_app_bridge = shared_only_decision
        legacy_inputs_page._apply_active_page_shear_widget_mirror_overlay = shear_overlay
        bridge._apply_active_page_shear_widget_mirror_overlay_for_app_bridge = shear_overlay
        legacy_inputs_page._overlay_current_design_action_results_for_summary = action_overlay
        bridge._overlay_current_design_action_results_for_summary_for_app_bridge = action_overlay
        legacy_inputs_page.build_legacy_longitudinal_mirrors_from_rows = mirrors
        bridge._build_legacy_longitudinal_mirrors_from_rows_for_app_bridge = mirrors
        legacy_inputs_page._recompute_summary_local_derived_fields = recompute
        bridge._recompute_summary_local_derived_fields_for_app_bridge = recompute
        legacy_inputs_page._overlay_current_normalized_shear_truth = truth
        bridge._overlay_current_normalized_shear_truth_for_app_bridge = truth
        legacy_inputs_page.ux_probe_record = ux_noop
        bridge.ux_probe_record = ux_noop
        legacy_value = legacy_inputs_page._resolved_inputs_summary_state()
        bridge_value = bridge._resolved_inputs_summary_state()
    finally:
        legacy_inputs_page.st = originals["legacy_st"]
        bridge.st = originals["bridge_st"]
        legacy_inputs_page._shared_state_snapshot = originals["legacy_shared"]
        bridge._shared_state_snapshot_for_summary_bridge = originals["bridge_shared"]
        legacy_inputs_page._guidance_state_snapshot = originals["legacy_guidance"]
        bridge._guidance_state_snapshot_for_summary_bridge = originals["bridge_guidance"]
        legacy_inputs_page._inputs_summary_should_use_shared_only = originals["legacy_shared_only"]
        bridge._inputs_summary_should_use_shared_only_for_app_bridge = originals["bridge_shared_only"]
        legacy_inputs_page._apply_active_page_shear_widget_mirror_overlay = originals["legacy_shear_overlay"]
        bridge._apply_active_page_shear_widget_mirror_overlay_for_app_bridge = originals["bridge_shear_overlay"]
        legacy_inputs_page._overlay_current_design_action_results_for_summary = originals["legacy_action_overlay"]
        bridge._overlay_current_design_action_results_for_summary_for_app_bridge = originals["bridge_action_overlay"]
        legacy_inputs_page.build_legacy_longitudinal_mirrors_from_rows = originals["legacy_mirrors"]
        bridge._build_legacy_longitudinal_mirrors_from_rows_for_app_bridge = originals["bridge_mirrors"]
        legacy_inputs_page._recompute_summary_local_derived_fields = originals["legacy_recompute"]
        bridge._recompute_summary_local_derived_fields_for_app_bridge = originals["bridge_recompute"]
        legacy_inputs_page._overlay_current_normalized_shear_truth = originals["legacy_truth"]
        bridge._overlay_current_normalized_shear_truth_for_app_bridge = originals["bridge_truth"]
        legacy_inputs_page.ux_probe_record = originals["legacy_ux"]
        bridge.ux_probe_record = originals["bridge_ux"]

    return {
        "case": name,
        "match": legacy_value == bridge_value and dict(legacy_session) == dict(bridge_session),
        "legacy": legacy_value,
        "bridge": bridge_value,
        "legacy_session_marker": legacy_session.get("_inputs_summary_state_mode"),
        "bridge_session_marker": bridge_session.get("_inputs_summary_state_mode"),
    }


def _overview_case_rows() -> list[dict[str, Any]]:
    return [
        {
            "name": "all_pass_summary_utils",
            "context": {
                "state": {"case": "all_pass_summary_utils"},
                "actions": {"Mu": 250, "Vu": 120, "signature": (("case", "pass"),)},
            },
            "bend": {"rows": [{"status": "PASS"}], "summary_util": 0.82},
            "shear": {"rows": [{"status": "PASS"}], "summary_util": 0.61},
            "crack": {"rows": [{"status": "PASS", "util": 0.44}]},
            "defl": {"rows": [{"status": "PASS"}], "summary_util_total": 0.36},
            "truth": {"truth": "pass"},
        },
        {
            "name": "row_util_fallback_and_warn",
            "context": {
                "state": {"case": "row_util_fallback_and_warn"},
                "actions": {"Mu": 260, "Vu": 125, "signature": (("case", "warn"),)},
            },
            "bend": {"rows": [{"status": "PASS", "util": 0.71}]},
            "shear": {"rows": [{"status": "CHECK", "util": 0.93}], "summary_rows": [{"util": 0.93}]},
            "crack": {"rows": [{"status": "WARN", "util": 0.88}]},
            "defl": {"rows": [{"status": "PASS"}], "summary_util_total": 0.62},
            "truth": {"truth": "warn"},
        },
        {
            "name": "shear_governing_override",
            "context": {
                "state": {"case": "shear_governing_override"},
                "actions": {"Mu": 260, "Vu": 125, "signature": (("case", "governing"),)},
            },
            "bend": {"rows": [{"status": "PASS"}], "summary_util": 0.68},
            "shear": {
                "rows": [{"status": "PASS"}],
                "summary_util": 0.52,
                "summary_governing_status": "FAIL",
                "summary_governing_util": 1.04,
                "summary_governing_source": "sectional",
                "summary_governing_check_name": "shear strength",
                "summary_governing_reason": "sectional failure",
                "summary_governing_selection_origin": "summary",
            },
            "crack": {"rows": [{"status": "PASS", "util": 0.31}]},
            "defl": {"rows": [{"status": "PASS"}], "summary_util_total": 0.49},
            "truth": {"truth": "governing"},
        },
        {
            "name": "stage3_truth_issue",
            "context": {
                "state": {
                    "case": "stage3_truth_issue",
                    "shear_design_status": "INVALID",
                },
                "actions": {"Mu": 260, "Vu": 125, "signature": (("case", "truth"),)},
            },
            "bend": {"rows": [{"status": "PASS"}], "summary_util": 0.64},
            "shear": {"rows": [{"status": "PASS"}], "summary_util": 0.59},
            "crack": {"rows": [{"status": "PASS", "util": 0.41}]},
            "defl": {"rows": [{"status": "PASS"}], "summary_util_total": 0.52},
            "truth": {"truth": "stage3"},
        },
    ]


def _run_overview_case(case: dict[str, Any]) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    originals = {
        "legacy_bend": legacy_inputs_page.build_bending_check_rows_from_state,
        "legacy_shear": legacy_inputs_page.build_shear_check_rows_from_state,
        "legacy_crack": legacy_inputs_page._build_crack_pack_from_state,
        "legacy_defl": legacy_inputs_page._build_deflection_pack_from_state,
        "legacy_truth": legacy_inputs_page._stage3_final_published_shear_truth_bundle,
        "legacy_ux": legacy_inputs_page.ux_probe_record,
        "bridge_bend": bridge._build_bending_check_rows_from_state_for_app_bridge,
        "bridge_shear": bridge._build_shear_check_rows_from_state_for_app_bridge,
        "bridge_crack": bridge._build_crack_pack_from_state_for_app_bridge,
        "bridge_defl": bridge._build_deflection_pack_from_state_for_app_bridge,
        "bridge_truth": bridge._stage3_final_published_shear_truth_bundle_for_app_bridge,
        "bridge_ux": bridge.ux_probe_record,
    }

    def bend(_state: dict) -> dict:
        return dict(case["bend"])

    def shear(_state: dict) -> dict:
        return dict(case["shear"])

    def crack(_state: dict) -> dict:
        return dict(case["crack"])

    def defl(_state: dict) -> dict:
        return dict(case["defl"])

    def truth(_state: dict | None) -> dict:
        return dict(case["truth"])

    def ux_noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    try:
        legacy_inputs_page.build_bending_check_rows_from_state = bend
        legacy_inputs_page.build_shear_check_rows_from_state = shear
        legacy_inputs_page._build_crack_pack_from_state = crack
        legacy_inputs_page._build_deflection_pack_from_state = defl
        legacy_inputs_page._stage3_final_published_shear_truth_bundle = truth
        legacy_inputs_page.ux_probe_record = ux_noop
        bridge._build_bending_check_rows_from_state_for_app_bridge = bend
        bridge._build_shear_check_rows_from_state_for_app_bridge = shear
        bridge._build_crack_pack_from_state_for_app_bridge = crack
        bridge._build_deflection_pack_from_state_for_app_bridge = defl
        bridge._stage3_final_published_shear_truth_bundle_for_app_bridge = truth
        bridge.ux_probe_record = ux_noop
        legacy_value = legacy_inputs_page._collect_design_overview(
            {"input": case["name"]},
            context=dict(case["context"]),
        )
        bridge_value = bridge._collect_design_overview(
            {"input": case["name"]},
            context=dict(case["context"]),
        )
    finally:
        legacy_inputs_page.build_bending_check_rows_from_state = originals["legacy_bend"]
        legacy_inputs_page.build_shear_check_rows_from_state = originals["legacy_shear"]
        legacy_inputs_page._build_crack_pack_from_state = originals["legacy_crack"]
        legacy_inputs_page._build_deflection_pack_from_state = originals["legacy_defl"]
        legacy_inputs_page._stage3_final_published_shear_truth_bundle = originals["legacy_truth"]
        legacy_inputs_page.ux_probe_record = originals["legacy_ux"]
        bridge._build_bending_check_rows_from_state_for_app_bridge = originals["bridge_bend"]
        bridge._build_shear_check_rows_from_state_for_app_bridge = originals["bridge_shear"]
        bridge._build_crack_pack_from_state_for_app_bridge = originals["bridge_crack"]
        bridge._build_deflection_pack_from_state_for_app_bridge = originals["bridge_defl"]
        bridge._stage3_final_published_shear_truth_bundle_for_app_bridge = originals["bridge_truth"]
        bridge.ux_probe_record = originals["bridge_ux"]

    return {
        "case": str(case["name"]),
        "match": legacy_value == bridge_value,
        "legacy": legacy_value,
        "bridge": bridge_value,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    summary_rows = [
        _run_summary_case(
            name="widget_overlay_mode",
            session_values={
                "inputs_s_lig": 250,
                "inputs_lig_d": 10,
                "inputs_lig_legs": 2,
            },
            shared_only=False,
        ),
        _run_summary_case(
            name="shared_only_mode",
            session_values={
                "inputs_s_lig": 250,
                "inputs_lig_d": 10,
                "inputs_lig_legs": 2,
            },
            shared_only=True,
        ),
    ]
    overview_rows = [_run_overview_case(case) for case in _overview_case_rows()]

    checks = {
        "summary_branch_parity": all(bool(row["match"]) for row in summary_rows),
        "overview_branch_parity": all(bool(row["match"]) for row in overview_rows),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_summary_overview_contract_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "summary_branch_samples": summary_rows,
        "overview_branch_samples": overview_rows,
        "wrapper_note": "summary and overview are local app-bridge orchestration with branch parity",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_summary_overview_contract_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_summary_overview_contract_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Summary/Overview Contract Parity",
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
