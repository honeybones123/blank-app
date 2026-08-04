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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_terminal_bending_followup_gate_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_terminal_bending_followup_gate_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_collect = inputs_page._collect_design_overview
    original_snapshot = inputs_page._guidance_state_snapshot
    original_context = inputs_page._build_design_actions_context

    failures: list[str] = []
    cases: list[dict] = []
    calls: list[dict] = []

    def run_case(
        name: str,
        *,
        expected_allowed: bool,
        expected_collect_calls: int,
        overview: dict,
        family: str = "bending",
        updates: dict | None = None,
        expected_util: float | None = 0.70,
    ) -> tuple[dict, dict, float | None, bool]:
        calls.clear()

        def fake_collect(state, *, context):
            calls.append({"state": dict(state), "context": dict(context or {})})
            return dict(overview)

        inputs_page._collect_design_overview = fake_collect
        result = inputs_page.render_design_guide_presentation_terminal_bending_followup_gate_setup(
            presentation_bending_family=family,
            presentation_bending_updates=dict(updates or {}),
            presentation_bending_expected_for_contract=expected_util,
            guidance_disp_state={"D": 500, "bottom_bar_dia": 20},
        )
        cases.append({"name": name, "result": result, "collect_calls": len(calls)})
        if result[3] is not expected_allowed:
            failures.append(f"{name}:expected_allowed={expected_allowed}:result={result}")
        if len(calls) != expected_collect_calls:
            failures.append(f"{name}:expected_collect_calls={expected_collect_calls}:actual={len(calls)}")
        return result

    try:
        inputs_page._guidance_state_snapshot = lambda state: dict(state or {})
        inputs_page._build_design_actions_context = lambda state: {"ctx": True}

        result = run_case(
            "positive_gate_builds_terminal_state_and_allows_followup",
            expected_allowed=True,
            expected_collect_calls=1,
            overview={"utils": {"bending": 0.70}},
            updates={"bottom_bar_dia": 16},
            expected_util=0.70,
        )
        terminal_state = result[0]
        if terminal_state.get("D") != 500 or terminal_state.get("bottom_bar_dia") != 16:
            failures.append(f"positive_terminal_state_mismatch:{terminal_state}")
        if result[1] != {"utils": {"bending": 0.70}} or result[2] != 0.70:
            failures.append(f"positive_overview_or_util_mismatch:{result}")

        run_case(
            "non_bending_family_blocks_without_collection",
            expected_allowed=False,
            expected_collect_calls=0,
            overview={"utils": {"bending": 0.70}},
            family="combined",
            updates={"bottom_bar_dia": 16},
            expected_util=0.70,
        )
        run_case(
            "empty_updates_block_without_collection",
            expected_allowed=False,
            expected_collect_calls=0,
            overview={"utils": {"bending": 0.70}},
            updates={},
            expected_util=0.70,
        )
        run_case(
            "missing_expected_util_blocks_without_collection",
            expected_allowed=False,
            expected_collect_calls=0,
            overview={"utils": {"bending": 0.70}},
            updates={"bottom_bar_dia": 16},
            expected_util=None,
        )
        run_case(
            "accepted_expected_util_blocks_without_collection",
            expected_allowed=False,
            expected_collect_calls=0,
            overview={"utils": {"bending": 0.70}},
            updates={"bottom_bar_dia": 16},
            expected_util=0.95,
        )
        run_case(
            "terminal_bending_util_above_threshold_blocks_followup",
            expected_allowed=False,
            expected_collect_calls=1,
            overview={"utils": {"bending": 0.95}},
            updates={"bottom_bar_dia": 16},
            expected_util=0.70,
        )
        run_case(
            "missing_terminal_bending_util_blocks_followup",
            expected_allowed=False,
            expected_collect_calls=1,
            overview={"utils": {}},
            updates={"bottom_bar_dia": 16},
            expected_util=0.70,
        )
    finally:
        inputs_page._collect_design_overview = original_collect
        inputs_page._guidance_state_snapshot = original_snapshot
        inputs_page._build_design_actions_context = original_context

    payload_out = {
        "verifier": "inputs_page_presentation_terminal_bending_followup_gate_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Terminal Bending Followup Gate Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['result'][3]}`" for case in cases),
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
