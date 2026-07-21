from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_click_bending_replacement_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_click_bending_replacement_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_build_final_design_guide_post_click_bending_replacement_audit_result_proof": (
            inputs_page._build_final_design_guide_post_click_bending_replacement_audit_result_proof
        ),
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_mode_config": inputs_page._design_mode_config,
        "_stamp_final_publication_post_click_low_bending_resolution_request_proof": (
            inputs_page._stamp_final_publication_post_click_low_bending_resolution_request_proof
        ),
        "_post_click_low_bending_resolution_item": inputs_page._post_click_low_bending_resolution_item,
        "_stamp_final_publication_post_click_low_bending_resolution_result_projection": (
            inputs_page._stamp_final_publication_post_click_low_bending_resolution_result_projection
        ),
        "_stamp_final_publication_post_click_low_bending_resolution_result_item_adapter": (
            inputs_page._stamp_final_publication_post_click_low_bending_resolution_result_item_adapter
        ),
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof": (
            inputs_page._stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof
        ),
        "_build_final_design_guide_post_click_final_contract_check_adapter_result": (
            inputs_page._build_final_design_guide_post_click_final_contract_check_adapter_result
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    audit_response: dict = {}
    resolution_response = None
    adapter_response: dict = {}
    exact_adapter_response: dict = {}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def audit_builder(**kwargs):
        events.append({"event": "audit_builder", "kwargs": dict(kwargs)})
        return dict(audit_response or {})

    def goal(state):
        events.append({"event": "goal", "state": dict(state or {})})
        return "goal-x"

    def mode_config(goal_value):
        events.append({"event": "mode_config", "goal": goal_value})
        return {"mode": goal_value}

    def request_proof(**kwargs):
        events.append({"event": "request_proof", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["request_seen"] = True

    def resolution_item(state, overview, config, audit, *, debug_sink):
        events.append(
            {
                "event": "resolution_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "config": dict(config or {}),
                "audit": dict(audit or {}),
            }
        )
        debug_sink["resolution_seen"] = True
        return dict(resolution_response) if isinstance(resolution_response, dict) else resolution_response

    def result_projection(**kwargs):
        events.append({"event": "result_projection", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["projection_seen_count"] = (
            int(kwargs["guidance_debug"].get("projection_seen_count") or 0) + 1
        )

    def result_item_adapter(**kwargs):
        events.append({"event": "result_item_adapter", "kwargs": dict(kwargs)})
        return dict(adapter_response or {})

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(dict(contract or {}).get("enabled"))

    def raw_bound(**kwargs):
        events.append({"event": "raw_bound", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["raw_bound_seen"] = True

    def exact_adapter(**kwargs):
        events.append({"event": "exact_adapter", "kwargs": dict(kwargs)})
        return dict(exact_adapter_response or {})

    def run_case(
        name: str,
        *,
        visible_action: bool,
        item: dict,
        resolution: dict,
        debug: dict,
        audit: dict,
        low_bending_resolution,
        adapter: dict,
        exact_adapter_result: dict,
    ) -> dict:
        nonlocal events, audit_response, resolution_response, adapter_response, exact_adapter_response
        events = []
        audit_response = dict(audit or {})
        resolution_response = (
            dict(low_bending_resolution)
            if isinstance(low_bending_resolution, dict)
            else low_bending_resolution
        )
        adapter_response = dict(adapter or {})
        exact_adapter_response = dict(exact_adapter_result or {})
        guidance_debug = dict(debug or {})
        final_resolution = dict(resolution or {})
        result = inputs_page.render_design_guide_post_click_bending_replacement_setup(
            post_click_bending_low_visible_action=bool(visible_action),
            final_visible_item=dict(item or {}),
            final_visible_resolution=final_resolution,
            guidance_debug=guidance_debug,
            current_state={"D": 500},
            dg_overview={"overview": True},
            last_apply_route_for_visible={"route": "last"},
        )
        (
            result_item,
            result_resolution,
            result_audit,
            result_bending_resolution,
            result_contract,
            replacement_applied,
            audit_sources,
        ) = result
        case = {
            "name": name,
            "item": _jsonable(result_item),
            "resolution": _jsonable(result_resolution),
            "audit": _jsonable(result_audit),
            "bending_resolution": _jsonable(result_bending_resolution),
            "contract": _jsonable(result_contract),
            "replacement_applied": replacement_applied,
            "audit_sources": _jsonable(audit_sources),
            "debug": _jsonable(guidance_debug),
            "events": _jsonable(list(events)),
        }
        cases.append(case)
        return case

    try:
        inputs_page._build_final_design_guide_post_click_bending_replacement_audit_result_proof = audit_builder
        inputs_page._design_optimisation_goal = goal
        inputs_page._design_mode_config = mode_config
        inputs_page._stamp_final_publication_post_click_low_bending_resolution_request_proof = request_proof
        inputs_page._post_click_low_bending_resolution_item = resolution_item
        inputs_page._stamp_final_publication_post_click_low_bending_resolution_result_projection = result_projection
        inputs_page._stamp_final_publication_post_click_low_bending_resolution_result_item_adapter = result_item_adapter
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof = raw_bound
        inputs_page._build_final_design_guide_post_click_final_contract_check_adapter_result = exact_adapter

        item = {
            "title_main": "Visible",
            "candidate_search_evidence": {"direct": True},
            "action_payload": {"candidate_search_evidence": {"payload": True}},
            "resolved_candidate": {"candidate_search_evidence": {"resolved": True}},
        }
        case = run_case(
            "visible_action_false_defaults_only",
            visible_action=False,
            item=item,
            resolution={"publication_hash": "hash-before"},
            debug={"seed": True},
            audit={"audit_projection": {"audit": True}, "audit_projection_hash": "audit-hash"},
            low_bending_resolution={"title_main": "Should not run"},
            adapter={},
            exact_adapter_result={},
        )
        expect(
            "visible_action_false_defaults_only",
            case["item"]["title_main"] == "Visible"
            and case["resolution"] == {"publication_hash": "hash-before"}
            and case["audit"] == {}
            and case["bending_resolution"] == {}
            and case["contract"] == {}
            and case["replacement_applied"] is False
            and case["audit_sources"][1] == {"direct": True}
            and case["events"] == [],
            f"case={case}",
        )

        case = run_case(
            "visible_action_adapted_enabled_contract",
            visible_action=True,
            item=item,
            resolution={"overview": {"source": "resolution"}},
            debug={"seed": True},
            audit={"audit_projection": {"audit": True}, "audit_projection_hash": "audit-hash"},
            low_bending_resolution={
                "title_main": "Raw resolution",
                "button_contract": {"enabled": True},
            },
            adapter={
                "adapted_item": {
                    "title_main": "Adapted resolution",
                    "button_contract": {"enabled": True, "family": "bending"},
                },
                "adapted_item_hash": "adapted-hash",
                "proof_hash": "proof-hash",
            },
            exact_adapter_result={},
        )
        event_names = [event["event"] for event in case["events"]]
        expect(
            "visible_action_adapted_enabled_contract",
            case["item"]["title_main"] == "Visible"
            and case["bending_resolution"]["title_main"] == "Adapted resolution"
            and case["contract"] == {"enabled": True, "family": "bending"}
            and case["replacement_applied"] is False
            and case["debug"].get("final_publication_post_click_bending_replacement_audit_merge_cutover_hash") == "audit-hash"
            and case["debug"].get("final_publication_post_click_low_bending_resolution_result_item_adapter_live_cutover_used") is True
            and case["debug"].get("projection_seen_count") == 2
            and "exact_adapter" not in event_names,
            f"case={case}",
        )

        case = run_case(
            "visible_action_disabled_contract_exact_replacement",
            visible_action=True,
            item=item,
            resolution={"overview": {"source": "resolution"}},
            debug={"seed": True},
            audit={"audit_projection": {"audit": True}, "audit_projection_hash": "audit-hash"},
            low_bending_resolution={
                "title_main": "Raw blocker",
                "button_contract": {"enabled": False},
            },
            adapter={},
            exact_adapter_result={
                "result": {
                    "replacement_item": {"title_main": "Exact replacement"},
                    "final_visible_resolution": {"publication_hash": "hash-after"},
                    "guidance_debug_patch": {"patched": True},
                    "replacement_applied": True,
                },
                "result_hash": "result-hash",
                "proof_hash": "exact-proof",
            },
        )
        event_names = [event["event"] for event in case["events"]]
        expect(
            "visible_action_disabled_contract_exact_replacement",
            case["item"] == {"title_main": "Exact replacement"}
            and case["resolution"] == {"publication_hash": "hash-after"}
            and case["contract"] == {"enabled": False}
            and case["replacement_applied"] is True
            and case["debug"].get("patched") is True
            and case["debug"].get("final_publication_post_click_final_contract_adapter_result_live_cutover_hash") == "result-hash"
            and case["debug"].get("final_publication_post_click_final_contract_adapter_result_live_cutover_apply_driving") is False
            and "raw_bound" in event_names
            and "exact_adapter" in event_names,
            f"case={case}",
        )
    finally:
        inputs_page._build_final_design_guide_post_click_bending_replacement_audit_result_proof = originals[
            "_build_final_design_guide_post_click_bending_replacement_audit_result_proof"
        ]
        inputs_page._design_optimisation_goal = originals["_design_optimisation_goal"]
        inputs_page._design_mode_config = originals["_design_mode_config"]
        inputs_page._stamp_final_publication_post_click_low_bending_resolution_request_proof = originals[
            "_stamp_final_publication_post_click_low_bending_resolution_request_proof"
        ]
        inputs_page._post_click_low_bending_resolution_item = originals[
            "_post_click_low_bending_resolution_item"
        ]
        inputs_page._stamp_final_publication_post_click_low_bending_resolution_result_projection = originals[
            "_stamp_final_publication_post_click_low_bending_resolution_result_projection"
        ]
        inputs_page._stamp_final_publication_post_click_low_bending_resolution_result_item_adapter = originals[
            "_stamp_final_publication_post_click_low_bending_resolution_result_item_adapter"
        ]
        inputs_page._design_guide_button_contract_enabled = originals[
            "_design_guide_button_contract_enabled"
        ]
        inputs_page._stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof = originals[
            "_stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof"
        ]
        inputs_page._build_final_design_guide_post_click_final_contract_check_adapter_result = originals[
            "_build_final_design_guide_post_click_final_contract_check_adapter_result"
        ]

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Click Bending Replacement Setup Verifier",
                "",
                f"Status: {payload['status']}",
                "",
                "## Cases",
                "",
                *[
                    f"- {case['name']}: {len(case['events'])} events"
                    for case in cases
                ],
                "",
                "## Artifacts",
                "",
                f"- JSON: `{json_path.relative_to(ROOT)}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print("POST_CLICK_BENDING_REPLACEMENT_SETUP_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("POST_CLICK_BENDING_REPLACEMENT_SETUP_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
