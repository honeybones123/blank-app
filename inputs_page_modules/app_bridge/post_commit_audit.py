"""Post-commit audit coordination for Inputs one-click actions."""

from __future__ import annotations

import copy
from typing import Any


_POST_COMMIT_AUDIT_DEPENDENCIES: tuple[str, ...] = (
    "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
    "_accepted_green_cleanup_evidence_by_family",
    "_accepted_green_exact_blocker_is_valid",
    "_accepted_green_exact_blockers_by_family",
    "_bending_low_util_floor_exact_blocker",
    "_build_canonical_design_state_pack",
    "_collect_design_overview",
    "_final_accepted_meaningful_family_utils",
    "_governing_family_for_local_cleanup",
    "_guidance_state_snapshot",
    "_resolved_inputs_summary_state",
    "_shared_state_snapshot",
    "_shear_low_util_active_links_exact_blocker",
    "_shear_overprovision_floor_exact_blocker",
    "BEAM_STATUS_FAIL",
    "evaluate_candidate_full",
    "SHARED_DEFAULTS",
)


def bind_post_commit_audit_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _POST_COMMIT_AUDIT_DEPENDENCIES
            if name in namespace
        }
    )


def _one_click_commit_audit_passes(
    commit_audit: dict | None,
    *,
    partial_progress_commit: bool = False,
    best_effort_cleanup_commit: bool = False,
    pre_commit_worst_util: float | None = None,
    pre_commit_statuses: dict | None = None,
) -> tuple[bool, str]:
    """
    Conservative live gate after one-click writes to shared state.
    Returns (passes, reject_reason_code) for ``_one_click_post_commit_audit`` output.

    When ``partial_progress_commit`` is True (combined-domain underdesign hop that
    deliberately may not clear all FAIL statuses in one batch), require intended updates
    to match and util to improve vs pre-commit instead of util<=1.0 with all PASS.
    """
    if not isinstance(commit_audit, dict):
        return False, "post_commit_missing_validation"
    if not bool(commit_audit.get("post_commit_matches_intended_updates")):
        return False, "post_commit_mismatch"
    post_worst = commit_audit.get("post_commit_live_worst_util")
    if post_worst is None:
        return False, "post_commit_missing_validation"
    try:
        w = float(post_worst)
    except (TypeError, ValueError):
        return False, "post_commit_missing_validation"
    if (partial_progress_commit or best_effort_cleanup_commit) and pre_commit_worst_util is not None:
        try:
            pre_w = float(pre_commit_worst_util)
        except (TypeError, ValueError):
            return False, "post_commit_missing_validation"
        if w > pre_w - 0.01:
            return False, (
                "post_commit_no_util_improvement_best_effort_cleanup"
                if best_effort_cleanup_commit
                else "post_commit_no_util_improvement_partial_path"
            )
    elif w > 1.0 + 1e-9:
        return False, "post_commit_util_exceeds_limit"
    st = commit_audit.get("post_commit_live_statuses")
    if st is None:
        return False, "post_commit_missing_validation"
    if best_effort_cleanup_commit:
        if not isinstance(st, dict):
            return False, "post_commit_missing_validation"
        try:
            pre_fail_count = sum(
                1
                for v in dict(pre_commit_statuses or {}).values()
                if str(v).strip() == "FAIL" or v == BEAM_STATUS_FAIL
            )
            post_fail_count = sum(
                1
                for v in dict(st or {}).values()
                if str(v).strip() == "FAIL" or v == BEAM_STATUS_FAIL
            )
        except Exception:
            return False, "post_commit_missing_validation"
        if post_fail_count >= pre_fail_count:
            return False, "post_commit_no_fail_count_improvement_best_effort_cleanup"
        return True, ""
    if isinstance(st, dict) and not partial_progress_commit:
        for v in st.values():
            if str(v).strip() == "FAIL" or v == BEAM_STATUS_FAIL:
                return False, "post_commit_fail_status"
    return True, ""


