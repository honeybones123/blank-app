from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CURRENT_COORDINATORS = ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _base_cleanup_item() -> dict:
    return {
        "title_main": "Bending cleanup - further reduction reaches target range",
        "title": "Bending cleanup - further reduction reaches target range",
        "family": "bending",
        "check_key": "bending",
        "guidance_intent": "optional_cleanup",
        "status": "PASS",
        "primary_action": "Run one-click auto design",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "updates": {"bot_row_1_bars": 3},
            "preview_pass": True,
        },
        "candidate_search_evidence": {
            "target_low": 0.85,
            "target_high": 1.0,
        },
    }


def _payload_for(
    *,
    bending_status: str,
    bending_util: float,
    active_failures: list[str],
    explicit_payload_active: bool = True,
    stale_debug_active: bool = False,
    stale_family_status: bool = False,
    stale_text_signal: bool = False,
) -> dict:
    overview = {
        "statuses": {"bending": bending_status, "shear": "PASS"},
        "utils": {"bending": bending_util, "shear": 0.93},
        "any_fail": str(bending_status).upper() == "FAIL",
    }
    item = _base_cleanup_item()
    if stale_text_signal:
        item["reasoning"] = "Bending capacity fails in stale debug text, but current overview passes."
    payload = {
        "guidance_items": [_base_cleanup_item()],
        "debug_trace": {
            "overview": {"statuses": {"bending": "FAIL"}, "utils": {"bending": 1.25}},
            "current_overview": dict(overview),
        },
        "overview": dict(overview),
        "family_status_current": {
            "bending": {"status": bending_status, "util": bending_util},
            "shear": {"status": "PASS", "util": 0.93},
        },
    }
    payload["guidance_items"] = [item]
    if explicit_payload_active:
        payload["active_failures"] = list(active_failures)
    if stale_debug_active:
        payload["debug_trace"]["active_failures"] = list(active_failures)
    if stale_family_status:
        payload["debug_trace"]["family_status_current"] = {
            "bending": {"status": "FAIL", "util": 1.25},
            "shear": {"status": "PASS", "util": 0.93},
        }
    return payload


