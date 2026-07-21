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


class Projection:
    title = "Projected fallback title"
    pill = "ACTION"
    shell_model = {"shell": "model"}
    view_model = {"view": "model"}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_missing_card_publication_authority_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_missing_card_publication_authority_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
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
    hash_calls: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def record_payload(**kwargs):
        payload_calls.append(dict(kwargs))
        return {"payload": "ok", "updates": dict(kwargs.get("button_contract", {}).get("updates") or {})}

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

    def hash_parts(**kwargs):
        hash_calls.append(dict(kwargs))
        return f"{kwargs.get('cta_hash')}::{kwargs.get('display_hash')}"

    try:
        inputs_page._record_rendered_design_guide_primary_apply_payload = record_payload
        inputs_page._shared_state_snapshot = lambda: {"state": "current"}
        inputs_page._stamp_final_publication_cta_authority = stamp_cta
        inputs_page._overview_active_failure_keys = lambda overview: ["bending"] if overview.get("bending") else []
        inputs_page._build_final_design_guide_direct_shell_card_projection = projection
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))
        inputs_page._stamp_final_publication_display_authority = stamp_display
        inputs_page._final_publication_authority_hash_from_parts = hash_parts

        title, contract, publication_hash, cta_authority, display_authority = (
            inputs_page.render_inputs_design_guide_missing_card_publication_authority_coordinator(
                fallback_title="Fallback title",
                fallback_item={"title_main": "Fallback title", "governing_label": "bending"},
                fallback_rec={"title": "Fallback rec"},
                fallback_contract={
                    "enabled": True,
                    "family": "bending",
                    "expected_util": 0.82,
                    "preview_pass": True,
                    "updates": {"D": 450},
                },
                fallback_overview_for_boundary={"bending": True},
                dg_bundle_after_render={"debug": True},
            )
        )
    finally:
        _restore()

    if title != "Projected fallback title":
        failures.append(f"title_mismatch:{title}")
    if contract.get("cta_stamped") is not True:
        failures.append(f"cta_contract_not_returned:{contract}")
    if publication_hash != "cta-hash::display-hash":
        failures.append(f"publication_hash_mismatch:{publication_hash}")
    if cta_authority != {"cta_hash": "cta-hash"}:
        failures.append(f"cta_authority_mismatch:{cta_authority}")
    if display_authority != {"display_hash": "display-hash"}:
        failures.append(f"display_authority_mismatch:{display_authority}")
    if len(payload_calls) != 1 or payload_calls[0].get("state") != {"state": "current"}:
        failures.append(f"payload_call_mismatch:{payload_calls}")
    if len(cta_calls) != 1 or cta_calls[0].get("fallback_only") is not True:
        failures.append(f"cta_call_mismatch:{cta_calls}")
    if len(projection_calls) != 1:
        failures.append(f"projection_call_count_mismatch:{len(projection_calls)}")
    else:
        projection_call = projection_calls[0]
        if projection_call.get("pill") != "ACTION":
            failures.append(f"projection_pill_mismatch:{projection_call}")
        if projection_call.get("current_overview") != {"bending": True}:
            failures.append(f"projection_overview_mismatch:{projection_call}")
    if len(display_calls) != 1 or display_calls[0].get("fallback_only") is not True:
        failures.append(f"display_call_mismatch:{display_calls}")
    if len(hash_calls) != 1 or hash_calls[0] != {"cta_hash": "cta-hash", "display_hash": "display-hash"}:
        failures.append(f"hash_call_mismatch:{hash_calls}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_missing_card_publication_authority_coordinator" not in source:
        failures.append("missing_card_publication_authority_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_fallback_payload =",
        "_fallback_cta_authority =",
        "_fallback_shell_projection =",
        "_fallback_display_authority =",
        "_fallback_publication_hash =",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_design_guide_missing_card_publication_authority_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "payload_call_count": len(payload_calls),
        "projection_call_count": len(projection_calls),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Missing-Card Publication Authority Coordinator Verifier",
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
