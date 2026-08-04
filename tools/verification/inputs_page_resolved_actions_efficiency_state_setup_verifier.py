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
    json_path = ARTIFACT_DIR / f"inputs_page_resolved_actions_efficiency_state_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_resolved_actions_efficiency_state_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original = inputs_page._debug_resolved_guidance_actions
    failures: list[str] = []
    events: list[dict[str, Any]] = []
    stages: list[str] = []

    def _resolved_actions(state):
        events.append({"event": "resolved_actions", "state": dict(state or {})})
        return {"Mu": 12.3, "Vu": 4.5, "source": "unit"}

    try:
        inputs_page._debug_resolved_guidance_actions = _resolved_actions
        resolved, efficiency_state, mode_mt, bottom_bt = (
            inputs_page.render_design_guide_resolved_actions_and_efficiency_state_setup(
                current_state={"beam": "B1"},
                guidance_debug={
                    "efficiency_tightening_state": {
                        "mode_tightening": {"mode": "reduce"},
                        "bottom_tightening": {"bars": 2},
                        "other": True,
                    }
                },
                stage=lambda label: stages.append(str(label)),
            )
        )
    finally:
        inputs_page._debug_resolved_guidance_actions = original

    if events != [{"event": "resolved_actions", "state": {"beam": "B1"}}]:
        failures.append(f"resolved_actions_call_mismatch:{events}")
    if stages != ["post_plan.after_resolved_guidance_actions"]:
        failures.append(f"stage_mismatch:{stages}")
    if resolved != {"Mu": 12.3, "Vu": 4.5, "source": "unit"}:
        failures.append(f"resolved_mismatch:{resolved}")
    if efficiency_state.get("other") is not True:
        failures.append(f"efficiency_state_mismatch:{efficiency_state}")
    if mode_mt != {"mode": "reduce"}:
        failures.append(f"mode_tightening_mismatch:{mode_mt}")
    if bottom_bt != {"bars": 2}:
        failures.append(f"bottom_tightening_mismatch:{bottom_bt}")

    payload = {
        "verifier": "inputs_page_resolved_actions_efficiency_state_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "events": events,
        "stages": stages,
        "resolved": resolved,
        "efficiency_state": efficiency_state,
        "mode_tightening": mode_mt,
        "bottom_tightening": bottom_bt,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Resolved Actions Efficiency State Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                f"- resolved actions: `{resolved}`",
                f"- mode tightening: `{mode_mt}`",
                f"- bottom tightening: `{bottom_bt}`",
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
