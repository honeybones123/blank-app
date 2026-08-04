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
        f"inputs_page_post_cleanup_invalid_render_shear_blocker_detailing_floor_setup_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_shear_blocker_detailing_floor_setup_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    floor_id_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_detailing_floor_setup(
        shear_blocker={
            "best_rejected_candidate_id": "shear_cleanup_floor_no_links_remaining",
            "safe_candidate_count": 0,
        },
        shear_blocker_util=0.4,
        best_safe_updates={"s_lig": 250},
        best_safe_already_applied=False,
        guidance_debug={"overview": {"utils": {"shear": 0.61}}},
        guidance_disp_state={"lig_d": 10, "lig_legs": 2, "s_lig": 300},
        dg_overview={"utils": {"shear": 0.72}},
    )
    true_floor_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_detailing_floor_setup(
        shear_blocker={"safe_candidate_count": 0},
        shear_blocker_util=0.4,
        best_safe_updates={},
        best_safe_already_applied=False,
        guidance_debug={"overview": {"utils": {"shear": 0.63}}},
        guidance_disp_state={"lig_d": 10, "lig_legs": 2, "s_lig": 300},
        dg_overview={"utils": {"shear": 0.72}},
    )
    cleared_floor_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_detailing_floor_setup(
        shear_blocker={"safe_candidate_count": 1, "executable_candidate_count": 0},
        shear_blocker_util=0.4,
        best_safe_updates={"s_lig": 250},
        best_safe_already_applied=False,
        guidance_debug={"overview": {"utils": {"shear": 0.63}}},
        guidance_disp_state={"lig_d": 10, "lig_legs": 2, "s_lig": 300},
        dg_overview={"utils": {"shear": 0.72}},
    )

    floor_id_blocker, floor_id_util, floor_id_applied, floor_id_floor = floor_id_result
    expect(
        "floor_id_path",
        floor_id_applied is True
        and floor_id_floor is True
        and floor_id_util == 0.61
        and floor_id_blocker["starting_util"] == 0.72
        and floor_id_blocker["current_util"] == 0.61
        and floor_id_blocker["failed_check_util"] == 0.61,
        f"floor_id_result={floor_id_result}",
    )
    true_floor_blocker, true_floor_util, true_floor_applied, true_floor = true_floor_result
    expect(
        "true_floor_path",
        true_floor_applied is False
        and true_floor is True
        and true_floor_util == 0.63
        and true_floor_blocker["current_util"] == 0.63
        and true_floor_blocker["failed_check_util"] == 0.63,
        f"true_floor_result={true_floor_result}",
    )
    cleared_floor_blocker, cleared_floor_util, cleared_floor_applied, cleared_floor = cleared_floor_result
    expect(
        "cleared_floor_path",
        cleared_floor_applied is False
        and cleared_floor is False
        and cleared_floor_util == 0.4
        and "current_util" not in cleared_floor_blocker
        and "failed_check_util" not in cleared_floor_blocker,
        f"cleared_floor_result={cleared_floor_result}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "floor_id_result": {
            "shear_blocker": floor_id_blocker,
            "shear_blocker_util": floor_id_util,
            "best_safe_already_applied": floor_id_applied,
            "shear_links_at_detailing_floor": floor_id_floor,
        },
        "true_floor_result": {
            "shear_blocker": true_floor_blocker,
            "shear_blocker_util": true_floor_util,
            "best_safe_already_applied": true_floor_applied,
            "shear_links_at_detailing_floor": true_floor,
        },
        "cleared_floor_result": {
            "shear_blocker": cleared_floor_blocker,
            "shear_blocker_util": cleared_floor_util,
            "best_safe_already_applied": cleared_floor_applied,
            "shear_links_at_detailing_floor": cleared_floor,
        },
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Shear Blocker Detailing Floor Setup Verifier",
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
