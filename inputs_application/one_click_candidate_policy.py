"""Candidate evaluation and classification for the one-click transaction."""

from __future__ import annotations

import math
from collections.abc import Callable


def evaluate_auto_design_candidate(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    guidance_state_snapshot: Callable[[dict | None], dict],
    evaluate_candidate_full: Callable[..., dict | None],
) -> dict | None:
    candidate_state = guidance_state_snapshot(state)
    if updates:
        candidate_state.update(updates)
    return evaluate_candidate_full(
        candidate_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
    )


def candidate_failure_coverage_summary(
    current_state: dict,
    candidate: dict,
    *,
    collect_design_overview: Callable[..., dict],
) -> dict:
    current_overview = (
        collect_design_overview(current_state)
        if isinstance(current_state, dict)
        else {}
    )
    candidate_overview = (
        dict(candidate.get("overview") or {})
        if isinstance(candidate, dict)
        else {}
    )
    current_fail = sorted(
        key
        for key, value in (current_overview.get("statuses") or {}).items()
        if str(value or "").upper() == "FAIL"
    )
    candidate_fail = sorted(
        key
        for key, value in (candidate_overview.get("statuses") or {}).items()
        if str(value or "").upper() == "FAIL"
    )
    covered = sorted(
        key for key in current_fail if key not in candidate_fail
    )
    remaining = sorted(
        key for key in current_fail if key in candidate_fail
    )
    return {
        "current_fail_keys": list(current_fail),
        "candidate_fail_keys": list(candidate_fail),
        "covered_fail_keys": list(covered),
        "remaining_fail_keys": list(remaining),
        "covers_all_current_failures": (
            len(current_fail) > 0 and len(remaining) == 0
        ),
    }


