"""Design Guide presentation-state coordination for the Inputs page."""

from __future__ import annotations

from typing import Any


_PRESENTATION_STATE_DEPENDENCIES: tuple[str, ...] = (
    "DESIGN_GUIDE_INTENTS",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD",
    "TARGET_BAND_EPS",
    "st",
    "_derive_design_guide_guidance_intent",
    "_design_guide_display_truth_for_item",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_guidance_governing_primary_action",
    "_is_in_target_zone_with_eps",
    "_current_design_guide_fail_fingerprint",
    "_design_guide_fail_fingerprints_equivalent",
    "_one_click_feedback_cta_state",
    "_recommendation_blocked_reason",
    "_recommendation_commit_eligible",
    "_ONE_CLICK_CTA_BLOCKING_REASONS",
    "is_unnecessarily_overdesigned",
)


def bind_presentation_state_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRESENTATION_STATE_DEPENDENCIES
            if name in namespace
        }
    )


def _latest_solver_result_cta_state(overview: dict | None) -> dict:
    """
    Presentation-layer guard based on the latest one-click solver result.

    This is intentionally separate from `_one_click_run_feedback` so a blocked solver result
    cannot be visually overwritten by a freshly rebuilt guidance card in the next render.
    """
    result = st.session_state.get("_solver_result")
    if not isinstance(result, dict):
        return {
            "status": "",
            "reason": "",
            "matches_current_state": False,
            "current_fail_fingerprint": {},
            "result_fail_fingerprint": {},
        }

    status = str(result.get("status") or st.session_state.get("auto_design_status") or "").strip()
    stop_reason = str(result.get("stop_reason") or "").strip()
    envelope = dict(result.get("recommendation_envelope") or {})
    blocked_reason = str(envelope.get("blocked_reason") or stop_reason or "").strip()
    commit_eligible = bool(envelope.get("commit_eligible"))

    if commit_eligible:
        return {
            "status": status,
            "reason": blocked_reason,
            "matches_current_state": False,
            "current_fail_fingerprint": {},
            "result_fail_fingerprint": {},
        }

    if blocked_reason not in _ONE_CLICK_CTA_BLOCKING_REASONS and status not in {
        "blocked",
        "no_action",
        "no_actionable_full_coverage_candidate",
        "rejected",
    }:
        return {
            "status": status,
            "reason": blocked_reason,
            "matches_current_state": False,
            "current_fail_fingerprint": {},
            "result_fail_fingerprint": {},
        }

    result_dbg = dict(result.get("one_click_solver_debug") or {})
    result_fp = dict(result_dbg.get("current_fail_fingerprint") or {})
    current_fp = _current_design_guide_fail_fingerprint(overview)
    fingerprints_match = bool(
        result_fp
        and (
            result_fp == current_fp
            or _design_guide_fail_fingerprints_equivalent(result_fp, current_fp)
        )
    )

    return {
        "status": status,
        "reason": blocked_reason,
        "matches_current_state": bool(fingerprints_match),
        "current_fail_fingerprint": dict(current_fp),
        "result_fail_fingerprint": dict(result_fp),
    }


def _build_design_guide_presentation_state(
    *,
    primary_item: dict | None,
    overview: dict | None,
    efficiency_state: dict | None,
    disp_state: dict,
    mode_config: dict | None,
    recommendation_result: dict | None = None,
    pending_recommendation: dict | None = None,
) -> dict:
    """
    Design Guide presentation contract (product rules - do not regress without explicit review).

    - fail beats everything
    - warn / near-limit beats healthy (including utilisation at the upper guidance threshold while
      checks still PASS)
    - healthy means:
        all_key_pass
        no fail
        no warn
        in target band
        not unnecessarily overdesigned
    - efficiency means safe but materially overdesigned
    - the primary recommendation is rendered in one card only (callers must not duplicate titles /
      change lines outside this surface)
    - this function controls card and apply button theme (css_bucket, use_success_style); it does
      not change recommendation semantics or apply payloads

    Evaluation order: fail -> warn -> healthy -> efficiency -> info.
    """
    _ = (overview, efficiency_state, disp_state, mode_config, recommendation_result, pending_recommendation)
    item = dict(primary_item or {})
    if not item:
        return {}

    truth = dict(item.get("display_truth") or {})
    headline = str(item.get("title_main") or item.get("title") or "Design guidance").strip()
    subtext = str(
        item.get("guidance_why_text_compact")
        or item.get("guidance_why")
        or item.get("reason")
        or item.get("body")
        or ""
    ).strip()
    guidance_intent = str(item.get("guidance_intent") or "").strip()
    displayed_status = str(
        truth.get("displayed_status")
        or item.get("status")
        or item.get("critical_status")
        or ""
    ).strip().upper()
    if guidance_intent == "specific_blocker" or displayed_status in {"FAIL", "FAILED", "BLOCKED", "ERROR"}:
        css_bucket = "fail"
    elif displayed_status in {"WARN", "WARNING", "NEAR_LIMIT"}:
        css_bucket = "warn"
    elif displayed_status in {"PASS", "OK", "OPTIMAL", "EFFICIENCY"}:
        css_bucket = "pass"
    else:
        css_bucket = str(item.get("bucket") or "info").strip().lower() or "info"

    return {
        "headline": headline,
        "subtext": subtext,
        "css_bucket": css_bucket,
        "use_success_style": bool(
            guidance_intent == "already_efficient"
            and css_bucket == "pass"
        ),
        "guidance_intent": guidance_intent or None,
        "design_guide_terminal_state": item.get("design_guide_terminal_state"),
        "display_truth_source": truth.get("display_truth_source"),
        "displayed_util": truth.get("displayed_util"),
        "displayed_status": truth.get("displayed_status"),
        "displayed_within_target_band": truth.get("displayed_within_target_band"),
        "target_low": truth.get("target_low"),
        "target_high": truth.get("target_high"),
        "source_summary_util": truth.get("source_summary_util"),
        "source_candidate_util": truth.get("source_candidate_util"),
        "source_post_commit_util": truth.get("source_post_commit_util"),
        "presentation_source": "authoritative_primary_item",
    }
