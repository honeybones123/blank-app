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
    json_path = ARTIFACT_DIR / f"inputs_page_final_recommendation_overlap_debug_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_final_recommendation_overlap_debug_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
        "_guidance_item_family_tag": inputs_page._guidance_item_family_tag,
        "_guidance_item_family": inputs_page._guidance_item_family,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for original_name, original_value in originals.items():
            setattr(inputs_page, original_name, original_value)
        inputs_page.st.session_state.pop("_design_guide_overlap_suppression_debug", None)
        inputs_page.st.session_state.pop("_design_guide_family_suppression_debug", None)

    def _run_case(
        name: str,
        *,
        recommendation_needed: bool,
        guidance_items: list[dict],
        guidance_debug: dict | None = None,
        current_recommendation_result: dict | None = None,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        state = {"D": 500}
        redundancy_meta = {
            "suppressed": True,
            "reason": "unit_overlap",
            "suppressed_titles": ["duplicate secondary"],
            "subset_suppressed": True,
            "subset_suppressed_titles": ["subset card"],
            "primary_update_keys": ["D"],
            "secondary_update_keys": ["B"],
        }
        family_suppression_meta = {
            "primary_family": "bending",
            "secondary_families": ["shear"],
            "applied": True,
            "reason": "unit_family_consolidation",
            "promoted_title": "Primary card",
            "suppressed_titles": ["Suppressed shear"],
            "kept_secondary_titles": ["Kept shear"],
            "item_debug": [{"family": "shear"}],
        }

        def _recommend(items, state_arg, *, branch, request_kind):
            events.append("recommend")
            return {"branch": branch, "request_kind": request_kind, "count": len(items)}

        def _family_tag(item, state_arg):
            events.append(f"family_tag:{item.get('id') or item.get('family')}")
            return f"tag:{item.get('family', 'unknown')}"

        def _family(item):
            events.append(f"family:{item.get('id') or item.get('family')}")
            return str(item.get("family") or "")

        try:
            inputs_page._recommendation_result_for_primary_guidance_card = _recommend
            inputs_page._guidance_item_family_tag = _family_tag
            inputs_page._guidance_item_family = _family

            out_debug, recommendation = inputs_page.render_design_guide_final_recommendation_and_overlap_debug(
                recommendation_needed=recommendation_needed,
                guidance_items=guidance_items,
                guidance_disp_state=state,
                guidance_debug=dict(guidance_debug or {}),
                current_recommendation_result=current_recommendation_result,
                branch_for_recommendation="unit_branch",
                redundancy_meta=redundancy_meta,
                family_suppression_meta=family_suppression_meta,
                stage=lambda label: stages.append(str(label)),
            )
            session_overlap = dict(inputs_page.st.session_state.get("_design_guide_overlap_suppression_debug") or {})
            session_family = dict(inputs_page.st.session_state.get("_design_guide_family_suppression_debug") or {})
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "debug": out_debug,
            "recommendation": recommendation,
            "session_overlap": session_overlap,
            "session_family": session_family,
        }
        cases.append(case)
        return case

    recomputed = _run_case(
        "recommendation_needed_two_items",
        recommendation_needed=True,
        guidance_items=[
            {"id": "primary", "family": "bending", "title_main": "Primary card"},
            {"id": "secondary", "family": "shear", "title_main": "Secondary card", "action_type": "apply"},
        ],
    )
    if recomputed["events"] != ["recommend", "family_tag:primary", "family:secondary", "family_tag:secondary"]:
        failures.append(f"recomputed_events_mismatch:{recomputed['events']}")
    if recomputed["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"recomputed_stage_mismatch:{recomputed['stages']}")
    if recomputed["recommendation"] != {"branch": "unit_branch", "request_kind": "design_guide", "count": 2}:
        failures.append(f"recomputed_recommendation_mismatch:{recomputed['recommendation']}")
    expected_debug = {
        "design_guide_overlap_suppressed": True,
        "design_guide_overlap_suppression_reason": "unit_overlap",
        "design_guide_family_suppression_applied": True,
        "design_guide_family_suppression_reason": "unit_family_consolidation",
        "primary_card_family_tag": "tag:bending",
        "secondary_card_family_tag": "tag:shear",
        "secondary_card_materially_distinct": True,
        "surfaced_secondary_card_action_type": "apply",
        "surfaced_secondary_card_title": "Secondary card",
        "surfaced_secondary_card_family": "tag:shear",
        "surfaced_secondary_shear_card": True,
        "surfaced_secondary_card_source": "design_guide_visible_index_1_post_family_consolidation",
    }
    for key, expected in expected_debug.items():
        if recomputed["debug"].get(key) != expected:
            failures.append(f"recomputed_{key}_mismatch:{recomputed['debug'].get(key)}")
    if recomputed["session_overlap"].get("reason") != "unit_overlap":
        failures.append(f"recomputed_session_overlap_mismatch:{recomputed['session_overlap']}")
    if recomputed["session_family"].get("primary_family") != "bending":
        failures.append(f"recomputed_session_family_mismatch:{recomputed['session_family']}")

    preserved = _run_case(
        "recommendation_preserved_no_items",
        recommendation_needed=False,
        guidance_items=[],
        guidance_debug={"guidance_dedupe_meta": {"primary_card_family_tag": "fallback-primary", "secondary_card_family_tag": "fallback-secondary"}},
        current_recommendation_result={"existing": True},
    )
    if preserved["events"]:
        failures.append(f"preserved_events_mismatch:{preserved['events']}")
    if preserved["stages"]:
        failures.append(f"preserved_stage_mismatch:{preserved['stages']}")
    if preserved["recommendation"] != {"existing": True}:
        failures.append(f"preserved_recommendation_mismatch:{preserved['recommendation']}")
    if preserved["debug"].get("primary_card_family_tag") != "fallback-primary":
        failures.append(f"preserved_primary_tag_mismatch:{preserved['debug'].get('primary_card_family_tag')}")
    if preserved["debug"].get("secondary_card_family_tag") != "fallback-secondary":
        failures.append(f"preserved_secondary_tag_mismatch:{preserved['debug'].get('secondary_card_family_tag')}")
    if preserved["debug"].get("secondary_card_materially_distinct") is not False:
        failures.append(f"preserved_secondary_distinct_mismatch:{preserved['debug'].get('secondary_card_materially_distinct')}")
    if preserved["debug"].get("surfaced_secondary_card_source") is not None:
        failures.append(f"preserved_secondary_source_mismatch:{preserved['debug'].get('surfaced_secondary_card_source')}")

    payload = {
        "verifier": "inputs_page_final_recommendation_overlap_debug_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Recommendation Overlap Debug Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` events: `{case['events']}`, stages: `{case['stages']}`"
                    for case in cases
                ),
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