def main() -> int:
    from design_brain.publication import enforce_underdesign_repair_publication_boundary

    stale_active_pass_payload = _payload_for(
        bending_status="PASS",
        bending_util=0.19,
        active_failures=["bending"],
    )
    stale_active_pass_result = enforce_underdesign_repair_publication_boundary(
        dict(stale_active_pass_payload)
    )
    stale_items = list(stale_active_pass_result.get("guidance_items") or [])
    stale_primary = dict(stale_items[0] if stale_items else {})
    stale_debug = dict(stale_active_pass_result.get("debug_trace") or {})

    true_fail_payload = _payload_for(
        bending_status="FAIL",
        bending_util=1.25,
        active_failures=["bending"],
    )
    true_fail_result = enforce_underdesign_repair_publication_boundary(dict(true_fail_payload))
    true_fail_items = list(true_fail_result.get("guidance_items") or [])
    true_fail_primary = dict(true_fail_items[0] if true_fail_items else {})
    true_fail_debug = dict(true_fail_result.get("debug_trace") or {})

    implicit_cases: dict[str, dict] = {}
    for case_name, case_payload in {
        "stale_debug_active_failure": _payload_for(
            bending_status="PASS",
            bending_util=0.19,
            active_failures=["bending"],
            explicit_payload_active=False,
            stale_debug_active=True,
        ),
        "stale_debug_overview_failure": _payload_for(
            bending_status="PASS",
            bending_util=0.19,
            active_failures=[],
            explicit_payload_active=False,
        ),
        "stale_family_status_failure": _payload_for(
            bending_status="PASS",
            bending_util=0.19,
            active_failures=["bending"],
            explicit_payload_active=False,
            stale_family_status=True,
        ),
        "stale_text_signal_failure": _payload_for(
            bending_status="PASS",
            bending_util=0.19,
            active_failures=[],
            explicit_payload_active=False,
            stale_text_signal=True,
        ),
    }.items():
        case_result = enforce_underdesign_repair_publication_boundary(dict(case_payload))
        case_items = list(case_result.get("guidance_items") or [])
        case_primary = dict(case_items[0] if case_items else {})
        case_debug = dict(case_result.get("debug_trace") or {})
        implicit_cases[case_name] = {
            "title": case_primary.get("title_main") or case_primary.get("title"),
            "contract_boundary_passed": case_debug.get("contract_boundary_passed"),
            "active_failures_after_reconciliation": case_debug.get("active_failures"),
            "blocked": bool(case_primary.get("contract_boundary_blocked_publication")),
        }

    render_sources = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, CURRENT_COORDINATORS)
        if path.exists()
    )
    fresh_overview_handoff_tokens = {
        "fresh_collect_before_debug_fallback": (
            "_fresh_dg_overview = _collect_design_overview(" in render_sources
            and "_debug_dg_overview = guidance_debug.get(\"overview\")" in render_sources
        ),
        "fresh_overview_used_when_statuses_present": (
            "_dg_overview = dict(_fresh_dg_overview)" in render_sources
        ),
        "freshness_debug_stamp": (
            "design_guide_overview_refreshed_from_current_state" in render_sources
        ),
    }

    checks = {
        "stale_explicit_active_bending_pruned_when_current_overview_passes": (
            stale_debug.get("active_failures") == []
            and stale_debug.get("contract_boundary_passed") is True
        ),
        "stale_active_pass_does_not_publish_bending_capacity_low_shell": (
            str(stale_primary.get("title_main") or stale_primary.get("title") or "")
            != "Bending capacity is low"
            and not bool(stale_primary.get("contract_boundary_blocked_publication"))
        ),
        "true_active_bending_failure_still_enforces_boundary": (
            true_fail_debug.get("active_failures") == ["bending"]
            and true_fail_debug.get("contract_boundary_passed") is False
            and true_fail_debug.get("contract_boundary_violation_reason")
            == "bending_fail_governs_missing_repair_ACTION_or_family_owned_no_repair_proof"
        ),
        "implicit_stale_active_failure_sources_are_pruned": all(
            row.get("active_failures_after_reconciliation") == []
            and row.get("contract_boundary_passed") is True
            and row.get("title") != "Bending capacity is low"
            and row.get("blocked") is False
            for row in implicit_cases.values()
        ),
        **fresh_overview_handoff_tokens,
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "failures": failures,
        "stale_active_pass": {
            "title": stale_primary.get("title_main") or stale_primary.get("title"),
            "contract_boundary_passed": stale_debug.get("contract_boundary_passed"),
            "active_failures_after_reconciliation": stale_debug.get("active_failures"),
            "blocked": bool(stale_primary.get("contract_boundary_blocked_publication")),
        },
        "true_active_failure": {
            "title": true_fail_primary.get("title_main") or true_fail_primary.get("title"),
            "contract_boundary_passed": true_fail_debug.get("contract_boundary_passed"),
            "active_failures_after_reconciliation": true_fail_debug.get("active_failures"),
            "blocked": bool(true_fail_primary.get("contract_boundary_blocked_publication")),
        },
        "implicit_stale_cases": implicit_cases,
        "product_behaviour_intent": (
            "A stale explicit active-failure flag must not override current overview proof that "
            "bending passes. A true bending failure must still be blocked unless it publishes a "
            "repair action or legal no-repair proof."
        ),
    }

    stamp = _utc_stamp()
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    verification_path = (
        VERIFICATION_DIR
        / f"design_guide_stale_active_failure_publication_guard_{stamp}.json"
    )
    audit_path = AUDIT_DIR / f"design_guide_stale_active_failure_publication_guard_{stamp}.md"
    verification_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    audit_path.write_text(
        "\n".join(
            [
                "# Design Guide stale active-failure publication guard snapshot",
                "",
                f"Result: **{status}**",
                "",
                "Checks:",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "This verifies the screenshot class where the summary proves bending PASS but stale",
                "publication/debug state still claims an active bending failure.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide stale active-failure publication guard {status}")
    print(f"verification: {verification_path}")
    print(f"audit: {audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
