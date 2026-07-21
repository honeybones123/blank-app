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
    json_path = ARTIFACT_DIR / f"inputs_page_primary_intent_display_truth_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_intent_display_truth_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_guidance_intent_debug_rows": inputs_page._design_guide_guidance_intent_debug_rows,
        "_parse_util_value": inputs_page._parse_util_value,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for original_name, original_value in originals.items():
            setattr(inputs_page, original_name, original_value)

    def _run_case(
        name: str,
        *,
        guidance_items: list[dict],
        button_enabled: bool = True,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        debug: dict[str, Any] = {"existing": True}

        def _intent_rows(items):
            events.append("intent_rows")
            return [{"title": dict(item).get("title_main"), "intent": dict(item).get("guidance_intent")} for item in items]

        def _parse(value):
            events.append(f"parse:{value}")
            if value is None:
                return None
            if isinstance(value, str) and value.endswith("%"):
                return float(value[:-1]) / 100.0
            return float(value)

        def _enabled(contract):
            events.append("button_enabled")
            return button_enabled

        try:
            inputs_page._design_guide_guidance_intent_debug_rows = _intent_rows
            inputs_page._parse_util_value = _parse
            inputs_page._design_guide_button_contract_enabled = _enabled

            out_debug, out_items = inputs_page.render_design_guide_primary_intent_display_truth(
                guidance_items=[dict(item) for item in guidance_items],
                guidance_debug=debug,
                stage=lambda label: stages.append(str(label)),
            )
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "debug": out_debug,
            "items": out_items,
        }
        cases.append(case)
        return case

    no_items = _run_case("no_items", guidance_items=[])
    if no_items["events"] != ["intent_rows", "parse:None"]:
        failures.append(f"no_items_events_mismatch:{no_items['events']}")
    if no_items["stages"] != ["after_intent_debug_rows"]:
        failures.append(f"no_items_stage_mismatch:{no_items['stages']}")
    if no_items["debug"].get("primary_guidance_intent") is not None:
        failures.append(f"no_items_intent_mismatch:{no_items['debug'].get('primary_guidance_intent')}")
    if no_items["debug"].get("primary_button_contract") != {} or no_items["debug"].get("primary_display_truth") != {}:
        failures.append(f"no_items_primary_payload_mismatch:{no_items['debug']}")

    preview_pass = _run_case(
        "enabled_preview_pass",
        guidance_items=[
            {
                "title_main": "Primary",
                "guidance_intent": "efficiency_tightening",
                "button_contract": {"expected_util": "85%", "preview_pass": True},
                "display_truth": {"target_low": "80%", "target_high": "90%", "existing_truth": True},
            }
        ],
    )
    if preview_pass["events"] != ["intent_rows", "parse:85%", "button_enabled", "parse:80%", "parse:90%"]:
        failures.append(f"preview_pass_events_mismatch:{preview_pass['events']}")
    truth = dict(preview_pass["debug"].get("primary_display_truth") or {})
    if truth.get("display_truth_source") != "candidate_preview":
        failures.append(f"preview_pass_source_mismatch:{truth}")
    if truth.get("displayed_util") != 0.85 or truth.get("source_candidate_util") != 0.85:
        failures.append(f"preview_pass_util_mismatch:{truth}")
    if truth.get("displayed_status") != "PASS" or truth.get("displayed_within_target_band") is not True:
        failures.append(f"preview_pass_status_mismatch:{truth}")
    item_truth = dict(preview_pass["items"][0].get("display_truth") or {})
    if item_truth != truth or preview_pass["items"][0].get("displayed_util") != 0.85:
        failures.append(f"preview_pass_item_truth_mismatch:{preview_pass['items'][0]}")

    preview_blocked = _run_case(
        "enabled_preview_blocked_default_band",
        guidance_items=[
            {
                "title_main": "Primary",
                "guidance_intent": "required_fix",
                "button_contract": {"expected_util": 0.7, "preview_pass": False},
                "display_truth": {},
            }
        ],
    )
    blocked_truth = dict(preview_blocked["debug"].get("primary_display_truth") or {})
    if blocked_truth.get("displayed_status") != "PREVIEW_BLOCKED":
        failures.append(f"preview_blocked_status_mismatch:{blocked_truth}")
    if blocked_truth.get("displayed_within_target_band") is not False:
        failures.append(f"preview_blocked_band_mismatch:{blocked_truth}")

    disabled = _run_case(
        "disabled_contract_no_truth_override",
        guidance_items=[
            {
                "title_main": "Primary",
                "guidance_intent": "specific_blocker",
                "button_contract": {"expected_util": 0.85, "preview_pass": True},
                "display_truth": {"displayed_status": "BLOCKED"},
            }
        ],
        button_enabled=False,
    )
    if disabled["events"] != ["intent_rows", "parse:0.85", "button_enabled"]:
        failures.append(f"disabled_events_mismatch:{disabled['events']}")
    if disabled["debug"].get("primary_display_truth") != {"displayed_status": "BLOCKED"}:
        failures.append(f"disabled_truth_mismatch:{disabled['debug'].get('primary_display_truth')}")
    if disabled["items"][0].get("displayed_util") is not None:
        failures.append(f"disabled_item_mutated:{disabled['items'][0]}")

    payload = {
        "verifier": "inputs_page_primary_intent_display_truth_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Intent Display Truth Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` events: `{case['events']}`, stages: `{case['stages']}`" for case in cases),
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
