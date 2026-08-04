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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_merge_stamping_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_merge_stamping_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    same_updates = {"s_lig": 150, "bottom_bar_dia": 16}
    same_evidence = {"source": "same_click"}
    same_statuses = {"bending": "PASS", "shear": "PASS"}
    same_overview = {"utils": {"bending": 0.91, "shear": 0.92}}
    exact_blockers = {"shear": {"reason": "link_spacing"}}
    base_evidence = {"existing": True}
    guidance_debug = {"existing_debug": True}

    result = inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_merge_stamping(
        presentation_same_updates=same_updates,
        presentation_same_util=0.92,
        presentation_same_evidence=same_evidence,
        presentation_same_statuses=same_statuses,
        presentation_same_overview=same_overview,
        presentation_same_exact_blockers=exact_blockers,
        presentation_bending_evidence=dict(base_evidence),
        guidance_debug=dict(guidance_debug),
    )
    cases.append({"name": "same_click_stamping_with_exact_blockers", "result": result})
    updates, title, family, subfamilies, candidate_id, evidence, debug = result
    if updates != same_updates:
        failures.append(f"updates_mismatch:{updates}")
    if title != "Shear and bending cleanup - one-click optimisation":
        failures.append(f"title_mismatch:{title}")
    if family != "combined" or subfamilies != ["shear", "bottom_reinforcement"]:
        failures.append(f"family_mismatch:{family}:{subfamilies}")
    expected_candidate_id = inputs_page._guidance_cleanup_candidate_id("combined", same_updates)
    if candidate_id != expected_candidate_id:
        failures.append(f"candidate_id_mismatch:{candidate_id}:{expected_candidate_id}")
    expected_evidence = {
        "existing": True,
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "family": "combined",
        "same_click_cleanup_merge": same_evidence,
        "selected_candidate_id": expected_candidate_id,
        "selected_candidate_updates": same_updates,
        "selected_candidate_util": 0.92,
        "best_safe_candidate_updates": same_updates,
        "best_safe_final_util": 0.92,
        "best_safe_candidate_applied": False,
        "no_second_cta_required": True,
        "merged_preview_statuses": same_statuses,
        "merged_preview_utils": same_overview["utils"],
        "exact_blockers_by_family": exact_blockers,
        "post_click_exact_blockers_by_family": exact_blockers,
        "cleanup_evidence_by_family": exact_blockers,
        "post_click_cleanup_evidence_by_family": exact_blockers,
        "outside_target_band_allowed": True,
        "outside_target_band_allowed_category": "combined_cleanup_exact_blocker_after_same_click_merge",
    }
    for key, value in expected_evidence.items():
        if evidence.get(key) != value:
            failures.append(f"evidence_{key}_mismatch:{evidence.get(key)}:{value}")
    if debug.get("existing_debug") is not True:
        failures.append(f"debug_existing_lost:{debug}")
    if debug.get("same_click_presentation_bending_folded_residual_shear") is not True:
        failures.append(f"debug_folded_flag_missing:{debug}")
    if debug.get("same_click_presentation_bending_folded_updates") != same_updates:
        failures.append(f"debug_folded_updates_mismatch:{debug}")

    result = inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_merge_stamping(
        presentation_same_updates={"s_lig": 175},
        presentation_same_util=0.9,
        presentation_same_evidence={},
        presentation_same_statuses={},
        presentation_same_overview={},
        presentation_same_exact_blockers={},
        presentation_bending_evidence={},
        guidance_debug={},
    )
    cases.append({"name": "same_click_stamping_without_exact_blockers", "result": result})
    evidence = result[5]
    blocker_keys = {
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "outside_target_band_allowed",
        "outside_target_band_allowed_category",
    }
    unexpected = sorted(key for key in blocker_keys if key in evidence)
    if unexpected:
        failures.append(f"unexpected_blocker_keys_without_exact_blockers:{unexpected}")

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_same_click_shear_merge_stamping_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Same-Click Shear Merge Stamping Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
