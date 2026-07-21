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
        f"inputs_page_final_visible_publication_resolution_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_visible_publication_resolution_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "session_state": inputs_page.st.session_state,
        "_attach_exact_low_util_evidence_to_visible_item": (
            inputs_page._attach_exact_low_util_evidence_to_visible_item
        ),
        "_build_design_guide_publication_context": (
            inputs_page._build_design_guide_publication_context
        ),
        "_build_design_guide_publication_dependencies": (
            inputs_page._build_design_guide_publication_dependencies
        ),
        "_final_visible_resolution_from_final_publication_authority": (
            inputs_page._final_visible_resolution_from_final_publication_authority
        ),
        "_stamp_design_guide_controller_trace_only_parity": (
            inputs_page._stamp_design_guide_controller_trace_only_parity
        ),
        "_record_design_guide_publication_snapshot": (
            inputs_page._record_design_guide_publication_snapshot
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def attach_exact(item, debug):
        events.append({"event": "attach_exact", "item": dict(item or {})})
        attached = dict(item or {})
        attached["attached_exact"] = True
        attached["debug_seen"] = dict(debug or {}).get("seed")
        return attached

    def build_context(state, overview, items):
        events.append(
            {
                "event": "build_context",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "item_count": len(list(items or [])),
            }
        )
        return {
            "state_D": dict(state or {}).get("D"),
            "overview_status": dict(overview or {}).get("status"),
            "item_count": len(list(items or [])),
        }

    def build_dependencies():
        events.append({"event": "build_dependencies"})
        return {"deps": True}

    def resolve_authority(*, item, overview, presentation, debug_sink, publication_reason):
        events.append(
            {
                "event": "resolve_authority",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "presentation": dict(presentation or {}),
                "publication_reason": publication_reason,
            }
        )
        debug_sink["final_publication_inner_authority"] = "resolver"
        return {
            "item": {"title_main": "Resolved", "from_item": dict(item or {})},
            "publication_hash": "hash-x",
            "display_hash": "display-x",
        }

    def stamp_trace(*, item, debug_sink, final_visible_resolution, publication_reason, expected_publication_hash):
        events.append(
            {
                "event": "stamp_trace",
                "item": dict(item or {}),
                "publication_reason": publication_reason,
                "expected_publication_hash": expected_publication_hash,
                "hash": dict(final_visible_resolution or {}).get("publication_hash"),
            }
        )
        debug_sink["design_guide_controller_trace_only_parity"] = {"ok": True}
        debug_sink["final_visible_resolution_trace"] = "trace-x"

    def record_snapshot(resolution, *, source, input_count, publication_context):
        events.append(
            {
                "event": "record_snapshot",
                "source": source,
                "input_count": input_count,
                "publication_context": dict(publication_context or {}),
                "hash": dict(resolution or {}).get("publication_hash"),
            }
        )

    def run_case(
        name: str,
        *,
        session_state: dict,
        guidance_items: list,
        guidance_debug: dict,
    ) -> dict:
        nonlocal events
        events = []
        inputs_page.st.session_state = dict(session_state or {})
        debug = dict(guidance_debug or {})
        result = inputs_page.render_design_guide_final_visible_publication_resolution_setup(
            guidance_items=list(guidance_items or []),
            guidance_debug=debug,
            current_state={"D": 500},
            dg_overview={"status": "FAIL"},
            dg_presentation={"headline": "Before"},
        )
        result_items, context, dependencies, resolution = result
        case = {
            "name": name,
            "items": result_items,
            "context": context,
            "dependencies": dependencies,
            "resolution": resolution,
            "debug": debug,
            "session": dict(inputs_page.st.session_state),
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._attach_exact_low_util_evidence_to_visible_item = attach_exact
        inputs_page._build_design_guide_publication_context = build_context
        inputs_page._build_design_guide_publication_dependencies = build_dependencies
        inputs_page._final_visible_resolution_from_final_publication_authority = resolve_authority
        inputs_page._stamp_design_guide_controller_trace_only_parity = stamp_trace
        inputs_page._record_design_guide_publication_snapshot = record_snapshot

        bundle_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY

        case = run_case(
            "creates_session_bundle_and_records_snapshot",
            session_state={},
            guidance_items=[{"title_main": "Visible"}],
            guidance_debug={"seed": 1},
        )
        bundle = dict(case["session"].get(bundle_key) or {})
        event_names = [event["event"] for event in case["events"]]
        expect(
            "creates_session_bundle_and_records_snapshot",
            case["items"][0].get("attached_exact") is True
            and case["context"] == {"state_D": 500, "overview_status": "FAIL", "item_count": 1}
            and case["dependencies"] == {"deps": True}
            and case["resolution"].get("publication_hash") == "hash-x"
            and bundle.get("seed") == 1
            and bundle.get("design_guide_controller_trace_only_parity") == {"ok": True}
            and bundle.get("final_visible_resolution_trace") == "trace-x"
            and bundle.get("design_guide_controller_trace_session_sync") is True
            and bundle.get("design_guide_controller_trace_session_sync_product_driving") is False
            and event_names == [
                "attach_exact",
                "build_context",
                "build_dependencies",
                "resolve_authority",
                "stamp_trace",
                "record_snapshot",
            ],
            f"case={case}",
        )

        case = run_case(
            "existing_session_bundle_setdefault_preserves_existing",
            session_state={bundle_key: {"seed": "existing"}},
            guidance_items=[{"title_main": "Visible"}],
            guidance_debug={"seed": "new", "design_guide_controller_existing": "value"},
        )
        bundle = dict(case["session"].get(bundle_key) or {})
        expect(
            "existing_session_bundle_setdefault_preserves_existing",
            bundle.get("seed") == "existing"
            and bundle.get("design_guide_controller_existing") == "value"
            and bundle.get("design_guide_controller_trace_only_parity") == {"ok": True},
            f"case={case}",
        )

        case = run_case(
            "skips_trace_stamp_when_trace_already_present",
            session_state={bundle_key: {}},
            guidance_items=[{"title_main": "Visible"}],
            guidance_debug={
                "design_guide_controller_trace_only_parity": {"existing": True},
            },
        )
        bundle = dict(case["session"].get(bundle_key) or {})
        event_names = [event["event"] for event in case["events"]]
        expect(
            "skips_trace_stamp_when_trace_already_present",
            "stamp_trace" not in event_names
            and bundle.get("design_guide_controller_trace_only_parity") == {"existing": True}
            and bundle.get("design_guide_controller_trace_session_sync") is True,
            f"case={case}",
        )

        case = run_case(
            "empty_items_resolution_still_records",
            session_state={},
            guidance_items=[],
            guidance_debug={},
        )
        event_names = [event["event"] for event in case["events"]]
        resolver_event = next(
            event for event in case["events"] if event["event"] == "resolve_authority"
        )
        snapshot_event = next(
            event for event in case["events"] if event["event"] == "record_snapshot"
        )
        expect(
            "empty_items_resolution_still_records",
            "attach_exact" not in event_names
            and resolver_event["item"] == {}
            and snapshot_event["input_count"] == 0
            and case["items"] == [],
            f"case={case}",
        )
    finally:
        inputs_page.st.session_state = originals["session_state"]
        inputs_page._attach_exact_low_util_evidence_to_visible_item = originals[
            "_attach_exact_low_util_evidence_to_visible_item"
        ]
        inputs_page._build_design_guide_publication_context = originals[
            "_build_design_guide_publication_context"
        ]
        inputs_page._build_design_guide_publication_dependencies = originals[
            "_build_design_guide_publication_dependencies"
        ]
        inputs_page._final_visible_resolution_from_final_publication_authority = originals[
            "_final_visible_resolution_from_final_publication_authority"
        ]
        inputs_page._stamp_design_guide_controller_trace_only_parity = originals[
            "_stamp_design_guide_controller_trace_only_parity"
        ]
        inputs_page._record_design_guide_publication_snapshot = originals[
            "_record_design_guide_publication_snapshot"
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
                "# Inputs Page Final Visible Publication Resolution Setup Verifier",
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
        print("FINAL_VISIBLE_PUBLICATION_RESOLUTION_SETUP_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("FINAL_VISIBLE_PUBLICATION_RESOLUTION_SETUP_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
