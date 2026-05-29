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
    _same_value,
    _wait_for_post_click_state_without_run_end,
    _wait_for_post_publish_alignment,
)
from tools.verification.helpers.overdesign_assertions import (
    assert_no_unresolved_material_overdesign,
    overdesign_debug_from_browser_state,
)


MU_LABEL = "Positive design moment Mu*+ (kNm)"
VU_LABEL = "Design shear Vu* (kN)"
TU_LABEL = "Design torsion Tu* (kNm)"
N_LABEL = "Axial force N* (kN)"
DIRECT_STATE_RECIPE = "CONTRACT_DIRECT_STATE_SEED"

SHEAR_KEYS = {"lig_d", "lig_legs", "s_lig"}
GEOMETRY_KEYS = {"b", "D", "bw", "bf", "tf", "tw", "bf_bot", "tf_bot"}
BOTTOM_KEYS = {
    "bot1_count",
    "db_bot_1",
    "bot2_count",
    "db_bot_2",
    "bot_row_count",
    "bot_row_1_bars",
    "bot_row_1_dia",
    "bot_row_1_spacing",
    "bot_row_2_bars",
    "bot_row_2_dia",
    "bot_row_2_spacing",
    "bot1_layout_mode",
    "bot2_layout_mode",
}


CONTRACT_CASES = [
    {"case_id": "A_BEND_IN_BAND_SHEAR_ZERO", "mu": 35.0, "vu": 0.0, "tu": 0.0, "n": 0.0, "setup_strategy": "direct_state_seed"},
    {"case_id": "B_BEND_IN_BAND_TINY_SHEAR", "mu": 35.0, "vu": 10.0, "tu": 0.0, "n": 0.0, "setup_strategy": "direct_state_seed"},
    {"case_id": "C_BEND_IN_BAND_SMALL_SHEAR", "mu": 35.0, "vu": 50.0, "tu": 0.0, "n": 0.0, "setup_strategy": "direct_state_seed"},
    {"case_id": "D_PURE_SHEAR_LOW_DEMAND", "mu": 0.0, "vu": 150.0, "tu": 0.0, "n": 0.0, "setup_strategy": "direct_state_seed"},
    {"case_id": "E_COMBINED_LOW_DEMAND", "mu": 55.0, "vu": 200.0, "tu": 0.0, "n": 0.0, "setup_strategy": "direct_state_seed"},
    {"case_id": "F_BENDING_ONLY_OVERDESIGN", "mu": 45.0, "vu": 0.0, "tu": 0.0, "n": 0.0, "setup_strategy": "direct_state_seed"},
    {"case_id": "G_COMBINED_OVERDESIGN", "mu": 80.0, "vu": 175.0, "tu": 0.0, "n": 0.0, "setup_strategy": "direct_state_seed"},
    {
        "case_id": "H_ALREADY_EFFICIENT_BENDING",
        "mu": 230.0,
        "vu": 0.0,
        "tu": 0.0,
        "n": 0.0,
        "setup_strategy": "direct_state_seed",
        "seed_recipe": "CONTRACT_DIRECT_STATE_SEED_H_ALREADY_EFFICIENT_BENDING",
    },
]
DEFAULT_CASE_TIMEOUT_S = 120.0


class CaseTimeout(RuntimeError):
    def __init__(self, stage: str, timeout_s: float, last_known_state: dict[str, Any] | None = None):
        super().__init__(f"case timed out at stage {stage} after {timeout_s:.1f}s")
        self.stage = stage
        self.timeout_s = float(timeout_s)
        self.last_known_state = dict(last_known_state or {})


