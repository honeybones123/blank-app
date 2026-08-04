from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from tools.verification.helpers.browser_state_overlay import (
    merge_fragment_browser_state_overlay,
)

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verification.helpers.browser_one_click_regression import (
    BROWSER_STATE_LABEL,
    TRACER_PATH,
    _query,
    _terminate_process_tree,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
)


MU_LABEL = "Positive design moment Mu*+ (kNm)"
VU_LABEL = "Design shear Vu* (kN)"

PAGE_CYCLE_GHOST_FAILURE_CLASS = "ghost_or_empty_ui_render_after_page_cycle"
PAGE_CYCLE_FALSE_POSITIVE_HEALTHY_CLASS = "page_cycle_false_positive_evidence_healthy"
PAGE_CYCLE_CAPTURE_UNAVAILABLE_CLASS = "page_cycle_failure_capture_unavailable"
EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS = "empty_calc_or_check_card_shell_visible"
BENDING_READY_GATE_TIMEOUT_CLASS = "bending_ready_gate_timeout"
INPUTS_READY_GATE_TIMEOUT_CLASS = "inputs_ready_gate_timeout"
PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS = "page_cycle_navigation_timeout"
PAGE_CYCLE_LATE_SLUG_CONFIRMATION_CLASS = "page_cycle_late_slug_confirmation"
STREAMLIT_RUNTIME_RECONNECT_CLASS = "streamlit_runtime_reconnect_during_verification"
DESIGN_PAGE_PRE_RENDER_TIMEOUT_CLASS = "design_page_pre_render_timeout"
PAGE_CYCLE_GHOST_FAILURE_MESSAGE = (
    "UI page-cycle regression: empty/ghost calc boxes or stale page content "
    "remained visible after navigating between pages."
)
PAGE_CYCLE_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("inputs", "Inputs"),
    ("design", "Design"),
    ("bending", "Bending"),
    ("shear", "Shear"),
    ("deflection", "Deflection"),
    ("crack", "Crack Control"),
    ("creep", "Creep"),
    ("shrinkage", "Shrinkage"),
    ("inputs", "Inputs"),
)
PAGE_CYCLE_REDUCED_DESIGN_TRUTH_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("inputs", "Inputs"),
    ("design", "Design"),
    ("inputs", "Inputs"),
)
PAGE_CYCLE_MODE_SEQUENCES: dict[str, tuple[tuple[str, str], ...]] = {
    "full": PAGE_CYCLE_SEQUENCE,
    "inputs_design_inputs": PAGE_CYCLE_REDUCED_DESIGN_TRUTH_SEQUENCE,
}


LADDER_STEPS = [
    ("A_M45_V0", 45.0, 0.0),
    ("A_M55_V0", 55.0, 0.0),
    ("A_M300_V0", 300.0, 0.0),
    ("A_M500_V0", 500.0, 0.0),
    ("A_M600_V0", 600.0, 0.0),
    ("B_M0_V150", 0.0, 150.0),
    ("B_M0_V200", 0.0, 200.0),
    ("B_M0_V400", 0.0, 400.0),
    ("B_M0_V600", 0.0, 600.0),
    ("C_M45_V150", 45.0, 150.0),
    ("C_M55_V200", 55.0, 200.0),
    ("C_M300_V400", 300.0, 400.0),
    ("C_M600_V600", 600.0, 600.0),
    ("D_M600_V0", 600.0, 0.0),
    ("D_M500_V0", 500.0, 0.0),
    ("D_M300_V0", 300.0, 0.0),
    ("D_M55_V0", 55.0, 0.0),
    ("D_M45_V0", 45.0, 0.0),
    ("E_M0_V600", 0.0, 600.0),
    ("E_M0_V400", 0.0, 400.0),
    ("E_M0_V200", 0.0, 200.0),
    ("E_M0_V150", 0.0, 150.0),
    ("F_M600_V600", 600.0, 600.0),
    ("F_M300_V400", 300.0, 400.0),
    ("F_M55_V200", 55.0, 200.0),
    ("F_M45_V150", 45.0, 150.0),
]


def _browser_state_raw_candidates(page, *, timeout_ms: int = 1_500) -> list[str]:
    try:
        values: list[str] = []
        selectors = (
            "textarea[aria-label='Browser state']",
            "[data-testid='stTextArea'] textarea",
            "[aria-label='Browser state']",
            "[data-testid='stCodeBlock']",
        )
        for selector in selectors:
            locator = page.locator(selector)
            try:
                count = locator.count()
            except Exception:
                count = 0
            for index in range(count):
                item = locator.nth(index)
                try:
                    raw = item.input_value(timeout=max(100, int(timeout_ms)))
                except Exception:
                    try:
                        raw = item.text_content(timeout=max(100, int(timeout_ms))) or ""
                    except Exception:
                        raw = ""
                if raw and str(raw).strip():
                    values.append(str(raw).strip())
        values.sort(key=len, reverse=True)
        return values
    except Exception:
        try:
            locator = page.get_by_label(BROWSER_STATE_LABEL).first
            locator.wait_for(state="attached", timeout=max(100, int(timeout_ms)))
            raw = str(locator.input_value(timeout=max(100, int(timeout_ms))) or "")
            return [raw] if raw.strip() else []
        except Exception:
            return []


def _browser_state_raw(page, *, timeout_ms: int = 1_500) -> str:
    candidates = _browser_state_raw_candidates(page, timeout_ms=timeout_ms)
    return candidates[0] if candidates else ""


def _fragment_browser_state_overlay(page, *, timeout_ms: int) -> dict[str, Any]:
    try:
        overlay_node = page.locator(
            "[data-codex-inputs-workspace-overlay='1']"
        ).last
        if overlay_node.count() > 0:
            raw = overlay_node.text_content(
                timeout=max(100, int(timeout_ms))
            )
        else:
            locator = page.locator(
                "textarea[aria-label='Inputs workspace state']"
            ).last
            raw = locator.input_value(timeout=max(100, int(timeout_ms)))
        payload = json.loads(str(raw or ""))
        if not isinstance(payload, dict):
            return {}
        overlay = payload.get("browser_state_overlay")
        return dict(overlay) if isinstance(overlay, dict) else {}
    except Exception:
        return {}


def _with_fragment_browser_state_overlay(
    page,
    state: dict[str, Any],
    *,
    timeout_ms: int,
) -> dict[str, Any]:
    overlay = _fragment_browser_state_overlay(page, timeout_ms=timeout_ms)
    return (
        merge_fragment_browser_state_overlay(dict(state), overlay)
        if overlay.get("fragment_fresh")
        else state
    )


def _load_browser_state(page, timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = time.time() + max(0.1, float(timeout_s or 30.0))
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            remaining_ms = max(100, min(2_000, int((deadline - time.time()) * 1000)))
            last_parsed: dict[str, Any] | None = None
            best_non_lightweight: dict[str, Any] | None = None
            fragment_overlay: dict[str, Any] = {}
            browser_state_candidates: list[tuple[tuple[int, int, int, int], dict[str, Any]]] = []
            for candidate_index, raw in enumerate(
                _browser_state_raw_candidates(page, timeout_ms=remaining_ms)
            ):
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    candidate_overlay = parsed.get("browser_state_overlay")
                    if (
                        isinstance(candidate_overlay, dict)
                        and candidate_overlay.get("fragment_fresh")
                    ):
                        fragment_overlay = dict(candidate_overlay)
                    if (
                        parsed.get("browser_shared_probe")
                        and not parsed.get("pre_page_render_lightweight")
                    ):
                        timing = (
                            dict(parsed.get("render_timing_probe") or {})
                            if isinstance(parsed.get("render_timing_probe"), dict)
                            else {}
                        )
                        try:
                            rerun_seq = int(timing.get("rerun_seq") or -1)
                        except (TypeError, ValueError):
                            rerun_seq = -1
                        try:
                            event_count = int(timing.get("event_count") or -1)
                        except (TypeError, ValueError):
                            event_count = -1
                        try:
                            results_version = int(parsed.get("results_version") or -1)
                        except (TypeError, ValueError):
                            results_version = -1
                        browser_state_candidates.append(
                            (
                                (
                                    rerun_seq,
                                    event_count,
                                    results_version,
                                    -candidate_index,
                                ),
                                parsed,
                            )
                        )
                        continue
                    if not parsed.get("pre_page_render_lightweight"):
                        best_non_lightweight = parsed
                    last_parsed = parsed
            if browser_state_candidates:
                browser_state_candidate = max(
                    browser_state_candidates,
                    key=lambda row: row[0],
                )[1]
                return (
                    merge_fragment_browser_state_overlay(
                        browser_state_candidate,
                        fragment_overlay,
                    )
                    if fragment_overlay
                    else _with_fragment_browser_state_overlay(
                        page,
                        browser_state_candidate,
                        timeout_ms=remaining_ms,
                    )
                )
            if best_non_lightweight is not None:
                return _with_fragment_browser_state_overlay(
                    page,
                    best_non_lightweight,
                    timeout_ms=remaining_ms,
                )
            if last_parsed is not None and not last_parsed.get("pre_page_render_lightweight"):
                return _with_fragment_browser_state_overlay(
                    page,
                    last_parsed,
                    timeout_ms=remaining_ms,
                )
            if last_parsed is not None and time.time() >= deadline:
                return last_parsed
            raise ValueError("Browser state probe was empty")
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    if last_error is not None:
        raise last_error
    return {}


def _browser_state_signature(page) -> str | None:
    try:
        return _browser_state_raw(page, timeout_ms=2_000) or "{}"
    except Exception:
        return None


def _extract_actions_used(state: dict[str, Any]) -> dict[str, Any]:
    guidance_compute = dict(state.get("guidance_compute_probe") or {})
    overview = dict(guidance_compute.get("overview") or {})
    return dict(overview.get("actions_used") or {})


def _state_matches_edited_inputs(
    state: dict[str, Any],
    *,
    mu: float,
    vu: float,
    require_solver_cleared: bool,
) -> bool:
    probe = dict(state.get("summary_state_probe") or {})
    shared = dict(state.get("browser_shared_probe") or {})
    actions_used = _extract_actions_used(state)
    solver_result = state.get("solver_result")
    feedback = state.get("one_click_feedback")

    probe_mu_present = probe.get("uls_Mstar") is not None
    probe_vu_present = probe.get("uls_Vstar") is not None
    shared_mu_ok = bool(
        _same_value(shared.get("uls_Mstar"), mu)
        and _same_value(shared.get("load_Mstar_proxy"), mu)
        and _same_value(shared.get("inputs_load_Mstar_pos_proxy"), mu)
    )
    shared_vu_ok = bool(
        _same_value(shared.get("uls_Vstar"), vu)
        and _same_value(shared.get("load_Vstar_proxy"), vu)
        and _same_value(shared.get("inputs_load_Vstar_proxy"), vu)
    )
    mu_ok = bool(shared_mu_ok and (not probe_mu_present or _same_value(probe.get("uls_Mstar"), mu)))
    vu_ok = bool(shared_vu_ok and (not probe_vu_present or _same_value(probe.get("uls_Vstar"), vu)))

    guidance_mu_ok = True
    guidance_vu_ok = True
    if actions_used:
        if "Mu" in actions_used:
            guidance_mu_ok = _same_value(actions_used.get("Mu"), mu)
        elif "Mu_pos" in actions_used:
            guidance_mu_ok = _same_value(actions_used.get("Mu_pos"), mu)
        if "Vu" in actions_used:
            guidance_vu_ok = _same_value(actions_used.get("Vu"), vu)

    settled = bool(mu_ok and vu_ok and guidance_mu_ok and guidance_vu_ok)
    if not settled:
        return False
    if not require_solver_cleared:
        return True
    return bool(not solver_result and not feedback)


def _wait_for_state(
    page,
    *,
    mu: float,
    vu: float,
    expect_solver_cleared: bool,
    timeout_s: float = 45.0,
) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        try:
            last_state = _load_browser_state(page, timeout_s=min(2.0, remaining))
        except Exception:
            time.sleep(min(0.4, max(0.05, deadline - time.time())))
            continue
        if _state_matches_edited_inputs(
            last_state,
            mu=mu,
            vu=vu,
            require_solver_cleared=expect_solver_cleared,
        ):
            return last_state, True
        time.sleep(0.4)
    return last_state, False


def _snapshot_post_publish_state(state: dict[str, Any]) -> tuple[Any, ...]:
    overview = dict(state.get("summary_overview_probe") or {})
    statuses = tuple(sorted(dict(overview.get("statuses") or {}).items()))
    return (
        _float_or_none(overview.get("worst_util")),
        statuses,
    )


def _wait_for_post_publish_alignment(
    page,
    *,
    mu: float,
    vu: float,
    run_end_data: dict[str, Any] | None,
    timeout_s: float = 45.0,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] = {}
    target_util = _float_or_none((run_end_data or {}).get("final_live_worst_util"))
    target_statuses = dict((run_end_data or {}).get("post_commit_live_statuses") or {})
    target_audit_util = _float_or_none((run_end_data or {}).get("post_commit_live_worst_util"))
    stable_count = 0
    last_sig: tuple[Any, ...] | None = None
    polls = 0
    start = time.time()
    while time.time() < deadline:
        polls += 1
        remaining = max(0.1, deadline - time.time())
        try:
            last_state = _load_browser_state(page, timeout_s=min(2.0, remaining))
        except Exception:
            time.sleep(min(0.4, max(0.05, deadline - time.time())))
            continue
        if not _state_matches_edited_inputs(
            last_state,
            mu=mu,
            vu=vu,
            require_solver_cleared=False,
        ):
            time.sleep(0.4)
            continue
        if target_util is None and target_audit_util is None and not target_statuses:
            return last_state, True, {
                "settle_wait_time_ms": int((time.time() - start) * 1000),
                "poll_cycles": polls,
                "stability_multiple_cycles": False,
            }
        overview = dict(last_state.get("summary_overview_probe") or {})
        current_util = _float_or_none(overview.get("worst_util"))
        current_statuses = dict(overview.get("statuses") or {})
        util_ok = True if target_util is None else _same_value(current_util, target_util, tol=5e-3)
        audit_ok = True if target_audit_util is None else _same_value(target_audit_util, target_util, tol=5e-3)
        statuses_ok = True if not target_statuses else current_statuses == target_statuses
        if util_ok and audit_ok and statuses_ok:
            sig = _snapshot_post_publish_state(last_state)
            if sig == last_sig:
                stable_count += 1
            else:
                last_sig = sig
                stable_count = 1
            if stable_count >= 2:
                return last_state, True, {
                    "settle_wait_time_ms": int((time.time() - start) * 1000),
                    "poll_cycles": polls,
                    "stability_multiple_cycles": True,
                }
        else:
            stable_count = 0
            last_sig = None
        time.sleep(0.4)
    return last_state, False, {
        "settle_wait_time_ms": int((time.time() - start) * 1000),
        "poll_cycles": polls,
        "stability_multiple_cycles": stable_count > 1,
    }


def _wait_for_post_click_state_without_run_end(
    page,
    *,
    mu: float,
    vu: float,
    pre_state: dict[str, Any],
    timeout_s: float = 45.0,
 ) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] = {}
    pre_probe = dict(pre_state.get("summary_state_probe") or {})
    pre_overview = dict(pre_state.get("summary_overview_probe") or {})
    polls = 0
    start = time.time()
    while time.time() < deadline:
        polls += 1
        remaining = max(0.1, deadline - time.time())
        try:
            last_state = _load_browser_state(page, timeout_s=min(2.0, remaining))
        except Exception:
            time.sleep(min(0.4, max(0.05, deadline - time.time())))
            continue
        probe = dict(last_state.get("summary_state_probe") or {})
        overview = dict(last_state.get("summary_overview_probe") or {})
        if not (
            _same_value(probe.get("uls_Mstar"), mu)
            and _same_value(probe.get("uls_Vstar"), vu)
        ):
            time.sleep(0.4)
            continue
        state_changed = bool(
            not _same_value(overview.get("worst_util"), pre_overview.get("worst_util"), tol=5e-3)
            or dict(overview.get("statuses") or {}) != dict(pre_overview.get("statuses") or {})
            or dict(probe) != dict(pre_probe)
            or bool(last_state.get("solver_result"))
            or bool(last_state.get("one_click_feedback"))
        )
        if state_changed:
            return last_state, True, {
                "settle_wait_time_ms": int((time.time() - start) * 1000),
                "poll_cycles": polls,
                "stability_multiple_cycles": False,
            }
        time.sleep(0.4)
    return last_state, False, {
        "settle_wait_time_ms": int((time.time() - start) * 1000),
        "poll_cycles": polls,
        "stability_multiple_cycles": False,
    }


def _set_number_input(page, label: str, value: float) -> None:
    locator = page.locator(f'input[aria-label="{label}"]:visible').first
    locator.wait_for(timeout=30_000)
    target_text = str(int(value) if float(value).is_integer() else value)
    try:
        locator.click(timeout=10_000)
        locator.press("Control+A", timeout=5_000)
        locator.press("Delete", timeout=5_000)
        locator.type(target_text, delay=15, timeout=10_000)
    except Exception:
        page.evaluate(
            """
            ({ label, value }) => {
                const inputs = Array.from(document.querySelectorAll('input'));
                const el = inputs.find((candidate) =>
                    candidate.getAttribute('aria-label') === label
                    && candidate.offsetParent !== null
                ) || inputs.find((candidate) => candidate.getAttribute('aria-label') === label);
                if (!el) {
                    return false;
                }
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
                if (setter) {
                    setter.call(el, value);
                } else {
                    el.value = value;
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.blur();
                return true;
            }
            """,
            {"label": label, "value": target_text},
        )
        page.keyboard.press("Tab")
    deadline = time.time() + 10.0
    target = str(float(value))
    target_alt = target_text if float(value).is_integer() else target
    last_value = None
    while time.time() < deadline:
        try:
            current = page.locator(f'input[aria-label="{label}"]:visible').first.input_value(timeout=1_000)
        except Exception:
            current = None
        last_value = current
        if current in {target, target_alt}:
            return
        time.sleep(0.2)
    # Streamlit can rerender the number input immediately after input/change
    # dispatch, leaving the old DOM handle unreadable.  The caller validates
    # the edit against shared/published state via _commit_number_input_like_user.
    return


def _input_dom_matches(page, label: str, value: float, *, timeout_s: float = 2.0) -> bool:
    deadline = time.time() + max(0.1, float(timeout_s or 2.0))
    target = float(value)
    while time.time() < deadline:
        try:
            current = page.locator(f'input[aria-label="{label}"]:visible').first.input_value(timeout=500)
        except Exception:
            time.sleep(0.1)
            continue
        if _same_value(current, target, tol=5e-2):
            return True
        time.sleep(0.1)
    return False


def _wait_for_partial_state(
    page,
    *,
    mu: float | None = None,
    vu: float | None = None,
    timeout_s: float = 20.0,
) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        try:
            last_state = _load_browser_state(page, timeout_s=min(2.0, remaining))
        except Exception:
            time.sleep(min(0.3, max(0.05, deadline - time.time())))
            continue
        probe = dict(last_state.get("summary_state_probe") or {})
        shared = dict(last_state.get("browser_shared_probe") or {})
        mu_ok = True
        vu_ok = True
        if mu is not None:
            mu_ok = bool(
                _same_value(probe.get("uls_Mstar"), mu) and _same_value(shared.get("uls_Mstar"), mu)
            )
        if vu is not None:
            vu_ok = bool(
                _same_value(probe.get("uls_Vstar"), vu) and _same_value(shared.get("uls_Vstar"), vu)
            )
        if mu_ok and vu_ok:
            return last_state, True
        time.sleep(0.3)
    return last_state, False


def _stable_preclick_signature(state: dict[str, Any]) -> tuple[Any, ...]:
    probe = dict(state.get("summary_state_probe") or {})
    shared = dict(state.get("browser_shared_probe") or {})
    overview = dict(state.get("summary_overview_probe") or {})
    guidance = dict(state.get("guidance_compute_probe") or {})
    statuses = tuple(sorted(dict(overview.get("statuses") or {}).items()))
    return (
        probe.get("uls_Mstar"),
        probe.get("uls_Vstar"),
        shared.get("b"),
        shared.get("D"),
        shared.get("bot1_count"),
        shared.get("db_bot_1"),
        shared.get("lig_d"),
        shared.get("lig_legs"),
        shared.get("s_lig"),
        overview.get("worst_util"),
        statuses,
        guidance.get("primary_action_type"),
        guidance.get("primary_title"),
        guidance.get("primary_terminal_state"),
        guidance.get("user_visible_no_action_reason"),
        guidance.get("stop_reason"),
        guidance.get("guidance_branch"),
        bool(state.get("solver_result")),
        bool(state.get("one_click_feedback")),
    )


def _wait_for_settled_preclick_state(
    page,
    *,
    mu: float,
    vu: float,
    timeout_s: float = 20.0,
    stable_reads: int = 3,
 ) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] = {}
    last_sig: tuple[Any, ...] | None = None
    stable_count = 0
    polls = 0
    start = time.time()
    while time.time() < deadline:
        polls += 1
        last_state, matched = _wait_for_state(
            page,
            mu=mu,
            vu=vu,
            expect_solver_cleared=True,
            timeout_s=1.5,
        )
        if not matched:
            time.sleep(0.2)
            continue
        sig = _stable_preclick_signature(last_state)
        if sig == last_sig:
            stable_count += 1
        else:
            last_sig = sig
            stable_count = 1
        if stable_count >= max(1, stable_reads):
            return last_state, True, {
                "settle_wait_time_ms": int((time.time() - start) * 1000),
                "poll_cycles": polls,
                "stability_multiple_cycles": stable_count > 1,
            }
        time.sleep(0.25)
    return last_state, False, {
        "settle_wait_time_ms": int((time.time() - start) * 1000),
        "poll_cycles": polls,
        "stability_multiple_cycles": stable_count > 1,
    }


def _preclick_actionable(state: dict[str, Any]) -> bool:
    guidance = dict(state.get("guidance_compute_probe") or {})
    return bool(str(guidance.get("primary_action_type") or "").strip())


def _commit_number_input_like_user(
    page,
    *,
    active_label: str,
    other_label: str | None,
    mu: float | None = None,
    vu: float | None = None,
    reconcile_timeout_s: float = 45.0,
    stage_callback: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], bool, str, dict[str, Any]]:
    active = page.locator(f'input[aria-label="{active_label}"]:visible').first
    other = (
        page.locator(f'input[aria-label="{other_label}"]:visible').first
        if other_label
        else None
    )

    def _wait_target(timeout_s: float) -> tuple[dict[str, Any], bool, dict[str, Any]]:
        if mu is not None and vu is not None:
            return _wait_for_settled_preclick_state(page, mu=mu, vu=vu, timeout_s=timeout_s)
        if mu is not None:
            state, ok = _wait_for_partial_state(page, mu=mu, timeout_s=timeout_s)
            return state, ok, {"settle_wait_time_ms": 0, "poll_cycles": 0, "stability_multiple_cycles": False}
        if vu is not None:
            state, ok = _wait_for_partial_state(page, vu=vu, timeout_s=timeout_s)
            return state, ok, {"settle_wait_time_ms": 0, "poll_cycles": 0, "stability_multiple_cycles": False}
        return _load_browser_state(page), False, {"settle_wait_time_ms": 0, "poll_cycles": 0, "stability_multiple_cycles": False}

    commit_methods: list[tuple[str, callable]] = [
        ("enter", lambda: active.press("Enter")),
        ("tab", lambda: active.press("Tab")),
    ]
    if other is not None:
        commit_methods.append(("click_other_widget", lambda: other.click(timeout=1_000)))
    commit_methods.append(
        (
            "click_apply_beam_reo_load_edits",
            lambda: page.get_by_role("button", name="Apply Beam/Reo/Load Edits").click(timeout=5_000),
        )
    )
    commit_methods.append(
        ("click_design_guide", lambda: page.get_by_text("Design Guide").first.click(timeout=5_000))
    )

    last_state: dict[str, Any] = {}
    deadline = time.time() + max(0.1, float(reconcile_timeout_s))
    for method_name, method in commit_methods:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        before_sig = _browser_state_signature(page)
        if stage_callback:
            stage_callback({"stage": "commit_method_started", "method": method_name})
        try:
            method()
        except Exception:
            pass
        if stage_callback:
            stage_callback({"stage": "commit_method_completed", "method": method_name})
        time.sleep(0.5)
        if stage_callback:
            stage_callback({"stage": "reconcile_wait_started", "method": method_name})
        last_state, matched, meta = _wait_target(remaining)
        if stage_callback:
            stage_callback({"stage": "reconcile_wait_completed", "method": method_name, "matched": matched})
        after_sig = _browser_state_signature(page)
        if matched:
            meta = dict(meta)
            meta["commit_method"] = method_name
            return last_state, True, method_name, meta
        if before_sig is not None and after_sig is not None and before_sig != after_sig:
            meta = dict(meta)
            meta["commit_method"] = f"{method_name}:rerun_without_target_reconcile"
            last_state = dict(last_state or {})
    return last_state, False, "none", {"settle_wait_time_ms": 0, "poll_cycles": 0, "stability_multiple_cycles": False, "commit_method": "none"}


def _apply_live_inputs(page, *, mu: float, vu: float) -> tuple[dict[str, Any], dict[str, Any]]:
    last_state: dict[str, Any] = {}
    pre_settle_meta: dict[str, Any] = {
        "mu": {},
        "vu": {},
        "final_publish": {},
    }

    def _active_inputs_rerun(state: dict[str, Any] | None) -> bool:
        state = dict(state or {})
        summary_probe = dict(state.get("summary_state_probe") or {})
        return bool(
            state.get("pre_page_render_lightweight")
            or summary_probe.get("_probe_skipped")
            == "pre_page_render_lightweight_before_page_body_mount"
        )

    for _ in range(1):
        _set_number_input(page, MU_LABEL, mu)
        last_state, matched, _, meta = _commit_number_input_like_user(
            page,
            active_label=MU_LABEL,
            other_label=VU_LABEL,
            mu=mu,
            vu=None,
            reconcile_timeout_s=12.0,
        )
        pre_settle_meta["mu"] = dict(meta)
        rerun_in_progress = _active_inputs_rerun(last_state)
        if not matched:
            pre_settle_meta["mu"]["dom_committed_without_published_state"] = _input_dom_matches(
                page, MU_LABEL, mu
            )
            pre_settle_meta["mu"]["inputs_rerun_in_progress"] = rerun_in_progress
            pre_settle_meta["mu"]["awaiting_final_exact_state"] = True
        # Do not fail merely because a legitimate Inputs rerun temporarily
        # removed the widget and ordinary browser-state probe.  Exact Mu/Vu
        # publication is proved by the final settled-state wait below.
        break

    for _ in range(1):
        _set_number_input(page, VU_LABEL, vu)
        last_state, matched, _, meta = _commit_number_input_like_user(
            page,
            active_label=VU_LABEL,
            other_label=MU_LABEL,
            mu=mu,
            vu=vu,
            reconcile_timeout_s=12.0,
        )
        pre_settle_meta["vu"] = dict(meta)
        rerun_in_progress = _active_inputs_rerun(last_state)
        if not matched:
            pre_settle_meta["vu"]["dom_committed_without_published_state"] = _input_dom_matches(
                page, VU_LABEL, vu
            )
            pre_settle_meta["vu"]["inputs_rerun_in_progress"] = rerun_in_progress
            pre_settle_meta["vu"]["awaiting_final_exact_state"] = True
        final_state, final_matched, final_meta = _wait_for_settled_preclick_state(
            page,
            mu=mu,
            vu=vu,
            timeout_s=75.0,
        )
        pre_settle_meta["final_publish"] = dict(final_meta)
        if final_matched:
            return final_state, pre_settle_meta
        # Engineering edits intentionally rerun only the Inputs workspace
        # fragment. The visible inputs and outputs can therefore be current
        # while the app-scope debug probe remains from the prior outer render.
        # Passing still requires exact settled Mu/Vu publication.
        last_state = final_state or last_state
        break
    raise RuntimeError(
        f"Combined Mu/Vu edit did not reconcile into shared/published state. "
        f"expected Mu={mu}, Vu={vu}, probe={dict(last_state.get('summary_state_probe') or {})}, "
        f"shared={dict(last_state.get('browser_shared_probe') or {})}"
    )


def _commit_live_edit(page) -> None:
    # Force a real blur/commit on the active input before we judge whether the
    # app reconciled the edited value into shared state.
    try:
        page.evaluate(
            """
            () => {
              const el = document.activeElement;
              if (el && typeof el.blur === "function") {
                el.blur();
              }
            }
            """
        )
    except Exception:
        pass
    try:
        page.keyboard.press("Tab")
    except Exception:
        pass
    try:
        page.get_by_text("Design Guide").first.click(timeout=5_000)
    except Exception:
        pass
    time.sleep(0.6)


