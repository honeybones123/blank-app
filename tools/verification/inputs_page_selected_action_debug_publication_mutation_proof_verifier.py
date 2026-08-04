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
    json_path = ARTIFACT_DIR / (
        f"inputs_page_selected_action_debug_publication_mutation_proof_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_selected_action_debug_publication_mutation_proof_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_stamp = inputs_page._stamp_final_publication_post_resolver_mutation_proof
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def stamp_proof(*, item, final_visible_resolution, guidance_debug, publication_reason):
        events.append(
            {
                "event": "stamp_proof",
                "item": dict(item or {}),
                "final_visible_resolution": dict(final_visible_resolution or {}),
                "publication_reason": publication_reason,
                "debug_before": dict(guidance_debug or {}),
            }
        )
        guidance_debug["proof_called"] = True
        guidance_debug["proof_publication_reason"] = publication_reason

    def run_case(
        name: str,
        *,
        item: dict,
        contract: dict,
        resolution: dict,
        debug: dict,
    ) -> dict:
        nonlocal events
        events = []
        guidance_debug = dict(debug or {})
        inputs_page.render_design_guide_selected_action_debug_and_publication_mutation_proof(
            final_visible_item=dict(item or {}),
            final_visible_contract=dict(contract or {}),
            final_visible_resolution=dict(resolution or {}),
            guidance_debug=guidance_debug,
        )
        case = {
            "name": name,
            "debug": guidance_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._stamp_final_publication_post_resolver_mutation_proof = stamp_proof

        case = run_case(
            "enabled_contract_stamps_selected_action_and_reason",
            item={
                "title_main": "Increase depth",
                "title": "Fallback title",
                "action_type": "apply_resolved_candidate",
                "family": "bending",
                "check_key": "shear",
            },
            contract={"family": "contract_family"},
            resolution={"render_reason": "final-visible-reason", "state_fingerprint": "fp"},
            debug={"button_contract_enabled": True},
        )
        expect(
            "enabled_contract_stamps_selected_action_and_reason",
            case["debug"]["selected_title"] == "Increase depth"
            and case["debug"]["selected_action_type"] == "apply_resolved_candidate"
            and case["debug"]["selected_action_family"] == "bending"
            and case["debug"]["proof_called"] is True
            and case["debug"]["proof_publication_reason"] == "final-visible-reason"
            and case["events"][0]["item"]["title_main"] == "Increase depth"
            and case["events"][0]["final_visible_resolution"]["state_fingerprint"] == "fp",
            f"case={case}",
        )

        case = run_case(
            "enabled_contract_falls_back_to_check_key_and_contract_family",
            item={
                "title": "Title from title",
                "action_type": "direct",
                "check_key": "serviceability",
            },
            contract={"family": "contract_family"},
            resolution={},
            debug={"button_contract_enabled": True},
        )
        expect(
            "enabled_contract_falls_back_to_check_key_and_contract_family",
            case["debug"]["selected_title"] == "Title from title"
            and case["debug"]["selected_action_family"] == "serviceability"
            and case["debug"]["proof_publication_reason"] == "render_stage_final_visible_resolver",
            f"case={case}",
        )

        case = run_case(
            "enabled_contract_falls_back_to_contract_family",
            item={"title": "Title only", "action_type": "direct"},
            contract={"family": "contract_family"},
            resolution={},
            debug={"button_contract_enabled": True},
        )
        expect(
            "enabled_contract_falls_back_to_contract_family",
            case["debug"]["selected_action_family"] == "contract_family",
            f"case={case}",
        )

        case = run_case(
            "disabled_contract_skips_selected_action_but_stamps_proof",
            item={
                "title_main": "No selected stamp",
                "action_type": "apply_resolved_candidate",
                "family": "bending",
            },
            contract={"family": "bending"},
            resolution={"render_reason": "disabled-reason"},
            debug={"button_contract_enabled": False},
        )
        expect(
            "disabled_contract_skips_selected_action_but_stamps_proof",
            "selected_title" not in case["debug"]
            and "selected_action_type" not in case["debug"]
            and "selected_action_family" not in case["debug"]
            and case["debug"]["proof_called"] is True
            and case["debug"]["proof_publication_reason"] == "disabled-reason",
            f"case={case}",
        )
    finally:
        inputs_page._stamp_final_publication_post_resolver_mutation_proof = original_stamp

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Selected Action Debug Publication Mutation Proof Verifier",
                "",
                f"Status: {payload['status']}",
                "",
                "## Cases",
                "",
                *[
                    f"- {case['name']}: {len(case['events'])} events"
                    for case in cases
                ],
                "",
                "## Artifacts",
                "",
                f"- JSON: `{json_path.relative_to(ROOT)}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print("SELECTED_ACTION_DEBUG_PUBLICATION_MUTATION_PROOF_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("SELECTED_ACTION_DEBUG_PUBLICATION_MUTATION_PROOF_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
