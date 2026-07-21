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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_post_cleanup_gate_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_post_cleanup_gate_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_design_guide_presentation_cleanup_override_pipeline": inputs_page.render_design_guide_presentation_cleanup_override_pipeline,
        "render_design_guide_post_cleanup_terminal_state_reconciliation": inputs_page.render_design_guide_post_cleanup_terminal_state_reconciliation,
        "render_design_guide_post_cleanup_audit_and_early_shear_pipeline": inputs_page.render_design_guide_post_cleanup_audit_and_early_shear_pipeline,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(name: str, *, early_return: bool):
        calls: list[dict[str, Any]] = []
        stage_calls: list[str] = []
        inputs_render_audit = {"audit": "input"}

        def presentation(**kwargs):
            calls.append({"event": "presentation", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["presentation"] = True
            return (
                [{"title_main": "Presented"}],
                {"headline": "Presented headline"},
                "Headline",
                "Subtext",
                {"rr": "presentation"},
                debug,
            )

        def terminal_reconcile(**kwargs):
            calls.append({"event": "terminal_reconcile", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["terminal_reconcile"] = True
            return (
                False,
                True,
                True,
                "optimal",
                "terminal_reconciled",
                debug,
            )

        def audit(**kwargs):
            calls.append({"event": "audit", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["audit"] = True
            return {"post_cleanup": True}, debug, early_return

        try:
            inputs_page.render_design_guide_presentation_cleanup_override_pipeline = presentation
            inputs_page.render_design_guide_post_cleanup_terminal_state_reconciliation = terminal_reconcile
            inputs_page.render_design_guide_post_cleanup_audit_and_early_shear_pipeline = audit
            result = inputs_page.render_design_guide_presentation_post_cleanup_gate_coordinator(
                guidance_items=[{"title_main": "Input"}],
                dg_presentation={"headline": "Input"},
                guidance_debug={"start": True},
                guidance_disp_state={"depth": 500},
                recommendation_result={"rr": "input"},
                terminal_state=None,
                terminal_state_source="input_source",
                render_plan={"reason": "input"},
                dg_overview={"overview": True},
                inputs_render_audit=inputs_render_audit,
                stage=lambda label: stage_calls.append(label),
            )
        finally:
            _restore()
        case = {
            "name": name,
            "early_return": early_return,
            "result": result,
            "calls": calls,
            "stage_calls": stage_calls,
        }
        cases.append(case)
        return case

    case = _run_case("normal_gate", early_return=False)
    if [call["event"] for call in case["calls"]] != [
        "presentation",
        "terminal_reconcile",
        "audit",
    ]:
        failures.append(f"normal_call_order_mismatch:{case}")
    if case["result"] != (
        [{"title_main": "Presented"}],
        {"headline": "Presented headline"},
        {"rr": "presentation"},
        {"start": True, "presentation": True, "terminal_reconcile": True, "audit": True},
        "optimal",
        "terminal_reconciled",
        True,
        {"post_cleanup": True},
        False,
    ):
        failures.append(f"normal_result_mismatch:{case}")
    terminal_kwargs = case["calls"][1]["kwargs"]
    if terminal_kwargs.get("presentation_headline") != "Headline":
        failures.append(f"terminal_headline_mismatch:{case}")
    if terminal_kwargs.get("presentation_subtext") != "Subtext":
        failures.append(f"terminal_subtext_mismatch:{case}")
    audit_kwargs = case["calls"][2]["kwargs"]
    if audit_kwargs.get("post_cleanup_build_active_shear_blocker") is not True:
        failures.append(f"audit_build_active_shear_blocker_mismatch:{case}")
    if audit_kwargs.get("inputs_render_audit") != {"audit": "input"}:
        failures.append(f"audit_inputs_render_audit_mismatch:{case}")

    case = _run_case("early_shear_return", early_return=True)
    if case["result"][-1] is not True:
        failures.append(f"early_return_flag_mismatch:{case}")

    payload = {
        "verifier": "inputs_page_presentation_post_cleanup_gate_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Post Cleanup Gate Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` early={case['result'][-1]}" for case in cases),
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
