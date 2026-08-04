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
        f"inputs_page_terminal_exact_blocker_render_reconciliation_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_terminal_exact_blocker_render_reconciliation_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    session_key = inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY
    original_exact_filter = inputs_page._accepted_green_exact_blockers_by_family
    original_session_present = session_key in inputs_page.st.session_state
    original_session_value = inputs_page.st.session_state.get(session_key)

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def exact_filter(source):
        source_dict = dict(source or {})
        exact = dict(
            source_dict.get("post_click_exact_blockers_by_family")
            or source_dict.get("exact_blockers_by_family")
            or {}
        )
        events.append({"event": "exact_filter", "source": source_dict})
        return {
            str(family or "").strip().lower(): dict(blocker or {})
            for family, blocker in exact.items()
            if isinstance(blocker, dict) and blocker.get("valid")
        }

    def reset_session(route=None) -> None:
        inputs_page.st.session_state.pop(session_key, None)
        if route is not None:
            inputs_page.st.session_state[session_key] = dict(route)

    def run_case(name: str, *, audit: dict, debug: dict, session_route=None):
        nonlocal events
        events = []
        reset_session(session_route)
        result = inputs_page.render_design_guide_terminal_exact_blocker_render_reconciliation(
            post_cleanup_render_audit=audit,
            guidance_debug=debug,
        )
        cases.append(
            {
                "name": name,
                "result": result,
                "audit": dict(audit),
                "debug": dict(debug),
                "events": list(events),
            }
        )
        return result, audit, debug, list(events)

    try:
        inputs_page._accepted_green_exact_blockers_by_family = exact_filter

        result, audit, debug, event_log = run_case(
            "no_sources_noop",
            audit={},
            debug={},
            session_route=None,
        )
        expect("no_sources_noop", result == {}, f"result={result}")
        expect("no_sources_noop", audit == {}, f"audit={audit}")
        expect("no_sources_noop", debug == {}, f"debug={debug}")
        expect("no_sources_noop", event_log == [], f"events={event_log}")

        audit_exact = {
            "shear": {"valid": True, "current_util": 0.72},
            "bending": {"valid": False, "current_util": 0.8},
        }
        lower_precedence_debug_exact = {"geometry": {"valid": True}}
        lower_precedence_session_exact = {"serviceability": {"valid": True}}
        result, audit, debug, event_log = run_case(
            "audit_post_click_exact_precedence_and_list_prune",
            audit={
                "post_click_exact_blockers_by_family": dict(audit_exact),
                "post_click_unresolved_low_util_families": ["Shear", "bending", ""],
                "post_click_unresolved_overprovided_families": ["shear", "geometry"],
                "post_click_families_below_final_threshold": ["SHEAR", "bending"],
            },
            debug={
                "post_click_exact_blockers_by_family": dict(lower_precedence_debug_exact),
                "post_click_unresolved_low_util_families": ["shear"],
            },
            session_route={
                "post_apply_exact_blockers_by_family": dict(lower_precedence_session_exact)
            },
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            result == audit_exact,
            f"result={result}",
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            audit.get("post_click_exact_blockers_by_family") == audit_exact
            and audit.get("exact_blockers_by_family") == audit_exact,
            f"audit_exact={audit}",
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            debug.get("post_click_exact_blockers_by_family") == audit_exact
            and debug.get("exact_blockers_by_family") == audit_exact,
            f"debug_exact={debug}",
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            audit.get("post_click_unresolved_low_util_families") == ["bending", ""],
            f"low={audit.get('post_click_unresolved_low_util_families')}",
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            audit.get("post_click_unresolved_overprovided_families") == ["geometry"],
            f"over={audit.get('post_click_unresolved_overprovided_families')}",
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            audit.get("post_click_families_below_final_threshold") == ["bending"],
            f"below={audit.get('post_click_families_below_final_threshold')}",
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            debug.get("post_click_unresolved_low_util_families") == ["shear"],
            f"debug_low={debug.get('post_click_unresolved_low_util_families')}",
        )
        expect(
            "audit_post_click_exact_precedence_and_list_prune",
            len(event_log) == 1,
            f"events={event_log}",
        )

        alias_exact = {"bending": {"valid": True, "current_util": 0.83}}
        result, audit, debug, event_log = run_case(
            "audit_alias_exact_used_when_post_click_missing",
            audit={
                "exact_blockers_by_family": dict(alias_exact),
                "post_click_unresolved_low_util_families": ["bending", "shear"],
            },
            debug={"post_click_exact_blockers_by_family": {"shear": {"valid": True}}},
            session_route=None,
        )
        expect(
            "audit_alias_exact_used_when_post_click_missing",
            result == alias_exact,
            f"result={result}",
        )
        expect(
            "audit_alias_exact_used_when_post_click_missing",
            audit.get("post_click_exact_blockers_by_family") == alias_exact,
            f"audit={audit}",
        )
        expect(
            "audit_alias_exact_used_when_post_click_missing",
            audit.get("post_click_unresolved_low_util_families") == ["shear"],
            f"low={audit.get('post_click_unresolved_low_util_families')}",
        )

        debug_alias_exact = {"shear": {"valid": False, "current_util": 0.7}}
        result, audit, debug, event_log = run_case(
            "debug_alias_used_when_audit_missing_and_no_valid_prune",
            audit={
                "post_click_unresolved_low_util_families": ["shear"],
                "post_click_families_below_final_threshold": ["shear"],
            },
            debug={"exact_blockers_by_family": dict(debug_alias_exact)},
            session_route=None,
        )
        expect(
            "debug_alias_used_when_audit_missing_and_no_valid_prune",
            result == debug_alias_exact,
            f"result={result}",
        )
        expect(
            "debug_alias_used_when_audit_missing_and_no_valid_prune",
            audit.get("post_click_unresolved_low_util_families") == ["shear"]
            and audit.get("post_click_families_below_final_threshold") == ["shear"],
            f"audit_lists={audit}",
        )
        expect(
            "debug_alias_used_when_audit_missing_and_no_valid_prune",
            len(event_log) == 1,
            f"events={event_log}",
        )

        post_apply_exact = {"shear": {"valid": True, "source": "post_apply"}}
        route_alias_exact = {"bending": {"valid": True, "source": "route_alias"}}
        result, audit, debug, event_log = run_case(
            "last_apply_post_apply_exact_precedes_route_alias",
            audit={"post_click_unresolved_low_util_families": ["shear", "bending"]},
            debug={},
            session_route={
                "post_apply_exact_blockers_by_family": dict(post_apply_exact),
                "exact_blockers_by_family": dict(route_alias_exact),
            },
        )
        expect(
            "last_apply_post_apply_exact_precedes_route_alias",
            result == post_apply_exact,
            f"result={result}",
        )
        expect(
            "last_apply_post_apply_exact_precedes_route_alias",
            audit.get("post_click_exact_blockers_by_family") == post_apply_exact
            and debug.get("post_click_exact_blockers_by_family") == post_apply_exact,
            f"audit={audit} debug={debug}",
        )
        expect(
            "last_apply_post_apply_exact_precedes_route_alias",
            audit.get("post_click_unresolved_low_util_families") == ["bending"],
            f"low={audit.get('post_click_unresolved_low_util_families')}",
        )

        route_exact = {"bending": {"valid": True, "source": "route_alias"}}
        result, audit, debug, event_log = run_case(
            "last_apply_route_alias_used_when_post_apply_missing",
            audit={"post_click_unresolved_low_util_families": ["bending", "shear"]},
            debug={},
            session_route={"exact_blockers_by_family": dict(route_exact)},
        )
        expect(
            "last_apply_route_alias_used_when_post_apply_missing",
            result == route_exact,
            f"result={result}",
        )
        expect(
            "last_apply_route_alias_used_when_post_apply_missing",
            audit.get("post_click_unresolved_low_util_families") == ["shear"],
            f"low={audit.get('post_click_unresolved_low_util_families')}",
        )
    finally:
        inputs_page._accepted_green_exact_blockers_by_family = original_exact_filter
        inputs_page.st.session_state.pop(session_key, None)
        if original_session_present:
            inputs_page.st.session_state[session_key] = original_session_value

    payload_out = {
        "verifier": "inputs_page_terminal_exact_blocker_render_reconciliation_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(
        json.dumps(payload_out, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Exact Blocker Render Reconciliation",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload_out['status']}",
                "",
                "Scope:",
                "- Guards the extracted terminal exact-blocker render reconciliation coordinator.",
                "- Verifies source precedence, alias stamping, audit-list pruning, and session fallback.",
                "- Confirms downstream terminal-green code still receives the reconciled exact blocker map.",
                "",
                "Cases:",
                *[f"- {case['name']}" for case in cases],
                "",
                "Failures:",
                *(f"- {failure}" for failure in failures),
                "" if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload_out, indent=2, sort_keys=True, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