def _guidance_summary(state: dict[str, Any]) -> dict[str, Any]:
    guidance = dict(state.get("guidance_probe") or {})
    pending_meta = dict(state.get("pending_recommendation_meta") or {})
    feedback = dict(state.get("one_click_feedback") or {})
    solver_result = dict(state.get("solver_result") or {})
    overview = dict((state.get("summary_overview_probe") or {}))
    shared = dict((state.get("browser_shared_probe") or {}))
    return {
        "guidance_title": guidance.get("primary_title"),
        "guidance_action_type": guidance.get("primary_action_type"),
        "guidance_status": guidance.get("primary_status"),
        "pending_status": pending_meta.get("status"),
        "feedback_reason": feedback.get("reason"),
        "solver_status": solver_result.get("status"),
        "solver_stop_reason": solver_result.get("stop_reason"),
        "governing_util": overview.get("worst_util"),
        "statuses": dict(overview.get("statuses") or {}),
        "shared_uls_Mstar": shared.get("uls_Mstar"),
        "shared_uls_Vstar": shared.get("uls_Vstar"),
        "shared_load_Mstar_proxy": shared.get("load_Mstar_proxy"),
        "shared_load_Vstar_proxy": shared.get("load_Vstar_proxy"),
    }


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _same_value(a: Any, b: Any, tol: float = 1e-6) -> bool:
    fa = _float_or_none(a)
    fb = _float_or_none(b)
    if fa is None or fb is None:
        return a == b
    return abs(fa - fb) <= tol


def _validate_live_step(
    *,
    edited_mu: float,
    edited_vu: float,
    pre_state: dict[str, Any],
    post_state: dict[str, Any],
    run_end_event: dict[str, Any] | None,
    button_found: bool,
) -> dict[str, Any]:
    pre_probe = dict(pre_state.get("summary_state_probe") or {})
    post_probe = dict(post_state.get("summary_state_probe") or {})
    pre_shared = dict(pre_state.get("browser_shared_probe") or {})
    post_shared = dict(post_state.get("browser_shared_probe") or {})
    pre_overview = dict(pre_state.get("summary_overview_probe") or {})
    post_overview = dict(post_state.get("summary_overview_probe") or {})
    pre_feedback = dict(pre_state.get("one_click_feedback") or {})
    pre_solver = dict(pre_state.get("solver_result") or {})
    post_feedback = dict(post_state.get("one_click_feedback") or {})
    post_solver = dict(post_state.get("solver_result") or {})
    run_end = dict((run_end_event or {}).get("data") or {})
    post_publish_aligned = bool(post_state.get("_post_publish_aligned"))

    pre_actions_match = bool(
        _same_value(pre_probe.get("uls_Mstar"), edited_mu)
        and _same_value(pre_probe.get("uls_Vstar"), edited_vu)
    )
    post_actions_match = bool(
        _same_value(post_probe.get("uls_Mstar"), edited_mu)
        and _same_value(post_probe.get("uls_Vstar"), edited_vu)
    )
    pre_shared_match = bool(
        _same_value(pre_shared.get("uls_Mstar"), edited_mu)
        and _same_value(pre_shared.get("uls_Vstar"), edited_vu)
    )
    post_shared_match = bool(
        _same_value(post_shared.get("uls_Mstar"), edited_mu)
        and _same_value(post_shared.get("uls_Vstar"), edited_vu)
    )
    stale_feedback_cleared = bool(not pre_feedback and not pre_solver)
    run_end_present = bool(run_end)
    post_commit_statuses = dict(run_end.get("post_commit_live_statuses") or {})
    final_statuses = post_commit_statuses or dict(post_overview.get("statuses") or {})
    final_util = (
        _float_or_none(run_end.get("final_live_worst_util"))
        if run_end_present
        else _float_or_none(post_overview.get("worst_util"))
    )
    stop_reason = str(
        run_end.get("stop_reason")
        or post_solver.get("stop_reason")
        or post_feedback.get("reason")
        or ""
    ).strip() or None
    no_commit_expected = bool(
        stop_reason == "no_full_coverage_candidate"
        and run_end.get("winner_label") in (None, "")
        and run_end.get("final_updates") in (None, {})
        and run_end.get("one_click_commit_audit") in (None, {})
        and run_end.get("post_commit_live_worst_util") in (None, "")
    )
    # If the page correctly offers no one-click action for the current state,
    # treat the stable pre/post published state as aligned rather than as a
    # missing publish event.
    if not button_found:
        post_publish_aligned = bool(
            pre_actions_match
            and post_actions_match
            and pre_shared_match
            and post_shared_match
            and _same_value(pre_overview.get("worst_util"), post_overview.get("worst_util"))
            and dict(pre_overview.get("statuses") or {}) == dict(post_overview.get("statuses") or {})
        )

    telemetry_gap = bool(button_found and not run_end_present and post_publish_aligned)
    stale_state_issue = bool(
        (not pre_actions_match)
        or (not pre_shared_match)
        or (not stale_feedback_cleared)
        or (button_found and not post_actions_match)
        or (button_found and not post_shared_match)
        or (button_found and not post_publish_aligned)
    )
    notes: list[str] = []
    if not pre_actions_match:
        notes.append("pre_click_summary_did_not_match_edited_inputs")
    if not pre_shared_match:
        notes.append("pre_click_shared_state_did_not_match_edited_inputs")
    if not stale_feedback_cleared:
        notes.append("stale_solver_feedback_survived_edit")
    if button_found and not post_actions_match:
        notes.append("post_click_summary_did_not_match_consumed_inputs")
    if button_found and not post_shared_match:
        notes.append("post_click_shared_state_did_not_match_consumed_inputs")
    if button_found and not run_end_present and not post_publish_aligned:
        notes.append("missing_run_end_event")
    if button_found and not post_publish_aligned:
        notes.append("post_click_published_summary_did_not_align_with_run_end")
    if telemetry_gap:
        notes.append("run_end_event_missing_but_published_state_aligned")

    return {
        "pre_actions_match": pre_actions_match,
        "post_actions_match": post_actions_match,
        "pre_shared_match": pre_shared_match,
        "post_shared_match": post_shared_match,
        "stale_feedback_cleared": stale_feedback_cleared,
        "button_found": bool(button_found),
        "run_end_present": run_end_present,
        "telemetry_gap": telemetry_gap,
        "post_publish_aligned": post_publish_aligned,
        "stop_reason": stop_reason,
        "final_governing_util": final_util,
        "final_statuses": final_statuses,
        "stale_state_issue": stale_state_issue,
        "notes": notes,
        "pre_governing_util": _float_or_none(pre_overview.get("worst_util")),
        "post_governing_util_probe": _float_or_none(post_overview.get("worst_util")),
        "no_commit_expected": no_commit_expected,
    }


def _page_cycle_write_text(path: Path, text: str) -> str | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _page_cycle_write_json(path: Path, payload: Any) -> str | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _page_cycle_loading_visible(page) -> bool:
    script = r"""
    () => {
      const visible = (el) => {
        if (!el) return false;
        const closedDetails = el.closest('details:not([open])');
        if (closedDetails && closedDetails !== el && !el.closest('summary')) return false;
        if (el.hasAttribute('inert') || el.closest('[inert]')) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 8 && rect.height > 8;
      };
      const loadingSelectors = [
        '[data-testid="stSpinner"]',
        '[data-testid="stSkeleton"]',
        '[aria-busy="true"]',
        '[role="progressbar"]'
      ];
      for (const selector of loadingSelectors) {
        if (Array.from(document.querySelectorAll(selector)).some(visible)) return true;
      }
      const texts = Array.from(document.querySelectorAll('main, [data-testid="stAppViewContainer"] *'))
        .filter(visible)
        .map((el) => String(el.innerText || "").replace(/\s+/g, " ").trim())
        .filter((text) => text.length > 0 && text.length < 120);
      return texts.some((text) => (
        /^(loading|preparing|running|please wait|design guidance is preparing)(\.{0,3})$/i.test(text)
        || /^loading\s+(inputs|design|bending|shear|deflection|crack|creep|shrinkage)\b/i.test(text)
        || /^running\s+(calculation|design|solver)/i.test(text)
      ));
    }
    """
    try:
        return bool(page.evaluate(script))
    except Exception:
        return False


def _page_cycle_current_slug(page) -> str:
    try:
        match = re.search(r"[?&]page=([^&#]+)", str(page.url or ""))
        if match:
            return match.group(1).strip().lower()
    except Exception:
        pass
    try:
        locator = page.get_by_label(BROWSER_STATE_LABEL)
        locator.wait_for(state="attached", timeout=500)
        raw = locator.input_value(timeout=500) or "{}"
        state = json.loads(raw)
        slug = str(state.get("page_slug") or "").strip().lower()
        if slug:
            return slug
    except Exception:
        pass
    return ""


def _page_cycle_connection_error_visible(page) -> bool:
    status = _page_cycle_streamlit_status_detail(page)
    return str(status.get("status") or "").upper() in {
        "CONNECTING",
        "DISCONNECTED",
        "ERROR",
        "CONNECTION ERROR",
        "STREAMLIT SERVER IS NOT RESPONDING",
    }


def _page_cycle_wait_for_slug_or_marker(page, slug: str, deadline: float) -> dict[str, Any]:
    polls = 0
    last_slug = ""
    last_marker: dict[str, Any] = {}
    marker_seen_with_slug_mismatch = False
    while time.perf_counter() < deadline:
        polls += 1
        last_slug = _page_cycle_current_slug(page)
        if last_slug == slug:
            return {"ok": True, "polls": polls, "current_slug": last_slug, "reason": "slug_matched"}
        last_marker = _page_cycle_content_marker(page, slug)
        if bool(last_marker.get("marker_present")) and bool(last_marker.get("active_expected_nav")):
            marker_seen_with_slug_mismatch = True
        time.sleep(0.1)
    return {
        "ok": False,
        "polls": polls,
        "current_slug": last_slug,
        "reason": "marker_seen_but_slug_mismatch" if marker_seen_with_slug_mismatch else "navigation_timeout",
        "content_marker": last_marker,
    }


def _page_cycle_remaining_ms(deadline: float, *, cap_ms: int = 1500) -> int:
    remaining_ms = int(max(0.0, deadline - time.perf_counter()) * 1000)
    return max(1, min(int(cap_ms), remaining_ms))


def _page_cycle_deadline_result(
    *,
    target_slug: str,
    current_slug: str,
    selector: str,
    elapsed_ms: int,
    errors: list[str],
    message: str,
) -> dict[str, Any]:
    exact_slug_confirmed = str(current_slug) == str(target_slug)
    return {
        "clicked": exact_slug_confirmed,
        "already_active": False,
        "selector": selector,
        "classification": (
            PAGE_CYCLE_LATE_SLUG_CONFIRMATION_CLASS
            if exact_slug_confirmed
            else PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS
        ),
        "elapsed_ms": int(elapsed_ms),
        "current_slug": current_slug,
        "errors": errors,
        "message": (
            f"navigation to {target_slug} reached the exact target slug at the deadline"
            if exact_slug_confirmed
            else message
        ),
        "late_slug_confirmation": exact_slug_confirmed,
    }


def _page_cycle_click_page(page, slug: str, label: str, *, timeout_s: float = 20.0) -> dict[str, Any]:
    click_errors: list[str] = []
    started = time.perf_counter()
    deadline = started + max(3.0, float(timeout_s))

    def _timed_out(selector: str) -> dict[str, Any] | None:
        if time.perf_counter() < deadline:
            return None
        return _page_cycle_deadline_result(
            target_slug=slug,
            current_slug=_page_cycle_current_slug(page),
            selector=selector,
            elapsed_ms=int(max(0.0, time.perf_counter() - started) * 1000),
            errors=click_errors[-8:],
            message=f"navigation to {slug} timed out before page slug/readiness marker appeared",
        )

    if _page_cycle_current_slug(page) == slug:
        return {
            "clicked": False,
            "already_active": True,
            "errors": [],
            "elapsed_ms": int(max(0.0, time.perf_counter() - started) * 1000),
        }
    streamlit_radio_label = page.locator('div[data-testid="stRadio"] label').filter(
        has=page.locator("p").filter(has_text=re.compile(rf"^\s*{re.escape(label)}\s*$"))
    ).first
    try:
        timed_out = _timed_out("streamlit_radio_label")
        if timed_out:
            return timed_out
        streamlit_radio_label.click(timeout=_page_cycle_remaining_ms(deadline))
        wait_meta = _page_cycle_wait_for_slug_or_marker(page, slug, min(deadline, time.perf_counter() + 4.0))
        if wait_meta.get("ok"):
            return {
                "clicked": True,
                "already_active": False,
                "selector": "streamlit_radio_label",
                "wait": wait_meta,
                "errors": click_errors[-5:],
                "elapsed_ms": int(max(0.0, time.perf_counter() - started) * 1000),
            }
        click_errors.append(f"streamlit_radio_label: clicked but page slug did not become {slug}")
    except Exception as exc:
        click_errors.append(f"streamlit_radio_label: {type(exc).__name__}: {exc}")
    direct_nav_label = page.locator("div[role='radiogroup'] label").filter(
        has_text=re.compile(rf"^\s*{re.escape(label)}\s*$")
    ).first
    try:
        timed_out = _timed_out("visible_radio_nav_label")
        if timed_out:
            return timed_out
        direct_nav_label.click(timeout=_page_cycle_remaining_ms(deadline), force=True)
        wait_meta = _page_cycle_wait_for_slug_or_marker(page, slug, min(deadline, time.perf_counter() + 4.0))
        if wait_meta.get("ok"):
            return {
                "clicked": True,
                "already_active": False,
                "selector": "visible_radio_nav_label",
                "wait": wait_meta,
                "errors": click_errors[-5:],
                "elapsed_ms": int(max(0.0, time.perf_counter() - started) * 1000),
            }
        click_errors.append(f"visible_radio_nav_label: clicked but page slug did not become {slug}")
    except Exception as exc:
        click_errors.append(f"visible_radio_nav_label: {type(exc).__name__}: {exc}")
    try:
        timed_out = _timed_out("visible_nav_label_center")
        if timed_out:
            return timed_out
        target = page.evaluate(
            r"""
            (label) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el) return false;
                if (el.hasAttribute("inert") || el.closest("[inert]")) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && rect.width > 4
                  && rect.height > 4;
              };
              const candidates = Array.from(document.querySelectorAll(
                'div[role="radiogroup"] label, label, [role="tab"], a[href*="page="], button'
              ))
                .filter(visible)
                .filter((el) => clean(el.innerText || el.getAttribute("aria-label") || el.textContent) === label)
                .map((el) => {
                  const rect = el.getBoundingClientRect();
                  return {
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                    text: clean(el.innerText || el.getAttribute("aria-label") || el.textContent),
                    tag: el.tagName.toLowerCase()
                  };
                });
              return candidates[0] || null;
            }
            """,
            label,
        )
        if target:
            page.mouse.click(float(target["x"]), float(target["y"]))
            wait_meta = _page_cycle_wait_for_slug_or_marker(page, slug, min(deadline, time.perf_counter() + 4.0))
            if wait_meta.get("ok"):
                return {
                    "clicked": True,
                    "already_active": False,
                    "selector": "visible_nav_label_center",
                    "wait": wait_meta,
                    "errors": click_errors[-5:],
                    "elapsed_ms": int(max(0.0, time.perf_counter() - started) * 1000),
                }
            click_errors.append(f"visible_nav_label_center: clicked but page slug did not become {slug}")
    except Exception as exc:
        click_errors.append(f"visible_nav_label_center: {type(exc).__name__}: {exc}")
    nav_label = (
        page.locator('div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] label')
        .filter(has_text=re.compile(rf"^\s*{re.escape(label)}\s*$"))
        .first
    )
    for name, locator in (
        ("top_nav_label", nav_label),
        ("query_anchor", page.locator(f'a[href*="page={slug}"]').first),
        ("href_target", page.locator(f'[href*="page={slug}"]').first),
        ("tab_role", page.get_by_role("tab", name=label, exact=True)),
        ("link_role", page.get_by_role("link", name=label, exact=True)),
        ("button_role", page.get_by_role("button", name=label, exact=True)),
        ("label_role", page.get_by_label(label, exact=True)),
        ("exact_text", page.get_by_text(label, exact=True)),
    ):
        try:
            timed_out = _timed_out(name)
            if timed_out:
                return timed_out
            locator.click(timeout=_page_cycle_remaining_ms(deadline))
            wait_meta = _page_cycle_wait_for_slug_or_marker(page, slug, min(deadline, time.perf_counter() + 4.0))
            if wait_meta.get("ok"):
                return {
                    "clicked": True,
                    "already_active": False,
                    "selector": name,
                    "wait": wait_meta,
                    "errors": click_errors[-5:],
                    "elapsed_ms": int(max(0.0, time.perf_counter() - started) * 1000),
                }
            click_errors.append(f"{name}: clicked but page slug did not become {slug}")
        except Exception as exc:
            click_errors.append(f"{name}: {type(exc).__name__}: {exc}")
    return _page_cycle_deadline_result(
        target_slug=slug,
        current_slug=_page_cycle_current_slug(page),
        selector="all_navigation_selectors",
        elapsed_ms=int(max(0.0, time.perf_counter() - started) * 1000),
        errors=click_errors[-5:],
        message=f"could not click {label} page/tab",
    )


def _page_cycle_content_marker(page, slug: str) -> dict[str, Any]:
    script = r"""
    (slug) => {
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const visible = (el) => {
        if (!el) return false;
        if (el.hasAttribute('inert') || el.closest('[inert]')) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 4 && rect.height > 4;
      };
      const main = document.querySelector('[data-testid="stMain"]') || document.querySelector('main') || document.body;
      const text = clean(main ? main.innerText : document.body.innerText);
      const visibleTextMatches = (pattern) => Array.from(document.querySelectorAll('[data-testid="stVerticalBlock"], [data-testid="stMarkdownContainer"], [data-testid="stExpander"], label, button'))
        .filter(visible)
        .some((el) => pattern.test(clean(el.innerText || el.textContent)));
      const markerPatterns = {
        inputs: [/Inputs Start Your Design/i, /Batch design/i, /Active beam/i],
        design: [/Beam Actions & Diagrams/i, /Load diagram/i, /Design-action source/i],
        bending: [/Bending capacity/i, /Sagging bending check/i, /Stress.strain model/i],
        shear: [/Shear & Torsion/i, /Shear\s+[—-]\s*ULS/i, /Show detailed MCFT breakdown/i],
        deflection: [/Deflection/i, /Short-term deflection/i, /Long-term deflection/i],
        creep: [/Creep/i],
        shrinkage: [/Shrinkage/i],
        crack: [/Crack Control/i, /Crack width/i]
      };
      const patterns = markerPatterns[slug] || [new RegExp(slug, "i")];
      const matchedMarkers = patterns
        .filter((pattern) => pattern.test(text))
        .map((pattern) => String(pattern));
      const headings = Array.from(document.querySelectorAll('h1, h2, h3, [data-testid="stHeading"]'))
        .filter(visible)
        .map((el) => clean(el.innerText || el.textContent))
        .filter(Boolean)
        .slice(0, 8);
      const activeLabels = Array.from(document.querySelectorAll('div[role="radiogroup"] label, label'))
        .filter(visible)
        .filter((el) => {
          const input = el.querySelector('input') || el.control || null;
          return input && input.checked;
        })
        .map((el) => clean(el.innerText || el.textContent))
        .filter(Boolean)
        .slice(0, 12);
      const expectedLabel = {
        inputs: "Inputs",
        design: "Design",
        bending: "Bending",
        shear: "Shear",
        deflection: "Deflection",
        creep: "Creep",
        shrinkage: "Shrinkage",
        crack: "Crack Control"
      }[slug] || slug;
      const activeExpectedNav = activeLabels.some((label) => label === expectedLabel);
      const shearHeadingVisible = slug === "shear" && visibleTextMatches(/Shear & Torsion/i);
      const shearSummaryVisible = slug === "shear" && (
        visibleTextMatches(/Shear\s+[—-]\s*ULS/i)
        || visibleTextMatches(/φVu\s*=/i)
        || visibleTextMatches(/Capacity\s+φVu/i)
        || visibleTextMatches(/Shear design checks/i)
        || visibleTextMatches(/Shear reinforcement checks/i)
        || visibleTextMatches(/MCFT and strength checks/i)
      );
      return {
        marker_present: matchedMarkers.length > 0,
        matched_markers: matchedMarkers,
        headings,
        active_labels: activeLabels,
        active_expected_nav: activeExpectedNav,
        shear_heading_visible: shearHeadingVisible,
        shear_summary_visible: shearSummaryVisible,
        shear_page_ready: slug === "shear" ? Boolean(activeExpectedNav && shearHeadingVisible && shearSummaryVisible) : null,
        main_text_length: text.length,
        main_text_sample: text.slice(0, 500)
      };
    }
    """
    try:
        return dict(page.evaluate(script, slug) or {})
    except Exception as exc:
        return {"marker_error": f"{type(exc).__name__}: {exc}", "marker_present": False}


