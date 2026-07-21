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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_missing_card_fallback_identity_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_missing_card_fallback_identity_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_canonical = inputs_page._canonical_overdesign_family_from_updates
    failures: list[str] = []

    bundle: dict[str, Any] = {
        "primary_card_title": "Shear cleanup - one-click optimisation",
        "primary_guidance_intent": "efficiency_tightening",
        "selection_reason": "family chooser selected bending cleanup",
        "family_route_owner": "family_chooser",
        "candidate_search_evidence": {
            "matched_family_ids": ["BENDING_OVERDESIGN_GOVERNS"],
            "selection_evidence": {"source": "candidate-search"},
            "bending_fail_contract_ladder_found_safe": True,
        },
        "recommendation_result": {
            "title": "Existing recommendation",
            "updates": {"D": 450},
        },
    }
    fallback_contract = {
        "enabled": True,
        "action_type": "apply_resolved_candidate",
        "family": "shear",
        "updates": {"D": 450},
        "source_candidate_id": "candidate-1",
    }

    try:
        inputs_page._canonical_overdesign_family_from_updates = (
            lambda family, updates: "BENDING_OVERDESIGN_GOVERNS"
        )
        title, contract, item, rec = (
            inputs_page.render_inputs_design_guide_missing_card_fallback_identity_coordinator(
                dg_bundle_after_render=bundle,
                fallback_contract=fallback_contract,
            )
        )
    finally:
        inputs_page._canonical_overdesign_family_from_updates = original_canonical

    if title != "Bending cleanup - best safe one-click reduction":
        failures.append(f"title_not_corrected:{title}")
    for key in (
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "candidate_family_id",
        "card_family_id",
        "apply_payload_family_id",
    ):
        if contract.get(key) != "BENDING_OVERDESIGN_GOVERNS":
            failures.append(f"contract_family_key_mismatch:{key}:{contract}")
        if bundle.get(key) != "BENDING_OVERDESIGN_GOVERNS":
            failures.append(f"bundle_family_key_mismatch:{key}:{bundle}")
        if item.get(key) != "BENDING_OVERDESIGN_GOVERNS":
            failures.append(f"item_family_key_mismatch:{key}:{item}")
    if bundle.get("primary_card_title") != title:
        failures.append(f"bundle_title_mismatch:{bundle}")
    if item.get("candidate_id") != "candidate-1" or item.get("source_candidate_id") != "candidate-1":
        failures.append(f"candidate_id_mismatch:{item}")
    if item.get("selection_reason") != "family chooser selected bending cleanup":
        failures.append(f"selection_reason_not_copied:{item}")
    if item.get("family_route_owner") != "family_chooser":
        failures.append(f"family_route_owner_not_copied:{item}")
    if item.get("matched_family_ids") != ["BENDING_OVERDESIGN_GOVERNS"]:
        failures.append(f"matched_family_ids_not_copied:{item}")
    if item.get("selection_evidence") != {"source": "candidate-search"}:
        failures.append(f"selection_evidence_not_copied:{item}")
    if item.get("family_selection_source") != "family_chooser_contract":
        failures.append(f"default_family_selection_source_missing:{item}")
    if rec != {"title": "Existing recommendation", "updates": {"D": 450}}:
        failures.append(f"recommendation_result_mismatch:{rec}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_missing_card_fallback_identity_coordinator" not in source:
        failures.append("missing_card_fallback_identity_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_fallback_canonical_family =",
        "_fallback_candidate_evidence =",
        "_fallback_identity_sources =",
        "_fallback_selected_family =",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_design_guide_missing_card_fallback_identity_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Missing-Card Fallback Identity Coordinator Verifier",
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
