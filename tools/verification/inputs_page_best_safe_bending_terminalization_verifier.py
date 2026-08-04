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


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_best_safe_bending_terminalization_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_best_safe_bending_terminalization_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_post_click_low_bending_resolution_item": inputs_page._post_click_low_bending_resolution_item,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "normalise_final_visible_design_guide_item": inputs_page.normalise_final_visible_design_guide_item,
    }
    missing_button_contract_key = not hasattr(inputs_page, "DESIGN_GUIDE_BUTTON_CONTRACT_KEY")
    if not missing_button_contract_key:
        originals["DESIGN_GUIDE_BUTTON_CONTRACT_KEY"] = inputs_page.DESIGN_GUIDE_BUTTON_CONTRACT_KEY
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)
        if missing_button_contract_key and hasattr(inputs_page, "DESIGN_GUIDE_BUTTON_CONTRACT_KEY"):
            delattr(inputs_page, "DESIGN_GUIDE_BUTTON_CONTRACT_KEY")

    def _base_inputs() -> dict[str, Any]:
        return {
            "displayed_primary_item": {"title": "original"},
            "displayed_primary_button_contract": {"enabled": True, "family": "original"},
            "displayed_primary_payload": {"payload": "original"},
            "displayed_primary_resolved": {"resolved": "original"},
            "displayed_primary_candidate_search_evidence": {"evidence": "original"},
            "guidance_items": [{"title": "original"}, {"title": "secondary"}],
            "render_plan": {"visible_guidance_items": [{"title": "original"}], "reason": "original"},
            "guidance_debug": {},
        }

    non_bending = _base_inputs()
    try:
        inputs_page.st = _FakeStreamlit()
        result = inputs_page.render_design_guide_displayed_best_safe_bending_terminalization(
            proof_action_family="shear",
            proof_exact={"shear": {"family": "shear"}},
            guidance_disp_state={"D": 500},
            overview={"utils": {"shear": 0.7}},
            **non_bending,
        )
    finally:
        _restore()
    cases.append({"name": "non_bending_noop", "result": result, "inputs": non_bending})
    if result[0] != {"title": "original"}:
        failures.append(f"non_bending_item_changed:{result}")
    if non_bending["render_plan"].get("reason") != "original":
        failures.append(f"non_bending_render_plan_changed:{non_bending['render_plan']}")

    terminal = _base_inputs()
    terminal_events: list[dict[str, Any]] = []

    def _terminal_item(state, overview, mode_config, audit, *, debug_sink):
        terminal_events.append(
            {
                "event": "terminal_item",
                "state": dict(state or {}),
                "mode_config": dict(mode_config or {}),
                "audit": dict(audit or {}),
            }
        )
        debug_sink["terminal_builder_called"] = True
        return {
            "title": "terminal",
            "button_contract": {"enabled": False, "family": "bending", "blocking_reason": "exact"},
            "action_payload": {"payload": "terminal"},
            "resolved_candidate": {"resolved": "terminal"},
            "candidate_search_evidence": {"evidence": "terminal"},
        }

    try:
        fake_st = _FakeStreamlit()
        inputs_page.st = fake_st
        inputs_page.DESIGN_GUIDE_BUTTON_CONTRACT_KEY = "_focused_design_guide_button_contract"
        inputs_page._post_click_low_bending_resolution_item = _terminal_item
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "balanced"
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))
        inputs_page.normalise_final_visible_design_guide_item = (
            lambda item: {**dict(item), "normalised": True}
        )
        result = inputs_page.render_design_guide_displayed_best_safe_bending_terminalization(
            proof_action_family="bending",
            proof_exact={"bending": {"family": "bending"}},
            guidance_disp_state={"D": 500},
            overview={"utils": {"bending": 0.74, "shear": 0.91}},
            **terminal,
        )
    finally:
        _restore()
    cases.append(
        {
            "name": "bending_terminalizes_disabled_contract",
            "result": result,
            "inputs": terminal,
            "events": terminal_events,
            "session_state": dict(fake_st.session_state),
        }
    )
    if result[0].get("title") != "terminal" or not result[0].get("normalised"):
        failures.append(f"terminal_item_result_mismatch:{result}")
    if result[2] != {"payload": "terminal"}:
        failures.append(f"terminal_payload_mismatch:{result}")
    if terminal["guidance_items"][0].get("title") != "terminal":
        failures.append(f"terminal_guidance_items_not_replaced:{terminal['guidance_items']}")
    if terminal["render_plan"].get("reason") != "post_click_displayed_best_safe_action_terminalized":
        failures.append(f"terminal_render_plan_reason_mismatch:{terminal['render_plan']}")
    if terminal["guidance_debug"].get("button_contract_enabled") is not False:
        failures.append(f"terminal_debug_contract_state_mismatch:{terminal['guidance_debug']}")
    if fake_st.session_state.get(inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY) != {}:
        failures.append(f"terminal_primary_payload_not_cleared:{fake_st.session_state}")
    if not terminal_events or terminal_events[0]["audit"].get("post_click_families_below_final_threshold") != ["bending"]:
        failures.append(f"terminal_audit_low_families_mismatch:{terminal_events}")

    enabled = _base_inputs()

    def _enabled_item(state, overview, mode_config, audit, *, debug_sink):
        return {
            "title": "enabled",
            "button_contract": {"enabled": True, "family": "bending"},
        }

    try:
        inputs_page.st = _FakeStreamlit()
        inputs_page._post_click_low_bending_resolution_item = _enabled_item
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "balanced"
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))
        result = inputs_page.render_design_guide_displayed_best_safe_bending_terminalization(
            proof_action_family="bending",
            proof_exact={"bending": {"family": "bending"}},
            guidance_disp_state={"D": 500},
            overview={"utils": {"bending": 0.74}},
            **enabled,
        )
    finally:
        _restore()
    cases.append({"name": "enabled_contract_no_replacement", "result": result, "inputs": enabled})
    if result[0] != {"title": "original"}:
        failures.append(f"enabled_item_should_not_replace:{result}")
    if enabled["render_plan"].get("reason") != "original":
        failures.append(f"enabled_render_plan_changed:{enabled['render_plan']}")

    payload = {
        "verifier": "inputs_page_best_safe_bending_terminalization_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Best Safe Bending Terminalization Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}`" for case in cases),
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
