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


class Projection:
    title = "Projected pre-render title"
    pill = "ACTION"
    shell_model = {"shell": "model"}
    view_model = {"view": "model"}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_pre_render_direct_action_publication_probe_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_render_direct_action_publication_probe_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "st",
        "_record_rendered_design_guide_primary_apply_payload",
        "_shared_state_snapshot",
        "_stamp_final_publication_cta_authority",
        "_overview_active_failure_keys",
        "_build_final_design_guide_direct_shell_card_projection",
        "_design_guide_button_contract_enabled",
        "_stamp_final_publication_display_authority",
        "_final_publication_authority_hash_from_parts",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    payload_calls: list[dict[str, Any]] = []
    cta_calls: list[dict[str, Any]] = []
    projection_calls: list[dict[str, Any]] = []
    display_calls: list[dict[str, Any]] = []

    fake_st = FakeStreamlit()

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def record_payload(**kwargs):
        payload_calls.append(dict(kwargs))
        return {"payload": "ok"}

    def stamp_cta(**kwargs):
        cta_calls.append(dict(kwargs))
        contract = dict(kwargs.get("button_contract") or {})
        contract["cta_stamped"] = True
        return contract, {"cta_hash": "cta-hash"}

    def projection(**kwargs):
        projection_calls.append(dict(kwargs))
        return Projection()

    def stamp_display(**kwargs):
        display_calls.append(dict(kwargs))
        return {"display_hash": "display-hash"}

    try:
        inputs_page.st = fake_st
        inputs_page._record_rendered_design_guide_primary_apply_payload = record_payload
        inputs_page._shared_state_snapshot = lambda: {"state": "current"}
        inputs_page._stamp_final_publication_cta_authority = stamp_cta
        inputs_page._overview_active_failure_keys = lambda overview: ["shear"] if overview.get("shear") else []
        inputs_page._build_final_design_guide_direct_shell_card_projection = projection
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))
        inputs_page._stamp_final_publication_display_authority = stamp_display
        inputs_page._final_publication_authority_hash_from_parts = (
            lambda *, cta_hash, display_hash: f"{cta_hash}::{display_hash}"
        )
        bundle = {
            "design_guide_render_eligibility_trace": {"existing": True},
            "final_publication_verifier_payload": {"publication_hash": "pub-hash"},
        }
        inputs_page.render_inputs_pre_render_direct_action_publication_probe_coordinator(
            pre_render_title="Pre-render title",
            pre_render_item={"title_main": "Pre-render title", "governing_label": "shear"},
            pre_render_rec={"title": "Pre-render rec"},
            pre_render_contract={
                "enabled": True,
                "family": "shear",
                "expected_util": 0.76,
                "preview_pass": True,
                "updates": {"N12": 4},
            },
            pre_render_overview_for_boundary={"shear": True},
            pre_render_dg_bundle=bundle,
        )
    finally:
        _restore()

    if len(payload_calls) != 1 or payload_calls[0].get("state") != {"state": "current"}:
        failures.append(f"payload_call_mismatch:{payload_calls}")
    if len(cta_calls) != 1 or cta_calls[0].get("fallback_only") is not True:
        failures.append(f"cta_call_mismatch:{cta_calls}")
    if len(projection_calls) != 1:
        failures.append(f"projection_call_count_mismatch:{len(projection_calls)}")
    elif projection_calls[0].get("pill") != "ACTION":
        failures.append(f"projection_pill_mismatch:{projection_calls[0]}")
    if len(display_calls) != 1 or display_calls[0].get("fallback_only") is not True:
        failures.append(f"display_call_mismatch:{display_calls}")
    trace = bundle.get("design_guide_render_eligibility_trace")
    if not isinstance(trace, dict) or trace.get("real_design_guide_card_rendered_source") != "pre_render_direct_action_shell":
        failures.append(f"eligibility_trace_mismatch:{trace}")
    probe = dict(bundle.get("actual_card_render_probe") or {})
    if probe.get("marker") != "browser_enabled_contract_pre_render_shell_deleted":
        failures.append(f"probe_marker_mismatch:{probe}")
    if probe.get("item_title") != "Projected pre-render title":
        failures.append(f"probe_title_mismatch:{probe}")
    if probe.get("final_publication_authority_hash") != "cta-hash::display-hash":
        failures.append(f"probe_hash_mismatch:{probe}")
    if bundle.get("pre_render_enabled_contract_shell_deleted") is not True:
        failures.append(f"pre_render_deleted_flag_missing:{bundle}")
    if fake_st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY) != bundle:
        failures.append("bundle_not_written_to_session")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_pre_render_direct_action_publication_probe_coordinator" not in source:
        failures.append("pre_render_direct_action_publication_probe_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_pre_render_payload =",
        "_pre_render_cta_authority =",
        "_pre_render_shell_projection =",
        "_pre_render_display_authority =",
        "_pre_render_publication_hash =",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_pre_render_direct_action_publication_probe_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "payload_call_count": len(payload_calls),
        "projection_call_count": len(projection_calls),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre-Render Direct Action Publication Probe Coordinator Verifier",
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
