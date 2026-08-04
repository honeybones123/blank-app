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
        f"inputs_page_post_cleanup_zero_shear_low_family_cleanup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_zero_shear_low_family_cleanup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_float_from_state = inputs_page._float_from_state
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def float_from_state(state, key, default=None):
        events.append({"event": "float_from_state", "key": key, "default": default})
        return dict(state or {}).get(key, default)

    def run_case(name: str, *, audit: dict, debug: dict, state: dict):
        nonlocal events
        events = []
        result = inputs_page.render_design_guide_post_cleanup_zero_shear_low_family_cleanup(
            post_cleanup_render_audit=audit,
            guidance_debug=debug,
            guidance_disp_state=state,
        )
        cases.append(
            {
                "name": name,
                "result": sorted(result),
                "audit": dict(audit),
                "debug": dict(debug),
                "events": list(events),
            }
        )
        return result, audit, debug, list(events)

    try:
        inputs_page._float_from_state = float_from_state

        cleanup_audit = {
            "post_click_families_below_final_threshold": ["Shear", "bending", ""],
            "post_click_unresolved_low_util_families": ["shear", "BENDING", ""],
            "post_click_unresolved_overprovided_families": ["SHEAR", "geometry"],
            "post_click_exact_blockers_by_family": {
                "shear": {"remove": True},
                "bending": {"keep": True},
            },
            "exact_blockers_by_family": {
                "shear": {"remove": True},
                "bending": {"keep": True},
            },
            "post_click_cleanup_evidence_by_family": {
                "shear": {"remove": True},
                "bending": {"keep": True},
            },
            "cleanup_evidence_by_family": {
                "shear": {"remove": True},
                "bending": {"keep": True},
            },
        }
        cleanup_debug = {"existing": "keep"}
        result, audit, debug, event_log = run_case(
            "zero_shear_demand_removes_shear_low_family_and_blockers",
            audit=cleanup_audit,
            debug=cleanup_debug,
            state={"Vu_star": 0.0, "uls_Vstar": 0.0, "load_Vstar_proxy": 0.0},
        )
        expect(
            "zero_shear_demand_removes_shear_low_family_and_blockers",
            result == {"bending"},
            f"result={result}",
        )
        expect(
            "zero_shear_demand_removes_shear_low_family_and_blockers",
            audit.get("post_click_families_below_final_threshold") == ["bending", ""],
            f"below={audit.get('post_click_families_below_final_threshold')}",
        )
        expect(
            "zero_shear_demand_removes_shear_low_family_and_blockers",
            audit.get("post_click_unresolved_low_util_families") == ["bending", ""],
            f"low={audit.get('post_click_unresolved_low_util_families')}",
        )
        expect(
            "zero_shear_demand_removes_shear_low_family_and_blockers",
            audit.get("post_click_unresolved_overprovided_families") == ["geometry"],
            f"over={audit.get('post_click_unresolved_overprovided_families')}",
        )
        for blocker_key in (
            "post_click_exact_blockers_by_family",
            "exact_blockers_by_family",
            "post_click_cleanup_evidence_by_family",
            "cleanup_evidence_by_family",
        ):
            expect(
                "zero_shear_demand_removes_shear_low_family_and_blockers",
                audit.get(blocker_key) == {"bending": {"keep": True}},
                f"{blocker_key}={audit.get(blocker_key)}",
            )
            expect(
                "zero_shear_demand_removes_shear_low_family_and_blockers",
                debug.get(blocker_key) == {"bending": {"keep": True}},
                f"debug_{blocker_key}={debug.get(blocker_key)}",
            )
        expect(
            "zero_shear_demand_removes_shear_low_family_and_blockers",
            debug.get("post_cleanup_zero_shear_demand_removed_shear_low_family") is True,
            f"debug_flag={debug}",
        )
        expect(
            "zero_shear_demand_removes_shear_low_family_and_blockers",
            [event["key"] for event in event_log] == ["Vu_star", "uls_Vstar", "load_Vstar_proxy"],
            f"events={event_log}",
        )

        no_shear_audit = {
            "post_click_families_below_final_threshold": ["bending"],
            "post_click_unresolved_low_util_families": ["bending"],
            "post_click_exact_blockers_by_family": {"bending": {"keep": True}},
        }
        no_shear_debug = {"existing": "keep"}
        original_no_shear_audit = json.loads(json.dumps(no_shear_audit))
        original_no_shear_debug = dict(no_shear_debug)
        result, audit, debug, event_log = run_case(
            "no_shear_low_family_noop",
            audit=no_shear_audit,
            debug=no_shear_debug,
            state={"Vu_star": 0.0, "uls_Vstar": 0.0, "load_Vstar_proxy": 0.0},
        )
        expect("no_shear_low_family_noop", result == {"bending"}, f"result={result}")
        expect("no_shear_low_family_noop", audit == original_no_shear_audit, f"audit={audit}")
        expect("no_shear_low_family_noop", debug == original_no_shear_debug, f"debug={debug}")

        demand_audit = {
            "post_click_families_below_final_threshold": ["shear", "bending"],
            "post_click_unresolved_low_util_families": ["shear", "bending"],
            "post_click_exact_blockers_by_family": {
                "shear": {"keep": "demand"},
                "bending": {"keep": True},
            },
        }
        demand_debug = {"existing": "keep"}
        original_demand_audit = json.loads(json.dumps(demand_audit))
        original_demand_debug = dict(demand_debug)
        result, audit, debug, event_log = run_case(
            "nonzero_shear_demand_keeps_shear_low_family",
            audit=demand_audit,
            debug=demand_debug,
            state={"Vu_star": 0.0, "uls_Vstar": 0.02, "load_Vstar_proxy": 0.0},
        )
        expect(
            "nonzero_shear_demand_keeps_shear_low_family",
            result == {"shear", "bending"},
            f"result={result}",
        )
        expect(
            "nonzero_shear_demand_keeps_shear_low_family",
            audit == original_demand_audit,
            f"audit={audit}",
        )
        expect(
            "nonzero_shear_demand_keeps_shear_low_family",
            debug == original_demand_debug,
            f"debug={debug}",
        )
    finally:
        inputs_page._float_from_state = original_float_from_state

    payload_out = {
        "verifier": "inputs_page_post_cleanup_zero_shear_low_family_cleanup_verifier",
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
                "# Inputs Page Post-Cleanup Zero Shear Low-Family Cleanup",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload_out['status']}",
                "",
                "Scope:",
                "- Guards the extracted zero-shear low-family cleanup coordinator.",
                "- Verifies shear removal from low-family lists, blocker alias cleanup, debug sync, and no-op paths.",
                "- Confirms the helper returns the low-family set consumed by later render branches.",
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
