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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_render_design_guide_item_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_render_design_guide_item_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    contract = {
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": {"bot": 4},
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "source_candidate_id": "candidate-1",
    }
    bundle = {
        "primary_card_title": "Shear cleanup - reduce links",
        "candidate_search_evidence": {"evidence": True},
        "primary_guidance_intent": "efficiency_tightening",
    }
    title, item = inputs_page.render_inputs_pre_render_design_guide_item_coordinator(
        pre_render_dg_bundle=bundle,
        pre_render_contract=contract,
        pre_render_canonical_family="BENDING_OVERDESIGN_GOVERNS",
        pre_render_safe_combined_promoted=False,
        pre_render_safe_combined_updates={},
    )
    if title != "Bending cleanup - best safe one-click reduction":
        failures.append(f"title_correction_mismatch:{title}")
    if bundle.get("primary_card_title") != title:
        failures.append(f"bundle_title_not_updated:{bundle}")
    expected_base_subset = {
        "title_main": title,
        "title": title,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "check_key": "bending",
        "updates": {"bot": 4},
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "candidate_id": "candidate-1",
        "source_candidate_id": "candidate-1",
        "candidate_search_evidence": {"evidence": True},
        "guidance_intent": "efficiency_tightening",
    }
    for key, expected in expected_base_subset.items():
        if item.get(key) != expected:
            failures.append(f"base_item_{key}_mismatch:{item.get(key)}")
    if item.get("button_contract") != contract:
        failures.append("base_item_button_contract_mismatch")

    combined_title, combined_item = inputs_page.render_inputs_pre_render_design_guide_item_coordinator(
        pre_render_dg_bundle={"selected_title": "Combined cleanup"},
        pre_render_contract={
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": {"lig": 200},
            "candidate_id": "candidate-2",
        },
        pre_render_canonical_family="SHEAR_OVERDESIGN_GOVERNS",
        pre_render_safe_combined_promoted=True,
        pre_render_safe_combined_updates={"lig": 250, "bot": 3},
    )
    if combined_title != "Combined cleanup":
        failures.append(f"combined_title_mismatch:{combined_title}")
    combined_expected = {
        "family": "combined",
        "check_key": "combined",
        "selected_action_family": "combined",
        "updates": {"lig": 250, "bot": 3},
        "selected_action_updates": {"lig": 250, "bot": 3},
        "selected_family_id": "COMBINED_OVERDESIGN",
        "selected_family": "COMBINED_OVERDESIGN",
        "published_family_id": "COMBINED_OVERDESIGN",
        "cta_family_id": "COMBINED_OVERDESIGN",
        "candidate_family_id": "COMBINED_OVERDESIGN",
        "card_family_id": "COMBINED_OVERDESIGN",
        "apply_payload_family_id": "COMBINED_OVERDESIGN",
        "family_match_passed": True,
        "family_match_violation_reason": None,
    }
    for key, expected in combined_expected.items():
        if combined_item.get(key) != expected:
            failures.append(f"combined_item_{key}_mismatch:{combined_item.get(key)}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_pre_render_design_guide_item_coordinator" not in source:
        failures.append("pre_render_design_guide_item_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    if "locals().get(\"_pre_render_canonical_family\")" in fresh_panel:
        failures.append("fresh_panel_still_uses_local_canonical_family_lookup")

    payload = {
        "verifier": "inputs_page_pre_render_design_guide_item_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre-Render Design Guide Item Coordinator Verifier",
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
