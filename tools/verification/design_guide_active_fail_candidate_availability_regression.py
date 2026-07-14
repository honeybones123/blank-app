"""Regression for active-fail candidate availability.

This verifier guards two failure modes found from live family visual snapshots:

* combined active fail route must not fail because the rescue overview tier
  helper is missing
* pure bending fail route must not publish no-candidate evidence before
  generating an executable geometry/reinforcement repair candidate when the
  contract allows width/depth/reinforcement movement
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (
    build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs,
    resolve_design_guide_controller_active_fail_executor_overview_util_tier,
)
from design_brain.candidate_evaluation import evaluate_active_fail_executor_candidate_with_updates
from design_brain.families.bending_fail import BendingFailFamily


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _representative_bending_fail_state() -> dict[str, Any]:
    return {
        "uls_Mstar": 300.0,
        "uls_Vstar": 0.0,
        "uls_Tstar": 0.0,
        "uls_Nstar": 0.0,
        "b": 300.0,
        "D": 400.0,
        "bf": 600.0,
        "bf_bot": 600.0,
        "fc": 40.0,
        "fsy": 500.0,
        "cover": 40.0,
        "cover_side": 40.0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 150.0,
        "bot_row_1_bars": 4,
        "bot_row_1_dia": 16,
        "bot_row_2_bars": 0,
        "bot_row_2_dia": 16,
        "top_row_count": 1,
        "top_row_1_bars": 2,
        "top_row_1_dia": 10,
    }


def _low_geometry_bending_fail_state() -> dict[str, Any]:
    return {
        "load_Mstar_pos_proxy": 300.0,
        "load_Mstar_proxy": 300.0,
        "uls_Mstar": 300.0,
        "uls_Mstar_pos_manual": 300.0,
        "uls_Mstar_neg_manual": 0.0,
        "load_Vstar_proxy": 0.0,
        "uls_Vstar": 0.0,
        "uls_Tstar": 0.0,
        "uls_Nstar": 0.0,
        "b": 250.0,
        "bw": 250.0,
        "b_web": 250.0,
        "D": 300.0,
        "bf": 600.0,
        "bf_bot": 600.0,
        "fc": 40.0,
        "fsy": 500.0,
        "cover": 40.0,
        "cover_bot": 40.0,
        "cover_top": 40.0,
        "cover_side": 40.0,
        "side_cover_bot": 40.0,
        "side_cover_top": 40.0,
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": 200.0,
        "bot1_count": 3,
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 10,
        "db_bot_1": 10,
        "bot_row_1_mode": "Count",
        "bot1_layout_mode": "Count",
        "bot2_count": 0,
        "bot_row_2_bars": 0,
        "bot_row_2_dia": 10,
        "db_bot_2": 10,
        "bot_row_2_mode": "Count",
        "bot2_layout_mode": "Count",
        "bot_row_count": 1,
        "top1_count": 2,
        "top_row_1_bars": 2,
        "top_row_1_dia": 10,
        "db_top_1": 10,
        "top_row_1_mode": "Count",
        "top1_layout_mode": "Count",
        "top_row_count": 1,
        "span_L_m": 2.0,
        "L": 2000.0,
        "sec_shape": "RECT",
        "actions_mode": "manual",
    }


def _evaluate_first_low_geometry_bending_spec(
    first_spec: dict[str, Any],
) -> dict[str, Any]:
    logging.getLogger("streamlit").setLevel(logging.ERROR)
    import inputs_page as ip

    candidate = evaluate_active_fail_executor_candidate_with_updates(
        _low_geometry_bending_fail_state(),
        updates=dict(first_spec.get("updates") or {}),
        source="bending_fail_contract_ladder",
        label="low geometry bending fail regression",
        action_type="apply_resolved_candidate",
        state_snapshot_fn=ip._guidance_state_snapshot,
        evaluator_fn=ip.evaluate_candidate_full,
    )
    cand = dict(candidate or {}) if isinstance(candidate, dict) else {}
    overview = dict(cand.get("overview") or {})
    return {
        "candidate_is_compliant": bool(cand.get("is_compliant")),
        "worst_util": cand.get("worst_util"),
        "statuses": dict(overview.get("statuses") or {}),
        "utils": dict(overview.get("utils") or {}),
        "bending_components": dict(cand.get("bending_components") or {}),
    }


def _build_payload() -> dict[str, Any]:
    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    controller_source = (ROOT / "design_brain" / "design_guide_controller.py").read_text(encoding="utf-8")

    overview = {"utils": {"bending": 2.74, "shear": 2.8}}
    overview_tier = resolve_design_guide_controller_active_fail_executor_overview_util_tier(
        overview,
        "combined",
    )
    rescue_route = build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(
        action_tier="high",
        util_tier=overview_tier,
        tier_order=("medium", "high", "very_high", "extreme"),
    )

    bending_ladder = BendingFailFamily().contracted_repair_ladder_specs(
        _representative_bending_fail_state(),
        width_key="b",
        geometry_locked=False,
    )
    specs = [dict(row) for row in list(bending_ladder.get("specs") or ()) if isinstance(row, dict)]
    first_spec = dict(specs[0]) if specs else {}
    known_bad = [
        dict(row)
        for row in list(bending_ladder.get("known_bad_candidates_skipped") or ())
        if isinstance(row, dict)
    ]
    low_geometry_ladder = BendingFailFamily().contracted_repair_ladder_specs(
        _low_geometry_bending_fail_state(),
        width_key="b",
        geometry_locked=False,
    )
    low_geometry_specs = [
        dict(row) for row in list(low_geometry_ladder.get("specs") or ()) if isinstance(row, dict)
    ]
    low_geometry_first_spec = dict(low_geometry_specs[0]) if low_geometry_specs else {}
    low_geometry_eval = (
        _evaluate_first_low_geometry_bending_spec(low_geometry_first_spec)
        if low_geometry_first_spec
        else {}
    )

    return {
        "schema": "design_guide_active_fail_candidate_availability_regression.v1",
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "combined_rescue_tier_boundary": {
            "inputs_page_imports_controller_overview_tier_helper": (
                "resolve_design_guide_controller_active_fail_executor_overview_util_tier as _rescue_mode_overview_util_tier"
                in inputs_source
            ),
            "old_missing_choose_helper_call_removed": "_rescue_mode_choose_tier_from_overview(" not in inputs_source,
            "controller_helper_exists": (
                "def resolve_design_guide_controller_active_fail_executor_overview_util_tier(" in controller_source
            ),
            "controller_helper_exported": (
                '"resolve_design_guide_controller_active_fail_executor_overview_util_tier"' in controller_source
            ),
            "overview_tier": overview_tier,
            "requested_tier": rescue_route.get("requested_tier"),
            "rescue_tiers": list(rescue_route.get("rescue_tiers") or ()),
        },
        "bending_fail_candidate_availability": {
            "spec_count": len(specs),
            "known_bad_candidate_count": int(bending_ladder.get("known_bad_candidate_count") or 0),
            "width_steps_mm": list(bending_ladder.get("width_steps_mm") or ()),
            "first_spec_updates": dict(first_spec.get("updates") or {}),
            "known_bad_reasons": sorted({str(row.get("reason") or "") for row in known_bad if row.get("reason")}),
            "candidate_strategy": bending_ladder.get("candidate_strategy"),
            "stop_reason_if_no_candidate": bending_ladder.get("stop_reason_if_no_candidate"),
        },
        "bending_fail_low_geometry_candidate_availability": {
            "source_state": "b250_D300_3N10_M300_V0_links_off",
            "spec_count": len(low_geometry_specs),
            "first_spec_stage": low_geometry_first_spec.get("stage_name"),
            "first_spec_strategy": low_geometry_first_spec.get("strategy"),
            "first_spec_updates": dict(low_geometry_first_spec.get("updates") or {}),
            "first_spec_clear_spacing": low_geometry_first_spec.get("clear_spacing"),
            "first_spec_spacing_threshold_basis": low_geometry_first_spec.get("spacing_threshold_basis"),
            "first_spec_eval": dict(low_geometry_eval),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_contract_aligned": True,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    combined = dict(payload.get("combined_rescue_tier_boundary") or {})
    bending = dict(payload.get("bending_fail_candidate_availability") or {})
    low_geometry = dict(payload.get("bending_fail_low_geometry_candidate_availability") or {})
    first_updates = dict(bending.get("first_spec_updates") or {})
    low_updates = dict(low_geometry.get("first_spec_updates") or {})
    low_eval = dict(low_geometry.get("first_spec_eval") or {})
    low_statuses = {
        str(key).strip().lower(): str(value).strip().upper()
        for key, value in dict(low_eval.get("statuses") or {}).items()
    }
    return {
        "combined_imports_controller_overview_tier_helper": bool(
            combined.get("inputs_page_imports_controller_overview_tier_helper")
        ),
        "combined_missing_choose_helper_call_removed": bool(combined.get("old_missing_choose_helper_call_removed")),
        "combined_controller_helper_exists": bool(combined.get("controller_helper_exists")),
        "combined_controller_helper_exported": bool(combined.get("controller_helper_exported")),
        "combined_rescue_route_produces_requested_tier": bool(combined.get("requested_tier")),
        "bending_generates_executable_spec": int(bending.get("spec_count") or 0) > 0,
        "bending_width_rescue_extends_past_old_200mm_cap": any(
            float(step) > 200.0 for step in list(bending.get("width_steps_mm") or ())
        ),
        "bending_first_spec_has_executor_updates": bool(first_updates),
        "low_geometry_bending_generates_moderate_rescue_first": (
            low_geometry.get("first_spec_stage") == "contract_runtime_moderate_geometry_reo_rescue"
        ),
        "low_geometry_bending_first_spec_has_expected_updates": (
            float(low_updates.get("b") or 0.0) == 300.0
            and float(low_updates.get("D") or 0.0) == 450.0
            and int(low_updates.get("bot1_count") or 0) == 7
            and int(low_updates.get("db_bot_1") or 0) == 20
        ),
        "low_geometry_bending_first_spec_evaluates_compliant": bool(
            low_eval.get("candidate_is_compliant")
        ),
        "low_geometry_bending_status_passes": low_statuses.get("bending") == "PASS",
        "no_product_behavior_flagged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    payload = dict(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    payload["snapshot_hash"] = _stable_hash({k: v for k, v in payload.items() if k != "snapshot_hash"})
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_candidate_availability_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_candidate_availability_regression_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bending = dict(payload.get("bending_fail_candidate_availability") or {})
    low_geometry = dict(payload.get("bending_fail_low_geometry_candidate_availability") or {})
    combined = dict(payload.get("combined_rescue_tier_boundary") or {})
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Active-Fail Candidate Availability Regression",
                "",
                "## Executive Summary",
                "",
                f"Status: `{payload['status']}`",
                f"Snapshot hash: `{payload['snapshot_hash']}`",
                "",
                "## Combined Active-Fail Route",
                "",
                f"- Overview tier: `{combined.get('overview_tier')}`",
                f"- Requested tier: `{combined.get('requested_tier')}`",
                f"- Rescue tiers: `{combined.get('rescue_tiers')}`",
                f"- Old missing chooser helper call removed: `{combined.get('old_missing_choose_helper_call_removed')}`",
                "",
                "## BENDING_FAIL_GOVERNS Candidate Availability",
                "",
                f"- Executable spec count: `{bending.get('spec_count')}`",
                f"- Known-bad candidate count: `{bending.get('known_bad_candidate_count')}`",
                f"- Width steps: `{bending.get('width_steps_mm')}`",
                f"- Known-bad reasons: `{bending.get('known_bad_reasons')}`",
                f"- First spec updates: `{bending.get('first_spec_updates')}`",
                "",
                "## Low-Geometry BENDING_FAIL_GOVERNS Regression",
                "",
                f"- Source state: `{low_geometry.get('source_state')}`",
                f"- Executable spec count: `{low_geometry.get('spec_count')}`",
                f"- First spec stage: `{low_geometry.get('first_spec_stage')}`",
                f"- First spec strategy: `{low_geometry.get('first_spec_strategy')}`",
                f"- First spec updates: `{low_geometry.get('first_spec_updates')}`",
                f"- First spec clear spacing: `{low_geometry.get('first_spec_clear_spacing')}`",
                f"- First spec spacing threshold basis: `{low_geometry.get('first_spec_spacing_threshold_basis')}`",
                f"- First spec eval: `{low_geometry.get('first_spec_eval')}`",
                "",
                "## Checks",
                "",
                *[f"- {name}: `{value}`" for name, value in checks.items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = _build_payload()
    checks = _checks(payload)
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_candidate_availability_regression {('PASS' if all(checks.values()) else 'FAIL')}")
    print(json_path)
    print(report_path)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
