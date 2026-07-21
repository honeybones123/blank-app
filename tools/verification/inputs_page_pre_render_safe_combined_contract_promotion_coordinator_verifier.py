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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_render_safe_combined_contract_promotion_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_render_safe_combined_contract_promotion_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "_shared_state_snapshot",
        "_float_from_state",
        "_updates_match_state",
        "_COMPOUND_SHEAR_UPDATE_KEYS",
        "_COMPOUND_BOTTOM_UPDATE_KEYS",
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
        "TARGET_BAND_EPS",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def float_from_state(state, key, default=0.0):
        return state.get(key, default)

    try:
        inputs_page._shared_state_snapshot = lambda: {"uls_Vstar": 120.0, "Vu_star": 0.0}
        inputs_page._float_from_state = float_from_state
        inputs_page._updates_match_state = lambda state, updates: False
        inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"sv"}
        inputs_page._COMPOUND_BOTTOM_UPDATE_KEYS = {"bot"}
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.75
        inputs_page.TARGET_BAND_EPS = 0.001

        contract = {
            "selected_family_id": "COMBINED_OVERDESIGN",
            "family": "combined",
        }
        proof = {
            "updates": {"sv": 180, "bot": 4},
            "expected_util": 0.82,
            "target_band_candidate_count": 1,
            "safe_cleanup_candidate_found": True,
            "executor_backed": True,
            "preview_pass": True,
            "candidate_id": "candidate-safe-combined",
        }
        returned_proof, updates, expected, eligible = (
            inputs_page.render_inputs_pre_render_safe_combined_contract_promotion_coordinator(
                pre_render_dg_bundle={"design_brain_safe_combined_cleanup_proof": proof},
                pre_render_contract=contract,
            )
        )
        if not eligible:
            failures.append("eligible_case_not_promoted")
        if returned_proof != proof:
            failures.append(f"proof_mismatch:{returned_proof}")
        if updates != {"sv": 180, "bot": 4}:
            failures.append(f"updates_mismatch:{updates}")
        if expected != 0.82:
            failures.append(f"expected_mismatch:{expected}")
        for key, value in {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": {"sv": 180, "bot": 4},
            "preview_pass": True,
            "blocking_reason": None,
            "source_candidate_id": "candidate-safe-combined",
            "candidate_id": "candidate-safe-combined",
            "selected_family_id": "COMBINED_OVERDESIGN",
            "published_family_id": "COMBINED_OVERDESIGN",
            "cta_family_id": "COMBINED_OVERDESIGN",
            "candidate_family_id": "COMBINED_OVERDESIGN",
            "card_family_id": "COMBINED_OVERDESIGN",
            "apply_payload_family_id": "COMBINED_OVERDESIGN",
            "expected_util": 0.82,
        }.items():
            if contract.get(key) != value:
                failures.append(f"contract_{key}_mismatch:{contract}")

        below_contract = {
            "selected_family_id": "COMBINED_OVERDESIGN",
            "family": "combined",
        }
        _, _, below_expected, below_eligible = (
            inputs_page.render_inputs_pre_render_safe_combined_contract_promotion_coordinator(
                pre_render_dg_bundle={
                    "design_brain_safe_combined_cleanup_proof": {
                        "updates": {"sv": 180, "bot": 4},
                        "expected_util": 0.40,
                        "target_band_candidate_count": 1,
                        "safe_cleanup_candidate_found": True,
                        "executor_backed": True,
                        "preview_pass": True,
                    }
                },
                pre_render_contract=below_contract,
            )
        )
        if below_expected != 0.40:
            failures.append(f"below_expected_mismatch:{below_expected}")
        if below_eligible:
            failures.append("below_threshold_case_promoted")
        if below_contract.get("enabled"):
            failures.append(f"below_threshold_contract_mutated:{below_contract}")

        inputs_page._updates_match_state = lambda state, updates: True
        matched_contract = {
            "selected_family_id": "COMBINED_OVERDESIGN",
            "family": "combined",
        }
        _, _, _, matched_eligible = (
            inputs_page.render_inputs_pre_render_safe_combined_contract_promotion_coordinator(
                pre_render_dg_bundle={"design_brain_safe_combined_cleanup_proof": proof},
                pre_render_contract=matched_contract,
            )
        )
        if matched_eligible:
            failures.append("state_matching_updates_promoted")
    finally:
        _restore()

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_pre_render_safe_combined_contract_promotion_coordinator" not in source:
        failures.append("safe_combined_contract_promotion_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_pre_render_combined_promotion_contract_allows_combined =",
        "_pre_render_safe_combined_shear_demand =",
        "_pre_render_safe_combined_candidate_id =",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_pre_render_safe_combined_contract_promotion_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre-Render Safe Combined Contract Promotion Coordinator Verifier",
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
