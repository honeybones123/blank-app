from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_active_failure_visible_truth_priority_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_failure_visible_truth_priority_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_guidance_item_is_cleanup_or_terminal": inputs_page._guidance_item_is_cleanup_or_terminal,
        "_clear_stale_design_guide_cleanup_state": inputs_page._clear_stale_design_guide_cleanup_state,
        "_direct_target_band_guidance_item": inputs_page._direct_target_band_guidance_item,
        "_active_failure_item_from_overview": inputs_page._active_failure_item_from_overview,
        "_design_guide_apply_button_contracts_to_items": inputs_page._design_guide_apply_button_contracts_to_items,
        "_design_guide_apply_display_truth_to_items": inputs_page._design_guide_apply_display_truth_to_items,
        "_COMPOUND_SHEAR_UPDATE_KEYS": inputs_page._COMPOUND_SHEAR_UPDATE_KEYS,
    }
    calls: list[str] = []
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install(
        *,
        cleanup_or_terminal: bool,
        direct_item: dict | Exception | None,
        fallback_item: dict | None,
    ) -> None:
        calls.clear()
        inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"lig_d", "lig_legs", "s_lig"}
        inputs_page._guidance_item_is_cleanup_or_terminal = lambda item: bool(cleanup_or_terminal)

        def _clear(reason):
            calls.append(f"clear:{reason}")

        def _direct(state, overview, mode_config, *, strengthening=False, debug_sink=None):
            calls.append("direct")
            if isinstance(direct_item, Exception):
                raise direct_item
            return dict(direct_item or {})

        def _fallback(state, overview):
            calls.append("fallback")
            return dict(fallback_item or {})

        def _apply_contracts(items, *, state=None):
            calls.append("apply_contracts")
            return [dict(item, contracts_applied=True) for item in list(items or [])]

        def _apply_display(items, *, state=None, overview=None, mode_config=None):
            calls.append("apply_display")
            return [dict(item, display_applied=True) for item in list(items or [])]

        inputs_page._clear_stale_design_guide_cleanup_state = _clear
        inputs_page._direct_target_band_guidance_item = _direct
        inputs_page._active_failure_item_from_overview = _fallback
        inputs_page._design_guide_apply_button_contracts_to_items = _apply_contracts
        inputs_page._design_guide_apply_display_truth_to_items = _apply_display

    def _run_case(
        name: str,
        *,
        active_keys: set[str],
        primary: dict,
        primary_key: str,
        primary_active_blocker: bool,
        cleanup_or_terminal: bool,
        direct_item: dict | Exception | None,
        fallback_item: dict | None = None,
    ) -> tuple[dict, list, list, object, object, object]:
        try:
            _install(
                cleanup_or_terminal=cleanup_or_terminal,
                direct_item=direct_item,
                fallback_item=fallback_item,
            )
            result = inputs_page.render_design_guide_active_failure_visible_truth_priority_branch(
                active_fail_keys_for_render=set(active_keys),
                primary_for_active_guard=dict(primary),
                primary_guard_is_active_blocker=primary_active_blocker,
                primary_guard_key=primary_key,
                guidance_debug={"candidate_search_evidence": {"debug": True}},
                guidance_items=[dict(primary)],
                guidance_items_raw=[dict(primary)],
                guidance_disp_state={"D": 400},
                dg_overview={"statuses": {"bending": "FAIL"}},
                dg_mode_cfg={"goal": "balanced"},
                terminal_state="old_terminal",
                terminal_state_source="old_source",
                recommendation_result={"winner": "old"},
            )
        finally:
            case_calls = list(calls)
            _restore()
        cases.append({"name": name, "calls": case_calls})
        return result

    direct = _run_case(
        "direct_active_failure_priority",
        active_keys={"bending"},
        primary={"family": "cleanup", "title": "Cleanup card"},
        primary_key="cleanup",
        primary_active_blocker=False,
        cleanup_or_terminal=True,
        direct_item={"family": "bending", "check_key": "bending", "title_main": "Bending capacity is low"},
    )
    direct_debug, direct_items, direct_raw, direct_terminal, direct_source, direct_rec = direct
    if direct_items[0].get("title_main") != "Bending capacity is low":
        failures.append(f"direct_item_not_promoted:{direct_items}")
    if direct_items[0].get("contracts_applied") is not True or direct_items[0].get("display_applied") is not True:
        failures.append(f"direct_render_adapters_not_applied:{direct_items}")
    if direct_raw[0].get("title_main") != "Bending capacity is low":
        failures.append(f"direct_raw_not_original_active_item:{direct_raw}")
    if direct_terminal is not None or direct_source != "active_failure_visible_truth_takes_priority" or direct_rec is not None:
        failures.append(f"direct_terminal_state_mismatch:{direct_terminal}:{direct_source}:{direct_rec}")
    if direct_debug.get("guidance_branch") != "active_failure_visible_truth_takes_priority":
        failures.append(f"direct_guidance_branch_mismatch:{direct_debug}")
    if direct_debug.get("selected_action_family") != "cleanup":
        failures.append(f"direct_selected_action_family_mismatch:{direct_debug}")

    evidence = {
        "target_band_candidate_count": 1,
        "selected_candidate_updates": {"lig_d": 12},
    }
    propagated = _run_case(
        "evidence_propagates_for_active_shear_family",
        active_keys={"shear"},
        primary={"family": "cleanup", "candidate_search_evidence": evidence},
        primary_key="cleanup",
        primary_active_blocker=True,
        cleanup_or_terminal=False,
        direct_item={"family": "shear", "check_key": "shear", "title_main": "Shear capacity is low"},
    )
    propagated_item = propagated[1][0]
    if propagated_item.get("candidate_search_evidence") != evidence:
        failures.append(f"evidence_not_propagated:{propagated_item}")
    if dict(propagated_item.get("action_payload") or {}).get("candidate_search_evidence") != evidence:
        failures.append(f"evidence_not_propagated_to_payload:{propagated_item}")

    fallback = _run_case(
        "fallback_item_used_when_direct_raises",
        active_keys={"bending"},
        primary={"family": "cleanup"},
        primary_key="cleanup",
        primary_active_blocker=True,
        cleanup_or_terminal=False,
        direct_item=RuntimeError("direct failed"),
        fallback_item={"family": "bending", "check_key": "bending", "title_main": "Fallback bending card"},
    )
    if fallback[1][0].get("title_main") != "Fallback bending card":
        failures.append(f"fallback_item_not_used:{fallback[1]}")

    noop = _run_case(
        "primary_already_matches_active_failure_noop",
        active_keys={"bending"},
        primary={"family": "bending", "title": "Existing active card"},
        primary_key="bending",
        primary_active_blocker=False,
        cleanup_or_terminal=False,
        direct_item={"family": "bending", "title_main": "Should not run"},
    )
    if noop[1][0].get("title") != "Existing active card":
        failures.append(f"noop_item_changed:{noop[1]}")
    if cases[-1]["calls"]:
        failures.append(f"noop_called_collaborators:{cases[-1]['calls']}")
    if noop[3] != "old_terminal" or noop[4] != "old_source" or noop[5] != {"winner": "old"}:
        failures.append(f"noop_terminal_state_changed:{noop[3]}:{noop[4]}:{noop[5]}")

    payload = {
        "verifier": "inputs_page_active_failure_visible_truth_priority_branch_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Failure Visible Truth Priority Branch Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` calls={case['calls']}" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
