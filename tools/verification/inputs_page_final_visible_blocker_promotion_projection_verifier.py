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
        f"inputs_page_final_visible_blocker_promotion_projection_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_visible_blocker_promotion_projection_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_guide_item_is_visible_blocker": inputs_page._design_guide_item_is_visible_blocker,
        "_visible_safe_low_util_cleanup_action_from_evidence": (
            inputs_page._visible_safe_low_util_cleanup_action_from_evidence
        ),
        "_apply_final_design_guide_safe_low_util_promotion_projection": (
            inputs_page._apply_final_design_guide_safe_low_util_promotion_projection
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    visible_blocker = False
    action_response = None
    projection_response: dict = {}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def is_visible_blocker(item):
        events.append({"event": "is_visible_blocker", "item": dict(item or {})})
        return bool(visible_blocker)

    def safe_action(item, overview, state, *, debug_sink):
        events.append(
            {
                "event": "safe_action",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "state": dict(state or {}),
                "debug": dict(debug_sink or {}),
            }
        )
        return action_response

    def apply_projection(*, item, final_visible_resolution, guidance_debug, promoted_item):
        events.append(
            {
                "event": "apply_projection",
                "item": dict(item or {}),
                "final_visible_resolution": dict(final_visible_resolution or {}),
                "guidance_debug": dict(guidance_debug or {}),
                "promoted_item": dict(promoted_item or {}),
            }
        )
        return dict(projection_response or {})

    def run_case(
        name: str,
        *,
        item: dict,
        resolution: dict,
        debug: dict,
        blocker: bool,
        action,
        projection: dict | None = None,
    ) -> dict:
        nonlocal events, visible_blocker, action_response, projection_response
        events = []
        visible_blocker = bool(blocker)
        action_response = action
        projection_response = dict(projection or {})
        result_debug = dict(debug or {})
        result_resolution = dict(resolution or {})
        result_item, returned_resolution = (
            inputs_page.render_design_guide_final_visible_blocker_promotion_projection(
                final_visible_item=dict(item or {}),
                final_visible_resolution=result_resolution,
                guidance_debug=result_debug,
                dg_overview={"status": "FAIL"},
                current_state={"D": 500},
            )
        )
        case = {
            "name": name,
            "item": result_item,
            "resolution": returned_resolution,
            "debug": result_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._design_guide_item_is_visible_blocker = is_visible_blocker
        inputs_page._visible_safe_low_util_cleanup_action_from_evidence = safe_action
        inputs_page._apply_final_design_guide_safe_low_util_promotion_projection = apply_projection

        case = run_case(
            "non_blocker_skips_promotion",
            item={"title_main": "Visible"},
            resolution={"publication_hash": "hash-before"},
            debug={"seed": True},
            blocker=False,
            action={"title_main": "Should not use"},
        )
        expect(
            "non_blocker_skips_promotion",
            case["item"] == {"title_main": "Visible"}
            and case["resolution"] == {"publication_hash": "hash-before"}
            and case["debug"] == {"seed": True}
            and [event["event"] for event in case["events"]] == ["is_visible_blocker"],
            f"case={case}",
        )

        case = run_case(
            "blocker_without_safe_action_skips_projection",
            item={"title_main": "Blocked"},
            resolution={"publication_hash": "hash-before"},
            debug={"seed": True},
            blocker=True,
            action=None,
        )
        expect(
            "blocker_without_safe_action_skips_projection",
            case["item"] == {"title_main": "Blocked"}
            and case["resolution"] == {"publication_hash": "hash-before"}
            and case["debug"] == {"seed": True}
            and [event["event"] for event in case["events"]]
            == ["is_visible_blocker", "safe_action"],
            f"case={case}",
        )

        case = run_case(
            "blocker_with_safe_action_applies_projection",
            item={"title_main": "Blocked"},
            resolution={"publication_hash": "hash-before"},
            debug={"seed": True},
            blocker=True,
            action={"title_main": "Promoted action"},
            projection={
                "item": {"title_main": "Promoted visible"},
                "final_visible_resolution": {"publication_hash": "hash-after"},
                "guidance_debug": {"promoted": True},
            },
        )
        projection_event = next(
            event for event in case["events"] if event["event"] == "apply_projection"
        )
        expect(
            "blocker_with_safe_action_applies_projection",
            case["item"] == {"title_main": "Promoted visible"}
            and case["resolution"] == {"publication_hash": "hash-after"}
            and case["debug"] == {"promoted": True}
            and projection_event["item"] == {"title_main": "Blocked"}
            and projection_event["final_visible_resolution"] == {"publication_hash": "hash-before"}
            and projection_event["guidance_debug"] == {"seed": True}
            and projection_event["promoted_item"] == {"title_main": "Promoted action"},
            f"case={case}",
        )
    finally:
        inputs_page._design_guide_item_is_visible_blocker = originals[
            "_design_guide_item_is_visible_blocker"
        ]
        inputs_page._visible_safe_low_util_cleanup_action_from_evidence = originals[
            "_visible_safe_low_util_cleanup_action_from_evidence"
        ]
        inputs_page._apply_final_design_guide_safe_low_util_promotion_projection = originals[
            "_apply_final_design_guide_safe_low_util_promotion_projection"
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
                "# Inputs Page Final Visible Blocker Promotion Projection Verifier",
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
        print("FINAL_VISIBLE_BLOCKER_PROMOTION_PROJECTION_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("FINAL_VISIBLE_BLOCKER_PROMOTION_PROJECTION_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
