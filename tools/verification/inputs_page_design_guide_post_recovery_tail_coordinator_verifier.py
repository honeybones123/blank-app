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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_post_recovery_tail_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_post_recovery_tail_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    recovery_calls: list[dict] = []

    def recover(**kwargs):
        recovery_calls.append(dict(kwargs))
        return True

    inputs_page.render_inputs_design_guide_post_recovery_tail_coordinator(
        dg_bundle_after_render={
            "actual_card_render_probe": {
                "marker": "fallback_enabled_contract_shell_deleted",
                "render_button_contract_enabled": False,
            }
        },
        show_design_guide_for_current_inputs=True,
        design_guide_slot=object(),
        render_design_guide_slot_from_final_publication_payload_fn=recover,
    )
    if recovery_calls != [{"source": "after_tail_final_panel_publication_payload_recovery"}]:
        failures.append(f"tail_recovery_call_mismatch:{recovery_calls}")

    recovery_calls.clear()
    inputs_page.render_inputs_design_guide_post_recovery_tail_coordinator(
        dg_bundle_after_render={
            "actual_card_render_probe": {
                "marker": "render_final_panel_missing_card_clean_recovery",
                "render_button_contract_enabled": True,
            }
        },
        show_design_guide_for_current_inputs=True,
        design_guide_slot=object(),
        render_design_guide_slot_from_final_publication_payload_fn=recover,
    )
    if recovery_calls:
        failures.append(f"tail_recovery_called_when_card_rendered:{recovery_calls}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_post_recovery_tail_coordinator" not in source:
        failures.append("post_recovery_tail_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    if "render_inputs_design_guide_post_recovery_tail_coordinator(" not in fresh_panel:
        failures.append("fresh_panel_does_not_call_tail_coordinator")
    missing_card_call = fresh_panel.find(
        "render_inputs_design_guide_missing_card_recovery_render_coordinator("
    )
    tail_call = fresh_panel.find("render_inputs_design_guide_post_recovery_tail_coordinator(")
    if missing_card_call == -1 or tail_call == -1 or tail_call < missing_card_call:
        failures.append("tail_coordinator_not_after_missing_card_recovery_call")

    payload = {
        "verifier": "inputs_page_design_guide_post_recovery_tail_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Post-Recovery Tail Coordinator Verifier",
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
