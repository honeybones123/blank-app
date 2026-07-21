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
        f"inputs_page_final_active_failure_key_render_context_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_active_failure_key_render_context_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []
    original_session_state = inputs_page.st.session_state

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def run_case(
        name: str,
        *,
        guidance_items: list,
        guidance_debug: dict,
        dg_overview: dict,
        post_cleanup_acceptance_enabled: bool = False,
    ):
        inputs_page.st.session_state = (
            {"_design_guide_post_cleanup_acceptance_enabled": True}
            if post_cleanup_acceptance_enabled
            else {}
        )
        final_primary, active_keys = (
            inputs_page.render_design_guide_final_active_failure_key_render_context_setup(
                guidance_items=guidance_items,
                guidance_debug=guidance_debug,
                dg_overview=dg_overview,
            )
        )
        case = {
            "name": name,
            "final_primary": final_primary,
            "active_keys": sorted(active_keys),
            "guidance_debug": dict(guidance_debug),
        }
        cases.append(case)
        return final_primary, active_keys, guidance_debug

    direct_item = {"title_main": "Bending capacity is low"}
    final_primary, active_keys, debug = run_case(
        "direct_overview_active_failure_keys_preserved",
        guidance_items=[direct_item],
        guidance_debug={},
        dg_overview={"statuses": {"bending": "FAIL"}, "utils": {"bending": 1.08}, "any_fail": True},
    )
    expect(
        "direct_overview_active_failure_keys_preserved",
        final_primary == direct_item and active_keys == {"bending"},
        f"final_primary={final_primary} active_keys={active_keys}",
    )
    expect(
        "direct_overview_active_failure_keys_preserved",
        "final_active_failure_keys_fallback_used" not in debug,
        f"debug={debug}",
    )

    fallback_item = {
        "title_main": "Visible family status failure",
        "family_status_current": {
            "shear": {"status": "FAIL", "util": 1.08},
        },
    }
    final_primary, active_keys, debug = run_case(
        "fallback_from_visible_item_family_status",
        guidance_items=[fallback_item],
        guidance_debug={},
        dg_overview={"statuses": {}, "utils": {}, "any_fail": False},
    )
    expect(
        "fallback_from_visible_item_family_status",
        active_keys == {"shear"},
        f"active_keys={active_keys}",
    )
    expect(
        "fallback_from_visible_item_family_status",
        debug.get("final_active_failure_keys_fallback_used") is True
        and debug.get("final_active_failure_keys_for_render") == ["shear"],
        f"debug={debug}",
    )

    final_primary, active_keys, debug = run_case(
        "post_click_required_checks_accepted_skips_fallback",
        guidance_items=[fallback_item],
        guidance_debug={},
        dg_overview={"statuses": {}, "utils": {}, "any_fail": False, "all_key_pass": True},
        post_cleanup_acceptance_enabled=True,
    )
    expect(
        "post_click_required_checks_accepted_skips_fallback",
        active_keys == set(),
        f"active_keys={active_keys}",
    )
    expect(
        "post_click_required_checks_accepted_skips_fallback",
        debug.get("final_active_failure_keys_fallback_skipped") is True
        and debug.get("generic_target_band_search_skipped") is True,
        f"debug={debug}",
    )

    locked_item = {
        "title_main": "Locked",
        "selected_family_id": "LOCKED_NO_REPAIR",
    }
    final_primary, active_keys, debug = run_case(
        "locked_no_repair_suppresses_active_repair",
        guidance_items=[locked_item],
        guidance_debug={},
        dg_overview={"statuses": {"bending": "FAIL"}, "utils": {"bending": 1.08}, "any_fail": True},
    )
    expect(
        "locked_no_repair_suppresses_active_repair",
        active_keys == set(),
        f"active_keys={active_keys}",
    )
    expect(
        "locked_no_repair_suppresses_active_repair",
        debug.get("final_active_failure_repair_suppressed_by_locked_no_repair") is True
        and debug.get("locked_no_repair_final_publication_preserved") is True,
        f"debug={debug}",
    )

    geometry_item = {
        "title_main": "Geometry detailing",
        "candidate_search_evidence": {
            "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
        },
    }
    final_primary, active_keys, debug = run_case(
        "geometry_detailing_suppresses_active_repair",
        guidance_items=[geometry_item],
        guidance_debug={},
        dg_overview={"statuses": {"shear": "FAIL"}, "utils": {"shear": 1.08}, "any_fail": True},
    )
    expect(
        "geometry_detailing_suppresses_active_repair",
        active_keys == set(),
        f"active_keys={active_keys}",
    )
    expect(
        "geometry_detailing_suppresses_active_repair",
        debug.get("final_active_failure_repair_suppressed_by_geometry_detailing") is True
        and debug.get("geometry_detailing_final_publication_preserved") is True,
        f"debug={debug}",
    )

    inputs_page.st.session_state = original_session_state

    payload = {
        "verifier": "inputs_page_final_active_failure_key_render_context_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Active Failure Key Render Context",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload['status']}",
                "",
                "Scope:",
                "- Guards the extracted final active-failure render-key context coordinator.",
                "- Verifies overview keys, fallback keys, post-click accepted skip, locked/no-repair suppression, and geometry-detailing suppression.",
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
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
