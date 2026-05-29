from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import inputs_page
from tools.verification.helpers.browser_one_click_regression import TRACER_PATH, _query, _start_streamlit, _wait_for_http, _wait_for_run_end
from tools.verification.helpers.browser_helpers import (
    _apply_live_inputs,
    _wait_for_settled_preclick_state,
    _wait_for_post_click_state_without_run_end,
    _wait_for_post_publish_alignment,
)
from tools.verification.runners.recommendation_contract_ladder import _capture_state, _truth_alignment
from tools.verification.recipes.one_click_recipe_defs import TARGET_BAND, build_state
from tools.verification.helpers.overdesign_assertions import (
    assert_no_unresolved_material_overdesign,
    overdesign_debug_from_browser_state,
)


BASE_RECIPE_NAME = "SO_BASE_HEAVY_LINKS_CONSERVATIVE"
TARGET_LOW = float(TARGET_BAND["min"])
TARGET_HIGH = float(TARGET_BAND["max"])

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

CASES = [
    {
        "case_id": "BENDING_SAFE_OVERDESIGNED",
        "description": "Safe combined design below target should not be accepted as within target band.",
        "recipe": BASE_RECIPE_NAME,
        "seed_recipe": "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED",
        "mu": 45.0,
        "vu": 0.0,
    },
    {
        "case_id": "SHEAR_SAFE_OVERDESIGNED",
        "description": "Low/moderate Vu with heavy links should optimise shear or explain blocker.",
        "recipe": BASE_RECIPE_NAME,
        "seed_recipe": "OPT_EXPECT_SHEAR_SAFE_OVERDESIGNED",
        "mu": 0.0,
        "vu": 150.0,
    },
    {
        "case_id": "COMBINED_SAFE_OVERDESIGNED",
        "description": "Low Mu and low Vu with heavy geometry/reo should not be silently accepted.",
        "recipe": BASE_RECIPE_NAME,
        "seed_recipe": "OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED",
        "mu": 45.0,
        "vu": 150.0,
    },
    {
        "case_id": "ALREADY_TARGET",
        "description": "Design already inside target band may be accepted as within target band.",
        "recipe": BASE_RECIPE_NAME,
        "seed_recipe": "OPT_EXPECT_ALREADY_TARGET",
        "mu": 100.0,
        "vu": 0.0,
    },
    {
        "case_id": "IN_BAND_ZERO_SHEAR_ACTIVE_LINKS",
        "description": "A settled in-band design with zero shear demand must not keep a final tightening CTA alive.",
        "recipe": BASE_RECIPE_NAME,
        "seed_recipe": "OPT_EXPECT_IN_BAND_ZERO_SHEAR_ACTIVE_LINKS",
        "mu": 95.0,
        "vu": 0.0,
    },
    {
        "case_id": "IN_BAND_TINY_SHEAR_ACTIVE_LINKS",
        "description": "A settled in-band design with tiny shear demand must not keep a final tightening CTA alive.",
        "recipe": BASE_RECIPE_NAME,
        "seed_recipe": "OPT_EXPECT_IN_BAND_TINY_SHEAR_ACTIVE_LINKS",
        "mu": 95.0,
        "vu": 10.0,
    },
    {
        "case_id": "MINIMUM_GEOMETRY_BLOCKED",
        "description": "Below-target design may remain if a clear practical blocker is explained.",
        "recipe": None,
        "seed_recipe": "OPT_EXPECT_MINIMUM_GEOMETRY_BLOCKED",
        "mu": 40.0,
        "vu": 0.0,
    },
]


def _manual_actions(mu: float, vu: float) -> dict[str, Any]:
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
        "uls_Nstar": 0.0,
        "load_Nstar_proxy": 0.0,
        "N_star": 0.0,
        "Tu_star": 0.0,
        "sls_Mstar": 0.0,
        "sls_Vstar": 0.0,
        "sls_Nstar": 0.0,
    }


def _evaluate_state(mu: float, vu: float) -> dict[str, Any]:
    state = build_state({**BASE_CHANGES, **_manual_actions(mu, vu)})
    candidate = inputs_page.evaluate_candidate_full(state, source="optimisation_expectation_seed")
    if not isinstance(candidate, dict):
        raise RuntimeError(f"Seed evaluation failed for Mu={mu}, Vu={vu}")
    return candidate