def _post_click_accepted_green_audit(
    overview: dict | None,
    *,
    blocker_source: dict | None = None,
    state: dict | None = None,
    threshold: float | None = None,
    build_active_shear_blocker: bool = True,
) -> dict:
    if threshold is None:
        threshold = FINAL_ACCEPTED_MIN_FAMILY_UTIL
    family_utils, meaningful_utils, excluded_families = _final_accepted_meaningful_family_utils(overview)
    governing_family = _governing_family_for_local_cleanup(overview, family_utils)
    low_util_families = [
        family
        for family, util in sorted(meaningful_utils.items())
        if float(util) < float(threshold)
    ]
    exact_blockers = _accepted_green_exact_blockers_by_family(blocker_source)
    if "shear" in low_util_families and "shear" not in exact_blockers:
        shear_floor_blocker = _shear_overprovision_floor_exact_blocker(state, overview)
        if _accepted_green_exact_blocker_is_valid(shear_floor_blocker):
            exact_blockers["shear"] = dict(shear_floor_blocker)
    if (
        build_active_shear_blocker
        and "shear" in low_util_families
        and "shear" not in exact_blockers
    ):
        shear_active_blocker = _shear_low_util_active_links_exact_blocker(
            state,
            overview,
            threshold=threshold,
        )
        if _accepted_green_exact_blocker_is_valid(shear_active_blocker):
            exact_blockers["shear"] = dict(shear_active_blocker)
    if "bending" in low_util_families and "bending" not in exact_blockers:
        bending_floor_blocker = _bending_low_util_floor_exact_blocker(state, overview)
        if _accepted_green_exact_blocker_is_valid(bending_floor_blocker):
            exact_blockers["bending"] = dict(bending_floor_blocker)
    cleanup_evidence = _accepted_green_cleanup_evidence_by_family(blocker_source)
    unresolved = [
        family
        for family in low_util_families
        if family not in exact_blockers
    ]
    valid = not unresolved
    invalid_reason = (
        f"unresolved_meaningful_family_util_below_{float(threshold):.2f}:" + ",".join(unresolved)
        if unresolved
        else ""
    )
    return {
        "final_accepted_min_family_util": float(threshold),
        "post_click_family_utils": dict(family_utils),
        "post_click_family_utils_meaningful": dict(meaningful_utils),
        "post_click_families_below_final_threshold": list(low_util_families),
        "post_click_unresolved_low_util_families": list(unresolved),
        "post_click_excluded_families": dict(excluded_families),
        "post_click_materially_overprovided_families": list(low_util_families),
        "post_click_unresolved_overprovided_families": list(unresolved),
        "post_click_cleanup_evidence_by_family": dict(cleanup_evidence),
        "post_click_exact_blockers_by_family": dict(exact_blockers),
        "post_click_accepted_green_valid": bool(valid),
        "post_click_accepted_green_invalid_reason": invalid_reason,
        "post_click_materially_overprovided_threshold": float(threshold),
        "post_click_governing_family": governing_family,
    }


