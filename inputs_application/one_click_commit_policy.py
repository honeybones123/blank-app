"""Post-commit acceptance policy for the one-click transaction."""

from __future__ import annotations

from collections.abc import Callable

def one_click_commit_audit_passes(
    commit_audit: dict | None,
    *,
    partial_progress_commit: bool = False,
    best_effort_cleanup_commit: bool = False,
    pre_commit_worst_util: float | None = None,
    pre_commit_statuses: dict | None = None,
    fail_status: str,
) -> tuple[bool, str]:
    if not isinstance(commit_audit, dict):
        return False, "post_commit_missing_validation"
    if not bool(commit_audit.get("post_commit_matches_intended_updates")):
        return False, "post_commit_mismatch"
    post_worst = commit_audit.get("post_commit_live_worst_util")
    if post_worst is None:
        return False, "post_commit_missing_validation"
    try:
        worst = float(post_worst)
    except (TypeError, ValueError):
        return False, "post_commit_missing_validation"
    if (
        partial_progress_commit or best_effort_cleanup_commit
    ) and pre_commit_worst_util is not None:
        try:
            pre_worst = float(pre_commit_worst_util)
        except (TypeError, ValueError):
            return False, "post_commit_missing_validation"
        if worst > pre_worst - 0.01:
            return False, (
                "post_commit_no_util_improvement_best_effort_cleanup"
                if best_effort_cleanup_commit
                else "post_commit_no_util_improvement_partial_path"
            )
    elif worst > 1.0 + 1e-9:
        return False, "post_commit_util_exceeds_limit"
    statuses = commit_audit.get("post_commit_live_statuses")
    if statuses is None:
        return False, "post_commit_missing_validation"
    if best_effort_cleanup_commit:
        if not isinstance(statuses, dict):
            return False, "post_commit_missing_validation"
        try:
            pre_fail_count = sum(
                1
                for value in dict(pre_commit_statuses or {}).values()
                if str(value).strip() == "FAIL" or value == fail_status
            )
            post_fail_count = sum(
                1
                for value in dict(statuses or {}).values()
                if str(value).strip() == "FAIL" or value == fail_status
            )
        except Exception:
            return False, "post_commit_missing_validation"
        if post_fail_count >= pre_fail_count:
            return (
                False,
                "post_commit_no_fail_count_improvement_best_effort_cleanup",
            )
        return True, ""
    if isinstance(statuses, dict) and not partial_progress_commit:
        for value in statuses.values():
            if str(value).strip() == "FAIL" or value == fail_status:
                return False, "post_commit_fail_status"
    return True, ""


def one_click_committable_candidate_eval(
    base_state: dict,
    updates: dict | None,
    *,
    source: str,
    label: str | None,
    action_type: str | None,
    sanitize_shared_update_bundle: Callable[..., tuple[dict, dict]],
    guidance_state_snapshot: Callable[[dict | None], dict],
    normalise_invalid_shear_state_updates: Callable[..., dict],
    canonical_convenience_fields_from_state: Callable[[dict], dict],
    canonical_convenience_meta_key: str,
    evaluate_auto_design_candidate: Callable[..., dict | None],
) -> tuple[dict | None, dict, dict]:
    sanitized_updates, sanitize_meta = sanitize_shared_update_bundle(
        updates,
        source=source,
    )
    if not sanitized_updates:
        return None, sanitized_updates, sanitize_meta
    committed_state = guidance_state_snapshot(dict(base_state or {}))
    committed_state.update(dict(sanitized_updates))
    try:
        committed_state.update(
            normalise_invalid_shear_state_updates(
                committed_state,
                {},
                source=f"{source}:preview_normalise",
            )
        )
    except Exception:
        pass
    try:
        convenience_updates = dict(
            canonical_convenience_fields_from_state(committed_state)
            or {}
        )
        convenience_meta = dict(
            convenience_updates.pop(
                canonical_convenience_meta_key,
                {},
            )
            or {}
        )
        if bool(
            convenience_meta.get(
                "canonical_convenience_resync_valid"
            )
        ):
            committed_state.update(convenience_updates)
    except Exception:
        pass
    try:
        evaluation = evaluate_auto_design_candidate(
            committed_state,
            updates={},
            source=source,
            label=label,
            action_type=action_type,
        )
    except Exception:
        evaluation = None
    return evaluation, sanitized_updates, sanitize_meta


