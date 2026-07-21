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
    json_path = ARTIFACT_DIR / f"inputs_page_specific_blocker_proof_materialization_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_specific_blocker_proof_materialization_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_parse_util_value": inputs_page._parse_util_value,
        "_guidance_item": inputs_page._guidance_item,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for original_name, original_value in originals.items():
            setattr(inputs_page, original_name, original_value)
        try:
            inputs_page.st.session_state.pop(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY, None)
        except Exception:
            pass

    def _run_case(
        name: str,
        *,
        guidance_items: list[dict],
        guidance_debug: dict[str, Any],
        session_debug: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _parse(value):
            events.append({"event": "parse", "value": value})
            if value is None:
                return None
            if isinstance(value, str) and value.endswith("%"):
                return float(value[:-1]) / 100.0
            return float(value)

        def _guidance_item(*args, **kwargs):
            events.append(
                {
                    "event": "guidance_item",
                    "family": args[0],
                    "title": args[1],
                    "reason": args[2],
                    "status": kwargs.get("status"),
                    "util": kwargs.get("util"),
                }
            )
            return {
                "family": args[0],
                "title_main": args[1],
                "body": args[2],
                "status": kwargs.get("status"),
                "util": kwargs.get("util"),
            }

        try:
            inputs_page._parse_util_value = _parse
            inputs_page._guidance_item = _guidance_item
            if session_debug is not None:
                inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = dict(session_debug)
            else:
                inputs_page.st.session_state.pop(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY, None)

            out_debug, out_items = inputs_page.render_design_guide_specific_blocker_proof_materialization(
                guidance_items=[dict(item) for item in guidance_items],
                guidance_debug=dict(guidance_debug),
            )
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "debug": out_debug,
            "items": out_items,
        }
        cases.append(case)
        return case

    non_empty = _run_case(
        "non_empty_noop",
        guidance_items=[{"title_main": "existing"}],
        guidance_debug={"primary_guidance_intent": "specific_blocker", "exact_blockers_by_family": {"bending": {}}},
    )
    if non_empty["events"]:
        failures.append(f"non_empty_events_mismatch:{non_empty['events']}")
    if non_empty["items"] != [{"title_main": "existing"}]:
        failures.append(f"non_empty_items_mismatch:{non_empty['items']}")
    if non_empty["debug"].get("specific_blocker_materialized_from_proof"):
        failures.append(f"non_empty_materialized:{non_empty['debug']}")

    empty_no_proof = _run_case(
        "empty_no_proof_noop",
        guidance_items=[],
        guidance_debug={"primary_guidance_intent": "specific_blocker"},
    )
    if empty_no_proof["events"] or empty_no_proof["items"]:
        failures.append(f"empty_no_proof_mismatch:{empty_no_proof}")
    if empty_no_proof["debug"].get("specific_blocker_materialized_from_proof"):
        failures.append(f"empty_no_proof_materialized:{empty_no_proof['debug']}")

    local = _run_case(
        "local_specific_blocker_materialized",
        guidance_items=[],
        guidance_debug={
            "primary_guidance_intent": "specific_blocker",
            "primary_card_title": "Cleanup blocked by stale title",
            "primary_button_contract": {
                "enabled": False,
                "family": "shear",
                "blocking_reason": "contract reason",
                "source_candidate_id": "old",
            },
            "post_click_exact_blockers_by_family": {
                "shear": {"current_util": "74%", "reason": "blocker reason"},
            },
            "primary_display_truth": {"displayed_status": "BLOCKED"},
            "safe_local_cleanup_count": 2,
            "candidate_search_evidence": {"source": "local"},
        },
    )
    if [event["event"] for event in local["events"]] != ["parse", "guidance_item"]:
        failures.append(f"local_events_mismatch:{local['events']}")
    if local["items"][0].get("family") != "shear":
        failures.append(f"local_family_mismatch:{local['items']}")
    if local["items"][0].get("title_main") != "Shear cleanup blocked by exact engineering limit":
        failures.append(f"local_title_mismatch:{local['items'][0].get('title_main')}")
    local_contract = dict(local["items"][0].get("button_contract") or {})
    if local_contract.get("enabled") is not False or local_contract.get("family") != "shear":
        failures.append(f"local_contract_mismatch:{local_contract}")
    if local_contract.get("blocking_reason") != "contract reason" or local_contract.get("source_candidate_id") != "old":
        failures.append(f"local_contract_preserve_mismatch:{local_contract}")
    if local["debug"].get("specific_blocker_materialized_from_proof") is not True:
        failures.append(f"local_materialized_missing:{local['debug']}")
    if local["debug"].get("button_contract_enabled") is not False or local["debug"].get("button_contract_updates") != {}:
        failures.append(f"local_debug_contract_mismatch:{local['debug']}")

    session = _run_case(
        "session_specific_blocker_merged",
        guidance_items=[],
        guidance_debug={"primary_card_title": "Local overlay", "safe_local_cleanup_count": 3},
        session_debug={
            "primary_card_intent": "specific_blocker",
            "button_contract": {"enabled": False, "family": "bending"},
            "exact_blockers_by_family": {"bending": {"failed_check_util": 0.76, "reason": "session blocker"}},
            "primary_display_truth": {"display_truth_source": "session_truth"},
            "cleanup_evidence_by_family": {"bending": {"searched": True}},
        },
    )
    if session["items"][0].get("family") != "bending":
        failures.append(f"session_family_mismatch:{session['items']}")
    if session["items"][0].get("title_main") != "Local overlay":
        failures.append(f"session_title_overlay_missing:{session['items'][0].get('title_main')}")
    if session["items"][0].get("cleanup_evidence_by_family") != {"bending": {"searched": True}}:
        failures.append(f"session_cleanup_evidence_mismatch:{session['items'][0].get('cleanup_evidence_by_family')}")
    if session["debug"].get("safe_local_cleanup_count") != 3:
        failures.append(f"session_local_overlay_count_mismatch:{session['debug']}")

    invalid_family = _run_case(
        "invalid_family_falls_back_to_general",
        guidance_items=[],
        guidance_debug={
            "primary_guidance_intent": "specific_blocker",
            "button_contract": {"enabled": False, "family": "unknown"},
            "exact_blockers_by_family": {"unknown": {"current_util": 0.8, "reason": "unknown reason"}},
        },
    )
    if invalid_family["items"][0].get("family") != "general":
        failures.append(f"invalid_family_not_general:{invalid_family['items']}")
    if invalid_family["items"][0].get("title_main") != "Design cleanup blocked by exact engineering limit":
        failures.append(f"invalid_family_title_mismatch:{invalid_family['items'][0].get('title_main')}")
    invalid_contract = dict(invalid_family["items"][0].get("button_contract") or {})
    if invalid_contract.get("family") != "unknown":
        failures.append(f"invalid_family_contract_mismatch:{invalid_contract}")

    payload = {
        "verifier": "inputs_page_specific_blocker_proof_materialization_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Specific Blocker Proof Materialization Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` events: `{[event['event'] for event in case['events']]}`, item_count: `{len(case['items'])}`"
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
