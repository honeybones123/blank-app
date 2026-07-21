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


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_final_panel_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_final_panel_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_st = inputs_page.st
    original_render_final_panel = inputs_page.design_guide_page.render_final_panel
    failures: list[str] = []
    render_calls: list[dict[str, Any]] = []

    fake_st = FakeStreamlit()
    fake_st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = {
        "design_guide_render_eligibility_trace": {
            "existing": True,
            "landing_shell_rendered": True,
        }
    }

    def _restore() -> None:
        inputs_page.st = original_st
        inputs_page.design_guide_page.render_final_panel = original_render_final_panel

    def render_final_panel(st_arg, **kwargs):
        render_calls.append({"st_is_fake": st_arg is fake_st, **dict(kwargs)})

    try:
        inputs_page.st = fake_st
        inputs_page.design_guide_page.render_final_panel = render_final_panel
        returned_bundle = inputs_page.render_inputs_design_guide_final_panel_coordinator(
            design_guide_slot="slot",
            sync_callbacks={"sync": True},
            inputs_render_audit={"audit": True},
            inputs_detailed_mode=True,
            fast_focus_section="design-guide",
            trace={"trace": True},
        )
    finally:
        _restore()

    if returned_bundle is not fake_st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY]:
        failures.append("returned_bundle_not_session_bundle")
    if len(render_calls) != 1:
        failures.append(f"render_final_panel_call_count_mismatch:{len(render_calls)}")
    else:
        call = render_calls[0]
        if call.get("st_is_fake") is not True:
            failures.append(f"streamlit_argument_mismatch:{call}")
        for key, expected in {
            "slot": "slot",
            "sync_callbacks": {"sync": True},
            "inputs_render_audit": {"audit": True},
            "inputs_detailed_mode": True,
            "fast_focus_section": "design-guide",
            "trace": {"trace": True},
            "render_panel_accepts_sync_callbacks": False,
        }.items():
            if call.get(key) != expected:
                failures.append(f"render_call_{key}_mismatch:{call}")
        if call.get("render_panel") is not inputs_page.render_design_guide_panel_orchestration_coordinator:
            failures.append("render_panel_bridge_mismatch")
    trace = fake_st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY].get(
        "design_guide_render_eligibility_trace"
    )
    expected_trace = {
        "existing": True,
        "design_guide_slot_created": True,
        "landing_shell_rendered": False,
        "real_design_guide_card_rendered": True,
        "real_design_guide_card_rendered_source": "render_final_panel",
    }
    if trace != expected_trace:
        failures.append(f"eligibility_trace_mismatch:{trace}")
    if fake_st.session_state.get("_design_guide_render_eligibility_trace_last") != expected_trace:
        failures.append(
            f"eligibility_trace_last_mismatch:{fake_st.session_state.get('_design_guide_render_eligibility_trace_last')}"
        )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_final_panel_coordinator" not in source:
        failures.append("final_panel_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_post_render_eligibility_trace",
        "design_guide_page.render_final_panel(",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_design_guide_final_panel_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "render_call_count": len(render_calls),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Final Panel Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
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
