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
    json_path = ARTIFACT_DIR / f"inputs_page_acceptance_audit_state_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_acceptance_audit_state_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    fake_st = _FakeStreamlit()
    route_overview = {
        "any_fail": False,
        "utils": {"bending": 0.91, "shear": 0.90},
        "statuses": {"bending": "PASS", "shear": "PASS"},
    }
    fake_st.session_state[inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
        "post_apply_resolved_candidate_attempted": True,
        "resolved_candidate_family_tag": "bending",
        "resolved_candidate_label": "bending capacity repair",
        "post_apply_overview": dict(route_overview),
    }

    stages: list[str] = []
    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_post_click_accepted_green_audit": inputs_page._post_click_accepted_green_audit,
        "_local_cleanup_post_apply_acceptance_matches": inputs_page._local_cleanup_post_apply_acceptance_matches,
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "_post_apply_combined_chained_terminal_recent_refresh_ready": inputs_page._post_apply_combined_chained_terminal_recent_refresh_ready,
    }
    try:
        inputs_page.st = fake_st
        inputs_page._post_click_accepted_green_audit = lambda overview, blocker_source, state: {
            "post_click_accepted_green": True,
            "post_click_accepted_green_valid": True,
            "post_click_design_guide_state": "accepted_green",
            "terminal_state_reason": "verifier_acceptance",
        }
        inputs_page._local_cleanup_post_apply_acceptance_matches = lambda state: True
        inputs_page._overview_required_checks_acceptable = lambda overview: True
        inputs_page._post_apply_combined_chained_terminal_recent_refresh_ready = lambda route, state: False

        (
            acceptance_audit,
            guidance_debug,
            last_apply_route,
            last_apply_label,
            last_apply_family,
            combined_terminal_ready,
            acceptance_overview,
            post_active_failure_repair,
        ) = inputs_page.render_design_guide_acceptance_audit_state(
            guidance_disp_state={"D": 500},
            guidance_debug={"existing": True},
            render_overview=dict(route_overview),
            family_speed_isolated_bending_repair=False,
            stage=lambda label: stages.append(str(label)),
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    failures: list[str] = []
    if stages != ["after_render_acceptance_audit"]:
        failures.append(f"stage_order_mismatch:{stages}")
    if acceptance_audit.get("terminal_state_reason") != "verifier_acceptance":
        failures.append(f"acceptance_audit_mismatch:{acceptance_audit}")
    if guidance_debug.get("terminal_state_reason") != "verifier_acceptance":
        failures.append(f"guidance_debug_not_updated:{guidance_debug}")
    if last_apply_family != "bending":
        failures.append(f"last_apply_family_mismatch:{last_apply_family}")
    if last_apply_label != "bending capacity repair":
        failures.append(f"last_apply_label_mismatch:{last_apply_label}")
    if combined_terminal_ready is not False:
        failures.append(f"combined_terminal_ready_mismatch:{combined_terminal_ready}")
    if post_active_failure_repair is not True:
        failures.append(f"post_active_failure_repair_mismatch:{post_active_failure_repair}")
    if acceptance_overview != route_overview:
        failures.append(f"acceptance_overview_mismatch:{acceptance_overview}")
    if last_apply_route.get("post_apply_overview") != route_overview:
        failures.append("last_apply_route_not_preserved")

    payload = {
        "verifier": "inputs_page_acceptance_audit_state_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "stages": stages,
        "acceptance_audit": acceptance_audit,
        "last_apply_family": last_apply_family,
        "last_apply_label": last_apply_label,
        "combined_terminal_ready": combined_terminal_ready,
        "post_active_failure_repair": post_active_failure_repair,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Acceptance Audit State Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                f"- stages: `{stages}`",
                f"- last apply family: `{last_apply_family}`",
                f"- last apply label: `{last_apply_label}`",
                f"- post-active repair: `{post_active_failure_repair}`",
                f"- acceptance audit: `{acceptance_audit}`",
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
