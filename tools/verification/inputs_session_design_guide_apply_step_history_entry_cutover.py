from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_apply_step_history_entry_plan


def _old_entry(**values):
    pre = dict(values["pre_overview"] or {})
    post = dict(values["post_overview"] or {})
    try:
        pre_wu = float(pre.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        pre_wu = 0.0
    try:
        post_wu = float(post.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        post_wu = 0.0
    step_index = values["existing_step_count"] + 1
    entered = bool(not values["pre_in_target_band"] and values["post_in_target_band"])
    first = values["first_target_band_step"]
    set_first = entered and first is None
    first_after = step_index if set_first else (int(first) if first is not None else None)
    ctx = values["context"]
    entry = {
        "step_index": step_index,
        "applied_at": values["applied_at"],
        "guidance_branch_before": ctx.get("guidance_branch_before"),
        "recommendation_title": str(values["recommendation_title"]),
        "recommendation_family_tag": values["recommendation_family_tag"],
        "recommendation_subfamilies": values["recommendation_subfamilies"],
        "pre_apply_worst_util": pre_wu,
        "post_apply_worst_util": post_wu,
        "pre_apply_statuses": dict(pre.get("statuses") or {}),
        "post_apply_statuses": dict(post.get("statuses") or {}),
        "pre_apply_signature": dict(values["pre_apply_signature"]),
        "post_apply_signature": dict(values["post_apply_signature"]),
        "pre_apply_target_band": [values["target_util_min"], values["target_util_max"]],
        "entered_target_band_on_this_step": entered,
        "first_target_band_step_after_apply": first_after,
        "applied_change_lines": list(values["applied_change_lines"]),
        "action_type": values["action_type"],
        "recommendation_label_at_step_start": ctx.get("recommendation_label_at_step_start"),
        "recommendation_action_type_at_step_start": ctx.get("recommendation_action_type_at_step_start"),
        "used_resolved_payload": bool(ctx.get("used_resolved_payload")),
        "one_click_candidate_available_at_step_start": bool(ctx.get("one_click_candidate_available_at_step_start")),
        "one_click_candidate_label_at_step_start": ctx.get("one_click_candidate_label_at_step_start"),
    }
    return entry, set_first, first_after


def main() -> int:
    inputs = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    builders = (ROOT / "inputs_page_modules" / "session" / "builders.py").read_text(encoding="utf-8")
    init_text = (ROOT / "inputs_page_modules" / "session" / "__init__.py").read_text(encoding="utf-8")
    base = {
        "context": {
            "guidance_branch_before": "repair",
            "recommendation_label_at_step_start": "Repair",
            "recommendation_action_type_at_step_start": "apply_resolved_candidate",
            "used_resolved_payload": True,
            "one_click_candidate_available_at_step_start": True,
            "one_click_candidate_label_at_step_start": "Candidate A",
        },
        "pre_overview": {"worst_util": 1.2, "statuses": {"bending": "FAIL"}},
        "post_overview": {"worst_util": 0.92, "statuses": {"bending": "PASS"}},
        "existing_step_count": 2,
        "applied_at": "2026-07-16T12:00:00",
        "recommendation_title": "Strengthen beam",
        "recommendation_family_tag": "BENDING_FAIL_GOVERNS",
        "recommendation_subfamilies": ["bottom_reo"],
        "pre_apply_signature": {"D_mm": 600.0},
        "post_apply_signature": {"D_mm": 650.0},
        "target_util_min": 0.85,
        "target_util_max": 1.0,
        "applied_change_lines": ["Depth: 600 -> 650"],
        "action_type": "apply_resolved_candidate",
    }
    scenarios = []
    for name, overrides in (
        ("enters_band_first_time", {"pre_in_target_band": False, "post_in_target_band": True, "first_target_band_step": None}),
        ("already_in_band", {"pre_in_target_band": True, "post_in_target_band": True, "first_target_band_step": 1}),
        ("still_outside", {"pre_in_target_band": False, "post_in_target_band": False, "first_target_band_step": None}),
        ("invalid_utils", {"pre_in_target_band": False, "post_in_target_band": False, "first_target_band_step": None, "pre_overview": {"worst_util": "bad"}, "post_overview": {"worst_util": None}}),
    ):
        values = dict(base)
        values.update(overrides)
        plan = build_inputs_design_guide_apply_step_history_entry_plan(**values)
        old_entry, old_set, old_first = _old_entry(**values)
        scenarios.append(
            {
                "name": name,
                "match": plan.entry == old_entry and plan.set_first_target_band_step == old_set and plan.first_target_band_step_after_apply == old_first and bool(plan.display_hash),
            }
        )
    failures = []
    if not all(row["match"] for row in scenarios):
        failures.append("Apply step-history entry parity failed")
    start = inputs.index("def _finalize_design_guide_apply_step_history")
    end = inputs.index("def _design_guide_step_history_debug_summary", start)
    body = inputs[start:end]
    if "build_inputs_design_guide_apply_step_history_entry_plan(" not in body:
        failures.append("page helper does not delegate entry construction")
    for snippet in ('"step_index": step_index', '"pre_apply_worst_util": pre_wu', '"entered_target_band_on_this_step": entered'):
        if snippet in body:
            failures.append(f"old page-owned entry construction remains: {snippet}")
    for required in ("_collect_design_overview(", "_compute_bottom_reo_recommendation(", "_guidance_apply_change_lines(", "st.session_state"):
        if required not in body:
            failures.append(f"required page-owned orchestration moved unexpectedly: {required}")
    if "st.session_state" in builders or "import streamlit" in builders or "import inputs_page" in builders:
        failures.append("session builder imports or reads forbidden page/UI state")
    if "build_inputs_design_guide_apply_step_history_entry_plan" not in init_text:
        failures.append("entry-plan builder is not exported")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_SESSION_DESIGN_GUIDE_APPLY_STEP_HISTORY_ENTRY_LOCKED" if not failures else "FAIL"
    result = {
        "audit": "inputs_session_design_guide_apply_step_history_entry_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "apply_orchestration_moved": False,
        "session_write_ownership_moved": False,
        "scenarios": scenarios,
        "failures": failures,
    }
    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_session_design_guide_apply_step_history_entry_{timestamp}.json"
    report_path = audit_dir / f"inputs_session_design_guide_apply_step_history_entry_{timestamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Session Design Guide Apply Step History Entry",
                "",
                f"Decision: `{decision}`",
                "",
                f"Scenarios checked: `{len(scenarios)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The session module owns pure entry construction and first-target-band step bookkeeping.",
                "`inputs_page.py` retains engineering callbacks, title resolution, timestamps, session mutation, and Apply orchestration.",
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
