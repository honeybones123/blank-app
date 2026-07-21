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
        f"inputs_page_terminal_green_unresolved_family_render_guard_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_terminal_green_unresolved_family_render_guard_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_guard = inputs_page._terminal_green_unresolved_strength_families
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    unresolved_to_return: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def terminal_guard(overview, debug, *, state):
        events.append(
            {
                "event": "terminal_guard",
                "overview": dict(overview or {}),
                "debug": dict(debug or {}),
                "state": dict(state or {}),
            }
        )
        return list(unresolved_to_return)

    def run_case(
        name: str,
        *,
        guidance_debug: dict,
        dg_overview: dict,
        exact_for_terminal_render: dict,
        post_cleanup_render_audit: dict,
        returned_unresolved: list[str],
    ):
        nonlocal events, unresolved_to_return
        events = []
        unresolved_to_return = list(returned_unresolved)
        result = inputs_page.render_design_guide_terminal_green_unresolved_family_render_guard(
            guidance_debug=guidance_debug,
            dg_overview=dg_overview,
            exact_for_terminal_render=exact_for_terminal_render,
            post_cleanup_render_audit=post_cleanup_render_audit,
            guidance_disp_state={"D": 500},
        )
        cases.append(
            {
                "name": name,
                "result": result,
                "guidance_debug": dict(guidance_debug),
                "post_cleanup_render_audit": dict(post_cleanup_render_audit),
                "events": list(events),
            }
        )
        return result, guidance_debug, post_cleanup_render_audit, list(events)

    try:
        inputs_page._terminal_green_unresolved_strength_families = terminal_guard

        no_op_debug = {"overview": {"source": "debug", "any_fail": False}, "keep": True}
        no_op_audit = {
            "post_click_accepted_green_valid": True,
            "post_click_unresolved_low_util_families": ["existing"],
        }
        result, debug, audit, event_log = run_case(
            "no_unresolved_noop_after_guard_call",
            guidance_debug=no_op_debug,
            dg_overview={"source": "fallback"},
            exact_for_terminal_render={"shear": {"valid": True}},
            post_cleanup_render_audit=no_op_audit,
            returned_unresolved=[],
        )
        expect("no_unresolved_noop_after_guard_call", result == [], f"result={result}")
        expect(
            "no_unresolved_noop_after_guard_call",
            debug == no_op_debug,
            f"debug={debug}",
        )
        expect(
            "no_unresolved_noop_after_guard_call",
            audit == no_op_audit,
            f"audit={audit}",
        )
        expect(
            "no_unresolved_noop_after_guard_call",
            len(event_log) == 1,
            f"events={event_log}",
        )
        if event_log:
            expect(
                "no_unresolved_noop_after_guard_call",
                event_log[0]["overview"] == {"source": "debug", "any_fail": False},
                f"overview={event_log[0]['overview']}",
            )
            expect(
                "no_unresolved_noop_after_guard_call",
                event_log[0]["debug"].get("exact_blockers_by_family")
                == {"shear": {"valid": True}},
                f"debug_exact={event_log[0]['debug']}",
            )
            expect(
                "no_unresolved_noop_after_guard_call",
                event_log[0]["debug"].get("post_click_exact_blockers_by_family")
                == {"shear": {"valid": True}},
                f"debug_post_exact={event_log[0]['debug']}",
            )

        unresolved_debug = {"overview": {}, "existing_debug": "keep"}
        unresolved_audit = {
            "post_click_accepted_green_valid": True,
            "post_click_unresolved_low_util_families": ["shear", "bending"],
            "other_audit": "keep",
        }
        result, debug, audit, event_log = run_case(
            "unresolved_families_stamp_audit_and_debug",
            guidance_debug=unresolved_debug,
            dg_overview={"source": "fallback", "any_fail": False},
            exact_for_terminal_render={"bending": {"valid": True}},
            post_cleanup_render_audit=unresolved_audit,
            returned_unresolved=["bending", "shear"],
        )
        expect(
            "unresolved_families_stamp_audit_and_debug",
            result == ["bending", "shear"],
            f"result={result}",
        )
        expect(
            "unresolved_families_stamp_audit_and_debug",
            debug.get("terminal_green_safety_unresolved_families")
            == ["bending", "shear"],
            f"debug_unresolved={debug.get('terminal_green_safety_unresolved_families')}",
        )
        expect(
            "unresolved_families_stamp_audit_and_debug",
            audit.get("post_click_accepted_green_valid") is False,
            f"accepted={audit.get('post_click_accepted_green_valid')}",
        )
        expect(
            "unresolved_families_stamp_audit_and_debug",
            audit.get("post_click_accepted_green_invalid_reason")
            == "terminal_green_unresolved_strength_families:bending,shear",
            f"reason={audit.get('post_click_accepted_green_invalid_reason')}",
        )
        expect(
            "unresolved_families_stamp_audit_and_debug",
            audit.get("post_click_unresolved_low_util_families")
            == ["shear", "bending"],
            f"low={audit.get('post_click_unresolved_low_util_families')}",
        )
        expect(
            "unresolved_families_stamp_audit_and_debug",
            debug.get("post_click_accepted_green_valid") is False
            and debug.get("other_audit") == "keep",
            f"debug={debug}",
        )
        if event_log:
            expect(
                "unresolved_families_stamp_audit_and_debug",
                event_log[0]["overview"] == {"source": "fallback", "any_fail": False},
                f"overview={event_log[0]['overview']}",
            )
    finally:
        inputs_page._terminal_green_unresolved_strength_families = original_guard

    payload_out = {
        "verifier": "inputs_page_terminal_green_unresolved_family_render_guard_verifier",
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
                "# Inputs Page Terminal Green Unresolved Family Render Guard",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload_out['status']}",
                "",
                "Scope:",
                "- Guards the extracted terminal-green unresolved-family render coordinator.",
                "- Verifies guard input projection, no-op path, unresolved-family audit stamping, and debug sync.",
                "- Confirms the helper returns the unresolved list consumed by terminal render gating.",
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
