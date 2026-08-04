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


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalise(val) for key, val in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, float):
        return round(value, 12)
    return value


def main() -> int:
    import streamlit as st

    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    explicit_goals = [
        *sorted(str(goal) for goal in legacy_inputs_page.DESIGN_OPTIMISATION_GOAL_LABELS),
        "invalid_goal",
        "",
        None,
    ]
    cases: list[dict[str, Any]] = []
    failures: list[str] = []
    for goal in explicit_goals:
        expected = _normalise(legacy_inputs_page._design_mode_config(goal))
        actual = _normalise(bridge._design_mode_config(goal))
        passed = expected == actual
        case = {
            "case": f"explicit:{goal!r}",
            "passed": passed,
            "expected": expected,
            "actual": actual,
        }
        cases.append(case)
        if not passed:
            failures.append(case["case"])

    previous_goal = st.session_state.get("design_optimisation_goal", None)
    had_previous_goal = "design_optimisation_goal" in st.session_state
    try:
        for session_goal in ("balanced", "shallower_beam", "less_longitudinal_reinforcement", "less_shear_reinforcement", "invalid_goal"):
            st.session_state["design_optimisation_goal"] = session_goal
            expected = _normalise(legacy_inputs_page._design_mode_config())
            actual = _normalise(bridge._design_mode_config())
            passed = expected == actual
            case = {
                "case": f"session:{session_goal}",
                "passed": passed,
                "expected": expected,
                "actual": actual,
            }
            cases.append(case)
            if not passed:
                failures.append(case["case"])
    finally:
        if had_previous_goal:
            st.session_state["design_optimisation_goal"] = previous_goal
        else:
            st.session_state.pop("design_optimisation_goal", None)

    payload = {
        "audit": "inputs_page_design_mode_config_bridge_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_design_mode_config_bridge_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_mode_config_bridge_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Mode Config Bridge Parity",
                "",
                f"Status: `{payload['status']}`",
                f"Case count: `{payload['case_count']}`",
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
