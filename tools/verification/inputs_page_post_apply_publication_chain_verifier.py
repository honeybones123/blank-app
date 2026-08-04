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
    json_path = ARTIFACT_DIR / f"inputs_page_post_apply_publication_chain_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_apply_publication_chain_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    originals = {
        "candidate": inputs_page.render_design_guide_residual_width_cleanup_candidate,
        "residual_publication": inputs_page.render_design_guide_residual_width_cleanup_publication,
        "post_active": inputs_page.render_design_guide_post_active_accepted_green_publication,
        "secondary": inputs_page.render_design_guide_post_click_target_accepted_secondary_blocker,
        "local": inputs_page.render_design_guide_post_apply_local_cleanup_accepted,
        "exact": inputs_page.render_design_guide_post_apply_exact_low_util_blocker,
        "required": inputs_page.render_design_guide_post_apply_required_checks_pass_terminal,
        "invalid": inputs_page.render_design_guide_post_click_invalid_accepted_cleanup_resolution,
    }

    def publish_at(kwargs):
        return dict(kwargs.get("guidance_disp_state") or {}).get("publish_at")

    def residual_candidate(**kwargs):
        calls.append({"event": "candidate", "publish_at": publish_at(kwargs)})
        return {"residual": True}, {"contract": True}, {"width": 1}, {"match": True}

    def residual_publication(**kwargs):
        calls.append({"event": "residual_publication", "publish_at": publish_at(kwargs)})
        debug = dict(kwargs.get("guidance_debug") or {})
        if publish_at(kwargs) == "residual":
            debug["residual_published"] = True
            return True, [{"id": "residual"}], debug, {"rr": "residual"}
        return False, [], debug, {"rr": "residual_unused"}

    def branch_result(name, kwargs, *, needs_previous=False):
        state_publish_at = publish_at(kwargs)
        previous = bool(kwargs.get("previous_branch_taken"))
        calls.append({"event": name, "publish_at": state_publish_at, "previous": previous})
        debug = dict(kwargs.get("guidance_debug") or {})
        if state_publish_at == name and (not needs_previous or previous):
            debug[f"{name}_published"] = True
            return True, [{"id": name}], debug, {"rr": name}
        return False, [], debug, {"rr": f"{name}_unused"}

    def post_active(**kwargs):
        calls.append(
            {
                "event": "post_active",
                "publish_at": publish_at(kwargs),
                "residual_width_cleanup_published": bool(kwargs.get("residual_width_cleanup_published")),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        if publish_at(kwargs) == "post_active":
            debug["post_active_published"] = True
            return True, [{"id": "post_active"}], debug, {"rr": "post_active"}
        return False, [], debug, {"rr": "post_active_unused"}

    def secondary(**kwargs):
        return branch_result("secondary", kwargs)

    def local(**kwargs):
        return branch_result("local", kwargs)

    def exact(**kwargs):
        return branch_result("exact", kwargs, needs_previous=True)

    def required(**kwargs):
        return branch_result("required", kwargs, needs_previous=True)

    def invalid(**kwargs):
        return branch_result("invalid", kwargs, needs_previous=True)

    stage_events: list[str] = []

    def stage(name: str) -> None:
        stage_events.append(name)

    try:
        inputs_page.render_design_guide_residual_width_cleanup_candidate = residual_candidate
        inputs_page.render_design_guide_residual_width_cleanup_publication = residual_publication
        inputs_page.render_design_guide_post_active_accepted_green_publication = post_active
        inputs_page.render_design_guide_post_click_target_accepted_secondary_blocker = secondary
        inputs_page.render_design_guide_post_apply_local_cleanup_accepted = local
        inputs_page.render_design_guide_post_apply_exact_low_util_blocker = exact
        inputs_page.render_design_guide_post_apply_required_checks_pass_terminal = required
        inputs_page.render_design_guide_post_click_invalid_accepted_cleanup_resolution = invalid

        residual_items, residual_debug, residual_rr, residual_invalid_taken = (
            inputs_page.render_design_guide_post_apply_publication_chain(
                guidance_items=[{"id": "original"}],
                guidance_debug={},
                guidance_disp_state={"publish_at": "residual"},
                render_overview={},
                render_mode_config={},
                render_acceptance_audit={},
                render_acceptance_overview={},
                render_post_active_failure_repair=False,
                family_speed_isolated_bending_repair=False,
                render_combined_terminal_apply_ready=False,
                branch_for_recommendation="branch",
                recommendation_result={"rr": "original"},
                stage=stage,
            )
        )

        invalid_items, invalid_debug, invalid_rr, invalid_taken = (
            inputs_page.render_design_guide_post_apply_publication_chain(
                guidance_items=[{"id": "original"}],
                guidance_debug={},
                guidance_disp_state={"publish_at": "invalid"},
                render_overview={},
                render_mode_config={},
                render_acceptance_audit={},
                render_acceptance_overview={},
                render_post_active_failure_repair=False,
                family_speed_isolated_bending_repair=False,
                render_combined_terminal_apply_ready=False,
                branch_for_recommendation="branch",
                recommendation_result={"rr": "original"},
                stage=stage,
            )
        )

        local_items, local_debug, local_rr, local_invalid_taken = (
            inputs_page.render_design_guide_post_apply_publication_chain(
                guidance_items=[{"id": "original"}],
                guidance_debug={},
                guidance_disp_state={"publish_at": "local"},
                render_overview={},
                render_mode_config={},
                render_acceptance_audit={},
                render_acceptance_overview={},
                render_post_active_failure_repair=False,
                family_speed_isolated_bending_repair=False,
                render_combined_terminal_apply_ready=False,
                branch_for_recommendation="branch",
                recommendation_result={"rr": "original"},
                stage=stage,
            )
        )
    finally:
        inputs_page.render_design_guide_residual_width_cleanup_candidate = originals["candidate"]
        inputs_page.render_design_guide_residual_width_cleanup_publication = originals["residual_publication"]
        inputs_page.render_design_guide_post_active_accepted_green_publication = originals["post_active"]
        inputs_page.render_design_guide_post_click_target_accepted_secondary_blocker = originals["secondary"]
        inputs_page.render_design_guide_post_apply_local_cleanup_accepted = originals["local"]
        inputs_page.render_design_guide_post_apply_exact_low_util_blocker = originals["exact"]
        inputs_page.render_design_guide_post_apply_required_checks_pass_terminal = originals["required"]
        inputs_page.render_design_guide_post_click_invalid_accepted_cleanup_resolution = originals["invalid"]

    expect(
        "residual_publication_replaces_items_and_rr",
        residual_items == [{"id": "residual"}]
        and residual_debug.get("residual_published") is True
        and residual_rr == {"rr": "residual"}
        and residual_invalid_taken is False,
        f"items={residual_items} debug={residual_debug} rr={residual_rr} invalid={residual_invalid_taken}",
    )
    expect(
        "invalid_publication_uses_previous_branch_chain",
        invalid_items == [{"id": "original"}]
        and invalid_debug == {}
        and invalid_rr == {"rr": "original"}
        and invalid_taken is False,
        f"items={invalid_items} debug={invalid_debug} rr={invalid_rr} invalid={invalid_taken}",
    )
    expect(
        "local_publication_updates_then_propagates_previous_flag",
        local_items == [{"id": "local"}]
        and local_debug.get("local_published") is True
        and local_rr == {"rr": "local"}
        and any(call["event"] == "exact" and call["publish_at"] == "local" and call["previous"] is True for call in calls)
        and any(call["event"] == "required" and call["publish_at"] == "local" and call["previous"] is True for call in calls)
        and any(call["event"] == "invalid" and call["publish_at"] == "local" and call["previous"] is True for call in calls),
        f"items={local_items} debug={local_debug} rr={local_rr} calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "residual_items": residual_items,
        "residual_debug": residual_debug,
        "residual_rr": residual_rr,
        "residual_invalid_taken": residual_invalid_taken,
        "invalid_items": invalid_items,
        "invalid_debug": invalid_debug,
        "invalid_rr": invalid_rr,
        "invalid_taken": invalid_taken,
        "local_items": local_items,
        "local_debug": local_debug,
        "local_rr": local_rr,
        "local_invalid_taken": local_invalid_taken,
        "calls": calls,
        "stage_events": stage_events,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Apply Publication Chain Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
