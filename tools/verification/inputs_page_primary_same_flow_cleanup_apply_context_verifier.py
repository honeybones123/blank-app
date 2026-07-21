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


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_primary_same_flow_cleanup_apply_context_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_same_flow_cleanup_apply_context_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    fake_st = FakeStreamlit()
    original_st = inputs_page.st
    route_key = inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY
    binding_key = inputs_page.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY

    try:
        inputs_page.st = fake_st

        direct_route = {
            "apply_used_resolved_candidate_payload": True,
            "applied_updates": {"s_lig": 250},
            "resolved_candidate_label": "same cleanup pass",
        }
        fake_st.session_state.clear()
        fake_st.session_state[route_key] = dict(direct_route)
        direct_result = inputs_page.render_design_guide_primary_same_flow_cleanup_apply_context(
            primary_guidance_disp_state_for_render={"lig_d": 10, "lig_legs": 2},
        )

        fallback_route = {
            "apply_used_resolved_candidate_payload": False,
            "applied_updates": {},
            "resolved_candidate_label": "plain apply",
        }
        fake_st.session_state.clear()
        fake_st.session_state[route_key] = dict(fallback_route)
        fake_st.session_state[binding_key] = {
            "actual_changed_updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 300},
        }
        fallback_result = inputs_page.render_design_guide_primary_same_flow_cleanup_apply_context(
            primary_guidance_disp_state_for_render={"lig_d": 0, "lig_legs": 0},
        )

        fake_st.session_state.clear()
        fake_st.session_state[route_key] = {
            "apply_used_resolved_candidate_payload": True,
            "applied_updates": {"s_lig": 250},
            "resolved_candidate_label": "strength repair",
        }
        fake_st.session_state[binding_key] = {
            "applied_updates": {"s_lig": 250},
        }
        false_result = inputs_page.render_design_guide_primary_same_flow_cleanup_apply_context(
            primary_guidance_disp_state_for_render={"lig_d": 10, "lig_legs": 2},
        )
    finally:
        inputs_page.st = original_st

    expect(
        "direct_route_cleanup",
        direct_result == (direct_route, True),
        f"direct_result={direct_result}",
    )
    expect(
        "binding_audit_fallback",
        fallback_result == (fallback_route, True),
        f"fallback_result={fallback_result}",
    )
    expect(
        "false_path",
        false_result[0].get("resolved_candidate_label") == "strength repair"
        and false_result[1] is False,
        f"false_result={false_result}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "direct_result": direct_result,
        "fallback_result": fallback_result,
        "false_result": false_result,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Same Flow Cleanup Apply Context Verifier",
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
