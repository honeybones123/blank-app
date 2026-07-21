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


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_post_render_probe_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_post_render_probe_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "st",
        "_design_guide_button_contract_enabled",
        "_apply_final_publication_cta_to_primary_render_contract",
        "_shared_state_snapshot",
        "_design_guide_primary_apply_state_fingerprint",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    projection_calls: list[dict[str, Any]] = []
    recovery_calls: list[dict[str, Any]] = []

    fake_st = FakeStreamlit()

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def contract_enabled(contract: dict) -> bool:
        return bool(contract.get("enabled") or contract.get("actionable"))

    def project_cta(*, item, existing_contract, debug_sink, state):
        projection_calls.append(
            {
                "item": dict(item),
                "existing_contract": dict(existing_contract),
                "debug_sink_is_bundle": isinstance(debug_sink, dict),
                "state": dict(state),
            }
        )
        return (
            {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "bending",
                "updates": {"D": 450},
            },
            True,
        )

    def recover_from_publication_payload(**kwargs):
        recovery_calls.append(dict(kwargs))
        fake_st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = {
            "actual_card_render_probe": {
                "marker": "early_final_publication_payload_render",
                "render_button_contract_enabled": True,
            }
        }
        return True

    try:
        inputs_page.st = fake_st
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._apply_final_publication_cta_to_primary_render_contract = project_cta
        inputs_page._shared_state_snapshot = lambda: {"state": "current"}
        inputs_page._design_guide_primary_apply_state_fingerprint = lambda state: "state-fp"

        bundle = {
            "primary_card_title": "Projected card",
            "final_publication_verifier_payload": {"cta": {"enabled": True}},
            "actual_card_render_probe": {
                "marker": "browser_enabled_contract_pre_render_shell_deleted"
            },
        }
        returned_bundle, fallback_contract, projected, rendered = (
            inputs_page.render_inputs_design_guide_post_render_probe_coordinator(
                dg_bundle_after_render=bundle,
                render_design_guide_slot_from_final_publication_payload_fn=recover_from_publication_payload,
            )
        )

        if not projected:
            failures.append("publication_cta_projection_not_reported")
        if not rendered:
            failures.append("recovered_probe_not_reported_rendered")
        if returned_bundle is not fake_st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY]:
            failures.append("recovered_bundle_not_returned")
        if fallback_contract.get("updates") != {"D": 450}:
            failures.append(f"projected_contract_updates_mismatch:{fallback_contract}")
        if bundle.get("button_contract_enabled") is not True:
            failures.append(f"projected_bundle_flags_missing:{bundle}")
        if len(projection_calls) != 1:
            failures.append(f"projection_call_count_mismatch:{len(projection_calls)}")
        if recovery_calls != [{"source": "after_render_panel_authoritative_publication_projection"}]:
            failures.append(f"recovery_call_mismatch:{recovery_calls}")

        fake_st.session_state.clear()
        projection_calls.clear()
        recovery_calls.clear()
        fake_st.session_state[inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY] = {
            "updates": {"D": 450},
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "state_fingerprint": "state-fp",
        }
        bound_bundle = {
            "displayed_primary_button_contract": {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "bending",
                "updates": {"D": 450},
            },
            "actual_card_render_probe": {
                "marker": "fallback_enabled_contract_shell_deleted"
            },
        }
        returned_bound_bundle, _, projected_bound, rendered_bound = (
            inputs_page.render_inputs_design_guide_post_render_probe_coordinator(
                dg_bundle_after_render=bound_bundle,
                render_design_guide_slot_from_final_publication_payload_fn=lambda **kwargs: False,
            )
        )
    finally:
        _restore()

    if projected_bound:
        failures.append("enabled_contract_should_not_project_publication_cta")
    if rendered_bound:
        failures.append("deleted_marker_should_not_count_as_rendered")
    if returned_bound_bundle.get("fallback_enabled_contract_shell_payload_already_bound") is not True:
        failures.append(f"payload_already_bound_marker_missing:{returned_bound_bundle}")
    if (
        fake_st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY, {}).get(
            "fallback_enabled_contract_shell_payload_already_bound"
        )
        is not True
    ):
        failures.append("payload_already_bound_session_write_missing")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_post_render_probe_coordinator" not in source:
        failures.append("post_render_probe_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_publication_cta_fallback_item =",
        "_publication_payload_recovery =",
        "_rendered_primary_payload_after_render =",
        "_rendered_primary_payload_matches_fallback =",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_design_guide_post_render_probe_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "projection_call_count": len(projection_calls),
        "recovery_call_count": len(recovery_calls),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Post-Render Probe Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
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