def _find_target_band_mu(vu: float, *, lo: float = 0.88, hi: float = 0.95, target: float = 0.90) -> float:
    best_in_band: tuple[float, float] | None = None
    best_any: tuple[float, float] | None = None
    for mu in range(20, 601, 5):
        candidate = _evaluate_state(float(mu), float(vu))
        overview = dict(candidate.get("overview") or {})
        util = _float_or_none(overview.get("worst_util"))
        statuses = dict(overview.get("statuses") or {})
        if util is None:
            continue
        distance = abs(util - target)
        if best_any is None or distance < best_any[1]:
            best_any = (float(mu), distance)
        if all(str(status or "").upper() in {"PASS", "INFO", "NEAR LIMIT", "—", "-"} for status in statuses.values()):
            if lo <= util <= hi and (best_in_band is None or distance < best_in_band[1]):
                best_in_band = (float(mu), distance)
    if best_in_band is not None:
        return best_in_band[0]
    if best_any is not None:
        return best_any[0]
    return 280.0


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _resolve_case_actions(case: dict[str, Any]) -> dict[str, float]:
    vu = float(case.get("vu") or 0.0)
    if case.get("mu_mode") == "target_band":
        mu = _find_target_band_mu(vu)
    else:
        mu = float(case.get("mu") or 0.0)
    return {"mu": mu, "vu": vu}


def _actionable(pre: dict[str, Any]) -> bool:
    primary = dict(pre.get("guidance_primary") or {})
    return bool(primary.get("actionable_button")) and bool(str(primary.get("action_type") or "").strip())


def _text_blob(state: dict[str, Any]) -> str:
    primary = dict(state.get("guidance_primary") or {})
    raw = dict(state.get("raw_state") or {})
    guidance_probe = dict(raw.get("guidance_probe") or {})
    compute_probe = dict(raw.get("guidance_compute_probe") or {})
    parts = [
        str(primary.get("title") or ""),
        str(primary.get("visible_text") or ""),
        str(primary.get("terminal_state") or ""),
        str(primary.get("guidance_branch") or ""),
        str((primary.get("button_contract") or {}).get("blocking_reason") or ""),
        str((guidance_probe.get("primary_button_contract") or {}).get("blocking_reason") or ""),
        str((compute_probe.get("primary_button_contract") or {}).get("blocking_reason") or ""),
        str(guidance_probe.get("user_visible_no_action_reason") or ""),
        str(compute_probe.get("user_visible_no_action_reason") or ""),
    ]
    return " ".join(part for part in parts if part).lower()


def _has_blocker_explanation(state: dict[str, Any]) -> bool:
    text = _text_blob(state)
    blocker_tokens = [
        "minimum",
        "min ",
        "spacing",
        "detailing",
        "discrete",
        "constructability",
        "no one-click optimisation available",
        "no safe one-click cleanup candidate",
        "no executor-backed local reduction is available",
        "no further safe local reductions",
        "blocked",
        "manual review",
        "no practical",
        "would violate",
        "would fail",
        "already efficient",
        "very low demand",
    ]
    return any(token in text for token in blocker_tokens)


def _says_within_target_band(state: dict[str, Any]) -> bool:
    text = _text_blob(state)
    return "within target band" in text or "design is within target band" in text


def _all_safe(statuses: dict[str, Any]) -> bool:
    values = [str(v or "").upper() for v in statuses.values()]
    return bool(values) and all(v in {"PASS", "INFO", "NEAR LIMIT", "—", "-"} for v in values)


def _extract_util(state: dict[str, Any]) -> float | None:
    summary = dict(state.get("summary") or {})
    return _float_or_none(summary.get("worst_util"))


def _material_improvement(pre_util: float | None, post_util: float | None) -> bool:
    if pre_util is None or post_util is None:
        return False
    return (post_util - pre_util) >= 0.02


def _material_worsening(pre_util: float | None, post_util: float | None) -> bool:
    if pre_util is None or post_util is None:
        return False
    return (pre_util - post_util) >= 0.02


def _selected_action(pre: dict[str, Any], run_end_event: dict[str, Any] | None) -> str:
    run_data = dict((run_end_event or {}).get("data") or {})
    compare = dict(run_data.get("compare") or {})
    return (
        str(compare.get("winner_label") or "").strip()
        or str((pre.get("guidance_primary") or {}).get("title") or "").strip()
        or "unknown"
    )


