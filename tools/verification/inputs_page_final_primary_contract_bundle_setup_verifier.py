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
    def __init__(self, session_state: dict[str, Any]) -> None:
        self.session_state = session_state


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_final_primary_contract_bundle_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_final_primary_contract_bundle_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_record_rendered_design_guide_primary_apply_payload": (
            inputs_page._record_rendered_design_guide_primary_apply_payload
        ),
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        session_state: dict[str, Any],
        displayed_contract: dict,
        guidance_debug: dict,
        displayed_item: dict | None,
        enabled: bool,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _enabled(contract):
            events.append({"event": "enabled", "contract": dict(contract or {})})
            return bool(enabled)

        def _record(**kwargs):
            events.append(
                {
                    "event": "record",
                    "item": dict(kwargs.get("item") or {}),
                    "rec": dict(kwargs.get("rec") or {}),
                    "button_contract": dict(kwargs.get("button_contract") or {}),
                    "state": dict(kwargs.get("state") or {}),
                }
            )
            return {"recorded": True, "updates": dict(kwargs.get("button_contract", {}).get("updates") or {})}

        try:
            inputs_page.st = _FakeStreamlit(dict(session_state))
            inputs_page._design_guide_button_contract_enabled = _enabled
            inputs_page._record_rendered_design_guide_primary_apply_payload = _record
            result = inputs_page.render_design_guide_final_primary_contract_bundle_setup(
                displayed_primary_button_contract=dict(displayed_contract),
                guidance_debug=guidance_debug,
                displayed_primary_item=None if displayed_item is None else dict(displayed_item),
                guidance_disp_state={"D": 500},
            )
        finally:
            _restore()
        case = {
            "name": name,
            "events": events,
            "result": result,
            "guidance_debug": guidance_debug,
        }
        cases.append(case)
        return case

    existing_payload = _run_case(
        "enabled_uses_session_payload",
        session_state={
            inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY: {"session_payload": True},
            "pending_recommendation": {"id": "pending"},
        },
        displayed_contract={"enabled": True, "family": "bending", "updates": {"D": 550}, "preview_pass": True},
        guidance_debug={},
        displayed_item={"title": "primary"},
        enabled=True,
    )
    if [event["event"] for event in existing_payload["events"]] != ["enabled"]:
        failures.append(f"existing_payload_event_mismatch:{existing_payload['events']}")
    if existing_payload["result"][2] != {"session_payload": True}:
        failures.append(f"existing_payload_result_mismatch:{existing_payload['result']}")
    if existing_payload["guidance_debug"].get("selected_action_type") != "apply_resolved_candidate":
        failures.append(f"existing_payload_debug_missing:{existing_payload['guidance_debug']}")

    recorded = _run_case(
        "enabled_records_missing_payload",
        session_state={"pending_recommendation": {"id": "pending"}},
        displayed_contract={"enabled": True, "family": "shear", "updates": {"s_lig": 150}},
        guidance_debug={},
        displayed_item={"title": "primary"},
        enabled=True,
    )
    if [event["event"] for event in recorded["events"]] != ["enabled", "record"]:
        failures.append(f"recorded_event_mismatch:{recorded['events']}")
    if recorded["result"][2] != {"recorded": True, "updates": {"s_lig": 150}}:
        failures.append(f"recorded_payload_mismatch:{recorded['result']}")
    if recorded["guidance_debug"].get("button_contract_updates") != {"s_lig": 150}:
        failures.append(f"recorded_debug_updates_mismatch:{recorded['guidance_debug']}")

    disabled = _run_case(
        "disabled_uses_existing_debug_payload",
        session_state={inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY: {"session_payload": True}},
        displayed_contract={},
        guidance_debug={
            "button_contract": {"family": "debug"},
            "design_guide_primary_apply_payload": {"debug_payload": True},
        },
        displayed_item={"title": "primary"},
        enabled=False,
    )
    if [event["event"] for event in disabled["events"]] != ["enabled"]:
        failures.append(f"disabled_event_mismatch:{disabled['events']}")
    if disabled["result"][0].get("family") != "debug":
        failures.append(f"disabled_contract_precedence_mismatch:{disabled['result']}")
    if disabled["result"][1] is not False:
        failures.append(f"disabled_enabled_flag_mismatch:{disabled['result']}")
    if disabled["result"][2] != {"debug_payload": True}:
        failures.append(f"disabled_payload_fallback_mismatch:{disabled['result']}")

    no_item = _run_case(
        "enabled_without_item_does_not_record",
        session_state={},
        displayed_contract={"enabled": True, "family": "bending"},
        guidance_debug={},
        displayed_item=None,
        enabled=True,
    )
    if [event["event"] for event in no_item["events"]] != ["enabled"]:
        failures.append(f"no_item_event_mismatch:{no_item['events']}")
    if no_item["result"][2] != {}:
        failures.append(f"no_item_payload_mismatch:{no_item['result']}")

    payload = {
        "verifier": "inputs_page_final_primary_contract_bundle_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Primary Contract Bundle Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` events: `{','.join(event['event'] for event in case['events'])}`" for case in cases),
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
