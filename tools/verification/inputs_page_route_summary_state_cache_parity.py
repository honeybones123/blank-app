from __future__ import annotations

import copy
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


def _summary_state() -> dict[str, Any]:
    return {
        "Mu_star": 100.0,
        "Vu_star": 80.0,
        "Tu_star": 5.0,
        "sls_Mstar": 40.0,
        "sls_Vstar": 20.0,
        "sigma_sr": 150.0,
        "s_lig": 200,
        "lig_d": 10,
        "lig_legs": 2,
        "Ast_bot": 1200,
        "d": 550,
        "bot1_count": 4,
        "db_bot_1": 20,
        "final_shear_truth_bundle_complete": True,
        "shear_truth_status": "PASS",
        "final_shear_truth_resolved": True,
        "final_shear_truth_failure_reason": "",
        "published_result_spacing_mm": 200,
        "published_result_spacing_meaning": "input",
    }


def _summary_debug() -> dict[str, Any]:
    return {
        "summary_state_source": "test",
        "summary_shared_only_mode": False,
        "summary_shared_only_reason": "",
        "overlay_count": 2,
        "summary_shared_vs_widget_diffs": {"Vu_star": [70, 80]},
    }


def _expected_action_fp() -> tuple[Any, ...]:
    return (
        ("fp", "test"),
        (11.0, 22.0, 33.0, 44.0, 55.0),
        100.0,
        80.0,
        5.0,
        40.0,
        20.0,
        150.0,
        (("Vu_star", "[70, 80]"),),
    )