def _detect_unnecessary_strengthening(
    *,
    pre_summary: dict[str, Any],
    post_summary: dict[str, Any],
    pre_reinf: dict[str, Any],
    post_reinf: dict[str, Any],
) -> tuple[bool, bool, str | None]:
    pre_statuses = dict(pre_summary.get("statuses") or {})
    all_pass_pre = _all_safe(pre_statuses)
    pre_util = _float_or_none(pre_summary.get("worst_util"))
    post_util = _float_or_none(post_summary.get("worst_util"))
    below_target_pre = bool(pre_util is not None and pre_util < TARGET_LOW)

    geometry_increased = bool(
        (_float_or_none(post_reinf.get("b")) or 0.0) > (_float_or_none(pre_reinf.get("b")) or 0.0) + 1e-6
        or (_float_or_none(post_reinf.get("D")) or 0.0) > (_float_or_none(pre_reinf.get("D")) or 0.0) + 1e-6
    )
    flexural_increased = bool(
        (_float_or_none(post_reinf.get("bot1_count")) or 0.0) > (_float_or_none(pre_reinf.get("bot1_count")) or 0.0) + 1e-6
        or (_float_or_none(post_reinf.get("db_bot_1")) or 0.0) > (_float_or_none(pre_reinf.get("db_bot_1")) or 0.0) + 1e-6
    )
    shear_increased = bool(
        (_float_or_none(post_reinf.get("lig_legs")) or 0.0) > (_float_or_none(pre_reinf.get("lig_legs")) or 0.0) + 1e-6
        or (_float_or_none(post_reinf.get("lig_d")) or 0.0) > (_float_or_none(pre_reinf.get("lig_d")) or 0.0) + 1e-6
        or (
            _float_or_none(post_reinf.get("s_lig")) is not None
            and _float_or_none(pre_reinf.get("s_lig")) is not None
            and (_float_or_none(post_reinf.get("s_lig")) or 0.0) < (_float_or_none(pre_reinf.get("s_lig")) or 0.0) - 1e-6
        )
    )
    lower_util_after = _material_worsening(pre_util, post_util)
    if not all_pass_pre:
        return False, False, None
    if not below_target_pre:
        return False, False, None
    geometry_decreased = bool(
        (_float_or_none(post_reinf.get("b")) or 0.0) < (_float_or_none(pre_reinf.get("b")) or 0.0) - 1e-6
        or (_float_or_none(post_reinf.get("D")) or 0.0) < (_float_or_none(pre_reinf.get("D")) or 0.0) - 1e-6
    )
    target_after = bool(post_util is not None and TARGET_LOW <= post_util <= TARGET_HIGH)
    if geometry_decreased and target_after and post_util is not None and pre_util is not None and post_util > pre_util + 0.02:
        return False, False, None
    if shear_increased:
        return True, True, "shear reinforcement increased even though shear already passed with low utilisation"
    if geometry_increased:
        return True, False, "geometry increased even though all checks already passed below target"
    if flexural_increased:
        return True, False, "reinforcement increased even though all checks already passed below target"
    if lower_util_after:
        return True, False, "selected action increased capacity even though no governing check was failing"
    return False, False, None


