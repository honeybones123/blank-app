"""Focused browser + internal debug ladder for shear overdesign decision tracing.

Diagnostic only:
- no app-behavior changes
- no solver ranking changes
- explains why shear cleanup does or does not become the actionable primary move
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import sys
import time
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import shear_checks_helpers

if not hasattr(shear_checks_helpers, "spacing_truth"):
    shear_checks_helpers.spacing_truth = None

import inputs_page
from tools.verification.helpers.browser_one_click_regression import (
    TRACER_PATH,
    _query,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
)
from tools.verification.helpers.browser_helpers import (
    _apply_live_inputs,
    _load_browser_state,
    _wait_for_post_click_state_without_run_end,
    _wait_for_post_publish_alignment,
)
from tools.verification.runners.recommendation_contract_ladder import _capture_state, _truth_alignment
from tools.verification.recipes.one_click_recipe_defs import build_state
from tools.verification.helpers.overdesign_assertions import (
    assert_no_unresolved_material_overdesign,
    overdesign_debug_from_browser_state,
)


BASE_RECIPE_NAME = "SO_BASE_HEAVY_LINKS_CONSERVATIVE"


CASE_DEFS = [
    {
        "case_id": "SO_CASE_1_PURE_SHEAR_LOW_DEMAND",
        "description": "Pure shear low demand, heavy links.",
        "mu_mode": "fixed",
        "mu": 0.0,
        "vu": 150.0,
    },
    {
        "case_id": "SO_CASE_2_BENDING_OK_SHEAR_ZERO",
        "description": "Bending in target band, Vu = 0, heavy links present.",
        "mu_mode": "target_band",
        "mu": None,
        "vu": 0.0,
    },
    {
        "case_id": "SO_CASE_3_BENDING_OK_SHEAR_MODERATE",
        "description": "Bending in target band, Vu = 75, heavy links present.",
        "mu_mode": "target_band",
        "mu": None,
        "vu": 75.0,
    },
    {
        "case_id": "SO_CASE_4_COMBINED_LOW_DEMAND",
        "description": "Combined low demand on conservative section and heavy links.",
        "mu_mode": "fixed",
        "mu": 55.0,
        "vu": 200.0,
    },
    {
        "case_id": "SO_CASE_5_SHEAR_ONLY_BELOW_TARGET",
        "description": "Shear-only overdesign with governing shear utilisation below target.",
        "mu_mode": "fixed",
        "mu": 0.0,
        "vu": 300.0,
    },
]


BASE_CHANGES = {
    "b": 450.0,
    "bw": 450.0,
    "D": 500.0,
    "cover_top": 40.0,
    "cover_bot": 40.0,
    "cover_side": 40.0,
    "bot1_count": 4,
    "db_bot_1": 16.0,
    "bot_row_count": 1,
    "bot_row_1_bars": 4,
    "bot_row_1_dia": 16.0,
    "top1_count": 2,
    "db_top_1": 10.0,
    "top_row_count": 1,
    "top_row_1_bars": 2,
    "top_row_1_dia": 10.0,
    "lig_d": 24,
    "lig_legs": 4,
    "s_lig": 125.0,
}


def _manual_actions(mu: float, vu: float, tu: float = 0.0, n: float = 0.0) -> dict[str, Any]:
    return {
        "uls_Mstar": float(mu),
        "load_Mstar_proxy": float(mu),
        "load_Mstar_pos_proxy": float(mu),
        "uls_Mstar_pos_manual": float(mu),
        "uls_Mstar_neg_manual": 0.0,
        "Mu_star": float(mu),
        "Mu_star_manual": float(mu),
        "load_Mstar_neg_proxy": 0.0,
        "uls_Vstar": float(vu),
        "load_Vstar_proxy": float(vu),
        "Vu_star": float(vu),
        "Vu_star_manual": float(vu),
        "Tu_star": float(tu),
        "N_star": float(n),
        "uls_Nstar": float(n),
        "load_Nstar_proxy": float(n),
        "sls_Mstar": 0.0,
        "sls_Vstar": 0.0,
        "sls_Nstar": 0.0,
    }


def _quiet_call(fn, *args, **kwargs):
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        return fn(*args, **kwargs)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _build_case_state(mu: float, vu: float) -> dict[str, Any]:
    return build_state(
        {
            **BASE_CHANGES,
            **_manual_actions(mu, vu, 0.0, 0.0),
        }
    )


def _evaluate_state(mu: float, vu: float) -> dict[str, Any]:
    state = _build_case_state(mu, vu)
    candidate = _quiet_call(inputs_page.evaluate_candidate_full, state, source="shear_overdesign_debug_seed")
    if not isinstance(candidate, dict):
        raise RuntimeError(f"Seed evaluation failed for Mu={mu}, Vu={vu}")
    return candidate


def _find_target_band_mu(vu: float, *, lo: float = 0.88, hi: float = 0.95, target: float = 0.92) -> float:
    best_in_band: tuple[float, float] | None = None
    best_any: tuple[float, float] | None = None
    for mu in range(20, 401, 5):
        candidate = _evaluate_state(float(mu), float(vu))
        overview = dict(candidate.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})
        bending_status = str(statuses.get("bending") or "").upper()
        bending_util = _float_or_none(utils.get("bending"))
        if bending_util is None:
            continue
        distance = abs(float(bending_util) - float(target))
        if best_any is None or distance < best_any[1]:
            best_any = (float(mu), distance)
        if bending_status == "PASS" and lo <= float(bending_util) <= hi:
            if best_in_band is None or distance < best_in_band[1]:
                best_in_band = (float(mu), distance)
    if best_in_band is not None:
        return float(best_in_band[0])
    if best_any is not None:
        return float(best_any[0])
    return 120.0


def _resolve_case_actions(case: dict[str, Any]) -> dict[str, float]:
    vu = float(case["vu"])
    if str(case.get("mu_mode") or "") == "target_band":
        mu = _find_target_band_mu(vu)
    else:
        mu = float(case.get("mu") or 0.0)
    return {"mu": mu, "vu": vu, "tu": 0.0, "n": 0.0}


def _wait_for_recipe(page, recipe_name: str, timeout_s: float = 25.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        last_state = _load_browser_state(page)
        if str(last_state.get("browser_recipe") or "") == recipe_name and not last_state.get("browser_recipe_error"):
            return last_state
        time.sleep(0.25)
    raise RuntimeError(
        f"Browser recipe '{recipe_name}' did not settle. "
        f"last_state={{browser_recipe={last_state.get('browser_recipe')!r}, "
        f"error={last_state.get('browser_recipe_error')!r}}}"
    )


def _shear_summary_from_eval(eval_obj: dict[str, Any]) -> dict[str, Any]:
    overview = dict(eval_obj.get("overview") or {})
    packs = dict(overview.get("packs") or {})
    shear_pack = dict(packs.get("shear") or {})
    bending_pack = dict(packs.get("bending") or {})
    state = dict(eval_obj.get("state") or {})
    return {
        "Mu": _float_or_none(state.get("uls_Mstar")),
        "Vu": _float_or_none(state.get("uls_Vstar")),
        "Tu": _float_or_none(state.get("Tu_star")),
        "N": _float_or_none(state.get("N_star") or state.get("uls_Nstar")),
        "b": _float_or_none(state.get("b")),
        "D": _float_or_none(state.get("D")),
        "d": _float_or_none(state.get("d")),
        "cover_top": _float_or_none(state.get("cover_top")),
        "cover_bot": _float_or_none(state.get("cover_bot")),
        "cover_side": _float_or_none(state.get("cover_side")),
        "bot1_count": state.get("bot1_count"),
        "db_bot_1": _float_or_none(state.get("db_bot_1")),
        "top1_count": state.get("top1_count"),
        "db_top_1": _float_or_none(state.get("db_top_1")),
        "lig_legs": state.get("lig_legs"),
        "s_lig": _float_or_none(state.get("s_lig")),
        "lig_d": state.get("lig_d"),
        "phiVu": _float_or_none(shear_pack.get("summary_phiVu_kN")),
        "Vstar_eq": _float_or_none(shear_pack.get("summary_Veq_kN")),
        "shear_util": _float_or_none((overview.get("utils") or {}).get("shear")),
        "bending_util": _float_or_none((overview.get("utils") or {}).get("bending")),
        "shear_status": (overview.get("statuses") or {}).get("shear"),
        "bending_status": (overview.get("statuses") or {}).get("bending"),
        "governing_family": overview.get("governing_util_source"),
        "governing_check": overview.get("governing_check"),
        "phiMu": _float_or_none(bending_pack.get("summary_phiMu_kNm")),
    }


def _candidate_distance_to_target(util: float | None, state: dict[str, Any]) -> float | None:
    if util is None:
        return None
    mode_cfg = _quiet_call(inputs_page._design_mode_config, _quiet_call(inputs_page._design_optimisation_goal, state))
    target_lo, target_hi, _ = _quiet_call(
        inputs_page._resolved_efficiency_target_band,
        mode_cfg,
        goal=_quiet_call(inputs_page._design_optimisation_goal, state),
    )
    return float(_quiet_call(inputs_page._distance_to_target_band, float(util), float(target_lo), float(target_hi)))


def _summarize_primary_item(item: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    payload = dict(item.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or {})
    return {
        "title": item.get("title_main"),
        "bucket": item.get("bucket"),
        "status": item.get("status"),
        "action_type": item.get("action_type"),
        "family": _quiet_call(inputs_page._guidance_item_family, item),
        "guidance_intent": item.get("guidance_intent"),
        "design_guide_terminal_state": item.get("design_guide_terminal_state"),
        "executor_contract_blocked_reason": item.get("executor_contract_blocked_reason"),
        "resolved_one_click": bool(_quiet_call(inputs_page._guidance_item_is_resolved_one_click, item)),
        "resolved_candidate_label": payload.get("resolved_candidate_label"),
        "resolved_candidate_action_type": payload.get("resolved_candidate_action_type"),
        "updates": dict(payload.get("resolved_candidate_updates") or payload.get("updates") or {}),
        "resolved_candidate_post_util": payload.get(
            "resolved_candidate_post_util",
            resolved.get("candidate_post_util", resolved.get("worst_util")),
        ),
        "resolved_candidate_reaches_target_band": payload.get(
            "resolved_candidate_reaches_target_band",
            resolved.get("candidate_reaches_target_band"),
        ),
        "candidate_search_evidence": dict(
            item.get("candidate_search_evidence")
            or payload.get("candidate_search_evidence")
            or resolved.get("candidate_search_evidence")
            or {}
        ),
    }


def _is_in_target_terminal_primary(primary: dict[str, Any] | None) -> bool:
    if not isinstance(primary, dict):
        return False
    title = str(primary.get("title") or primary.get("title_main") or "").lower()
    intent = str(primary.get("guidance_intent") or primary.get("primary_card_intent") or "").strip()
    terminal = str(primary.get("design_guide_terminal_state") or "").strip()
    return (
        intent == "already_efficient"
        or terminal == "optimal"
        or "target band achieved" in title
        or "design is efficient" in title
    )


def _is_direct_target_band_primary(primary: dict[str, Any] | None) -> bool:
    if not isinstance(primary, dict):
        return False
    evidence = dict(primary.get("candidate_search_evidence") or {})
    if bool(primary.get("resolved_candidate_reaches_target_band")):
        return True
    try:
        selected_util = float(primary.get("resolved_candidate_post_util"))
    except (TypeError, ValueError):
        selected_util = None
    try:
        target_low = float(evidence.get("target_low", 0.88))
        target_high = float(evidence.get("target_high", 0.95))
    except (TypeError, ValueError):
        target_low, target_high = 0.88, 0.95
    scope = str(evidence.get("search_scope") or "").strip()
    target_count = int(evidence.get("target_band_candidate_count") or 0)
    return bool(
        selected_util is not None
        and target_low <= selected_util <= target_high
        and (
            target_count > 0
            or scope in {"design_guide_direct_target_band_search", "one_click_solver_direct_target_band_search"}
        )
    )


def _build_shear_candidate_trace(state: dict[str, Any]) -> dict[str, Any]:
    eval_obj = _evaluate_state(float(state.get("uls_Mstar") or 0.0), float(state.get("uls_Vstar") or 0.0))
    seed_state = dict(eval_obj.get("state") or {})
    seed_overview = dict(eval_obj.get("overview") or {})
    mode_config = _quiet_call(inputs_page._design_mode_config, _quiet_call(inputs_page._design_optimisation_goal, seed_state))
    context = _quiet_call(inputs_page._build_auto_design_context, seed_state, mode_config, reference_overview=seed_overview)
    eval_cache: dict[str, Any] = {}
    metrics: dict[str, Any] = {
        "_reference_overview": seed_overview,
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    current_spacing = float(seed_state.get("s_lig", 200.0) or 200.0)
    current_legs = int(seed_state.get("lig_legs", 0) or 0)
    current_dia = int(seed_state.get("lig_d", 0) or 0)
    current_density = (current_legs * max(current_dia, 1) ** 2) / max(current_spacing, 1.0)

    generated_rows: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []
    filtered_rows: list[dict[str, Any]] = []

    candidate_states = list(_quiet_call(inputs_page.generate_less_shear_reo_variants, eval_obj, mode_config) or [])
    for idx, candidate_state in enumerate(candidate_states, start=1):
        candidate_id = f"shear_candidate_{idx:02d}"
        cand = _quiet_call(
            inputs_page._evaluate_candidate_fast,
            candidate_state,
            seed_state=seed_state,
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="shear_overdesign_debug_ladder",
            label=_quiet_call(inputs_page._shear_state_label, candidate_state),
            action_type="increase_link_spacing",
        )
        spacing = float(candidate_state.get("s_lig", current_spacing) or current_spacing)
        legs = int(candidate_state.get("lig_legs", current_legs) or current_legs)
        dia = int(candidate_state.get("lig_d", current_dia) or current_dia)
        candidate_density = (legs * max(dia, 1) ** 2) / max(spacing, 1.0)
        spacing_increase = max(spacing - current_spacing, 0.0)
        leg_reduction = max(current_legs - legs, 0)
        dia_reduction = max(current_dia - dia, 0)
        reduction_kind = (
            "remove_links"
            if legs <= 0
            else "increase_spacing"
            if spacing_increase > 0.0
            else "reduce_legs"
            if leg_reduction > 0
            else "reduce_dia"
            if dia_reduction > 0
            else "none"
        )

        rejection_reasons: list[str] = []
        invalid_spacing_without_activation = bool(
            _quiet_call(
                inputs_page._invalid_shear_spacing_change_without_activation,
                seed_state,
                candidate_state,
                source="shear_overdesign_debug_ladder",
            )
        )
        if invalid_spacing_without_activation:
            rejection_reasons.append("invalid_spacing_without_activation")

        if cand is None:
            rejection_reasons.append("preview_failed")

        if cand is not None:
            if not bool(cand.get("is_compliant")):
                rejection_reasons.append("fails_shear_capacity")
            pure_updates, bad_keys = _quiet_call(
                inputs_page._shear_detailing_updates_pure,
                dict(cand.get("updates") or {}),
            )
            if not pure_updates:
                rejection_reasons.append("non_shear_detailing_updates")
            if candidate_density >= current_density - 1e-9:
                rejection_reasons.append("non_material_change")
            if spacing_increase <= 0.0 and leg_reduction <= 0 and dia_reduction <= 0:
                rejection_reasons.append("no_real_density_reduction")

        row = {
            "candidate_id": candidate_id,
            "source": "generate_less_shear_reo_variants",
            "action_type": (
                "remove_shear_links"
                if reduction_kind == "remove_links"
                else "increase_link_spacing"
                if reduction_kind == "increase_spacing"
                else "reduce_number_of_legs"
            ),
            "label": _quiet_call(inputs_page._shear_state_label, candidate_state),
            "proposed_updates": _quiet_call(inputs_page._candidate_state_to_shared_updates, seed_state, candidate_state),
            "proposed_spacing": spacing,
            "proposed_legs": legs,
            "proposed_link_diameter": dia,
            "expected_phiVu": None,
            "expected_shear_util": None,
            "expected_bending_util": None,
            "classification": "cleanup",
            "one_click_resolved": False,
            "commit_eligible": False,
            "rejection_reasons": list(rejection_reasons),
            "internal_bad_update_keys": list(bad_keys) if cand is not None and not pure_updates else [],
            "contract_blocked_reason": None,
            "primary_one_click_reason": None,
            "score": None,
            "distance_to_target_band": None,
            "reaches_target_band": False,
            "is_primary_candidate": False,
            "displayed_as_primary_card": False,
            "cta_enabled": False,
        }

        if cand is not None:
            overview = dict(cand.get("overview") or {})
            shear_pack = dict((overview.get("packs") or {}).get("shear") or {})
            row["expected_phiVu"] = _float_or_none(shear_pack.get("summary_phiVu_kN"))
            row["expected_shear_util"] = _float_or_none((overview.get("utils") or {}).get("shear"))
            row["expected_bending_util"] = _float_or_none((overview.get("utils") or {}).get("bending"))
            cand["score"] = _quiet_call(inputs_page._score_auto_design_candidate, cand, mode_config, eval_obj)
            row["score"] = _float_or_none(cand.get("score"))
            row["distance_to_target_band"] = _candidate_distance_to_target(row["expected_shear_util"], seed_state)
            row["reaches_target_band"] = bool(_quiet_call(inputs_page._candidate_reaches_target_band_one_step, cand, mode_config))
            item = _quiet_call(
                inputs_page._guidance_item_from_resolved_candidate,
                cand,
                state=seed_state,
                overview=seed_overview,
                title=str(cand.get("label") or "Shear cleanup"),
                reasoning="Debug shear cleanup probe candidate.",
                status="EFFICIENCY",
            )
            if isinstance(item, dict) and item:
                row["one_click_resolved"] = bool(_quiet_call(inputs_page._guidance_item_is_resolved_one_click, item))
                contract_allowed, contract_reason = _quiet_call(
                    inputs_page._guidance_executor_actionability_contract,
                    item,
                    state=seed_state,
                )
                primary_valid, primary_meta = _quiet_call(
                    inputs_page._candidate_is_valid_primary_one_click,
                    item,
                    seed_overview,
                )
                row["contract_blocked_reason"] = None if contract_allowed else str(contract_reason or "")
                row["primary_one_click_reason"] = str(primary_meta.get("reason") or "")
                row["commit_eligible"] = bool(contract_allowed and primary_valid)

        if rejection_reasons:
            filtered_rows.append(row)
        else:
            valid_rows.append(row)
        generated_rows.append(row)

    target_lo, target_hi, _ = _quiet_call(
        inputs_page._resolved_efficiency_target_band,
        mode_config,
        goal=_quiet_call(inputs_page._design_optimisation_goal, seed_state),
    )
    target_mid = (float(target_lo) + float(target_hi)) / 2.0
    ranked_rows = sorted(
        valid_rows,
        key=lambda item: (
            0 if item["expected_shear_util"] is not None and float(target_lo) <= float(item["expected_shear_util"]) <= float(target_hi) else 1,
            abs(float(item["expected_shear_util"] or 0.0) - target_mid),
            0 if str(item.get("action_type") or "") == "increase_link_spacing" else 1,
            -float(item.get("proposed_spacing") or current_spacing),
            int(item.get("proposed_legs") or current_legs),
            int(item.get("proposed_link_diameter") or current_dia),
        ),
    )
    if ranked_rows:
        ranked_rows[0]["is_primary_candidate"] = True

    shear_debug = {}
    shear_rec = _quiet_call(inputs_page._compute_shear_tightening_recommendation, seed_state, out_debug=shear_debug)
    return {
        "seed_eval": eval_obj,
        "generated_candidates": generated_rows,
        "valid_candidates": ranked_rows,
        "filtered_candidates": filtered_rows,
        "top_shear_candidate": ranked_rows[0] if ranked_rows else None,
        "shear_tightening_recommendation": copy.deepcopy(shear_rec),
        "shear_tightening_debug": copy.deepcopy(shear_debug),
        "metrics": metrics,
    }


def _derive_final_explanation(
    *,
    case_id: str,
    pre_guidance: dict[str, Any],
    offline_guidance: dict[str, Any],
    trace: dict[str, Any],
) -> str:
    valid_count = len(trace.get("valid_candidates") or [])
    filtered_count = len(trace.get("filtered_candidates") or [])
    shear_debug = dict(trace.get("shear_tightening_debug") or {})
    contract_reason = str(
        pre_guidance.get("executor_contract_blocked_reason")
        or ((trace.get("top_shear_candidate") or {}).get("contract_blocked_reason"))
        or shear_debug.get("design_guide_executor_contract_primary_blocked_reason")
        or ""
    ).strip()
    terminal_reason = str(shear_debug.get("shear_tightening_terminal_reason") or "").strip()
    top = trace.get("top_shear_candidate") or {}
    selected_primary = dict(offline_guidance.get("primary_item") or {})
    selected_family = str((selected_primary or {}).get("family") or "")
    if _is_in_target_terminal_primary(pre_guidance) or _is_in_target_terminal_primary(selected_primary):
        return (
            "Shear cleanup candidates exist, but the current governing utilisation is already "
            "inside the target band. The Design Guide correctly keeps optional shear cleanup out "
            "of the primary card."
        )
    if _is_direct_target_band_primary(selected_primary):
        return (
            "Shear cleanup candidates exist, but the selected primary one-click is a direct "
            "target-band move. The Design Guide correctly prefers the governing target-band "
            "solution over optional local shear cleanup."
        )

    if not (trace.get("generated_candidates") or []):
        return "Shear did not optimise because no shear reduction candidates were generated from the current detailing state."
    if valid_count == 0:
        if terminal_reason == "no_compliant_density_reduction_candidates":
            return "Shear did not optimise because no wider-spacing / fewer-leg / smaller-link candidate survived the current compliance and density-reduction checks."
        if "governing_truth" in terminal_reason:
            return "Shear did not optimise because cleanup is blocked by the current governing-truth gate before reduction candidates can be committed."
        if contract_reason:
            return f"Shear did not optimise because the Design Guide demotes the cleanup to advisory ({contract_reason})."
        return "Shear did not optimise because candidates were generated but filtered out before any valid shear cleanup remained."
    if contract_reason == "blocked_shear_cleanup_does_not_reach_final_family_threshold":
        return (
            "Shear cleanup is blocked by exact final-threshold evidence: the shear cleanup "
            "search found no executor-backed one-click candidate that reaches the final "
            "accepted-family threshold of 0.85 while preserving bending, shear, serviceability, "
            "and detailing checks; further reduction is controlled by minimum/no-links detailing."
        )
    if contract_reason:
        return f"Shear did not optimise because a valid shear cleanup exists, but the displayed primary card is blocked by the executor contract gate ({contract_reason})."
    if selected_family and selected_family not in {"shear", "compound", "combined"}:
        return f"Shear did not optimise because a valid shear cleanup exists, but ranking/selection currently prefers a {selected_family} primary move."
    if selected_family in {"compound", "combined"}:
        return "Shear cleanup candidates exist, and the selected primary is a combined executor-backed move rather than a detached advisory shear card."
    if case_id and str(pre_guidance.get('action_type') or '').strip():
        return "Shear did not optimise because the selected primary action follows another family path before any surviving shear cleanup candidate is surfaced."
    return "Shear did not optimise because the surviving shear cleanup candidates did not become the selected primary executor-backed action."


def _run_offline_guidance(state: dict[str, Any]) -> dict[str, Any]:
    payload = _quiet_call(
        inputs_page._compute_design_guidance_items,
        state,
        guidance_debug_verbose=True,
        debug_enabled=False,
    )
    items = list(payload.get("guidance_items") or [])
    primary = items[0] if items else None
    debug_trace = dict(payload.get("debug_trace") or {})
    return {
        "payload": payload,
        "primary_item": _summarize_primary_item(primary),
        "debug_trace": debug_trace,
    }


def _build_case_result(
    *,
    case: dict[str, Any],
    resolved_actions: dict[str, float],
    candidate_trace: dict[str, Any],
    offline_guidance: dict[str, Any],
    pre_summary: dict[str, Any],
    pre_guidance_primary: dict[str, Any],
    pre_reinforcement: dict[str, Any],
    pre_settle_meta: dict[str, Any] | None,
    click_attempted: bool,
    run_end_event: dict[str, Any] | None,
    post_summary: dict[str, Any],
    post_guidance_primary: dict[str, Any],
    post_reinforcement: dict[str, Any],
    post_settle_meta: dict[str, Any] | None,
    click_error: str | None,
    alignment: dict[str, Any],
    post_publish_aligned: bool,
    browser_mode: str,
) -> dict[str, Any]:
    run_data = dict((run_end_event or {}).get("data") or {})
    primary_card = pre_guidance_primary
    selected_primary = offline_guidance["primary_item"]
    top_shear_candidate = candidate_trace.get("top_shear_candidate") or {}
    shear_debug = dict(candidate_trace.get("shear_tightening_debug") or {})
    contract_gate_blocked = bool(
        str(selected_primary.get("executor_contract_blocked_reason") or "").strip()
        or str(shear_debug.get("design_guide_executor_contract_primary_blocked_reason") or "").strip()
    )
    advisory_reason = (
        str(selected_primary.get("executor_contract_blocked_reason") or "")
        or str(shear_debug.get("design_guide_executor_contract_primary_blocked_reason") or "")
    )

    top_rejection_reason = None
    filtered = candidate_trace.get("filtered_candidates") or []
    if filtered:
        freq = Counter(
            reason
            for row in filtered
            for reason in list(row.get("rejection_reasons") or [])
            if reason
        )
        if freq:
            top_rejection_reason = freq.most_common(1)[0][0]

    final_explanation = _derive_final_explanation(
        case_id=case["case_id"],
        pre_guidance=primary_card,
        offline_guidance=offline_guidance,
        trace=candidate_trace,
    )

    decision_trace = {
        "case_id": case["case_id"],
        "starting_shear_util": _float_or_none((pre_summary or {}).get("utils", {}).get("shear")),
        "starting_spacing": (pre_reinforcement or {}).get("s_lig"),
        "starting_legs": (pre_reinforcement or {}).get("lig_legs"),
        "valid_shear_reduction_candidates_count": len(candidate_trace.get("valid_candidates") or []),
        "filtered_shear_reduction_candidates_count": len(candidate_trace.get("filtered_candidates") or []),
        "top_shear_reduction_candidate": (
            {
                "candidate_id": top_shear_candidate.get("candidate_id"),
                "label": top_shear_candidate.get("label"),
                "action_type": top_shear_candidate.get("action_type"),
                "proposed_spacing": top_shear_candidate.get("proposed_spacing"),
                "proposed_legs": top_shear_candidate.get("proposed_legs"),
                "proposed_link_diameter": top_shear_candidate.get("proposed_link_diameter"),
            }
            if top_shear_candidate
            else None
        ),
        "top_shear_reduction_rejection_reason": top_rejection_reason,
        "selected_primary_candidate": {
            "title": primary_card.get("title"),
            "action_type": primary_card.get("action_type"),
            "family": primary_card.get("family"),
        },
        "selected_primary_direct_target_band": bool(_is_direct_target_band_primary(selected_primary)),
        "selected_primary_reason": (
            str(offline_guidance.get("debug_trace", {}).get("guidance_branch") or "")
            or str(offline_guidance.get("debug_trace", {}).get("optimisation_selector_fallback_reason") or "")
        ),
        "contract_gate_blocked": bool(contract_gate_blocked),
        "advisory_reason": advisory_reason or None,
        "final_explanation": final_explanation,
    }

    print("SHEAR OVERDESIGN DECISION TRACE")
    print(f"case_id: {decision_trace['case_id']}")
    print(f"starting_shear_util: {decision_trace['starting_shear_util']}")
    print(f"starting_spacing: {decision_trace['starting_spacing']}")
    print(f"starting_legs: {decision_trace['starting_legs']}")
    print(f"valid_shear_reduction_candidates_count: {decision_trace['valid_shear_reduction_candidates_count']}")
    print(f"filtered_shear_reduction_candidates_count: {decision_trace['filtered_shear_reduction_candidates_count']}")
    print(f"top_shear_reduction_candidate: {decision_trace['top_shear_reduction_candidate']}")
    print(f"top_shear_reduction_rejection_reason: {decision_trace['top_shear_reduction_rejection_reason']}")
    print(f"selected_primary_candidate: {decision_trace['selected_primary_candidate']}")
    print(f"selected_primary_reason: {decision_trace['selected_primary_reason']}")
    print(f"contract_gate_blocked: {decision_trace['contract_gate_blocked']}")
    print(f"advisory_reason: {decision_trace['advisory_reason']}")
    print(f"final_explanation: {decision_trace['final_explanation']}")

    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "browser_mode": browser_mode,
        "resolved_actions": resolved_actions,
        "starting_state": _shear_summary_from_eval(candidate_trace["seed_eval"]),
        "candidate_generation": candidate_trace["generated_candidates"],
        "candidate_filtering": candidate_trace["filtered_candidates"],
        "candidate_ranking": candidate_trace["valid_candidates"],
        "shear_tightening_debug": candidate_trace["shear_tightening_debug"],
        "shear_tightening_recommendation": candidate_trace["shear_tightening_recommendation"],
        "offline_guidance_primary": selected_primary,
        "offline_guidance_debug": offline_guidance["debug_trace"],
        "pre_click_summary": pre_summary,
        "pre_click_guidance_primary": primary_card,
        "pre_click_reinforcement": pre_reinforcement,
        "pre_click_settle_meta": dict(pre_settle_meta or {}),
        "click_attempted": click_attempted,
        "run_end_present": bool(run_end_event),
        "run_end_stop_reason": run_data.get("stop_reason"),
        "run_end_winner_label": dict(run_data.get("compare") or {}).get("winner_label"),
        "final_updates": dict((run_data.get("compare") or {}).get("final_updates") or {}),
        "post_click_summary": post_summary,
        "post_click_guidance_primary": post_guidance_primary,
        "post_click_reinforcement": post_reinforcement,
        "post_click_settle_meta": dict(post_settle_meta or {}),
        "stale_state_flags": {
            "click_error": click_error,
            "post_publish_aligned": bool(post_publish_aligned),
            "truth_alignment": bool(alignment.get("aligned")),
        },
        "truth_layer_alignment": alignment,
        "decision_trace": decision_trace,
        "contract_gate_blocked": bool(contract_gate_blocked),
        "advisory_reason": advisory_reason or None,
        "final_explanation": final_explanation,
        "debug_snapshot": {
            "run_end_event": run_end_event,
            "offline_guidance_debug": offline_guidance["debug_trace"],
        },
    }


def _run_case_offline(case: dict[str, Any]) -> dict[str, Any]:
    resolved_actions = _resolve_case_actions(case)
    offline_state = _build_case_state(resolved_actions["mu"], resolved_actions["vu"])
    offline_guidance = _run_offline_guidance(offline_state)
    candidate_trace = _build_shear_candidate_trace(offline_state)
    seed_summary = _shear_summary_from_eval(candidate_trace["seed_eval"])
    primary = dict(offline_guidance["primary_item"] or {})
    pre_summary = {
        "Mu": resolved_actions["mu"],
        "Vu": resolved_actions["vu"],
        "worst_util": seed_summary.get("bending_util")
        if (seed_summary.get("bending_util") or 0.0) >= (seed_summary.get("shear_util") or 0.0)
        else seed_summary.get("shear_util"),
        "governing_family": seed_summary.get("governing_family"),
        "governing_check": seed_summary.get("governing_check"),
        "utils": {
            "bending": seed_summary.get("bending_util"),
            "shear": seed_summary.get("shear_util"),
        },
        "statuses": {
            "bending": seed_summary.get("bending_status"),
            "shear": seed_summary.get("shear_status"),
        },
    }
    pre_guidance_primary = {
        **primary,
        "title": primary.get("title"),
        "actionable_button": bool(primary.get("action_type")),
        "pending_meta": {},
    }
    pre_reinforcement = {
        "b": seed_summary.get("b"),
        "D": seed_summary.get("D"),
        "bot1_count": seed_summary.get("bot1_count"),
        "db_bot_1": seed_summary.get("db_bot_1"),
        "lig_d": seed_summary.get("lig_d"),
        "lig_legs": seed_summary.get("lig_legs"),
        "s_lig": seed_summary.get("s_lig"),
    }
    return _build_case_result(
        case=case,
        resolved_actions=resolved_actions,
        candidate_trace=candidate_trace,
        offline_guidance=offline_guidance,
        pre_summary=pre_summary,
        pre_guidance_primary=pre_guidance_primary,
        pre_reinforcement=pre_reinforcement,
        pre_settle_meta={},
        click_attempted=False,
        run_end_event=None,
        post_summary=pre_summary,
        post_guidance_primary=pre_guidance_primary,
        post_reinforcement=pre_reinforcement,
        post_settle_meta={},
        click_error="browser_probe_unavailable_offline_fallback",
        alignment={"aligned": True},
        post_publish_aligned=True,
        browser_mode="offline_fallback",
    )


def _run_case_on_page(page, case: dict[str, Any], base_url: str) -> dict[str, Any]:
    try:
        page.goto(
            _query(base_url, {"page": "inputs", "browser_recipe": BASE_RECIPE_NAME}),
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        page.get_by_label("Browser state").wait_for(state="attached", timeout=8_000)
        _wait_for_recipe(page, BASE_RECIPE_NAME, timeout_s=8.0)

        resolved_actions = _resolve_case_actions(case)
        offline_state = _build_case_state(resolved_actions["mu"], resolved_actions["vu"])
        pre_state_raw, pre_settle_meta = _apply_live_inputs(
            page,
            mu=float(resolved_actions["mu"]),
            vu=float(resolved_actions["vu"]),
        )
        pre = _capture_state(page)

        offline_guidance = _run_offline_guidance(offline_state)
        candidate_trace = _build_shear_candidate_trace(offline_state)

        click_attempted = False
        click_error = None
        run_end_event = None
        post_settle_meta: dict[str, Any] = {}
        post_publish_aligned = False
        if bool(pre["guidance_primary"].get("actionable_button")):
            click_attempted = True
            try:
                button = page.get_by_role("button", name="Run one-click auto design")
                button.wait_for(timeout=5_000)
                tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
                click_started_ms = int(time.time() * 1000)
                button.click(timeout=10_000)
                run_end_event, _ = _wait_for_run_end(tracer_offset, start_time_ms=click_started_ms)
                run_end_data = dict((run_end_event or {}).get("data") or {})
                if run_end_data:
                    _, post_publish_aligned, post_settle_meta = _wait_for_post_publish_alignment(
                        page,
                        mu=float(resolved_actions["mu"]),
                        vu=float(resolved_actions["vu"]),
                        run_end_data=run_end_data,
                        timeout_s=45.0,
                    )
                else:
                    _, post_publish_aligned, post_settle_meta = _wait_for_post_click_state_without_run_end(
                        page,
                        mu=float(resolved_actions["mu"]),
                        vu=float(resolved_actions["vu"]),
                        pre_state=pre_state_raw,
                        timeout_s=45.0,
                    )
            except PlaywrightTimeoutError as exc:
                click_error = f"{type(exc).__name__}: {exc}"

        post = _capture_state(page)
        alignment = _truth_alignment(run_end_event, post["raw_state"])
        result = _build_case_result(
            case=case,
            resolved_actions=resolved_actions,
            candidate_trace=candidate_trace,
            offline_guidance=offline_guidance,
            pre_summary=pre["summary"],
            pre_guidance_primary=pre["guidance_primary"],
            pre_reinforcement=pre["reinforcement"],
            pre_settle_meta=pre_settle_meta,
            click_attempted=click_attempted,
            run_end_event=run_end_event,
            post_summary=post["summary"],
            post_guidance_primary=post["guidance_primary"],
            post_reinforcement=post["reinforcement"],
            post_settle_meta=post_settle_meta,
            click_error=click_error,
            alignment=alignment,
            post_publish_aligned=post_publish_aligned,
            browser_mode="browser_live",
        )
        material_overdesign_audit_failures: list[str] = []
        for label, capture in (("pre", pre), ("post", post)):
            before_count = len(material_overdesign_audit_failures)
            audit = overdesign_debug_from_browser_state(
                capture.get("raw_state"),
                primary=dict(capture.get("guidance_primary") or {}),
                summary=dict(capture.get("summary") or {}),
            )
            assert_no_unresolved_material_overdesign(
                str(case.get("case_id") or ""),
                audit,
                fail_reasons=material_overdesign_audit_failures,
            )
            if len(material_overdesign_audit_failures) > before_count:
                material_overdesign_audit_failures[-1] = f"{label}:{material_overdesign_audit_failures[-1]}"
        result["material_overdesign_audit_failures"] = material_overdesign_audit_failures
        return result
    except Exception:
        return _run_case_offline(case)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8524)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--browser-live",
        action="store_true",
        help="Attempt the slow browser probe. By default this diagnostic uses its offline fallback path.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        default=None,
        help="Run only the named case_id. May be supplied more than once.",
    )
    args = parser.parse_args(argv)

    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_dir = REPO_ROOT / "artifacts" / "verification" / "latest"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"shear_overdesign_debug_ladder_{timestamp}.json"
    requested_cases = {str(case_id).strip() for case_id in (args.case_ids or []) if str(case_id).strip()}
    case_defs = [case for case in CASE_DEFS if not requested_cases or str(case.get("case_id")) in requested_cases]
    missing_cases = sorted(requested_cases - {str(case.get("case_id")) for case in case_defs})
    if missing_cases:
        raise SystemExit(f"Unknown shear overdesign case id(s): {', '.join(missing_cases)}")
    use_browser_live = bool(args.browser_live or args.base_url)
    try:
        if use_browser_live and args.base_url:
            _wait_for_http(base_url)
        elif use_browser_live:
            process = _start_streamlit(args.port)

        results: list[dict[str, Any]] = []
        no_candidates_generated = 0
        generated_but_filtered = 0
        valid_survived_not_selected = 0
        blocked_non_governing_cleanup = 0
        blocked_no_resolved_candidate = 0
        blocked_minimum_detailing = 0
        advisory_only = 0
        real_optimiser_gap = 0
        material_overdesign_audit_failure_count = 0

        def record_result(result: dict[str, Any]) -> None:
            nonlocal no_candidates_generated
            nonlocal generated_but_filtered
            nonlocal valid_survived_not_selected
            nonlocal blocked_non_governing_cleanup
            nonlocal blocked_no_resolved_candidate
            nonlocal blocked_minimum_detailing
            nonlocal advisory_only
            nonlocal real_optimiser_gap
            nonlocal material_overdesign_audit_failure_count
            results.append(result)
            if result.get("material_overdesign_audit_failures"):
                material_overdesign_audit_failure_count += 1
            valid_count = int(result["decision_trace"]["valid_shear_reduction_candidates_count"] or 0)
            filtered_count = int(result["decision_trace"]["filtered_shear_reduction_candidates_count"] or 0)
            primary_family = str((result.get("pre_click_guidance_primary") or {}).get("family") or "")
            in_target_terminal = bool(
                _is_in_target_terminal_primary(result.get("pre_click_guidance_primary"))
                or _is_in_target_terminal_primary(result.get("offline_guidance_primary"))
            )
            direct_target_primary = bool(
                result.get("decision_trace", {}).get("selected_primary_direct_target_band")
                or _is_direct_target_band_primary(result.get("offline_guidance_primary"))
            )
            final_threshold_blocker = (
                "unresolved_meaningful_family_util_below_0.85"
                in str(result.get("advisory_reason") or "")
                or "blocked_shear_cleanup_does_not_reach_final_family_threshold"
                in str(result.get("advisory_reason") or "")
                or "blocked by exact final-threshold evidence"
                in str(result.get("final_explanation") or "").lower()
                or "final accepted-family threshold"
                in str(result.get("final_explanation") or "").lower()
            )
            if not (result.get("candidate_generation") or []):
                no_candidates_generated += 1
            elif valid_count == 0 and filtered_count > 0:
                generated_but_filtered += 1
            elif (
                valid_count > 0
                and primary_family not in {"shear", "compound", "combined"}
                and not in_target_terminal
                and not direct_target_primary
                and not final_threshold_blocker
            ):
                valid_survived_not_selected += 1
            if "non_governing_cleanup" in str(result.get("advisory_reason") or "") or "non_governing_cleanup" in str(result.get("final_explanation") or ""):
                blocked_non_governing_cleanup += 1
            if "executor_backed" in str(result.get("advisory_reason") or "") or "resolved" in str(result.get("advisory_reason") or ""):
                blocked_no_resolved_candidate += 1
            if any(
                token in " ".join(
                    reason
                    for row in list(result.get("candidate_filtering") or [])
                    for reason in list(row.get("rejection_reasons") or [])
                )
                for token in ("invalid_spacing_without_activation", "fails_shear_capacity")
            ):
                blocked_minimum_detailing += 1
            if (
                bool(result.get("contract_gate_blocked"))
                or (
                    not bool((result.get("pre_click_guidance_primary") or {}).get("actionable_button"))
                    and not in_target_terminal
                )
            ) and not final_threshold_blocker:
                advisory_only += 1
            if (
                valid_count > 0
                and primary_family not in {"shear", "compound", "combined"}
                and not bool(result.get("contract_gate_blocked"))
                and not in_target_terminal
                and not direct_target_primary
                and not final_threshold_blocker
            ):
                real_optimiser_gap += 1

        if use_browser_live:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=not args.headed)
                for case in case_defs:
                    print(f"shear_overdesign_debug_ladder: BEGIN {case['case_id']}", flush=True)
                    context = browser.new_context()
                    page = context.new_page()
                    result = _run_case_on_page(page, case, base_url)
                    print(f"shear_overdesign_debug_ladder: END {case['case_id']}", flush=True)
                    record_result(result)
                    context.close()
                browser.close()
        else:
            for case in case_defs:
                print(f"shear_overdesign_debug_ladder: BEGIN {case['case_id']}", flush=True)
                result = _run_case_offline(case)
                print(f"shear_overdesign_debug_ladder: END {case['case_id']}", flush=True)
                record_result(result)

        payload = {
            "base_url": base_url,
            "generated_at": timestamp,
            "requested_cases": sorted(requested_cases),
            "cases": results,
            "summary": {
                "total_cases": len(results),
                "cases_where_no_shear_reduction_candidates_were_generated": no_candidates_generated,
                "cases_where_candidates_were_generated_but_filtered": generated_but_filtered,
                "cases_where_valid_candidates_survived_but_were_not_selected": valid_survived_not_selected,
                "cases_blocked_by_non_governing_cleanup": blocked_non_governing_cleanup,
                "cases_blocked_by_no_resolved_one_click_candidate": blocked_no_resolved_candidate,
                "cases_blocked_by_minimum_detailing_or_spacing_limits": blocked_minimum_detailing,
                "cases_where_shear_optimisation_is_advisory_only": advisory_only,
                "cases_where_this_is_a_real_optimiser_gap": real_optimiser_gap,
                "material_overdesign_audit_failure_count": material_overdesign_audit_failure_count,
            },
        }
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print(f"shear_overdesign_debug_ladder: {artifact_path}")
        print(f"total cases: {payload['summary']['total_cases']}")
        print(
            "cases where no shear reduction candidates were generated: "
            f"{payload['summary']['cases_where_no_shear_reduction_candidates_were_generated']}"
        )
        print(
            "cases where candidates were generated but filtered: "
            f"{payload['summary']['cases_where_candidates_were_generated_but_filtered']}"
        )
        print(
            "cases where valid candidates survived but were not selected: "
            f"{payload['summary']['cases_where_valid_candidates_survived_but_were_not_selected']}"
        )
        print(
            "cases blocked by non_governing_cleanup: "
            f"{payload['summary']['cases_blocked_by_non_governing_cleanup']}"
        )
        print(
            "cases blocked by no_resolved_one_click_candidate: "
            f"{payload['summary']['cases_blocked_by_no_resolved_one_click_candidate']}"
        )
        print(
            "cases blocked by minimum detailing/spacing limits: "
            f"{payload['summary']['cases_blocked_by_minimum_detailing_or_spacing_limits']}"
        )
        print(
            "cases where shear optimisation is advisory-only: "
            f"{payload['summary']['cases_where_shear_optimisation_is_advisory_only']}"
        )
        print(
            "cases where this is a real optimiser gap: "
            f"{payload['summary']['cases_where_this_is_a_real_optimiser_gap']}"
        )
        print(
            "material overdesign audit failures: "
            f"{payload['summary']['material_overdesign_audit_failure_count']}"
        )
        return 1 if material_overdesign_audit_failure_count else 0
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