def _post_commit_audit_subset(
    intended: dict,
    *,
    shared_defaults: dict,
) -> dict:
    if not isinstance(intended, dict):
        return {
            "audited_updates": {},
            "ignored_keys": [],
            "has_row_model_updates": False,
            "ignored_row_model_legacy_mirror_keys": [],
        }
    derived = {
        "d", "do", "Ast_bot", "Ast_top", "nb_bot", "nb_top",
        "db_bot", "db_top", "bot_rows_resolved", "top_rows_resolved",
        "bot_bar_coords", "top_bar_coords", "resolved_longitudinal_bars",
        "resolved_longitudinal_warnings", "Ast_top_web", "Ast_top_flange",
        "Ast_bottom_web", "Ast_bottom_flange", "total_bot_bars",
        "total_top_bars", "A_g", "ybar_top_g", "Ixx_g", "Ztop_g",
        "Zbot_g", "b_web", "b_crack", "A_ct_default", "Ec", "Eceff",
        "defl_bw", "canonical_pack_built", "canonical_pack_valid",
        "canonical_pack_source", "canonical_pack_error",
        "canonical_pack_error_stage", "longitudinal_reo_truth_source",
        "row_model_legacy_sync_applied", "row_model_legacy_sync_diff_keys",
    }
    row_mirrors = {
        "bot1_count", "bot2_count", "top1_count", "top2_count",
        "nb_bot", "nb_top", "db_bot_1", "db_bot_2", "db_top_1",
        "db_top_2", "db_bot", "db_top", "bot_entry", "top_entry",
        "s_bot", "s_top", "total_bot_bars", "total_top_bars",
        "Ast_bot", "Ast_top",
    }
    has_rows = any(
        str(key).startswith(("bot_row_", "top_row_"))
        for key in intended
    )
    audited: dict = {}
    ignored: list[str] = []
    for key, value in intended.items():
        normalized = str(key or "")
        if (
            not normalized
            or normalized.startswith("_")
            or normalized not in shared_defaults
            or normalized in derived
            or (has_rows and normalized in row_mirrors)
        ):
            if normalized:
                ignored.append(normalized)
            continue
        audited[normalized] = value
    return {
        "audited_updates": audited,
        "ignored_keys": sorted(set(ignored)),
        "has_row_model_updates": has_rows,
        "ignored_row_model_legacy_mirror_keys": sorted(
            key for key in ignored if key in row_mirrors
        ),
    }


