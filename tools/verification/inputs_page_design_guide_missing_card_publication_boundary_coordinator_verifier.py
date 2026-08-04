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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_missing_card_publication_boundary_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_missing_card_publication_boundary_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "enforce_underdesign_repair_publication_boundary",
        "enforce_family_selection_publication_contract",
        "_overview_active_failure_keys",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    underdesign_calls: list[dict[str, Any]] = []
    family_calls: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def active_failures(overview):
        return ["shear"] if overview.get("shear_fail") else []

    def underdesign(payload):
        underdesign_calls.append(dict(payload))
        item = dict(payload["guidance_items"][0])
        item["title_main"] = "Boundary fallback title"
        item["button_contract"] = {"action_type": "boundary", "updates": {"N12": 3}}
        debug = dict(payload.get("debug_trace") or {})
        debug["underdesign_boundary"] = True
        return {"guidance_items": [item], "debug_trace": debug}

    def family(payload):
        family_calls.append(dict(payload))
        item = dict(payload["guidance_items"][0])
        item["title"] = "Family fallback title"
        item["button_contract"] = {"action_type": "family", "updates": {"N16": 2}}
        debug = dict(payload.get("debug_trace") or {})
        debug["family_boundary"] = True
        return {"guidance_items": [item], "debug_trace": debug}

    try:
        inputs_page._overview_active_failure_keys = active_failures
        inputs_page.enforce_underdesign_repair_publication_boundary = underdesign
        inputs_page.enforce_family_selection_publication_contract = family
        bundle = {
            "overview": {"shear_fail": True},
            "debug_seed": True,
        }
        title, item, contract, overview = (
            inputs_page.render_inputs_design_guide_missing_card_publication_boundary_coordinator(
                fallback_title="Original fallback title",
                fallback_item={
                    "title_main": "Original fallback title",
                    "button_contract": {"action_type": "original", "updates": {"x": 1}},
                    "family_status_current": {"shear": "FAIL"},
                },
                fallback_contract={"action_type": "original", "updates": {"x": 1}},
                dg_bundle_after_render=bundle,
            )
        )
    finally:
        _restore()

    if title != "Boundary fallback title":
        failures.append(f"title_mismatch:{title}")
    if item.get("title") != "Family fallback title":
        failures.append(f"item_title_mismatch:{item}")
    if contract != {"action_type": "family", "updates": {"N16": 2}}:
        failures.append(f"contract_mismatch:{contract}")
    if overview != {"shear_fail": True}:
        failures.append(f"overview_mismatch:{overview}")
    if bundle.get("underdesign_boundary") is not True or bundle.get("family_boundary") is not True:
        failures.append(f"bundle_debug_updates_missing:{bundle}")
    if len(underdesign_calls) != 1 or len(family_calls) != 1:
        failures.append(
            f"boundary_call_count_mismatch:underdesign={len(underdesign_calls)} family={len(family_calls)}"
        )
    else:
        if underdesign_calls[0].get("active_failures") != ["shear"]:
            failures.append(f"underdesign_active_failures_mismatch:{underdesign_calls[0]}")
        if family_calls[0].get("active_failures") != ["shear"]:
            failures.append(f"family_active_failures_mismatch:{family_calls[0]}")
        if family_calls[0]["guidance_items"][0].get("title_main") != "Boundary fallback title":
            failures.append(f"family_did_not_receive_underdesign_item:{family_calls[0]}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_missing_card_publication_boundary_coordinator" not in source:
        failures.append("missing_card_publication_boundary_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_fallback_boundary_payload =",
        "_fallback_boundary_items =",
        "_fallback_family_payload =",
        "_fallback_family_items =",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_design_guide_missing_card_publication_boundary_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "underdesign_call_count": len(underdesign_calls),
        "family_call_count": len(family_calls),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Missing-Card Publication Boundary Coordinator Verifier",
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
