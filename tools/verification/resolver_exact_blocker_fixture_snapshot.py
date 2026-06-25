"""Synthetic snapshot for the resolver non-empty exact-blocker proof lane.

This is branch-level proof only.  It does not claim that a product scenario can
discover an exact blocker; it proves that when the resolver is given a valid
non-empty exact blocker, the final active-action payload lane preserves it.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterator


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ARTIFACT_DIR = REPO / "artifacts" / "verification"


def _stable_hash(value: Any) -> str:
    try:
        payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        payload = repr(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _families(value: Any) -> list[str]:
    return sorted(str(key) for key in dict(value or {}).keys())


def _parse_util(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@contextmanager
def _patched(module: Any, replacements: dict[str, Any]) -> Iterator[None]:
    originals = {name: getattr(module, name) for name in replacements}
    try:
        for name, replacement in replacements.items():
            setattr(module, name, replacement)
        yield
    finally:
        for name, original in originals.items():
            setattr(module, name, original)


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 600.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 80.0,
        "uls_Vstar": 80.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }


def _overview_for(active_family: str) -> dict[str, Any]:
    statuses = {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"}
    statuses[active_family] = "FAIL"
    utils = {"bending": 0.91, "shear": 0.92, "crack": 0.0, "deflection": 0.0}
    utils[active_family] = 1.18
    return {
        "statuses": statuses,
        "utils": utils,
        "any_fail": True,
        "all_key_pass": False,
        "worst_util": 1.18,
    }


def _active_item_for(active_family: str) -> dict[str, Any]:
    updates = {"s_lig": 150} if active_family == "shear" else {"bot1_count": 5}
    return {
        "title_main": f"{active_family.title()} capacity is low",
        "title": f"{active_family.title()} capacity is low",
        "family": active_family,
        "check_key": active_family,
        "selected_action_family": active_family,
        "selected_family": active_family,
        "published_family_id": f"{active_family.upper()}_FAIL_SYNTHETIC",
        "apply_payload_family_id": active_family,
        "status": "ACTION",
        "bucket": "action",
        "guidance_intent": "required_fix",
        "action_type": "apply_resolved_candidate",
        "primary_card_actionable": True,
        "updates": dict(updates),
        "candidate_id": f"synthetic_{active_family}_repair",
        "source_candidate_id": f"synthetic_{active_family}_repair",
        "candidate_search_evidence": {"candidate_rows": [], "source": "synthetic_exact_blocker_fixture"},
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": active_family,
            "updates": dict(updates),
            "preview_pass": True,
            "blocking_reason": None,
            "candidate_id": f"synthetic_{active_family}_repair",
            "source_candidate_id": f"synthetic_{active_family}_repair",
            "expected_util": 0.74,
        },
        "action_payload": {"updates": dict(updates)},
        "resolved_candidate": {"updates": dict(updates), "family": active_family},
    }


def _dependencies(module: Any, *, active_family: str, replacement: bool):
    from design_brain.publication import DesignGuidePublicationDependencies

    def _exact_cleanup_blocker_for_outside_target_action(**kwargs: Any) -> dict[str, Any]:
        family = str(kwargs.get("family") or active_family)
        return {
            "family": family,
            "exact_blocker": True,
            "search_ran": True,
            "search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_ran": True,
            "target_band_search_exhaustive": True,
            "failed_check_name": f"final accepted {family} utilisation threshold",
            "failed_check_status": "below_final_accepted_threshold",
            "failed_check_util": kwargs.get("final_util"),
            "failed_check_capacity_or_limit": kwargs.get("target_low"),
            "current_util": kwargs.get("current_util"),
            "reason": f"Synthetic exact blocker proves {family} final-payload propagation.",
            "fallback_candidate_id": kwargs.get("fallback_candidate_id"),
            "source": kwargs.get("source"),
            "no_second_cta_required": bool(replacement),
        }

    def _post_click_low_bending_resolution_item(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
        if not replacement:
            return None
        exact = {
            active_family: {
                "family": active_family,
                "exact_blocker": True,
                "reason": "Synthetic post-click replacement blocker.",
                "no_second_cta_required": True,
            }
        }
        return {
            "title_main": "Further cleanup blocked",
            "title": "Further cleanup blocked",
            "family": active_family,
            "check_key": active_family,
            "guidance_intent": "specific_blocker",
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "blocking_reason": "Synthetic exact blocker prevents second CTA.",
                "updates": {},
            },
            "exact_blockers_by_family": dict(exact),
            "post_click_exact_blockers_by_family": dict(exact),
            "candidate_search_evidence": {
                "exact_blockers_by_family": dict(exact),
                "post_click_exact_blockers_by_family": dict(exact),
            },
        }

    null = lambda *args, **kwargs: None
    false = lambda *args, **kwargs: False
    identity_state = lambda state=None, *args, **kwargs: dict(state or {})
    overview = _overview_for(active_family)
    active_item = _active_item_for(active_family)

    return DesignGuidePublicationDependencies(
        active_fail_near_current_repair_item=lambda *args, **kwargs: copy.deepcopy(active_item),
        active_repair_with_residual_shear_target_cleanup=null,
        bending_fail_publication_snapshot_for_state=null,
        bending_only_target_band_cleanup_item=null,
        build_bending_check_rows_from_state=lambda *args, **kwargs: [],
        build_design_actions_context=lambda state=None, *args, **kwargs: {"state": dict(state or {})},
        build_shear_check_rows_from_state=lambda *args, **kwargs: [],
        collect_design_overview=lambda *args, **kwargs: dict(overview),
        combine_best_safe_shear_with_bending_cleanup_item=null,
        combined_low_util_exact_blocker_final_item=null,
        design_guide_apply_button_contracts_to_items=lambda items, *args, **kwargs: [
            copy.deepcopy(item) for item in list(items or [])
        ],
        design_guide_preview_contract_for_updates=lambda *args, **kwargs: (True, 0.74, None),
        design_mode_config=lambda *args, **kwargs: {"target_lo": 0.85, "target_hi": 1.0},
        design_optimisation_goal=lambda *args, **kwargs: "balanced",
        direct_target_band_guidance_item=lambda *args, **kwargs: copy.deepcopy(active_item),
        evaluate_auto_design_candidate=lambda *args, **kwargs: {"overview": dict(overview), "worst_util": 0.74},
        exact_cleanup_blocker_for_outside_target_action=_exact_cleanup_blocker_for_outside_target_action,
        float_from_state=lambda state, key, default=None: _parse_util(dict(state or {}).get(key)) or default,
        guidance_change_lines_for_updates=lambda state, updates: [f"{key}: {value}" for key, value in dict(updates or {}).items()],
        guidance_cleanup_candidate_id=lambda *args, **kwargs: f"synthetic_{active_family}_repair",
        guidance_compact_change_text=lambda lines: "; ".join(str(line) for line in list(lines or [])),
        guidance_default_alternatives_text=lambda *args, **kwargs: "Synthetic alternatives.",
        guidance_item_from_resolved_candidate=lambda candidate, *args, **kwargs: dict(candidate or {}),
        guidance_state_snapshot=identity_state,
        local_cleanup_post_apply_acceptance_matches=false,
        overview_active_failure_keys=lambda ov=None: {active_family},
        overview_required_checks_acceptable=false,
        parse_util_value=_parse_util,
        post_active_repair_residual_shear_exact_blocker=null,
        post_active_repair_target_accepted_item=null,
        post_click_accepted_green_audit=lambda *args, **kwargs: {},
        post_click_applied_residual_shear_exact_blocker=null,
        post_click_low_bending_resolution_item=_post_click_low_bending_resolution_item,
        probe_equivalent_bending_cleanup_action_item=null,
        resolve_design_actions_from_state=lambda *args, **kwargs: {},
        resolve_recommendation_updates=lambda item, *args, **kwargs: dict((item or {}).get("updates") or {}),
        resolved_inputs_summary_state=lambda: ({}, {}),
        shared_state_snapshot=lambda: {},
        shear_best_safe_cleanup_item_from_evidence=null,
        shear_cleanup_exact_blocker_guidance_item=null,
        shear_demands_negligible=false,
        shear_low_util_target_cleanup_item=null,
        suppress_design_guide_blocker_cta=false,
        updates_match_state=false,
        visible_cleanup_blocker_from_action=null,
    )


def _scenario(module: Any, *, name: str, active_family: str, replacement: bool) -> dict[str, Any]:
    from design_brain.publication import DesignGuidePublicationContext

    state = _base_state()
    overview = _overview_for(active_family)

    def _no_promote(*, active_item: dict, contract: dict, updates: dict, **kwargs: Any):
        return dict(active_item), dict(contract), dict(updates), False

    def _no_merge(*, active_item: dict, contract: dict, updates: dict, active_family: str, active_title: str, **kwargs: Any):
        return dict(active_item), dict(contract), dict(updates), active_family, active_title, None, None

    def _preview_truth(**kwargs: Any):
        return (
            f"synthetic_{active_family}_repair",
            0.74,
            {"bending": 0.91 if active_family != "bending" else 0.74, "shear": 0.92 if active_family != "shear" else 0.74},
            1.18,
        )

    replacements = {
        "_promote_safe_active_fail_repair_for_final_visible_item": _no_promote,
        "_merge_residual_cleanup_for_final_visible_active_action": _no_merge,
        "_resolve_final_visible_active_action_preview_truth": _preview_truth,
    }
    with _patched(module, replacements):
        result = module.resolve_final_visible_design_guide_item(
            state,
            overview,
            [],
            publication_context=DesignGuidePublicationContext(
                current_summary_state=dict(state),
                current_overview=dict(overview),
                resolved_inputs_summary=dict(state),
                final_seed_state=dict(state),
                guidance_state_snapshot=dict(state),
                current_design_overview=dict(overview),
                direct_failure_state=dict(state),
            ),
            publication_dependencies=_dependencies(module, active_family=active_family, replacement=replacement),
        )

    item = dict(result.get("item") or {})
    payload = dict(item.get("action_payload") or {})
    candidate = dict(item.get("resolved_candidate") or {})
    evidence = dict(item.get("candidate_search_evidence") or {})
    debug = dict(result.get("debug") or {})
    blocker_sources = {
        "item": dict(item.get("exact_blockers_by_family") or {}),
        "payload": dict(payload.get("exact_blockers_by_family") or {}),
        "resolved_candidate": dict(candidate.get("exact_blockers_by_family") or {}),
        "evidence": dict(evidence.get("exact_blockers_by_family") or {}),
        "debug": dict(debug.get("post_click_exact_blockers_by_family") or {}),
    }
    if replacement:
        required_sources = ("item", "debug")
    else:
        required_sources = ("item", "payload", "resolved_candidate", "evidence")
    missing = [source for source in required_sources if active_family not in blocker_sources[source]]
    status = "PASS" if not missing else "FAIL"
    return {
        "name": name,
        "status": status,
        "missing_sources": missing,
        "render_reason": result.get("render_reason"),
        "active_family": active_family,
        "replacement_expected": replacement,
        "item_identity_hash": _stable_hash(item),
        "action_payload_hash": _stable_hash(payload),
        "resolved_candidate_hash": _stable_hash(candidate),
        "exact_blocker_families_by_source": {
            key: _families(value) for key, value in blocker_sources.items()
        },
        "blocker_source_hashes": {key: _stable_hash(value) for key, value in blocker_sources.items()},
        "final_payload_carries_exact_blocker_proof": bool(active_family in blocker_sources["payload"]),
        "resolved_candidate_carries_exact_blocker_proof": bool(active_family in blocker_sources["resolved_candidate"]),
        "post_click_replacement_returned": result.get("render_reason")
        == "final_visible_post_click_active_action_exact_blocker",
        "final_item": {
            "title": item.get("title") or item.get("title_main"),
            "family": item.get("family"),
            "selected_action_family": item.get("selected_action_family"),
            "button_contract_enabled": bool(dict(item.get("button_contract") or {}).get("enabled")),
            "final_visible_resolver_reason": item.get("final_visible_resolver_reason"),
        },
    }


def main() -> int:
    import inputs_page as module

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    scenarios = [
        _scenario(module, name="shear_final_payload_exact_blocker", active_family="shear", replacement=False),
        _scenario(module, name="bending_post_click_replacement_exact_blocker", active_family="bending", replacement=True),
    ]
    status = "PASS" if all(scenario.get("status") == "PASS" for scenario in scenarios) else "FAIL"
    report = {
        "schema": "resolver_exact_blocker_fixture_snapshot.v1",
        "scope": "synthetic_branch_level_proof_not_product_path_discovery",
        "status": status,
        "scenarios": scenarios,
    }
    output = ARTIFACT_DIR / f"resolver_exact_blocker_fixture_snapshot_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
