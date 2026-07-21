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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_render_bending_exact_blocker_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_render_bending_exact_blocker_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
        "TARGET_BAND_EPS",
        "GUIDANCE_TARGET_UTIL_MAX",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    try:
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.75
        inputs_page.TARGET_BAND_EPS = 0.001
        inputs_page.GUIDANCE_TARGET_UTIL_MAX = 0.95

        evidence = {
            "current_util": 0.38,
            "starting_util": 0.39,
            "ast_min_governs": True,
            "candidate_search_exhaustive": "true",
            "safe_executor_backed_candidates_count": 4,
            "target_band_candidate_count": 0,
            "total_candidates_considered": 12,
            "width_reduction_as_min_relief_checked": True,
            "depth_reduction_as_min_relief_checked": True,
            "width_reduction_restarted_reinforcement_candidate_count": 2,
            "exact_stop_cleanup_proof_chain_complete": True,
            "every_valid_cleanup_path_exhausted_for_contract_defined_reasons": True,
        }
        bundle = {
            "design_brain_result": {
                "evidence": {
                    "candidate_search": {
                        "bending_cleanup_evidence": dict(evidence)
                    }
                }
            }
        }
        returned_evidence, blocker = inputs_page.render_inputs_pre_render_bending_exact_blocker_coordinator(
            pre_render_dg_bundle=bundle,
            pre_render_safe_combined_expected=0.40,
            pre_render_safe_combined_updates={"bot": 4},
        )
        if returned_evidence != evidence:
            failures.append(f"evidence_mismatch:{returned_evidence}")
        if blocker.get("family") != "bending":
            failures.append(f"family_mismatch:{blocker}")
        if blocker.get("failed_check_status") != "BLOCKED_BY_MINIMUM_BENDING_REINFORCEMENT":
            failures.append(f"ast_min_status_mismatch:{blocker}")
        if blocker.get("best_safe_final_util") != 0.40:
            failures.append(f"best_safe_final_util_mismatch:{blocker}")
        if blocker.get("best_safe_candidate_updates") != {"bot": 4}:
            failures.append(f"updates_mismatch:{blocker}")
        if blocker.get("safe_candidate_count") != 4:
            failures.append(f"safe_candidate_count_mismatch:{blocker}")
        if blocker.get("attempted_candidate_count") != 12:
            failures.append(f"attempted_candidate_count_mismatch:{blocker}")
        if "Ast-min" not in str(blocker.get("reason")):
            failures.append(f"ast_min_reason_missing:{blocker.get('reason')}")

        ductility_evidence = {
            "current_util": 0.52,
            "ductility_governs_cleanup": True,
            "exact_stop_cleanup_proof_chain_complete": True,
        }
        _, ductility_blocker = inputs_page.render_inputs_pre_render_bending_exact_blocker_coordinator(
            pre_render_dg_bundle={
                "design_brain_result": {
                    "evidence": {
                        "candidate_search": {
                            "bending_cleanup_evidence": dict(ductility_evidence)
                        }
                    }
                }
            },
            pre_render_safe_combined_expected=0.50,
            pre_render_safe_combined_updates={"bot": 3},
        )
        if "Ductility" not in str(ductility_blocker.get("reason")):
            failures.append(f"ductility_reason_missing:{ductility_blocker.get('reason')}")

        _, no_blocker = inputs_page.render_inputs_pre_render_bending_exact_blocker_coordinator(
            pre_render_dg_bundle=bundle,
            pre_render_safe_combined_expected=0.82,
            pre_render_safe_combined_updates={"bot": 4},
        )
        if no_blocker:
            failures.append(f"in_target_case_should_not_block:{no_blocker}")
    finally:
        _restore()

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_pre_render_bending_exact_blocker_coordinator" not in source:
        failures.append("bending_exact_blocker_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_pre_render_ast_min_governs =",
        "_pre_render_ductility_governs =",
        "_pre_render_failed_check_name =",
        "_pre_render_bending_exact_blocker = {}",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_pre_render_bending_exact_blocker_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre-Render Bending Exact Blocker Coordinator Verifier",
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