def _page_cycle_churn_snapshot(page, *, slug: str, detail: bool = False) -> dict[str, Any]:
    script = r"""
    (args) => {
      const slug = args && args.slug;
      const detail = Boolean(args && args.detail);
      const now = Date.now();
      window.__codexPageCycleNodeIds = window.__codexPageCycleNodeIds || new WeakMap();
      window.__codexPageCycleNodeSeq = window.__codexPageCycleNodeSeq || 1;
      const nodeId = (el) => {
        if (!el) return null;
        if (!window.__codexPageCycleNodeIds.has(el)) {
          window.__codexPageCycleNodeIds.set(el, window.__codexPageCycleNodeSeq++);
        }
        return window.__codexPageCycleNodeIds.get(el);
      };
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const hash = (value) => {
        const text = String(value || "");
        let h = 2166136261;
        for (let i = 0; i < text.length; i += 1) {
          h ^= text.charCodeAt(i);
          h = Math.imul(h, 16777619);
        }
        return (h >>> 0).toString(16);
      };
      if (!window.__codexPageCycleChurnProbe) {
        window.__codexPageCycleChurnProbe = {
          installedAt: now,
          mutationCount: 0,
          batches: [],
          lastBatchAt: null,
          lastBatchSize: 0
        };
        const visibleForProbe = (el) => {
          if (!el || !el.getBoundingClientRect) return false;
          if (el.hasAttribute && (el.hasAttribute("hidden") || el.hasAttribute("inert") || el.closest("[inert]"))) return false;
          const style = window.getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
        };
        const cleanForProbe = (value) => String(value || "").replace(/\s+/g, " ").trim();
        const nearbyHeading = (el) => {
          let cur = el;
          for (let depth = 0; cur && depth < 5; depth += 1, cur = cur.parentElement) {
            const heading = Array.from(cur.querySelectorAll ? cur.querySelectorAll("h1,h2,h3,h4,[data-testid*='header' i],strong,b") : [])
              .filter(visibleForProbe)
              .map((node) => cleanForProbe(node.innerText || node.textContent))
              .find((text) => text.length > 0);
            if (heading) return heading.slice(0, 120);
          }
          let prev = el && el.previousElementSibling;
          for (let i = 0; prev && i < 6; i += 1, prev = prev.previousElementSibling) {
            const text = cleanForProbe(prev.innerText || prev.textContent);
            if (text.length > 0) return text.slice(0, 120);
          }
          return "";
        };
        const ownerFor = (node) => {
          const el = node && node.nodeType === Node.ELEMENT_NODE ? node : (node && node.parentElement);
          if (!el) return {owner: "unknown", label: "unknown", visible: false};
          const owner = el.closest([
            "[data-testid='design-guide-card']",
            ".fast-guidance-item",
            ".summary-check-card",
            ".summary-card-stack",
            "[data-testid='stPlotlyChart']",
            ".js-plotly-plot",
            "[data-testid='stExpander']",
            "[data-testid='stNumberInput']",
            "[data-testid='stTextInput']",
            "[data-testid='stSelectbox']",
            "[data-testid='stButton']",
            "[data-testid='stVerticalBlock']",
            "main"
          ].join(",")) || el;
          const testid = owner.getAttribute ? owner.getAttribute("data-testid") : null;
          const cls = String(owner.className || "");
          const text = cleanForProbe(owner.innerText || owner.textContent).slice(0, 120);
          let family = "streamlit_layout_wrapper";
          if (owner.matches && (owner.matches("[data-testid='design-guide-card']") || owner.matches(".fast-guidance-item"))) family = "design_guide_card";
          else if (owner.matches && (owner.matches(".summary-check-card") || owner.matches(".summary-card-stack") || /summary/i.test(testid || cls))) family = "summary_tables";
          else if (owner.matches && (owner.matches("[data-testid='stPlotlyChart']") || owner.matches(".js-plotly-plot") || /plotly|chart/i.test(testid || cls))) family = "plotly_or_chart";
          else if (owner.matches && owner.matches("[data-testid='stExpander']")) family = "expanders";
          else if (/NumberInput|TextInput|Selectbox|Button|Widget/i.test(testid || cls)) family = "input_widgets";
          else if (/calc|check|derivation|card/i.test(testid || cls)) family = "calc_boxes";
          const heading = nearbyHeading(owner);
          return {
            owner: family,
            label: heading || text || testid || cls.slice(0, 80) || String(owner.tagName || "").toLowerCase(),
            visible: visibleForProbe(owner),
            tag: String(owner.tagName || "").toLowerCase(),
            testid,
            cls: cls.slice(0, 100)
          };
        };
        const chartFor = (node) => {
          const el = node && node.nodeType === Node.ELEMENT_NODE ? node : (node && node.parentElement);
          if (!el || !el.closest) return null;
          return el.closest("[data-testid='stPlotlyChart'], .js-plotly-plot, .plot-container, .svg-container");
        };
        const isForbiddenChartFilterTarget = (node) => {
          const el = node && node.nodeType === Node.ELEMENT_NODE ? node : (node && node.parentElement);
          if (!el || !el.closest) return true;
          return Boolean(el.closest([
            "[data-testid='design-guide-card']",
            ".fast-guidance-item",
            ".summary-check-card",
            ".summary-card-stack",
            "[data-testid*='summary' i]",
            "[data-testid*='check' i]",
            "[data-testid='stNumberInput']",
            "[data-testid='stTextInput']",
            "[data-testid='stSelectbox']",
            "[data-testid='stButton']",
            "[data-codex-page-root]",
            "main"
          ].join(",")) && !el.closest("[data-testid='stPlotlyChart'], .js-plotly-plot, .plot-container, .svg-container"));
        };
        const isChartInternalMutation = (rec) => {
          const target = rec && rec.target;
          const el = target && target.nodeType === Node.ELEMENT_NODE ? target : (target && target.parentElement);
          if (!el || !el.closest) return false;
          if (isForbiddenChartFilterTarget(el)) return false;
          const chart = chartFor(el);
          if (!chart) {
            const tag = String(el.tagName || "").toLowerCase();
            return ["path", "g", "text", "rect", "line", "circle", "polyline", "polygon", "svg"].includes(tag)
              && Boolean(el.closest(".plotly, .main-svg, .cartesianlayer, .scatterlayer, .pielayer, .barlayer"));
          }
          for (const node of Array.from(rec.addedNodes || [])) {
            if (node.nodeType === Node.ELEMENT_NODE && isForbiddenChartFilterTarget(node)) return false;
          }
          for (const node of Array.from(rec.removedNodes || [])) {
            if (node.nodeType === Node.ELEMENT_NODE && isForbiddenChartFilterTarget(node)) return false;
          }
          return true;
        };
        const chartInfoFor = (chart) => {
          if (!chart) return null;
          const testid = chart.getAttribute ? chart.getAttribute("data-testid") : null;
          const cls = String(chart.className || "");
          const label = nearbyHeading(chart) || cleanForProbe(chart.innerText || chart.textContent).slice(0, 120) || testid || cls.slice(0, 80) || String(chart.tagName || "").toLowerCase();
          const canvases = Array.from(chart.querySelectorAll ? chart.querySelectorAll("canvas") : []);
          return {
            id: nodeId(chart),
            owner: "plotly_or_chart",
            label,
            visible: visibleForProbe(chart),
            tag: String(chart.tagName || "").toLowerCase(),
            testid,
            cls: cls.slice(0, 100),
            svg_count: chart.querySelectorAll ? chart.querySelectorAll("svg").length : 0,
            canvas_count: canvases.length,
            webgl_canvas_count: canvases.filter((canvas) => {
              try { return Boolean(canvas.getContext && (canvas.getContext("webgl") || canvas.getContext("webgl2"))); }
              catch (_err) { return false; }
            }).length
          };
        };
        const obs = new MutationObserver((records) => {
          const probe = window.__codexPageCycleChurnProbe;
          const recs = Array.from(records || []);
          const added = recs.reduce((acc, rec) => acc + (rec.addedNodes ? rec.addedNodes.length : 0), 0);
          const removed = recs.reduce((acc, rec) => acc + (rec.removedNodes ? rec.removedNodes.length : 0), 0);
          const attrs = recs.filter((rec) => rec.type === "attributes").length;
          const sampledRecs = recs.slice(0, 250);
          const ownerCounts = new Map();
          const chartCounts = new Map();
          const targetOwners = [];
          probe.chartMutationTotals = probe.chartMutationTotals || {};
          const chartInternalRecords = recs.filter(isChartInternalMutation).length;
          const nonChartRecords = Math.max(0, recs.length - chartInternalRecords);
          probe.chartInternalMutationCount = Number(probe.chartInternalMutationCount || 0) + chartInternalRecords;
          probe.nonChartMutationCount = Number(probe.nonChartMutationCount || 0) + nonChartRecords;
          sampledRecs.forEach((rec) => {
            const owner = ownerFor(rec.target);
            const key = [owner.owner, owner.label, owner.visible ? "visible" : "hidden"].join("|");
            const prev = ownerCounts.get(key) || {...owner, records: 0, added: 0, removed: 0, attributes: 0};
            prev.records += 1;
            prev.added += rec.addedNodes ? rec.addedNodes.length : 0;
            prev.removed += rec.removedNodes ? rec.removedNodes.length : 0;
            prev.attributes += rec.type === "attributes" ? 1 : 0;
            ownerCounts.set(key, prev);
            if (targetOwners.length < 10) targetOwners.push(owner);
            const chartInfo = chartInfoFor(chartFor(rec.target));
            if (chartInfo) {
              const chartKey = [chartInfo.id, chartInfo.label, chartInfo.visible ? "visible" : "hidden"].join("|");
              const chartPrev = chartCounts.get(chartKey) || {...chartInfo, records: 0, added: 0, removed: 0, attributes: 0};
              chartPrev.records += 1;
              chartPrev.added += rec.addedNodes ? rec.addedNodes.length : 0;
              chartPrev.removed += rec.removedNodes ? rec.removedNodes.length : 0;
              chartPrev.attributes += rec.type === "attributes" ? 1 : 0;
              chartPrev.structural = chartPrev.added + chartPrev.removed;
              chartPrev.attribute_only = chartPrev.attributes > 0 && chartPrev.structural === 0;
              chartCounts.set(chartKey, chartPrev);
              const totalPrev = probe.chartMutationTotals[chartKey] || {...chartInfo, records: 0, added: 0, removed: 0, attributes: 0, structural: 0};
              totalPrev.records += 1;
              totalPrev.added += rec.addedNodes ? rec.addedNodes.length : 0;
              totalPrev.removed += rec.removedNodes ? rec.removedNodes.length : 0;
              totalPrev.attributes += rec.type === "attributes" ? 1 : 0;
              totalPrev.structural = totalPrev.added + totalPrev.removed;
              totalPrev.attribute_only = totalPrev.attributes > 0 && totalPrev.structural === 0;
              totalPrev.last_at = Date.now();
              probe.chartMutationTotals[chartKey] = totalPrev;
            }
          });
          const topOwners = Array.from(ownerCounts.values()).sort((a, b) => b.records - a.records).slice(0, 10);
          const topCharts = Array.from(chartCounts.values()).sort((a, b) => b.records - a.records).slice(0, 10);
          probe.mutationCount += recs.length;
          probe.lastBatchAt = Date.now();
          probe.lastBatchSize = recs.length;
          probe.batches.push({
            at: probe.lastBatchAt,
            records: recs.length,
            added,
            removed,
            attributes: attrs,
            chartInternalRecords,
            nonChartRecords,
            sampled_records: sampledRecs.length,
            topOwners,
            topCharts,
            targetOwners,
            targets: sampledRecs.slice(0, 20).map((rec) => {
              const target = rec.target;
              return target ? {
                tag: String(target.tagName || "").toLowerCase(),
                id: target.id || null,
                testid: target.getAttribute ? target.getAttribute("data-testid") : null,
                cls: String(target.className || "").slice(0, 80)
              } : null;
            }).filter(Boolean).slice(0, 5)
          });
          if (probe.batches.length > 200) probe.batches = probe.batches.slice(-200);
        });
        obs.observe(document.documentElement || document.body, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ["class", "style", "hidden", "aria-busy", "aria-disabled", "data-testid"]
        });
        window.__codexPageCycleChurnProbe.observerInstalled = true;
      }
      const visible = (el) => {
        if (!el) return false;
        if (el.hasAttribute && (el.hasAttribute("hidden") || el.hasAttribute("inert") || el.closest("[inert]"))) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        if (style.display === "none" || style.visibility === "hidden") return false;
        if (Number(style.opacity || "1") <= 0.02) return false;
        return rect.width >= 2 && rect.height >= 2;
      };
      const nodes = (selector) => {
        try { return Array.from(document.querySelectorAll(selector)); }
        catch (_err) { return []; }
      };
      const firstVisible = (selectors) => {
        for (const selector of selectors) {
          const found = nodes(selector).find(visible);
          if (found) return found;
        }
        return null;
      };
      const activeNav = nodes('label, button, [role="tab"], [aria-current], [data-baseweb="tab"]')
        .filter(visible)
        .map((el) => ({text: clean(el.innerText || el.textContent), ariaCurrent: el.getAttribute("aria-current"), checked: el.getAttribute("aria-checked")}))
        .filter((item) => item.ariaCurrent || item.checked === "true" || item.text.toLowerCase() === String(slug || "").toLowerCase())
        .slice(0, 10);
      const bodyText = clean(document.body ? document.body.innerText : "");
      const main = firstVisible(["main", "[data-testid='stAppViewContainer']", ".stApp"]);
      const pageRoot = firstVisible([
        `[data-codex-page-root="${slug}"]`,
        `[data-testid*="${slug}" i]`,
        "main [data-testid='stVerticalBlock']",
        "main"
      ]) || main;
      const dg = firstVisible(["[data-testid='design-guide-card']", ".fast-guidance-item", "[data-testid*='design-guide' i]"]);
      const summary = firstVisible([".summary-card-stack", ".summary-check-card", "[data-testid*='summary' i]", "[data-testid*='check' i]"]);
      const rootSignature = (el) => {
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        return hash([
          String(el.tagName || ""),
          String(el.className || "").slice(0, 160),
          el.getAttribute ? (el.getAttribute("data-testid") || "") : "",
          clean(el.innerText || el.textContent).slice(0, 500),
          Math.round(rect.width),
          Math.round(rect.height)
        ].join("|"));
      };
      const rootSignatureValue = rootSignature(pageRoot);
      const afterRootHash = performance.now();
      const visibleCount = (selector) => nodes(selector).filter(visible).length;
      const cardCount = [
        "[data-testid='stExpander']",
        ".summary-check-card",
        ".fast-guidance-item",
        "[data-testid='design-guide-card']",
        "[class*='card' i]"
      ].reduce((acc, selector) => acc + visibleCount(selector), 0);
      const calcCount = [
        "[class*='calc' i]",
        "[class*='check' i]",
        ".summary-check-card",
        "[data-testid*='check' i]"
      ].reduce((acc, selector) => acc + visibleCount(selector), 0);
      const fadedCount = nodes("main *, [data-testid='stAppViewContainer'] *").filter((el) => {
        if (!visible(el)) return false;
        const rect = el.getBoundingClientRect();
        const opacity = Number(window.getComputedStyle(el).opacity || "1");
        return opacity > 0.02 && opacity < 0.65 && rect.width > 120 && rect.height > 24;
      }).length;
      const spinnerCount = nodes('[data-testid="stSpinner"], [class*="spinner" i], [aria-busy="true"]').filter(visible).length;
      const chartNodes = Array.from(new Set(nodes("[data-testid='stPlotlyChart'], .js-plotly-plot, .plot-container, .svg-container")));
      const visibleChartNodes = chartNodes.filter(visible);
      const visibleNonChartSelector = (detail ? [
        "h1",
        "h2",
        "h3",
        "label",
        "button",
        "[data-testid='stMarkdownContainer']",
        "[data-testid='stExpander']",
        ".summary-check-card",
        ".fast-guidance-item",
        "[data-testid='design-guide-card']"
      ] : [
        "h1",
        "h2",
        "h3",
        "label",
        "button",
        "[data-testid='stExpander']",
        ".summary-check-card",
        ".fast-guidance-item",
        "[data-testid='design-guide-card']"
      ]).join(",");
      const visibleNonChartItems = nodes(visibleNonChartSelector)
        .filter((el) => visible(el) && !el.closest("[data-testid='stPlotlyChart'], .js-plotly-plot, .plot-container, .svg-container"))
        .map((el) => {
          const text = clean(el.innerText || el.textContent);
          const tag = String(el.tagName || "").toLowerCase();
          const testid = el.getAttribute ? el.getAttribute("data-testid") : null;
          const cls = String(el.className || "").slice(0, 100);
          if (!detail) {
            return {
              text,
              text_hash: hash(text),
              category: "lightweight_visible_text",
              tag,
              testid,
              cls: "",
              owner: "",
              owner_label: "",
              owner_visible: true
            };
          }
          const ownerEl = el.closest([
            "[data-testid='design-guide-card']",
            ".fast-guidance-item",
            ".summary-check-card",
            ".summary-card-stack",
            "[data-testid='stExpander']",
            "[data-testid='stNumberInput']",
            "[data-testid='stTextInput']",
            "[data-testid='stSelectbox']",
            "[data-testid='stButton']",
            "[data-testid='stVerticalBlock']",
            "main"
          ].join(",")) || el;
          const ownerTestid = ownerEl.getAttribute ? ownerEl.getAttribute("data-testid") : null;
          const ownerCls = String(ownerEl.className || "");
          const ownerText = clean(ownerEl.innerText || ownerEl.textContent).slice(0, 120);
          let ownerName = "streamlit_layout_wrapper";
          if (ownerEl.matches && (ownerEl.matches("[data-testid='design-guide-card']") || ownerEl.matches(".fast-guidance-item"))) ownerName = "design_guide_card";
          else if (ownerEl.matches && (ownerEl.matches(".summary-check-card") || ownerEl.matches(".summary-card-stack") || /summary/i.test(ownerTestid || ownerCls))) ownerName = "summary_tables";
          else if (ownerEl.matches && ownerEl.matches("[data-testid='stExpander']")) ownerName = "expanders";
          else if (/NumberInput|TextInput|Selectbox|Button|Widget/i.test(ownerTestid || ownerCls)) ownerName = "input_widgets";
          else if (/calc|check|derivation|card/i.test(ownerTestid || ownerCls)) ownerName = "calc_boxes";
          const ownerLabel = ownerText || ownerTestid || ownerCls.slice(0, 80) || String(ownerEl.tagName || "").toLowerCase();
          let category = "unknown";
          if (/loading|preparing|running|please wait/i.test(text)) category = "loading_marker";
          else if (/debug|probe|json|browser-state|timeline|fingerprint|uuid|cid/i.test(text) || /language-json|token/i.test(cls)) category = "debug_or_probe_text";
          else if (/PASS|FAIL|CAPACITY|Utilisation|Applied|Capacity|φ|eta|η|kNm|kN|mm/i.test(text)) category = "calc_or_check_result";
          else if (/expand_more|keyboard_arrow|INFO|ULS|SLS/i.test(text) || testid === "stExpander") category = "expander_or_status";
          else if (/input|select|button|widget/i.test(testid || cls) || tag === "label" || tag === "button") category = "streamlit_widget_label_or_value";
          else if (/Beam design|Inputs|Design|Bending|Shear|Deflection|Crack|Creep|Shrinkage/i.test(text)) category = "page_navigation_or_header";
          return {
            text,
            text_hash: hash(text),
            category,
            tag,
            testid,
            cls,
            owner: ownerName,
            owner_label: ownerLabel,
            owner_visible: visible(ownerEl)
          };
        })
        .filter(Boolean)
        .filter((item) => item.text.length > 0)
        .slice(0, detail ? 120 : 40);
      const visibleNonChartText = visibleNonChartItems.map((item) => item.text).join(" | ").slice(0, 20000);
      const canvases = nodes("canvas");
      const webglCanvasCount = canvases.filter((canvas) => {
        try { return Boolean(canvas.getContext && (canvas.getContext("webgl") || canvas.getContext("webgl2"))); }
        catch (_err) { return false; }
      }).length;
      const probe = window.__codexPageCycleChurnProbe || {};
      const chartMutationTotals = Object.values(probe.chartMutationTotals || {})
        .sort((a, b) => (b.records || 0) - (a.records || 0))
        .slice(0, 20);
      return {
        timestamp_ms: now,
        active_page: slug,
        url: window.location.href,
        body_text_length: bodyText.length,
        body_text_hash: hash(bodyText.slice(0, 20000)),
        visible_non_chart_text_length: visibleNonChartText.length,
        visible_non_chart_text_hash: hash(visibleNonChartText),
        visible_non_chart_text_items: detail ? visibleNonChartItems.slice(0, 80) : [],
        visible_card_count: cardCount,
        visible_calc_box_count: calcCount,
        visible_expander_count: visibleCount("[data-testid='stExpander']"),
        input_widget_count: visibleCount("[data-testid='stNumberInput'], [data-testid='stTextInput'], [data-testid='stSelectbox'], [data-testid='stButton']"),
        faded_inactive_overlay_count: fadedCount,
        loading_spinner_count: spinnerCount,
        streamlit_block_count: nodes("[data-testid='stVerticalBlock']").length,
        dom_node_count: nodes("*").length,
        plotly_container_count: chartNodes.length,
        visible_plotly_container_count: visibleChartNodes.length,
        hidden_plotly_container_count: Math.max(0, chartNodes.length - visibleChartNodes.length),
        svg_node_count: nodes("svg").length,
        canvas_node_count: canvases.length,
        webgl_canvas_count: webglCanvasCount,
        summary_table_exists: Boolean(summary),
        design_guide_container_exists: Boolean(dg),
        active_page_body_exists: Boolean(pageRoot),
        active_nav_or_tab_state: activeNav,
        page_root_id: nodeId(pageRoot),
        page_root_hash: rootSignature(pageRoot),
        design_guide_container_id: nodeId(dg),
        design_guide_container_hash: rootSignature(dg),
        summary_table_root_id: nodeId(summary),
        summary_table_root_hash: rootSignature(summary),
        mutation_count_total: Number(probe.mutationCount || 0),
        chart_internal_mutation_count_total: Number(probe.chartInternalMutationCount || 0),
        non_chart_mutation_count_total: Number(probe.nonChartMutationCount || 0),
        chart_mutation_total_records: chartMutationTotals.reduce((acc, item) => acc + Number(item.records || 0), 0),
        chart_mutation_visible_records: chartMutationTotals.reduce((acc, item) => acc + (item.visible ? Number(item.records || 0) : 0), 0),
        chart_mutation_hidden_records: chartMutationTotals.reduce((acc, item) => acc + (item.visible ? 0 : Number(item.records || 0)), 0),
        chart_mutation_top: detail ? chartMutationTotals : [],
        mutation_recent_batches: detail ? Array.from(probe.batches || []).slice(-8) : [],
        mutation_top_attribution: detail ? Array.from(probe.batches || [])
          .flatMap((batch) => Array.from(batch.topOwners || []).map((owner) => ({
            ...owner,
            at: batch.at,
            batch_records: batch.records,
            batch_added: batch.added,
            batch_removed: batch.removed
          })))
          .sort((a, b) => (b.records || 0) - (a.records || 0))
          .slice(0, 20) : [],
        last_mutation_age_ms: probe.lastBatchAt ? Math.max(0, now - Number(probe.lastBatchAt || 0)) : null,
        last_mutation_batch_size: Number(probe.lastBatchSize || 0)
      };
    }
    """
    try:
        return dict(page.evaluate(script, {"slug": slug, "detail": bool(detail)}) or {})
    except Exception as exc:
        return {"churn_probe_error": f"{type(exc).__name__}: {exc}", "active_page": slug}


def _page_cycle_summarise_churn(iterations: list[dict[str, Any]], *, settle_reset_count: int, longest_stable: int) -> dict[str, Any]:
    if not iterations:
        return {
            "iteration_count": 0,
            "settle_reset_count": int(settle_reset_count),
            "longest_stable_window_polls": int(longest_stable),
        }
    mutation_counts = [int((row.get("snapshot") or {}).get("mutation_count_total") or 0) for row in iterations]
    node_counts = [int((row.get("snapshot") or {}).get("dom_node_count") or 0) for row in iterations]
    root_changes = []
    detach_events = []
    previous_root = None
    previous_exists = None
    largest_node_delta = 0
    for row in iterations:
        snap = dict(row.get("snapshot") or {})
        root_id = snap.get("page_root_id")
        exists = bool(snap.get("active_page_body_exists"))
        if previous_root is not None and root_id is not None and root_id != previous_root:
            root_changes.append(
                {
                    "iteration": row.get("iteration"),
                    "from": previous_root,
                    "to": root_id,
                    "url": snap.get("url"),
                }
            )
        if previous_exists is not None and previous_exists != exists:
            detach_events.append(
                {
                    "iteration": row.get("iteration"),
                    "transition": "reattached" if exists else "detached",
                    "url": snap.get("url"),
                }
            )
        if root_id is not None:
            previous_root = root_id
        previous_exists = exists
    for before, after in zip(node_counts, node_counts[1:]):
        largest_node_delta = max(largest_node_delta, abs(int(after) - int(before)))
    largest_mutation_burst = 0
    attribution: dict[str, dict[str, Any]] = {}
    chart_attribution: dict[str, dict[str, Any]] = {}
    largest_batch: dict[str, Any] = {}
    for row in iterations:
        for batch in list((row.get("snapshot") or {}).get("mutation_recent_batches") or []):
            if isinstance(batch, dict):
                records = int(batch.get("records") or 0)
                largest_mutation_burst = max(largest_mutation_burst, records)
                if records >= int(largest_batch.get("records") or 0):
                    largest_batch = dict(batch)
                for owner in list(batch.get("topOwners") or []):
                    if not isinstance(owner, dict):
                        continue
                    key = "|".join(
                        [
                            str(owner.get("owner") or "unknown"),
                            str(owner.get("label") or "unknown")[:120],
                            "visible" if owner.get("visible") else "hidden",
                        ]
                    )
                    current = dict(attribution.get(key) or {})
                    current["owner"] = owner.get("owner") or "unknown"
                    current["label"] = owner.get("label") or "unknown"
                    current["visible"] = bool(owner.get("visible"))
                    current["records"] = int(current.get("records") or 0) + int(owner.get("records") or 0)
                    current["added"] = int(current.get("added") or 0) + int(owner.get("added") or 0)
                    current["removed"] = int(current.get("removed") or 0) + int(owner.get("removed") or 0)
                    current["attributes"] = int(current.get("attributes") or 0) + int(owner.get("attributes") or 0)
                    attribution[key] = current
                for chart in list(batch.get("topCharts") or []):
                    if not isinstance(chart, dict):
                        continue
                    key = "|".join(
                        [
                            str(chart.get("id") or "unknown"),
                            str(chart.get("label") or "unknown")[:120],
                            "visible" if chart.get("visible") else "hidden",
                        ]
                    )
                    current = dict(chart_attribution.get(key) or {})
                    current["id"] = chart.get("id")
                    current["owner"] = chart.get("owner") or "plotly_or_chart"
                    current["label"] = chart.get("label") or "unknown"
                    current["visible"] = bool(chart.get("visible"))
                    current["records"] = int(current.get("records") or 0) + int(chart.get("records") or 0)
                    current["added"] = int(current.get("added") or 0) + int(chart.get("added") or 0)
                    current["removed"] = int(current.get("removed") or 0) + int(chart.get("removed") or 0)
                    current["attributes"] = int(current.get("attributes") or 0) + int(chart.get("attributes") or 0)
                    current["structural"] = int(current.get("structural") or 0) + int(chart.get("structural") or 0)
                    current["svg_count"] = chart.get("svg_count")
                    current["canvas_count"] = chart.get("canvas_count")
                    current["webgl_canvas_count"] = chart.get("webgl_canvas_count")
                    chart_attribution[key] = current
    top_attribution = sorted(
        attribution.values(),
        key=lambda item: (
            -int(item.get("records") or 0),
            -int(item.get("added") or 0) - int(item.get("removed") or 0),
            str(item.get("owner") or ""),
        ),
    )[:20]
    top_chart_attribution = sorted(
        chart_attribution.values(),
        key=lambda item: (
            -int(item.get("records") or 0),
            -int(item.get("structural") or 0),
            str(item.get("label") or ""),
        ),
    )[:20]
    loading_polls = sum(1 for row in iterations if bool((row.get("snapshot") or {}).get("loading_spinner_count")))
    summary_exists_polls = sum(1 for row in iterations if bool((row.get("snapshot") or {}).get("summary_table_exists")))
    dg_exists_polls = sum(1 for row in iterations if bool((row.get("snapshot") or {}).get("design_guide_container_exists")))
    classifications = []
    if root_changes:
        classifications.append("full_remount_or_root_replacement")
    if detach_events:
        classifications.append("transient_detach_or_reattach")
    if loading_polls:
        classifications.append("loading_or_spinner_present")
    if not classifications:
        classifications.append("no_root_replacement_detected")
    return {
        "iteration_count": len(iterations),
        "settle_reset_count": int(settle_reset_count),
        "longest_stable_window_polls": int(longest_stable),
        "mutation_count_start": mutation_counts[0] if mutation_counts else 0,
        "mutation_count_end": mutation_counts[-1] if mutation_counts else 0,
        "mutation_count_delta": (mutation_counts[-1] - mutation_counts[0]) if len(mutation_counts) >= 2 else 0,
        "largest_dom_node_delta": largest_node_delta,
        "largest_mutation_burst": largest_mutation_burst,
        "largest_mutation_batch": largest_batch,
        "top_mutation_attribution": top_attribution,
        "top_chart_mutation_attribution": top_chart_attribution,
        "chart_mutation_records": sum(int(item.get("records") or 0) for item in chart_attribution.values()),
        "visible_chart_mutation_records": sum(int(item.get("records") or 0) for item in chart_attribution.values() if item.get("visible")),
        "hidden_chart_mutation_records": sum(int(item.get("records") or 0) for item in chart_attribution.values() if not item.get("visible")),
        "visible_mutation_records": sum(int(item.get("records") or 0) for item in attribution.values() if item.get("visible")),
        "hidden_mutation_records": sum(int(item.get("records") or 0) for item in attribution.values() if not item.get("visible")),
        "root_identity_change_count": len(root_changes),
        "root_identity_changes": root_changes[-20:],
        "active_page_detach_events": detach_events[-20:],
        "loading_indicator_poll_count": loading_polls,
        "summary_table_exists_poll_count": summary_exists_polls,
        "design_guide_container_exists_poll_count": dg_exists_polls,
        "classification_hints": classifications,
        "first_snapshot": iterations[0].get("snapshot"),
        "last_snapshot": iterations[-1].get("snapshot"),
        "iterations_tail": iterations[-20:],
    }


def _page_cycle_extract_probe_events(page) -> dict[str, Any]:
    try:
        state = _load_browser_state(page)
    except Exception as exc:
        return {"browser_state_read_error": f"{type(exc).__name__}: {exc}", "events": []}
    ux = dict(state.get("ux_latency_probe") or {})
    speed = dict(state.get("speed_profile_probe") or {})
    events = list(ux.get("recent_events") or [])
    return {
        "events": events[-120:],
        "ux_counts": dict(ux.get("counts") or {}),
        "speed_top_sections": list(speed.get("sections") or [])[:20],
    }


def _page_cycle_build_mutation_attribution(page_cycle_diagnostics: dict[str, Any], probe_events: dict[str, Any]) -> dict[str, Any]:
    events = [
        dict(event)
        for event in list((probe_events or {}).get("events") or [])
        if isinstance(event, dict)
    ]

    def _nearby_events(timestamp_ms: Any, needle: str) -> list[dict[str, Any]]:
        try:
            ts = int(timestamp_ms or 0)
        except Exception:
            return []
        out = []
        for event in events:
            try:
                ets = int(event.get("timestamp_ms") or 0)
            except Exception:
                continue
            name = str(event.get("name") or "")
            if needle not in name:
                continue
            if abs(ets - ts) <= 2000:
                out.append(
                    {
                        "timestamp_ms": ets,
                        "delta_ms": ets - ts,
                        "name": name,
                        "cache_hit": event.get("cache_hit"),
                        "fingerprint_sha1": event.get("fingerprint_sha1"),
                        "meta": dict(event.get("meta") or {}),
                    }
                )
        return out[:20]

    pages_out = []
    global_attribution: dict[str, dict[str, Any]] = {}
    largest_batch: dict[str, Any] = {}
    for page_item in list((page_cycle_diagnostics or {}).get("pages") or []):
        churn = dict(page_item.get("churn_summary") or {})
        page_batches = []
        for iteration in list(churn.get("iterations_tail") or []):
            snap = dict(iteration.get("snapshot") or {})
            for batch in list(snap.get("mutation_recent_batches") or []):
                if not isinstance(batch, dict):
                    continue
                if int(batch.get("records") or 0) >= int(largest_batch.get("records") or 0):
                    largest_batch = {
                        "page": page_item.get("page"),
                        "iteration": iteration.get("iteration"),
                        **dict(batch),
                    }
                for owner in list(batch.get("topOwners") or []):
                    if not isinstance(owner, dict):
                        continue
                    key = "|".join(
                        [
                            str(owner.get("owner") or "unknown"),
                            str(owner.get("label") or "unknown")[:120],
                            "visible" if owner.get("visible") else "hidden",
                        ]
                    )
                    current = dict(global_attribution.get(key) or {})
                    current["owner"] = owner.get("owner") or "unknown"
                    current["label"] = owner.get("label") or "unknown"
                    current["visible"] = bool(owner.get("visible"))
                    current["records"] = int(current.get("records") or 0) + int(owner.get("records") or 0)
                    current["added"] = int(current.get("added") or 0) + int(owner.get("added") or 0)
                    current["removed"] = int(current.get("removed") or 0) + int(owner.get("removed") or 0)
                    current["attributes"] = int(current.get("attributes") or 0) + int(owner.get("attributes") or 0)
                    global_attribution[key] = current
                page_batches.append(
                    {
                        "iteration": iteration.get("iteration"),
                        "timestamp_ms": batch.get("at"),
                        "records": batch.get("records"),
                        "added": batch.get("added"),
                        "removed": batch.get("removed"),
                        "attributes": batch.get("attributes"),
                        "top_owners": list(batch.get("topOwners") or [])[:10],
                        "summary_rebuild_events_within_2s": _nearby_events(batch.get("at"), "summary.overview_pack_rebuild"),
                        "candidate_preview_events_within_2s": _nearby_events(batch.get("at"), "candidate_preview_evaluation"),
                    }
                )
        pages_out.append(
            {
                "page": page_item.get("page"),
                "settled": page_item.get("settled"),
                "settle_elapsed_ms": page_item.get("settle_elapsed_ms"),
                "largest_mutation_burst": churn.get("largest_mutation_burst"),
                "top_mutation_attribution": list(churn.get("top_mutation_attribution") or [])[:10],
                "recent_batches": page_batches[-25:],
            }
        )
    top_global = sorted(
        global_attribution.values(),
        key=lambda item: (
            -int(item.get("records") or 0),
            -int(item.get("added") or 0) - int(item.get("removed") or 0),
            str(item.get("owner") or ""),
        ),
    )[:30]
    return {
        "created_at_ms": int(time.time() * 1000),
        "largest_mutation_batch": largest_batch,
        "top_global_mutation_attribution": top_global,
        "visible_mutation_records": sum(int(item.get("records") or 0) for item in global_attribution.values() if item.get("visible")),
        "hidden_mutation_records": sum(int(item.get("records") or 0) for item in global_attribution.values() if not item.get("visible")),
        "pages": pages_out,
        "probe_event_count": len(events),
        "speed_top_sections": list((probe_events or {}).get("speed_top_sections") or [])[:20],
    }


def _page_cycle_build_chart_mutation_diagnostics(page_cycle_diagnostics: dict[str, Any]) -> dict[str, Any]:
    pages_out: list[dict[str, Any]] = []
    global_charts: dict[str, dict[str, Any]] = {}
    largest_chart_owner: dict[str, Any] = {}
    for page_item in list((page_cycle_diagnostics or {}).get("pages") or []):
        churn = dict(page_item.get("churn_summary") or {})
        page_charts: dict[str, dict[str, Any]] = {}
        recent_chart_batches: list[dict[str, Any]] = []
        last_snapshot = dict(churn.get("last_snapshot") or {})
        for iteration in list(churn.get("iterations_tail") or []):
            snap = dict(iteration.get("snapshot") or {})
            for batch in list(snap.get("mutation_recent_batches") or []):
                if not isinstance(batch, dict):
                    continue
                top_charts = [dict(item) for item in list(batch.get("topCharts") or []) if isinstance(item, dict)]
                if top_charts:
                    recent_chart_batches.append(
                        {
                            "iteration": iteration.get("iteration"),
                            "timestamp_ms": batch.get("at"),
                            "batch_records": batch.get("records"),
                            "charts": top_charts[:10],
                        }
                    )
                for chart in top_charts:
                    key = "|".join(
                        [
                            str(chart.get("id") or "unknown"),
                            str(chart.get("label") or "unknown")[:120],
                            "visible" if chart.get("visible") else "hidden",
                        ]
                    )
                    for store in (page_charts, global_charts):
                        current = dict(store.get(key) or {})
                        current["id"] = chart.get("id")
                        current["owner"] = chart.get("owner") or "plotly_or_chart"
                        current["label"] = chart.get("label") or "unknown"
                        current["visible"] = bool(chart.get("visible"))
                        current["records"] = int(current.get("records") or 0) + int(chart.get("records") or 0)
                        current["added"] = int(current.get("added") or 0) + int(chart.get("added") or 0)
                        current["removed"] = int(current.get("removed") or 0) + int(chart.get("removed") or 0)
                        current["attributes"] = int(current.get("attributes") or 0) + int(chart.get("attributes") or 0)
                        current["structural"] = int(current.get("structural") or 0) + int(chart.get("structural") or 0)
                        current["attribute_only"] = bool(current.get("attributes")) and int(current.get("structural") or 0) == 0
                        current["svg_count"] = chart.get("svg_count")
                        current["canvas_count"] = chart.get("canvas_count")
                        current["webgl_canvas_count"] = chart.get("webgl_canvas_count")
                        store[key] = current
        top_page_charts = sorted(
            page_charts.values(),
            key=lambda item: (
                -int(item.get("records") or 0),
                -int(item.get("structural") or 0),
                str(item.get("label") or ""),
            ),
        )[:20]
        if top_page_charts and int(top_page_charts[0].get("records") or 0) >= int(largest_chart_owner.get("records") or 0):
            largest_chart_owner = {"page": page_item.get("page"), **dict(top_page_charts[0])}
        pages_out.append(
            {
                "page": page_item.get("page"),
                "settled": page_item.get("settled"),
                "settle_elapsed_ms": page_item.get("settle_elapsed_ms"),
                "plotly_container_count": last_snapshot.get("plotly_container_count"),
                "visible_plotly_container_count": last_snapshot.get("visible_plotly_container_count"),
                "hidden_plotly_container_count": last_snapshot.get("hidden_plotly_container_count"),
                "svg_node_count": last_snapshot.get("svg_node_count"),
                "canvas_node_count": last_snapshot.get("canvas_node_count"),
                "webgl_canvas_count": last_snapshot.get("webgl_canvas_count"),
                "chart_mutation_total_records": sum(int(item.get("records") or 0) for item in page_charts.values()),
                "chart_mutation_visible_records": sum(int(item.get("records") or 0) for item in page_charts.values() if item.get("visible")),
                "chart_mutation_hidden_records": sum(int(item.get("records") or 0) for item in page_charts.values() if not item.get("visible")),
                "top_chart_mutation_owners": top_page_charts,
                "recent_chart_batches": recent_chart_batches[-25:],
            }
        )
    top_global = sorted(
        global_charts.values(),
        key=lambda item: (
            -int(item.get("records") or 0),
            -int(item.get("structural") or 0),
            str(item.get("label") or ""),
        ),
    )[:30]
    return {
        "created_at_ms": int(time.time() * 1000),
        "largest_chart_mutation_owner": largest_chart_owner,
        "top_global_chart_mutation_owners": top_global,
        "chart_mutation_total_records": sum(int(item.get("records") or 0) for item in global_charts.values()),
        "chart_mutation_visible_records": sum(int(item.get("records") or 0) for item in global_charts.values() if item.get("visible")),
        "chart_mutation_hidden_records": sum(int(item.get("records") or 0) for item in global_charts.values() if not item.get("visible")),
        "pages": pages_out,
    }


