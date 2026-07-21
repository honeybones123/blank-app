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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_final_visible_item_binding_zero_shear_projection_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_visible_item_binding_zero_shear_projection_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "session_state": inputs_page.st.session_state,
        "_final_publication_projection_bypass_page_guard_inputs": (
            inputs_page._final_publication_projection_bypass_page_guard_inputs
        ),
        "_build_final_visible_render_binding_payload": (
            inputs_page._build_final_visible_render_binding_payload
        ),
        "_store_final_visible_compatibility_restamper_render_item_projection_debug": (
            inputs_page._store_final_visible_compatibility_restamper_render_item_projection_debug
        ),
        "_zero_shear_ligature_cleanup_contract_signal": (
            inputs_page._zero_shear_ligature_cleanup_contract_signal
        ),
        "_parse_util_value": inputs_page._parse_util_value,
        "_float_from_state": inputs_page._float_from_state,
        "_design_guide_cleanup_arrangement_label": (
            inputs_page._design_guide_cleanup_arrangement_label
        ),
        "_apply_final_design_guide_zero_shear_render_consumer_projection": (
            inputs_page._apply_final_design_guide_zero_shear_render_consumer_projection
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    binding_response: dict = {}
    ligature_signal = False

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def bypass_inputs(*, input_item, debug_sink):
        events.append(
            {
                "event": "bypass_inputs",
                "input_item": dict(input_item or {}),
                "debug_keys": sorted(str(key) for key in dict(debug_sink or {})),
            }
        )
        return {"bypass_guard": "ok"}

    def build_binding(**kwargs):
        events.append({"event": "build_binding", "kwargs": dict(kwargs)})
        return dict(binding_response or {})

    def store_projection(*, debug_sink, render_projection, callsite_id):
        events.append(
            {
                "event": "store_projection",
                "render_projection": dict(render_projection or {}),
                "callsite_id": callsite_id,
            }
        )
        debug_sink["stored_projection"] = dict(render_projection or {})

    def zero_shear_signal(state):
        events.append({"event": "zero_shear_signal", "state": dict(state or {})})
        return bool(ligature_signal)

    def parse_util(value):
        events.append({"event": "parse_util", "value": value})
        return float(value or 0.0)

    def float_from_state(state, key, default=None):
        events.append({"event": "float_from_state", "key": key})
        return dict(state or {}).get(key, default)

    def arrangement_label(family, state):
        events.append({"event": "arrangement_label", "family": family})
        return "no links"

    def zero_shear_projection(*, item, guidance_debug, session_debug, terminal_stop_row):
        events.append(
            {
                "event": "zero_shear_projection",
                "item": dict(item or {}),
                "guidance_debug": dict(guidance_debug or {}),
                "session_debug": dict(session_debug or {}) if isinstance(session_debug, dict) else None,
                "terminal_stop_row": dict(terminal_stop_row or {}),
            }
        )
        return {
            "item": {"title_main": "Zero projected", "design_guide_terminal_state": "optimal"},
            "guidance_debug": {"after_zero": True},
            "session_debug": {"session_after_zero": True},
        }

    def run_case(
        name: str,
        *,
        response: dict,
        resolution: dict,
        debug: dict,
        session_state: dict,
        state: dict | None = None,
        overview: dict | None = None,
        signal: bool = False,
    ) -> dict:
        nonlocal events, binding_response, ligature_signal
        events = []
        binding_response = dict(response or {})
        ligature_signal = bool(signal)
        inputs_page.st.session_state = dict(session_state or {})
        guidance_debug = dict(debug or {})
        item = inputs_page.render_design_guide_final_visible_item_binding_and_zero_shear_projection(
            final_visible_resolution=dict(resolution or {}),
            guidance_debug=guidance_debug,
            current_state=dict(state or {"uls_Vstar": 0.0, "load_Vstar_proxy": 0.0}),
            dg_overview=dict(overview or {"utils": {"shear": 0.0}}),
        )
        case = {
            "name": name,
            "item": item,
            "debug": guidance_debug,
            "session": dict(inputs_page.st.session_state),
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._final_publication_projection_bypass_page_guard_inputs = bypass_inputs
        inputs_page._build_final_visible_render_binding_payload = build_binding
        inputs_page._store_final_visible_compatibility_restamper_render_item_projection_debug = store_projection
        inputs_page._zero_shear_ligature_cleanup_contract_signal = zero_shear_signal
        inputs_page._parse_util_value = parse_util
        inputs_page._float_from_state = float_from_state
        inputs_page._design_guide_cleanup_arrangement_label = arrangement_label
        inputs_page._apply_final_design_guide_zero_shear_render_consumer_projection = zero_shear_projection

        bundle_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY

        case = run_case(
            "basic_binding_updates_debug",
            response={
                "item": {"title_main": "Bound", "design_guide_terminal_state": "review"},
                "debug_updates": {"binding_debug": True},
            },
            resolution={"item": {"title_main": "Input"}},
            debug={
                "final_visible_restamper_adapter_bypass_states": {
                    "render_fast_design_guidance_panel.final_visible_item_binding": {"previous": True}
                },
                "final_visible_contract_binding_adapter_cutovers": {"existing": True},
            },
            session_state={"pending_recommendation": {"id": "rec-1"}},
        )
        build_event = next(event for event in case["events"] if event["event"] == "build_binding")
        expect(
            "basic_binding_updates_debug",
            case["item"].get("title_main") == "Bound"
            and case["debug"].get("binding_debug") is True
            and build_event["kwargs"].get("callsite_id")
            == "render_fast_design_guidance_panel.final_visible_item_binding"
            and build_event["kwargs"].get("rec") == {"id": "rec-1"}
            and build_event["kwargs"].get("previous_adapter_state") == {"previous": True}
            and build_event["kwargs"].get("existing_cutover_traces") == {"existing": True}
            and build_event["kwargs"].get("bypass_guard") == "ok",
            f"case={case}",
        )

        case = run_case(
            "stores_projection_debug_when_requested",
            response={
                "item": {"title_main": "Projected", "design_guide_terminal_state": "review"},
                "debug_updates": {},
                "store_projection_debug": True,
                "render_projection": {"projection": "payload"},
            },
            resolution={"item": {"title_main": "Input"}},
            debug={},
            session_state={},
        )
        expect(
            "stores_projection_debug_when_requested",
            case["debug"].get("stored_projection") == {"projection": "payload"}
            and "store_projection" in [event["event"] for event in case["events"]],
            f"case={case}",
        )

        case = run_case(
            "applies_zero_shear_projection_and_replaces_debug_session",
            response={
                "item": {"title_main": "Zero", "design_guide_terminal_state": "optimal"},
                "debug_updates": {"before_zero": True},
            },
            resolution={
                "item": {"title_main": "Input"},
                "render_reason": "final_visible_zero_shear_demand_accepted",
            },
            debug={"seed": True},
            session_state={bundle_key: {"session_seed": True}},
            state={"uls_Vstar": 0.0, "load_Vstar_proxy": 0.0},
            overview={"utils": {"shear": 0.0}},
        )
        zero_event = next(
            event for event in case["events"] if event["event"] == "zero_shear_projection"
        )
        expect(
            "applies_zero_shear_projection_and_replaces_debug_session",
            case["item"].get("title_main") == "Zero projected"
            and case["debug"] == {"after_zero": True}
            and case["session"].get(bundle_key) == {"session_after_zero": True}
            and zero_event["terminal_stop_row"].get("attempted") is True
            and zero_event["terminal_stop_row"].get("current_arrangement_label") == "no links"
            and zero_event["terminal_stop_row"].get("failed_check_demand") == 0.0,
            f"case={case}",
        )

        case = run_case(
            "ligature_signal_skips_zero_shear_projection",
            response={
                "item": {"title_main": "Zero", "design_guide_terminal_state": "optimal"},
                "debug_updates": {"kept": True},
            },
            resolution={
                "item": {"title_main": "Input"},
                "render_reason": "final_visible_zero_shear_demand_accepted",
            },
            debug={},
            session_state={bundle_key: {"session_seed": True}},
            signal=True,
        )
        expect(
            "ligature_signal_skips_zero_shear_projection",
            case["item"].get("title_main") == "Zero"
            and case["debug"].get("kept") is True
            and "zero_shear_projection" not in [event["event"] for event in case["events"]],
            f"case={case}",
        )
    finally:
        inputs_page.st.session_state = originals["session_state"]
        inputs_page._final_publication_projection_bypass_page_guard_inputs = originals[
            "_final_publication_projection_bypass_page_guard_inputs"
        ]
        inputs_page._build_final_visible_render_binding_payload = originals[
            "_build_final_visible_render_binding_payload"
        ]
        inputs_page._store_final_visible_compatibility_restamper_render_item_projection_debug = originals[
            "_store_final_visible_compatibility_restamper_render_item_projection_debug"
        ]
        inputs_page._zero_shear_ligature_cleanup_contract_signal = originals[
            "_zero_shear_ligature_cleanup_contract_signal"
        ]
        inputs_page._parse_util_value = originals["_parse_util_value"]
        inputs_page._float_from_state = originals["_float_from_state"]
        inputs_page._design_guide_cleanup_arrangement_label = originals[
            "_design_guide_cleanup_arrangement_label"
        ]
        inputs_page._apply_final_design_guide_zero_shear_render_consumer_projection = originals[
            "_apply_final_design_guide_zero_shear_render_consumer_projection"
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
                "# Inputs Page Final Visible Item Binding Zero Shear Projection Verifier",
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
        print("FINAL_VISIBLE_ITEM_BINDING_ZERO_SHEAR_PROJECTION_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("FINAL_VISIBLE_ITEM_BINDING_ZERO_SHEAR_PROJECTION_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