class CaseProgress:
    def __init__(self, case_id: str, timeout_s: float):
        self.case_id = case_id
        self.timeout_s = float(timeout_s)
        self.started_at = time.time()
        self.stage = "case_start"
        self.events: list[dict[str, Any]] = []
        self.last_known_state: dict[str, Any] = {}

    def elapsed(self) -> float:
        return time.time() - self.started_at

    def remaining(self, fallback: float = 1.0) -> float:
        return max(float(fallback), self.timeout_s - self.elapsed())

    def log(self, stage: str, **details: Any) -> None:
        self.stage = stage
        event = {
            "case_id": self.case_id,
            "stage": stage,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_seconds": round(self.elapsed(), 3),
            **details,
        }
        self.events.append(event)
        detail_text = " ".join(f"{k}={v}" for k, v in details.items() if v is not None)
        print(f"[contract] {self.case_id} {stage} +{event['elapsed_seconds']:.1f}s {detail_text}".rstrip(), flush=True)
        self.check()

    def capture_state(self, page) -> None:
        try:
            raw = _load_browser_state(page)
            overview = dict(raw.get("summary_overview_probe") or {})
            guidance = dict(raw.get("guidance_compute_probe") or {})
            self.last_known_state = {
                "summary_overview_probe": {
                    "worst_util": overview.get("worst_util"),
                    "governing_util": overview.get("governing_util"),
                    "governing_check": overview.get("governing_check"),
                    "statuses": dict(overview.get("statuses") or {}),
                    "all_key_pass": overview.get("all_key_pass"),
                },
                "guidance_compute_probe": {
                    "primary_title": guidance.get("primary_title"),
                    "primary_action_type": guidance.get("primary_action_type"),
                    "primary_updates": dict(guidance.get("primary_updates") or {}),
                    "primary_terminal_state": guidance.get("primary_terminal_state"),
                },
            }
        except Exception as exc:
            self.last_known_state = {"state_capture_error": f"{type(exc).__name__}: {exc}"}

    def check(self) -> None:
        if self.elapsed() > self.timeout_s:
            exc = CaseTimeout(self.stage, self.timeout_s, self.last_known_state)
            exc.progress_log = list(self.events)
            raise exc


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _first_guidance_card_text(page) -> str | None:
    selectors = [
        ".fast-guidance-item",
        "[class*='fast-guidance-item']",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                text = locator.inner_text(timeout=2_000)
                text = str(text or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return None


def _button_actionable(page) -> bool:
    try:
        button = page.get_by_role("button", name="Run one-click auto design")
        button.wait_for(timeout=2_000)
        return bool(button.is_visible() and button.is_enabled())
    except Exception:
        return False


def _recommendation_family_from_updates(updates: dict | None) -> str | None:
    upd = dict(updates or {})
    if not upd:
        return None
    keys = set(upd)
    if keys and keys <= SHEAR_KEYS:
        return "shear"
    if keys & SHEAR_KEYS and keys - SHEAR_KEYS:
        return "compound"
    if keys & (GEOMETRY_KEYS | BOTTOM_KEYS):
        return "bending"
    return "other"


def _scan_rejection_fields(data: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)
            key_l = str(key).lower()
            if any(token in key_l for token in ("reject", "filtered", "non_governing", "no_actionable", "stale")):
                out[full_key] = value
            out.update(_scan_rejection_fields(value, full_key))
    elif isinstance(data, list):
        for idx, value in enumerate(data):
            out.update(_scan_rejection_fields(value, f"{prefix}[{idx}]"))
    return out


def _truthy_rejection_value(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip()
    return text not in {"", "0", "0.0", "None", "False", "false", "[]", "{}"}


def _setup_strategy_for_case(case: dict[str, Any]) -> str:
    if bool(case.get("requires_pre_solve")):
        return "solver_prepared_state"
    strategy = str(case.get("setup_strategy") or "direct_state_seed").strip()
    if strategy not in {"direct_state_seed", "solver_prepared_state"}:
        return "direct_state_seed"
    return strategy


def _direct_seed_recipe_for_case(case: dict[str, Any]) -> str:
    return str(case.get("seed_recipe") or DIRECT_STATE_RECIPE)


def _wait_for_recipe(page, recipe_name: str, *, timeout_s: float = 30.0) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        last_state = _load_browser_state(page)
        if str(last_state.get("browser_recipe") or "") == recipe_name and not last_state.get("browser_recipe_error"):
            return last_state, True
        time.sleep(0.3)
    return last_state, False


def _state_changed_materially(pre: dict[str, Any], post: dict[str, Any]) -> bool:
    pre_summary = dict(pre.get("summary") or {})
    post_summary = dict(post.get("summary") or {})
    pre_reinf = dict(pre.get("reinforcement") or {})
    post_reinf = dict(post.get("reinforcement") or {})
    for key in ("worst_util", "governing_util"):
        if not _same_value(pre_summary.get(key), post_summary.get(key), tol=5e-3):
            return True
    for key in ("bot1_count", "db_bot_1", "b", "D", "lig_d", "lig_legs", "s_lig"):
        if not _same_value(pre_reinf.get(key), post_reinf.get(key), tol=5e-3):
            return True
    if str((pre.get("guidance_primary") or {}).get("title") or "").strip() != str(
        (post.get("guidance_primary") or {}).get("title") or ""
    ).strip():
        return True
    return False


def _no_run_end_but_contract_still_satisfied(pre: dict[str, Any], post: dict[str, Any]) -> bool:
    return _state_changed_materially(pre, post)


def _update_probe_mismatches(state: dict[str, Any], updates: dict[str, Any]) -> list[dict[str, Any]]:
    summary_probe = dict(state.get("summary_state_probe") or {})
    shared_probe = dict(state.get("browser_shared_probe") or {})
    active_record = dict(state.get("active_beam_record_probe") or {})
    mismatches: list[dict[str, Any]] = []
    for key, expected in sorted((updates or {}).items()):
        shared_actual = shared_probe.get(key)
        if not _same_value(shared_actual, expected):
            mismatches.append(
                {
                    "probe": "browser_shared_probe",
                    "key": key,
                    "expected": expected,
                    "actual": shared_actual,
                }
            )
        if key in summary_probe and not _same_value(summary_probe.get(key), expected):
            mismatches.append(
                {
                    "probe": "summary_state_probe",
                    "key": key,
                    "expected": expected,
                    "actual": summary_probe.get(key),
                }
            )
        if key in active_record and not _same_value(active_record.get(key), expected):
            mismatches.append(
                {
                    "probe": "active_beam_record_probe",
                    "key": key,
                    "expected": expected,
                    "actual": active_record.get(key),
                }
            )
    return mismatches


def _wait_for_post_click_updates_reflected(
    page,
    updates: dict[str, Any],
    *,
    timeout_s: float,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    if not updates:
        return _load_browser_state(page), True, {"update_reflection_required": False}
    deadline = time.time() + max(0.1, timeout_s)
    last_state: dict[str, Any] = {}
    last_mismatches: list[dict[str, Any]] = []
    polls = 0
    start = time.time()
    while time.time() < deadline:
        polls += 1
        last_state = _load_browser_state(page)
        last_mismatches = _update_probe_mismatches(last_state, updates)
        if not last_mismatches:
            return (
                last_state,
                True,
                {
                    "update_reflection_required": True,
                    "update_reflection_polls": polls,
                    "update_reflection_wait_time_ms": int((time.time() - start) * 1000),
                    "update_reflection_mismatches": [],
                },
            )
        time.sleep(0.35)
    return (
        last_state,
        False,
        {
            "update_reflection_required": True,
            "update_reflection_polls": polls,
            "update_reflection_wait_time_ms": int((time.time() - start) * 1000),
            "update_reflection_mismatches": last_mismatches,
        },
    )


def _capture_state(page) -> dict[str, Any]:
    state = _load_browser_state(page)
    summary_probe = dict(state.get("summary_state_probe") or {})
    overview = dict(state.get("summary_overview_probe") or {})
    guidance = dict(state.get("guidance_compute_probe") or {})
    shared = dict(state.get("browser_shared_probe") or {})
    dg_probe = dict(state.get("design_guide_probe") or {})
    pending_meta = dict(state.get("pending_recommendation_meta") or {})
    utils = dict(overview.get("utils") or {})
    statuses = dict(overview.get("statuses") or {})
    primary_updates = dict(guidance.get("primary_updates") or {})
    return {
        "raw_state": state,
        "summary": {
            "Mu": summary_probe.get("uls_Mstar"),
            "Vu": summary_probe.get("uls_Vstar"),
            "Tu": shared.get("Tu_star"),
            "N": shared.get("uls_Nstar"),
            "worst_util": overview.get("worst_util"),
            "governing_util": overview.get("governing_util"),
            "governing_check": overview.get("governing_check"),
            "governing_family": overview.get("governing_util_source"),
            "utils": utils,
            "statuses": statuses,
            "all_key_pass": overview.get("all_key_pass"),
            "any_fail": overview.get("any_fail"),
            "any_warn": overview.get("any_warn"),
        },
        "reinforcement": {
            "Ast_bot": shared.get("Ast_bot"),
            "bot1_count": summary_probe.get("bot1_count"),
            "db_bot_1": summary_probe.get("db_bot_1"),
            "b": summary_probe.get("b"),
            "D": summary_probe.get("D"),
            "lig_d": summary_probe.get("lig_d"),
            "lig_legs": summary_probe.get("lig_legs"),
            "s_lig": summary_probe.get("s_lig"),
        },
        "guidance_primary": {
            "title": guidance.get("primary_title"),
            "bucket_or_status": guidance.get("primary_status"),
            "action_type": guidance.get("primary_action_type"),
            "visible_text": _first_guidance_card_text(page),
            "actionable_button": _button_actionable(page),
            "updates": primary_updates,
            "button_contract": dict(guidance.get("primary_button_contract") or {}),
            "family": _recommendation_family_from_updates(primary_updates),
            "terminal_state": guidance.get("primary_terminal_state"),
            "guidance_branch": guidance.get("guidance_branch"),
            "selected_action_type": guidance.get("selected_action_type"),
            "selected_title": guidance.get("selected_title"),
            "pending_meta": pending_meta,
        },
        "shared_probe": shared,
        "active_beam_record_probe": dict(state.get("active_beam_record_probe") or {}),
        "guidance_debug_fields": {
            "overview": dict(guidance.get("overview") or {}),
            "efficiency_tightening_state": dict(guidance.get("efficiency_tightening_state") or {}),
            "design_guide_probe": dg_probe,
        },
    }


def _seed_heavy_combined_state(page, progress: CaseProgress) -> dict[str, Any]:
    progress.log("seed_start")
    _apply_live_inputs(page, mu=300.0, vu=400.0)
    progress.capture_state(page)
    progress.log("seed_inputs_applied")
    button = page.get_by_role("button", name="Run one-click auto design")
    button.wait_for(timeout=min(10_000, int(progress.remaining(1.0) * 1000)))
    progress.log("seed_button_status", button_visible=button.is_visible(), button_enabled=button.is_enabled())
    tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
    click_started_ms = int(time.time() * 1000)
    button.click(timeout=10_000)
    progress.log("seed_click_attempted")
    run_end_event, _ = _wait_for_run_end(
        tracer_offset,
        timeout_s=min(45.0, progress.remaining(1.0)),
        start_time_ms=click_started_ms,
    )
    progress.log("seed_run_end_seen", run_end_seen=bool(run_end_event))
    _run_end_data = dict((run_end_event or {}).get("data") or {})
    post_state, aligned, meta = _wait_for_post_publish_alignment(
        page,
        mu=300.0,
        vu=400.0,
        run_end_data=_run_end_data,
        timeout_s=min(45.0, progress.remaining(1.0)),
    )
    progress.capture_state(page)
    progress.log("seed_post_publish_alignment", aligned=bool(aligned))
    return {
        "seed_run_end": run_end_event,
        "seed_aligned": bool(aligned),
        "seed_settle_meta": meta,
        "seed_state": _capture_state(page),
        "post_state": post_state,
    }


def _truth_alignment(run_end_event: dict[str, Any] | None, post_state_raw: dict[str, Any]) -> dict[str, Any]:
    run_data = dict((run_end_event or {}).get("data") or {})
    solver_result = dict(post_state_raw.get("solver_result") or {})
    commit_audit = dict(solver_result.get("one_click_commit_audit") or {})
    displayed_overview = dict(post_state_raw.get("summary_overview_probe") or {})
    displayed_util = displayed_overview.get("worst_util")
    displayed_statuses = dict(displayed_overview.get("statuses") or {})
    run_end_util = run_data.get("final_live_worst_util")
    audit_util = commit_audit.get("post_commit_live_worst_util") or run_data.get("post_commit_live_worst_util")
    run_end_statuses = dict(run_data.get("post_commit_live_statuses") or {})
    audit_statuses = dict(commit_audit.get("post_commit_live_statuses") or run_end_statuses)
    aligned = bool(
        (run_end_util is None or _same_value(run_end_util, displayed_util, tol=5e-3))
        and (audit_util is None or _same_value(audit_util, displayed_util, tol=5e-3))
        and (not run_end_statuses or run_end_statuses == displayed_statuses)
        and (not audit_statuses or audit_statuses == displayed_statuses)
    )
    return {
        "aligned": aligned,
        "run_end_util": run_end_util,
        "post_commit_audit_util": audit_util,
        "published_displayed_util": displayed_util,
        "run_end_statuses": run_end_statuses,
        "post_commit_audit_statuses": audit_statuses,
        "published_displayed_statuses": displayed_statuses,
    }


def _verdict_for_case(
    *,
    case: dict[str, Any],
    pre: dict[str, Any],
    post: dict[str, Any],
    click_attempted: bool,
    run_end_event: dict[str, Any] | None,
    click_error: str | None,
    post_publish_aligned: bool,
) -> tuple[str, str | None, dict[str, int]]:
    counters = {
        "actionable_rejected_click": 0,
        "non_governing_cleanup_rejection": 0,
        "no_actionable_candidates": 0,
        "source_action_type_mismatch": 0,
        "misleading_best_available_out_of_band_candidate": 0,
    }
    pre_primary = dict(pre.get("guidance_primary") or {})
    post_primary = dict(post.get("guidance_primary") or {})
    pre_summary = dict(pre.get("summary") or {})
    run_data = dict((run_end_event or {}).get("data") or {})
    compare = dict(run_data.get("compare") or {})
    final_updates = dict(compare.get("final_updates") or {})
    stop_reason = str(run_data.get("stop_reason") or "").strip()
    winner_label = str(compare.get("winner_label") or "").strip() or None
    guidance_action_type = str(pre_primary.get("action_type") or "").strip() or None
    guidance_family = str(pre_primary.get("family") or "").strip() or None
    run_family = _recommendation_family_from_updates(final_updates)
    actionable = bool(pre_primary.get("actionable_button")) and bool(guidance_action_type)
    rejection_fields = _scan_rejection_fields(
        {
            "run_end": run_data,
            "post_feedback": (post.get("raw_state") or {}).get("one_click_feedback"),
            "post_solver_result": (post.get("raw_state") or {}).get("solver_result"),
            "post_design_guide_probe": ((post.get("raw_state") or {}).get("design_guide_probe") or {}),
        }
    )

    if not actionable:
        terminal = str(pre_primary.get("terminal_state") or "").strip()
        if terminal in {"optimal", "very_low_demand"} or not pre_primary.get("visible_text"):
            return "PASS", None, counters
        return "PASS", None, counters

    if click_error:
        counters["actionable_rejected_click"] += 1
        return "FAIL", f"click_error:{click_error}", counters

    if click_attempted and not run_end_event:
        if _no_run_end_but_contract_still_satisfied(pre, post):
            return "PASS", None, counters
        counters["actionable_rejected_click"] += 1
        return "FAIL", "clicked_actionable_card_but_no_run_end", counters

    if stop_reason in {"no_actionable_candidates", "no_actionable_candidates_after_full_tightening_search"}:
        counters["actionable_rejected_click"] += 1
        counters["no_actionable_candidates"] += 1
        return "FAIL", stop_reason, counters

    if any("non_governing_cleanup" in k.lower() and _truthy_rejection_value(v) for k, v in rejection_fields.items()):
        counters["actionable_rejected_click"] += 1
        counters["non_governing_cleanup_rejection"] += 1
        return "FAIL", "rejected_as_non_governing_cleanup", counters

    if any("filtered" in k.lower() and _truthy_rejection_value(v) for k, v in rejection_fields.items()):
        counters["actionable_rejected_click"] += 1
        return "FAIL", "all_candidates_filtered_out", counters

    if any("stale" in k.lower() and _truthy_rejection_value(v) for k, v in rejection_fields.items()):
        return "FAIL", "stale_state_issue", counters

    if not final_updates:
        post_terminal = str(post_primary.get("terminal_state") or "").strip()
        post_text = str(post_primary.get("visible_text") or "").lower()
        if post_terminal in {"optimal", "very_low_demand"} or "no changes needed" in post_text or "already efficient" in post_text:
            return "PASS", None, counters
        counters["actionable_rejected_click"] += 1
        return "FAIL", "actionable_card_disappeared_without_commit_or_clear_reason", counters

    if guidance_action_type and run_family and guidance_family and guidance_family != "compound" and run_family not in {guidance_family, "compound"}:
        counters["source_action_type_mismatch"] += 1
        return "FAIL", "source_action_type_mismatch", counters

    if guidance_family in {"bending", "shear"} and run_family == "compound":
        reasons = " ".join(
            [
                str(pre_primary.get("title") or ""),
                str(pre_primary.get("visible_text") or ""),
                str(winner_label or ""),
            ]
        ).lower()
        if "compound" not in reasons and "geometry and shear" not in reasons and "rebalance" not in reasons:
            counters["source_action_type_mismatch"] += 1
            return "FAIL", "unexplained_compound_logic", counters

    if (
        "target band" in str(pre_primary.get("visible_text") or "").lower()
        and stop_reason == "best_available_out_of_band_candidate"
    ):
        counters["misleading_best_available_out_of_band_candidate"] += 1
        return "FAIL", "misleading_best_available_out_of_band_candidate", counters

    if not post_publish_aligned:
        return "FAIL", "truth_layer_mismatch_after_valid_run", counters

    return "PASS", None, counters


def _empty_counters() -> dict[str, int]:
    return {
        "actionable_rejected_click": 0,
        "non_governing_cleanup_rejection": 0,
        "no_actionable_candidates": 0,
        "source_action_type_mismatch": 0,
        "misleading_best_available_out_of_band_candidate": 0,
    }


def _timeout_result(case: dict[str, Any], exc: CaseTimeout) -> dict[str, Any]:
    setup_strategy = _setup_strategy_for_case(case)
    return {
        "case_id": case["case_id"],
        "browser_mode": "browser_live",
        "setup_strategy": setup_strategy,
        "requires_pre_solve": bool(case.get("requires_pre_solve")),
        "setup_duration_seconds": None,
        "actual_contract_duration_seconds": None,
        "total_case_duration_seconds": float(exc.timeout_s),
        "progress_log": list(getattr(exc, "progress_log", []) or []),
        "case_duration_seconds": float(exc.timeout_s),
        "timeout_stage": exc.stage,
        "timeout_seconds": exc.timeout_s,
        "last_known_state": dict(exc.last_known_state or {}),
        "inputs": {
            "Mu": case["mu"],
            "Vu": case["vu"],
            "Tu": case["tu"],
            "N": case["n"],
        },
        "pre_click_summary": {},
        "pre_click_guidance_primary": {},
        "pre_click_reinforcement": {},
        "pre_click_actionable": False,
        "pre_click_guidance_debug_fields": {},
        "pre_click_settle_meta": {},
        "click_attempted": False,
        "run_end_present": False,
        "run_end_stop_reason": None,
        "run_end_winner_label": None,
        "final_updates": {},
        "rejected_candidate_counters_reasons": {},
        "post_click_summary": {},
        "post_click_guidance_primary": {},
        "post_click_reinforcement": {},
        "post_click_guidance_debug_fields": {},
        "post_click_settle_meta": {},
        "stale_state_flags": {"timeout_stage": exc.stage},
        "truth_layer_alignment": {"aligned": False},
        "verdict": "FAIL",
        "failure_reason": f"case_timeout:{exc.stage}",
        "debug_snapshot": {
            "timeout_stage": exc.stage,
            "timeout_seconds": exc.timeout_s,
            "last_known_state": dict(exc.last_known_state or {}),
        },
        "summary_counts": _empty_counters(),
    }


def _exception_result(case: dict[str, Any], exc: Exception, stage: str = "case_exception") -> dict[str, Any]:
    setup_strategy = _setup_strategy_for_case(case)
    return {
        "case_id": case["case_id"],
        "browser_mode": "browser_live",
        "setup_strategy": setup_strategy,
        "requires_pre_solve": bool(case.get("requires_pre_solve")),
        "setup_duration_seconds": None,
        "actual_contract_duration_seconds": None,
        "total_case_duration_seconds": None,
        "progress_log": [],
        "case_duration_seconds": None,
        "timeout_stage": stage,
        "timeout_seconds": None,
        "last_known_state": {},
        "inputs": {
            "Mu": case["mu"],
            "Vu": case["vu"],
            "Tu": case["tu"],
            "N": case["n"],
        },
        "pre_click_summary": {},
        "pre_click_guidance_primary": {},
        "pre_click_reinforcement": {},
        "pre_click_actionable": False,
        "pre_click_guidance_debug_fields": {},
        "pre_click_settle_meta": {},
        "click_attempted": False,
        "run_end_present": False,
        "run_end_stop_reason": None,
        "run_end_winner_label": None,
        "final_updates": {},
        "rejected_candidate_counters_reasons": {},
        "post_click_summary": {},
        "post_click_guidance_primary": {},
        "post_click_reinforcement": {},
        "post_click_guidance_debug_fields": {},
        "post_click_settle_meta": {},
        "stale_state_flags": {"exception": f"{type(exc).__name__}: {exc}"},
        "truth_layer_alignment": {"aligned": False},
        "verdict": "FAIL",
        "failure_reason": f"case_exception:{type(exc).__name__}:{exc}",
        "debug_snapshot": {"exception": f"{type(exc).__name__}: {exc}"},
        "summary_counts": _empty_counters(),
    }


def _stage_timeout_result(
    case: dict[str, Any],
    *,
    stage: str,
    timeout_s: float,
    last_known_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exc = CaseTimeout(stage, timeout_s, last_known_state)
    return _timeout_result(case, exc)


def _run_case(page, case: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
    progress = CaseProgress(str(case["case_id"]), timeout_s)
    setup_strategy = _setup_strategy_for_case(case)
    setup_start = time.time()
    progress.log("case_start")
    if setup_strategy == "solver_prepared_state":
        seed_info = _seed_heavy_combined_state(page, progress)
    else:
        progress.log("direct_state_seed_ready", recipe=_direct_seed_recipe_for_case(case))
        seed_info = {
            "seed_run_end": None,
            "seed_aligned": True,
            "seed_settle_meta": {},
            "seed_state": _capture_state(page),
            "post_state": _load_browser_state(page),
        }
    pre_state_raw, pre_settle_meta = _apply_live_inputs(page, mu=float(case["mu"]), vu=float(case["vu"]))
    progress.capture_state(page)
    progress.log("inputs_applied")
    pre = _capture_state(page)
    setup_duration = time.time() - setup_start
    actual_start = time.time()
    progress.log(
        "pre_click_state_captured",
        actionable=bool(pre["guidance_primary"]["actionable_button"]),
        title=pre["guidance_primary"].get("title"),
    )

    click_attempted = False
    click_error = None
    run_end_event = None
    post_state_raw = pre_state_raw
    post_settle_meta: dict[str, Any] = {}
    post_publish_aligned = False

    if bool(pre["guidance_primary"]["actionable_button"]):
        click_attempted = True
        try:
            button = page.get_by_role("button", name="Run one-click auto design")
            button.wait_for(timeout=min(5_000, int(progress.remaining(1.0) * 1000)))
            progress.log("button_actionability_status", button_visible=button.is_visible(), button_enabled=button.is_enabled())
            tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
            click_started_ms = int(time.time() * 1000)
            button.click(timeout=10_000)
            progress.log("click_attempted")
            run_end_event, _ = _wait_for_run_end(
                tracer_offset,
                timeout_s=min(45.0, progress.remaining(1.0)),
                start_time_ms=click_started_ms,
            )
            run_end_data = dict((run_end_event or {}).get("data") or {})
            progress.log("run_end_seen", run_end_seen=bool(run_end_event))
            if run_end_data:
                post_state_raw, post_publish_aligned, post_settle_meta = _wait_for_post_publish_alignment(
                    page,
                    mu=float(case["mu"]),
                    vu=float(case["vu"]),
                    run_end_data=run_end_data,
                    timeout_s=min(45.0, progress.remaining(1.0)),
                )
                expected_updates = dict((run_end_data.get("compare") or {}).get("final_updates") or {})
                if expected_updates:
                    post_state_raw, updates_reflected, update_reflection_meta = _wait_for_post_click_updates_reflected(
                        page,
                        expected_updates,
                        timeout_s=min(30.0, progress.remaining(1.0)),
                    )
                    post_publish_aligned = bool(post_publish_aligned and updates_reflected)
                    post_settle_meta = {
                        **dict(post_settle_meta or {}),
                        **dict(update_reflection_meta or {}),
                    }
                progress.capture_state(page)
                progress.log("post_publish_alignment", aligned=bool(post_publish_aligned))
            else:
                post_state_raw, post_publish_aligned, post_settle_meta = _wait_for_post_click_state_without_run_end(
                    page,
                    mu=float(case["mu"]),
                    vu=float(case["vu"]),
                    pre_state=pre_state_raw,
                    timeout_s=min(45.0, progress.remaining(1.0)),
                )
                progress.capture_state(page)
                progress.log("post_click_without_run_end_alignment", aligned=bool(post_publish_aligned))
        except PlaywrightTimeoutError as exc:
            click_error = f"{type(exc).__name__}: {exc}"
            progress.log("click_or_wait_timeout", click_error=click_error)
    else:
        progress.log("click_skipped", actionable=False)

    post = _capture_state(page)
    progress.capture_state(page)
    progress.log("post_click_state_captured")
    actual_duration = time.time() - actual_start
    alignment = _truth_alignment(run_end_event, post["raw_state"])
    verdict, failure_reason, counters = _verdict_for_case(
        case=case,
        pre=pre,
        post=post,
        click_attempted=click_attempted,
        run_end_event=run_end_event,
        click_error=click_error,
        post_publish_aligned=bool(alignment["aligned"]),
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
    if material_overdesign_audit_failures and verdict == "PASS":
        verdict = "FAIL"
        failure_reason = material_overdesign_audit_failures[0]

    run_data = dict((run_end_event or {}).get("data") or {})
    compare = dict(run_data.get("compare") or {})
    debug_snapshot = None
    if verdict == "FAIL":
        debug_snapshot = {
            "run_end_event": run_end_event,
            "solver_debug": ((post["raw_state"] or {}).get("solver_result") or {}).get("one_click_solver_debug"),
            "publish_debug": {
                "auto_design_entry_before_reconcile": (post["raw_state"] or {}).get("auto_design_entry_probe_before_reconcile"),
                "auto_design_entry_after_reconcile": (post["raw_state"] or {}).get("auto_design_entry_probe_after_reconcile"),
                "auto_design_entry_after_run": (post["raw_state"] or {}).get("auto_design_entry_probe_after_run"),
                "design_guide_probe": (post["raw_state"] or {}).get("design_guide_probe"),
            },
            "rejection_fields": _scan_rejection_fields(
                {
                    "run_end": run_data,
                    "solver_result": (post["raw_state"] or {}).get("solver_result"),
                    "one_click_feedback": (post["raw_state"] or {}).get("one_click_feedback"),
                    "design_guide_probe": (post["raw_state"] or {}).get("design_guide_probe"),
                }
            ),
        }

    return {
        "case_id": case["case_id"],
        "browser_mode": "browser_live",
        "setup_strategy": setup_strategy,
        "requires_pre_solve": bool(case.get("requires_pre_solve")),
        "setup_duration_seconds": round(setup_duration, 3),
        "actual_contract_duration_seconds": round(actual_duration, 3),
        "total_case_duration_seconds": round(progress.elapsed(), 3),
        "progress_log": list(progress.events),
        "case_duration_seconds": round(progress.elapsed(), 3),
        "timeout_stage": None,
        "timeout_seconds": None,
        "last_known_state": dict(progress.last_known_state),
        "seed": {
            "kind": "heavy_combined_seed",
            "snapshot": seed_info["seed_state"],
        },
        "inputs": {
            "Mu": case["mu"],
            "Vu": case["vu"],
            "Tu": case["tu"],
            "N": case["n"],
        },
        "pre_click_summary": pre["summary"],
        "pre_click_guidance_primary": pre["guidance_primary"],
        "pre_click_reinforcement": pre["reinforcement"],
        "pre_click_shared_probe": pre["shared_probe"],
        "pre_click_active_beam_record_probe": pre["active_beam_record_probe"],
        "pre_click_actionable": bool(pre["guidance_primary"]["actionable_button"]),
        "pre_click_guidance_debug_fields": pre["guidance_debug_fields"],
        "pre_click_settle_meta": pre_settle_meta,
        "click_attempted": click_attempted,
        "run_end_present": bool(run_end_event),
        "run_end_stop_reason": run_data.get("stop_reason"),
        "run_end_winner_label": compare.get("winner_label"),
        "final_updates": dict(compare.get("final_updates") or {}),
        "rejected_candidate_counters_reasons": _scan_rejection_fields(
            {
                "run_end": run_data,
                "solver_result": (post["raw_state"] or {}).get("solver_result"),
                "one_click_feedback": (post["raw_state"] or {}).get("one_click_feedback"),
                "design_guide_probe": (post["raw_state"] or {}).get("design_guide_probe"),
            }
        ),
        "post_click_summary": post["summary"],
        "post_click_guidance_primary": post["guidance_primary"],
        "post_click_reinforcement": post["reinforcement"],
        "post_click_shared_probe": post["shared_probe"],
        "post_click_active_beam_record_probe": post["active_beam_record_probe"],
        "post_click_guidance_debug_fields": post["guidance_debug_fields"],
        "post_click_settle_meta": post_settle_meta,
        "stale_state_flags": {
            "click_error": click_error,
            "guidance_probe_error": pre["guidance_debug_fields"]["design_guide_probe"].get("debug_bundle", {}).get("_probe_error")
            if isinstance(pre["guidance_debug_fields"].get("design_guide_probe"), dict)
            else None,
        },
        "truth_layer_alignment": alignment,
        "verdict": verdict,
        "failure_reason": failure_reason,
        "material_overdesign_audit_failures": material_overdesign_audit_failures,
        "debug_snapshot": debug_snapshot,
        "summary_counts": counters,
    }


def _build_payload(
    *,
    base_url: str,
    timestamp: str,
    results: list[dict[str, Any]],
    active_case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    count_actionable_rejected = 0
    count_non_governing_cleanup = 0
    count_no_actionable = 0
    count_source_mismatch = 0
    count_misleading_best_available = 0
    for result in results:
        if result["verdict"] == "FAIL" and result.get("pre_click_actionable"):
            count_actionable_rejected += 1
        if result.get("failure_reason") == "rejected_as_non_governing_cleanup":
            count_non_governing_cleanup += 1
        if result.get("failure_reason") == "no_actionable_candidates":
            count_no_actionable += 1
        if result.get("failure_reason") in {"source_action_type_mismatch", "unexplained_compound_logic"}:
            count_source_mismatch += 1
        if result.get("failure_reason") == "misleading_best_available_out_of_band_candidate":
            count_misleading_best_available += 1
    timeout_cases = [item for item in results if item.get("timeout_stage")]
    first_timeout = timeout_cases[0] if timeout_cases else {}
    return {
        "base_url": base_url,
        "generated_at": timestamp,
        "active_case": active_case,
        "cases": results,
        "summary": {
            "total_cases": len(results),
            "configured_total_cases": len(CONTRACT_CASES),
            "PASS_count": sum(1 for item in results if item["verdict"] == "PASS"),
            "FAIL_count": sum(1 for item in results if item["verdict"] == "FAIL"),
            "timeout_count": len(timeout_cases),
            "first_timeout_case": first_timeout.get("case_id"),
            "first_timeout_stage": first_timeout.get("timeout_stage"),
            "setup_strategies": {
                strategy: sum(1 for item in results if item.get("setup_strategy") == strategy)
                for strategy in sorted({str(item.get("setup_strategy") or "") for item in results if item.get("setup_strategy")})
            },
            "total_duration_seconds": round(
                sum(float(item.get("total_case_duration_seconds") or item.get("case_duration_seconds") or 0.0) for item in results),
                3,
            ),
            "cases_with_actionable_card_but_rejected_click": count_actionable_rejected,
            "cases_with_non_governing_cleanup_rejection": count_non_governing_cleanup,
            "cases_with_no_actionable_candidates": count_no_actionable,
            "cases_with_source_action_type_mismatch": count_source_mismatch,
            "cases_with_misleading_best_available_out_of_band_candidate": count_misleading_best_available,
        },
    }


def _write_partial_artifact(
    artifact_path: Path,
    *,
    base_url: str,
    timestamp: str,
    results: list[dict[str, Any]],
    active_case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _build_payload(base_url=base_url, timestamp=timestamp, results=results, active_case=active_case)
    artifact_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8523)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--case-timeout-s", type=float, default=DEFAULT_CASE_TIMEOUT_S)
    parser.add_argument("--case", action="append", dest="case_ids", default=None)
    parser.add_argument("--cases", default=None, help="Comma-separated case_id list.")
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args(argv)

    all_case_ids = [str(case.get("case_id") or "") for case in CONTRACT_CASES]
    if args.list_cases:
        print("\n".join(all_case_ids))
        return 0
    requested_case_ids = {
        str(case_id).strip()
        for case_id in (args.case_ids or [])
        if str(case_id).strip()
    }
    requested_case_ids.update(
        str(case_id).strip()
        for case_id in str(args.cases or "").split(",")
        if str(case_id).strip()
    )
    selected_cases = [
        case
        for case in CONTRACT_CASES
        if not requested_case_ids or str(case.get("case_id") or "") in requested_case_ids
    ]
    missing_case_ids = sorted(requested_case_ids - set(all_case_ids))
    if missing_case_ids:
        raise SystemExit(f"Unknown recommendation contract case(s): {', '.join(missing_case_ids)}")

    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_dir = REPO_ROOT / "artifacts" / "verification" / "latest"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"recommendation_contract_ladder_{timestamp}.json"
    results: list[dict[str, Any]] = []
    try:
        if args.base_url is None:
            print(f"[contract] app_starting port={args.port}", flush=True)
            process = _start_streamlit(args.port)
            print(f"[contract] app_ready base_url={base_url}", flush=True)
        else:
            print(f"[contract] waiting_for_existing_app base_url={base_url}", flush=True)
            _wait_for_http(base_url)
            print(f"[contract] app_ready base_url={base_url}", flush=True)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            print("[contract] browser_launched", flush=True)

            for case in selected_cases:
                setup_strategy = _setup_strategy_for_case(case)
                active_case = {
                    "case_id": case["case_id"],
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "stage": "context_start",
                    "setup_strategy": setup_strategy,
                    "requires_pre_solve": bool(case.get("requires_pre_solve")),
                }
                _write_partial_artifact(
                    artifact_path,
                    base_url=base_url,
                    timestamp=timestamp,
                    results=results,
                    active_case=active_case,
                )
                context = browser.new_context()
                page = context.new_page()
                try:
                    active_case["stage"] = "page_goto"
                    active_case["stage_started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    _write_partial_artifact(
                        artifact_path,
                        base_url=base_url,
                        timestamp=timestamp,
                        results=results,
                        active_case=active_case,
                    )
                    query = {"page": "inputs"}
                    if setup_strategy == "direct_state_seed":
                        query["browser_recipe"] = _direct_seed_recipe_for_case(case)
                    page.goto(
                        _query(base_url, query),
                        wait_until="domcontentloaded",
                        timeout=min(60_000, int(args.case_timeout_s * 1000)),
                    )
                    print(f"[contract] {case['case_id']} reached_page", flush=True)
                    active_case["stage"] = "browser_state_wait"
                    active_case["stage_started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    _write_partial_artifact(
                        artifact_path,
                        base_url=base_url,
                        timestamp=timestamp,
                        results=results,
                        active_case=active_case,
                    )
                    page.get_by_label("Browser state").wait_for(
                        state="attached",
                        timeout=min(120_000, int(args.case_timeout_s * 1000)),
                    )
                    print(f"[contract] {case['case_id']} browser_state_attached", flush=True)
                    if setup_strategy == "direct_state_seed":
                        active_case["stage"] = "direct_recipe_wait"
                        active_case["stage_started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        _write_partial_artifact(
                            artifact_path,
                            base_url=base_url,
                            timestamp=timestamp,
                            results=results,
                            active_case=active_case,
                        )
                        direct_seed_recipe = _direct_seed_recipe_for_case(case)
                        recipe_state, recipe_ok = _wait_for_recipe(page, direct_seed_recipe, timeout_s=min(20.0, args.case_timeout_s))
                        if not recipe_ok:
                            raise CaseTimeout(
                                "direct_recipe_wait",
                                args.case_timeout_s,
                                {
                                    "browser_recipe": recipe_state.get("browser_recipe"),
                                    "browser_recipe_error": recipe_state.get("browser_recipe_error"),
                                    "browser_shared_probe": dict(recipe_state.get("browser_shared_probe") or {}),
                                },
                            )
                        print(f"[contract] {case['case_id']} direct_recipe_ready", flush=True)
                    result = _run_case(page, case, timeout_s=args.case_timeout_s)
                except CaseTimeout as exc:
                    print(f"[contract] {case['case_id']} timeout stage={exc.stage} seconds={exc.timeout_s}", flush=True)
                    result = _timeout_result(case, exc)
                except PlaywrightTimeoutError as exc:
                    stage = str(active_case.get("stage") or "browser_wait")
                    print(f"[contract] {case['case_id']} timeout stage={stage} exception={exc}", flush=True)
                    result = _stage_timeout_result(
                        case,
                        stage=stage,
                        timeout_s=args.case_timeout_s,
                        last_known_state={"playwright_timeout": f"{type(exc).__name__}: {exc}"},
                    )
                except Exception as exc:
                    print(f"[contract] {case['case_id']} exception {type(exc).__name__}: {exc}", flush=True)
                    result = _exception_result(case, exc)
                finally:
                    context.close()
                results.append(result)
                _write_partial_artifact(
                    artifact_path,
                    base_url=base_url,
                    timestamp=timestamp,
                    results=results,
                    active_case=None,
                )

            browser.close()

        payload = _write_partial_artifact(
            artifact_path,
            base_url=base_url,
            timestamp=timestamp,
            results=results,
            active_case=None,
        )

        print(f"recommendation_contract_ladder: {artifact_path}")
        print(f"total cases: {payload['summary']['total_cases']}")
        print(f"PASS count: {payload['summary']['PASS_count']}")
        print(f"FAIL count: {payload['summary']['FAIL_count']}")
        print(f"timeout count: {payload['summary']['timeout_count']}")
        print(f"first timeout case: {payload['summary']['first_timeout_case']}")
        print(f"first timeout stage: {payload['summary']['first_timeout_stage']}")
        print(f"setup strategies: {payload['summary']['setup_strategies']}")
        print(f"total duration seconds: {payload['summary']['total_duration_seconds']}")
        print(
            "cases with actionable card but rejected click: "
            f"{payload['summary']['cases_with_actionable_card_but_rejected_click']}"
        )
        print(
            "cases with non_governing_cleanup rejection: "
            f"{payload['summary']['cases_with_non_governing_cleanup_rejection']}"
        )
        print(
            "cases with no_actionable_candidates: "
            f"{payload['summary']['cases_with_no_actionable_candidates']}"
        )
        print(
            "cases with source/action_type mismatch: "
            f"{payload['summary']['cases_with_source_action_type_mismatch']}"
        )
        print(
            "cases with misleading best_available_out_of_band_candidate: "
            f"{payload['summary']['cases_with_misleading_best_available_out_of_band_candidate']}"
        )
        return 0 if int(payload["summary"].get("FAIL_count") or 0) == 0 else 1
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