def _page_cycle_stability_window_ms(iterations: list[dict[str, Any]], key_fn) -> dict[str, Any]:
    if not iterations:
        return {"longest_stable_ms": 0, "last_stable_ms": 0, "change_count": 0}
    longest = 0
    last_run = 0
    change_count = 0
    previous_key = None
    previous_elapsed = int(iterations[0].get("elapsed_ms") or 0)
    run_start = previous_elapsed
    for row in iterations:
        elapsed = int(row.get("elapsed_ms") or 0)
        key = key_fn(dict(row.get("snapshot") or {}), row)
        if previous_key is None:
            previous_key = key
            run_start = elapsed
        elif key != previous_key:
            last_run = max(0, previous_elapsed - run_start)
            longest = max(longest, last_run)
            change_count += 1
            previous_key = key
            run_start = elapsed
        previous_elapsed = elapsed
    last_run = max(0, previous_elapsed - run_start)
    longest = max(longest, last_run)
    return {"longest_stable_ms": int(longest), "last_stable_ms": int(last_run), "change_count": int(change_count)}


def _page_cycle_build_settle_signal_breakdown(page_cycle_diagnostics: dict[str, Any]) -> dict[str, Any]:
    pages_out: list[dict[str, Any]] = []
    for page_item in list((page_cycle_diagnostics or {}).get("pages") or []):
        churn = dict(page_item.get("churn_summary") or {})
        iterations = [dict(item) for item in list(churn.get("iterations_tail") or []) if isinstance(item, dict)]

        def _content_key(snapshot: dict[str, Any], row: dict[str, Any]) -> str:
            return json.dumps(
                {
                    "current_slug": page_item.get("current_slug"),
                    "visible_non_chart_text_hash": snapshot.get("visible_non_chart_text_hash") or snapshot.get("body_text_hash"),
                    "visible_card_count": snapshot.get("visible_card_count"),
                    "visible_calc_box_count": snapshot.get("visible_calc_box_count"),
                    "input_widget_count": snapshot.get("input_widget_count"),
                    "active_page_body_exists": snapshot.get("active_page_body_exists"),
                    "content_marker": (row.get("ready_conditions") or {}).get("marker_present"),
                },
                sort_keys=True,
            )

        def _identity_key(snapshot: dict[str, Any], _row: dict[str, Any]) -> str:
            return json.dumps(
                {
                    "page_root_id": snapshot.get("page_root_id"),
                    "page_root_hash": snapshot.get("page_root_hash"),
                    "design_guide_container_id": snapshot.get("design_guide_container_id"),
                    "design_guide_container_hash": snapshot.get("design_guide_container_hash"),
                },
                sort_keys=True,
            )

        def _full_dom_key(snapshot: dict[str, Any], row: dict[str, Any]) -> str:
            return json.dumps(
                {
                    "signature": row.get("signature"),
                    "dom_node_count": snapshot.get("dom_node_count"),
                    "mutation_count_total": snapshot.get("mutation_count_total"),
                    "last_mutation_batch_size": snapshot.get("last_mutation_batch_size"),
                },
                sort_keys=True,
            )

        def _chart_key(snapshot: dict[str, Any], _row: dict[str, Any]) -> str:
            return json.dumps(
                {
                    "chart_mutation_total_records": snapshot.get("chart_mutation_total_records"),
                    "visible_plotly_container_count": snapshot.get("visible_plotly_container_count"),
                    "svg_node_count": snapshot.get("svg_node_count"),
                    "canvas_node_count": snapshot.get("canvas_node_count"),
                },
                sort_keys=True,
            )

        content_window = _page_cycle_stability_window_ms(iterations, _content_key)
        identity_window = _page_cycle_stability_window_ms(iterations, _identity_key)
        full_dom_window = _page_cycle_stability_window_ms(iterations, _full_dom_key)
        chart_window = _page_cycle_stability_window_ms(iterations, _chart_key)
        chart_mutating_after_content_stable_ms = 0
        content_stable_seen_at: int | None = None
        previous_content_key = None
        previous_chart_total: int | None = None
        stable_content_start = 0
        for row in iterations:
            elapsed = int(row.get("elapsed_ms") or 0)
            snapshot = dict(row.get("snapshot") or {})
            content_key = _content_key(snapshot, row)
            chart_total = int(snapshot.get("chart_mutation_total_records") or 0)
            if previous_content_key is None or content_key != previous_content_key:
                previous_content_key = content_key
                stable_content_start = elapsed
            elif content_stable_seen_at is None and elapsed - stable_content_start >= 1000:
                content_stable_seen_at = stable_content_start
            if content_stable_seen_at is not None and previous_chart_total is not None and chart_total > previous_chart_total:
                chart_mutating_after_content_stable_ms = max(chart_mutating_after_content_stable_ms, elapsed - content_stable_seen_at)
            previous_chart_total = chart_total
        reason = "settled"
        if not page_item.get("settled"):
            last_snapshot = dict(churn.get("last_snapshot") or {})
            if page_item.get("current_slug") != page_item.get("page"):
                reason = "slug_not_expected"
            elif page_item.get("loading_visible"):
                reason = "loading_visible"
            elif not (page_item.get("body_text_length") or 0):
                reason = "body_text_empty"
            elif not ((page_item.get("content_marker") or {}).get("marker_present") or (page_item.get("content_marker") or {}).get("shear_page_ready")):
                reason = "content_marker_missing"
            elif int(last_snapshot.get("chart_mutation_total_records") or 0) > 0:
                reason = "content_ready_but_chart_or_dom_still_mutating"
            else:
                reason = "content_signature_not_stable"
        pages_out.append(
            {
                "page": page_item.get("page"),
                "settled": bool(page_item.get("settled")),
                "settle_elapsed_ms": page_item.get("settle_elapsed_ms"),
                "reason_settle_failed": reason,
                "content_stable_ms": content_window.get("longest_stable_ms"),
                "content_last_stable_ms": content_window.get("last_stable_ms"),
                "content_change_count": content_window.get("change_count"),
                "chart_internal_mutating_ms": int(chart_mutating_after_content_stable_ms),
                "chart_signal_last_stable_ms": chart_window.get("last_stable_ms"),
                "chart_signal_change_count": chart_window.get("change_count"),
                "full_dom_stable_ms": full_dom_window.get("longest_stable_ms"),
                "full_dom_last_stable_ms": full_dom_window.get("last_stable_ms"),
                "full_dom_change_count": full_dom_window.get("change_count"),
                "root_page_body_stable_ms": identity_window.get("longest_stable_ms"),
                "root_page_body_change_count": identity_window.get("change_count"),
                "design_guide_stable": int(churn.get("design_guide_container_exists_poll_count") or 0) == int(churn.get("iteration_count") or 0),
                "root_identity_change_count": churn.get("root_identity_change_count"),
                "active_page_detach_events": list(churn.get("active_page_detach_events") or []),
            }
        )
    slowest = sorted(pages_out, key=lambda item: int(item.get("settle_elapsed_ms") or 0), reverse=True)[:5]
    return {
        "created_at_ms": int(time.time() * 1000),
        "pages": pages_out,
        "slowest_pages": slowest,
        "content_stable_ms": max([int(item.get("content_stable_ms") or 0) for item in pages_out] or [0]),
        "chart_internal_mutating_ms": max([int(item.get("chart_internal_mutating_ms") or 0) for item in pages_out] or [0]),
        "full_dom_stable_ms": max([int(item.get("full_dom_stable_ms") or 0) for item in pages_out] or [0]),
    }


def _page_cycle_build_chart_internal_filter_audit(page_cycle_diagnostics: dict[str, Any]) -> dict[str, Any]:
    pages_out: list[dict[str, Any]] = []
    total_observed = 0
    total_ignored = 0
    total_retained = 0
    activated_pages: list[str] = []
    for page_item in list((page_cycle_diagnostics or {}).get("pages") or []):
        settle = dict(page_item.get("settle_filter_audit") or {})
        ignored = int(settle.get("chart_internal_mutations_ignored_after_content_stable") or 0)
        retained = int(settle.get("non_chart_mutations_retained_after_content_stable") or 0)
        observed = int(settle.get("total_mutations_observed") or 0)
        total_observed += observed
        total_ignored += ignored
        total_retained += retained
        if bool(settle.get("filter_activated")):
            activated_pages.append(str(page_item.get("page") or ""))
        pages_out.append(
            {
                "page": page_item.get("page"),
                "settled": page_item.get("settled"),
                "settle_elapsed_ms": page_item.get("settle_elapsed_ms"),
                "total_mutations_observed": observed,
                "chart_internal_mutations_ignored": ignored,
                "non_chart_mutations_retained": retained,
                "content_stability_gate_satisfied": bool(settle.get("content_stability_gate_satisfied")),
                "first_content_stable_elapsed_ms": settle.get("first_content_stable_elapsed_ms"),
                "filter_activated": bool(settle.get("filter_activated")),
                "visible_chart_mutation_count": settle.get("visible_chart_mutation_count"),
                "hidden_chart_mutation_count": settle.get("hidden_chart_mutation_count"),
                "ignored_mutation_selectors_or_classes": list(settle.get("ignored_mutation_selectors_or_classes") or [])[:20],
                "final_settle_decision": "settled" if page_item.get("settled") else "failed",
                "reason_if_failed": settle.get("reason_if_failed"),
            }
        )
    return {
        "created_at_ms": int(time.time() * 1000),
        "total_mutations_observed": total_observed,
        "chart_internal_mutations_ignored": total_ignored,
        "non_chart_mutations_retained": total_retained,
        "filter_activated": bool(activated_pages),
        "activated_pages": activated_pages,
        "pages": pages_out,
    }


def _page_cycle_text_item_key(item: dict[str, Any]) -> str:
    return "|".join(
        [
            str(item.get("category") or "unknown"),
            str(item.get("owner") or "unknown"),
            str(item.get("owner_label") or "")[:80],
            str(item.get("text_hash") or ""),
        ]
    )


def _page_cycle_text_diff(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
    previous_by_key = {_page_cycle_text_item_key(dict(item)): dict(item) for item in previous if isinstance(item, dict)}
    current_by_key = {_page_cycle_text_item_key(dict(item)): dict(item) for item in current if isinstance(item, dict)}
    removed_keys = [key for key in previous_by_key if key not in current_by_key]
    added_keys = [key for key in current_by_key if key not in previous_by_key]
    previous_by_owner: dict[str, list[dict[str, Any]]] = {}
    current_by_owner: dict[str, list[dict[str, Any]]] = {}
    for item in previous_by_key.values():
        previous_by_owner.setdefault("|".join([str(item.get("category") or ""), str(item.get("owner_label") or "")[:80]]), []).append(item)
    for item in current_by_key.values():
        current_by_owner.setdefault("|".join([str(item.get("category") or ""), str(item.get("owner_label") or "")[:80]]), []).append(item)
    changed = []
    for owner_key in sorted(set(previous_by_owner) & set(current_by_owner)):
        before = " | ".join(str(item.get("text") or "") for item in previous_by_owner[owner_key])[:200]
        after = " | ".join(str(item.get("text") or "") for item in current_by_owner[owner_key])[:200]
        if before != after:
            sample = current_by_owner[owner_key][0] if current_by_owner[owner_key] else {}
            changed.append(
                {
                    "category": sample.get("category"),
                    "nearest_section_heading": sample.get("owner_label"),
                    "nearest_card_or_container_label": sample.get("owner_label"),
                    "before": before,
                    "after": after,
                }
            )
    def _compact(keys: list[str], source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for key in keys[:20]:
            item = dict(source.get(key) or {})
            out.append(
                {
                    "text": str(item.get("text") or "")[:200],
                    "category": item.get("category"),
                    "nearest_section_heading": item.get("owner_label"),
                    "nearest_card_or_container_label": item.get("owner_label"),
                    "owner": item.get("owner"),
                    "tag": item.get("tag"),
                    "testid": item.get("testid"),
                    "cls": str(item.get("cls") or "")[:120],
                }
            )
        return out
    return {
        "added_visible_text_lines": _compact(added_keys, current_by_key),
        "removed_visible_text_lines": _compact(removed_keys, previous_by_key),
        "changed_visible_text_snippets": changed[:20],
    }


def _page_cycle_build_bending_content_stability_diff(page_cycle_diagnostics: dict[str, Any]) -> dict[str, Any]:
    pages_out: list[dict[str, Any]] = []
    repeated_snippets: dict[str, dict[str, Any]] = {}
    repeated_containers: dict[str, dict[str, Any]] = {}
    for page_item in list((page_cycle_diagnostics or {}).get("pages") or []):
        if page_item.get("page") != "bending":
            continue
        churn = dict(page_item.get("churn_summary") or {})
        previous_items: list[dict[str, Any]] = []
        previous_hash: str | None = None
        stable_run_start: int | None = None
        longest_stable_ms = 0
        hash_change_count = 0
        poll_rows: list[dict[str, Any]] = []
        reset_events: list[dict[str, Any]] = []
        for iteration in list(churn.get("iterations_tail") or []):
            if not isinstance(iteration, dict):
                continue
            snap = dict(iteration.get("snapshot") or {})
            elapsed = int(iteration.get("elapsed_ms") or 0)
            items = [dict(item) for item in list(snap.get("visible_non_chart_text_items") or []) if isinstance(item, dict)]
            current_hash = str(snap.get("visible_non_chart_text_hash") or snap.get("body_text_hash") or "")
            reset = previous_hash is not None and current_hash != previous_hash
            diff = _page_cycle_text_diff(previous_items, items) if previous_hash is not None else {
                "added_visible_text_lines": [],
                "removed_visible_text_lines": [],
                "changed_visible_text_snippets": [],
            }
            if reset:
                hash_change_count += 1
                if stable_run_start is not None:
                    longest_stable_ms = max(longest_stable_ms, max(0, elapsed - stable_run_start))
                stable_run_start = elapsed
                categories: dict[str, int] = {}
                for bucket in (
                    diff.get("added_visible_text_lines") or [],
                    diff.get("removed_visible_text_lines") or [],
                    diff.get("changed_visible_text_snippets") or [],
                ):
                    for change in bucket:
                        category = str((change or {}).get("category") or "unknown")
                        categories[category] = categories.get(category, 0) + 1
                        text = str((change or {}).get("text") or (change or {}).get("after") or (change or {}).get("before") or "")[:200]
                        if text:
                            current = dict(repeated_snippets.get(text) or {"text": text, "count": 0, "category": category})
                            current["count"] = int(current.get("count") or 0) + 1
                            repeated_snippets[text] = current
                        label = str((change or {}).get("nearest_card_or_container_label") or "unknown")[:200]
                        current_label = dict(repeated_containers.get(label) or {"label": label, "count": 0, "category": category})
                        current_label["count"] = int(current_label.get("count") or 0) + 1
                        repeated_containers[label] = current_label
                reset_events.append(
                    {
                        "poll_index": iteration.get("iteration"),
                        "elapsed_ms": elapsed,
                        "from_hash": previous_hash,
                        "to_hash": current_hash,
                        "dominant_categories": sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:8],
                        "diff": diff,
                    }
                )
            elif stable_run_start is None:
                stable_run_start = elapsed
            if stable_run_start is not None:
                longest_stable_ms = max(longest_stable_ms, max(0, elapsed - stable_run_start))
            poll_rows.append(
                {
                    "poll_index": iteration.get("iteration"),
                    "timestamp_ms": snap.get("timestamp_ms"),
                    "elapsed_ms": elapsed,
                    "active_page_slug": page_item.get("current_slug"),
                    "visible_non_chart_text_hash": current_hash,
                    "visible_non_chart_text_length": snap.get("visible_non_chart_text_length"),
                    "visible_card_count": snap.get("visible_card_count"),
                    "visible_calc_check_box_count": snap.get("visible_calc_box_count"),
                    "visible_heading_list": list((page_item.get("content_marker") or {}).get("headings") or [])[:12],
                    "loading_indicator_count": snap.get("loading_spinner_count"),
                    "faded_inert_overlay_count": snap.get("faded_inactive_overlay_count"),
                    "summary_check_container_count": 1 if snap.get("summary_table_exists") else 0,
                    "active_page_root_identity": {
                        "id": snap.get("page_root_id"),
                        "hash": snap.get("page_root_hash"),
                    },
                    "content_stability_timer_reset": bool(reset),
                    "visible_non_chart_text_items": [
                        {
                            "text": str(item.get("text") or "")[:200],
                            "category": item.get("category"),
                            "nearest_section_heading": item.get("owner_label"),
                            "nearest_card_or_container_label": item.get("owner_label"),
                            "owner": item.get("owner"),
                            "tag": item.get("tag"),
                            "testid": item.get("testid"),
                        }
                        for item in items[:30]
                    ],
                }
            )
            previous_hash = current_hash
            previous_items = items
        reason = "not_bending_failure"
        if page_item.get("settled"):
            reason = "bending_settled"
        elif not poll_rows:
            reason = "no_bending_polls"
        elif hash_change_count:
            reason = "visible_non_chart_content_changed_before_timeout"
        else:
            reason = "content_gate_blocked_without_hash_change"
        category_counts: dict[str, int] = {}
        for event in reset_events:
            for category, count in list(event.get("dominant_categories") or []):
                category_counts[str(category)] = category_counts.get(str(category), 0) + int(count or 0)
        likely_noise = any(key in category_counts for key in ("debug_or_probe_text", "loading_marker", "expander_or_status", "streamlit_widget_label_or_value"))
        likely_meaningful = any(key in category_counts for key in ("calc_or_check_result", "page_navigation_or_header"))
        pages_out.append(
            {
                "page": page_item.get("page"),
                "settled": bool(page_item.get("settled")),
                "settle_elapsed_ms": page_item.get("settle_elapsed_ms"),
                "polls": poll_rows,
                "content_hash_change_count": hash_change_count,
                "longest_stable_visible_content_window_ms": int(longest_stable_ms),
                "reason_content_gate_never_passed": reason,
                "reset_events": reset_events[:20],
                "top_changing_categories": sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))[:10],
                "likely_user_visible_meaningful_content": bool(likely_meaningful),
                "likely_verifier_debug_or_status_noise": bool(likely_noise),
            }
        )
    top_snippets = sorted(repeated_snippets.values(), key=lambda item: (-int(item.get("count") or 0), str(item.get("text") or "")))[:20]
    top_containers = sorted(repeated_containers.values(), key=lambda item: (-int(item.get("count") or 0), str(item.get("label") or "")))[:20]
    return {
        "created_at_ms": int(time.time() * 1000),
        "pages": pages_out,
        "top_repeated_changing_text_snippets": top_snippets,
        "top_repeated_changing_container_labels": top_containers,
        "bending_content_hash_changed": any(int(page.get("content_hash_change_count") or 0) > 0 for page in pages_out),
        "longest_stable_visible_content_window_ms": max([int(page.get("longest_stable_visible_content_window_ms") or 0) for page in pages_out] or [0]),
    }


def _page_cycle_bending_ready_marker(page) -> dict[str, Any]:
    script = r"""
    () => {
      const perfStart = performance.now();
      const now = Date.now();
      window.__codexBendingReadyNodeIds = window.__codexBendingReadyNodeIds || new WeakMap();
      window.__codexBendingReadyNodeSeq = window.__codexBendingReadyNodeSeq || 1;
      const nodeId = (el) => {
        if (!el) return null;
        if (!window.__codexBendingReadyNodeIds.has(el)) {
          window.__codexBendingReadyNodeIds.set(el, window.__codexBendingReadyNodeSeq++);
        }
        return window.__codexBendingReadyNodeIds.get(el);
      };
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const hash = (value) => {
        const text = String(value || "");
        let h = 2166136261;
        for (let i = 0; i < text.length; i += 1) {
          h ^= text.charCodeAt(i);
          h = Math.imul(h, 16777619);
        }
        return (h >>> 0).toString(16);
      };
      const visible = (el) => {
        if (!el) return false;
        if (el.hasAttribute && (el.hasAttribute("hidden") || el.hasAttribute("inert") || el.closest("[inert]"))) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 4 && rect.height > 4;
      };
      const nodes = (selector) => {
        try { return Array.from(document.querySelectorAll(selector)); }
        catch (_err) { return []; }
      };
      const visibleTextItems = (selector) => nodes(selector)
        .filter(visible)
        .map((el) => clean(String(el.textContent || el.innerText || "").slice(0, 1200)))
        .filter(Boolean);
      const visibleTextItemsLimited = (selector, limit = 40, chars = 360) => {
        const out = [];
        for (const el of nodes(selector)) {
          if (!visible(el)) continue;
          const text = clean(String(el.textContent || el.innerText || "").slice(0, chars));
          if (text) out.push(text);
          if (out.length >= limit) break;
        }
        return out;
      };
      const scanSelector = [
        "h1",
        "h2",
        "h3",
        "[data-testid='stHeading']",
        ".summary-check-card",
        "[data-testid*='check' i]",
        "button",
        "label",
        "[role='button']"
      ].join(",");
      const allVisibleText = visibleTextItemsLimited(scanSelector, 80, 360);
      const visibleMarkdownText = visibleTextItemsLimited("[data-testid='stMarkdownContainer']", 40, 360);
      const afterVisibleText = performance.now();
      const pageRoot = document.querySelector("main") || document.querySelector("[data-testid='stAppViewContainer']") || document.body;
      const isAppChrome = (el) => Boolean(el && el.closest && el.closest([
        "header",
        "[data-testid='stStatusWidget']",
        "[data-testid='stToolbar']",
        "[data-testid='stDecoration']",
        "[data-testid='stDeployButton']",
        "[data-testid='stMainMenu']"
      ].join(",")));
      const loadingVisible = nodes('[data-testid="stSpinner"], [data-testid="stSkeleton"], [role="progressbar"], [aria-busy="true"]')
        .some(visible);
      const afterLoadingQuery = performance.now();
      const headingPresent = [...allVisibleText, ...visibleMarkdownText].some((text) => /Bending capacity/i.test(text));
      const sectionPresent = allVisibleText.some((text) => /^Section$/i.test(text) || /\bSection\s+Side view\b/i.test(text));
      const sideViewPresent = allVisibleText.some((text) => /^Side view$/i.test(text) || /\bSection\s+Side view\b/i.test(text));
      const stopVisible = nodes("button,[role='button']")
        .filter(visible)
        .filter((el) => !isAppChrome(el))
        .some((el) => /^Stop$/i.test(clean(el.innerText || el.textContent)));
      const ulsCardTexts = visibleTextItemsLimited(
        "[data-testid='stExpander'], .summary-check-card, [data-testid*='check' i]",
        60,
        500
      );
      const bendingUlsCardPresent = ulsCardTexts.some((text) => /Bending\s+[—-]\s+ULS/i.test(text) || /Sagging bending check/i.test(text));
      const afterUlsQuery = performance.now();
      const visibleCount = (selector) => nodes(selector).filter(visible).length;
      const cardCount = [
        "[data-testid='stExpander']",
        ".summary-check-card",
        ".fast-guidance-item",
        "[data-testid='design-guide-card']"
      ].reduce((acc, selector) => acc + visibleCount(selector), 0);
      const calcCount = [
        ".summary-check-card",
        "[data-testid*='check' i]"
      ].reduce((acc, selector) => acc + visibleCount(selector), 0);
      const afterCountQuery = performance.now();
      const fadedCandidates = nodes("main [inert], main [aria-disabled='true'], main [style*='opacity'], main [class*='overlay' i], main [data-testid*='overlay' i]").filter((el) => {
        if (!visible(el)) return false;
        if (isAppChrome(el)) return false;
        if (el.closest("[data-testid='stPlotlyChart'], .js-plotly-plot, .plot-container, .svg-container")) return false;
        const rect = el.getBoundingClientRect();
        const opacity = Number(window.getComputedStyle(el).opacity || "1");
        return opacity > 0.02 && opacity < 0.65 && rect.width > 120 && rect.height > 24;
      });
      const fadedCandidateSet = new Set(fadedCandidates);
      const fadedRoots = fadedCandidates.filter((el) => {
        let parent = el.parentElement;
        while (parent) {
          if (fadedCandidateSet.has(parent)) return false;
          parent = parent.parentElement;
        }
        return true;
      });
      const fadedCount = fadedRoots.length;
      const afterFadedQuery = performance.now();
      const rootSignature = (el) => {
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        return hash([
          String(el.tagName || ""),
          String(el.className || "").slice(0, 160),
          el.getAttribute ? (el.getAttribute("data-testid") || "") : "",
          Math.round(rect.width),
          Math.round(rect.height)
        ].join("|"));
      };
      const rootSignatureValue = rootSignature(pageRoot);
      const afterRootHash = performance.now();
      const readinessText = [
        ...allVisibleText.filter((text) => /^(Bending capacity|Section|Side view|ULS|SLS|State:)$/i.test(text) || /Bending\s*(?:—|–|-|â€”|â€“)\s*ULS|Sagging bending check/i.test(text)),
        ...visibleMarkdownText.filter((text) => /Bending capacity|Bending\s*(?:—|–|-|â€”|â€“)\s*ULS|Sagging bending check/i.test(text)),
        ...ulsCardTexts.filter((text) => /Bending\s*(?:—|–|-|â€”|â€“)\s*ULS|Sagging bending check|Applied|Capacity|Utilisation/i.test(text)),
      ];
      const visibleNonChartText = readinessText
        .filter(Boolean)
        .map((text) => text.slice(0, 240))
        .join(" | ")
        .slice(0, 4000);
      const visibleNonChartTextHash = hash(visibleNonChartText);
      const afterReadinessHash = performance.now();
      return {
        timestamp_ms: now,
        loading_visible: loadingVisible,
        heading_present: headingPresent,
        section_present: sectionPresent,
        side_view_present: sideViewPresent,
        stop_absent: !stopVisible,
        stop_visible: stopVisible,
        bending_uls_card_present: bendingUlsCardPresent,
        faded_inert_count: fadedCount,
        visible_card_count: cardCount,
        visible_calc_check_count: calcCount,
        visible_non_chart_text_hash: visibleNonChartTextHash,
        visible_non_chart_text_length: visibleNonChartText.length,
        root_identity: {id: nodeId(pageRoot), hash: rootSignatureValue},
        marker_timing_ms: {
          total_js_ms: Number((afterReadinessHash - perfStart).toFixed(3)),
          total_poll_ms: Number((afterReadinessHash - perfStart).toFixed(3)),
          dom_query_ms: Number((afterVisibleText - perfStart).toFixed(3)),
          visible_text_hash_ms: Number((afterReadinessHash - afterRootHash).toFixed(3)),
          chart_mutation_query_ms: 0,
          faded_inert_query_ms: Number((afterFadedQuery - afterCountQuery).toFixed(3)),
          loading_query_ms: Number((afterLoadingQuery - afterVisibleText).toFixed(3)),
          uls_card_query_ms: Number((afterUlsQuery - afterLoadingQuery).toFixed(3)),
          card_count_query_ms: Number((afterCountQuery - afterUlsQuery).toFixed(3)),
          root_identity_hash_ms: Number((afterRootHash - afterFadedQuery).toFixed(3)),
          screenshot_cost_ms: 0
        },
        visible_heading_list: visibleTextItemsLimited("h1,h2,h3,[data-testid='stHeading']", 12, 240),
        visible_bending_controls: allVisibleText.filter((text) => /^(Section|Side view|ULS|SLS|State:)$/i.test(text)).slice(0, 20),
        visible_stop_texts: nodes("button,[role='button']")
          .filter(visible)
          .filter((el) => !isAppChrome(el))
          .map((el) => clean(el.innerText || el.textContent))
          .filter((text) => /Stop/i.test(text))
          .slice(0, 20),
        visible_chrome_stop_texts: nodes("button,[role='button'],[data-testid*='StatusWidget' i],header *,[data-testid='stStatusWidget']")
          .filter(visible)
          .filter(isAppChrome)
          .map((el) => clean(el.innerText || el.textContent))
          .filter((text) => /Stop/i.test(text))
          .slice(0, 20),
        faded_roots: fadedRoots.map((el) => clean(el.innerText || el.textContent).slice(0, 120)).filter(Boolean).slice(0, 12),
      };
    }
    """
    try:
        return dict(page.evaluate(script) or {})
    except Exception as exc:
        return {"marker_error": f"{type(exc).__name__}: {exc}"}


