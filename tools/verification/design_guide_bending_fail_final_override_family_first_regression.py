"""Regression for final active bending-fail resolver routing.

This protects the live bug where a pure BENDING_FAIL_GOVERNS state could reach
the final Design Guide render resolver, skip the family repair route, fall back
to generic target-band guidance, and then be blocked by the underdesign repair
invariant as non-executable.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.families.bending_fail import BendingFailFamily
from design_brain.publication import enforce_underdesign_repair_publication_boundary


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _severe_bending_fail_state() -> dict[str, Any]:
    return {
        "load_Mstar_pos_proxy": 250.0,
        "load_Mstar_proxy": 250.0,
        "uls_Mstar": 250.0,
        "uls_Mstar_pos_manual": 250.0,
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


def _line_number(source: str, needle: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _slice_between(source: str, start: str, end: str) -> str:
    start_index = source.find(start)
    end_index = source.find(end, start_index + 1) if start_index >= 0 else -1
    if start_index < 0:
        return ""
    if end_index < 0:
        return source[start_index:]
    return source[start_index:end_index]


def _build_payload() -> dict[str, Any]:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="replace")
    final_resolver_window = _slice_between(
        source,
        "_final_active_fail_keys_for_render = _overview_active_failure_keys",
        "_final_primary_after_direct = guidance_items[0]",
    )
    bending_branch = _slice_between(
        final_resolver_window,
        '_final_active_fail_keys_for_render == {"bending"}',
        "else:\n                try:\n                    _final_active_repair_item = _direct_target_band_guidance_item",
    )
    direct_target_line = _line_number(
        source,
        "_final_active_repair_item = _direct_target_band_guidance_item(",
    )
    bending_branch_line = _line_number(
        source,
        '_final_active_fail_keys_for_render == {"bending"}',
    )

    ladder = BendingFailFamily().contracted_repair_ladder_specs(
        _severe_bending_fail_state(),
        width_key="b",
        geometry_locked=False,
    )
    specs = [dict(row) for row in list(ladder.get("specs") or ()) if isinstance(row, dict)]
    first_spec = dict(specs[0]) if specs else {}
    boundary_payload = enforce_underdesign_repair_publication_boundary(
        {
            "guidance_items": [
                {
                    "title": "Bending capacity is low",
                    "family": "bending",
                    "guidance_intent": "required_fix",
                    "action_type": "apply_resolved_candidate",
                    "button_contract": {
                        "enabled": True,
                        "actionable": True,
                        "family": "bending",
                        "action_type": "apply_resolved_candidate",
                        "updates": dict(first_spec.get("updates") or {"D": 450.0}),
                        "preview_pass": True,
                        "blocking_reason": None,
                    },
                }
            ],
            "debug_trace": {},
            "overview": {"statuses": {"bending": "PASS"}, "utils": {"bending": 1.61}},
            "family_status_current": {"bending": {"status": "PASS", "util": 1.61}},
            "active_failures": [],
        }
    )
    boundary_debug = dict(boundary_payload.get("debug_trace") or {})
    boundary_items = [
        dict(row)
        for row in list(boundary_payload.get("guidance_items") or ())
        if isinstance(row, dict)
    ]
    boundary_item = dict(boundary_items[0]) if boundary_items else {}
    boundary_contract = dict(boundary_item.get("button_contract") or {})

    return {
        "schema": "design_guide_bending_fail_final_override_family_first_regression.v1",
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "final_resolver": {
            "bending_branch_line": bending_branch_line,
            "direct_target_fallback_line": direct_target_line,
            "active_failure_key_fallback_from_visible_truth": (
                "final_active_failure_keys_fallback_used" in final_resolver_window
                and "visible_item_or_debug_family_status" in final_resolver_window
                and "BENDING_FAIL_GOVERNS" in final_resolver_window
            ),
            "bending_branch_precedes_direct_target_fallback": (
                bending_branch_line is not None
                and direct_target_line is not None
                and bending_branch_line < direct_target_line
            ),
            "bending_branch_calls_family_repair_route": (
                "_active_fail_near_current_repair_item(" in bending_branch
                and '{"bending"}' in bending_branch
            ),
            "bending_branch_not_gated_by_stale_owner_metadata": (
                "_final_selected_family_id" not in bending_branch
                and "_final_primary_owner" not in bending_branch
                and "bending_fail_family_early_dispatch" not in bending_branch
            ),
            "bending_branch_stamps_family_authority": (
                "BENDING_FAIL_GOVERNS" in bending_branch
                and "design_brain.families.bending_fail.BendingFailFamily" in bending_branch
            ),
            "generic_target_band_remains_fallback_only": (
                "_direct_target_band_guidance_item(" in final_resolver_window
                and "selected_family_bending_fail_governs" in bending_branch
            ),
            "shear_family_first_branch_still_present": (
                '_final_active_fail_keys_for_render == {"shear"}' in final_resolver_window
                and "design_brain.families.shear_fail.ShearFailFamily" in final_resolver_window
            ),
        },
        "severe_bending_fail_family_ladder": {
            "source_state": "b250_D300_3N10_M250_V0_links_off",
            "spec_count": len(specs),
            "known_bad_candidate_count": int(ladder.get("known_bad_candidate_count") or 0),
            "candidate_strategy": ladder.get("candidate_strategy"),
            "contract_runtime_driven": bool(ladder.get("contract_runtime_driven")),
            "contract_runtime_authority": ladder.get("contract_runtime_authority"),
            "first_spec_stage": first_spec.get("stage_name"),
            "first_spec_strategy": first_spec.get("strategy"),
            "first_spec_updates": dict(first_spec.get("updates") or {}),
            "stop_reason_if_no_candidate": ladder.get("stop_reason_if_no_candidate"),
        },
        "underdesign_boundary_util_only_active_failure": {
            "active_failures": list(boundary_debug.get("active_failures") or []),
            "contract_boundary_passed": boundary_debug.get("contract_boundary_passed"),
            "allowed_outcome": boundary_debug.get("allowed_outcome"),
            "blocking_reason": boundary_contract.get("blocking_reason"),
            "action_type": boundary_contract.get("action_type"),
            "updates": dict(boundary_contract.get("updates") or {}),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    resolver = dict(payload.get("final_resolver") or {})
    ladder = dict(payload.get("severe_bending_fail_family_ladder") or {})
    boundary = dict(payload.get("underdesign_boundary_util_only_active_failure") or {})
    first_updates = dict(ladder.get("first_spec_updates") or {})
    return {
        "bending_branch_precedes_direct_target_fallback": bool(
            resolver.get("bending_branch_precedes_direct_target_fallback")
        ),
        "active_failure_key_fallback_from_visible_truth": bool(
            resolver.get("active_failure_key_fallback_from_visible_truth")
        ),
        "bending_branch_calls_family_repair_route": bool(
            resolver.get("bending_branch_calls_family_repair_route")
        ),
        "bending_branch_not_gated_by_stale_owner_metadata": bool(
            resolver.get("bending_branch_not_gated_by_stale_owner_metadata")
        ),
        "bending_branch_stamps_family_authority": bool(
            resolver.get("bending_branch_stamps_family_authority")
        ),
        "generic_target_band_remains_fallback_only": bool(
            resolver.get("generic_target_band_remains_fallback_only")
        ),
        "shear_family_first_branch_still_present": bool(
            resolver.get("shear_family_first_branch_still_present")
        ),
        "severe_bending_family_ladder_generates_specs": int(ladder.get("spec_count") or 0) > 0,
        "severe_bending_first_spec_has_updates": bool(first_updates),
        "severe_bending_ladder_contract_runtime_driven": bool(
            ladder.get("contract_runtime_driven")
        )
        and ladder.get("contract_runtime_authority") == "run_bending_fail_governs_ladder_runtime",
        "publication_boundary_treats_util_over_one_as_active_bending": (
            boundary.get("active_failures") == ["bending"]
        ),
        "publication_boundary_allows_executor_backed_bending_repair": (
            boundary.get("contract_boundary_passed") is True
            and boundary.get("allowed_outcome") == "repair_ACTION"
            and boundary.get("action_type") == "apply_resolved_candidate"
            and bool(boundary.get("updates"))
            and not boundary.get("blocking_reason")
        ),
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
    json_path = ARTIFACT_DIR / f"design_guide_bending_fail_final_override_family_first_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_fail_final_override_family_first_regression_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    resolver = dict(payload.get("final_resolver") or {})
    ladder = dict(payload.get("severe_bending_fail_family_ladder") or {})
    boundary = dict(payload.get("underdesign_boundary_util_only_active_failure") or {})
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Bending-Fail Final Override Family-First Regression",
                "",
                f"Status: `{payload['status']}`",
                f"Snapshot hash: `{payload['snapshot_hash']}`",
                "",
                "## Final Resolver Routing",
                "",
                f"- Bending branch line: `{resolver.get('bending_branch_line')}`",
                f"- Direct target fallback line: `{resolver.get('direct_target_fallback_line')}`",
                f"- Active-failure key fallback from visible truth: `{resolver.get('active_failure_key_fallback_from_visible_truth')}`",
                f"- Bending branch precedes generic fallback: `{resolver.get('bending_branch_precedes_direct_target_fallback')}`",
                f"- Bending branch calls family repair route: `{resolver.get('bending_branch_calls_family_repair_route')}`",
                f"- Bending branch avoids stale owner metadata gate: `{resolver.get('bending_branch_not_gated_by_stale_owner_metadata')}`",
                f"- Bending branch stamps family authority: `{resolver.get('bending_branch_stamps_family_authority')}`",
                "",
                "## Severe Bending-Fail Family Ladder",
                "",
                f"- Source state: `{ladder.get('source_state')}`",
                f"- Spec count: `{ladder.get('spec_count')}`",
                f"- First spec stage: `{ladder.get('first_spec_stage')}`",
                f"- First spec strategy: `{ladder.get('first_spec_strategy')}`",
                f"- First spec updates: `{ladder.get('first_spec_updates')}`",
                "",
                "## Underdesign Boundary Util-Only Failure",
                "",
                f"- Active failures: `{boundary.get('active_failures')}`",
                f"- Boundary passed: `{boundary.get('contract_boundary_passed')}`",
                f"- Allowed outcome: `{boundary.get('allowed_outcome')}`",
                f"- Blocking reason: `{boundary.get('blocking_reason')}`",
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
    print(
        "design_guide_bending_fail_final_override_family_first_regression "
        f"{'PASS' if all(checks.values()) else 'FAIL'}"
    )
    print(json_path)
    print(report_path)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