def _run_case(page, case: dict[str, Any], base_url: str) -> dict[str, Any]:
    query = {"page": "inputs"}
    seed_recipe = str(case.get("seed_recipe") or "").strip()
    if seed_recipe:
        query["browser_recipe"] = seed_recipe
    elif case.get("recipe"):
        query["browser_recipe"] = str(case["recipe"])
    page.goto(_query(base_url, query), wait_until="domcontentloaded", timeout=60_000)
    page.get_by_label("Browser state").wait_for(state="attached", timeout=120_000)

    resolved = _resolve_case_actions(case)
    if seed_recipe:
        pre_state_raw, matched, pre_settle_meta = _wait_for_settled_preclick_state(
            page,
            mu=resolved["mu"],
            vu=resolved["vu"],
            timeout_s=90.0,
            stable_reads=2,
        )
        pre_settle_meta = dict(pre_settle_meta)
        pre_settle_meta["setup_mode"] = "seeded_browser_recipe"
        pre_settle_meta["seed_recipe"] = seed_recipe
        if not matched:
            raise RuntimeError(
                f"Seed recipe did not reconcile into shared/published state. "
                f"recipe={seed_recipe}, expected Mu={resolved['mu']}, Vu={resolved['vu']}, "
                f"probe={dict(pre_state_raw.get('summary_state_probe') or {})}, "
                f"shared={dict(pre_state_raw.get('browser_shared_probe') or {})}"
            )
    else:
        pre_state_raw, pre_settle_meta = _apply_live_inputs(page, mu=resolved["mu"], vu=resolved["vu"])
    pre = _capture_state(page)
    pre_util = _extract_util(pre)
    pre_statuses = dict((pre.get("summary") or {}).get("statuses") or {})

    click_attempted = False
    click_error = None
    run_end_event = None
    post_settle_meta: dict[str, Any] = {}
    post_publish_aligned = True
    if _actionable(pre):
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
                    mu=resolved["mu"],
                    vu=resolved["vu"],
                    run_end_data=run_end_data,
                    timeout_s=45.0,
                )
            else:
                _, post_publish_aligned, post_settle_meta = _wait_for_post_click_state_without_run_end(
                    page,
                    mu=resolved["mu"],
                    vu=resolved["vu"],
                    pre_state=pre_state_raw,
                    timeout_s=45.0,
                )
        except PlaywrightTimeoutError as exc:
            click_error = f"{type(exc).__name__}: {exc}"
            post_publish_aligned = False

    post = _capture_state(page)
    alignment = _truth_alignment(run_end_event, post["raw_state"])
    post_util = _extract_util(post)
    post_statuses = dict((post.get("summary") or {}).get("statuses") or {})
    stop_reason = str(((run_end_event or {}).get("data") or {}).get("stop_reason") or "").strip() or None
    selected_action = _selected_action(pre, run_end_event)
    blocker_explained_pre = _has_blocker_explanation(pre)
    blocker_explained_post = _has_blocker_explanation(post)
    below_target_pre = bool(pre_util is not None and pre_util < TARGET_LOW)
    within_target_pre = bool(pre_util is not None and TARGET_LOW <= pre_util <= TARGET_HIGH)
    says_done_pre = _says_within_target_band(pre)
    optimisation_applied = _material_improvement(pre_util, post_util)
    reaches_target = bool(post_util is not None and TARGET_LOW <= post_util <= TARGET_HIGH)
    explained_blocker = blocker_explained_pre or blocker_explained_post or stop_reason in {
        "best_available_out_of_band_candidate",
        "legitimate_constrained_stop",
    }
    unnecessary_strengthening, unnecessary_shear_strengthening, strengthening_reason = _detect_unnecessary_strengthening(
        pre_summary=dict(pre.get("summary") or {}),
        post_summary=dict(post.get("summary") or {}),
        pre_reinf=dict(pre.get("reinforcement") or {}),
        post_reinf=dict(post.get("reinforcement") or {}),
    )

    failure_reason = None
    if click_error:
        failure_reason = f"click_error:{click_error}"
    elif unnecessary_strengthening:
        failure_reason = "unnecessary_strengthening"
    elif within_target_pre and _all_safe(pre_statuses) and _actionable(pre):
        failure_reason = "in_target_band_actionable_final_tightening"
    elif below_target_pre and says_done_pre and not explained_blocker:
        failure_reason = "below_target_design_incorrectly_accepted_as_within_target_band"
    elif below_target_pre and not _actionable(pre) and not explained_blocker:
        failure_reason = "remaining_overdesign_unexplained"
    elif click_attempted and not run_end_event and (reaches_target or optimisation_applied) and alignment.get("aligned", True) and post_publish_aligned:
        failure_reason = None
    elif click_attempted and not run_end_event and not optimisation_applied and not explained_blocker:
        failure_reason = "actionable_optimisation_without_run_end_or_explanation"
    elif click_attempted and not optimisation_applied and not reaches_target and not explained_blocker:
        failure_reason = "valid_optimisation_path_silently_ignored"
    elif not alignment.get("aligned", True) or not post_publish_aligned:
        failure_reason = "truth_layer_alignment_failure"
    elif not _all_safe(post_statuses):
        failure_reason = "unsafe_or_failing_status_present"
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
    if material_overdesign_audit_failures and failure_reason is None:
        failure_reason = material_overdesign_audit_failures[0]

    verdict = "PASS" if failure_reason is None else "FAIL"
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "recipe": case.get("recipe"),
        "seed_recipe": case.get("seed_recipe"),
        "inputs": {"Mu": resolved["mu"], "Vu": resolved["vu"]},
        "target_low": TARGET_LOW,
        "target_high": TARGET_HIGH,
        "selected_action": selected_action,
        "starting_utilisation": pre_util,
        "final_utilisation": post_util,
        "pre_click_summary": pre.get("summary"),
        "pre_click_guidance_primary": pre.get("guidance_primary"),
        "pre_click_reinforcement": pre.get("reinforcement"),
        "pre_click_settle_meta": pre_settle_meta,
        "pre_click_actionable": _actionable(pre),
        "pre_click_blocker_explained": blocker_explained_pre,
        "pre_click_banner_within_target_band": says_done_pre,
        "click_attempted": click_attempted,
        "run_end_present": bool(run_end_event),
        "run_end_stop_reason": stop_reason,
        "post_click_summary": post.get("summary"),
        "post_click_guidance_primary": post.get("guidance_primary"),
        "post_click_reinforcement": post.get("reinforcement"),
        "post_click_settle_meta": post_settle_meta,
        "post_click_blocker_explained": blocker_explained_post,
        "optimisation_applied": optimisation_applied,
        "reaches_target_band": reaches_target,
        "unnecessary_strengthening": unnecessary_strengthening,
        "unnecessary_shear_strengthening": unnecessary_shear_strengthening,
        "strengthening_reason": strengthening_reason,
        "truth_layer_alignment": alignment,
        "post_publish_aligned": bool(post_publish_aligned),
        "material_overdesign_audit_failures": material_overdesign_audit_failures,
        "verdict": verdict,
        "failure_reason": failure_reason,
    }


