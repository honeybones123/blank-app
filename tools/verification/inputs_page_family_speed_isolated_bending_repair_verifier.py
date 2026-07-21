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
    json_path = ARTIFACT_DIR / f"inputs_page_family_speed_isolated_bending_repair_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_family_speed_isolated_bending_repair_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_resolve = inputs_page._resolve_recommendation_updates
    original_enabled = inputs_page._design_guide_button_contract_enabled

    def resolve(item, *, state):
        calls.append({"event": "resolve", "item": dict(item or {}), "state": dict(state or {})})
        return {"resolved_update": 1}

    def contract_enabled(contract):
        calls.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool((contract or {}).get("enabled"))

    try:
        inputs_page._resolve_recommendation_updates = resolve
        inputs_page._design_guide_button_contract_enabled = contract_enabled

        positive_debug = {}
        positive_result, positive_debug = inputs_page.render_design_guide_family_speed_isolated_bending_repair(
            guidance_items=[
                {
                    "selected_family_id": "BENDING_FAIL_GOVERNS",
                    "published_family_id": "BENDING_FAIL_GOVERNS",
                    "cta_family_id": "BENDING_FAIL_GOVERNS",
                    "family_speed_isolation_active_repair": True,
                    "action_type": "apply_resolved_candidate",
                    "button_contract": {
                        "enabled": True,
                        "updates": {"n_bars": 4},
                    },
                }
            ],
            guidance_debug=positive_debug,
            guidance_disp_state={"case": "positive"},
        )

        fallback_debug = {
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "published_family_id": "BENDING_FAIL_GOVERNS",
            "cta_family_id": "BENDING_FAIL_GOVERNS",
            "family_speed_isolation_active_repair": True,
        }
        fallback_result, fallback_debug = inputs_page.render_design_guide_family_speed_isolated_bending_repair(
            guidance_items=[
                {
                    "action_type": "apply_resolved_candidate",
                    "button_contract": {"enabled": True},
                }
            ],
            guidance_debug=fallback_debug,
            guidance_disp_state={"case": "fallback"},
        )

        negative_debug = {}
        negative_result, negative_debug = inputs_page.render_design_guide_family_speed_isolated_bending_repair(
            guidance_items=[
                {
                    "selected_family_id": "SHEAR_FAIL_GOVERNS",
                    "published_family_id": "SHEAR_FAIL_GOVERNS",
                    "cta_family_id": "SHEAR_FAIL_GOVERNS",
                    "family_speed_isolation_active_repair": True,
                    "action_type": "apply_resolved_candidate",
                    "button_contract": {
                        "enabled": True,
                        "updates": {"s_lig": 150},
                    },
                }
            ],
            guidance_debug=negative_debug,
            guidance_disp_state={"case": "negative"},
        )
    finally:
        inputs_page._resolve_recommendation_updates = original_resolve
        inputs_page._design_guide_button_contract_enabled = original_enabled

    expected_reason = "BENDING_FAIL_GOVERNS active repair CTA already owns final publication"
    expect(
        "positive_debug_stamp",
        positive_result is True
        and positive_debug.get("post_publication_generic_proofs_skipped") is True
        and positive_debug.get("post_publication_generic_proofs_skipped_reason") == expected_reason,
        f"positive_result={positive_result} positive_debug={positive_debug}",
    )
    expect(
        "resolver_fallback_path",
        fallback_result is True
        and fallback_debug.get("post_publication_generic_proofs_skipped") is True
        and any(call["event"] == "resolve" and call["state"] == {"case": "fallback"} for call in calls),
        f"fallback_result={fallback_result} fallback_debug={fallback_debug} calls={calls}",
    )
    expect(
        "negative_no_debug_stamp",
        negative_result is False
        and "post_publication_generic_proofs_skipped" not in negative_debug
        and "post_publication_generic_proofs_skipped_reason" not in negative_debug,
        f"negative_result={negative_result} negative_debug={negative_debug}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "positive_result": positive_result,
        "positive_debug": positive_debug,
        "fallback_result": fallback_result,
        "fallback_debug": fallback_debug,
        "negative_result": negative_result,
        "negative_debug": negative_debug,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Family Speed Isolated Bending Repair Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