def _run(module: Any, *, legacy: bool, cache_hit: bool) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    calls: list[str] = []

    def resolved_inputs_summary_state():
        return copy.deepcopy(_summary_state()), copy.deepcopy(_summary_debug())

    def get_design_guide_fp(state):
        calls.append("fp")
        return ("fp", "test")

    def resolve_design_actions(state):
        calls.append("actions")
        return {"Mu_pos": 11.0, "Mu_neg": 22.0, "Vu": 33.0, "SLS_M": 44.0, "SLS_V": 55.0}

    def hc_try(tag, fn):
        calls.append(tag)
        return fn()

    def pack_builder(name):
        def build(state):
            calls.append(f"build:{name}")
            return {"rows": [{"uid": name}], "state_Mu": state.get("Mu_star")}

        return build

    expected_fp = _expected_action_fp()
    ss: dict[str, Any] = {
        "results_version": 9,
        "_final_shear_truth_normalized_source": "normalized",
        "_final_shear_truth_normalized_latest": {"spacing": 200},
    }
    if cache_hit:
        ss.update(
            {
                "_summary_cache_version": 9,
                "_summary_cache_action_fp": expected_fp,
                "_bend_pack": {"rows": [{"uid": "cached_bending"}]},
                "_shear_pack": {"rows": [{"uid": "cached_shear"}]},
                "_crack_pack": {"rows": [{"uid": "cached_crack"}]},
                "_defl_pack": {"rows": [{"uid": "cached_deflection"}]},
            }
        )
    marks: list[str] = []

    def mark(label: str) -> None:
        marks.append(label)

    if legacy:
        originals = {
            "_resolved": legacy_inputs_page._resolved_inputs_summary_state,
            "_fp": legacy_inputs_page._get_design_guide_fp,
            "actions": legacy_inputs_page.resolve_design_actions,
            "hc_try": legacy_inputs_page.hc_try,
            "bend": legacy_inputs_page.build_bending_check_rows_from_state,
            "shear": legacy_inputs_page.build_shear_check_rows_from_state,
            "crack": legacy_inputs_page.build_crack_check_rows_from_state,
            "defl": legacy_inputs_page.build_deflection_check_rows_from_state,
        }
        try:
            legacy_inputs_page._resolved_inputs_summary_state = resolved_inputs_summary_state
            legacy_inputs_page._get_design_guide_fp = get_design_guide_fp
            legacy_inputs_page.resolve_design_actions = resolve_design_actions
            legacy_inputs_page.hc_try = hc_try
            legacy_inputs_page.build_bending_check_rows_from_state = pack_builder("bending")
            legacy_inputs_page.build_shear_check_rows_from_state = pack_builder("shear")
            legacy_inputs_page.build_crack_check_rows_from_state = pack_builder("crack")
            legacy_inputs_page.build_deflection_check_rows_from_state = pack_builder("deflection")
            result = module.render_inputs_summary_state_cache_current_coordinator(ss=ss, mark=mark)
        finally:
            legacy_inputs_page._resolved_inputs_summary_state = originals["_resolved"]
            legacy_inputs_page._get_design_guide_fp = originals["_fp"]
            legacy_inputs_page.resolve_design_actions = originals["actions"]
            legacy_inputs_page.hc_try = originals["hc_try"]
            legacy_inputs_page.build_bending_check_rows_from_state = originals["bend"]
            legacy_inputs_page.build_shear_check_rows_from_state = originals["shear"]
            legacy_inputs_page.build_crack_check_rows_from_state = originals["crack"]
            legacy_inputs_page.build_deflection_check_rows_from_state = originals["defl"]
    else:
        originals = {
            "_resolved": route_bridge._resolved_inputs_summary_state,
            "_fp": route_bridge._get_design_guide_fp,
            "actions": route_bridge.resolve_design_actions,
            "hc_try": route_bridge.hc_try,
            "bend": route_bridge.build_bending_check_rows_from_state,
            "shear": route_bridge.build_shear_check_rows_from_state,
            "crack": route_bridge.build_crack_check_rows_from_state,
            "defl": route_bridge.build_deflection_check_rows_from_state,
        }
        try:
            route_bridge._resolved_inputs_summary_state = resolved_inputs_summary_state
            route_bridge._get_design_guide_fp = get_design_guide_fp
            route_bridge.resolve_design_actions = resolve_design_actions
            route_bridge.hc_try = hc_try
            route_bridge.build_bending_check_rows_from_state = pack_builder("bending")
            route_bridge.build_shear_check_rows_from_state = pack_builder("shear")
            route_bridge.build_crack_check_rows_from_state = pack_builder("crack")
            route_bridge.build_deflection_check_rows_from_state = pack_builder("deflection")
            result = module.render_inputs_summary_state_cache_current_coordinator(ss=ss, mark=mark)
        finally:
            route_bridge._resolved_inputs_summary_state = originals["_resolved"]
            route_bridge._get_design_guide_fp = originals["_fp"]
            route_bridge.resolve_design_actions = originals["actions"]
            route_bridge.hc_try = originals["hc_try"]
            route_bridge.build_bending_check_rows_from_state = originals["bend"]
            route_bridge.build_shear_check_rows_from_state = originals["shear"]
            route_bridge.build_crack_check_rows_from_state = originals["crack"]
            route_bridge.build_deflection_check_rows_from_state = originals["defl"]

    return {"result": result, "ss": ss, "marks": marks, "calls": calls}


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    reference_module = legacy_inputs_page
    reference_is_legacy = hasattr(
        legacy_inputs_page,
        "render_inputs_summary_state_cache_current_coordinator",
    )
    if not reference_is_legacy:
        reference_module = route_bridge
    for case_name, cache_hit in (("cache_miss", False), ("cache_hit", True)):
        legacy_result = _run(reference_module, legacy=reference_is_legacy, cache_hit=cache_hit)
        route_result = _run(route_bridge, legacy=False, cache_hit=cache_hit)
        cases[case_name] = {"legacy": legacy_result, "route": route_result}
        checks[f"{case_name}_result_matches_legacy"] = legacy_result["result"] == route_result["result"]
        checks[f"{case_name}_session_matches_legacy"] = legacy_result["ss"] == route_result["ss"]
        checks[f"{case_name}_marks_match_legacy"] = legacy_result["marks"] == route_result["marks"]

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["route_does_not_delegate_summary_state_cache"] = (
        "_legacy_inputs_page.render_inputs_summary_state_cache_current_coordinator" not in route_source
    )
    checks["cache_miss_builds_all_packs"] = all(
        f"summary.build_{name}_pack" in cases["cache_miss"]["route"]["calls"]
        for name in ("bending", "shear", "crack", "deflection")
    )
    checks["cache_hit_reuses_cached_packs"] = not any(
        str(call).startswith("summary.build_") for call in cases["cache_hit"]["route"]["calls"]
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_summary_state_cache_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "case_calls": {
            name: case["route"]["calls"]
            for name, case in cases.items()
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_summary_state_cache_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_summary_state_cache_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Summary State Cache Parity",
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
