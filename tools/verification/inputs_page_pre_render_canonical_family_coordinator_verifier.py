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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_render_canonical_family_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_render_canonical_family_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original = inputs_page._canonical_overdesign_family_from_updates
    failures: list[str] = []
    calls: list[dict[str, Any]] = []

    def _restore() -> None:
        inputs_page._canonical_overdesign_family_from_updates = original

    def canonical(family, updates):
        calls.append({"family": family, "updates": dict(updates)})
        if updates.get("shear") and updates.get("bottom"):
            return "combined_overdesign"
        return "not_overdesign"

    try:
        inputs_page._canonical_overdesign_family_from_updates = canonical
        contract = {
            "selected_family_id": "",
            "family": "combined",
            "updates": {"shear": 1, "bottom": 2},
        }
        bundle = {}
        result = inputs_page.render_inputs_pre_render_canonical_family_coordinator(
            pre_render_contract=contract,
            pre_render_dg_bundle=bundle,
        )
        expected_family = "COMBINED_OVERDESIGN"
        family_keys = [
            "family_id",
            "selected_family_id",
            "published_family_id",
            "cta_family_id",
            "candidate_family_id",
            "card_family_id",
            "apply_payload_family_id",
        ]
        if result != expected_family:
            failures.append(f"canonical_result_mismatch:{result}")
        for key in family_keys:
            if contract.get(key) != expected_family:
                failures.append(f"contract_family_key_mismatch:{key}:{contract.get(key)}")
        for key in [
            "selected_family_id",
            "selected_family",
            "published_family_id",
            "cta_family_id",
            "candidate_family_id",
            "card_family_id",
            "apply_payload_family_id",
        ]:
            if bundle.get(key) != expected_family:
                failures.append(f"bundle_family_key_mismatch:{key}:{bundle.get(key)}")
        if bundle.get("button_contract") != contract:
            failures.append("bundle_button_contract_not_updated")

        contract_noop = {"family": "bending", "updates": {"bottom": 2}}
        bundle_noop = {}
        result_noop = inputs_page.render_inputs_pre_render_canonical_family_coordinator(
            pre_render_contract=contract_noop,
            pre_render_dg_bundle=bundle_noop,
        )
        if result_noop != "NOT_OVERDESIGN":
            failures.append(f"noop_result_mismatch:{result_noop}")
        if "family_id" in contract_noop:
            failures.append(f"noop_contract_mutated:{contract_noop}")
        if bundle_noop:
            failures.append(f"noop_bundle_mutated:{bundle_noop}")
    finally:
        _restore()

    if calls != [
        {"family": "combined", "updates": {"shear": 1, "bottom": 2}},
        {"family": "bending", "updates": {"bottom": 2}},
    ]:
        failures.append(f"canonical_calls_mismatch:{calls}")
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_pre_render_canonical_family_coordinator" not in source:
        failures.append("pre_render_canonical_family_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    if "_pre_render_updates_for_family" in fresh_panel or "_pre_render_family_key" in fresh_panel:
        failures.append("fresh_panel_still_owns_canonical_family_loop")

    payload = {
        "verifier": "inputs_page_pre_render_canonical_family_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "canonical_calls": calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre-Render Canonical Family Coordinator Verifier",
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
