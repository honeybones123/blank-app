from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_cleanup_intent_contract_gate_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_intent_contract_gate_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "st": inputs_page.st,
        "_build_final_design_guide_post_cleanup_render_audit_intent_contract_result": (
            inputs_page._build_final_design_guide_post_cleanup_render_audit_intent_contract_result
        ),
        "_visible_strength_low_families": inputs_page._visible_strength_low_families,
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
    }
    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def build_intent_proof(*, guidance_debug):
        calls.append({"event": "build_intent_proof", "guidance_debug": dict(guidance_debug or {})})
        return {
            "proof_hash": "intent-proof-abc",
            "result": {
                "intent_contract": {
                    "family": "shear",
                    "updates": {"link_spacing": 175},
                    "expected_util": -0.1,
                },
                "intent_row": {"title": "Shear cleanup row", "check_key": "shear"},
            },
        }

    try:
        inputs_page.st = SimpleNamespace(
            session_state={
                inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY: {
                    "session_marker": "from_debug_bundle",
                }
            }
        )
        inputs_page._build_final_design_guide_post_cleanup_render_audit_intent_contract_result = (
            build_intent_proof
        )
        inputs_page._visible_strength_low_families = lambda overview: {"serviceability"}
        inputs_page._overview_active_failure_keys = lambda overview: {"bending", "torsion"}

        guidance_debug = {
            "runtime_marker": "from_guidance_debug",
            "overview": {"worst_util": 0.65},
            "candidate_search_evidence": {
                "selected_candidate_util": -0.1,
                "target_band_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
            },
            "low_util_families": ["bending"],
        }
        result = inputs_page.render_design_guide_post_cleanup_intent_contract_gate_setup(
            guidance_debug=guidance_debug,
            dg_overview={"fallback": True},
            post_cleanup_render_audit={
                "post_click_families_below_final_threshold": ["shear"],
            },
            post_cleanup_low_families=[],
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    (
        intent_contract,
        intent_row,
        intent_family,
        intent_low_families,
        current_strength_fail_for_intent,
        intent_target_contract_blocked,
    ) = result
    expect(
        "proof_input_merge",
        calls
        and calls[0]["guidance_debug"]["session_marker"] == "from_debug_bundle"
        and calls[0]["guidance_debug"]["runtime_marker"] == "from_guidance_debug",
        f"calls={calls}",
    )
    expect(
        "returned_gate_values",
        intent_contract["family"] == "shear"
        and intent_contract["updates"] == {"link_spacing": 175}
        and intent_row["check_key"] == "shear"
        and intent_family == "shear"
        and intent_low_families == {"bending", "shear"}
        and current_strength_fail_for_intent == {"bending"}
        and intent_target_contract_blocked is True,
        f"result={result}",
    )
    expect(
        "debug_stamps",
        guidance_debug["post_cleanup_render_audit_intent_contract_cutover_applied"] is True
        and guidance_debug["post_cleanup_render_audit_intent_contract_proof_hash"] == "intent-proof-abc"
        and guidance_debug["post_cleanup_intent_preference_probe"]
        == {
            "contract_found": True,
            "row_found": True,
            "family": "shear",
            "low_families": ["bending", "shear"],
            "current_strength_fail": ["bending"],
        }
        and guidance_debug["post_cleanup_intent_preference_blocked_by_target_contract"] is True
        and guidance_debug["post_cleanup_intent_preference_blocked_util"] == -0.1
        and guidance_debug["post_cleanup_intent_preference_blocked_target_count"] == 0,
        f"guidance_debug={guidance_debug}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "calls": calls,
        "result": {
            "intent_contract": intent_contract,
            "intent_row": intent_row,
            "intent_family": intent_family,
            "intent_low_families": sorted(intent_low_families),
            "current_strength_fail_for_intent": sorted(current_strength_fail_for_intent),
            "intent_target_contract_blocked": intent_target_contract_blocked,
        },
        "guidance_debug": guidance_debug,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Intent Contract Gate Setup Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": payload["verdict"],
                "json": str(json_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