def _one_click_post_commit_audit_subset(intended: dict) -> dict:
    """
    Return the authoritative subset of final_updates that should be compared
    exactly against fresh shared state after commit.

    Purpose:
    - compare only raw committed input truth
    - ignore derived / resolved / rebuilt / diagnostic keys
    """
    if not isinstance(intended, dict):
        return {
            "audited_updates": {},
            "ignored_keys": [],
            "has_row_model_updates": False,
            "ignored_row_model_legacy_mirror_keys": [],
        }

    DERIVED_OR_REBUILT_KEYS = {
        "d",
        "do",
        "Ast_bot",
        "Ast_top",
        "nb_bot",
        "nb_top",
        "db_bot",
        "db_top",
        "bot_rows_resolved",
        "top_rows_resolved",
        "bot_bar_coords",
        "top_bar_coords",
        "resolved_longitudinal_bars",
        "resolved_longitudinal_warnings",
        "Ast_top_web",
        "Ast_top_flange",
        "Ast_bottom_web",
        "Ast_bottom_flange",
        "total_bot_bars",
        "total_top_bars",
        "A_g",
        "ybar_top_g",
        "Ixx_g",
        "Ztop_g",
        "Zbot_g",
        "b_web",
        "b_crack",
        "A_ct_default",
        "Ec",
        "Eceff",
        "defl_bw",
        "canonical_pack_built",
        "canonical_pack_valid",
        "canonical_pack_source",
        "canonical_pack_error",
        "canonical_pack_error_stage",
        "longitudinal_reo_truth_source",
        "row_model_legacy_sync_applied",
        "row_model_legacy_sync_diff_keys",
    }
    ROW_MODEL_LEGACY_MIRROR_KEYS = {
        "bot1_count",
        "bot2_count",
        "top1_count",
        "top2_count",
        "nb_bot",
        "nb_top",
        "db_bot_1",
        "db_bot_2",
        "db_top_1",
        "db_top_2",
        "db_bot",
        "db_top",
        "bot_entry",
        "top_entry",
        "s_bot",
        "s_top",
        "total_bot_bars",
        "total_top_bars",
        "Ast_bot",
        "Ast_top",
    }
    row_model_prefixes = (
        "bot_row_",
        "top_row_",
    )
    has_row_model_updates = any(str(k).startswith(row_model_prefixes) for k in intended.keys())

    audited: dict[str, object] = {}
    ignored: list[str] = []

    for key, value in intended.items():
        k = str(key or "")
        if not k:
            continue
        if k.startswith("_"):
            ignored.append(k)
            continue
        if k not in SHARED_DEFAULTS:
            ignored.append(k)
            continue
        if k in DERIVED_OR_REBUILT_KEYS:
            ignored.append(k)
            continue
        if has_row_model_updates and k in ROW_MODEL_LEGACY_MIRROR_KEYS:
            ignored.append(k)
            continue
        audited[k] = value

    ignored_row_model_legacy_mirror_keys = sorted(
        [k for k in ignored if k in ROW_MODEL_LEGACY_MIRROR_KEYS]
    )
    return {
        "audited_updates": audited,
        "ignored_keys": sorted(set(ignored)),
        "has_row_model_updates": bool(has_row_model_updates),
        "ignored_row_model_legacy_mirror_keys": ignored_row_model_legacy_mirror_keys,
    }