def _case_exception_result(case: dict[str, Any], exc: Exception) -> dict[str, Any]:
    resolved = _resolve_case_actions(case)
    failure_reason = f"case_exception:{type(exc).__name__}: {exc}"
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "recipe": case.get("recipe"),
        "seed_recipe": case.get("seed_recipe"),
        "inputs": {"Mu": resolved["mu"], "Vu": resolved["vu"]},
        "target_low": TARGET_LOW,
        "target_high": TARGET_HIGH,
        "selected_action": None,
        "starting_utilisation": None,
        "final_utilisation": None,
        "pre_click_summary": None,
        "pre_click_guidance_primary": None,
        "pre_click_reinforcement": None,
        "pre_click_settle_meta": {},
        "pre_click_actionable": False,
        "pre_click_blocker_explained": False,
        "pre_click_banner_within_target_band": False,
        "click_attempted": False,
        "run_end_present": False,
        "run_end_stop_reason": None,
        "post_click_summary": None,
        "post_click_guidance_primary": None,
        "post_click_reinforcement": None,
        "post_click_settle_meta": {},
        "post_click_blocker_explained": False,
        "optimisation_applied": False,
        "reaches_target_band": False,
        "unnecessary_strengthening": False,
        "unnecessary_shear_strengthening": False,
        "strengthening_reason": None,
        "truth_layer_alignment": {"aligned": False, "reason": failure_reason},
        "post_publish_aligned": False,
        "verdict": "FAIL",
        "failure_reason": failure_reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8525)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Run only the named case_id. May be supplied more than once.",
    )
    parser.add_argument("--cases", default=None, help="Comma-separated case_id list.")
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args(argv)

    all_case_ids = [str(case.get("case_id") or "") for case in CASES]
    if args.list_cases:
        print("\n".join(all_case_ids))
        return 0

    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_dir = REPO_ROOT / "artifacts" / "verification" / "latest"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"optimisation_expectation_ladder_{timestamp}.json"
    try:
        if args.base_url is None:
            process = _start_streamlit(args.port)
        else:
            _wait_for_http(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            results: list[dict[str, Any]] = []
            unsafe_accepted = 0
            below_target_incorrectly_accepted = 0
            practical_blocker_explained = 0
            optimisation_applied_count = 0
            remaining_overdesign_unexplained = 0
            in_target_band_actionable_final_tightening_count = 0
            unnecessary_strengthening_count = 0
            unnecessary_shear_strengthening_count = 0
            unnecessary_strengthening_cases: list[dict[str, Any]] = []

            selected_case_ids = {str(item).strip() for item in (args.case or []) if str(item).strip()}
            selected_case_ids.update(
                str(item).strip()
                for item in str(args.cases or "").split(",")
                if str(item).strip()
            )
            selected_cases = [
                case for case in CASES
                if not selected_case_ids or str(case.get("case_id") or "") in selected_case_ids
            ]
            if selected_case_ids and len(selected_cases) != len(selected_case_ids):
                known = {str(case.get("case_id") or "") for case in CASES}
                missing = sorted(selected_case_ids - known)
                raise SystemExit(f"Unknown optimisation expectation case(s): {', '.join(missing)}")

            for case in selected_cases:
                context = browser.new_context()
                page = context.new_page()
                try:
                    result = _run_case(page, case, base_url)
                except Exception as exc:
                    result = _case_exception_result(case, exc)
                finally:
                    context.close()
                results.append(result)
                if result["pre_click_blocker_explained"] or result["post_click_blocker_explained"]:
                    practical_blocker_explained += 1
                if result["optimisation_applied"]:
                    optimisation_applied_count += 1
                if result["failure_reason"] == "unsafe_or_failing_status_present":
                    unsafe_accepted += 1
                if result["failure_reason"] == "below_target_design_incorrectly_accepted_as_within_target_band":
                    below_target_incorrectly_accepted += 1
                if result["failure_reason"] in {
                    "remaining_overdesign_unexplained",
                    "valid_optimisation_path_silently_ignored",
                }:
                    remaining_overdesign_unexplained += 1
                if result["failure_reason"] == "in_target_band_actionable_final_tightening":
                    in_target_band_actionable_final_tightening_count += 1
                if result.get("unnecessary_strengthening"):
                    unnecessary_strengthening_count += 1
                    if result.get("unnecessary_shear_strengthening"):
                        unnecessary_shear_strengthening_count += 1
                    unnecessary_strengthening_cases.append(
                        {
                            "case_id": result["case_id"],
                            "selected_action": result.get("selected_action"),
                            "starting_utilisation": result.get("starting_utilisation"),
                            "final_utilisation": result.get("final_utilisation"),
                            "reason": result.get("strengthening_reason"),
                        }
                    )

            browser.close()

        payload = {
            "base_url": base_url,
            "generated_at": timestamp,
            "cases": results,
            "summary": {
                "total_cases": len(results),
                "configured_total_cases": len(CASES),
                "PASS_count": sum(1 for item in results if item["verdict"] == "PASS"),
                "FAIL_count": sum(1 for item in results if item["verdict"] == "FAIL"),
                "unsafe_accepted_count": unsafe_accepted,
                "below_target_incorrectly_accepted_count": below_target_incorrectly_accepted,
                "practical_blocker_explained_count": practical_blocker_explained,
                "optimisation_applied_count": optimisation_applied_count,
                "remaining_overdesign_unexplained_count": remaining_overdesign_unexplained,
                "in_target_band_actionable_final_tightening_count": in_target_band_actionable_final_tightening_count,
                "unnecessary_strengthening_count": unnecessary_strengthening_count,
                "unnecessary_shear_strengthening_count": unnecessary_shear_strengthening_count,
                "unnecessary_strengthening_cases": unnecessary_strengthening_cases,
            },
        }
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print(f"optimisation_expectation_ladder: {artifact_path}")
        print(f"total cases: {payload['summary']['total_cases']}")
        print(f"PASS count: {payload['summary']['PASS_count']}")
        print(f"FAIL count: {payload['summary']['FAIL_count']}")
        print(f"unsafe accepted count: {payload['summary']['unsafe_accepted_count']}")
        print(
            "below target incorrectly accepted count: "
            f"{payload['summary']['below_target_incorrectly_accepted_count']}"
        )
        print(
            "practical blocker explained count: "
            f"{payload['summary']['practical_blocker_explained_count']}"
        )
        print(f"optimisation applied count: {payload['summary']['optimisation_applied_count']}")
        print(
            "remaining overdesign unexplained count: "
            f"{payload['summary']['remaining_overdesign_unexplained_count']}"
        )
        print(
            "in target band actionable final tightening count: "
            f"{payload['summary']['in_target_band_actionable_final_tightening_count']}"
        )
        print(
            "unnecessary strengthening count: "
            f"{payload['summary']['unnecessary_strengthening_count']}"
        )
        print(
            "unnecessary shear strengthening count: "
            f"{payload['summary']['unnecessary_shear_strengthening_count']}"
        )
        return 0 if payload["summary"]["FAIL_count"] == 0 else 1
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
