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


class _FakeSessionState(dict):
    pass


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = _FakeSessionState()


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_fast_terminal_after_compute_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_fast_terminal_after_compute_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    fake_st = _FakeStreamlit()
    route_overview = {
        "all_key_pass": True,
        "any_fail": False,
        "utils": {"bending": 0.91, "shear": 0.90},
        "statuses": {"bending": "PASS", "shear": "PASS"},
    }
    fake_st.session_state[inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
        "post_apply_resolved_candidate_attempted": True,
        "resolved_candidate_family_tag": "bending",
        "resolved_candidate_label": "bending capacity repair",
        "post_apply_overview": dict(route_overview),
        "actual_changed_updates": {"D": 520},
    }

    rendered: list[dict[str, Any]] = []
    stages: list[str] = []

    originals = {
        "st": inputs_page.st,
        "_post_apply_active_repair_required_checks_terminal_ready": inputs_page._post_apply_active_repair_required_checks_terminal_ready,
        "_post_apply_combined_chained_terminal_recent_refresh_ready": inputs_page._post_apply_combined_chained_terminal_recent_refresh_ready,
        "_local_cleanup_acceptance_fingerprint": inputs_page._local_cleanup_acceptance_fingerprint,
        "_local_cleanup_post_apply_acceptance_matches": inputs_page._local_cleanup_post_apply_acceptance_matches,
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "_post_active_repair_target_accepted_item": inputs_page._post_active_repair_target_accepted_item,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_apply_design_brain_publication_contract_for_render": inputs_page._apply_design_brain_publication_contract_for_render,
        "_stamp_final_publication_same_object_verifier_payload": inputs_page._stamp_final_publication_same_object_verifier_payload,
        "_stable_final_publication_hash": inputs_page._stable_final_publication_hash,
        "_render_guidance_secondary_items": inputs_page._render_guidance_secondary_items,
    }

    try:
        inputs_page.st = fake_st
        inputs_page._post_apply_active_repair_required_checks_terminal_ready = lambda route, state, allowed_families: True
        inputs_page._post_apply_combined_chained_terminal_recent_refresh_ready = lambda route, state: False
        inputs_page._local_cleanup_acceptance_fingerprint = lambda state: "fast-terminal-fp"
        inputs_page._local_cleanup_post_apply_acceptance_matches = lambda state: False
        inputs_page._overview_required_checks_acceptable = lambda overview: True
        inputs_page._design_optimisation_goal = lambda state: "balanced"
        inputs_page._design_mode_config = lambda goal: {"goal": goal}

        def _accepted_item(state, overview, config, audit, *, debug_sink=None, allow_required_checks_terminal=False):
            if isinstance(debug_sink, dict):
                debug_sink["accepted_item_called"] = True
            return {
                "title": "Design is efficient",
                "title_main": "Design is efficient",
                "primary_action": "All required checks pass.",
                "reasoning": "All required checks pass.",
                "button_contract": {"enabled": False, "updates": {}},
            }

        def _apply_contract(*, guidance_items, guidance_debug, render_plan, presentation, state, reason):
            guidance_debug = dict(guidance_debug or {})
            guidance_debug["contract_reason"] = reason
            return list(guidance_items or []), guidance_debug, dict(render_plan), dict(presentation), True

        def _stamp_payload(*, item, debug_sink):
            return {
                "display": {"title": item.get("title"), "status": "PASS"},
                "final_publication_cta_hash": "cta-hash",
                "final_publication_display_hash": "display-hash",
            }

        def _render_items(items, **kwargs):
            rendered.append({"items": [dict(item) for item in items], "kwargs": dict(kwargs)})

        inputs_page._post_active_repair_target_accepted_item = _accepted_item
        inputs_page._apply_design_brain_publication_contract_for_render = _apply_contract
        inputs_page._stamp_final_publication_same_object_verifier_payload = _stamp_payload
        inputs_page._stable_final_publication_hash = lambda payload: "publication-hash"
        inputs_page._render_guidance_secondary_items = _render_items

        guidance_debug: dict[str, Any] = {}
        handled = inputs_page.render_design_guide_fast_terminal_after_compute(
            guidance_disp_state={"D": 520},
            guidance_debug=guidance_debug,
            inputs_render_audit={},
            stage=lambda label: stages.append(str(label)),
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    debug_bundle = dict(fake_st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})
    render_plan = dict(fake_st.session_state.get("_design_guide_render_plan_debug") or {})
    failures: list[str] = []
    if handled is not True:
        failures.append("branch_did_not_return_true")
    if stages != ["post_apply_required_checks_pass_fast_terminal"]:
        failures.append(f"stage_marker_mismatch:{stages}")
    if len(rendered) != 1:
        failures.append(f"secondary_items_render_count:{len(rendered)}")
    if fake_st.session_state.get(inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY) != {}:
        failures.append("primary_apply_payload_not_cleared")
    if debug_bundle.get("guidance_branch") != "post_apply_required_checks_pass_fast_terminal":
        failures.append(f"debug_branch_mismatch:{debug_bundle.get('guidance_branch')}")
    if debug_bundle.get("publication_hash") != "publication-hash":
        failures.append(f"publication_hash_mismatch:{debug_bundle.get('publication_hash')}")
    if render_plan.get("reason") != "post_apply_required_checks_pass_fast_terminal":
        failures.append(f"render_plan_reason_mismatch:{render_plan.get('reason')}")
    if debug_bundle.get("contract_reason") != "post_apply_required_checks_pass_fast_terminal":
        failures.append(f"contract_reason_mismatch:{debug_bundle.get('contract_reason')}")

    payload = {
        "verifier": "inputs_page_fast_terminal_after_compute_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "handled": handled,
        "stages": stages,
        "render_count": len(rendered),
        "debug_branch": debug_bundle.get("guidance_branch"),
        "publication_hash": debug_bundle.get("publication_hash"),
        "render_plan_reason": render_plan.get("reason"),
        "contract_reason": debug_bundle.get("contract_reason"),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Fast Terminal After Compute Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                f"- handled: `{handled}`",
                f"- stages: `{stages}`",
                f"- render count: `{len(rendered)}`",
                f"- debug branch: `{debug_bundle.get('guidance_branch')}`",
                f"- publication hash: `{debug_bundle.get('publication_hash')}`",
                f"- render plan reason: `{render_plan.get('reason')}`",
                f"- contract reason: `{debug_bundle.get('contract_reason')}`",
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
