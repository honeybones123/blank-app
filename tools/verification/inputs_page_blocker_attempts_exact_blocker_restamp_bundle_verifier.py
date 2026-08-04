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
    json_path = ARTIFACT_DIR / f"inputs_page_blocker_attempts_exact_blocker_restamp_bundle_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_blocker_attempts_exact_blocker_restamp_bundle_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_blocker_attempts_table": inputs_page._design_guide_blocker_attempts_table,
        "_complete_exact_blocker_map_from_attempts": inputs_page._complete_exact_blocker_map_from_attempts,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    try:
        complete_events: list[dict[str, Any]] = []

        def _attempts_table(item):
            return {"bending": {"from_item": True, "attempted_util": 0.96}}

        def _complete(source, attempts):
            complete_events.append({"source": dict(source or {}), "attempts": dict(attempts or {})})
            out = dict(source or {})
            for family, attempt in dict(attempts or {}).items():
                out.setdefault(
                    family,
                    {
                        "family": family,
                        "source": "completed_from_attempt",
                        "current_util": dict(attempt or {}).get("attempted_util", 0.0),
                        "failed_check_util": dict(attempt or {}).get("attempted_util", 0.0),
                    },
                )
            return out

        inputs_page._design_guide_blocker_attempts_table = _attempts_table
        inputs_page._complete_exact_blocker_map_from_attempts = _complete

        displayed_evidence = {
            "exact_blockers_by_family": {
                "shear": {
                    "family": "shear",
                    "current_util": 0.75,
                    "failed_check_util": 0.74,
                }
            }
        }
        guidance_debug = {
            "blocker_attempts_by_family": {
                "shear": {"from_debug": True, "attempted_util": 0.88}
            }
        }
        engine_card_debug = {}
        engine_evidence = {}
        result = inputs_page.render_design_guide_blocker_attempts_and_exact_blocker_restamp_bundle(
            displayed_primary_item={"blocker_attempts_by_family": {"ignored": {"attempted_util": 0.5}}},
            displayed_primary_candidate_search_evidence=displayed_evidence,
            guidance_debug=guidance_debug,
            engine_card_debug=engine_card_debug,
            engine_candidate_search_evidence=engine_evidence,
            overview={"utils": {"bending": 0.82, "shear": 0.91}},
        )
    finally:
        _restore()

    (
        result_displayed_evidence,
        result_engine_evidence,
        result_guidance_debug,
        result_engine_card_debug,
        result_exact_blockers,
    ) = result
    cases.append(
        {
            "name": "merge_complete_restamp_and_mirror",
            "result_exact_blockers": result_exact_blockers,
            "events": complete_events,
            "displayed_evidence": result_displayed_evidence,
            "engine_evidence": result_engine_evidence,
            "guidance_debug": result_guidance_debug,
            "engine_card_debug": result_engine_card_debug,
        }
    )
    if sorted(result_exact_blockers.keys()) != ["bending", "shear"]:
        failures.append(f"exact_family_merge_mismatch:{result_exact_blockers}")
    if result_exact_blockers.get("shear", {}).get("current_util") != 0.91:
        failures.append(f"shear_current_util_not_restamped:{result_exact_blockers}")
    if result_exact_blockers.get("shear", {}).get("attempted_util") != 0.75:
        failures.append(f"shear_attempted_util_not_preserved:{result_exact_blockers}")
    if result_exact_blockers.get("bending", {}).get("current_util") != 0.82:
        failures.append(f"bending_current_util_not_restamped:{result_exact_blockers}")
    if result_displayed_evidence.get("post_click_cleanup_evidence_by_family") != result_exact_blockers:
        failures.append(f"displayed_maps_not_mirrored:{result_displayed_evidence}")
    if result_engine_evidence.get("exact_blockers_by_family") != result_exact_blockers:
        failures.append(f"engine_maps_not_mirrored:{result_engine_evidence}")
    if result_guidance_debug.get("blocker_attempts_by_family", {}).get("bending", {}).get("from_item") is not True:
        failures.append(f"attempts_not_written_to_debug:{result_guidance_debug}")
    if result_engine_card_debug != {}:
        failures.append(f"engine_card_debug_unexpected_change:{result_engine_card_debug}")

    try:
        inputs_page._design_guide_blocker_attempts_table = lambda item: {}
        inputs_page._complete_exact_blocker_map_from_attempts = lambda source, attempts: dict(source or {})
        empty_result = inputs_page.render_design_guide_blocker_attempts_and_exact_blocker_restamp_bundle(
            displayed_primary_item={},
            displayed_primary_candidate_search_evidence={},
            guidance_debug={},
            engine_card_debug={},
            engine_candidate_search_evidence={},
            overview={"utils": {}},
        )
    finally:
        _restore()
    cases.append({"name": "empty_noop", "result": empty_result})
    if empty_result != ({}, {}, {}, {}, {}):
        failures.append(f"empty_noop_mismatch:{empty_result}")

    payload = {
        "verifier": "inputs_page_blocker_attempts_exact_blocker_restamp_bundle_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Blocker Attempts Exact Blocker Restamp Bundle Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}`"
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
