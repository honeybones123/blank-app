"""Snapshot for active-fail rescue seed tier selection.

This verifier protects the case where absolute actions are modest but
utilisation already proves active bending/shear failure. The active-fail
runtime must receive approved rescue seed candidates in that case instead of
exhausting an empty candidate set.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run_compile(paths: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *paths],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": f"python -m py_compile {' '.join(paths)}",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _source_checks(source: str) -> dict[str, Any]:
    return {
        "combined_runtime_feed_uses_controller_route_inputs": (
            "_build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(\n"
            '                action_tier=_rescue_mode_action_tier(base, "combined"),\n'
            "                util_tier=_rescue_mode_overview_util_tier("
        )
        in source,
        "fallback_rescue_feed_uses_controller_route_inputs": (
            "_build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(\n"
            "            action_tier=_rescue_mode_action_tier(base, rescue_family),\n"
            "            util_tier=_rescue_mode_overview_util_tier("
        )
        in source,
        "smart_active_failure_feed_uses_controller_route_inputs": (
            "_build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(\n"
            "                action_tier=_rescue_mode_action_tier(base, family),\n"
            "                util_tier=_rescue_mode_overview_util_tier("
        )
        in source,
        "old_combined_action_only_feed_removed": (
            'requested_tier = _rescue_mode_action_tier(base, "combined")' not in source
        ),
        "deleted_choose_tier_from_overview_helper_not_used": (
            "_rescue_mode_choose_tier_from_overview" not in source
        ),
    }


def _build_snapshot() -> dict[str, Any]:
    import inputs_page  # type: ignore
    from design_brain.design_guide_controller import (
        build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs,
        resolve_design_guide_controller_active_fail_executor_overview_util_tier,
    )
    from design_brain.families.registry import family_strategy_for

    source = INPUTS_PAGE.read_text(encoding="utf-8")
    base = {
        "uls_Mstar": 200.0,
        "uls_Vstar": 100.0,
        "uls_Tstar": 0.0,
        "uls_Nstar": 0.0,
        "b": 250.0,
        "D": 500.0,
    }
    overview = {
        "utils": {"bending": 1.80, "shear": 1.55},
        "statuses": {"bending": "FAIL", "shear": "FAIL"},
        "any_fail": True,
        "all_key_pass": False,
    }

    action_tier = inputs_page._rescue_mode_action_tier(base, "combined")
    overview_tier = resolve_design_guide_controller_active_fail_executor_overview_util_tier(
        overview,
        "combined",
    )
    rescue_tier_inputs = build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(
        action_tier=action_tier,
        util_tier=overview_tier,
        tier_order=tuple(inputs_page.RESCUE_MODE_TIER_ORDER),
    )
    chosen_tier = rescue_tier_inputs.get("requested_tier")
    seed_order = list(rescue_tier_inputs.get("rescue_tiers") or [])
    approved_combined_merge_candidates: list[dict[str, Any]] = []
    for tier in seed_order:
        seed_spec = dict(((inputs_page.RESCUE_SEED_LIBRARY.get("combined") or {}).get(tier)) or {})
        seed_updates = dict(seed_spec.get("updates") or {})
        if not seed_updates:
            continue
        approved_combined_merge_candidates.append(
            {
                "source_family_id": "APPROVED_COMBINED_MERGE_RULE",
                "candidate_id": str(seed_spec.get("key") or f"combined_{tier}"),
                "updates": seed_updates,
                "evidence": {
                    "source": "RESCUE_SEED_LIBRARY",
                    "tier": tier,
                    "approved_merge_rule": "unlocked_combined_fail_rescue_seed",
                },
            }
        )
    medium_seed = dict(
        ((inputs_page.RESCUE_SEED_LIBRARY.get("combined") or {}).get("medium") or {})
    )
    medium_updates = dict(medium_seed.get("updates") or {})
    combined_strategy = family_strategy_for("COMBINED_BENDING_SHEAR_FAIL")
    combined_ladder = combined_strategy.contracted_repair_ladder_specs(
        base,
        width_key="b",
        geometry_locked=False,
        approved_combined_merge_candidates=tuple(approved_combined_merge_candidates),
    )
    combined_specs = list(combined_ladder.get("specs") or [])
    first_spec = dict(combined_specs[0] or {}) if combined_specs else {}
    first_source_proof = dict(first_spec.get("candidate_source_proof") or {})
    first_refinement_proof = dict(first_spec.get("target_band_refinement_proof") or {})
    first_exact_stop_proof = dict(first_spec.get("exact_stop_proof") or {})
    source_checks = _source_checks(source)
    required_bending_update_keys = ("bot1_count", "db_bot_1", "D", "b")
    required_shear_update_keys = ("lig_d", "lig_legs", "s_lig")
    seed_has_bending_updates = all(key in medium_updates for key in required_bending_update_keys)
    seed_has_shear_updates = all(key in medium_updates for key in required_shear_update_keys)

    checks = {
        "low_action_case_would_have_no_action_seed": action_tier is None,
        "overview_utilisation_selects_medium": overview_tier == "medium",
        "combined_choice_uses_overview_medium": chosen_tier == "medium",
        "seed_order_non_empty": bool(seed_order),
        "seed_order_starts_at_medium": seed_order[:1] == ["medium"],
        "medium_combined_seed_has_bending_updates": seed_has_bending_updates,
        "medium_combined_seed_has_shear_updates": seed_has_shear_updates,
        "approved_combined_merge_candidates_created": len(approved_combined_merge_candidates) == 4,
        "combined_runtime_returns_repair_specs": len(combined_specs) == 4,
        "combined_runtime_uses_approved_merge_rule": (
            first_source_proof.get("approved_combined_merge_candidate_count") == 4
            and first_source_proof.get("all_sources_allowed") is True
        ),
        "combined_runtime_does_not_fake_exact_stop_for_unproven_seed": first_exact_stop_proof.get("exact_stop") is False,
        "combined_runtime_records_target_band_refinement_lane": (
            first_refinement_proof.get("lane_id") == "APPROVED_COMBINED_TARGET_BAND_REFINEMENT"
            and first_refinement_proof.get("exact_stop_requires_evaluated_target_band") is True
        ),
        "combined_runtime_selects_safe_fallback_with_reason": (
            first_refinement_proof.get("fallback_selected") is True
            and bool(first_refinement_proof.get("fallback_reason"))
        ),
        **source_checks,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "case": {
            "base": base,
            "overview": overview,
            "action_tier": action_tier,
            "overview_tier": overview_tier,
            "chosen_tier": chosen_tier,
            "seed_order": seed_order,
            "approved_candidate_ids": [
                candidate.get("candidate_id") for candidate in approved_combined_merge_candidates
            ],
            "medium_seed_key": medium_seed.get("key"),
            "medium_update_keys": sorted(medium_updates.keys()),
            "combined_runtime_spec_count": len(combined_specs),
            "first_spec_update_hash": first_spec.get("update_hash"),
            "first_spec_candidate_source_proof": first_source_proof,
            "first_spec_target_band_refinement_proof": first_refinement_proof,
            "first_spec_exact_stop_proof": first_exact_stop_proof,
        },
        "contract_alignment": {
            "runtime_candidate_source": "APPROVED_COMBINED_MERGE_RULE",
            "reason": (
                "The page only supplies approved candidate updates; "
                "COMBINED_BENDING_SHEAR_FAIL remains responsible for ranking, "
                "selection, exhausted proof, and final family result."
            ),
        },
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    return payload


def _write_artifacts(payload: dict[str, Any], compile_result: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_rescue_seed_tier_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_rescue_seed_tier_{stamp}.md"
    json_path.write_text(_stable_json({"compile": compile_result, **payload}) + "\n", encoding="utf-8")

    checks = payload.get("checks") or {}
    check_lines = [
        f"- {name}: {'PASS' if passed else 'FAIL'}"
        for name, passed in sorted(checks.items())
    ]
    report = [
        "# Design Guide Active-Fail Rescue Seed Tier Snapshot",
        "",
        f"Result: `{payload.get('status')}`",
        "",
        "## Purpose",
        "Prove active combined failure with modest absolute actions but failing utilisation receives approved rescue seed candidates.",
        "",
        "## Key Result",
        f"- action tier: `{payload['case']['action_tier']}`",
        f"- overview tier: `{payload['case']['overview_tier']}`",
        f"- chosen tier: `{payload['case']['chosen_tier']}`",
        f"- seed order: `{payload['case']['seed_order']}`",
        "",
        "## Checks",
        *check_lines,
        "",
        "## Contract Alignment",
        payload["contract_alignment"]["reason"],
        "",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    compile_result = _run_compile(
        [
            "inputs_page.py",
            "tools/verification/design_guide_active_fail_rescue_seed_tier_snapshot.py",
            "design_brain/design_guide_controller.py",
        ]
    )
    payload = _build_snapshot()
    if not compile_result["passed"]:
        payload["status"] = "FAIL"
    json_path, report_path = _write_artifacts(payload, compile_result)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if payload["status"] == "PASS" and compile_result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
