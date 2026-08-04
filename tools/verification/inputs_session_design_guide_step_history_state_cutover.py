from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import (
    build_inputs_design_guide_step_history_debug_summary,
    build_inputs_design_guide_step_history_reset_plan,
)


def _old_summary(history, first):
    hist = list(history or [])
    ever = first is not None
    steps_to = int(first) if first is not None else None
    latest = hist[-1] if hist else {}
    tail = hist[-10:] if len(hist) > 10 else list(hist)
    compact = []
    for entry in hist:
        if not isinstance(entry, dict):
            continue
        compact.append(
            {
                "step": entry.get("step_index"),
                "pre": entry.get("pre_apply_worst_util"),
                "post": entry.get("post_apply_worst_util"),
                "entered_band": bool(entry.get("entered_target_band_on_this_step")),
                "title": entry.get("recommendation_title"),
            }
        )
    return {
        "design_guide_step_history_count": len(hist),
        "design_guide_step_history_tail": tail,
        "first_target_band_step": first,
        "current_step_index": len(hist),
        "ever_entered_target_band": ever,
        "steps_to_first_target_band": steps_to,
        "latest_step_pre_util": (latest or {}).get("pre_apply_worst_util"),
        "latest_step_post_util": (latest or {}).get("post_apply_worst_util"),
        "latest_step_title": (latest or {}).get("recommendation_title"),
        "latest_step_used_resolved_payload": bool((latest or {}).get("used_resolved_payload")),
        "converged_in_one_click": bool(steps_to == 1),
        "design_guide_step_history_compact": compact,
    }


def main() -> int:
    inputs = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    builders = (ROOT / "inputs_page_modules" / "session" / "builders.py").read_text(encoding="utf-8")
    init_text = (ROOT / "inputs_page_modules" / "session" / "__init__.py").read_text(encoding="utf-8")
    failures = []
    scenarios = []

    for name, current, previous, expected_reset in (
        ("first_anchor", ("goal", "beam", (1,)), None, False),
        ("same_anchor", ("goal", "beam", (1,)), ("goal", "beam", (1,)), False),
        ("changed_anchor", ("goal", "beam", (2,)), ("goal", "beam", (1,)), True),
    ):
        plan = build_inputs_design_guide_step_history_reset_plan(
            current_anchor=current,
            previous_anchor=previous,
        )
        scenarios.append(
            {
                "name": name,
                "match": plan.current_anchor == current and plan.reset_history is expected_reset and bool(plan.display_hash),
            }
        )

    history = [
        {
            "step_index": i,
            "pre_apply_worst_util": 1.0 - i * 0.01,
            "post_apply_worst_util": 0.9 - i * 0.01,
            "entered_target_band_on_this_step": i == 2,
            "recommendation_title": f"Step {i}",
            "used_resolved_payload": i % 2 == 0,
        }
        for i in range(1, 13)
    ]
    for name, rows, first in (("empty", [], None), ("history", history, 2), ("mixed_rows", ["bad", history[0]], 1)):
        summary = build_inputs_design_guide_step_history_debug_summary(
            history=rows,
            first_target_band_step=first,
        )
        scenarios.append(
            {
                "name": name,
                "match": summary.payload == _old_summary(rows, first) and bool(summary.display_hash),
            }
        )
    if not all(row["match"] for row in scenarios):
        failures.append("step-history scenario parity failed")

    reset_start = inputs.index("def _maybe_reset_design_guide_step_history")
    next_start = inputs.index("def _worst_util_in_efficiency_target_band", reset_start)
    summary_start = inputs.index("def _design_guide_step_history_debug_summary")
    render_start = inputs.index("def _render_design_guide_debug_sidebar", summary_start)
    reset_body = inputs[reset_start:next_start]
    summary_body = inputs[summary_start:render_start]
    if "build_inputs_design_guide_step_history_reset_plan(" not in reset_body:
        failures.append("history reset helper does not delegate")
    if "build_inputs_design_guide_step_history_debug_summary(" not in summary_body:
        failures.append("history debug summary does not delegate")
    for snippet in ("prev is not None and prev != anchor", "for e in hist:", '"converged_in_one_click": bool(steps_to == 1)'):
        if snippet in reset_body or snippet in summary_body:
            failures.append(f"old page-owned step-history policy remains: {snippet}")
    if "st.session_state" in builders or "import streamlit" in builders or "import inputs_page" in builders:
        failures.append("session builder imports or reads forbidden page/UI state")
    for name in (
        "build_inputs_design_guide_step_history_reset_plan",
        "build_inputs_design_guide_step_history_debug_summary",
    ):
        if name not in init_text:
            failures.append(f"session builder is not exported: {name}")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_SESSION_DESIGN_GUIDE_STEP_HISTORY_STATE_LOCKED" if not failures else "FAIL"
    result = {
        "audit": "inputs_session_design_guide_step_history_state_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "session_read_write_ownership_moved": False,
        "scenarios": scenarios,
        "failures": failures,
    }
    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_session_design_guide_step_history_state_{timestamp}.json"
    report_path = audit_dir / f"inputs_session_design_guide_step_history_state_{timestamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Session Design Guide Step History State",
                "",
                f"Decision: `{decision}`",
                "",
                f"Scenarios checked: `{len(scenarios)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The session module owns anchor-change reset policy and non-authoritative history summary shaping.",
                "`inputs_page.py` still owns anchors, session reads/writes, engineering overview collection, and Apply orchestration.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