def _one_click_post_commit_audit(intended: dict) -> dict:
    """Fresh shared snapshot vs intended updates (authoritative subset only), plus live worst util from evaluation."""
    subset_meta = _one_click_post_commit_audit_subset(intended)
    audited_updates = dict(subset_meta.get("audited_updates") or {})
    ignored_keys = list(subset_meta.get("ignored_keys") or [])
    has_row_model_updates = bool(subset_meta.get("has_row_model_updates"))
    ignored_row_model_legacy_mirror_keys = list(subset_meta.get("ignored_row_model_legacy_mirror_keys") or [])
    snap = _shared_state_snapshot()
    subset = {k: snap.get(k) for k in audited_updates.keys()}
    mismatch_keys: list[str] = []
    mismatch_details: dict[str, dict] = {}
    for k, intended_val in audited_updates.items():
        live = snap.get(k)
        mismatch = False
        if isinstance(intended_val, float) or isinstance(live, float):
            try:
                mismatch = abs(float(live) - float(intended_val)) > 1e-9
            except (TypeError, ValueError):
                mismatch = live != intended_val
        else:
            mismatch = live != intended_val
        if mismatch:
            mismatch_keys.append(k)
            mismatch_details[k] = {
                "intended": intended_val,
                "live": live,
            }
    post_worst: float | None = None
    post_statuses: dict | None = None
    post_eval_shared_worst: float | None = None
    post_eval_shared_statuses: dict | None = None
    post_eval_shared_packed_worst: float | None = None
    post_eval_shared_packed_statuses: dict | None = None
    post_eval_summary_worst: float | None = None
    post_eval_summary_statuses: dict | None = None
    post_summary_state_subset: dict | None = None
    try:
        summary_state, _ = _resolved_inputs_summary_state()
        post_summary_state_subset = {
            "b": summary_state.get("b"),
            "D": summary_state.get("D"),
            "bot1_count": summary_state.get("bot1_count"),
            "bot2_count": summary_state.get("bot2_count"),
            "db_bot_1": summary_state.get("db_bot_1"),
            "db_bot_2": summary_state.get("db_bot_2"),
            "lig_d": summary_state.get("lig_d"),
            "lig_legs": summary_state.get("lig_legs"),
            "s_lig": summary_state.get("s_lig"),
            "Ast_bot": summary_state.get("Ast_bot"),
            "d": summary_state.get("d"),
            "Mu_star": summary_state.get("Mu_star"),
            "Vu_star": summary_state.get("Vu_star"),
        }
        overview = _collect_design_overview(dict(summary_state or {}))
        post_worst = float((overview.get("worst_util") or 0.0))
        post_statuses = dict((overview.get("statuses") or {}))
        shared_eval = evaluate_candidate_full(
            _guidance_state_snapshot(snap),
            source="one_click_post_commit_audit_shared_eval",
            label="Post-commit shared eval",
            action_type="one_click",
            updates={},
        )
        if isinstance(shared_eval, dict):
            shared_overview = dict(shared_eval.get("overview") or {})
            post_eval_shared_worst = float(shared_overview.get("worst_util", 0.0) or 0.0)
            post_eval_shared_statuses = dict(shared_overview.get("statuses") or {})
        shared_packed_eval = evaluate_candidate_full(
            _build_canonical_design_state_pack(copy.deepcopy(snap)),
            source="one_click_post_commit_audit_shared_packed_eval",
            label="Post-commit shared packed eval",
            action_type="one_click",
            updates={},
        )
        if isinstance(shared_packed_eval, dict):
            shared_packed_overview = dict(shared_packed_eval.get("overview") or {})
            post_eval_shared_packed_worst = float(shared_packed_overview.get("worst_util", 0.0) or 0.0)
            post_eval_shared_packed_statuses = dict(shared_packed_overview.get("statuses") or {})
        summary_eval = evaluate_candidate_full(
            _guidance_state_snapshot(summary_state),
            source="one_click_post_commit_audit_summary_eval",
            label="Post-commit summary eval",
            action_type="one_click",
            updates={},
        )
        if isinstance(summary_eval, dict):
            summary_overview = dict(summary_eval.get("overview") or {})
            post_eval_summary_worst = float(summary_overview.get("worst_util", 0.0) or 0.0)
            post_eval_summary_statuses = dict(summary_overview.get("statuses") or {})
    except Exception:
        try:
            ev = evaluate_candidate_full(
                _guidance_state_snapshot(snap),
                source="one_click_post_commit_audit",
                label="Post-commit",
                action_type="one_click",
                updates={},
            )
            if isinstance(ev, dict):
                post_worst = float((ev.get("overview") or {}).get("worst_util", 0.0) or 0.0)
                post_statuses = dict((ev.get("overview") or {}).get("statuses") or {})
        except Exception:
            post_worst = None
            post_statuses = None
    return {
        "applied_final_updates": dict(intended),
        "audited_commit_updates": dict(audited_updates),
        "ignored_commit_update_keys": list(ignored_keys),
        "has_row_model_updates": has_row_model_updates,
        "ignored_row_model_legacy_mirror_keys": ignored_row_model_legacy_mirror_keys,
        "post_commit_shared_subset": subset,
        "post_commit_matches_intended_updates": bool(not mismatch_keys),
        "post_commit_mismatch_keys": list(mismatch_keys),
        "post_commit_mismatch_details": dict(mismatch_details),
        "post_commit_live_worst_util": post_worst,
        "post_commit_live_statuses": post_statuses,
        "post_commit_eval_shared_worst_util": post_eval_shared_worst,
        "post_commit_eval_shared_statuses": post_eval_shared_statuses,
        "post_commit_eval_shared_packed_worst_util": post_eval_shared_packed_worst,
        "post_commit_eval_shared_packed_statuses": post_eval_shared_packed_statuses,
        "post_commit_eval_summary_worst_util": post_eval_summary_worst,
        "post_commit_eval_summary_statuses": post_eval_summary_statuses,
        "post_commit_summary_state_subset": post_summary_state_subset,
    }
