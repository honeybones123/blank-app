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
    json_path = ARTIFACT_DIR / f"inputs_page_displayed_primary_apply_payload_debug_publication_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_displayed_primary_apply_payload_debug_publication_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_record_rendered_design_guide_primary_apply_payload": inputs_page._record_rendered_design_guide_primary_apply_payload,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        item: dict | None,
        contract: dict,
        enabled: bool,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _contract_enabled(contract_arg):
            events.append({"event": "contract_enabled", "contract": dict(contract_arg or {})})
            return bool(enabled)

        def _record_payload(**kwargs):
            events.append(
                {
                    "event": "record_payload",
                    "item": dict(kwargs.get("item") or {}),
                    "rec": dict(kwargs.get("rec") or {}),
                    "button_contract": dict(kwargs.get("button_contract") or {}),
                    "state": dict(kwargs.get("state") or {}),
                }
            )
            return {"payload": True, "family": dict(kwargs.get("button_contract") or {}).get("family")}

        try:
            inputs_page.st = _FakeStreamlit({"pending_recommendation": {"pending": True}})
            inputs_page._design_guide_button_contract_enabled = _contract_enabled
            inputs_page._record_rendered_design_guide_primary_apply_payload = _record_payload
            out_debug = inputs_page.render_design_guide_displayed_primary_apply_payload_debug_publication(
                displayed_primary_item=None if item is None else dict(item),
                displayed_primary_button_contract=dict(contract),
                guidance_disp_state={"state": True},
                guidance_debug={"existing": True},
            )
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "debug": out_debug,
        }
        cases.append(case)
        return case

    enabled_case = _run_case(
        "enabled_dict_item",
        item={"id": "primary"},
        contract={
            "enabled": True,
            "family": "combined",
            "updates": {"D": 550},
            "preview_pass": True,
            "blocking_reason": "unit",
        },
        enabled=True,
    )
    if [event.get("event") for event in enabled_case["events"]] != ["contract_enabled", "record_payload"]:
        failures.append(f"enabled_events_mismatch:{enabled_case['events']}")
    expected_debug_subset = {
        "primary_button_contract": {
            "enabled": True,
            "family": "combined",
            "updates": {"D": 550},
            "preview_pass": True,
            "blocking_reason": "unit",
        },
        "button_contract_enabled": True,
        "button_contract_updates": {"D": 550},
        "button_contract_preview_pass": True,
        "button_contract_blocking_reason": "unit",
        "selected_action_type": "apply_resolved_candidate",
        "selected_action_family": "combined",
        "selected_action_updates": {"D": 550},
        "design_guide_primary_apply_payload": {"payload": True, "family": "combined"},
    }
    for key, expected in expected_debug_subset.items():
        if enabled_case["debug"].get(key) != expected:
            failures.append(f"enabled_debug_{key}_mismatch:{enabled_case['debug'].get(key)}")
    record_event = enabled_case["events"][1] if len(enabled_case["events"]) > 1 else {}
    if record_event.get("rec") != {"pending": True}:
        failures.append(f"enabled_pending_rec_mismatch:{record_event}")
    if record_event.get("state") != {"state": True}:
        failures.append(f"enabled_state_mismatch:{record_event}")

    disabled_case = _run_case(
        "disabled_contract_noop",
        item={"id": "primary"},
        contract={"enabled": False, "family": "bending"},
        enabled=False,
    )
    if [event.get("event") for event in disabled_case["events"]] != ["contract_enabled"]:
        failures.append(f"disabled_events_mismatch:{disabled_case['events']}")
    if disabled_case["debug"] != {"existing": True}:
        failures.append(f"disabled_debug_changed:{disabled_case['debug']}")

    none_item_case = _run_case(
        "none_item_noop",
        item=None,
        contract={"enabled": True, "family": "bending"},
        enabled=True,
    )
    if [event.get("event") for event in none_item_case["events"]] != ["contract_enabled"]:
        failures.append(f"none_item_events_mismatch:{none_item_case['events']}")
    if none_item_case["debug"] != {"existing": True}:
        failures.append(f"none_item_debug_changed:{none_item_case['debug']}")

    payload = {
        "verifier": "inputs_page_displayed_primary_apply_payload_debug_publication_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Displayed Primary Apply Payload Debug Publication Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` events: `{[event.get('event') for event in case['events']]}`"
                    for case in cases
                ),
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
