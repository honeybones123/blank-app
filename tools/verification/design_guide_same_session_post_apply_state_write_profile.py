"""Same-session post-Apply state-write profile for Inputs smoothness.

Proof-only browser/live verifier. It applies the current Design Guide action,
then triggers a same-session Streamlit rerun without changing inputs. The goal
is to prove whether post-Apply state writes leave stale pending flags or cause
stable-authority rebuild churn before any product patch is attempted.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_smoothness_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _extract_counter_metrics,
    _extract_latest_design_guide_timing,
    _query,
    _run_live_scenario,
)
from tools.verification.design_guide_rerun_trigger_source_profile import (  # noqa: E402
    _dom_snapshot,
    _state_summary,
)
from tools.verification.design_guide_same_session_no_change_rerun_profile import (  # noqa: E402
    _click_streamlit_rerun,
    _load_browser_state_prefer_final_debug,
    _wait_for_full_publication_state,
    _wait_for_streamlit_idle,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _compact(value: Any, *, depth: int = 4, max_items: int = 18) -> Any:
    if depth <= 0:
        if isinstance(value, (dict, list, tuple, set)):
            return f"<{type(value).__name__}>"
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                out["..."] = f"{len(value) - max_items} more"
                break
            out[str(key)] = _compact(item, depth=depth - 1, max_items=max_items)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [_compact(item, depth=depth - 1, max_items=max_items) for item in seq[:max_items]]
        if len(seq) > max_items:
            out.append(f"... {len(seq) - max_items} more")
        return out
    return value


def _candidate_count(summary: dict[str, Any]) -> int:
    return int((summary.get("candidate_evaluation") or {}).get("count") or 0)


def _delta(after: Any, before: Any) -> int:
    try:
        return max(0, int(after or 0) - int(before or 0))
    except Exception:
        return 0


def _summarise_state(state: dict[str, Any], *, recipe: str, label: str) -> dict[str, Any]:
    timing = _extract_latest_design_guide_timing(state)
    counters = _extract_counter_metrics(state)
    source = _state_summary(state, label=label, recipe=recipe)
    return {
        "label": label,
        "rerun_seq": timing.get("rerun_seq"),
        "event_count": timing.get("event_count"),
        "trace_path": timing.get("trace_path"),
        "results_version": source.get("results_version"),
        "final_publication_hash": counters.get("final_publication_hash"),
        "final_publication_display_hash": counters.get("final_publication_display_hash"),
        "final_publication_cta_hash": counters.get("final_publication_cta_hash"),
        "button_contract_hash": counters.get("button_contract_hash"),
        "apply_payload_hash": counters.get("apply_payload_hash"),
        "candidate_evaluation": dict(counters.get("candidate_evaluation") or {}),
        "publication_rebuild_count": counters.get("publication_rebuild_count"),
        "card_render_model_rebuild_count": counters.get("card_render_model_rebuild_count"),
        "publication_stamp_bypass_count": counters.get("publication_stamp_bypass_count"),
        "card_render_model_bypass_count": counters.get("card_render_model_bypass_count"),
        "session_debug_stamp_count": counters.get("session_debug_stamp_count"),
        "stable_render_reuse_trace": _compact(counters.get("stable_render_reuse_trace") or {}, depth=3, max_items=10),
        "summary_card_html_bypass_debug": _compact(
            (source.get("summary_card_html_bypass_debug") or {}),
            depth=3,
            max_items=10,
        ),
        "summary_card_html_cache_probe": _compact(
            (source.get("summary_card_html_cache_probe") or {}),
            depth=3,
            max_items=10,
        ),
        "pending_flags": dict(source.get("pending_flags") or {}),
        "any_pending_flag": bool(source.get("any_pending_flag")),
        "rerun_trigger_events": list(source.get("rerun_triggers") or [])[-24:],
        "design_guide": _compact(source.get("design_guide") or {}, depth=3, max_items=10),
        "render_eligibility": _compact(source.get("render_eligibility") or {}, depth=3, max_items=10),
    }


def _stable_authority(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(
        left.get(key) == right.get(key)
        for key in (
            "final_publication_hash",
            "final_publication_display_hash",
            "final_publication_cta_hash",
            "button_contract_hash",
            "apply_payload_hash",
        )
        if left.get(key) or right.get(key)
    )


def _wait_for_rerun_change(page, before_seq: Any, *, recipe: str, timeout_s: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.time() + max(1.0, timeout_s)
    samples: list[dict[str, Any]] = []
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            state = dict(_load_browser_state_prefer_final_debug(page, timeout_s=1.5))
        except Exception:
            state = {}
        last_state = state
        summary = _summarise_state(state, recipe=recipe, label="after_post_apply_manual_rerun_sample") if state else {}
        samples.append({"sample_index": len(samples), "summary": summary})
        if summary.get("rerun_seq") not in (None, before_seq):
            return state, samples
        page.wait_for_timeout(350)
    return last_state, samples


def _wait_for_post_apply_auto_settle(
    page,
    *,
    recipe: str,
    before_seq: Any,
    timeout_s: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    deadline = time.time() + max(1.0, timeout_s)
    samples: list[dict[str, Any]] = []
    last_state: dict[str, Any] = {}
    saw_pending = False
    saw_rerun_change = False
    while time.time() < deadline:
        try:
            state = dict(_load_browser_state_prefer_final_debug(page, timeout_s=1.5))
        except Exception:
            state = {}
        last_state = state
        summary = _summarise_state(state, recipe=recipe, label="post_apply_auto_settle_sample") if state else {}
        pending = bool(summary.get("any_pending_flag"))
        saw_pending = saw_pending or pending
        saw_rerun_change = saw_rerun_change or (
            before_seq is not None and summary.get("rerun_seq") not in (None, before_seq)
        )
        samples.append({"sample_index": len(samples), "summary": summary})
        if state and not pending and saw_rerun_change:
            return state, samples, {
                "settled": True,
                "reason": "pending_clear_after_auto_rerun",
                "saw_pending": saw_pending,
                "saw_rerun_change": saw_rerun_change,
            }
        page.wait_for_timeout(450)
    return last_state, samples, {
        "settled": False,
        "reason": "pending_or_rerun_not_settled_before_timeout",
        "saw_pending": saw_pending,
        "saw_rerun_change": saw_rerun_change,
    }


def _capture(base_url: str, *, recipe: str, timeout_s: float, headed: bool) -> dict[str, Any]:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        idle_before = _wait_for_streamlit_idle(page, timeout_s=timeout_s)
        initial_state, initial_samples = _wait_for_full_publication_state(page, timeout_s=timeout_s)
        initial_summary = _summarise_state(initial_state, recipe=recipe, label="initial_before_apply")
        initial_dom = _dom_snapshot(page, label="initial_before_apply")
        try:
            post_apply_run = _run_live_scenario(
                page,
                scenario_id="post_apply_state_write_profile_apply",
                action="click_apply",
                base_url=base_url,
                recipe=recipe,
                timeout_s=timeout_s,
            )
        except PlaywrightTimeoutError as exc:
            post_apply_run = {
                "scenario_id": "post_apply_state_write_profile_apply",
                "action": "click_apply",
                "click_meta": {"clicked": False, "error": str(exc)},
                "elapsed_ms": None,
                "milestones": {},
                "counters": {},
                "layout": {},
                "churn": {},
            }
        post_apply_state, post_apply_samples, post_apply_settle = _wait_for_post_apply_auto_settle(
            page,
            recipe=recipe,
            before_seq=initial_summary.get("rerun_seq"),
            timeout_s=min(18.0, timeout_s),
        )
        post_apply_summary = _summarise_state(post_apply_state, recipe=recipe, label="post_apply_settled")
        post_apply_dom = _dom_snapshot(page, label="post_apply_settled")
        rerun_click = _click_streamlit_rerun(page)
        if rerun_click.get("clicked"):
            after_state, rerun_samples = _wait_for_rerun_change(
                page,
                post_apply_summary.get("rerun_seq"),
                recipe=recipe,
                timeout_s=timeout_s,
            )
        else:
            after_state, rerun_samples = {}, []
        page.wait_for_timeout(900)
        final_state = (
            dict(_load_browser_state_prefer_final_debug(page, timeout_s=min(10.0, timeout_s)))
            if rerun_click.get("clicked")
            else after_state
        )
        after_summary = _summarise_state(final_state, recipe=recipe, label="after_post_apply_manual_rerun") if final_state else {}
        after_dom = _dom_snapshot(page, label="after_post_apply_manual_rerun")
        idle_after = _wait_for_streamlit_idle(page, timeout_s=min(12.0, timeout_s))
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "idle_before": idle_before,
        "idle_after": idle_after,
        "initial": {"summary": initial_summary, "dom": initial_dom, "poll_samples": initial_samples},
        "post_apply": {
            "run": post_apply_run,
            "summary": post_apply_summary,
            "dom": post_apply_dom,
            "auto_settle": post_apply_settle,
            "poll_samples": post_apply_samples,
        },
        "manual_rerun": {"click": rerun_click, "summary": after_summary, "dom": after_dom, "poll_samples": rerun_samples},
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    initial = dict((capture.get("initial") or {}).get("summary") or {})
    post_apply = dict((capture.get("post_apply") or {}).get("summary") or {})
    post_apply_auto_settle = dict((capture.get("post_apply") or {}).get("auto_settle") or {})
    post_run = dict((capture.get("post_apply") or {}).get("run") or {})
    after = dict((capture.get("manual_rerun") or {}).get("summary") or {})
    rerun_click = dict((capture.get("manual_rerun") or {}).get("click") or {})
    apply_click = dict(post_run.get("click_meta") or {})
    stable_after_apply_rerun = _stable_authority(post_apply, after)
    stable_initial_to_post = _stable_authority(initial, post_apply)
    rerun_changed = post_apply.get("rerun_seq") is not None and after.get("rerun_seq") not in (None, post_apply.get("rerun_seq"))
    pending_after_apply = bool(post_apply.get("any_pending_flag"))
    pending_after_rerun = bool(after.get("any_pending_flag"))
    candidate_delta = _delta(_candidate_count(after), _candidate_count(post_apply))
    publication_delta = _delta(after.get("publication_rebuild_count"), post_apply.get("publication_rebuild_count"))
    card_model_delta = _delta(after.get("card_render_model_rebuild_count"), post_apply.get("card_render_model_rebuild_count"))
    debug_stamp_delta = _delta(after.get("session_debug_stamp_count"), post_apply.get("session_debug_stamp_count"))
    summary_bypass_after = dict(after.get("summary_card_html_bypass_debug") or {})
    summary_cache_after = dict(after.get("summary_card_html_cache_probe") or {})
    likely_sources: list[str] = []
    if not apply_click.get("clicked"):
        likely_sources.append("post_apply_action_not_clicked")
    if not rerun_click.get("clicked"):
        likely_sources.append("streamlit_rerun_control_not_clicked_after_apply")
    if pending_after_apply and not pending_after_rerun:
        likely_sources.append("pending_apply_refresh_consumed_by_manual_rerun")
    elif pending_after_apply or pending_after_rerun:
        likely_sources.append("pending_apply_or_action_flag_after_post_apply_rerun")
    if rerun_changed and stable_after_apply_rerun and candidate_delta:
        likely_sources.append("candidate_evaluation_after_stable_post_apply_rerun")
    if rerun_changed and stable_after_apply_rerun and publication_delta:
        likely_sources.append("publication_rebuild_after_stable_post_apply_rerun")
    if rerun_changed and stable_after_apply_rerun and card_model_delta:
        likely_sources.append("card_render_model_rebuild_after_stable_post_apply_rerun")
    if rerun_changed and stable_after_apply_rerun and debug_stamp_delta:
        likely_sources.append("debug_only_session_stamp_write_after_stable_post_apply_rerun")
    summary_html_bypassed = bool(
        summary_bypass_after.get("summary_card_html_bypassed")
        or summary_bypass_after.get("bypassed")
    )
    summary_cache_current = (
        bool(summary_cache_after.get("has_summary_cards_html"))
        and dict(summary_cache_after.get("reuse_keys") or {})
        == dict(summary_bypass_after.get("reuse_keys") or {})
    )
    if (
        summary_bypass_after
        and not summary_html_bypassed
        and stable_after_apply_rerun
        and summary_cache_current
        and not any([candidate_delta, publication_delta, card_model_delta, debug_stamp_delta])
    ):
        likely_sources.append("summary_html_cache_current_bypass_debug_stale_only")
    elif summary_bypass_after and not summary_html_bypassed and stable_after_apply_rerun:
        likely_sources.append("summary_html_rebuild_after_stable_post_apply_rerun")
    if not likely_sources and rerun_changed and stable_after_apply_rerun:
        likely_sources.append("stable_post_apply_rerun_no_product_state_write_hotspot")
    elif not likely_sources:
        likely_sources.append("post_apply_state_write_profile_inconclusive")

    if "post_apply_action_not_clicked" in likely_sources:
        decision = "BLOCKED_NO_ACTIONABLE_APPLY"
        next_slice = "Run a recipe with a visible executable Apply action before profiling post-Apply state writes."
        status = "PARTIAL"
    elif "streamlit_rerun_control_not_clicked_after_apply" in likely_sources:
        decision = "BLOCKED_RERUN_CONTROL_NOT_CLICKED"
        next_slice = "Run headed or add a test-only same-session rerun trigger before patching product code."
        status = "PARTIAL"
    elif "pending_apply_or_action_flag_after_post_apply_rerun" in likely_sources:
        decision = "PATCH_READY_SURVIVING_PENDING_FLAG_CLEANUP"
        next_slice = "Audit the surviving pending apply/action flag and clear only the proven stale non-authoritative write."
        status = "PASS"
    elif "pending_apply_refresh_consumed_by_manual_rerun" in likely_sources and not bool(post_apply_auto_settle.get("settled")):
        decision = "POST_APPLY_REFRESH_PENDING_UNTIL_MANUAL_RERUN"
        next_slice = "Audit why the Apply-triggered pending refresh is not settled before the manual rerun; do not clear it as stale."
        status = "PASS"
    elif "pending_apply_refresh_consumed_by_manual_rerun" in likely_sources and not stable_after_apply_rerun:
        decision = "POST_APPLY_AUTO_SETTLED_THEN_MANUAL_RERUN_CHANGED_AUTHORITY"
        next_slice = "Inspect post-Apply authority hash timing before patching state writes."
        status = "PASS"
    elif "pending_apply_refresh_consumed_by_manual_rerun" in likely_sources:
        decision = "POST_APPLY_REFRESH_QUEUE_CONSUMED_NO_PATCH"
        next_slice = "No stale pending flag survived; continue with first-paint/layout or browser-probe profiling."
        status = "PASS"
    elif any(source in likely_sources for source in (
        "candidate_evaluation_after_stable_post_apply_rerun",
        "publication_rebuild_after_stable_post_apply_rerun",
        "card_render_model_rebuild_after_stable_post_apply_rerun",
        "summary_html_rebuild_after_stable_post_apply_rerun",
    )):
        decision = "PATCH_READY_STABLE_POST_APPLY_REBUILD_DELTA"
        next_slice = "Patch only the proven stable-authority rebuild surface with a missing/stale/debug guard."
        status = "PASS"
    elif likely_sources == ["debug_only_session_stamp_write_after_stable_post_apply_rerun"]:
        decision = "NO_PATCH_DEBUG_ONLY_STAMP_DELTA"
        next_slice = "No product rebuild hotspot remains in this slice; continue with first-paint/layout or browser-probe profiling."
        status = "PASS"
    elif likely_sources == ["summary_html_cache_current_bypass_debug_stale_only"]:
        decision = "NO_PATCH_SUMMARY_CACHE_CURRENT_STALE_DEBUG_PROXY"
        next_slice = "No product summary rebuild patch is required; browser probe shows the cache is current and product counters are stable."
        status = "PASS"
    elif "stable_post_apply_rerun_no_product_state_write_hotspot" in likely_sources:
        decision = "NO_PATCH_PRODUCT_STATE_WRITES_CLEAN"
        next_slice = "Do not patch post-Apply state writes; move to first-paint/layout or browser-probe/root-shell profiling."
        status = "PASS"
    else:
        decision = "POST_APPLY_STATE_WRITE_SOURCE_UNCLEAR"
        next_slice = "Capture more detailed state-key deltas before implementing reuse."
        status = "PARTIAL"

    return {
        "status": status,
        "decision": decision,
        "apply_clicked": bool(apply_click.get("clicked")),
        "manual_rerun_clicked": bool(rerun_click.get("clicked")),
        "manual_rerun_seq_changed": bool(rerun_changed),
        "stable_initial_to_post_apply_authority": bool(stable_initial_to_post),
        "stable_post_apply_to_rerun_authority": bool(stable_after_apply_rerun),
        "pending_after_apply": pending_after_apply,
        "pending_after_rerun": pending_after_rerun,
        "post_apply_auto_settle": post_apply_auto_settle,
        "pending_flags_after_apply": dict(post_apply.get("pending_flags") or {}),
        "pending_flags_after_rerun": dict(after.get("pending_flags") or {}),
        "rebuild_deltas_after_stable_post_apply_rerun": {
            "candidate_evaluation": candidate_delta,
            "publication": publication_delta,
            "card_render_model": card_model_delta,
            "session_debug_stamp": debug_stamp_delta,
        },
        "rerun_trigger_events_after_apply": list(post_apply.get("rerun_trigger_events") or []),
        "rerun_trigger_events_after_rerun": list(after.get("rerun_trigger_events") or []),
        "likely_sources": likely_sources,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Same-Session Post-Apply State-Write Profile",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{cls.get('decision')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- Recipe: `{payload.get('recipe')}`",
            f"- Apply clicked: `{cls.get('apply_clicked')}`",
            f"- Manual rerun clicked: `{cls.get('manual_rerun_clicked')}`",
            f"- Manual rerun seq changed: `{cls.get('manual_rerun_seq_changed')}`",
            f"- Stable post-Apply to rerun authority: `{cls.get('stable_post_apply_to_rerun_authority')}`",
            f"- Likely sources: `{', '.join(cls.get('likely_sources') or [])}`",
            "",
            "## Pending Flags",
            "",
            f"- After Apply: `{cls.get('pending_flags_after_apply')}`",
            f"- After rerun: `{cls.get('pending_flags_after_rerun')}`",
            "",
            "## Rebuild Deltas After Stable Post-Apply Rerun",
            "",
            f"`{cls.get('rebuild_deltas_after_stable_post_apply_rerun')}`",
            "",
            "## Next Safe Slice",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_session_post_apply_state_write_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_session_post_apply_state_write_profile_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8718)
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()

    proc: subprocess.Popen[str] | None = None
    base_url = f"http://127.0.0.1:{args.port}"
    try:
        if not args.no_start_server:
            proc = _start_streamlit(args.port)
            _wait_for_http(base_url)
        capture = _capture(base_url, recipe=args.recipe, timeout_s=args.timeout_s, headed=args.headed)
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_same_session_post_apply_state_write_profile.v1",
            "created_at": _stamp(),
            "status": classification.get("status"),
            "recipe": args.recipe,
            "product_behaviour_changed": False,
            "classification": classification,
            "capture": capture,
        }
        json_path, md_path = _write(payload)
        print(json.dumps({"status": payload["status"], "decision": classification.get("decision"), "json": str(json_path), "report": str(md_path)}, indent=2))
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
