"""Regression snapshot for BENDING D/b ratio gating and reo arrangement spacing.

This verifier is intentionally focused:
- BENDING_FAIL_GOVERNS family spec generation must not emit candidates whose
  depth/width ratio exceeds the contract limit.
- Canonical Design Guide state must expose resolved longitudinal spacing from
  the actual layout engine, not stale row input compatibility spacing.

It does not drive CTA, publication, rendering, apply routing, or session state.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.families.bending_fail import BendingFailFamily  # noqa: E402
from design_brain.families.bending_fail_governs.contract import depth_width_rule  # noqa: E402
from design_brain.families.bending_fail_governs.geometry_ratio import (  # noqa: E402
    depth_width_ratio,
    guard_bending_depth_width_geometry_update,
)
from design_brain.candidate_evaluation import resolve_minimum_longitudinal_bar_rule  # noqa: E402
from design_brain.design_guide_controller import (  # noqa: E402
    accept_design_guide_controller_active_fail_executor_repair_candidate,
)
from inputs_application.geometry_search_policy import geometry_state_with_updates  # noqa: E402
from inputs_application.page_runtime.common import _build_canonical_design_state_pack  # noqa: E402
from inputs_page_modules.design_guide.current_coordinators import (  # noqa: E402
    _promote_button_contract_from_final_publication_cta,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable(value):
    if isinstance(value, dict):
        return {str(k): _stable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def _ratio(width, depth):
    try:
        width_f = float(width)
        depth_f = float(depth)
    except (TypeError, ValueError):
        return None
    if width_f <= 0.0:
        return None
    return depth_f / width_f


def _base_bending_state(**overrides):
    state = {
        "b": 300.0,
        "D": 400.0,
        "cover_side": 40.0,
        "cover_top": 40.0,
        "cover_bot": 40.0,
        "lig_d": 10,
        "lig_legs": 2,
        "bot_row_count": 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 4,
        "bot_row_1_spacing": 200.0,
        "bot_row_1_dia": 20,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": 0,
        "bot_row_2_spacing": 200.0,
        "bot_row_2_dia": 20,
        "top_row_count": 1,
        "top_row_1_mode": "Count",
        "top_row_1_bars": 2,
        "top_row_1_spacing": 200.0,
        "top_row_1_dia": 16,
        "top_row_2_mode": "Count",
        "top_row_2_bars": 0,
        "top_row_2_spacing": 200.0,
        "top_row_2_dia": 16,
        "min_clear_spacing": 20.0,
    }
    state.update(overrides)
    return state


def _ladder_case(name: str, state: dict) -> dict:
    family = BendingFailFamily()
    limit = float(depth_width_rule().get("maximum_preferred_ratio") or 0.0)
    ladder = family.contracted_repair_ladder_specs(state, width_key="b", geometry_locked=False)
    specs = list(ladder.get("specs") or [])
    known_bad = list(ladder.get("known_bad_candidates_skipped") or [])
    spec_rows = []
    invalid_specs = []
    for spec in specs:
        width = spec.get("b")
        depth = spec.get("D")
        ratio = _ratio(width, depth)
        row = {
            "stage_name": spec.get("stage_name"),
            "lane_id": spec.get("contract_runtime_lane_id"),
            "b": width,
            "D": depth,
            "depth_width_ratio": ratio,
            "update_keys": sorted((spec.get("updates") or {}).keys()),
        }
        spec_rows.append(row)
        if ratio is not None and ratio > limit + 1e-9:
            invalid_specs.append(row)
    ratio_known_bad = [
        row for row in known_bad if row.get("reason") == "depth_width_ratio_above_contract_limit"
    ]
    return {
        "name": name,
        "maximum_depth_width_ratio": limit,
        "spec_count": len(specs),
        "known_bad_count": len(known_bad),
        "ratio_known_bad_count": len(ratio_known_bad),
        "invalid_specs": invalid_specs,
        "spec_rows": spec_rows,
        "ratio_known_bad": ratio_known_bad,
        "passes": not invalid_specs,
    }


def _arrangement_case(name: str, state: dict, expected_spacing: float) -> dict:
    pack = _build_canonical_design_state_pack(state)
    bot_rows = list(pack.get("bot_rows_resolved") or [])
    active_bot_rows = [row for row in bot_rows if row.get("active")]
    primary = active_bot_rows[0] if active_bot_rows else {}
    actual_spacing = float(pack.get("s_bot", 0.0) or 0.0)
    primary_spacing = float(primary.get("spacing_resolved", 0.0) or 0.0)
    return {
        "name": name,
        "canonical_pack_valid": bool(pack.get("canonical_pack_valid")),
        "input_row_spacing": state.get("bot_row_1_spacing"),
        "s_bot": actual_spacing,
        "primary_spacing_resolved": primary_spacing,
        "expected_spacing": expected_spacing,
        "active_bottom_row_count": len(active_bot_rows),
        "bottom_rows": [
            {
                "row_index": row.get("row_index"),
                "bar_count_resolved": row.get("bar_count_resolved"),
                "spacing_resolved": row.get("spacing_resolved"),
                "fit_ok": row.get("fit_ok"),
            }
            for row in bot_rows
        ],
        "passes": bool(pack.get("canonical_pack_valid"))
        and abs(actual_spacing - expected_spacing) <= 1e-6
        and abs(primary_spacing - expected_spacing) <= 1e-6,
    }


def _later_geometry_ratio_case() -> dict:
    state = _base_bending_state(D=300.0, b=300.0)
    guarded = guard_bending_depth_width_geometry_update(
        current_width=float(state["b"]),
        current_depth=float(state["D"]),
        updates={"D": 850.0},
        width_update_key="b",
        width_locked=False,
        allow_width_rescue=True,
        minimum_practical_width=100.0,
    )
    updates = dict(guarded.updates)
    after = dict(state)
    after.update(updates)
    ratio = depth_width_ratio(width=float(after.get("b") or 0.0), depth=float(after.get("D") or 0.0))
    limit = float(depth_width_rule().get("maximum_preferred_ratio") or 0.0)
    return {
        "name": "increase_depth_action_rescues_width_for_ratio",
        "updates": updates,
        "D_after": after.get("D"),
        "b_after": after.get("b"),
        "depth_width_ratio_after": ratio,
        "maximum_depth_width_ratio": limit,
        "passes": bool(updates)
        and "D" in updates
        and "b" in updates
        and ratio is not None
        and ratio <= limit + 1e-9,
    }


def _geometry_state_builder_ratio_case() -> dict:
    state = _base_bending_state(D=800.0, b=300.0)
    candidate_state = geometry_state_with_updates(state, depth=850.0)
    ratio = depth_width_ratio(
        width=float(candidate_state.get("b") or 0.0),
        depth=float(candidate_state.get("D") or 0.0),
    )
    limit = float(depth_width_rule().get("maximum_preferred_ratio") or 0.0)
    return {
        "name": "geometry_state_builder_rescues_width_for_ratio",
        "D_after": candidate_state.get("D"),
        "b_after": candidate_state.get("b"),
        "depth_width_ratio_after": ratio,
        "maximum_depth_width_ratio": limit,
        "passes": ratio is not None and ratio <= limit + 1e-9 and float(candidate_state.get("b") or 0.0) > 300.0,
    }


def _stale_apply_payload_ratio_case() -> dict:
    state = _base_bending_state(D=300.0, b=300.0)
    guard = guard_bending_depth_width_geometry_update(
        current_width=float(state["b"]),
        current_depth=float(state["D"]),
        updates={"D": 850.0},
        width_update_key="b",
        width_locked=False,
        allow_width_rescue=False,
        minimum_practical_width=100.0,
    )
    return {
        "name": "stale_depth_only_apply_payload_blocked",
        "guard": dict(guard.__dict__),
        "passes": guard.blocked is True
        and guard.reason == "depth_width_ratio_above_contract_limit",
    }


def _stale_primary_payload_recovery_case() -> dict:
    fresh_updates = {"D": 850.0, "b": 430.0}
    stale_contract = {
        "enabled": False,
        "actionable": False,
        "family": "BENDING_FAIL_GOVERNS",
        "updates": {"D": 850.0},
        "disabled_reason": "stale_primary_payload",
    }
    item = {
        "family": "BENDING_FAIL_GOVERNS",
        "final_publication_verifier_payload": {
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "cta": {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family_id": "BENDING_FAIL_GOVERNS",
                "updates": dict(fresh_updates),
                "candidate_id": "fresh_final_publication_candidate",
            },
        },
    }
    promoted, recovered = _promote_button_contract_from_final_publication_cta(
        item=item,
        button_contract=stale_contract,
    )
    return {
        "name": "stale_primary_payload_recovers_from_final_publication_cta",
        "recovered": recovered,
        "promoted_contract": promoted,
        "passes": recovered is True
        and promoted.get("enabled") is True
        and promoted.get("updates") == fresh_updates
        and promoted.get("winning_update_payload_source")
        == "FinalDesignGuidePublication.cta.updates",
    }


def _minimum_two_bars_per_face_cases() -> list[dict]:
    cases = []
    valid_state = _base_bending_state()
    bottom_invalid = _base_bending_state(bot_row_1_bars=1, bot1_count=1)
    top_invalid = _base_bending_state(top_row_1_bars=1, top1_count=1)
    update_invalid = _base_bending_state()
    for name, state, updates, expected_valid in (
        ("valid_two_top_two_bottom", valid_state, {}, True),
        ("reject_one_bottom_bar", bottom_invalid, {}, False),
        ("reject_one_top_bar", top_invalid, {}, False),
        ("reject_update_to_one_bottom_bar", update_invalid, {"bot1_count": 1, "bot_row_1_bars": 1}, False),
    ):
        rule = resolve_minimum_longitudinal_bar_rule(state, updates)
        controller_accepts = None
        if updates:
            controller_accepts = (
                accept_design_guide_controller_active_fail_executor_repair_candidate(
                    candidate={
                        "is_compliant": True,
                        "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                        "overview": {
                            "all_key_pass": True,
                            "any_fail": False,
                        },
                        "updates": dict(updates),
                    },
                    base_state=state,
                    combined_family_ladder_attempted=True,
                )
            )
        cases.append(
            {
                "name": name,
                "rule": rule,
                "controller_accepts": controller_accepts,
                "expected_valid": expected_valid,
                "passes": bool(rule.get("valid")) is expected_valid
                and (
                    controller_accepts is None
                    or controller_accepts is False
                ),
            }
        )
    return cases


def build_snapshot() -> dict:
    ratio_cases = [
        _ladder_case("default_rescue_filters_over_ratio_candidate", _base_bending_state()),
        _ladder_case("depth_growth_blocked_when_next_depth_exceeds_ratio", _base_bending_state(D=590.0)),
    ]
    arrangement_cases = [
        _arrangement_case("count_mode_spacing_resolves_from_layout", _base_bending_state(), 66.66666666666667),
        _arrangement_case("width_change_recomputes_spacing", _base_bending_state(b=400.0), 100.0),
        _arrangement_case(
            "two_layer_count_mode_resolves_primary_spacing",
            _base_bending_state(
                bot_row_count=2,
                bot_row_1_bars=3,
                bot_row_1_dia=20,
                bot_row_2_bars=3,
                bot_row_2_dia=20,
            ),
            100.0,
        ),
    ]
    later_geometry_ratio_cases = [
        _later_geometry_ratio_case(),
        _geometry_state_builder_ratio_case(),
        _stale_apply_payload_ratio_case(),
    ]
    stale_primary_payload_recovery_case = _stale_primary_payload_recovery_case()
    minimum_bar_cases = _minimum_two_bars_per_face_cases()
    forbidden_fields = {
        "cta_rendering": False,
        "publication_rendering": False,
        "apply_routing": False,
        "session_state_required": False,
        "ui_widget_required": False,
        "inputs_page_direct_contract_json_owner": False,
    }
    geometry_policy_source = (ROOT / "inputs_application" / "geometry_search_policy.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    controller_source = (ROOT / "design_brain" / "design_guide_controller.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    coordinator_source = (
        ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py"
    ).read_text(encoding="utf-8", errors="replace")
    widget_runtime_source = (
        ROOT / "inputs_application" / "page_runtime" / "widgets.py"
    ).read_text(encoding="utf-8", errors="replace")
    design_brain_policy_case = guard_bending_depth_width_geometry_update(
        current_width=300.0,
        current_depth=300.0,
        updates={"D": 850.0},
        width_update_key="b",
        width_locked=False,
        allow_width_rescue=True,
        minimum_practical_width=100.0,
    )
    policy_boundary = {
        "design_brain_helper_imports": True,
        "geometry_policy_imports_geometry_ratio_helper": "bending_fail_governs.geometry_ratio" in geometry_policy_source,
        "geometry_policy_imports_bending_fail_contract_directly": "bending_fail_governs.contract import" in geometry_policy_source,
        "design_brain_helper_rescues_width": bool(design_brain_policy_case.rescued),
        "design_brain_helper_updates": dict(design_brain_policy_case.updates),
        "design_brain_helper_ratio": design_brain_policy_case.depth_width_ratio,
        "model_2d_no_longer_blocked_by_ratio": "_inputs_geometry_detailing_diagram_blocker" not in widget_runtime_source,
        "model_3d_no_longer_blocked_by_ratio": "_inputs_geometry_detailing_diagram_blocker" not in widget_runtime_source,
        "active_fail_acceptance_uses_minimum_bar_rule": "resolve_minimum_longitudinal_bar_rule(state, updates)" in controller_source,
        "stale_primary_payload_can_recover_from_final_publication_cta": (
            "def _promote_button_contract_from_final_publication_cta(" in coordinator_source
            and '"winning_update_payload_source": "FinalDesignGuidePublication.cta.updates"' in coordinator_source
            and stale_primary_payload_recovery_case.get("passes") is True
        ),
    }
    failures = []
    for case in ratio_cases:
        if not case.get("passes"):
            failures.append(f"ratio_case_failed:{case.get('name')}")
    if not any(case.get("ratio_known_bad_count", 0) > 0 for case in ratio_cases):
        failures.append("no_ratio_known_bad_record_observed")
    for case in arrangement_cases:
        if not case.get("passes"):
            failures.append(f"arrangement_case_failed:{case.get('name')}")
    for case in later_geometry_ratio_cases:
        if not case.get("passes"):
            failures.append(f"later_geometry_ratio_case_failed:{case.get('name')}")
    for case in minimum_bar_cases:
        if not case.get("passes"):
            failures.append(f"minimum_bar_case_failed:{case.get('name')}")
    if not stale_primary_payload_recovery_case.get("passes"):
        failures.append("stale_primary_payload_recovery_case_failed")
    if not policy_boundary["model_2d_no_longer_blocked_by_ratio"]:
        failures.append("model_2d_still_blocked_by_geometry_ratio")
    if not policy_boundary["model_3d_no_longer_blocked_by_ratio"]:
        failures.append("model_3d_still_blocked_by_geometry_ratio")
    if not policy_boundary["active_fail_acceptance_uses_minimum_bar_rule"]:
        failures.append("active_fail_acceptance_missing_minimum_two_bar_rule")
    if not policy_boundary["stale_primary_payload_can_recover_from_final_publication_cta"]:
        failures.append("stale_primary_payload_cannot_recover_from_final_publication_cta")
    if not policy_boundary["geometry_policy_imports_geometry_ratio_helper"]:
        failures.append("geometry_policy_not_using_design_brain_geometry_ratio_helper")
    if policy_boundary["geometry_policy_imports_bending_fail_contract_directly"]:
        failures.append("geometry_policy_imports_bending_fail_contract_directly")
    if not policy_boundary["design_brain_helper_rescues_width"]:
        failures.append("design_brain_geometry_ratio_helper_did_not_rescue_width")
    return {
        "schema": "design_guide_ratio_reo_arrangement_regression_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "ratio_owner": "design_brain.families.bending_fail.BendingFailFamily.contracted_repair_ladder_specs",
        "ratio_contract_source": "design_brain/families/bending_fail_governs/contract.json:depth_width_rule.maximum_preferred_ratio",
        "ratio_policy_boundary": policy_boundary,
        "arrangement_owner": "inputs_application.page_runtime.common._build_canonical_design_state_pack + section_layout.compute_section_layout_pure",
        "ratio_cases": ratio_cases,
        "later_geometry_ratio_cases": later_geometry_ratio_cases,
        "arrangement_cases": arrangement_cases,
        "minimum_bar_cases": minimum_bar_cases,
        "stale_primary_payload_recovery_case": stale_primary_payload_recovery_case,
        "forbidden_fields": forbidden_fields,
    }


def write_artifacts(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_guide_ratio_reo_arrangement_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_ratio_reo_arrangement_regression_{stamp}.md"
    artifact_path.write_text(json.dumps(_stable(snapshot), indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Ratio / Reo Arrangement Regression Snapshot",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Owners",
        f"- Ratio owner: `{snapshot['ratio_owner']}`",
        f"- Ratio contract source: `{snapshot['ratio_contract_source']}`",
        f"- Arrangement owner: `{snapshot['arrangement_owner']}`",
        "",
        "## Ratio Cases",
    ]
    for case in snapshot["ratio_cases"]:
        lines.extend(
            [
                f"- `{case['name']}`: passes=`{case['passes']}`, "
                f"spec_count=`{case['spec_count']}`, ratio_known_bad_count=`{case['ratio_known_bad_count']}`",
            ]
        )
    lines.append("")
    lines.append("## Later Geometry Ratio Cases")
    for case in snapshot["later_geometry_ratio_cases"]:
        lines.extend(
            [
                f"- `{case['name']}`: passes=`{case['passes']}`, "
                f"D_after=`{case.get('D_after')}`, b_after=`{case.get('b_after')}`, "
                f"ratio_after=`{case.get('depth_width_ratio_after')}`",
            ]
        )
    lines.append("")
    lines.append("## Minimum Longitudinal Bar Cases")
    for case in snapshot["minimum_bar_cases"]:
        rule = case.get("rule") or {}
        lines.extend(
            [
                f"- `{case['name']}`: passes=`{case['passes']}`, "
                f"bottom=`{rule.get('bottom_bar_count')}`, top=`{rule.get('top_bar_count')}`, "
                f"valid=`{rule.get('valid')}`",
            ]
        )
    lines.append("")
    lines.append("## Arrangement Cases")
    for case in snapshot["arrangement_cases"]:
        lines.extend(
            [
                f"- `{case['name']}`: passes=`{case['passes']}`, "
                f"s_bot=`{round(float(case['s_bot']), 6)}`, expected=`{round(float(case['expected_spacing']), 6)}`, "
                f"input_row_spacing=`{case['input_row_spacing']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Policy Boundary",
            f"- Geometry policy imports Design Brain geometry helper: `{snapshot['ratio_policy_boundary']['geometry_policy_imports_geometry_ratio_helper']}`",
            f"- Geometry policy imports bending contract directly: `{snapshot['ratio_policy_boundary']['geometry_policy_imports_bending_fail_contract_directly']}`",
            f"- Design Brain helper rescued width: `{snapshot['ratio_policy_boundary']['design_brain_helper_rescues_width']}`",
            f"- Stale primary payload recovers from FinalDesignGuidePublication.cta: `{snapshot['ratio_policy_boundary']['stale_primary_payload_can_recover_from_final_publication_cta']}`",
            "",
            "## Exclusions",
            "- No CTA rendering, publication rendering, apply routing, session state, or UI widget path is part of this proof.",
            "",
            "## Failures",
            *(f"- `{failure}`" for failure in snapshot.get("failures") or []),
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return artifact_path, report_path


def main() -> int:
    snapshot = build_snapshot()
    artifact_path, report_path = write_artifacts(snapshot)
    print(f"design_guide_ratio_reo_arrangement_regression {snapshot['result']}")
    print(f"artifact: {artifact_path}")
    print(f"report: {report_path}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
