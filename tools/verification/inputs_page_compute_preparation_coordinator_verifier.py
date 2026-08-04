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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_compute_preparation_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_compute_preparation_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_design_guide_guidance_cache_or_compute": inputs_page.render_design_guide_guidance_cache_or_compute,
        "render_design_guide_prepare_guidance_debug_and_state": inputs_page.render_design_guide_prepare_guidance_debug_and_state,
        "render_design_guide_fast_terminal_after_compute": inputs_page.render_design_guide_fast_terminal_after_compute,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(name: str, *, fast_terminal: bool):
        calls: list[dict[str, Any]] = []
        stage_calls: list[str] = []
        current_state = {"depth": 500}
        settle_gate_decision = {"allowed": True}
        inputs_render_audit = {"existing": "yes"}
        guidance_items_raw = [{"title_main": "Raw"}]
        guidance_debug = {"debug": "raw"}
        prepared_debug = {"debug": "prepared"}
        guidance_disp_state = {"depth": 600}

        def cache_or_compute(**kwargs):
            calls.append({"event": "cache_or_compute", "kwargs": dict(kwargs)})
            return (
                guidance_items_raw,
                guidance_debug,
                True,
                False,
                True,
                False,
                True,
                False,
                True,
            )

        def prepare(**kwargs):
            calls.append({"event": "prepare", "kwargs": dict(kwargs)})
            return prepared_debug, guidance_disp_state, 12.5

        def fast(**kwargs):
            calls.append({"event": "fast_terminal", "kwargs": dict(kwargs)})
            return fast_terminal

        try:
            inputs_page.render_design_guide_guidance_cache_or_compute = cache_or_compute
            inputs_page.render_design_guide_prepare_guidance_debug_and_state = prepare
            inputs_page.render_design_guide_fast_terminal_after_compute = fast
            result = inputs_page.render_design_guide_compute_preparation_coordinator(
                guidance_started_at=10.0,
                fingerprint="fingerprint-1",
                current_state=current_state,
                sidebar_debug=True,
                settle_gate_decision=settle_gate_decision,
                inputs_render_audit=inputs_render_audit,
                stage=lambda label: stage_calls.append(label),
            )
        finally:
            _restore()
        case = {
            "name": name,
            "result": result,
            "calls": calls,
            "stage_calls": stage_calls,
        }
        cases.append(case)
        return case

    case = _run_case("normal_compute_preparation", fast_terminal=False)
    if [call["event"] for call in case["calls"]] != [
        "cache_or_compute",
        "prepare",
        "fast_terminal",
    ]:
        failures.append(f"normal_call_order_mismatch:{case}")
    result = case["result"]
    if result != (
        [{"title_main": "Raw"}],
        {"debug": "prepared"},
        True,
        False,
        True,
        False,
        True,
        False,
        True,
        {"depth": 600},
        12.5,
        False,
    ):
        failures.append(f"normal_result_mismatch:{case}")
    cache_kwargs = case["calls"][0]["kwargs"]
    if cache_kwargs.get("fingerprint") != "fingerprint-1" or cache_kwargs.get("sidebar_debug") is not True:
        failures.append(f"normal_cache_kwargs_mismatch:{case}")
    prepare_kwargs = case["calls"][1]["kwargs"]
    if prepare_kwargs.get("guidance_started_at") != 10.0:
        failures.append(f"normal_prepare_start_mismatch:{case}")
    if prepare_kwargs.get("guidance_debug") != {"debug": "raw"}:
        failures.append(f"normal_prepare_debug_mismatch:{case}")
    if prepare_kwargs.get("settle_gate_decision") != {"allowed": True}:
        failures.append(f"normal_prepare_settle_gate_mismatch:{case}")
    fast_kwargs = case["calls"][2]["kwargs"]
    if fast_kwargs.get("guidance_debug") != {"debug": "prepared"}:
        failures.append(f"normal_fast_debug_mismatch:{case}")
    if fast_kwargs.get("inputs_render_audit") != {"existing": "yes"}:
        failures.append(f"normal_fast_audit_mismatch:{case}")

    case = _run_case("fast_terminal_rendered", fast_terminal=True)
    if case["result"][-1] is not True:
        failures.append(f"fast_terminal_flag_mismatch:{case}")
    if [call["event"] for call in case["calls"]] != [
        "cache_or_compute",
        "prepare",
        "fast_terminal",
    ]:
        failures.append(f"fast_terminal_call_order_mismatch:{case}")

    payload = {
        "verifier": "inputs_page_compute_preparation_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Compute Preparation Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` fast_terminal={case['result'][-1]}" for case in cases),
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
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
