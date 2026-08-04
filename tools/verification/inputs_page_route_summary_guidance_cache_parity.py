from __future__ import annotations

import copy
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


FP = ("summary", "fp")


def _complete_debug() -> dict[str, Any]:
    return {
        "guidance_resolved_state": {"Mu_star": 100.0},
        "overview": {"worst_util": 0.82},
        "efficiency_tightening_state": {"classification": "ok"},
    }


def _session_state(case_name: str) -> dict[str, Any]:
    if case_name == "cache_hit":
        return {
            "_design_guide_fp": FP,
            "_design_guide_cache": [{"check_key": "cached_simple"}],
            "_design_guide_cached_fingerprint": FP,
            "_design_guide_cached_items": [{"check_key": "cached_guidance"}],
            "_design_guide_cached_debug": _complete_debug(),
        }
    if case_name == "incomplete_cache":
        return {
            "_design_guide_fp": FP,
            "_design_guide_cache": [{"check_key": "stale"}],
            "_design_guide_cached_fingerprint": FP,
            "_design_guide_cached_items": [{"check_key": "stale"}],
            "_design_guide_cached_debug": {"overview": {}},
        }
    return {}


def _run(module: Any, *, legacy: bool, case_name: str) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    calls: list[str] = []
    fake_st = SimpleNamespace(session_state=_session_state(case_name))

    def get_design_guide_fp(state):
        calls.append("fp")
        return FP

    def compute_design_guidance_items(state, *, guidance_debug_verbose: bool, debug_enabled: bool):
        calls.append(
            f"compute:{guidance_debug_verbose}:{debug_enabled}:{state.get('Mu_star')}"
        )
        return {
            "guidance_items": [{"check_key": "computed"}],
            "debug_trace": {
                **_complete_debug(),
                "design_guide_presentation": {"should_not_cache": True},
                "debug_enabled": debug_enabled,
            },
        }

    summary_state = {"Mu_star": 100.0}
    summary_state_debug = {"initial": True}
    if legacy:
        originals = {
            "st": legacy_inputs_page.st,
            "_fp": legacy_inputs_page._get_design_guide_fp,
            "compute": legacy_inputs_page._compute_design_guidance_items,
        }
        try:
            legacy_inputs_page.st = fake_st
            legacy_inputs_page._get_design_guide_fp = get_design_guide_fp
            legacy_inputs_page._compute_design_guidance_items = compute_design_guidance_items
            result = module.render_inputs_summary_guidance_cache_current_coordinator(
                summary_state=copy.deepcopy(summary_state),
                summary_state_debug=summary_state_debug,
            )
        finally:
            legacy_inputs_page.st = originals["st"]
            legacy_inputs_page._get_design_guide_fp = originals["_fp"]
            legacy_inputs_page._compute_design_guidance_items = originals["compute"]
    else:
        originals = {
            "st": route_bridge.st,
            "_fp": route_bridge._get_design_guide_fp,
            "compute": route_bridge._compute_design_guidance_items,
        }
        try:
            route_bridge.st = fake_st
            route_bridge._get_design_guide_fp = get_design_guide_fp
            route_bridge._compute_design_guidance_items = compute_design_guidance_items
            result = module.render_inputs_summary_guidance_cache_current_coordinator(
                summary_state=copy.deepcopy(summary_state),
                summary_state_debug=summary_state_debug,
            )
        finally:
            route_bridge.st = originals["st"]
            route_bridge._get_design_guide_fp = originals["_fp"]
            route_bridge._compute_design_guidance_items = originals["compute"]
    return {
        "result": result,
        "summary_state_debug": summary_state_debug,
        "session_state": dict(fake_st.session_state),
        "calls": calls,
    }


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for case_name in ("cache_miss", "cache_hit", "incomplete_cache"):
        legacy_result = _run(legacy_inputs_page, legacy=True, case_name=case_name)
        route_result = _run(route_bridge, legacy=False, case_name=case_name)
        cases[case_name] = {"legacy": legacy_result, "route": route_result}
        checks[f"{case_name}_result_matches_legacy"] = legacy_result["result"] == route_result["result"]
        checks[f"{case_name}_debug_matches_legacy"] = (
            legacy_result["summary_state_debug"] == route_result["summary_state_debug"]
        )
        checks[f"{case_name}_session_matches_legacy"] = (
            legacy_result["session_state"] == route_result["session_state"]
        )
        checks[f"{case_name}_calls_match_legacy"] = legacy_result["calls"] == route_result["calls"]

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["route_does_not_delegate_summary_guidance_cache"] = (
        "_legacy_inputs_page.render_inputs_summary_guidance_cache_current_coordinator" not in route_source
    )
    checks["cache_hit_does_not_compute"] = not any(
        str(call).startswith("compute") for call in cases["cache_hit"]["route"]["calls"]
    )
    checks["incomplete_cache_recomputes"] = any(
        str(call).startswith("compute") for call in cases["incomplete_cache"]["route"]["calls"]
    )
    checks["miss_cache_removes_presentation_debug"] = (
        "design_guide_presentation"
        not in cases["cache_miss"]["route"]["session_state"].get("_design_guide_cached_debug", {})
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_summary_guidance_cache_parity",
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
    json_path = ARTIFACT_DIR / f"inputs_page_route_summary_guidance_cache_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_summary_guidance_cache_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Summary Guidance Cache Parity",
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