def design_guide_candidate_family(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "none"
    action_type = str(item.get("action_type") or "")
    if action_type == "apply_compound_guidance":
        return "compound"
    if action_type in (
        "apply_geometry_recommendation",
        "increase_depth",
        "increase_width",
        "tighten_geometry",
    ):
        return "geometry"
    if action_type in (
        "apply_bottom_recommendation",
        "reduce_bottom_reinforcement",
        "reduce_bar_spacing",
    ):
        return "bottom_reo"
    if action_type in (
        "apply_shear_recommendation",
        "increase_link_spacing",
        "reduce_number_of_legs",
        "reduce_link_spacing",
    ):
        return "shear"
    if action_type == "apply_mode_recommendation":
        return "mode_guidance"
    check_key = str(item.get("check_key") or "")
    return check_key if check_key else "general"


def governing_focus_from_overview(overview: dict | None) -> str:
    utils = ((overview or {}).get("utils") or {})
    primary: list[tuple[str, float]] = []
    for key in ("bending", "shear"):
        try:
            value = float(utils.get(key))
        except (TypeError, ValueError):
            continue
        if not math.isnan(value):
            primary.append((key, value))
    if primary:
        primary.sort(key=lambda item: item[1], reverse=True)
        return primary[0][0]
    best_key = "general"
    best_util = -1.0
    for key in ("crack", "deflection"):
        try:
            value = float(utils.get(key))
        except (TypeError, ValueError):
            continue
        if math.isnan(value):
            continue
        if value > best_util:
            best_key = key
            best_util = value
    return best_key


def current_design_guide_fail_fingerprint(
    overview: dict | None,
    *,
    parse_util_value: Callable[[object], float | None],
) -> dict:
    source = dict(overview or {})
    statuses = dict(source.get("statuses") or {})
    utils = dict(source.get("utils") or {})
    fail_keys = sorted(
        str(key)
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    )
    return {
        "fail_keys": list(fail_keys),
        "shear_status": str(
            statuses.get("shear") or ""
        ).strip().upper(),
        "shear_util": parse_util_value(utils.get("shear")),
        "bending_status": str(
            statuses.get("bending") or ""
        ).strip().upper(),
        "bending_util": parse_util_value(utils.get("bending")),
    }


def one_click_candidate_is_shear_governing_for_prune(
    *,
    family_hint: str,
    norm_updates: dict | None,
    family_matches_governing_domain: Callable[[str, str], bool],
) -> bool:
    family = str(family_hint or "").strip().lower()
    if (
        "cleanup" in family
        or family.endswith("_cleanup")
        or family == "non_governing_cleanup"
    ):
        return False
    if family_matches_governing_domain(family_hint, "shear"):
        return True
    updates = dict(norm_updates or {})
    return any(
        key in updates for key in ("lig_d", "lig_legs", "s_lig")
    )


def rescue_mode_eval_for_result(
    result: dict | None,
    *,
    build_canonical_design_state_pack: Callable[[dict], dict],
    evaluate_candidate_full: Callable[..., dict | None],
) -> dict | None:
    preview = dict((result or {}).get("final_state_preview") or {})
    if not preview:
        return None
    try:
        return evaluate_candidate_full(
            build_canonical_design_state_pack(preview),
            source="rescue_mode_result_eval",
            label="Rescue result",
            action_type="rescue_mode",
            updates={},
        )
    except Exception:
        return None


def rescue_mode_validate_seed(
    base_state: dict,
    seed_updates: dict,
    *,
    guidance_state_snapshot: Callable[[dict | None], dict],
    overlay_current_normalized_shear_truth: Callable[[dict], dict],
    build_canonical_design_state_pack: Callable[[dict], dict],
    design_state_coherence_check: Callable[[dict], dict],
    canonical_pack_is_valid: Callable[[dict], bool],
    evaluate_candidate_full: Callable[..., dict | None],
) -> tuple[bool, str | None, dict]:
    trial_state = guidance_state_snapshot(dict(base_state or {}))
    trial_state.update(dict(seed_updates or {}))
    trial_pack = build_canonical_design_state_pack(
        overlay_current_normalized_shear_truth(trial_state)
    )
    coherence = design_state_coherence_check(trial_pack)
    if not canonical_pack_is_valid(trial_pack):
        return (
            False,
            str(
                trial_pack.get("canonical_pack_error")
                or "canonical_pack_invalid"
            ),
            trial_state,
        )
    if bool(coherence.get("coherence_should_block")):
        issues = list(
            coherence.get("coherence_blocking_issues") or []
        )
        return (
            False,
            str(
                issues[0]
                if issues
                else "state_incoherent_after_rebuild"
            ),
            trial_state,
        )
    try:
        evaluation = evaluate_candidate_full(
            trial_pack,
            source="rescue_mode_seed_validation",
            label="Rescue seed validation",
            action_type="rescue_seed_validation",
            updates={},
        )
    except Exception:
        evaluation = None
    if not isinstance(evaluation, dict):
        return False, "seed_evaluation_failed", trial_state
    return True, None, trial_state


def shear_preview_for_updates(
    state: dict,
    shear_updates: dict,
    *,
    guidance_state_snapshot: Callable[[dict | None], dict],
    build_shear_check_rows_from_state: Callable[[dict], dict],
) -> dict | None:
    preview_state = guidance_state_snapshot(state)
    preview_state.update(shear_updates)
    pack = build_shear_check_rows_from_state(preview_state)
    if not pack:
        return None
    web_util = float("inf")
    for row in pack.get("rows", []):
        if row.get("title") == "Web-crushing strength":
            try:
                web_util = float(row.get("util"))
            except Exception:
                web_util = float("inf")
            break
    try:
        util = float(pack.get("summary_util"))
    except Exception:
        util = float("inf")
    return {
        "util": util,
        "web_util": web_util,
        "phi_vu": float(
            pack.get(
                "summary_governing_capacity_kN",
                pack.get("summary_phiVu_kN", 0.0),
            )
            or 0.0
        ),
        "veq": float(
            pack.get(
                "summary_governing_demand_kN",
                pack.get("summary_Veq_kN", 0.0),
            )
            or 0.0
        ),
        "rows": pack.get("rows", []),
    }


__all__ = [
    "candidate_failure_coverage_summary",
    "current_design_guide_fail_fingerprint",
    "design_guide_candidate_family",
    "evaluate_auto_design_candidate",
    "governing_focus_from_overview",
    "one_click_candidate_is_shear_governing_for_prune",
    "rescue_mode_eval_for_result",
    "rescue_mode_validate_seed",
    "shear_preview_for_updates",
]
