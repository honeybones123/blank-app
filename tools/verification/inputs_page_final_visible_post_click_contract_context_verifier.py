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
    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_final_visible_post_click_contract_context_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_visible_post_click_contract_context_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "session_state": inputs_page.st.session_state,
        "_parse_util_value": inputs_page._parse_util_value,
        "_float_from_state": inputs_page._float_from_state,
        "_stamp_final_publication_render_item_consumer_proof": (
            inputs_page._stamp_final_publication_render_item_consumer_proof
        ),
        "_stamp_final_publication_post_click_contract_check_input_proof": (
            inputs_page._stamp_final_publication_post_click_contract_check_input_proof
        ),
        "_stamp_final_publication_post_click_final_contract_predicate_result_adapter": (
            inputs_page._stamp_final_publication_post_click_final_contract_predicate_result_adapter
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    predicate_response: dict = {}
    contract_proof_response: dict = {}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def parse_util(value):
        events.append({"event": "parse_util", "value": value})
        if value is None:
            return None
        return float(value)

    def float_from_state(state, key, default=None):
        events.append({"event": "float_from_state", "key": key})
        return dict(state or {}).get(key, default)

    def consumer_proof(*, item, final_visible_resolution, guidance_debug, design_brain_result, publication_reason):
        events.append(
            {
                "event": "consumer_proof",
                "item": dict(item or {}),
                "final_visible_resolution": dict(final_visible_resolution or {}),
                "design_brain_result": dict(design_brain_result or {}),
                "publication_reason": publication_reason,
            }
        )
        guidance_debug["consumer_proof_seen"] = True

    def contract_input_proof(**kwargs):
        events.append({"event": "contract_input_proof", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["contract_input_seen"] = True
        return dict(contract_proof_response or {})

    def predicate_adapter(**kwargs):
        events.append({"event": "predicate_adapter", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["predicate_adapter_seen"] = True
        return dict(predicate_response or {})

    def run_case(
        name: str,
        *,
        session_state: dict,
        item: dict,
        resolution: dict,
        debug: dict,
        overview: dict,
        audit: dict | None,
        state: dict,
        predicate: dict,
        proof: dict,
    ) -> dict:
        nonlocal events, predicate_response, contract_proof_response
        events = []
        predicate_response = dict(predicate or {})
        contract_proof_response = dict(proof or {})
        inputs_page.st.session_state = dict(session_state or {})
        guidance_debug = dict(debug or {})
        context = inputs_page.render_design_guide_final_visible_post_click_contract_context(
            final_visible_item=dict(item or {}),
            final_visible_resolution=dict(resolution or {}),
            guidance_debug=guidance_debug,
            dg_overview=dict(overview or {}),
            current_state=dict(state or {}),
            post_cleanup_render_audit=dict(audit) if isinstance(audit, dict) else audit,
        )
        case = {
            "name": name,
            "context": _jsonable(context),
            "debug": _jsonable(guidance_debug),
            "events": _jsonable(list(events)),
        }
        cases.append(case)
        return case

    try:
        inputs_page._parse_util_value = parse_util
        inputs_page._float_from_state = float_from_state
        inputs_page._stamp_final_publication_render_item_consumer_proof = consumer_proof
        inputs_page._stamp_final_publication_post_click_contract_check_input_proof = contract_input_proof
        inputs_page._stamp_final_publication_post_click_final_contract_predicate_result_adapter = predicate_adapter

        last_route_key = inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY
        binding_audit_key = inputs_page.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY
        shear_update_key = sorted(inputs_page._COMPOUND_SHEAR_UPDATE_KEYS)[0]

        case = run_case(
            "session_route_cleanup_predicates_stamp_debug",
            session_state={
                last_route_key: {
                    "apply_used_resolved_candidate_payload": True,
                    "applied_updates": {"D": 550},
                    "resolved_candidate_label": "safe cleanup step",
                },
                binding_audit_key: {"applied_updates": {shear_update_key: 0}},
            },
            item={
                "family": "Bending",
                "expected_util": "0.82",
                "button_contract": {"family": "shear", "enabled": True},
            },
            resolution={
                "overview": {"utils": {"bending": "0.72"}},
                "design_brain_result": {"from_resolution": True},
            },
            debug={
                "design_brain_result": {"from_debug": True},
                "post_click_unresolved_low_util_families": ["Shear"],
                "post_click_families_below_final_threshold": ["torsion"],
            },
            overview={"utils": {"bending": "0.90"}},
            audit={
                "post_click_unresolved_low_util_families": ["bending"],
                "post_click_families_below_final_threshold": ["Shear"],
            },
            state={"lig_d": 0, "lig_legs": 0},
            predicate={
                "predicate_result": {
                    "contract_enabled": True,
                    "exact_blocker_on_visible_item": True,
                    "requires_exact_blocker": False,
                    "visible_action": True,
                },
                "predicate_result_hash": "predicate-hash",
            },
            proof={"proof": "ok"},
        )
        contract_event = next(event for event in case["events"] if event["event"] == "contract_input_proof")
        predicate_event = next(event for event in case["events"] if event["event"] == "predicate_adapter")
        expect(
            "session_route_cleanup_predicates_stamp_debug",
            case["context"]["final_family_for_post_click"] == "bending"
            and case["context"]["final_expected_util_for_post_click"] == 0.82
            and case["context"]["final_current_bending_util_for_post_click"] == 0.72
            and case["context"]["post_click_unresolved_families_for_visible"] == ["bending", "shear"]
            and case["context"]["post_click_below_floor_families_for_visible"] == ["shear", "torsion"]
            and case["context"]["same_flow_cleanup_apply_for_visible"] is True
            and case["context"]["binding_audit_for_visible"] == {}
            and case["context"]["post_click_bending_low_visible_action"] is True
            and case["debug"].get("final_publication_post_click_final_contract_predicate_result_live_cutover_hash") == "predicate-hash"
            and case["debug"].get("final_publication_post_click_final_contract_predicate_result_product_behavior_changed") is False
            and contract_event["kwargs"]["primary_payload_binding_audit"] == {}
            and predicate_event["kwargs"]["last_apply_route"]["resolved_candidate_label"] == "safe cleanup step",
            f"case={case}",
        )

        case = run_case(
            "guidance_route_binding_audit_sets_same_flow",
            session_state={
                binding_audit_key: {"applied_updates": {shear_update_key: 0}},
            },
            item={
                "check_key": "Shear",
                "util": "0.58",
                "button_contract": {"family": "shear"},
            },
            resolution={},
            debug={
                "post_cleanup_acceptance_probe": {
                    "last_apply_route": {
                        "apply_used_resolved_candidate_payload": False,
                        "applied_updates": {},
                        "resolved_candidate_label": "other step",
                    }
                }
            },
            overview={"utils": {"bending": "0.63"}},
            audit={},
            state={"lig_d": 0, "lig_legs": 0},
            predicate={"predicate_result": {}, "predicate_result_hash": "empty"},
            proof={"proof": "binding"},
        )
        expect(
            "guidance_route_binding_audit_sets_same_flow",
            case["context"]["final_family_for_post_click"] == "shear"
            and case["context"]["same_flow_cleanup_apply_for_visible"] is True
            and case["context"]["binding_audit_for_visible"] == {"applied_updates": {shear_update_key: 0}}
            and case["context"]["last_apply_route_for_visible"]["resolved_candidate_label"] == "other step"
            and "final_publication_post_click_final_contract_predicate_result_live_cutover_used"
            not in case["debug"],
            f"case={case}",
        )

        case = run_case(
            "post_cleanup_route_fallback_no_binding_no_predicates",
            session_state={},
            item={
                "displayed_util": "0.91",
                "button_contract": {"family": "serviceability"},
            },
            resolution={},
            debug={},
            overview={"utils": {"bending": "0.77"}},
            audit={
                "last_apply_route": {
                    "apply_used_resolved_candidate_payload": True,
                    "applied_updates": {"D": 510},
                    "post_apply_resolved_candidate_label": "strength adjustment",
                }
            },
            state={"lig_d": 10, "lig_legs": 2},
            predicate={},
            proof={"proof": "fallback"},
        )
        expect(
            "post_cleanup_route_fallback_no_binding_no_predicates",
            case["context"]["final_family_for_post_click"] == "serviceability"
            and case["context"]["final_expected_util_for_post_click"] == 0.91
            and case["context"]["final_current_bending_util_for_post_click"] == 0.77
            and case["context"]["same_flow_cleanup_apply_for_visible"] is False
            and case["context"]["last_apply_route_for_visible"]["post_apply_resolved_candidate_label"]
            == "strength adjustment"
            and case["debug"].get("consumer_proof_seen") is True
            and case["debug"].get("contract_input_seen") is True
            and case["debug"].get("predicate_adapter_seen") is True,
            f"case={case}",
        )
    finally:
        inputs_page.st.session_state = originals["session_state"]
        inputs_page._parse_util_value = originals["_parse_util_value"]
        inputs_page._float_from_state = originals["_float_from_state"]
        inputs_page._stamp_final_publication_render_item_consumer_proof = originals[
            "_stamp_final_publication_render_item_consumer_proof"
        ]
        inputs_page._stamp_final_publication_post_click_contract_check_input_proof = originals[
            "_stamp_final_publication_post_click_contract_check_input_proof"
        ]
        inputs_page._stamp_final_publication_post_click_final_contract_predicate_result_adapter = originals[
            "_stamp_final_publication_post_click_final_contract_predicate_result_adapter"
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
                "# Inputs Page Final Visible Post Click Contract Context Verifier",
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
        print("FINAL_VISIBLE_POST_CLICK_CONTRACT_CONTEXT_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("FINAL_VISIBLE_POST_CLICK_CONTRACT_CONTEXT_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
