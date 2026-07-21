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
        f"inputs_page_post_active_failure_repair_shear_blocker_refresh_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_active_failure_repair_shear_blocker_refresh_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_accepted_green_exact_blocker_is_valid": inputs_page._accepted_green_exact_blocker_is_valid,
        "_post_active_repair_residual_shear_exact_blocker": inputs_page._post_active_repair_residual_shear_exact_blocker,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    blocker_to_return: dict | None = None

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def blocker_valid(blocker) -> bool:
        events.append({"event": "valid", "blocker": dict(blocker or {})})
        return bool(isinstance(blocker, dict) and blocker.get("valid"))

    def residual_shear_blocker(state, overview, *, threshold):
        events.append(
            {
                "event": "residual_shear_blocker",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "threshold": threshold,
            }
        )
        return dict(blocker_to_return or {})

    def run_case(
        name: str,
        *,
        post_active_failure_repair_render: bool,
        audit: dict,
        debug: dict,
        returned_blocker: dict | None,
    ) -> tuple[bool, dict, dict, list[dict]]:
        nonlocal events, blocker_to_return
        events = []
        blocker_to_return = dict(returned_blocker or {})
        result = inputs_page.render_design_guide_post_active_failure_repair_shear_blocker_refresh(
            post_active_failure_repair_render=post_active_failure_repair_render,
            post_cleanup_render_audit=audit,
            guidance_debug=debug,
            guidance_disp_state={"D": 500, "s_lig": 200},
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
        inputs_page._accepted_green_exact_blocker_is_valid = blocker_valid
        inputs_page._post_active_repair_residual_shear_exact_blocker = residual_shear_blocker

        noop_audit = {
            "post_click_unresolved_low_util_families": ["bending"],
            "post_click_families_below_final_threshold": [],
            "post_click_exact_blockers_by_family": {"bending": {"valid": True}},
        }
        noop_debug = {"overview": {"utils": {"shear": 0.74}}}
        result, audit, debug, event_log = run_case(
            "no_shear_or_inactive_noop",
            post_active_failure_repair_render=True,
            audit=noop_audit,
            debug=noop_debug,
            returned_blocker={"valid": True},
        )
        expect("no_shear_or_inactive_noop", result is False, f"result={result}")
        expect("no_shear_or_inactive_noop", audit == noop_audit, f"audit={audit}")
        expect("no_shear_or_inactive_noop", debug == noop_debug, f"debug={debug}")
        expect("no_shear_or_inactive_noop", event_log == [], f"events={event_log}")

        valid_blocker = {
            "valid": True,
            "family": "shear",
            "current_util": 0.72,
            "reason": "shear remains below final threshold",
        }
        valid_audit = {
            "post_click_unresolved_low_util_families": ["shear", "bending"],
            "post_click_families_below_final_threshold": ["shear"],
            "post_click_exact_blockers_by_family": {"bending": {"valid": True}},
            "post_click_cleanup_evidence_by_family": {"bending": {"valid": True}},
            "local_cleanup_blocked_reasons_by_family": {"bending": ["keep"]},
        }
        valid_debug = {"overview": {"utils": {"shear": 0.72}}}
        result, audit, debug, event_log = run_case(
            "valid_blocker_refreshes_shear_evidence",
            post_active_failure_repair_render=True,
            audit=valid_audit,
            debug=valid_debug,
            returned_blocker=valid_blocker,
        )
        expect("valid_blocker_refreshes_shear_evidence", result is True, f"result={result}")
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("post_click_exact_blockers_by_family", {}).get("shear") == valid_blocker,
            f"exact={audit.get('post_click_exact_blockers_by_family')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("exact_blockers_by_family", {}).get("shear") == valid_blocker,
            f"exact_alias={audit.get('exact_blockers_by_family')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("post_click_cleanup_evidence_by_family", {}).get("shear") == valid_blocker,
            f"cleanup={audit.get('post_click_cleanup_evidence_by_family')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("cleanup_evidence_by_family", {}).get("shear") == valid_blocker,
            f"cleanup_alias={audit.get('cleanup_evidence_by_family')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("post_click_unresolved_low_util_families") == ["bending"],
            f"unresolved={audit.get('post_click_unresolved_low_util_families')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("post_click_unresolved_overprovided_families") == ["bending"],
            f"overprovided={audit.get('post_click_unresolved_overprovided_families')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("post_click_accepted_green_valid") is False,
            f"accepted={audit.get('post_click_accepted_green_valid')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("post_click_accepted_green_invalid_reason")
            == "unresolved_meaningful_family_util_below_0.85:bending",
            f"reason={audit.get('post_click_accepted_green_invalid_reason')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("local_cleanup_blocked_reasons_by_family", {}).get("shear")
            == ["shear remains below final threshold"],
            f"blocked={audit.get('local_cleanup_blocked_reasons_by_family')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            audit.get("safe_local_cleanup_count") == 0
            and audit.get("executable_safe_cleanup_count") == 0
            and audit.get("safe_shear_cleanup_count") == 0
            and audit.get("executable_shear_cleanup_count") == 0,
            f"counts={audit}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            debug.get("post_click_exact_blockers_by_family") == audit.get("post_click_exact_blockers_by_family"),
            f"debug_exact={debug.get('post_click_exact_blockers_by_family')}",
        )
        expect(
            "valid_blocker_refreshes_shear_evidence",
            [event["event"] for event in event_log]
            == ["valid", "residual_shear_blocker", "valid"],
            f"events={event_log}",
        )

        invalid_blocker = {
            "valid": False,
            "family": "shear",
            "current_util": 0.74,
            "reason": "raw blocker only",
        }
        invalid_audit = {
            "post_click_unresolved_low_util_families": ["shear"],
            "post_click_families_below_final_threshold": [],
            "post_click_exact_blockers_by_family": {},
        }
        invalid_debug = {"overview": {"utils": {"shear": 0.74}}}
        result, audit, debug, event_log = run_case(
            "invalid_blocker_stamps_raw_evidence",
            post_active_failure_repair_render=True,
            audit=invalid_audit,
            debug=invalid_debug,
            returned_blocker=invalid_blocker,
        )
        expect("invalid_blocker_stamps_raw_evidence", result is True, f"result={result}")
        expect(
            "invalid_blocker_stamps_raw_evidence",
            audit.get("post_click_shear_cleanup_evidence") == invalid_blocker,
            f"raw={audit.get('post_click_shear_cleanup_evidence')}",
        )
        expect(
            "invalid_blocker_stamps_raw_evidence",
            audit.get("candidate_search_evidence") == invalid_blocker,
            f"candidate={audit.get('candidate_search_evidence')}",
        )
        expect(
            "invalid_blocker_stamps_raw_evidence",
            debug.get("post_click_shear_cleanup_evidence") == invalid_blocker,
            f"debug_raw={debug.get('post_click_shear_cleanup_evidence')}",
        )
        expect(
            "invalid_blocker_stamps_raw_evidence",
            [event["event"] for event in event_log]
            == ["valid", "residual_shear_blocker", "valid"],
            f"events={event_log}",
        )

        stable_audit = {
            "post_click_unresolved_low_util_families": ["shear"],
            "post_click_families_below_final_threshold": [],
            "post_click_exact_blockers_by_family": {
                "shear": {"valid": True, "current_util": 0.72}
            },
        }
        stable_debug = {"overview": {"utils": {"shear": 0.72}}}
        result, audit, debug, event_log = run_case(
            "valid_current_blocker_does_not_rebuild",
            post_active_failure_repair_render=True,
            audit=stable_audit,
            debug=stable_debug,
            returned_blocker={"valid": True, "current_util": 0.9},
        )
        expect("valid_current_blocker_does_not_rebuild", result is True, f"result={result}")
        expect("valid_current_blocker_does_not_rebuild", audit == stable_audit, f"audit={audit}")
        expect("valid_current_blocker_does_not_rebuild", debug == stable_debug, f"debug={debug}")
        expect(
            "valid_current_blocker_does_not_rebuild",
            [event["event"] for event in event_log] == ["valid"],
            f"events={event_log}",
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    payload_out = {
        "verifier": "inputs_page_post_active_failure_repair_shear_blocker_refresh_verifier",
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
                "# Inputs Page Post-Active Failure Repair Shear Blocker Refresh",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload_out['status']}",
                "",
                "Scope:",
                "- Guards the extracted post-active failure repair shear blocker refresh coordinator.",
                "- Verifies no-op, valid blocker refresh, invalid raw evidence stamping, and stable current blocker branches.",
                "- Confirms no Design Brain ownership moved into the page shell.",
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