def one_click_post_commit_audit(
    intended: dict,
    *,
    shared_defaults: dict,
    shared_state_snapshot: Callable[[], dict],
    guidance_state_snapshot: Callable[[dict | None], dict],
    build_canonical_design_state_pack: Callable[[dict], dict],
    collect_design_overview: Callable[..., dict],
    evaluate_candidate_full: Callable[..., dict | None],
    resolve_summary_state: Callable[[], dict],
) -> dict:
    meta = _post_commit_audit_subset(
        intended,
        shared_defaults=shared_defaults,
    )
    audited = dict(meta["audited_updates"])
    ignored = list(meta["ignored_keys"])
    snapshot = shared_state_snapshot()
    subset = {key: snapshot.get(key) for key in audited}
    mismatch_keys: list[str] = []
    mismatch_details: dict[str, dict] = {}
    for key, intended_value in audited.items():
        live = snapshot.get(key)
        if isinstance(intended_value, float) or isinstance(live, float):
            try:
                mismatch = abs(float(live) - float(intended_value)) > 1e-9
            except (TypeError, ValueError):
                mismatch = live != intended_value
        else:
            mismatch = live != intended_value
        if mismatch:
            mismatch_keys.append(key)
            mismatch_details[key] = {
                "intended": intended_value,
                "live": live,
            }
    post_worst = post_statuses = None
    shared_worst = shared_statuses = None
    packed_worst = packed_statuses = None
    summary_worst = summary_statuses = None
    summary_subset = None
    try:
        summary_state = resolve_summary_state()
        summary_subset = {
            key: summary_state.get(key)
            for key in (
                "b", "D", "bot1_count", "bot2_count", "db_bot_1",
                "db_bot_2", "lig_d", "lig_legs", "s_lig", "Ast_bot",
                "d", "Mu_star", "Vu_star",
            )
        }
        overview = collect_design_overview(dict(summary_state or {}))
        post_worst = float(overview.get("worst_util") or 0.0)
        post_statuses = dict(overview.get("statuses") or {})
        shared_eval = evaluate_candidate_full(
            guidance_state_snapshot(snapshot),
            source="one_click_post_commit_audit_shared_eval",
            label="Post-commit shared eval",
            action_type="one_click",
            updates={},
        )
        if isinstance(shared_eval, dict):
            shared_overview = dict(shared_eval.get("overview") or {})
            shared_worst = float(shared_overview.get("worst_util", 0.0) or 0.0)
            shared_statuses = dict(shared_overview.get("statuses") or {})
        packed_eval = evaluate_candidate_full(
            build_canonical_design_state_pack(dict(snapshot)),
            source="one_click_post_commit_audit_shared_packed_eval",
            label="Post-commit shared packed eval",
            action_type="one_click",
            updates={},
        )
        if isinstance(packed_eval, dict):
            packed_overview = dict(packed_eval.get("overview") or {})
            packed_worst = float(packed_overview.get("worst_util", 0.0) or 0.0)
            packed_statuses = dict(packed_overview.get("statuses") or {})
            # Audit the committed shared snapshot.  The summary surface is
            # rerun-owned and can legitimately still expose pre-commit state.
            post_worst = packed_worst
            post_statuses = dict(packed_statuses)
        summary_eval = evaluate_candidate_full(
            guidance_state_snapshot(summary_state),
            source="one_click_post_commit_audit_summary_eval",
            label="Post-commit summary eval",
            action_type="one_click",
            updates={},
        )
        if isinstance(summary_eval, dict):
            summary_overview = dict(summary_eval.get("overview") or {})
            summary_worst = float(summary_overview.get("worst_util", 0.0) or 0.0)
            summary_statuses = dict(summary_overview.get("statuses") or {})
    except Exception:
        try:
            evaluation = evaluate_candidate_full(
                guidance_state_snapshot(snapshot),
                source="one_click_post_commit_audit",
                label="Post-commit",
                action_type="one_click",
                updates={},
            )
            if isinstance(evaluation, dict):
                overview = evaluation.get("overview") or {}
                post_worst = float(overview.get("worst_util", 0.0) or 0.0)
                post_statuses = dict(overview.get("statuses") or {})
        except Exception:
            post_worst = post_statuses = None
    return {
        "applied_final_updates": dict(intended),
        "audited_commit_updates": audited,
        "ignored_commit_update_keys": ignored,
        "has_row_model_updates": bool(meta["has_row_model_updates"]),
        "ignored_row_model_legacy_mirror_keys": list(
            meta["ignored_row_model_legacy_mirror_keys"]
        ),
        "post_commit_shared_subset": subset,
        "post_commit_matches_intended_updates": not mismatch_keys,
        "post_commit_mismatch_keys": mismatch_keys,
        "post_commit_mismatch_details": mismatch_details,
        "post_commit_live_worst_util": post_worst,
        "post_commit_live_statuses": post_statuses,
        "post_commit_eval_shared_worst_util": shared_worst,
        "post_commit_eval_shared_statuses": shared_statuses,
        "post_commit_eval_shared_packed_worst_util": packed_worst,
        "post_commit_eval_shared_packed_statuses": packed_statuses,
        "post_commit_eval_summary_worst_util": summary_worst,
        "post_commit_eval_summary_statuses": summary_statuses,
        "post_commit_summary_state_subset": summary_subset,
    }


__all__ = [
    "one_click_commit_audit_passes",
    "one_click_committable_candidate_eval",
    "one_click_post_commit_audit",
]
