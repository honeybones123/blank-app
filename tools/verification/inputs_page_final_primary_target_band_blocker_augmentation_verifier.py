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
    json_path = ARTIFACT_DIR / f"inputs_page_final_primary_target_band_blocker_augmentation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_final_primary_target_band_blocker_augmentation_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_resolved_efficiency_target_band": inputs_page._resolved_efficiency_target_band,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_guide_family_summary_util": inputs_page._design_guide_family_summary_util,
        "_normalise_design_guide_candidate_id": inputs_page._normalise_design_guide_candidate_id,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install_stubs(target_low: float = 0.85, target_high: float = 0.95) -> None:
        inputs_page._resolved_efficiency_target_band = lambda mode_config, *, goal=None: (
            target_low,
            target_high,
            0.90,
        )
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "balanced"
        inputs_page._design_guide_family_summary_util = (
            lambda overview, family: dict(overview.get("utils") or {}).get(family)
        )
        inputs_page._normalise_design_guide_candidate_id = (
            lambda *, family, updates: f"{family}:{','.join(sorted(dict(updates or {}).keys()))}"
        )

    def _run_case(
        name: str,
        *,
        enabled: bool,
        contract: dict,
        item: dict | None,
        state: dict,
        evidence: dict,
        debug: dict,
        overview: dict,
    ) -> dict[str, Any]:
        try:
            _install_stubs()
            result = inputs_page.render_design_guide_final_primary_target_band_blocker_augmentation(
                final_primary_contract_enabled=enabled,
                final_primary_contract_for_bundle=dict(contract),
                displayed_primary_item=None if item is None else dict(item),
                guidance_disp_state=dict(state),
                engine_candidate_search_evidence=dict(evidence),
                guidance_debug=debug,
                overview=dict(overview),
            )
        finally:
            _restore()
        case = {"name": name, "result": result}
        cases.append(case)
        return case

    direct = _run_case(
        "direct_bending_augmentation",
        enabled=True,
        contract={
            "family": "bending",
            "expected_util": 0.98,
            "updates": {"D": 600},
            "candidate_id": "bend-1",
        },
        item={"title": "primary"},
        state={"D": 500},
        evidence={"attempted_candidate_count": 7, "safe_candidate_count": 3},
        debug={},
        overview={"utils": {"bending": 0.82}},
    )
    direct_blocker = dict(direct["result"].get("exact_blockers_by_family", {}).get("bending") or {})
    if direct_blocker.get("family") != "bending":
        failures.append(f"direct_family_missing:{direct['result']}")
    if direct_blocker.get("best_safe_candidate_id") != "bend-1":
        failures.append(f"direct_candidate_id_mismatch:{direct_blocker}")
    if direct_blocker.get("attempted_candidate_count") != 7:
        failures.append(f"direct_attempted_count_mismatch:{direct_blocker}")
    if direct_blocker.get("safe_candidate_count") != 3:
        failures.append(f"direct_safe_count_mismatch:{direct_blocker}")
    if direct["result"].get("post_click_cleanup_evidence_by_family") != direct["result"].get("exact_blockers_by_family"):
        failures.append(f"direct_maps_not_mirrored:{direct['result']}")

    combined = _run_case(
        "combined_preview_selects_highest_family",
        enabled=True,
        contract={"family": "combined", "updates": {"D": 550}},
        item={
            "family_status_preview": {
                "bending": {"before_util": 0.80, "after_util": 0.97},
                "shear": {"before_util": 0.79, "after_util": 0.99},
            }
        },
        state={"D": 500},
        evidence={"preview_count": 4, "safe_executor_backed_candidates_count": 2},
        debug={},
        overview={"utils": {"bending": 0.80, "shear": 0.79}},
    )
    combined_blockers = dict(combined["result"].get("exact_blockers_by_family") or {})
    if sorted(combined_blockers.keys()) != ["shear"]:
        failures.append(f"combined_family_selection_mismatch:{combined_blockers}")
    if combined_blockers.get("shear", {}).get("best_safe_final_util") != 0.99:
        failures.append(f"combined_util_mismatch:{combined_blockers}")

    shear_floor = _run_case(
        "shear_link_floor_reason",
        enabled=True,
        contract={"family": "shear", "expected_util": 0.98, "updates": {"lig_d": 0, "lig_legs": 0}},
        item={"title": "primary"},
        state={"lig_d": 0, "lig_legs": 0},
        evidence={},
        debug={},
        overview={"utils": {"shear": 0.81}},
    )
    shear_reason = str(
        shear_floor["result"].get("exact_blockers_by_family", {}).get("shear", {}).get("reason") or ""
    )
    if "shear-link floor" not in shear_reason:
        failures.append(f"shear_floor_reason_missing:{shear_reason}")

    existing = _run_case(
        "existing_blocker_preserved",
        enabled=True,
        contract={"family": "bending", "expected_util": 0.98, "updates": {"D": 600}},
        item={"title": "primary"},
        state={"D": 500},
        evidence={},
        debug={"exact_blockers_by_family": {"bending": {"family": "bending", "source": "existing"}}},
        overview={"utils": {"bending": 0.82}},
    )
    if existing["result"].get("exact_blockers_by_family", {}).get("bending", {}).get("source") != "existing":
        failures.append(f"existing_blocker_changed:{existing['result']}")
    if "post_click_exact_blockers_by_family" in existing["result"]:
        failures.append(f"existing_unexpected_mirror_write:{existing['result']}")

    disabled = _run_case(
        "disabled_noop",
        enabled=False,
        contract={"family": "bending", "expected_util": 0.98},
        item={"title": "primary"},
        state={},
        evidence={},
        debug={"keep": True},
        overview={"utils": {"bending": 0.82}},
    )
    if disabled["result"] != {"keep": True}:
        failures.append(f"disabled_changed:{disabled['result']}")

    payload = {
        "verifier": "inputs_page_final_primary_target_band_blocker_augmentation_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Primary Target Band Blocker Augmentation Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` exact families: `{sorted(dict(case['result'].get('exact_blockers_by_family') or {}).keys())}`"
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
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