def _page_cycle_wait_for_bending_ready_gate(page, *, timeout_s: float = 45.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    polls: list[dict[str, Any]] = []
    stable = 0
    last_sig: str | None = None
    first_poll_ms: int | None = None
    ready_elapsed_ms: int | None = None
    start = time.perf_counter()
    final_unmet: list[str] = []
    while time.time() < deadline:
        poll_started = time.perf_counter()
        elapsed_ms = int(max(0.0, time.perf_counter() - start) * 1000)
        if first_poll_ms is None:
            first_poll_ms = elapsed_ms
        slug_started = time.perf_counter()
        current_slug = _page_cycle_current_slug(page)
        slug_done = time.perf_counter()
        marker_started = time.perf_counter()
        marker = _page_cycle_bending_ready_marker(page)
        marker_done = time.perf_counter()
        loading_visible = bool(marker.get("loading_visible"))
        faded_count = int(marker.get("faded_inert_count") or 0)
        card_count = int(marker.get("visible_card_count") or 0)
        calc_count = int(marker.get("visible_calc_check_count") or 0)
        text_hash = str(marker.get("visible_non_chart_text_hash") or "")
        root_identity = dict(marker.get("root_identity") or {})
        root_id = root_identity.get("id")
        root_hash = root_identity.get("hash")
        unmet = []
        if current_slug != "bending":
            unmet.append("active_page_not_bending")
        if not bool(marker.get("heading_present")):
            unmet.append("bending_heading_missing")
        if not bool(marker.get("section_present")):
            unmet.append("section_control_missing")
        if not bool(marker.get("side_view_present")):
            unmet.append("side_view_control_missing")
        if not bool(marker.get("stop_absent")):
            unmet.append("stop_control_still_visible")
        if not bool(marker.get("bending_uls_card_present")):
            unmet.append("bending_uls_card_missing")
        if loading_visible:
            unmet.append("loading_visible")
        if faded_count > 3:
            unmet.append("faded_or_inert_count_high")
        if not root_id or not root_hash:
            unmet.append("page_root_identity_missing")
        stable_calc_started = time.perf_counter()
        sig = json.dumps(
            {
                "slug": current_slug,
                "text_hash": text_hash,
                "card_count": card_count,
                "calc_count": calc_count,
                "root_id": root_id,
                "root_hash": root_hash,
                "faded_count": faded_count,
                "heading_present": bool(marker.get("heading_present")),
                "section_present": bool(marker.get("section_present")),
                "side_view_present": bool(marker.get("side_view_present")),
                "stop_absent": bool(marker.get("stop_absent")),
                "bending_uls_card_present": bool(marker.get("bending_uls_card_present")),
            },
            sort_keys=True,
        )
        stable_candidate = not unmet
        if stable_candidate and sig == last_sig:
            stable += 1
        elif stable_candidate:
            stable = 1
            last_sig = sig
        else:
            stable = 0
            last_sig = sig
        stable_calc_done = time.perf_counter()
        marker_timing = dict(marker.get("marker_timing_ms") or {})
        timing_breakdown = {
            "total_poll_ms": round((stable_calc_done - poll_started) * 1000.0, 3),
            "current_slug_ms": round((slug_done - slug_started) * 1000.0, 3),
            "marker_eval_ms": round((marker_done - marker_started) * 1000.0, 3),
            "stable_read_calculation_ms": round((stable_calc_done - stable_calc_started) * 1000.0, 3),
            "dom_query_ms": marker_timing.get("dom_query_ms"),
            "visible_text_hash_ms": marker_timing.get("visible_text_hash_ms"),
            "chart_mutation_query_ms": marker_timing.get("chart_mutation_query_ms", 0),
            "faded_inert_query_ms": marker_timing.get("faded_inert_query_ms"),
            "screenshot_cost_ms": marker_timing.get("screenshot_cost_ms", 0),
            "js_total_ms": marker_timing.get("total_js_ms"),
            "js_loading_query_ms": marker_timing.get("loading_query_ms"),
            "js_uls_card_query_ms": marker_timing.get("uls_card_query_ms"),
            "js_card_count_query_ms": marker_timing.get("card_count_query_ms"),
            "js_root_identity_hash_ms": marker_timing.get("root_identity_hash_ms"),
        }
        poll = {
            "poll_index": len(polls) + 1,
            "elapsed_ms": elapsed_ms,
            "current_slug": current_slug,
            "heading_present": bool(marker.get("heading_present")),
            "section_present": bool(marker.get("section_present")),
            "side_view_present": bool(marker.get("side_view_present")),
            "stop_absent": bool(marker.get("stop_absent")),
            "stop_visible": bool(marker.get("stop_visible")),
            "bending_uls_card_present": bool(marker.get("bending_uls_card_present")),
            "loading_visible": bool(loading_visible),
            "faded_inert_count": faded_count,
            "visible_card_count": card_count,
            "visible_calc_check_count": calc_count,
            "visible_non_chart_text_hash": text_hash,
            "root_identity": {"id": root_id, "hash": root_hash},
            "marker_error": marker.get("marker_error"),
            "stable_reads": stable,
            "unmet_conditions": list(unmet),
            "visible_heading_list": list(marker.get("visible_heading_list") or [])[:12],
            "visible_bending_controls": list(marker.get("visible_bending_controls") or [])[:20],
            "visible_stop_texts": list(marker.get("visible_stop_texts") or [])[:20],
            "visible_chrome_stop_texts": list(marker.get("visible_chrome_stop_texts") or [])[:20],
            "faded_roots": list(marker.get("faded_roots") or [])[:12],
            "timing_breakdown_ms": timing_breakdown,
        }
        polls.append(poll)
        final_unmet = list(unmet)
        if stable >= 2:
            ready_elapsed_ms = elapsed_ms
            return {
                "checked": True,
                "ok": True,
                "classification": None,
                "first_poll_elapsed_ms": first_poll_ms,
                "ready_elapsed_ms": ready_elapsed_ms,
                "poll_count": len(polls),
                "final_decision": "ready",
                "unmet_conditions": [],
                "polls": polls[-40:],
            }
        time.sleep(0.5)
    return {
        "checked": True,
        "ok": False,
        "classification": BENDING_READY_GATE_TIMEOUT_CLASS,
        "first_poll_elapsed_ms": first_poll_ms,
        "ready_elapsed_ms": ready_elapsed_ms,
        "poll_count": len(polls),
        "final_decision": "timeout",
        "unmet_conditions": final_unmet,
        "polls": polls[-80:],
    }


def _page_cycle_wait_for_inputs_ready_gate(page, *, timeout_s: float = 45.0) -> dict[str, Any]:
    """Wait for the visible Inputs body to finish its first render before strict settle checks."""
    deadline = time.time() + timeout_s
    polls: list[dict[str, Any]] = []
    stable = 0
    last_sig: str | None = None
    first_poll_ms: int | None = None
    ready_elapsed_ms: int | None = None
    start = time.perf_counter()
    final_unmet: list[str] = []
    while time.time() < deadline:
        elapsed_ms = int(max(0.0, time.perf_counter() - start) * 1000)
        if first_poll_ms is None:
            first_poll_ms = elapsed_ms
        poll_eval_started = time.perf_counter()
        current_slug = _page_cycle_current_slug(page)
        try:
            snapshot = dict(
                page.evaluate(
                    r"""
                    () => {
                      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
                      const visible = (el) => {
                        if (!el) return false;
                        if (el.hasAttribute("inert") || el.closest("[inert]")) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none"
                          && style.visibility !== "hidden"
                          && Number(style.opacity || "1") > 0.02
                          && rect.width > 2
                          && rect.height > 2;
                      };
                      const count = (selector) => {
                        try { return Array.from(document.querySelectorAll(selector)).filter(visible).length; }
                        catch (_err) { return 0; }
                      };
                      const bodyText = clean(document.body ? document.body.innerText : "");
                      const matchedMarkers = [];
                      [
                        ["Start Your Design", /Start Your Design/i],
                        ["Batch design", /Batch design/i],
                        ["Active beam", /Active beam/i],
                        ["Design Guide", /Design Guide/i]
                      ].forEach(([label, pattern]) => {
                        if (pattern.test(bodyText)) matchedMarkers.push(label);
                      });
                      let hash = 0;
                      for (let i = 0; i < bodyText.length; i += 23) {
                        hash = ((hash << 5) - hash + bodyText.charCodeAt(i)) | 0;
                      }
                      const root = document.querySelector('main, [data-testid="stMain"], [data-testid="stAppViewContainer"], .stApp');
                      const rootText = root ? clean(root.innerText || root.textContent || "") : "";
                      let rootHash = 0;
                      for (let i = 0; i < rootText.length; i += 29) {
                        rootHash = ((rootHash << 5) - rootHash + rootText.charCodeAt(i)) | 0;
                      }
                      const loadingCount = count('[data-testid="stSpinner"], [data-testid="stSkeleton"], [aria-busy="true"], [role="progressbar"]');
                      const fadedCount = Array.from(document.querySelectorAll('main, [data-testid="stAppViewContainer"], [data-testid="stVerticalBlock"], [data-testid="stExpander"]'))
                        .filter((el) => visible(el) && (Number(window.getComputedStyle(el).opacity || "1") < 0.75 || window.getComputedStyle(el).pointerEvents === "none"))
                        .length;
                      return {
                        body_text_length: bodyText.length,
                        marker_present: matchedMarkers.length > 0,
                        matched_markers: matchedMarkers,
                        loading_visible: loadingCount > 0,
                        faded_inactive_overlay_count: fadedCount,
                        visible_card_count: count('[data-testid="stExpander"], [data-testid="design-guide-card"], .fast-guidance-item, .summary-card'),
                        visible_calc_box_count: count('[data-testid="stExpander"], [data-testid*="check"], [data-testid*="summary"]'),
                        input_widget_count: count('input, textarea, select'),
                        summary_table_exists: count('[data-testid*="summary"], .summary-card') > 0,
                        design_guide_container_exists: count('[data-testid="design-guide-card"], .fast-guidance-item') > 0,
                        page_root_id: root ? 1 : null,
                        page_root_hash: root ? String(rootHash >>> 0) : "",
                        visible_non_chart_text_hash: String(hash >>> 0)
                      };
                    }
                    """
                )
                or {}
            )
        except Exception as exc:
            snapshot = {"inputs_ready_probe_error": f"{type(exc).__name__}: {exc}"}
        poll_eval_ms = int(max(0.0, time.perf_counter() - poll_eval_started) * 1000)
        loading_visible = bool(snapshot.get("loading_visible"))
        content_marker = {
            "marker_present": bool(snapshot.get("marker_present")),
            "matched_markers": list(snapshot.get("matched_markers") or []),
            "main_text_length": int(snapshot.get("body_text_length") or 0),
        }
        body_text_length = int(snapshot.get("body_text_length") or 0)
        matched_markers = list(snapshot.get("matched_markers") or [])
        faded_count = int(snapshot.get("faded_inactive_overlay_count") or 0)
        card_count = int(snapshot.get("visible_card_count") or 0)
        calc_count = int(snapshot.get("visible_calc_box_count") or 0)
        input_count = int(snapshot.get("input_widget_count") or 0)
        root_id = snapshot.get("page_root_id")
        root_hash = snapshot.get("page_root_hash")
        text_hash = str(snapshot.get("visible_non_chart_text_hash") or "")
        unmet: list[str] = []
        if current_slug != "inputs":
            unmet.append("active_page_not_inputs")
        if body_text_length <= 0:
            unmet.append("inputs_body_text_empty")
        if not bool(content_marker.get("marker_present")):
            unmet.append("inputs_content_marker_missing")
        if snapshot.get("inputs_ready_probe_error"):
            unmet.append("inputs_ready_probe_error")
        if loading_visible:
            unmet.append("loading_visible")
        if input_count <= 0:
            unmet.append("inputs_widgets_missing")
        if not root_id or not root_hash:
            unmet.append("page_root_identity_missing")
        sig = json.dumps(
            {
                "slug": current_slug,
                "text_hash": text_hash,
                "card_count": card_count,
                "calc_count": calc_count,
                "input_count": input_count,
                "summary_table_exists": bool(snapshot.get("summary_table_exists")),
                "design_guide_container_exists": bool(snapshot.get("design_guide_container_exists")),
                "root_id": root_id,
                "root_hash": root_hash,
                "matched_markers": matched_markers,
            },
            sort_keys=True,
        )
        stable_candidate = not unmet
        if stable_candidate and sig == last_sig:
            stable += 1
        elif stable_candidate:
            stable = 1
            last_sig = sig
        else:
            stable = 0
            last_sig = sig
        poll = {
            "poll_index": len(polls) + 1,
            "elapsed_ms": elapsed_ms,
            "current_slug": current_slug,
            "body_text_length": body_text_length,
            "marker_present": bool(content_marker.get("marker_present")),
            "matched_markers": matched_markers,
            "loading_visible": bool(loading_visible),
            "faded_inert_count": faded_count,
            "visible_card_count": card_count,
            "visible_calc_check_count": calc_count,
            "input_widget_count": input_count,
            "summary_table_exists": bool(snapshot.get("summary_table_exists")),
            "design_guide_container_exists": bool(snapshot.get("design_guide_container_exists")),
            "visible_non_chart_text_hash": text_hash,
            "root_identity": {"id": root_id, "hash": root_hash},
            "timing_breakdown_ms": {"total_poll_ms": poll_eval_ms, "dom_snapshot_ms": poll_eval_ms},
            "stable_reads": stable,
            "unmet_conditions": list(unmet),
        }
        polls.append(poll)
        final_unmet = list(unmet)
        if stable >= 2:
            ready_elapsed_ms = elapsed_ms
            return {
                "checked": True,
                "ok": True,
                "classification": None,
                "first_poll_elapsed_ms": first_poll_ms,
                "ready_elapsed_ms": ready_elapsed_ms,
                "poll_count": len(polls),
                "final_decision": "ready",
                "unmet_conditions": [],
                "polls": polls[-40:],
            }
        time.sleep(0.5)
    return {
        "checked": True,
        "ok": False,
        "classification": INPUTS_READY_GATE_TIMEOUT_CLASS,
        "first_poll_elapsed_ms": first_poll_ms,
        "ready_elapsed_ms": ready_elapsed_ms,
        "poll_count": len(polls),
        "final_decision": "timeout",
        "unmet_conditions": final_unmet,
        "polls": polls[-80:],
    }


def _page_cycle_lightweight_settle_snapshot(page, *, slug: str) -> dict[str, Any]:
    script = r"""
    (slug) => {
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const visible = (el) => {
        if (!el) return false;
        if (el.hasAttribute("inert") || el.closest("[inert]")) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none"
          && style.visibility !== "hidden"
          && Number(style.opacity || "1") > 0.02
          && rect.width > 2
          && rect.height > 2;
      };
      const count = (selector) => {
        try { return Array.from(document.querySelectorAll(selector)).filter(visible).length; }
        catch (_err) { return 0; }
      };
      const bodyText = clean(document.body ? document.body.innerText : "");
      const markerSpecs = {
        inputs: [/Start Your Design/i, /Batch design/i, /Active beam/i],
        design: [/Design Guide/i, /Design Actions/i],
        bending: [/Bending/i, /ULS/i, /Stress-block|Side view|Section/i],
        shear: [/Shear/i, /Torsion|Sectional shear|Web-crushing/i],
        deflection: [/Deflection/i],
        crack: [/Crack/i, /Crack Diagram|Crack control|w'?max/i],
        creep: [/Creep/i],
        shrinkage: [/Shrinkage/i]
      };
      const specs = markerSpecs[String(slug || "").toLowerCase()] || [new RegExp(String(slug || ""), "i")];
      const matchedMarkers = specs.filter((pattern) => pattern.test(bodyText)).map((pattern) => String(pattern));
      let hash = 0;
      for (let i = 0; i < bodyText.length; i += 31) {
        hash = ((hash << 5) - hash + bodyText.charCodeAt(i)) | 0;
      }
      const root = document.querySelector('main, [data-testid="stMain"], [data-testid="stAppViewContainer"], .stApp');
      const rootText = root ? clean(root.innerText || root.textContent || "") : "";
      let rootHash = 0;
      for (let i = 0; i < rootText.length; i += 37) {
        rootHash = ((rootHash << 5) - rootHash + rootText.charCodeAt(i)) | 0;
      }
      const headings = Array.from(document.querySelectorAll('h1, h2, h3, [role="heading"]'))
        .filter(visible)
        .map((el) => clean(el.innerText || el.textContent).slice(0, 120))
        .filter(Boolean)
        .slice(0, 12);
      const activeLabels = Array.from(document.querySelectorAll('label, [role="tab"], button, a'))
        .filter(visible)
        .map((el) => clean(el.innerText || el.getAttribute("aria-label") || el.textContent).slice(0, 80))
        .filter(Boolean)
        .slice(0, 20);
      const loadingCount = count('[data-testid="stSpinner"], [data-testid="stSkeleton"], [aria-busy="true"], [role="progressbar"]');
      const fadedCount = Array.from(document.querySelectorAll('main, [data-testid="stAppViewContainer"], [data-testid="stVerticalBlock"], [data-testid="stExpander"]'))
        .filter((el) => visible(el) && (Number(window.getComputedStyle(el).opacity || "1") < 0.75 || window.getComputedStyle(el).pointerEvents === "none"))
        .length;
      const stalePageTokens = [];
      if (String(slug || "").toLowerCase() === "inputs") {
        [
          "Equilibrium derivation",
          "Stress-strain model",
          "Stress–strain model",
          "Rectangular stress block",
          "Neutral axis depth",
          "Curvature derivation",
          "Deflection derivation",
          "Shear derivation",
          "Web-crushing derivation"
        ].forEach((token) => {
          if (bodyText.toLowerCase().includes(String(token).toLowerCase())) stalePageTokens.push(token);
        });
      }
      return {
        body_text_length: bodyText.length,
        body_text_hash: String(hash >>> 0),
        visible_non_chart_text_hash: String(hash >>> 0),
        marker_present: matchedMarkers.length > 0,
        matched_markers: matchedMarkers,
        headings,
        active_labels: activeLabels,
        loading_visible: loadingCount > 0,
        loading_spinner_count: loadingCount,
        faded_inactive_overlay_count: fadedCount,
        stale_page_tokens: stalePageTokens,
        visible_card_count: count('[data-testid="stExpander"], [data-testid="design-guide-card"], .fast-guidance-item, .summary-card'),
        visible_calc_box_count: count('[data-testid="stExpander"], [data-testid*="check"], [data-testid*="summary"]'),
        visible_expander_count: count('[data-testid="stExpander"]'),
        input_widget_count: count('input, textarea, select'),
        summary_table_exists: count('[data-testid*="summary"], .summary-card') > 0,
        design_guide_container_exists: count('[data-testid="design-guide-card"], .fast-guidance-item') > 0,
        active_page_body_exists: Boolean(root && visible(root)),
        streamlit_block_count: count('[data-testid="stVerticalBlock"]'),
        dom_node_count: document.querySelectorAll('*').length,
        page_root_id: root ? 1 : null,
        page_root_hash: root ? String(rootHash >>> 0) : "",
        mutation_count_total: 0,
        chart_internal_mutation_count_total: 0,
        non_chart_mutation_count_total: 0,
        chart_mutation_total_records: 0,
        chart_mutation_visible_records: 0,
        chart_mutation_hidden_records: 0,
        chart_mutation_top: [],
        mutation_recent_batches: [],
        mutation_top_attribution: [],
        active_page: slug,
        url: String(window.location.href || "")
      };
    }
    """
    try:
        return dict(page.evaluate(script, slug) or {})
    except Exception as exc:
        return {"lightweight_snapshot_error": f"{type(exc).__name__}: {exc}"}


def _page_cycle_wait_for_settle(page, *, expected_slug: str, timeout_s: float = 45.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    stable = 0
    longest_stable = 0
    last_sig: str | None = None
    last: dict[str, Any] = {}
    polls = 0
    settle_reset_count = 0
    churn_iterations: list[dict[str, Any]] = []
    required_stable_polls = 1 if expected_slug == "shear" else 2
    content_last_sig: str | None = None
    content_stable = 0
    first_content_stable_elapsed_ms: int | None = None
    previous_mutation_total: int | None = None
    previous_chart_internal_total: int | None = None
    previous_non_chart_total: int | None = None
    filter_audit: dict[str, Any] = {
        "filter_activated": False,
        "content_stability_gate_satisfied": False,
        "first_content_stable_elapsed_ms": None,
        "total_mutations_observed": 0,
        "chart_internal_mutations_ignored_after_content_stable": 0,
        "non_chart_mutations_retained_after_content_stable": 0,
        "visible_chart_mutation_count": 0,
        "hidden_chart_mutation_count": 0,
        "ignored_mutation_selectors_or_classes": [],
        "activation_events": [],
        "reason_if_failed": None,
    }
    while time.time() < deadline:
        polls += 1
        elapsed_ms = int(max(0.0, timeout_s - max(0.0, deadline - time.time())) * 1000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=1500)
        except Exception:
            pass
        current_slug = _page_cycle_current_slug(page)
        churn_snapshot = _page_cycle_lightweight_settle_snapshot(page, slug=expected_slug)
        loading_visible = bool(churn_snapshot.get("loading_visible"))
        content_marker = {
            "marker_present": bool(churn_snapshot.get("marker_present")),
            "matched_markers": list(churn_snapshot.get("matched_markers") or []),
            "headings": list(churn_snapshot.get("headings") or []),
            "active_labels": list(churn_snapshot.get("active_labels") or []),
            "active_expected_nav": current_slug == expected_slug,
            "shear_heading_visible": expected_slug == "shear" and bool(churn_snapshot.get("marker_present")),
            "shear_summary_visible": expected_slug == "shear" and int(churn_snapshot.get("visible_calc_box_count") or 0) > 0,
            "shear_page_ready": expected_slug == "shear" and bool(churn_snapshot.get("marker_present")),
            "main_text_length": int(churn_snapshot.get("body_text_length") or 0),
            "main_text_sample": "",
        }
        body_text_length = int(content_marker.get("main_text_length") or 0)
        marker_present = bool(content_marker.get("marker_present"))
        if expected_slug == "shear":
            marker_present = bool(content_marker.get("shear_page_ready"))
        stale_page_tokens = list(churn_snapshot.get("stale_page_tokens") or [])
        stale_page_tokens_clear = expected_slug != "inputs" or not stale_page_tokens
        mutation_total = int(churn_snapshot.get("mutation_count_total") or 0)
        chart_internal_total = int(churn_snapshot.get("chart_internal_mutation_count_total") or 0)
        non_chart_total = int(churn_snapshot.get("non_chart_mutation_count_total") or 0)
        mutation_delta = 0 if previous_mutation_total is None else max(0, mutation_total - previous_mutation_total)
        chart_internal_delta = 0 if previous_chart_internal_total is None else max(0, chart_internal_total - previous_chart_internal_total)
        non_chart_delta = 0 if previous_non_chart_total is None else max(0, non_chart_total - previous_non_chart_total)
        filter_audit["total_mutations_observed"] = mutation_total
        filter_audit["visible_chart_mutation_count"] = int(churn_snapshot.get("chart_mutation_visible_records") or 0)
        filter_audit["hidden_chart_mutation_count"] = int(churn_snapshot.get("chart_mutation_hidden_records") or 0)
        content_sig = json.dumps(
            {
                "slug": current_slug,
                "visible_non_chart_text_hash": churn_snapshot.get("visible_non_chart_text_hash") or churn_snapshot.get("body_text_hash"),
                "visible_card_count": churn_snapshot.get("visible_card_count"),
                "visible_calc_box_count": churn_snapshot.get("visible_calc_box_count"),
                "input_widget_count": churn_snapshot.get("input_widget_count"),
                "summary_table_exists": churn_snapshot.get("summary_table_exists"),
                "active_page_body_exists": churn_snapshot.get("active_page_body_exists"),
                "page_root_id": churn_snapshot.get("page_root_id"),
                "page_root_hash": churn_snapshot.get("page_root_hash"),
                "marker_present": marker_present,
                "matched_markers": list(content_marker.get("matched_markers") or []),
                "active_labels": list(content_marker.get("active_labels") or []),
                "stale_page_tokens": stale_page_tokens,
            },
            sort_keys=True,
        )
        faded_count = int(churn_snapshot.get("faded_inactive_overlay_count") or 0)
        # Non-input pages can report a small benign faded/inactive count while their active
        # content is already visible. Keep Inputs strict, and let the later DOM-health
        # probe fail true global faded overlays for every page.
        faded_ok_for_content_gate = faded_count == 0 or expected_slug != "inputs"
        content_gate_ready = (
            current_slug == expected_slug
            and body_text_length > 0
            and marker_present
            and not loading_visible
            and faded_ok_for_content_gate
            and stale_page_tokens_clear
            and bool(churn_snapshot.get("active_page_body_exists"))
        )
        if content_gate_ready:
            if content_sig == content_last_sig:
                content_stable += 1
            else:
                content_last_sig = content_sig
                content_stable = 1
            if content_stable >= required_stable_polls and first_content_stable_elapsed_ms is None:
                first_content_stable_elapsed_ms = elapsed_ms
                filter_audit["content_stability_gate_satisfied"] = True
                filter_audit["first_content_stable_elapsed_ms"] = first_content_stable_elapsed_ms
        else:
            content_stable = 0
            content_last_sig = content_sig
        content_stability_gate_satisfied = content_stable >= required_stable_polls
        chart_filter_eligible = (
            content_stability_gate_satisfied
            and mutation_delta > 0
            and chart_internal_delta > 0
            and non_chart_delta == 0
        )
        if content_stability_gate_satisfied and non_chart_delta > 0:
            filter_audit["non_chart_mutations_retained_after_content_stable"] = int(
                filter_audit.get("non_chart_mutations_retained_after_content_stable") or 0
            ) + non_chart_delta
        if chart_filter_eligible:
            filter_audit["filter_activated"] = True
            filter_audit["chart_internal_mutations_ignored_after_content_stable"] = int(
                filter_audit.get("chart_internal_mutations_ignored_after_content_stable") or 0
            ) + chart_internal_delta
            for chart in list(churn_snapshot.get("chart_mutation_top") or [])[:5]:
                if isinstance(chart, dict):
                    label = str(chart.get("label") or chart.get("cls") or chart.get("testid") or "plotly_or_chart")[:160]
                    values = list(filter_audit.get("ignored_mutation_selectors_or_classes") or [])
                    if label not in values:
                        values.append(label)
                    filter_audit["ignored_mutation_selectors_or_classes"] = values[:20]
            filter_audit["activation_events"] = list(filter_audit.get("activation_events") or [])[-20:] + [
                {
                    "elapsed_ms": elapsed_ms,
                    "mutation_delta": mutation_delta,
                    "chart_internal_delta": chart_internal_delta,
                    "non_chart_delta": non_chart_delta,
                }
            ]
        sig = json.dumps(
            (
                {
                    "slug": current_slug,
                    "loading": loading_visible,
                    "shear_active_nav": bool(content_marker.get("active_expected_nav")),
                    "shear_heading": bool(content_marker.get("shear_heading_visible")),
                    "shear_summary": bool(content_marker.get("shear_summary_visible")),
                    "shear_ready": bool(content_marker.get("shear_page_ready")),
                }
                if expected_slug == "shear"
                else {
                    "slug": current_slug,
                    "loading": loading_visible,
                    "marker_present": marker_present,
                    "matched_markers": list(content_marker.get("matched_markers") or []),
                    "headings": list(content_marker.get("headings") or []),
                    "active_labels": list(content_marker.get("active_labels") or []),
                }
            ),
            sort_keys=True,
        )
        last = {
            "expected_slug": expected_slug,
            "current_slug": current_slug,
            "url": str(getattr(page, "url", "") or ""),
            "body_text_length": body_text_length,
            "loading_visible": loading_visible,
            "content_marker": content_marker,
            "polls": polls,
        }
        churn_iterations.append(
            {
                "iteration": polls,
                "elapsed_ms": elapsed_ms,
                "ready_conditions": {
                    "slug_matches": current_slug == expected_slug,
                    "body_has_text": body_text_length > 0,
                    "marker_present": marker_present,
                    "stale_page_tokens_clear": stale_page_tokens_clear,
                    "stale_page_tokens": stale_page_tokens,
                    "loading_visible": loading_visible,
                    "content_stability_gate_satisfied": content_stability_gate_satisfied,
                    "chart_filter_eligible": chart_filter_eligible,
                },
                "signature": sig,
                "content_signature": content_sig,
                "mutation_delta": {
                    "total": mutation_delta,
                    "chart_internal": chart_internal_delta,
                    "non_chart": non_chart_delta,
                },
                "snapshot": churn_snapshot,
            }
        )
        if (
            current_slug == expected_slug
            and body_text_length > 0
            and marker_present
            and not loading_visible
            and stale_page_tokens_clear
        ):
            if sig == last_sig or chart_filter_eligible:
                stable += 1
            else:
                if stable > 0:
                    settle_reset_count += 1
                last_sig = sig
                stable = 1
            longest_stable = max(longest_stable, stable)
            if stable >= required_stable_polls:
                last["settled"] = True
                last["page_cycle_churn_summary"] = _page_cycle_summarise_churn(
                    churn_iterations,
                    settle_reset_count=settle_reset_count,
                    longest_stable=longest_stable,
                )
                last["chart_internal_filter_audit"] = dict(filter_audit)
                return last
        else:
            if stable > 0:
                settle_reset_count += 1
            stable = 0
            last_sig = sig
        previous_mutation_total = mutation_total
        previous_chart_internal_total = chart_internal_total
        previous_non_chart_total = non_chart_total
        time.sleep(0.5)
    last["settled"] = False
    last["page_cycle_churn_summary"] = _page_cycle_summarise_churn(
        churn_iterations,
        settle_reset_count=settle_reset_count,
        longest_stable=longest_stable,
    )
    last_snapshot = {}
    try:
        last_snapshot = dict((last.get("page_cycle_churn_summary") or {}).get("last_snapshot") or {})
    except Exception:
        last_snapshot = {}
    final_dom_health: dict[str, Any] = {}
    final_dom_health_clean_inputs = last.get("expected_slug") != "inputs"
    if last.get("expected_slug") == "inputs":
        try:
            final_dom_health = _page_cycle_dom_health(page, slug="inputs")
        except Exception as exc:
            final_dom_health = {"dom_probe_error": f"{type(exc).__name__}: {exc}"}
        final_input_controls = dict(final_dom_health.get("inputControls") or {})
        final_missing_controls = sorted(key for key, present in final_input_controls.items() if not present)
        final_dom_health_clean_inputs = (
            not final_dom_health.get("dom_probe_error")
            and not list(final_dom_health.get("staleTokens") or [])
            and not final_missing_controls
        )
        filter_audit["final_dom_health_reconciliation"] = {
            "checked": True,
            "stale_tokens": list(final_dom_health.get("staleTokens") or []),
            "missing_input_controls": final_missing_controls,
            "dom_probe_error": final_dom_health.get("dom_probe_error"),
            "generic_button_visible": bool(final_dom_health.get("genericButtonVisible")),
            "design_guide_card_count": int(final_dom_health.get("designGuideCardCount") or 0),
        }
    final_essential_content_ready = (
        last.get("current_slug") == last.get("expected_slug")
        and int(last.get("body_text_length") or 0) > 0
        and marker_present
        and not bool(last.get("loading_visible"))
        and bool(last_snapshot.get("active_page_body_exists"))
        and (last.get("expected_slug") != "inputs" or final_dom_health_clean_inputs)
        and int(last_snapshot.get("visible_card_count") or 0) > 0
        and int(last_snapshot.get("visible_calc_box_count") or 0) > 0
    )
    if final_essential_content_ready:
        last["settled"] = True
        last["settled_via_final_essential_content_snapshot"] = True
        filter_audit["content_stability_gate_satisfied"] = bool(filter_audit.get("content_stability_gate_satisfied"))
        filter_audit["reason_if_failed"] = None
        filter_audit["final_essential_content_ready"] = True
        filter_audit["final_essential_content_ready_note"] = (
            "Final visible page markers, cards, and calc/check boxes were present; "
            "visibility-aware DOM health checks still run after this settle decision."
        )
        if final_dom_health:
            filter_audit["final_dom_health_allowed_lightweight_stale_token_mismatch"] = bool(
                last.get("expected_slug") == "inputs"
                and list(last_snapshot.get("stale_page_tokens") or [])
                and not list(final_dom_health.get("staleTokens") or [])
            )
        last["chart_internal_filter_audit"] = dict(filter_audit)
        return last
    if last.get("current_slug") != last.get("expected_slug"):
        filter_audit["reason_if_failed"] = "slug_not_expected"
    elif last.get("loading_visible"):
        filter_audit["reason_if_failed"] = "loading_visible"
    elif not int(last.get("body_text_length") or 0):
        filter_audit["reason_if_failed"] = "body_text_empty"
    elif not marker_present:
        filter_audit["reason_if_failed"] = "content_marker_missing"
    elif last.get("expected_slug") == "inputs" and list(last_snapshot.get("stale_page_tokens") or []):
        filter_audit["reason_if_failed"] = "stale_page_content_visible_on_inputs"
        filter_audit["stale_page_tokens"] = list(last_snapshot.get("stale_page_tokens") or [])
    elif not filter_audit.get("content_stability_gate_satisfied"):
        filter_audit["reason_if_failed"] = "content_stability_gate_not_satisfied"
    elif int(filter_audit.get("non_chart_mutations_retained_after_content_stable") or 0) > 0:
        filter_audit["reason_if_failed"] = "non_chart_mutations_retained"
    else:
        filter_audit["reason_if_failed"] = "content_signature_not_stable"
    last["chart_internal_filter_audit"] = dict(filter_audit)
    return last


def _page_cycle_dom_health(page, *, slug: str) -> dict[str, Any]:
    script = r"""
    (slug) => {
      const visible = (el) => {
        if (!el) return false;
        const closedDetails = el.closest('details:not([open])');
        if (closedDetails && closedDetails !== el && !el.closest('summary')) return false;
        if (el.hasAttribute('inert') || el.closest('[inert]')) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        if (style.display === "none" || style.visibility === "hidden") return false;
        if (Number(style.opacity || "1") <= 0.02) return false;
        return rect.width >= 30 && rect.height >= 12;
      };
      const cleanText = (value) => String(value || "")
        .replace(/[›⌄⌃⌵▾▸◂▲▼▶◀^]/g, " ")
        .replace(/\b(expand_more|chevron_right|keyboard_arrow_down|keyboard_arrow_right)\b/ig, " ")
        .replace(/\s+/g, " ")
        .trim();
      const nodesFor = (selector) => {
        try { return Array.from(document.querySelectorAll(selector)); }
        catch (_err) { return []; }
      };
      const seen = new Set();
      const candidates = [];
      [
        '[data-testid="stExpander"]',
        '[data-testid="stExpanderDetails"]',
        '[data-testid="design-guide-card"]',
        '.fast-guidance-item',
        '[data-testid*="summary" i]',
        '[data-testid*="check" i]',
        '[data-testid*="card" i]',
        '[class*="calc" i]',
        '[class*="card" i]',
        '[class*="derivation" i]'
      ].forEach((selector) => {
        nodesFor(selector).forEach((el) => {
          if (!seen.has(el)) {
            seen.add(el);
            candidates.push({selector, el});
          }
        });
      });
      const emptyCards = [];
      const emptyCalcCheckShells = [];
      const fadedElements = [];
      const blankPlaceholderBars = [];
      candidates.forEach(({selector, el}, index) => {
        if (!visible(el)) return;
        const rect = el.getBoundingClientRect();
        if (rect.width < 80 || rect.height < 20) return;
        const text = cleanText(el.innerText);
        const hasVisibleRichContent = Array.from(el.querySelectorAll('input, textarea, select, button, canvas, svg, img, [role="img"]')).some((child) => visible(child));
        const hasIntentionalLoading = /loading|preparing|running|please wait/i.test(text);
        const style = window.getComputedStyle(el);
        const opacity = Number(style.opacity || "1");
        if (text.length < 3 && !hasVisibleRichContent && !hasIntentionalLoading) {
          emptyCards.push({
            selector,
            index,
            text,
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
            className: String(el.className || "").slice(0, 160),
            testid: el.getAttribute("data-testid") || null
          });
        }
        if (opacity > 0.02 && opacity < 0.65 && rect.width > 120 && rect.height > 24) {
          fadedElements.push({
            selector,
            index,
            opacity,
            text: text.slice(0, 160),
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
            className: String(el.className || "").slice(0, 160),
            testid: el.getAttribute("data-testid") || null
          });
        }
      });
      const meaningfulText = (value) => cleanText(value)
        .replace(/\b(i|info|details|open|close)\b/ig, " ")
        .replace(/\s+/g, " ")
        .trim();
      const shellCandidates = [];
      [
        'div[data-testid="stExpander"] details',
        '.summary-check-card details',
        '.step-card',
        '[class*="calcbox" i]',
        '[class*="calc-box" i]',
        '[class*="check-card" i]',
        '[class*="summary-check-card" i]'
      ].forEach((selector) => {
        nodesFor(selector).forEach((el) => shellCandidates.push({selector, el}));
      });
      shellCandidates.forEach(({selector, el}, index) => {
        if (!visible(el)) return;
        const rect = el.getBoundingClientRect();
        if (rect.width < 160 || rect.height < 22 || rect.height > 320) return;
        const summary = el.matches('details') ? el.querySelector('summary') : (el.querySelector('summary') || el);
        if (!summary || !visible(summary)) return;
        const summaryRaw = String(summary.innerText || summary.textContent || "");
        const summaryText = meaningfulText(summaryRaw);
        const titleText = meaningfulText(Array.from(summary.querySelectorAll('strong, b, h1, h2, h3, h4, .summary-check-title, [data-testid*="title" i]'))
          .map((node) => node.innerText || node.textContent || "")
          .join(" "));
        const resultText = meaningfulText(Array.from(summary.querySelectorAll('.summary-metric-value, .summary-status-pill, [class*="result" i], [data-testid*="status" i]'))
          .map((node) => node.innerText || node.textContent || "")
          .join(" "));
        const bodyText = el.matches('details') && !el.open
          ? ""
          : meaningfulText(Array.from(el.children)
              .filter((child) => child !== summary)
              .map((child) => child.innerText || child.textContent || "")
              .join(" "));
        const chevronVisible = Array.from(summary.querySelectorAll('svg, .summary-card-chevron, [class*="chevron" i], [class*="expand" i]')).some(visible)
          || /keyboard_arrow|expand_more|chevron|⌄|›|▸|▾|^>$/i.test(summaryRaw);
        const hasIntentionalLoading = /loading|preparing|running|please wait/i.test(summaryText + " " + bodyText);
        const hasMeaningfulTitle = titleText.length >= 3
          || /\b(check|bending|shear|deflection|crack|creep|shrinkage|stress|strain|capacity|summary|section)\b/i.test(summaryText);
        const hasResultOrBody = resultText.length >= 2
          || /\b(result|pass|fail|capacity|utilisation|applied|calculated|limit|not supplied|input required|info)\b/i.test(summaryText)
          || bodyText.length >= 3;
        if (chevronVisible && !hasIntentionalLoading && !hasMeaningfulTitle && !hasResultOrBody) {
          const style = window.getComputedStyle(el);
          emptyCalcCheckShells.push({
            selector,
            index,
            text: summaryText,
            titleText,
            resultText,
            bodyText: bodyText.slice(0, 240),
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
            className: String(el.className || "").slice(0, 160),
            testid: el.getAttribute("data-testid") || null,
            backgroundColor: String(style.backgroundColor || ""),
            borderColor: String(style.borderColor || "")
          });
        }
      });
      Array.from(document.querySelectorAll('main div, main section, [data-testid="stAppViewContainer"] div'))
        .forEach((el, index) => {
          if (!visible(el)) return;
          const rect = el.getBoundingClientRect();
          if (rect.width < 180 || rect.height < 28 || rect.height > 260) return;
          const text = cleanText(el.innerText);
          if (text.length > 0) return;
          const style = window.getComputedStyle(el);
          const bg = String(style.backgroundColor || "");
          const radius = String(style.borderRadius || "0");
          const radiusNumber = Number(String(radius).match(/[0-9.]+/)?.[0] || "0");
          const greyish = /rgba?\((23[0-9]|24[0-9]|25[0-5]),\s*(23[0-9]|24[0-9]|25[0-5]),\s*(23[0-9]|24[0-9]|25[0-5])/.test(bg)
            || /rgba?\((1[8-9][0-9]|2[0-4][0-9]),\s*(1[8-9][0-9]|2[0-4][0-9]),\s*(1[8-9][0-9]|2[0-4][0-9])/.test(bg);
          const visibleBlankShell = greyish || radiusNumber >= 6;
          if (!visibleBlankShell) return;
          const visibleControls = Array.from(el.querySelectorAll('input, textarea, select, button, canvas, svg, img, [role="img"]')).some((child) => visible(child));
          if (visibleControls) return;
          blankPlaceholderBars.push({
            selector: "blank-placeholder-bar",
            index,
            text,
            backgroundColor: bg,
            borderRadius: radius,
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
            className: String(el.className || "").slice(0, 160),
            testid: el.getAttribute("data-testid") || null
          });
        });
      const visibleButtons = Array.from(document.querySelectorAll('button')).filter(visible);
      const genericButtons = visibleButtons
        .filter((button) => /Run one-click auto design/i.test(cleanText(button.innerText)))
        .map((button) => cleanText(button.innerText));
      const designGuideCards = Array.from(document.querySelectorAll('[data-testid="design-guide-card"], .fast-guidance-item'))
        .filter(visible)
        .map((el) => cleanText(el.innerText));
      const bodyText = cleanText(document.body ? document.body.innerText : "");
      const headingVisible = /(^|\s)Design Guide(\s|$)/i.test(bodyText);
      const appContainers = Array.from(document.querySelectorAll('.stApp, [data-testid="stAppViewContainer"], main, section.main'))
        .filter(visible)
        .map((el) => {
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          return {
            opacity: Number(style.opacity || "1"),
            pointerEvents: style.pointerEvents,
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
            text: cleanText(el.innerText).slice(0, 120)
          };
        });
      const staleTokens = [];
      if (slug === "inputs") {
        [
          "Equilibrium derivation",
          "Stress-strain model",
          "Stress–strain model",
          "Rectangular stress block",
          "Neutral axis depth",
          "Curvature derivation",
          "Deflection derivation",
          "Shear derivation",
          "Web-crushing derivation"
        ].forEach((token) => {
          if (bodyText.toLowerCase().includes(token.toLowerCase())) staleTokens.push(token);
        });
      }
      const inputControls = {};
      if (slug === "inputs") {
        [
          ["batch_design", /Batch design/i],
          ["active_beam", /Active beam/i],
          ["add_button", /\bAdd\b/i],
          ["duplicate_button", /\bDuplicate\b/i],
          ["reset_button", /\bReset\b/i],
          ["show_manager_button", /Show Manager/i]
        ].forEach(([key, pattern]) => {
          inputControls[key] = pattern.test(bodyText);
        });
      }
      return {
        slug,
        bodyTextExcerpt: bodyText.slice(0, 4000),
        bodyTextLength: bodyText.length,
        emptyCards,
        emptyCalcCheckShells,
        blankPlaceholderBars,
        fadedElements,
        genericButtonVisible: genericButtons.length > 0,
        genericButtons,
        designGuideHeadingVisible: headingVisible,
        designGuideCardCount: designGuideCards.filter((text) => text.length >= 8).length,
        designGuideCardText: designGuideCards.slice(0, 3),
        appContainers,
        staleTokens,
        inputControls
      };
    }
    """
    try:
        return dict(page.evaluate(script, slug) or {})
    except Exception as exc:
        return {"slug": slug, "dom_probe_error": f"{type(exc).__name__}: {exc}"}


def _page_cycle_html_excerpt(page, failing_selectors: list[dict[str, Any]]) -> str:
    try:
        html = str(page.content() or "")
    except Exception as exc:
        return f"Could not capture page HTML: {type(exc).__name__}: {exc}"
    if not failing_selectors:
        return html[:12000]
    excerpts: list[str] = []
    for item in failing_selectors[:10]:
        token = str(item.get("testid") or item.get("className") or item.get("selector") or "").strip()
        token = token.split()[0] if token else ""
        if token and token in html:
            index = html.find(token)
            excerpts.append(html[max(0, index - 1000) : index + 3000])
    return "\n\n<!-- next excerpt -->\n\n".join(excerpts) if excerpts else html[:12000]


def _page_cycle_active_nav_state(page) -> dict[str, Any]:
    script = r"""
    () => {
      const visible = (el) => {
        if (!el) return false;
        if (el.hasAttribute('inert') || el.closest('[inert]')) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4;
      };
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const navItems = Array.from(document.querySelectorAll(
        'div[role="radiogroup"] label, [role="tab"], a[href*="page="], button, label'
      ))
        .filter(visible)
        .map((el) => {
          const input = el.querySelector('input') || (el.control || null);
          const rect = el.getBoundingClientRect();
          return {
            tag: el.tagName.toLowerCase(),
            text: clean(el.innerText || el.getAttribute("aria-label") || el.textContent).slice(0, 120),
            href: el.getAttribute("href") || null,
            ariaSelected: el.getAttribute("aria-selected"),
            ariaChecked: el.getAttribute("aria-checked"),
            checked: input ? Boolean(input.checked) : null,
            disabled: Boolean(el.disabled || el.getAttribute("aria-disabled") === "true"),
            className: String(el.className || "").slice(0, 160),
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
          };
        })
        .filter((item) => item.text || item.href);
      return {
        url: String(window.location.href || ""),
        title: String(document.title || ""),
        navItems
      };
    }
    """
    try:
        return dict(page.evaluate(script) or {})
    except Exception as exc:
        return {"nav_probe_error": f"{type(exc).__name__}: {exc}"}


def _page_cycle_visible_roots_and_loading(page) -> dict[str, Any]:
    script = r"""
    () => {
      const visible = (el) => {
        if (!el) return false;
        if (el.hasAttribute('inert') || el.closest('[inert]')) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4;
      };
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const describe = (selector) => Array.from(document.querySelectorAll(selector))
        .filter(visible)
        .slice(0, 20)
        .map((el) => {
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          return {
            selector,
            tag: el.tagName.toLowerCase(),
            testid: el.getAttribute("data-testid") || null,
            className: String(el.className || "").slice(0, 160),
            opacity: Number(style.opacity || "1"),
            pointerEvents: style.pointerEvents,
            text: clean(el.innerText || el.textContent).slice(0, 220),
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
          };
        });
      const rootSelectors = [
        '.stApp',
        '[data-testid="stAppViewContainer"]',
        '[data-testid="stMain"]',
        'main',
        'section.main',
        '[data-testid="stVerticalBlock"]',
        '[data-testid="stExpander"]',
        '[data-testid="stExpanderDetails"]',
        '[data-testid="design-guide-card"]',
        '.fast-guidance-item'
      ];
      const loadingSelectors = [
        '[data-testid="stSpinner"]',
        '[data-testid="stSkeleton"]',
        '[aria-busy="true"]',
        '[role="progressbar"]'
      ];
      return {
        visiblePageRoots: rootSelectors.flatMap(describe),
        loadingOverlays: loadingSelectors.flatMap(describe)
      };
    }
    """
    try:
        return dict(page.evaluate(script) or {})
    except Exception as exc:
        return {"root_probe_error": f"{type(exc).__name__}: {exc}"}


def _page_cycle_failed_page_capture(
    page,
    *,
    artifact_path: Path,
    label: str,
    slug: str,
    page_index: int,
    settle_meta: dict[str, Any],
    dom: dict[str, Any],
    page_failures: list[str],
    console_messages: list[str] | None,
) -> dict[str, Any]:
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{label}_{page_index}_{slug}_failed_page").strip("_")
    capture: dict[str, Any] = {
        "page": slug,
        "page_index": page_index,
        "failures": list(page_failures),
        "current_slug": _page_cycle_current_slug(page),
        "current_url": str(getattr(page, "url", "") or ""),
        "pending_settle_subconditions": {
            "expected_slug": settle_meta.get("expected_slug"),
            "current_slug": settle_meta.get("current_slug"),
            "slug_matches_expected": settle_meta.get("current_slug") == settle_meta.get("expected_slug"),
            "body_has_text": bool(int(settle_meta.get("body_text_length") or 0) > 0),
            "loading_visible": bool(settle_meta.get("loading_visible")),
            "settled": bool(settle_meta.get("settled")),
            "polls": settle_meta.get("polls"),
            "elapsed_ms": settle_meta.get("elapsed_ms"),
        },
        "empty_or_placeholder_cards": {
            "emptyCards": list(dom.get("emptyCards") or []),
            "emptyCalcCheckShells": list(dom.get("emptyCalcCheckShells") or []),
            "blankPlaceholderBars": list(dom.get("blankPlaceholderBars") or []),
            "fadedElements": list(dom.get("fadedElements") or []),
        },
        "artifact_errors": [],
    }
    try:
        viewport_path = artifact_path / f"{safe_label}_viewport.png"
        page.screenshot(path=str(viewport_path), full_page=False, timeout=10_000)
        capture["viewport_screenshot"] = str(viewport_path)
    except Exception as exc:
        capture["artifact_errors"].append(f"viewport_screenshot:{type(exc).__name__}:{exc}")
    try:
        full_path = artifact_path / f"{safe_label}_full_page.png"
        page.screenshot(path=str(full_path), full_page=True, timeout=10_000)
        capture["full_page_screenshot"] = str(full_path)
    except Exception as exc:
        capture["artifact_errors"].append(f"full_page_screenshot:{type(exc).__name__}:{exc}")
    capture["dom_excerpt_path"] = _page_cycle_write_text(
        artifact_path / f"{safe_label}_dom_excerpt.html",
        _page_cycle_html_excerpt(
            page,
            list(dom.get("emptyCards") or [])
            + list(dom.get("emptyCalcCheckShells") or [])
            + list(dom.get("blankPlaceholderBars") or []),
        ),
    )
    capture["active_nav_state_path"] = _page_cycle_write_json(
        artifact_path / f"{safe_label}_active_nav_state.json",
        _page_cycle_active_nav_state(page),
    )
    capture["visible_page_roots_path"] = _page_cycle_write_json(
        artifact_path / f"{safe_label}_visible_page_roots.json",
        _page_cycle_visible_roots_and_loading(page),
    )
    capture["console_errors_path"] = _page_cycle_write_json(
        artifact_path / f"{safe_label}_console_errors.json",
        list(console_messages or []),
    )
    heartbeat_path = artifact_path / "lifecycle_heartbeat.json"
    if heartbeat_path.exists():
        try:
            heartbeat_snapshot = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        except Exception as exc:
            heartbeat_snapshot = {"heartbeat_read_error": f"{type(exc).__name__}: {exc}"}
    else:
        heartbeat_snapshot = {"heartbeat_missing": True}
    capture["lifecycle_heartbeat_snapshot_path"] = _page_cycle_write_json(
        artifact_path / f"{safe_label}_lifecycle_heartbeat_snapshot.json",
        heartbeat_snapshot,
    )
    capture["pending_settle_subconditions_path"] = _page_cycle_write_json(
        artifact_path / f"{safe_label}_pending_settle_subconditions.json",
        capture["pending_settle_subconditions"],
    )
    return capture


def _page_cycle_page_closed_state(page) -> bool:
    try:
        return bool(page.is_closed())
    except Exception:
        return True


def _page_cycle_context_closed_state(page) -> bool:
    try:
        return bool(page.context is None or len(page.context.pages) < 1)
    except Exception:
        return True


def _page_cycle_browser_closed_state(page) -> bool:
    try:
        browser = page.context.browser
        return not bool(browser and browser.is_connected())
    except Exception:
        return True


def _page_cycle_streamlit_status_detail(page) -> dict[str, Any]:
    script = r"""
    () => {
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const visible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style && style.display !== "none" && style.visibility !== "hidden" &&
          Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
      };
      const connection = document.querySelector("[data-test-connection-state]");
      if (connection) {
        const state = clean(connection.getAttribute("data-test-connection-state")).toUpperCase();
        if (state && state !== "CONNECTED") {
          return {status: state, source: "data-test-connection-state", text: state};
        }
      }
      const statusNodes = Array.from(document.querySelectorAll(
        '[data-testid="stStatusWidget"], [data-testid="stSpinner"], [role="status"], [aria-live]'
      )).filter(visible);
      const statusText = clean(statusNodes.map((el) => el.innerText || el.textContent || "").join(" "));
      const upperStatus = statusText.toUpperCase();
      for (const token of ["CONNECTING", "CONNECTION ERROR", "STREAMLIT SERVER IS NOT RESPONDING", "RERUN", "RUNNING", "STOP"]) {
        if (upperStatus.includes(token)) {
          return {status: token, source: "streamlit_status_widget", text: statusText.slice(0, 240)};
        }
      }
      const bodyText = clean(document.body ? document.body.innerText : "");
      const upperBody = bodyText.toUpperCase();
      for (const token of ["CONNECTION ERROR", "STREAMLIT SERVER IS NOT RESPONDING"]) {
        if (upperBody.includes(token)) {
          return {status: token, source: "body_connection_error_text", text: bodyText.slice(0, 240)};
        }
      }
      return {status: "", source: "", text: ""};
    }
    """
    try:
        return dict(page.evaluate(script) or {})
    except Exception as exc:
        return {"status": "unreadable", "source": f"{type(exc).__name__}", "text": str(exc)[:240]}


def _page_cycle_streamlit_status(page) -> str:
    detail = _page_cycle_streamlit_status_detail(page)
    return str(detail.get("status") or "")


def _page_cycle_design_prerender_snapshot(page) -> dict[str, Any]:
    state: dict[str, Any] = {}
    error = None
    try:
        try:
            state = _load_browser_state(page, timeout_s=0.6)
        except TypeError:
            state = _load_browser_state(page)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        state = {}
    probe_phase = str(state.get("probe_phase") or state.get("browser_probe_phase") or "")
    pre_page_render_lightweight = bool(state.get("pre_page_render_lightweight"))
    results_version = state.get("results_version")
    streamlit_status_detail = _page_cycle_streamlit_status_detail(page)
    streamlit_status = str(streamlit_status_detail.get("status") or "")
    current_slug = _page_cycle_current_slug(page)
    content_marker = _page_cycle_content_marker(page, "design") if current_slug == "design" else {}
    loading_visible = _page_cycle_loading_visible(page)
    visible_counts = _page_cycle_visible_counts(page, slug="design") if current_slug == "design" else {}
    dom_rendered_design_content = (
        current_slug == "design"
        and bool(content_marker.get("marker_present"))
        and not loading_visible
        and int(visible_counts.get("visibleCalcCheckCount") or 0) > 0
        and int(visible_counts.get("empty_card_count") or 0) == 0
        and int(visible_counts.get("empty_calc_check_shell_count") or 0) == 0
        and int(visible_counts.get("loadingCount") or 0) == 0
        and int(visible_counts.get("fadedInertCount") or 0) == 0
    )
    rendered_design_content = (
        current_slug == "design"
        and (
            (probe_phase == "post_page_render" and not pre_page_render_lightweight)
            or dom_rendered_design_content
        )
        and bool(content_marker.get("marker_present"))
        and not loading_visible
    )
    results_version_zero_blocking = results_version == 0 and not rendered_design_content
    runtime_status_blocking = streamlit_status in {
        "CONNECTING",
        "DISCONNECTED",
        "ERROR",
        "CONNECTION ERROR",
        "STREAMLIT SERVER IS NOT RESPONDING",
    } or (streamlit_status == "RERUN" and not rendered_design_content)
    transitional = (
        current_slug == "design"
        and (
            ((probe_phase == "pre_page_render" or pre_page_render_lightweight) and not rendered_design_content)
            or results_version_zero_blocking
            or runtime_status_blocking
        )
    )
    return {
        "current_slug": current_slug,
        "transitional_design_prerender_detected": bool(transitional),
        "probe_phase": probe_phase,
        "pre_page_render_lightweight": bool(pre_page_render_lightweight),
        "results_version": results_version,
        "streamlit_status": streamlit_status,
        "streamlit_status_source": streamlit_status_detail.get("source"),
        "streamlit_status_text_excerpt": streamlit_status_detail.get("text"),
        "results_version_zero_blocking": bool(results_version_zero_blocking),
        "runtime_status_blocking": bool(runtime_status_blocking),
        "rendered_design_content": bool(rendered_design_content),
        "dom_rendered_design_content": bool(dom_rendered_design_content),
        "stale_pre_page_browser_state_ignored_after_dom_render": bool(
            dom_rendered_design_content
            and (probe_phase == "pre_page_render" or pre_page_render_lightweight)
        ),
        "loading_visible": bool(loading_visible),
        "content_marker": content_marker,
        "visible_counts": visible_counts,
        "browser_state_error": error,
        "url": str(getattr(page, "url", "") or ""),
    }


def _page_cycle_wait_for_design_prerender_exit(page, *, timeout_s: float = 45.0) -> dict[str, Any]:
    started = time.perf_counter()
    deadline = started + max(3.0, float(timeout_s))
    polls = 0
    stable_rendered = 0
    observations: list[dict[str, Any]] = []
    last: dict[str, Any] = {}
    while time.perf_counter() < deadline:
        polls += 1
        snapshot = _page_cycle_design_prerender_snapshot(page)
        snapshot["poll"] = polls
        snapshot["elapsed_ms"] = int(max(0.0, time.perf_counter() - started) * 1000)
        observations.append(snapshot)
        last = snapshot
        if not bool(snapshot.get("transitional_design_prerender_detected")):
            stable_rendered += 1
            if bool(snapshot.get("rendered_design_content")) or stable_rendered >= 2:
                return {
                    "ok": True,
                    "classification": None,
                    "poll_count": polls,
                    "elapsed_ms": int(max(0.0, time.perf_counter() - started) * 1000),
                    "transitional_design_prerender_detected": True,
                    "rendered_poll_count": stable_rendered,
                    "pre_render_exit_reason": (
                        "rendered_design_content"
                        if bool(snapshot.get("rendered_design_content"))
                        else "stable_non_transitional_polls"
                    ),
                    "first_poll": observations[0] if observations else None,
                    "last_poll": last,
                    "observations_tail": observations[-20:],
                    "final_ghost_empty_checks_ran_after_render_completion": True,
                }
        else:
            stable_rendered = 0
        time.sleep(0.5)
    return {
        "ok": False,
        "classification": DESIGN_PAGE_PRE_RENDER_TIMEOUT_CLASS,
        "poll_count": polls,
        "elapsed_ms": int(max(0.0, time.perf_counter() - started) * 1000),
        "transitional_design_prerender_detected": bool(
            observations and observations[0].get("transitional_design_prerender_detected")
        ),
        "first_poll": observations[0] if observations else None,
        "last_poll": last,
        "observations_tail": observations[-20:],
        "final_ghost_empty_checks_ran_after_render_completion": False,
    }


def _page_cycle_visible_counts(page, *, slug: str) -> dict[str, Any]:
    script = """
    ({slug}) => {
      const visible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style && style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity || '1') > 0.02 && rect.width > 1 && rect.height > 1;
      };
      const count = (selector) => Array.from(document.querySelectorAll(selector)).filter(visible).length;
      const textIncludes = (needle) => Array.from(document.querySelectorAll('body *'))
        .filter(visible)
        .some((el) => String(el.innerText || el.textContent || '').includes(needle));
      return {
        visibleCardCount: count('[data-testid="stExpander"], [data-testid="design-guide-card"], .fast-guidance-item, .summary-card'),
        visibleCalcCheckCount: count('[data-testid="stExpander"], [data-testid*="check"], [data-testid*="summary"]'),
        designGuideCardCount: count('[data-testid="design-guide-card"], .fast-guidance-item'),
        summaryCardCount: count('[data-testid*="summary"], .summary-card'),
        loadingCount: count('[data-testid="stSpinner"], [data-testid="stSkeleton"], [aria-busy="true"], [role="progressbar"]'),
        fadedInertCount: Array.from(document.querySelectorAll('main, [data-testid="stAppViewContainer"], [data-testid="stVerticalBlock"], [data-testid="stExpander"]'))
          .filter((el) => visible(el) && (Number(window.getComputedStyle(el).opacity || '1') < 0.75 || window.getComputedStyle(el).pointerEvents === 'none'))
          .length,
        inputsMarkerVisible: textIncludes('Start Your Design') || textIncludes('Active beam') || textIncludes('Batch design'),
        designMarkerVisible: textIncludes('Design Guide'),
        bendingMarkerVisible: textIncludes('Bending') && (textIncludes('ULS') || textIncludes('Stress-block')),
        shearMarkerVisible: textIncludes('Shear') && (textIncludes('Torsion') || textIncludes('Sectional shear')),
        deflectionMarkerVisible: textIncludes('Deflection'),
        crackMarkerVisible: textIncludes('Crack'),
        creepMarkerVisible: textIncludes('Creep'),
        shrinkageMarkerVisible: textIncludes('Shrinkage'),
      };
    }
    """
    try:
        counts = dict(page.evaluate(script, slug) or {})
    except Exception as exc:
        counts = {"count_probe_error": f"{type(exc).__name__}: {exc}"}
    try:
        dom = _page_cycle_dom_health(page, slug=slug)
        counts.update(
            {
                "empty_card_count": len(list(dom.get("emptyCards") or [])),
                "empty_calc_check_shell_count": len(list(dom.get("emptyCalcCheckShells") or [])),
                "blank_placeholder_bar_count": len(list(dom.get("blankPlaceholderBars") or [])),
                "faded_element_count": len(list(dom.get("fadedElements") or [])),
                "stale_token_count": len(list(dom.get("staleTokens") or [])),
                "dom_probe_error": dom.get("dom_probe_error"),
            }
        )
    except Exception as exc:
        counts["dom_health_error"] = f"{type(exc).__name__}: {exc}"
    return counts


def _page_cycle_crop_first_visible(page, selectors: list[str], path: Path) -> tuple[str | None, str | None]:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=750)
            locator.screenshot(path=str(path), timeout=3_000)
            return str(path), None
        except Exception:
            continue
    return None, selectors[0] if selectors else "unknown"


def _page_cycle_visited_pages_look_healthy(visited: list[dict[str, Any]], failures: list[str]) -> bool:
    if not visited:
        return False
    real_failure_tokens = (
        "page_did_not_settle:",
        "empty_calc_or_card_visible:",
        EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS,
        "empty_placeholder_card_visible:",
        "faded_or_disabled_ui_visible:",
        "stale_page_content_visible_on_inputs:",
        "inputs_controls_missing_after_return:",
        "generic_cta_without_design_guide_card",
        "dom_probe_error:",
        BENDING_READY_GATE_TIMEOUT_CLASS,
        INPUTS_READY_GATE_TIMEOUT_CLASS,
    )
    if any(any(str(item).startswith(token) for token in real_failure_tokens) for item in failures):
        return False
    if not any(str(item).startswith("navigation_click_failed:") for item in failures):
        return False
    for item in visited:
        page_slug = str(item.get("page") or "")
        settle = dict(item.get("settle") or {})
        marker = dict(settle.get("content_marker") or {})
        if not bool(settle.get("settled")):
            return False
        if str(settle.get("current_slug") or "") != page_slug:
            return False
        if bool(settle.get("loading_visible")):
            return False
        if int(settle.get("body_text_length") or marker.get("main_text_length") or 0) <= 0:
            return False
        if not bool(marker.get("marker_present")):
            return False
        dom = dict(item.get("dom_health") or {})
        if (
            dom.get("dom_probe_error")
            or list(dom.get("emptyCards") or [])
            or list(dom.get("emptyCalcCheckShells") or [])
            or list(dom.get("blankPlaceholderBars") or [])
            or list(dom.get("fadedElements") or [])
            or (page_slug == "inputs" and list(dom.get("staleTokens") or []))
        ):
            return False
    return True


def _page_cycle_failure_capture_available(evidence: dict[str, Any]) -> bool:
    if bool(evidence.get("page_closed")) or bool(evidence.get("context_closed")) or bool(evidence.get("browser_closed")):
        return False
    if evidence.get("visible_text_excerpt_error") and not evidence.get("visible_text_excerpt"):
        return False
    return bool(evidence.get("full_page_screenshot") or evidence.get("viewport_screenshot") or evidence.get("visible_text_excerpt"))


def _page_cycle_failure_evidence(
    page,
    *,
    artifact_path: Path,
    label: str,
    visited: list[dict[str, Any]],
    failures: list[str],
    failing_cards: list[dict[str, Any]],
    console_messages: list[str] | None,
    page_cycle_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_") or "page_cycle"
    evidence: dict[str, Any] = {
        "created_at_ms": int(time.time() * 1000),
        "label": label,
        "failures": list(failures),
        "failing_cards": list(failing_cards),
        "visited_pages_summary": [
            {
                "page": item.get("page"),
                "label": item.get("label"),
                "click": item.get("click"),
                "settled": bool((item.get("settle") or {}).get("settled")),
                "current_slug": (item.get("settle") or {}).get("current_slug"),
                "loading_visible": bool((item.get("settle") or {}).get("loading_visible")),
                "body_text_length": (item.get("settle") or {}).get("body_text_length"),
                "marker_present": ((item.get("settle") or {}).get("content_marker") or {}).get("marker_present"),
                "page_failures": list(item.get("failures") or []),
            }
            for item in visited
        ],
        "page_closed": _page_cycle_page_closed_state(page),
        "context_closed": _page_cycle_context_closed_state(page),
        "browser_closed": _page_cycle_browser_closed_state(page),
        "screenshot_capture_status": "not_attempted",
        "missing_crop_targets": [],
        "capture_errors": [],
    }
    if evidence["page_closed"] or evidence["context_closed"] or evidence["browser_closed"]:
        evidence["screenshot_capture_status"] = "page_or_context_closed"
        evidence_path = _page_cycle_write_json(artifact_path / "page_cycle_failure_evidence.json", evidence)
        evidence["path"] = evidence_path
        return evidence
    try:
        evidence["current_url"] = str(getattr(page, "url", "") or "")
    except Exception as exc:
        evidence["current_url_error"] = f"{type(exc).__name__}: {exc}"
    try:
        evidence["page_title"] = str(page.title() or "")
    except Exception as exc:
        evidence["page_title_error"] = f"{type(exc).__name__}: {exc}"
    try:
        evidence["active_route_slug"] = _page_cycle_current_slug(page)
    except Exception as exc:
        evidence["active_route_slug_error"] = f"{type(exc).__name__}: {exc}"
        evidence["active_route_slug"] = ""
    evidence["streamlit_status"] = _page_cycle_streamlit_status(page)
    try:
        text = str(page.locator("body").inner_text(timeout=2_000) or "")
        evidence["visible_text_excerpt"] = text[:8_000]
        evidence["visible_text_length"] = len(text)
        evidence["visible_text_excerpt_path"] = _page_cycle_write_text(
            artifact_path / "page_cycle_failure_visible_text_excerpt.txt",
            evidence["visible_text_excerpt"],
        )
    except Exception as exc:
        evidence["visible_text_excerpt_error"] = f"{type(exc).__name__}: {exc}"
    evidence["visible_counts"] = _page_cycle_visible_counts(page, slug=str(evidence.get("active_route_slug") or ""))
    try:
        full_path = artifact_path / "page_cycle_full_page_failure.png"
        page.screenshot(path=str(full_path), full_page=True, timeout=10_000)
        evidence["full_page_screenshot"] = str(full_path)
    except Exception as exc:
        evidence["capture_errors"].append(f"full_page_screenshot:{type(exc).__name__}:{exc}")
    try:
        viewport_path = artifact_path / "page_cycle_viewport_failure.png"
        page.screenshot(path=str(viewport_path), full_page=False, timeout=10_000)
        evidence["viewport_screenshot"] = str(viewport_path)
    except Exception as exc:
        evidence["capture_errors"].append(f"viewport_screenshot:{type(exc).__name__}:{exc}")
    crop_specs = {
        "design_guide_screenshot": (
            artifact_path / "page_cycle_design_guide_failure.png",
            ['[data-testid="design-guide-card"]', '[data-testid*="design-guide"]', ".fast-guidance-item", "text=Design Guide"],
            "design_guide",
        ),
        "summary_cards_screenshot": (
            artifact_path / "page_cycle_summary_cards_failure.png",
            ['[data-testid*="summary"]', '[data-testid*="check"]', ".summary-card", "text=Bending", "text=Shear"],
            "summary_cards",
        ),
        "debug_or_probe_screenshot": (
            artifact_path / "page_cycle_debug_or_probe_failure.png",
            ['[data-testid*="debug"]', '[data-testid*="probe"]', 'textarea[aria-label*="Browser state"]', "text=Browser state", "text=debug"],
            "debug_or_probe",
        ),
    }
    for key, (path, selectors, missing_label) in crop_specs.items():
        captured, missing = _page_cycle_crop_first_visible(page, selectors, path)
        if captured:
            evidence[key] = captured
        elif missing:
            evidence["missing_crop_targets"].append(missing_label)
    try:
        evidence["console_errors"] = list(console_messages or [])
        evidence["console_errors_path"] = _page_cycle_write_json(
            artifact_path / "page_cycle_failure_console_errors.json",
            list(console_messages or []),
        )
    except Exception as exc:
        evidence["capture_errors"].append(f"console_errors:{type(exc).__name__}:{exc}")
    heartbeat_path = artifact_path / "lifecycle_heartbeat.json"
    if heartbeat_path.exists():
        try:
            evidence["lifecycle_heartbeat_snapshot"] = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        except Exception as exc:
            evidence["lifecycle_heartbeat_snapshot"] = {"read_error": f"{type(exc).__name__}: {exc}"}
    else:
        evidence["lifecycle_heartbeat_snapshot"] = {"missing": True}
    evidence["page_cycle_summary"] = {
        "ok": bool(page_cycle_diagnostics.get("ok")),
        "page_count": len(list(page_cycle_diagnostics.get("pages") or [])),
        "largest_mutation_burst": page_cycle_diagnostics.get("largest_mutation_burst"),
        "settle_reset_total": page_cycle_diagnostics.get("settle_reset_total"),
        "root_identity_change_total": page_cycle_diagnostics.get("root_identity_change_total"),
    }
    evidence["healthy_page_evidence"] = _page_cycle_visited_pages_look_healthy(visited, failures)
    if evidence.get("full_page_screenshot") or evidence.get("viewport_screenshot"):
        evidence["screenshot_capture_status"] = "partial" if evidence["capture_errors"] else "captured"
    else:
        evidence["screenshot_capture_status"] = "failed"
    evidence_path = _page_cycle_write_json(artifact_path / "page_cycle_failure_evidence.json", evidence)
    evidence["path"] = evidence_path
    return evidence


def run_page_cycle_ghost_ui_check(
    page,
    *,
    base_url: str,
    artifact_dir: Path | str | None = None,
    console_messages: list[str] | None = None,
    label: str = "page_cycle",
    timeout_s: float = 45.0,
    page_cycle_mode: str = "full",
) -> dict[str, Any]:
    """Actively cycle app pages and fail on empty shells, faded UI, or stale page bleed."""
    artifact_path = Path(artifact_dir) if artifact_dir is not None else None
    requested_page_cycle_mode = str(page_cycle_mode or "full").strip() or "full"
    page_sequence = PAGE_CYCLE_MODE_SEQUENCES.get(requested_page_cycle_mode)
    if page_sequence is None:
        requested_page_cycle_mode = "full"
        page_sequence = PAGE_CYCLE_SEQUENCE
    visited: list[dict[str, Any]] = []
    failures: list[str] = []
    failing_cards: list[dict[str, Any]] = []
    failed_page_captures: list[dict[str, Any]] = []
    bending_ready_gate_audits: list[dict[str, Any]] = []
    inputs_ready_gate_audits: list[dict[str, Any]] = []
    design_prerender_audits: list[dict[str, Any]] = []
    page_cycle_diagnostics: dict[str, Any] = {
        "label": label,
        "page_cycle_mode": requested_page_cycle_mode,
        "page_cycle_reduced": requested_page_cycle_mode != "full",
        "page_slug_sequence": [slug for slug, _ in page_sequence],
        "started_at_ms": int(time.time() * 1000),
        "pages": [],
        "design_prerender_audits": design_prerender_audits,
    }
    if artifact_path is not None:
        artifact_path.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_") or "page_cycle"
    timing_breakdown: dict[str, Any] = {
        "label": label,
        "page_cycle_mode": requested_page_cycle_mode,
        "page_cycle_reduced": requested_page_cycle_mode != "full",
        "started_at_ms": page_cycle_diagnostics["started_at_ms"],
        "current_stage": "start",
        "page_slug_sequence": [slug for slug, _ in page_sequence],
        "pages": [],
        "final_unmet_condition": None,
    }
    if requested_page_cycle_mode != "full":
        timing_breakdown["reduced_cycle_note"] = (
            "Reduced previous-fixed page-cycle scope. Stale DOM, ready-gate, and visible "
            "truth checks still run on every visited page."
        )

    def _write_timing_breakdown() -> None:
        if artifact_path is None:
            return
        timing_breakdown["updated_at_ms"] = int(time.time() * 1000)
        _page_cycle_write_json(artifact_path / f"{safe_label}_timing_breakdown.json", timing_breakdown)
        if "final_page_cycle" in safe_label:
            _page_cycle_write_json(artifact_path / "final_page_cycle_timing_breakdown.json", timing_breakdown)

    _write_timing_breakdown()
    if _page_cycle_current_slug(page) == "inputs":
        # Preserve the live Streamlit session, including cid, focused recipe,
        # and committed edits. Reopening bare base_url here creates a new
        # client session and turns the page-cycle check into a state-reset
        # test before it has navigated anywhere.
        timing_breakdown["current_stage"] = "open_inputs_skipped_already_active"
        timing_breakdown["open_inputs_preserved_live_session"] = True
        _write_timing_breakdown()
    else:
        try:
            timing_breakdown["current_stage"] = "open_inputs_start"
            _write_timing_breakdown()
            page.goto(_query(base_url, {"page": "inputs"}), wait_until="domcontentloaded", timeout=90_000)
            timing_breakdown["current_stage"] = "open_inputs_done"
            _write_timing_breakdown()
        except Exception as exc:
            failures.append(f"open_inputs_failed:{type(exc).__name__}:{exc}")
            timing_breakdown["current_stage"] = "open_inputs_failed"
            timing_breakdown["final_unmet_condition"] = failures[-1]
            _write_timing_breakdown()

    for index, (slug, page_label) in enumerate(page_sequence):
        page_started = time.perf_counter()
        page_timing: dict[str, Any] = {
            "page": slug,
            "label": page_label,
            "page_index": index,
            "started_at_ms": int(time.time() * 1000),
            "stage": "page_start",
        }
        timing_breakdown["pages"].append(page_timing)
        timing_breakdown["current_stage"] = f"{slug}:page_start"
        _write_timing_breakdown()
        click_meta: dict[str, Any] = {"clicked": False, "already_active": False, "errors": []}
        if index > 0:
            click_started = time.perf_counter()
            page_timing["stage"] = "click_start"
            timing_breakdown["current_stage"] = f"{slug}:click_start"
            _write_timing_breakdown()
            click_meta = _page_cycle_click_page(page, slug, page_label)
            page_timing["click_elapsed_ms"] = int(max(0.0, time.perf_counter() - click_started) * 1000)
            page_timing["click_helper_result"] = {
                "clicked": bool(click_meta.get("clicked")),
                "already_active": bool(click_meta.get("already_active")),
                "selector": click_meta.get("selector"),
                "classification": click_meta.get("classification"),
                "elapsed_ms": click_meta.get("elapsed_ms"),
                "current_slug": click_meta.get("current_slug"),
                "message": click_meta.get("message"),
                "errors": list(click_meta.get("errors") or [])[-5:],
            }
            page_timing["stage"] = "click_done"
            timing_breakdown["current_stage"] = f"{slug}:click_done"
            _write_timing_breakdown()
            if not click_meta.get("clicked") and not click_meta.get("already_active"):
                failure_class = (
                    STREAMLIT_RUNTIME_RECONNECT_CLASS
                    if _page_cycle_connection_error_visible(page)
                    else PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS
                )
                if failure_class == STREAMLIT_RUNTIME_RECONNECT_CLASS:
                    click_meta["classification"] = STREAMLIT_RUNTIME_RECONNECT_CLASS
                    click_meta["streamlit_status"] = _page_cycle_streamlit_status(page)
                failure = f"{failure_class}:{slug}:{click_meta.get('message')}"
                failures.append(failure)
                page_timing["stage"] = "navigation_failed"
                page_timing["failures"] = [failure]
                page_timing["elapsed_ms"] = int(max(0.0, time.perf_counter() - page_started) * 1000)
                timing_breakdown["current_stage"] = f"{slug}:navigation_failed"
                timing_breakdown["final_unmet_condition"] = failure
                current_slug = _page_cycle_current_slug(page)
                settle_meta = {
                    "expected_slug": slug,
                    "current_slug": current_slug,
                    "url": str(getattr(page, "url", "") or ""),
                    "polls": 0,
                    "settled": False,
                    "elapsed_ms": page_timing["elapsed_ms"],
                    "loading_visible": _page_cycle_loading_visible(page),
                    "content_marker": _page_cycle_content_marker(page, slug),
                    "page_cycle_churn_summary": _page_cycle_summarise_churn([], settle_reset_count=0, longest_stable=0),
                    "navigation_click_meta": click_meta,
                }
                dom = _page_cycle_dom_health(page, slug=slug)
                failed_page_capture = None
                if artifact_path is not None:
                    failed_page_capture = _page_cycle_failed_page_capture(
                        page,
                        artifact_path=artifact_path,
                        label=label,
                        slug=slug,
                        page_index=index,
                        settle_meta=settle_meta,
                        dom=dom,
                        page_failures=[failure],
                        console_messages=console_messages,
                    )
                    failed_page_captures.append(failed_page_capture)
                page_cycle_diagnostics["pages"].append(
                    {
                        "page": slug,
                        "label": page_label,
                        "page_index": index,
                        "settled": False,
                        "settle_elapsed_ms": settle_meta.get("elapsed_ms"),
                        "current_slug": current_slug,
                        "loading_visible": bool(settle_meta.get("loading_visible")),
                        "body_text_length": settle_meta.get("body_text_length"),
                        "content_marker": settle_meta.get("content_marker"),
                        "churn_summary": settle_meta.get("page_cycle_churn_summary"),
                        "navigation_click_meta": click_meta,
                    }
                )
                visited.append(
                    {
                        "page": slug,
                        "label": page_label,
                        "click": click_meta,
                        "settle": settle_meta,
                        "dom_health": dom,
                        "failures": [failure],
                        "failed_page_capture": failed_page_capture,
                        "elapsed_ms": page_timing["elapsed_ms"],
                    }
                )
                _write_timing_breakdown()
                break
        runtime_transition_status = _page_cycle_streamlit_status(page)
        runtime_transition_failed = runtime_transition_status in {"CONNECTING", "CONNECTION ERROR", "STREAMLIT SERVER IS NOT RESPONDING"}
        page_timing["streamlit_status_before_ready_gate"] = runtime_transition_status
        bending_ready_gate_audit = None
        bending_ready_gate_failed = False
        inputs_ready_gate_audit = None
        inputs_ready_gate_failed = False
        if slug == "inputs" and not runtime_transition_failed:
            gate_started = time.perf_counter()
            page_timing["stage"] = "inputs_ready_gate_start"
            timing_breakdown["current_stage"] = f"{slug}:inputs_ready_gate_start"
            _write_timing_breakdown()
            inputs_ready_gate_audit = _page_cycle_wait_for_inputs_ready_gate(page, timeout_s=max(float(timeout_s), 45.0))
            page_timing["ready_gate_elapsed_ms"] = int(max(0.0, time.perf_counter() - gate_started) * 1000)
            page_timing["ready_gate_ok"] = bool(inputs_ready_gate_audit.get("ok"))
            page_timing["ready_gate_poll_count"] = inputs_ready_gate_audit.get("poll_count")
            page_timing["stage"] = "inputs_ready_gate_done"
            timing_breakdown["current_stage"] = f"{slug}:inputs_ready_gate_done"
            _write_timing_breakdown()
            inputs_ready_gate_audits.append(
                {
                    "page": slug,
                    "page_index": index,
                    "label": page_label,
                    **dict(inputs_ready_gate_audit),
                }
            )
            inputs_ready_gate_failed = not bool(inputs_ready_gate_audit.get("ok"))
        if slug == "bending" and not runtime_transition_failed:
            gate_started = time.perf_counter()
            page_timing["stage"] = "bending_ready_gate_start"
            timing_breakdown["current_stage"] = f"{slug}:bending_ready_gate_start"
            _write_timing_breakdown()
            bending_ready_gate_audit = _page_cycle_wait_for_bending_ready_gate(page, timeout_s=max(float(timeout_s), 45.0))
            page_timing["ready_gate_elapsed_ms"] = int(max(0.0, time.perf_counter() - gate_started) * 1000)
            page_timing["ready_gate_ok"] = bool(bending_ready_gate_audit.get("ok"))
            page_timing["ready_gate_poll_count"] = bending_ready_gate_audit.get("poll_count")
            page_timing["stage"] = "bending_ready_gate_done"
            timing_breakdown["current_stage"] = f"{slug}:bending_ready_gate_done"
            _write_timing_breakdown()
            bending_ready_gate_audits.append(
                {
                    "page": slug,
                    "page_index": index,
                    "label": page_label,
                    **dict(bending_ready_gate_audit),
                }
            )
            bending_ready_gate_failed = not bool(bending_ready_gate_audit.get("ok"))
        settle_started = time.perf_counter()
        page_timing["stage"] = "settle_start"
        timing_breakdown["current_stage"] = f"{slug}:settle_start"
        _write_timing_breakdown()
        if runtime_transition_failed:
            current_slug = _page_cycle_current_slug(page)
            settle_meta = {
                "expected_slug": slug,
                "current_slug": current_slug,
                "url": str(getattr(page, "url", "") or ""),
                "body_text_length": 0,
                "loading_visible": True,
                "content_marker": {},
                "polls": 0,
                "settled": False,
                "elapsed_ms": int(max(0.0, time.perf_counter() - settle_started) * 1000),
                "streamlit_status": runtime_transition_status,
                "page_cycle_churn_summary": _page_cycle_summarise_churn([], settle_reset_count=0, longest_stable=0),
            }
        elif bending_ready_gate_failed or inputs_ready_gate_failed:
            current_slug = _page_cycle_current_slug(page)
            content_marker = _page_cycle_content_marker(page, slug)
            loading_visible = _page_cycle_loading_visible(page)
            churn_snapshot = _page_cycle_churn_snapshot(page, slug=slug, detail=True)
            body_text_length = int(content_marker.get("main_text_length") or churn_snapshot.get("body_text_length") or 0)
            gate_classification = (
                BENDING_READY_GATE_TIMEOUT_CLASS if bending_ready_gate_failed else INPUTS_READY_GATE_TIMEOUT_CLASS
            )
            settle_meta = {
                "expected_slug": slug,
                "current_slug": current_slug,
                "url": str(getattr(page, "url", "") or ""),
                "body_text_length": body_text_length,
                "loading_visible": loading_visible,
                "content_marker": content_marker,
                "polls": 0,
                "settled": False,
                "elapsed_ms": int(max(0.0, time.perf_counter() - settle_started) * 1000),
                "bending_ready_gate_audit": bending_ready_gate_audit,
                "inputs_ready_gate_audit": inputs_ready_gate_audit,
                "page_cycle_churn_summary": _page_cycle_summarise_churn(
                    [
                        {
                            "iteration": 1,
                            "elapsed_ms": 0,
                            "ready_conditions": {
                                "slug_matches": current_slug == slug,
                                "body_has_text": body_text_length > 0,
                                "marker_present": bool(content_marker.get("marker_present")),
                                "loading_visible": loading_visible,
                                gate_classification: True,
                            },
                            "signature": gate_classification,
                            "snapshot": churn_snapshot,
                        }
                    ],
                    settle_reset_count=0,
                    longest_stable=0,
                ),
            }
        else:
            settle_meta = _page_cycle_wait_for_settle(page, expected_slug=slug, timeout_s=timeout_s)
            settle_meta["elapsed_ms"] = int(max(0.0, time.perf_counter() - settle_started) * 1000)
            if bending_ready_gate_audit is not None:
                settle_meta["bending_ready_gate_audit"] = bending_ready_gate_audit
            if inputs_ready_gate_audit is not None:
                settle_meta["inputs_ready_gate_audit"] = inputs_ready_gate_audit
        page_timing["settle_elapsed_ms"] = settle_meta.get("elapsed_ms")
        page_timing["settled"] = bool(settle_meta.get("settled"))
        page_timing["current_slug"] = settle_meta.get("current_slug")
        page_timing["visible_text_stability_ms"] = (
            ((settle_meta.get("page_cycle_churn_summary") or {}).get("longest_stable_ms"))
            if isinstance(settle_meta.get("page_cycle_churn_summary"), dict)
            else None
        )
        chart_audit = settle_meta.get("chart_internal_filter_audit") if isinstance(settle_meta, dict) else None
        if isinstance(chart_audit, dict):
            page_timing["chart_internal_mutations_ignored"] = chart_audit.get("chart_internal_mutations_ignored")
            page_timing["chart_internal_mutation_count"] = chart_audit.get("total_chart_internal_mutations")
        churn = dict(settle_meta.get("page_cycle_churn_summary") or {})
        page_timing["settle_reset_count"] = churn.get("settle_reset_count")
        page_timing["iteration_count"] = churn.get("iteration_count")
        last_snapshot = churn.get("last_snapshot") if isinstance(churn.get("last_snapshot"), dict) else {}
        page_timing["faded_inert_count_last"] = last_snapshot.get("faded_inactive_overlay_count")
        page_timing["visible_card_count_last"] = last_snapshot.get("visible_card_count")
        page_timing["visible_calc_box_count_last"] = last_snapshot.get("visible_calc_box_count")
        page_timing["loading_spinner_count_last"] = last_snapshot.get("loading_spinner_count")
        page_timing["stage"] = "settle_done"
        timing_breakdown["current_stage"] = f"{slug}:settle_done"
        _write_timing_breakdown()
        design_prerender_audit = None
        design_prerender_failed = False
        if slug == "design" and bool(settle_meta.get("settled")):
            initial_design_prerender = _page_cycle_design_prerender_snapshot(page)
            if bool(initial_design_prerender.get("transitional_design_prerender_detected")):
                page_timing["stage"] = "design_prerender_wait_start"
                page_timing["transitional_design_prerender_detected"] = True
                page_timing["design_prerender_initial"] = dict(initial_design_prerender)
                timing_breakdown["current_stage"] = f"{slug}:design_prerender_wait_start"
                _write_timing_breakdown()
                design_prerender_audit = _page_cycle_wait_for_design_prerender_exit(
                    page,
                    timeout_s=max(3.0, float(timeout_s)),
                )
                design_prerender_failed = not bool(design_prerender_audit.get("ok"))
                design_prerender_audits.append(
                    {
                        "page": slug,
                        "page_index": index,
                        "label": page_label,
                        **dict(design_prerender_audit),
                    }
                )
                settle_meta["design_prerender_audit"] = design_prerender_audit
                page_timing["design_prerender_elapsed_ms"] = design_prerender_audit.get("elapsed_ms")
                page_timing["design_prerender_ok"] = bool(design_prerender_audit.get("ok"))
                page_timing["design_prerender_last_poll"] = design_prerender_audit.get("last_poll")
                page_timing["stage"] = "design_prerender_wait_done"
                timing_breakdown["current_stage"] = f"{slug}:design_prerender_wait_done"
                if design_prerender_failed:
                    timing_breakdown["final_unmet_condition"] = f"{DESIGN_PAGE_PRE_RENDER_TIMEOUT_CLASS}:{slug}"
                _write_timing_breakdown()
            else:
                design_prerender_audit = {
                    "ok": True,
                    "classification": None,
                    "poll_count": 1,
                    "elapsed_ms": 0,
                    "transitional_design_prerender_detected": False,
                    "first_poll": initial_design_prerender,
                    "last_poll": initial_design_prerender,
                    "observations_tail": [initial_design_prerender],
                    "final_ghost_empty_checks_ran_after_render_completion": True,
                }
                design_prerender_audits.append(
                    {
                        "page": slug,
                        "page_index": index,
                        "label": page_label,
                        **dict(design_prerender_audit),
                    }
                )
                settle_meta["design_prerender_audit"] = design_prerender_audit
        dom = _page_cycle_dom_health(page, slug=slug)
        page_timing["stage"] = "dom_health_done"
        _write_timing_breakdown()
        churn_summary = dict(settle_meta.get("page_cycle_churn_summary") or {})
        last_snapshot = churn_summary.get("last_snapshot") if isinstance(churn_summary.get("last_snapshot"), dict) else {}
        page_cycle_diagnostics["pages"].append(
            {
                "page": slug,
                "label": page_label,
                "page_index": index,
                "settled": bool(settle_meta.get("settled")),
                "settle_elapsed_ms": settle_meta.get("elapsed_ms"),
                "current_slug": settle_meta.get("current_slug"),
                "loading_visible": bool(settle_meta.get("loading_visible")),
                "body_text_length": settle_meta.get("body_text_length"),
                "content_marker": settle_meta.get("content_marker"),
                "churn_summary": churn_summary,
                "settle_filter_audit": settle_meta.get("chart_internal_filter_audit"),
                "bending_ready_gate_audit": bending_ready_gate_audit,
                "inputs_ready_gate_audit": inputs_ready_gate_audit,
                "design_prerender_audit": design_prerender_audit,
                "visible_card_count": last_snapshot.get("visible_card_count"),
                "visible_calc_box_count": last_snapshot.get("visible_calc_box_count"),
                "visible_expander_count": last_snapshot.get("visible_expander_count"),
                "faded_inactive_overlay_count": last_snapshot.get("faded_inactive_overlay_count"),
                "loading_spinner_count": last_snapshot.get("loading_spinner_count"),
                "streamlit_block_count": last_snapshot.get("streamlit_block_count"),
                "summary_table_exists": last_snapshot.get("summary_table_exists"),
                "design_guide_container_exists": last_snapshot.get("design_guide_container_exists"),
            }
        )
        page_failures: list[str] = []
        if runtime_transition_failed:
            page_failures.append(f"{STREAMLIT_RUNTIME_RECONNECT_CLASS}:{slug}:{runtime_transition_status}")
        elif bending_ready_gate_failed:
            page_failures.append(f"{BENDING_READY_GATE_TIMEOUT_CLASS}:{slug}")
        elif inputs_ready_gate_failed:
            page_failures.append(f"{INPUTS_READY_GATE_TIMEOUT_CLASS}:{slug}")
        elif design_prerender_failed:
            page_failures.append(f"{DESIGN_PAGE_PRE_RENDER_TIMEOUT_CLASS}:{slug}")
        elif not settle_meta.get("settled"):
            streamlit_status = _page_cycle_streamlit_status(page)
            if streamlit_status in {"CONNECTING", "CONNECTION ERROR", "STREAMLIT SERVER IS NOT RESPONDING"} or _page_cycle_connection_error_visible(page):
                page_failures.append(f"{STREAMLIT_RUNTIME_RECONNECT_CLASS}:{slug}:{streamlit_status or 'runtime_transition'}")
            elif str(settle_meta.get("current_slug") or "") != slug:
                page_failures.append(
                    f"{PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS}:{slug}:current_slug={settle_meta.get('current_slug')}"
                )
            else:
                page_failures.append(f"page_did_not_settle:{slug}")
        if dom.get("dom_probe_error"):
            page_failures.append(f"dom_probe_error:{dom.get('dom_probe_error')}")
        empty_cards = list(dom.get("emptyCards") or [])
        if empty_cards and not design_prerender_failed:
            page_failures.append(f"empty_calc_or_card_visible:{slug}:{len(empty_cards)}")
            for item in empty_cards[:10]:
                failing_cards.append({"page": slug, "reason": "empty_calc_or_card_visible", **dict(item)})
        empty_calc_check_shells = list(dom.get("emptyCalcCheckShells") or [])
        if empty_calc_check_shells and not design_prerender_failed:
            page_failures.append(f"{EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS}:{slug}:{len(empty_calc_check_shells)}")
            for item in empty_calc_check_shells[:10]:
                failing_cards.append({"page": slug, "reason": EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS, **dict(item)})
        blank_bars = list(dom.get("blankPlaceholderBars") or [])
        if blank_bars and not design_prerender_failed:
            page_failures.append(f"empty_placeholder_card_visible:{slug}:{len(blank_bars)}")
            for item in blank_bars[:10]:
                failing_cards.append({"page": slug, "reason": "empty_placeholder_card_visible", **dict(item)})
        faded = list(dom.get("fadedElements") or [])
        app_containers = list(dom.get("appContainers") or [])
        globally_faded = any(
            isinstance(item, dict)
            and float(item.get("opacity") or 1.0) < 0.75
            and float((item.get("rect") or {}).get("width") or 0.0) > 400
            for item in app_containers
        )
        if globally_faded or (slug == "inputs" and faded):
            page_failures.append(f"faded_or_disabled_ui_visible:{slug}")
            for item in faded[:10]:
                failing_cards.append({"page": slug, "reason": "faded_or_disabled_ui_visible", **dict(item)})
        if (
            dom.get("designGuideHeadingVisible")
            and dom.get("genericButtonVisible")
            and int(dom.get("designGuideCardCount") or 0) < 1
        ):
            page_failures.append("generic_cta_without_design_guide_card")
        if slug == "inputs":
            stale_tokens = list(dom.get("staleTokens") or [])
            if stale_tokens:
                page_failures.append(f"stale_page_content_visible_on_inputs:{', '.join(stale_tokens)}")
            controls = dict(dom.get("inputControls") or {})
            manager_controls = {
                key: bool(present)
                for key, present in controls.items()
                if key != "batch_design"
            }
            # The current Batch design workspace is intentionally collapsed.
            # Its manager controls are rendered inside the expander and are
            # therefore absent from visible body text until it is opened.
            # A collapsed workspace marker is healthy; if any manager control
            # is visible, retain the stronger all-controls-present contract.
            missing_controls = []
            if not bool(controls.get("batch_design")):
                missing_controls.append("batch_design")
            if any(manager_controls.values()):
                missing_controls.extend(
                    sorted(
                        key
                        for key, present in manager_controls.items()
                        if not present
                    )
                )
            if missing_controls:
                page_failures.append(f"inputs_controls_missing_after_return:{', '.join(missing_controls)}")
        failed_page_capture = None
        if page_failures and artifact_path is not None:
            failed_page_capture = _page_cycle_failed_page_capture(
                page,
                artifact_path=artifact_path,
                label=label,
                slug=slug,
                page_index=index,
                settle_meta=settle_meta,
                dom=dom,
                page_failures=page_failures,
                console_messages=console_messages,
            )
            failed_page_captures.append(failed_page_capture)
        if page_failures:
            failures.extend(page_failures)
        page_timing["failures"] = list(page_failures)
        page_timing["elapsed_ms"] = int(max(0.0, time.perf_counter() - page_started) * 1000)
        page_timing["stage"] = "page_done"
        timing_breakdown["current_stage"] = f"{slug}:page_done"
        if page_failures and not timing_breakdown.get("final_unmet_condition"):
            timing_breakdown["final_unmet_condition"] = ";".join(page_failures)
        _write_timing_breakdown()
        visited.append(
            {
                "page": slug,
                "label": page_label,
                "click": click_meta,
                "settle": settle_meta,
                "dom_health": dom,
                "failures": page_failures,
                "failed_page_capture": failed_page_capture,
                "elapsed_ms": int(max(0.0, time.perf_counter() - page_started) * 1000),
            }
        )
        if page_failures:
            break

    ok = not failures
    timing_breakdown["current_stage"] = "done"
    timing_breakdown["ok"] = bool(ok)
    timing_breakdown["failures"] = list(failures)
    timing_breakdown["completed_at_ms"] = int(time.time() * 1000)
    if failures and not timing_breakdown.get("final_unmet_condition"):
        timing_breakdown["final_unmet_condition"] = ";".join(failures)
    _write_timing_breakdown()
    page_cycle_diagnostics["completed_at_ms"] = int(time.time() * 1000)
    page_cycle_diagnostics["ok"] = bool(ok)
    page_cycle_diagnostics["failures"] = list(failures)
    page_cycle_diagnostics["page_cycle_iteration_total"] = sum(
        int(((page_item.get("churn_summary") or {}).get("iteration_count") or 0))
        for page_item in list(page_cycle_diagnostics.get("pages") or [])
    )
    page_cycle_diagnostics["settle_reset_total"] = sum(
        int(((page_item.get("churn_summary") or {}).get("settle_reset_count") or 0))
        for page_item in list(page_cycle_diagnostics.get("pages") or [])
    )
    page_cycle_diagnostics["largest_mutation_burst"] = max(
        [
            int(((page_item.get("churn_summary") or {}).get("largest_mutation_burst") or 0))
            for page_item in list(page_cycle_diagnostics.get("pages") or [])
        ]
        or [0]
    )
    page_cycle_diagnostics["root_identity_change_total"] = sum(
        int(((page_item.get("churn_summary") or {}).get("root_identity_change_count") or 0))
        for page_item in list(page_cycle_diagnostics.get("pages") or [])
    )
    page_cycle_diagnostics["correlation_summary"] = {
        "summary_rebuild_correlation_hint": (
            "Compare page churn timestamps with browser-state ux_latency_probe and speed_profile_probe; "
            "this file records page-cycle DOM churn windows without changing assertions."
        ),
        "pages_with_summary_table_absent": [
            page_item.get("page")
            for page_item in list(page_cycle_diagnostics.get("pages") or [])
            if not bool(page_item.get("summary_table_exists"))
        ],
        "pages_with_design_guide_container_absent_on_inputs": [
            page_item.get("page")
            for page_item in list(page_cycle_diagnostics.get("pages") or [])
            if page_item.get("page") == "inputs" and not bool(page_item.get("design_guide_container_exists"))
        ],
    }
    diagnostics_path = None
    if artifact_path is not None:
        safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")
        diagnostics_path = _page_cycle_write_json(
            artifact_path / f"{safe_label}_page_cycle_diagnostics.json",
            page_cycle_diagnostics,
        )
    bending_ready_gate_audit: dict[str, Any] = {
        "created_at_ms": int(time.time() * 1000),
        "pages": bending_ready_gate_audits,
        "any_timeout": any(not bool(item.get("ok")) for item in bending_ready_gate_audits),
        "all_passed": bool(bending_ready_gate_audits) and all(bool(item.get("ok")) for item in bending_ready_gate_audits),
    }
    bending_ready_gate_timing_breakdown: dict[str, Any] = {
        "created_at_ms": int(time.time() * 1000),
        "pages": [
            {
                "page": item.get("page"),
                "page_index": item.get("page_index"),
                "ok": item.get("ok"),
                "classification": item.get("classification"),
                "ready_elapsed_ms": item.get("ready_elapsed_ms"),
                "poll_count": item.get("poll_count"),
                "polls": [
                    {
                        "poll_index": poll.get("poll_index"),
                        "elapsed_ms": poll.get("elapsed_ms"),
                        "stable_reads": poll.get("stable_reads"),
                        "unmet_conditions": list(poll.get("unmet_conditions") or []),
                        "timing_breakdown_ms": dict(poll.get("timing_breakdown_ms") or {}),
                    }
                    for poll in list(item.get("polls") or [])
                ],
                "max_total_poll_ms": max(
                    [
                        float(dict(poll.get("timing_breakdown_ms") or {}).get("total_poll_ms") or 0.0)
                        for poll in list(item.get("polls") or [])
                    ]
                    or [0.0]
                ),
                "max_marker_eval_ms": max(
                    [
                        float(dict(poll.get("timing_breakdown_ms") or {}).get("marker_eval_ms") or 0.0)
                        for poll in list(item.get("polls") or [])
                    ]
                    or [0.0]
                ),
            }
            for item in bending_ready_gate_audits
        ],
        "notes": (
            "Diagnostics only. Measures Bending ready-gate poll overhead; "
            "does not alter page-cycle assertions or timeout thresholds."
        ),
    }
    inputs_ready_gate_audit: dict[str, Any] = {
        "created_at_ms": int(time.time() * 1000),
        "pages": inputs_ready_gate_audits,
        "any_timeout": any(not bool(item.get("ok")) for item in inputs_ready_gate_audits),
        "all_passed": bool(inputs_ready_gate_audits) and all(bool(item.get("ok")) for item in inputs_ready_gate_audits),
        "notes": (
            "Diagnostics only. Waits for the visible Inputs body to finish its first render "
            "before the existing page-cycle settle assertions run."
        ),
    }
    heavy_diagnostics_required = not ok
    heavy_diagnostics_deferred: dict[str, Any] = {
        "deferred": True,
        "reason": "page_cycle_pass_heavy_diagnostics_deferred",
        "notes": (
            "Heavy mutation/chart/content-diff diagnostics are built on page-cycle failure. "
            "All page-cycle assertions already ran before this point."
        ),
    }
    probe_events = _page_cycle_extract_probe_events(page) if heavy_diagnostics_required else []
    dom_mutation_attribution = (
        _page_cycle_build_mutation_attribution(page_cycle_diagnostics, probe_events)
        if heavy_diagnostics_required
        else dict(heavy_diagnostics_deferred)
    )
    chart_mutation_diagnostics = (
        _page_cycle_build_chart_mutation_diagnostics(page_cycle_diagnostics)
        if heavy_diagnostics_required
        else dict(heavy_diagnostics_deferred)
    )
    settle_signal_breakdown = (
        _page_cycle_build_settle_signal_breakdown(page_cycle_diagnostics)
        if heavy_diagnostics_required
        else dict(heavy_diagnostics_deferred)
    )
    chart_internal_filter_audit = (
        _page_cycle_build_chart_internal_filter_audit(page_cycle_diagnostics)
        if heavy_diagnostics_required
        else dict(heavy_diagnostics_deferred)
    )
    bending_content_stability_diff = (
        _page_cycle_build_bending_content_stability_diff(page_cycle_diagnostics)
        if heavy_diagnostics_required
        else dict(heavy_diagnostics_deferred)
    )
    attribution_path = None
    chart_diagnostics_path = None
    settle_breakdown_path = None
    chart_filter_audit_path = None
    bending_content_diff_path = None
    bending_ready_gate_audit_path = None
    bending_ready_gate_timing_breakdown_path = None
    inputs_ready_gate_audit_path = None
    design_prerender_audit_path = None
    if artifact_path is not None:
        safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")
        if heavy_diagnostics_required:
            attribution_path = _page_cycle_write_json(
                artifact_path / f"{safe_label}_dom_mutation_attribution.json",
                dom_mutation_attribution,
            )
            _page_cycle_write_json(
                artifact_path / "dom_mutation_attribution.json",
                dom_mutation_attribution,
            )
            chart_diagnostics_path = _page_cycle_write_json(
                artifact_path / f"{safe_label}_chart_mutation_diagnostics.json",
                chart_mutation_diagnostics,
            )
            _page_cycle_write_json(
                artifact_path / "chart_mutation_diagnostics.json",
                chart_mutation_diagnostics,
            )
            settle_breakdown_path = _page_cycle_write_json(
                artifact_path / f"{safe_label}_settle_signal_breakdown.json",
                settle_signal_breakdown,
            )
            _page_cycle_write_json(
                artifact_path / "settle_signal_breakdown.json",
                settle_signal_breakdown,
            )
            chart_filter_audit_path = _page_cycle_write_json(
                artifact_path / f"{safe_label}_chart_internal_filter_audit.json",
                chart_internal_filter_audit,
            )
            _page_cycle_write_json(
                artifact_path / "chart_internal_filter_audit.json",
                chart_internal_filter_audit,
            )
            bending_content_diff_path = _page_cycle_write_json(
                artifact_path / f"{safe_label}_bending_content_stability_diff.json",
                bending_content_stability_diff,
            )
            _page_cycle_write_json(
                artifact_path / "bending_content_stability_diff.json",
                bending_content_stability_diff,
            )
        bending_ready_gate_audit_path = _page_cycle_write_json(
            artifact_path / f"{safe_label}_bending_ready_gate_audit.json",
            bending_ready_gate_audit,
        )
        _page_cycle_write_json(
            artifact_path / "bending_ready_gate_audit.json",
            bending_ready_gate_audit,
        )
        bending_ready_gate_timing_breakdown_path = _page_cycle_write_json(
            artifact_path / f"{safe_label}_bending_ready_gate_timing_breakdown.json",
            bending_ready_gate_timing_breakdown,
        )
        _page_cycle_write_json(
            artifact_path / "bending_ready_gate_timing_breakdown.json",
            bending_ready_gate_timing_breakdown,
        )
        inputs_ready_gate_audit_path = _page_cycle_write_json(
            artifact_path / f"{safe_label}_inputs_ready_gate_audit.json",
            inputs_ready_gate_audit,
        )
        _page_cycle_write_json(
            artifact_path / "inputs_ready_gate_audit.json",
            inputs_ready_gate_audit,
        )
        design_prerender_audit = {
            "created_at_ms": int(time.time() * 1000),
            "pages": design_prerender_audits,
            "any_timeout": any(not bool(item.get("ok")) for item in design_prerender_audits),
            "all_passed": bool(design_prerender_audits)
            and all(bool(item.get("ok")) for item in design_prerender_audits),
            "final_ghost_empty_checks_ran_after_render_completion": any(
                bool(item.get("final_ghost_empty_checks_ran_after_render_completion"))
                for item in design_prerender_audits
            ),
        }
        design_prerender_audit_path = _page_cycle_write_json(
            artifact_path / f"{safe_label}_design_prerender_audit.json",
            design_prerender_audit,
        )
        _page_cycle_write_json(
            artifact_path / "design_prerender_audit.json",
            design_prerender_audit,
        )
    page_cycle_failure_evidence: dict[str, Any] | None = None
    if not ok and artifact_path is not None:
        page_cycle_failure_evidence = _page_cycle_failure_evidence(
            page,
            artifact_path=artifact_path,
            label=label,
            visited=visited,
            failures=failures,
            failing_cards=failing_cards,
            console_messages=console_messages,
            page_cycle_diagnostics=page_cycle_diagnostics,
        )
    failure_classification = None
    if not ok:
        if any(str(item).startswith(EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS) for item in failures):
            failure_classification = EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS
        elif any(str(item).startswith(BENDING_READY_GATE_TIMEOUT_CLASS) for item in failures):
            failure_classification = BENDING_READY_GATE_TIMEOUT_CLASS
        elif any(str(item).startswith(INPUTS_READY_GATE_TIMEOUT_CLASS) for item in failures):
            failure_classification = INPUTS_READY_GATE_TIMEOUT_CLASS
        elif any(str(item).startswith(DESIGN_PAGE_PRE_RENDER_TIMEOUT_CLASS) for item in failures):
            failure_classification = DESIGN_PAGE_PRE_RENDER_TIMEOUT_CLASS
        elif any(str(item).startswith(STREAMLIT_RUNTIME_RECONNECT_CLASS) for item in failures):
            failure_classification = STREAMLIT_RUNTIME_RECONNECT_CLASS
        elif any(str(item).startswith(PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS) for item in failures):
            failure_classification = PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS
        elif page_cycle_failure_evidence is not None and not _page_cycle_failure_capture_available(page_cycle_failure_evidence):
            failure_classification = PAGE_CYCLE_CAPTURE_UNAVAILABLE_CLASS
        elif page_cycle_failure_evidence is not None and bool(page_cycle_failure_evidence.get("healthy_page_evidence")):
            failure_classification = PAGE_CYCLE_FALSE_POSITIVE_HEALTHY_CLASS
        else:
            failure_classification = PAGE_CYCLE_GHOST_FAILURE_CLASS
    result: dict[str, Any] = {
        "checked": True,
        "ok": ok,
        "failure_classification": failure_classification,
        "message": PAGE_CYCLE_GHOST_FAILURE_MESSAGE if not ok else "page-cycle UI health check passed",
        "page_cycle_mode": requested_page_cycle_mode,
        "page_cycle_reduced": requested_page_cycle_mode != "full",
        "page_slug_sequence": [slug for slug, _ in page_sequence],
        "navigated_required_page_cycle": len(visited) == len(page_sequence),
        "navigated_full_page_cycle": len(visited) == len(PAGE_CYCLE_SEQUENCE)
        and requested_page_cycle_mode == "full",
        "visited_pages": visited,
        "failures": failures,
        "failing_cards": failing_cards,
        "failed_page_captures": failed_page_captures,
        "page_cycle_diagnostics": page_cycle_diagnostics,
        "page_cycle_diagnostics_path": diagnostics_path,
        "dom_mutation_attribution": dom_mutation_attribution,
        "dom_mutation_attribution_path": attribution_path,
        "chart_mutation_diagnostics": chart_mutation_diagnostics,
        "chart_mutation_diagnostics_path": chart_diagnostics_path,
        "settle_signal_breakdown": settle_signal_breakdown,
        "settle_signal_breakdown_path": settle_breakdown_path,
        "chart_internal_filter_audit": chart_internal_filter_audit,
        "chart_internal_filter_audit_path": chart_filter_audit_path,
        "bending_content_stability_diff": bending_content_stability_diff,
        "bending_content_stability_diff_path": bending_content_diff_path,
        "bending_ready_gate_audit": bending_ready_gate_audit,
        "bending_ready_gate_audit_path": bending_ready_gate_audit_path,
        "bending_ready_gate_timing_breakdown": bending_ready_gate_timing_breakdown,
        "bending_ready_gate_timing_breakdown_path": bending_ready_gate_timing_breakdown_path,
        "inputs_ready_gate_audit": inputs_ready_gate_audit,
        "inputs_ready_gate_audit_path": inputs_ready_gate_audit_path,
        "design_prerender_audits": design_prerender_audits,
        "design_prerender_audit_path": design_prerender_audit_path,
        "page_cycle_failure_evidence": page_cycle_failure_evidence,
        "page_cycle_failure_evidence_path": (
            page_cycle_failure_evidence.get("path") if isinstance(page_cycle_failure_evidence, dict) else None
        ),
        "console_error_count": len(console_messages or []),
    }
    if not ok and artifact_path is not None:
        result["active_url"] = str(getattr(page, "url", "") or "")
        result["active_page_tab"] = visited[-1].get("page") if visited else ""
        result["current_url_path"] = _page_cycle_write_text(
            artifact_path / f"{label}_active_url.txt",
            str(result.get("active_url") or ""),
        )
        result["active_page_path"] = _page_cycle_write_text(
            artifact_path / f"{label}_active_page.txt",
            str(result.get("active_page_tab") or ""),
        )
        result["console_errors_path"] = _page_cycle_write_json(
            artifact_path / f"{label}_console_errors.json",
            list(console_messages or []),
        )
        result["failing_cards_path"] = _page_cycle_write_json(
            artifact_path / f"{label}_failing_cards.json",
            failing_cards,
        )
        result["dom_snapshot_path"] = _page_cycle_write_text(
            artifact_path / f"{label}_dom_excerpt.html",
            _page_cycle_html_excerpt(page, failing_cards),
        )
        try:
            visible_text = str(page.locator("body").inner_text(timeout=2000) or "")[:8000]
        except Exception:
            visible_text = ""
        result["visible_text_excerpt_path"] = _page_cycle_write_text(
            artifact_path / f"{label}_visible_text_excerpt.txt",
            visible_text,
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8512)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--normal-mode", action="store_true")
    parser.add_argument("--steps", nargs="*", default=None)
    args = parser.parse_args(argv)

    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    try:
        if args.base_url is None:
            process = _start_streamlit(args.port)
        else:
            _wait_for_http(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context()
            page = context.new_page()
            start_query = {"page": "inputs"}
            if not args.normal_mode:
                start_query["browser_recipe"] = "A_bending_under_only"
            page.goto(
                _query(base_url, start_query),
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            page.get_by_label(BROWSER_STATE_LABEL).wait_for(state="attached", timeout=30_000)

            results: list[dict[str, Any]] = []
            selected_steps = LADDER_STEPS
            if args.steps:
                wanted = set(args.steps)
                selected_steps = [step for step in LADDER_STEPS if step[0] in wanted]
            steps = list(selected_steps[: args.limit] if args.limit else selected_steps)
            for step_name, mu, vu in steps:
                print(f"RUNNING {step_name} Mu={mu} Vu={vu}", file=sys.stderr, flush=True)
                pre_state, pre_settle_meta = _apply_live_inputs(page, mu=mu, vu=vu)
                tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
                button = page.get_by_role("button", name="Run one-click auto design")
                button_found = False
                click_error = None
                click_started_ms = None
                guidance_actionable = _preclick_actionable(pre_state)
                if guidance_actionable:
                    try:
                        button.wait_for(timeout=10_000)
                        if button.is_visible() and button.is_enabled():
                            button_found = True
                            click_started_ms = int(time.time() * 1000)
                            button.click(timeout=10_000)
                    except PlaywrightTimeoutError as exc:
                        click_error = f"{type(exc).__name__}: {exc}"
                post_state = pre_state
                run_end_event = None
                post_settle_meta: dict[str, Any] = {
                    "settle_wait_time_ms": 0,
                    "poll_cycles": 0,
                    "stability_multiple_cycles": False,
                }
                if button_found:
                    run_end_event, _ = _wait_for_run_end(
                        tracer_offset,
                        start_time_ms=click_started_ms,
                    )
                    if run_end_event is not None:
                        post_state, post_publish_aligned, post_settle_meta = _wait_for_post_publish_alignment(
                            page,
                            mu=mu,
                            vu=vu,
                            run_end_data=dict((run_end_event or {}).get("data") or {}),
                        )
                    else:
                        post_state, post_publish_aligned, post_settle_meta = _wait_for_post_click_state_without_run_end(
                            page,
                            mu=mu,
                            vu=vu,
                            pre_state=pre_state,
                        )
                    post_state = dict(post_state or {})
                    post_state["_post_publish_aligned"] = bool(post_publish_aligned)
                validation = _validate_live_step(
                    edited_mu=mu,
                    edited_vu=vu,
                    pre_state=pre_state,
                    post_state=post_state,
                    run_end_event=run_end_event,
                    button_found=button_found,
                )
                results.append(
                    {
                        "step": step_name,
                        "edited_inputs": {"Mu": mu, "Vu": vu},
                        "pre_click_shared_probe": dict(pre_state.get("browser_shared_probe") or {}),
                        "pre_click_active_beam_record_probe": dict(pre_state.get("active_beam_record_probe") or {}),
                        "pre_click_summary_probe": dict(pre_state.get("summary_state_probe") or {}),
                        "pre_click_auto_design_entry_before_reconcile": dict(
                            pre_state.get("auto_design_entry_probe_before_reconcile") or {}
                        ),
                        "pre_click_auto_design_entry_after_reconcile": dict(
                            pre_state.get("auto_design_entry_probe_after_reconcile") or {}
                        ),
                        "pre_click": _guidance_summary(pre_state),
                        "pre_click_guidance_actionable": guidance_actionable,
                        "pre_click_settle_meta": pre_settle_meta,
                        "button_found": button_found,
                        "click_error": click_error,
                        "post_click_shared_probe": dict(post_state.get("browser_shared_probe") or {}),
                        "post_click_active_beam_record_probe": dict(post_state.get("active_beam_record_probe") or {}),
                        "post_click_summary_probe": dict(post_state.get("summary_state_probe") or {}),
                        "post_click_auto_design_entry_before_reconcile": dict(
                            post_state.get("auto_design_entry_probe_before_reconcile") or {}
                        ),
                        "post_click_auto_design_entry_after_reconcile": dict(
                            post_state.get("auto_design_entry_probe_after_reconcile") or {}
                        ),
                        "post_click_auto_design_entry_after_run": dict(
                            post_state.get("auto_design_entry_probe_after_run") or {}
                        ),
                        "post_click": _guidance_summary(post_state),
                        "post_click_settle_meta": post_settle_meta,
                        "consumed_inputs_probe": dict(post_state.get("summary_state_probe") or {}),
                        "run_end_event": run_end_event,
                        "validation": validation,
                    }
                )

            print(json.dumps({"used_single_page_session": True, "steps": results}, indent=2))
            context.close()
            browser.close()
    finally:
        _terminate_process_tree(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
