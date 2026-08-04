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
        self.markdown_calls: list[dict[str, Any]] = []
        self.button_calls: list[dict[str, Any]] = []

    def markdown(self, body, **kwargs):
        self.markdown_calls.append({"body": body, **dict(kwargs)})

    def button(self, label, **kwargs):
        self.button_calls.append({"label": label, **dict(kwargs)})
        return False


class FakeSlot:
    def __init__(self) -> None:
        self.empty_count = 0
        self.container_count = 0

    def empty(self) -> None:
        self.empty_count += 1

    def container(self):
        slot = self

        class _Container:
            def __enter__(self):
                slot.container_count += 1
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Container()


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_missing_card_recovery_render_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_missing_card_recovery_render_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "st",
        "_build_final_design_guide_publication",
        "_build_final_design_guide_card_format",
        "_render_final_design_guide_card_html",
        "_design_guide_button_contract_enabled",
        "_queue_primary_design_guide_button_action",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    publication_calls: list[dict[str, Any]] = []
    tail_recovery_calls: list[dict[str, Any]] = []

    fake_st = FakeStreamlit()
    fake_slot = FakeSlot()

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def build_publication(**kwargs):
        publication_calls.append(dict(kwargs))
        return {"publication": True, **dict(kwargs)}

    def build_format(publication):
        return {"format": True, "publication": dict(publication)}

    def render_html(card_format):
        return "<div>Recovered card</div>"

    def contract_enabled(contract):
        return bool(contract.get("enabled") or contract.get("actionable"))

    def tail_recovery(**kwargs):
        tail_recovery_calls.append(dict(kwargs))
        return True

    try:
        inputs_page.st = fake_st
        inputs_page._build_final_design_guide_publication = build_publication
        inputs_page._build_final_design_guide_card_format = build_format
        inputs_page._render_final_design_guide_card_html = render_html
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._queue_primary_design_guide_button_action = lambda *args, **kwargs: None

        bundle = {
            "final_publication_verifier_payload": {"publication_hash": "pub-hash"},
        }
        inputs_page.render_inputs_design_guide_missing_card_recovery_render_coordinator(
            design_guide_slot=fake_slot,
            dg_bundle_after_render=bundle,
            fallback_title="Recovered title",
            fallback_item={"title_main": "Recovered title"},
            fallback_rec={"title": "Recovered title"},
            fallback_contract={
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "updates": {"D": 450},
            },
            fallback_publication_hash="authority-hash",
            fallback_cta_authority={"cta_hash": "cta-hash"},
            fallback_display_authority={"display_hash": "display-hash"},
            show_design_guide_for_current_inputs=True,
            render_design_guide_slot_from_final_publication_payload_fn=tail_recovery,
        )
    finally:
        _restore()

    if len(publication_calls) != 1:
        failures.append(f"publication_call_count_mismatch:{len(publication_calls)}")
    else:
        call = publication_calls[0]
        if call.get("publication_reason") != "render_final_panel_missing_card_recovery":
            failures.append(f"publication_reason_mismatch:{call}")
        if call.get("item", {}).get("title_main") != "Recovered title":
            failures.append(f"publication_item_mismatch:{call}")
    if fake_slot.empty_count != 1 or fake_slot.container_count != 1:
        failures.append(f"slot_render_mismatch:empty={fake_slot.empty_count} container={fake_slot.container_count}")
    if not fake_st.markdown_calls or fake_st.markdown_calls[0].get("body") != "### Design Guide":
        failures.append(f"design_guide_heading_missing:{fake_st.markdown_calls}")
    if len(fake_st.button_calls) != 1:
        failures.append(f"button_call_count_mismatch:{len(fake_st.button_calls)}")
    else:
        button = fake_st.button_calls[0]
        if button.get("label") != "Apply: Recovered title":
            failures.append(f"button_label_mismatch:{button}")
        if button.get("key") != "apply_design_guide_missing_card_recovery":
            failures.append(f"button_key_mismatch:{button}")
        args = tuple(button.get("args") or ())
        if len(args) != 4 or args[1] != "handle_apply_buttons":
            failures.append(f"button_args_mismatch:{button}")
    probe = dict(bundle.get("actual_card_render_probe") or {})
    if probe.get("marker") != "render_final_panel_missing_card_clean_recovery":
        failures.append(f"probe_marker_mismatch:{probe}")
    if probe.get("render_button_contract_enabled") is not True:
        failures.append(f"probe_enabled_mismatch:{probe}")
    if probe.get("final_publication_authority_hash") != "authority-hash":
        failures.append(f"publication_hash_mismatch:{probe}")
    if bundle.get("render_final_panel_missing_card_clean_recovery") is not True:
        failures.append(f"clean_recovery_flag_missing:{bundle}")
    if bundle.get("fallback_enabled_contract_shell_deleted") is not True:
        failures.append(f"fallback_deleted_flag_missing:{bundle}")
    if fake_st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY) != bundle:
        failures.append("debug_bundle_not_written_to_session")
    if tail_recovery_calls:
        failures.append(f"tail_recovery_should_not_run_when_card_rendered:{tail_recovery_calls}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_missing_card_recovery_render_coordinator" not in source:
        failures.append("missing_card_recovery_render_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_fallback_clean_recovery_rendered =",
        "_fallback_clean_recovery_error =",
        "_fallback_publication =",
        "_fallback_apply_label =",
        "_post_recovery_probe =",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_design_guide_missing_card_recovery_render_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "publication_call_count": len(publication_calls),
        "button_call_count": len(fake_st.button_calls),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Missing-Card Recovery Render Coordinator Verifier",
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
