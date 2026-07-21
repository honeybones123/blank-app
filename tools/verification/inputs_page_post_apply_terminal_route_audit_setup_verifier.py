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
        f"inputs_page_post_apply_terminal_route_audit_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_apply_terminal_route_audit_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_post_apply_active_repair_required_checks_terminal_ready": (
            inputs_page._post_apply_active_repair_required_checks_terminal_ready
        ),
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    route_ready_response = False
    overview_acceptable_response = True

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def route_ready(route, state, *, allowed_families):
        events.append(
            {
                "event": "route_ready",
                "route": dict(route or {}),
                "state": dict(state or {}),
                "allowed_families": sorted(str(family) for family in allowed_families),
            }
        )
        return bool(route_ready_response)

    def overview_acceptable(overview):
        events.append({"event": "overview_acceptable", "overview": dict(overview or {})})
        return bool(overview_acceptable_response)

    def run_case(
        name: str,
        *,
        route: dict | None = None,
        post_active: bool = True,
        cleanup_audit: dict | None = None,
        dg_overview: dict | None = None,
        debug: dict | None = None,
        state: dict | None = None,
        ready: bool = False,
        acceptable: bool = True,
    ) -> dict:
        nonlocal events, route_ready_response, overview_acceptable_response
        events = []
        route_ready_response = bool(ready)
        overview_acceptable_response = bool(acceptable)
        result = inputs_page.render_design_guide_post_apply_terminal_route_audit_setup(
            post_apply_terminal_route=dict(route or {}),
            post_active_failure_repair_render=post_active,
            post_cleanup_render_audit=dict(cleanup_audit or {}),
            dg_overview=dict(dg_overview or {}),
            guidance_debug=dict(debug or {}),
            guidance_disp_state=dict(state or {}),
        )
        overview, route_overview, route_ready_result, audit = result
        case = {
            "name": name,
            "overview": overview,
            "route_overview": route_overview,
            "route_ready": route_ready_result,
            "audit": audit,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._post_apply_active_repair_required_checks_terminal_ready = route_ready
        inputs_page._overview_required_checks_acceptable = overview_acceptable

        route_overview = {"all_key_pass": True, "any_fail": False, "worst_util": 0.91}
        case = run_case(
            "ready_passing_route_overrides_overview_and_synthesizes_audit",
            route={"post_apply_overview": dict(route_overview), "family": "bending"},
            dg_overview={"source": "dg"},
            debug={"overview": {"source": "debug"}},
            ready=True,
            acceptable=True,
        )
        event_names = [event["event"] for event in case["events"]]
        expect(
            "ready_passing_route_overrides_overview_and_synthesizes_audit",
            case["overview"] == route_overview
            and case["route_overview"] == route_overview
            and case["route_ready"] is True
            and case["audit"]["post_click_accepted_green_valid"] is True
            and case["audit"]["terminal_state_source"] == "last_apply_route_post_apply_overview"
            and event_names == ["route_ready", "overview_acceptable"],
            f"case={case}",
        )
        expect(
            "ready_passing_route_allowed_families",
            {"bending", "shear", "combined", "geometry"}.issubset(
                set(case["events"][0]["allowed_families"])
            ),
            f"case={case}",
        )

        existing_audit = {"existing": True}
        case = run_case(
            "existing_cleanup_audit_is_preserved",
            route={"post_apply_overview": dict(route_overview)},
            cleanup_audit=dict(existing_audit),
            ready=True,
            acceptable=True,
        )
        expect(
            "existing_cleanup_audit_is_preserved",
            case["audit"] == existing_audit
            and [event["event"] for event in case["events"]] == ["route_ready"],
            f"case={case}",
        )

        case = run_case(
            "route_not_ready_preserves_debug_overview",
            route={"post_apply_overview": dict(route_overview)},
            dg_overview={"source": "dg"},
            debug={"overview": {"source": "debug"}},
            ready=False,
            acceptable=True,
        )
        expect(
            "route_not_ready_preserves_debug_overview",
            case["overview"] == {"source": "debug"}
            and case["route_ready"] is False
            and case["audit"] == {}
            and [event["event"] for event in case["events"]] == ["route_ready"],
            f"case={case}",
        )

        case = run_case(
            "unacceptable_required_checks_blocks_synthesized_audit",
            route={"post_apply_overview": dict(route_overview)},
            dg_overview={"source": "dg"},
            debug={},
            ready=True,
            acceptable=False,
        )
        expect(
            "unacceptable_required_checks_blocks_synthesized_audit",
            case["overview"] == route_overview
            and case["audit"] == {}
            and [event["event"] for event in case["events"]] == ["route_ready", "overview_acceptable"],
            f"case={case}",
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "cases": cases,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Apply Terminal Route Audit Setup Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Cases",
                "",
                *[f"- `{case['name']}`" for case in cases],
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": payload["verdict"],
                "json": str(json_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
