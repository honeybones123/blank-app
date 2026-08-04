"""Browser/live Design Guide smoothness profile.

Measurement-only profiler. It does not implement bypasses, delete code, or
change product behaviour. The script opens the live Streamlit app in Chromium,
collects browser-visible milestone/layout data, and joins it with the app's
existing Browser state probes for render timing, speed profiling, candidate
evaluation, publication stamping, CTA binding, and card render-model bypasses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import (  # noqa: E402
    _load_browser_state,
    _page_cycle_churn_snapshot,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)
from tools.verification.verification_run_manifest import current_run_artifact  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "R1A_M300_V0"

AREA_SELECTORS: dict[str, list[str]] = {
    "inputs_heading": ["h1", "h2", "h3", "[role='heading']"],
    "nav_tabs": ["[role='tab']", "label", "button", "a"],
    "summary_cards": [".summary-check-card", ".summary-card-stack", "[data-testid*='summary' i]"],
    "batch_design": ["h1", "h2", "h3", "[data-testid='stExpander']", "[data-testid='stMarkdownContainer']"],
    "design_guide_card": ["[data-testid='design-guide-card']", ".fast-guidance-item", "[data-testid*='design-guide' i]"],
}


def _query(url: str, params: dict[str, Any]) -> str:
    return f"{str(url).rstrip('/')}/?{urlencode({k: v for k, v in params.items() if v is not None})}"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_artifact(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        path, payload = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "status": None, "payload": {}, "current_run": True}
        return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload, "current_run": True}
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _install_layout_probe(context) -> None:
    context.add_init_script(
        r"""
        (() => {
          window.__dgSmoothnessProbe = window.__dgSmoothnessProbe || {
            installedAt: Date.now(),
            layoutShiftTotal: 0,
            layoutShiftEntries: [],
            paintEntries: [],
            largestContentfulPaint: null,
            observerErrors: []
          };
          const probe = window.__dgSmoothnessProbe;
          try {
            const po = new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                if (entry.hadRecentInput) continue;
                probe.layoutShiftTotal += Number(entry.value || 0);
                probe.layoutShiftEntries.push({
                  value: Number(entry.value || 0),
                  startTime: Number(entry.startTime || 0),
                  sources: Array.from(entry.sources || []).slice(0, 6).map((source) => {
                    const node = source.node;
                    const rect = node && node.getBoundingClientRect ? node.getBoundingClientRect() : null;
                    return {
                      tag: node ? String(node.tagName || "").toLowerCase() : null,
                      text: node ? String(node.innerText || node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120) : null,
                      cls: node ? String(node.className || "").slice(0, 100) : null,
                      testid: node && node.getAttribute ? node.getAttribute("data-testid") : null,
                      rect: rect ? {x: rect.x, y: rect.y, width: rect.width, height: rect.height} : null
                    };
                  })
                });
              }
              if (probe.layoutShiftEntries.length > 200) {
                probe.layoutShiftEntries = probe.layoutShiftEntries.slice(-200);
              }
            });
            po.observe({type: "layout-shift", buffered: true});
            probe.layoutShiftObserverInstalled = true;
          } catch (err) {
            probe.observerErrors.push(`layout-shift:${err && err.message ? err.message : err}`);
          }
          try {
            const paint = new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                probe.paintEntries.push({name: entry.name, startTime: Number(entry.startTime || 0)});
              }
            });
            paint.observe({type: "paint", buffered: true});
            probe.paintObserverInstalled = true;
          } catch (err) {
            probe.observerErrors.push(`paint:${err && err.message ? err.message : err}`);
          }
          try {
            const lcp = new PerformanceObserver((list) => {
              const entries = list.getEntries();
              const last = entries[entries.length - 1];
              if (last) {
                probe.largestContentfulPaint = {
                  startTime: Number(last.startTime || 0),
                  size: Number(last.size || 0),
                  text: last.element ? String(last.element.innerText || last.element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120) : null
                };
              }
            });
            lcp.observe({type: "largest-contentful-paint", buffered: true});
            probe.lcpObserverInstalled = true;
          } catch (err) {
            probe.observerErrors.push(`lcp:${err && err.message ? err.message : err}`);
          }
        })();
        """
    )


def _browser_area_snapshot(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (areaSelectors) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                if (el.hasAttribute && (el.hasAttribute("hidden") || el.hasAttribute("inert") || el.closest("[inert]"))) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const hash = (value) => {
                const text = String(value || "");
                let h = 2166136261;
                for (let i = 0; i < text.length; i += 1) {
                  h ^= text.charCodeAt(i);
                  h = Math.imul(h, 16777619);
                }
                return (h >>> 0).toString(16);
              };
              const textMatches = {
                inputs_heading: /(Inputs|Start Your Design)/i,
                nav_tabs: /(Inputs|Bending|Shear|Deflection|Crack|Creep|Shrinkage|Batch)/i,
                summary_cards: /(Bending|Shear|Capacity|Utilisation|PASS|FAIL|summary)/i,
                batch_design: /Batch design/i,
                design_guide_card: /Design Guide|Run one-click|Apply|Strengthening|required|cleanup|safe/i
              };
              const findArea = (name, selectors) => {
                let candidates = [];
                for (const selector of selectors || []) {
                  try {
                    candidates = candidates.concat(Array.from(document.querySelectorAll(selector)));
                  } catch (_err) {}
                }
                const matched = candidates.find((el) => visible(el) && textMatches[name] && textMatches[name].test(clean(el.innerText || el.textContent)));
                const fallback = candidates.find(visible);
                const el = matched || fallback || null;
                if (!el) return {exists: false, visible: false};
                const rect = el.getBoundingClientRect();
                const text = clean(el.innerText || el.textContent).slice(0, 500);
                return {
                  exists: true,
                  visible: visible(el),
                  tag: String(el.tagName || "").toLowerCase(),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 120),
                  text_hash: hash(text),
                  text_sample: text.slice(0, 160),
                  rect: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom)
                  }
                };
              };
              const areas = {};
              for (const [name, selectors] of Object.entries(areaSelectors || {})) {
                areas[name] = findArea(name, selectors);
              }
              const probe = window.__dgSmoothnessProbe || {};
              return {
                timestamp_ms: Date.now(),
                performance_now_ms: Math.round(performance.now()),
                url: window.location.href,
                areas,
                layout_shift_total: Number(probe.layoutShiftTotal || 0),
                layout_shift_entries: Array.from(probe.layoutShiftEntries || []).slice(-30),
                paint_entries: Array.from(probe.paintEntries || []).slice(-20),
                largest_contentful_paint: probe.largestContentfulPaint || null,
                observer_errors: Array.from(probe.observerErrors || [])
              };
            }
            """,
            AREA_SELECTORS,
        )
        or {}
    )


def _visible_probe(page) -> dict[str, Any]:
    try:
        return dict(
            page.evaluate(
                r"""
                () => {
                  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
                  const visible = (el) => {
                    if (!el || !el.getBoundingClientRect) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
                  };
                  const count = (selector) => {
                    try { return Array.from(document.querySelectorAll(selector)).filter(visible).length; }
                    catch (_err) { return 0; }
                  };
                  const text = clean(document.body ? document.body.innerText : "");
                  return {
                    inputs_heading_visible: /(Inputs|Start Your Design)/i.test(text),
                    nav_tabs_visible: /(Bending|Shear|Deflection|Crack|Creep|Shrinkage)/i.test(text),
                    summary_cards_visible: count(".summary-check-card, .summary-card-stack, [data-testid*='summary' i]") > 0 || /(Bending|Shear).*(PASS|FAIL|Utilisation)/i.test(text),
                    batch_design_visible: /Batch design/i.test(text),
                    design_guide_shell_visible: /Design Guide/i.test(text),
                    rendered_design_guide_card_visible: count("[data-testid='design-guide-card'], .fast-guidance-item, [data-testid*='design-guide' i]") > 0,
                    body_text_length: text.length,
                    spinner_count: count('[data-testid="stSpinner"], [data-testid="stSkeleton"], [aria-busy="true"], [role="progressbar"]')
                  };
                }
                """
            )
            or {}
        )
    except Exception as exc:
        return {"visible_probe_error": f"{type(exc).__name__}: {exc}"}


def _click_live_design_guide_action(page) -> dict[str, Any]:
    """Click the current live Design Guide action button, if one is visible.

    The profiler should not assume one historical label. The rendered product
    may expose one-click, apply, or cleanup action wording depending on the
    selected family state. This stays browser/live and does not alter routing.
    """

    result = dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                if (el.disabled || el.getAttribute("aria-disabled") === "true") return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const actionPattern = /(Run one-click auto design|Apply recommendation|Apply Design Guide|Apply selected|Apply repair|Apply cleanup|Use this design|Update design|Apply)/i;
              const rejectPattern = /(debug|show|hide|download|export|copy|reset|clear|reload|browse|select|previous|next|beam\/reo\/load edits)$/i;
              const buttons = Array.from(document.querySelectorAll("button,[role='button']"))
                .map((el) => ({el, text: clean(el.innerText || el.textContent || el.getAttribute("aria-label"))}))
                .filter((item) => visible(item.el) && actionPattern.test(item.text) && !rejectPattern.test(item.text));
              const preferred = buttons.find((item) => /Run one-click auto design/i.test(item.text))
                || buttons.find((item) => /Apply/i.test(item.text))
                || buttons[0];
              if (!preferred) {
                return {
                  clicked: false,
                  reason: "no_visible_design_guide_action_button",
                  visible_button_texts: Array.from(document.querySelectorAll("button,[role='button']"))
                    .filter((el) => {
                      const style = window.getComputedStyle(el);
                      const rect = el.getBoundingClientRect();
                      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 2 && rect.height > 2;
                    })
                    .map((el) => clean(el.innerText || el.textContent || el.getAttribute("aria-label")))
                    .filter(Boolean)
                    .slice(0, 30)
                };
              }
              preferred.el.click();
              return {clicked: true, button_text: preferred.text, candidate_count: buttons.length};
            }
            """
        )
        or {}
    )
    if not result.get("clicked"):
        raise PlaywrightTimeoutError(str(result))
    page.wait_for_timeout(1200)
    return result


def _debug_bundle(state: dict[str, Any]) -> dict[str, Any]:
    return dict((dict(state.get("design_guide_probe") or {})).get("debug_bundle") or {})


def _final_publication_ready(state: dict[str, Any]) -> bool:
    bundle = _debug_bundle(state)
    payload = dict(bundle.get("final_publication_verifier_payload") or {})
    hashes = dict(state.get("final_publication_hashes") or {})
    return bool(
        payload.get("publication_hash")
        or bundle.get("final_publication_publication_hash")
        or bundle.get("final_publication_authority_hash")
        or hashes.get("publication_hash")
        or hashes.get("authority_hash")
    )


def _card_render_model_ready(state: dict[str, Any]) -> bool:
    bundle = _debug_bundle(state)
    hashes = dict(state.get("final_publication_hashes") or {})
    return bool(
        bundle.get("actual_card_render_probe")
        or bundle.get("final_publication_display_hash")
        or bundle.get("final_publication_card_render_model_bypass_decisions")
        or hashes.get("display_hash")
    )


def _wait_until(page, condition, *, timeout_s: float = 45.0, interval_s: float = 0.25) -> tuple[int | None, dict[str, Any], dict[str, Any]]:
    start = time.perf_counter()
    last_visible: dict[str, Any] = {}
    last_state: dict[str, Any] = {}
    while time.perf_counter() - start <= timeout_s:
        last_visible = _visible_probe(page)
        try:
            last_state = _load_browser_state(page, timeout_s=1.0)
        except Exception:
            last_state = {}
        try:
            if bool(condition(last_visible, last_state)):
                return int((time.perf_counter() - start) * 1000), last_visible, last_state
        except Exception:
            pass
        time.sleep(interval_s)
    return None, last_visible, last_state


def _extract_latest_design_guide_timing(state: dict[str, Any]) -> dict[str, Any]:
    render = dict(state.get("render_timing_probe") or {})
    events = [dict(item) for item in list(render.get("events") or []) if isinstance(item, dict)]
    dg_end = None
    final_pub = None
    card_model = None
    summary_render = None
    for event in events:
        name = str(event.get("name") or "")
        meta = dict(event.get("meta") or {})
        if name == "inputs_page.design_guide_build.end":
            dg_end = event
        if "summary_render" in name:
            summary_render = event
        if (
            "final_publication" in name
            or meta.get("final_publication_authority_hash")
            or meta.get("final_publication_display_hash")
        ):
            final_pub = event
        if "card_render_model" in name or meta.get("card_render_model_bypassed") is not None:
            card_model = event
    return {
        "rerun_seq": render.get("rerun_seq"),
        "event_count": render.get("event_count"),
        "trace_path": render.get("trace_path"),
        "design_guide_build_end": dg_end,
        "summary_render": summary_render,
        "final_publication_event": final_pub,
        "card_render_model_event": card_model,
        "events_tail": events[-25:],
    }


def _extract_dg_speed_diag(state: dict[str, Any]) -> dict[str, Any]:
    latest = _extract_latest_design_guide_timing(state)
    event = dict(latest.get("design_guide_build_end") or {})
    meta = dict(event.get("meta") or {})
    return dict(meta.get("dg_speed_diag") or {})


def _extract_counter_metrics(state: dict[str, Any]) -> dict[str, Any]:
    bundle = _debug_bundle(state)
    debug_probe = dict(state.get("browser_debug_probe") or {})
    dg_speed = _extract_dg_speed_diag(state)
    speed = dict(state.get("speed_profile_probe") or {})
    ux = dict(state.get("ux_latency_probe") or {})
    candidate_eval = {
        "count": int(dg_speed.get("evaluate_candidate_full_count") or 0),
        "cache_hits": int(dg_speed.get("evaluate_candidate_full_cache_hit_count") or 0),
        "cache_misses": int(dg_speed.get("evaluate_candidate_full_cache_miss_count") or 0),
        "total_ms": float(dg_speed.get("evaluate_candidate_full_total_ms") or 0.0),
        "repeated_fingerprints": dict(dg_speed.get("evaluate_candidate_full_fingerprints") or {}),
    }
    duplicate_decisions = dict(bundle.get("final_publication_duplicate_stamp_bypass_decisions_by_candidate") or {})
    duplicate_rows = []
    for candidate, rows_by_instance in duplicate_decisions.items():
        if not isinstance(rows_by_instance, dict):
            continue
        for instance_key, row in rows_by_instance.items():
            if isinstance(row, dict):
                duplicate_rows.append(
                    {
                        "candidate": candidate,
                        "instance_key": instance_key,
                        **row,
                    }
                )
    card_decisions = dict(bundle.get("final_publication_card_render_model_bypass_decisions") or {})
    card_rows = []
    for key, row in card_decisions.items():
        if isinstance(row, dict):
            card_rows.append({"cache_key": key, **row})
    settle_gate = dict(
        debug_probe.get("design_guide_settle_gate")
        or bundle.get("design_guide_settle_gate")
        or state.get("_design_guide_family_settle_gate")
        or {}
    )
    duplicate_stamp_rebuild_count = sum(1 for row in duplicate_rows if not bool(row.get("bypassed")))
    button_contract = dict(
        bundle.get("displayed_primary_button_contract")
        or bundle.get("primary_button_contract")
        or bundle.get("button_contract")
        or {}
    )
    controller_parity = dict(bundle.get("design_guide_controller_trace_only_parity") or {})
    legacy_publication_hash = (
        dict(bundle.get("final_publication_verifier_payload") or {}).get("publication_hash")
        or bundle.get("final_publication_publication_hash")
        or bundle.get("final_publication_authority_hash")
    )
    controller_publication_hash = (
        controller_parity.get("controller_publication_hash")
        or controller_parity.get("live_publication_hash")
    )
    controller_display_hash = controller_parity.get("controller_display_hash")
    controller_cta_hash = controller_parity.get("controller_cta_hash")
    return {
        "dg_speed_diag": dg_speed,
        "candidate_evaluation": candidate_eval,
        "speed_profile_last_run_top": list(speed.get("last_run_sections") or [])[:15],
        "speed_profile_all_top": list(speed.get("sections") or [])[:15],
        "model_diagram_render_reuse_trace": dict(debug_probe.get("inputs_model_diagram_render_reuse_trace") or {}),
        "stable_render_reuse_trace": dict(debug_probe.get("inputs_stable_render_reuse_trace") or {}),
        "summary_card_html_bypass_debug": dict(
            debug_probe.get("final_publication_summary_card_html_bypass_debug") or {}
        ),
        "first_paint_summary_reuse_debug": dict(
            debug_probe.get("inputs_first_paint_cached_summary_reuse_debug") or {}
        ),
        "summary_final_render_skip_debug": dict(
            debug_probe.get("inputs_summary_final_render_skip_debug") or {}
        ),
        "inputs_dirty_cache_probe": dict(
            debug_probe.get("inputs_dirty_cache_probe") or {}
        ),
        "ux_counts": dict(ux.get("counts") or {}),
        "ux_recent_event_count": len(list(ux.get("recent_events") or [])),
        "rerun_trigger_events": (
            list(debug_probe.get("inputs_rerun_trigger_events") or [])
            + list(debug_probe.get("ssl_rerun_triggers") or [])
        )[-24:],
        "publication_rebuild_count": int(settle_gate.get("expensive_publication_count") or 0),
        "skipped_publication_rebuild_count": int(settle_gate.get("skipped_expensive_publication_count") or 0),
        "duplicate_publication_stamp_rebuild_count": duplicate_stamp_rebuild_count,
        "publication_stamp_bypass_count": sum(1 for row in duplicate_rows if bool(row.get("bypassed"))),
        "publication_stamp_decisions": duplicate_rows,
        "card_render_model_rebuild_count": sum(1 for row in card_rows if not bool(row.get("card_render_model_bypassed"))),
        "card_render_model_bypass_count": sum(1 for row in card_rows if bool(row.get("card_render_model_bypassed"))),
        "card_render_model_decisions": card_rows,
        "cta_apply_binding_count": 1 if button_contract else 0,
        "button_contract_hash": _stable_hash(button_contract) if button_contract else None,
        "apply_payload_hash": _stable_hash(state.get("design_guide_primary_apply_payload") or {}),
        "session_debug_stamp_field_count": len([key for key in bundle if "final_publication" in str(key)]),
        "final_publication_hash": controller_publication_hash or legacy_publication_hash,
        "final_publication_hash_source": (
            "DesignGuideController.trace_only"
            if controller_publication_hash
            else "legacy_final_publication_debug"
        ),
        "legacy_final_publication_hash": legacy_publication_hash,
        "controller_publication_hash": controller_publication_hash,
        "final_publication_display_hash": controller_display_hash or bundle.get("final_publication_display_hash"),
        "final_publication_display_hash_source": (
            "DesignGuideController.trace_only"
            if controller_display_hash
            else "legacy_final_publication_debug"
        ),
        "legacy_final_publication_display_hash": bundle.get("final_publication_display_hash"),
        "controller_display_hash": controller_display_hash,
        "final_publication_cta_hash": controller_cta_hash or bundle.get("final_publication_cta_hash"),
        "final_publication_cta_hash_source": (
            "DesignGuideController.trace_only"
            if controller_cta_hash
            else "legacy_final_publication_debug"
        ),
        "legacy_final_publication_cta_hash": bundle.get("final_publication_cta_hash"),
        "controller_cta_hash": controller_cta_hash,
    }


def _layout_delta(first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    first_areas = dict(first.get("areas") or {})
    last_areas = dict(last.get("areas") or {})
    for name in AREA_SELECTORS:
        before = dict(first_areas.get(name) or {})
        after = dict(last_areas.get(name) or {})
        brect = dict(before.get("rect") or {})
        arect = dict(after.get("rect") or {})
        if not brect or not arect:
            out[name] = {"measured": False, "reason": "area_missing_before_or_after"}
            continue
        top_delta = abs(float(arect.get("top") or 0) - float(brect.get("top") or 0))
        height_delta = abs(float(arect.get("height") or 0) - float(brect.get("height") or 0))
        width_delta = abs(float(arect.get("width") or 0) - float(brect.get("width") or 0))
        out[name] = {
            "measured": True,
            "top_delta_px": round(top_delta, 2),
            "height_delta_px": round(height_delta, 2),
            "width_delta_px": round(width_delta, 2),
            "text_hash_changed": before.get("text_hash") != after.get("text_hash"),
            "before": before,
            "after": after,
        }
    return out


def _run_live_scenario(page, *, scenario_id: str, action: str, base_url: str, recipe: str, timeout_s: float) -> dict[str, Any]:
    started = time.perf_counter()
    scenario_deadline = started + max(1.0, float(timeout_s))
    if action == "goto":
        page.goto(_query(base_url, {"page": "inputs", "browser_recipe": recipe}), wait_until="domcontentloaded", timeout=90_000)
    elif action == "reload":
        page.reload(wait_until="domcontentloaded", timeout=90_000)
    elif action == "click_apply":
        clicked_meta = _click_live_design_guide_action(page)
    else:
        raise ValueError(f"unknown scenario action {action!r}")

    # Install the churn observer as early as possible after navigation/click.
    early_area = _browser_area_snapshot(page)
    try:
        _page_cycle_churn_snapshot(page, slug="inputs", detail=True)
    except Exception:
        pass

    milestones: dict[str, Any] = {}
    milestone_specs = [
        ("inputs_heading", lambda visible, state: bool(visible.get("inputs_heading_visible"))),
        ("nav_tabs", lambda visible, state: bool(visible.get("nav_tabs_visible"))),
        ("summary_cards", lambda visible, state: bool(visible.get("summary_cards_visible"))),
        ("batch_design", lambda visible, state: bool(visible.get("batch_design_visible"))),
        ("design_guide_shell", lambda visible, state: bool(visible.get("design_guide_shell_visible"))),
        ("final_design_guide_publication", lambda visible, state: _final_publication_ready(state)),
        (
            "card_render_model",
            lambda visible, state: _card_render_model_ready(state)
            or (
                bool(visible.get("rendered_design_guide_card_visible"))
                and _final_publication_ready(state)
            ),
        ),
        ("rendered_design_guide_card", lambda visible, state: bool(visible.get("rendered_design_guide_card_visible"))),
    ]
    last_state: dict[str, Any] = {}
    for name, predicate in milestone_specs:
        remaining_s = scenario_deadline - time.perf_counter()
        if remaining_s <= 0:
            elapsed_ms, visible, state = None, _visible_probe(page), {}
        else:
            elapsed_ms, visible, state = _wait_until(
                page,
                predicate,
                timeout_s=min(max(0.25, remaining_s), 10.0),
            )
        milestones[name] = {
            "elapsed_ms": elapsed_ms,
            "visible_probe": visible,
            "state_available": bool(state),
            "timed_out": elapsed_ms is None,
        }
        if state:
            last_state = state

    # Let late browser/layout mutations land, then sample final state.
    page.wait_for_timeout(800)
    final_area = _browser_area_snapshot(page)
    try:
        layout_shift_delta = max(
            0.0,
            float(final_area.get("layout_shift_total") or 0.0)
            - float(early_area.get("layout_shift_total") or 0.0),
        )
    except Exception:
        layout_shift_delta = None
    churn_snapshot = _page_cycle_churn_snapshot(page, slug="inputs", detail=True)
    try:
        final_state = _load_browser_state(page, timeout_s=3.0)
    except Exception:
        final_state = last_state
    timing = _extract_latest_design_guide_timing(final_state)
    counters = _extract_counter_metrics(final_state)
    scenario_elapsed_ms = int((time.perf_counter() - started) * 1000)
    rerun_seq = timing.get("rerun_seq")
    return {
        "scenario_id": scenario_id,
        "action": action,
        "click_meta": locals().get("clicked_meta"),
        "elapsed_ms": scenario_elapsed_ms,
        "rerun_seq": rerun_seq,
        "milestones": milestones,
        "timing": timing,
        "counters": counters,
        "layout": {
            "early_area_snapshot": early_area,
            "final_area_snapshot": final_area,
            "area_deltas": _layout_delta(early_area, final_area),
            "layout_shift_total": layout_shift_delta,
            "layout_shift_cumulative_initial": early_area.get("layout_shift_total"),
            "layout_shift_cumulative_final": final_area.get("layout_shift_total"),
            "layout_shift_entries_tail": list(final_area.get("layout_shift_entries") or [])[-20:],
        },
        "churn": {
            "mutation_count_total": churn_snapshot.get("mutation_count_total"),
            "last_mutation_batch_size": churn_snapshot.get("last_mutation_batch_size"),
            "mutation_recent_batches": list(churn_snapshot.get("mutation_recent_batches") or [])[-8:],
            "mutation_top_attribution": list(churn_snapshot.get("mutation_top_attribution") or [])[:12],
            "dom_node_count": churn_snapshot.get("dom_node_count"),
            "streamlit_block_count": churn_snapshot.get("streamlit_block_count"),
        },
        "snapshot_hash": _stable_hash(
            {
                "scenario_id": scenario_id,
                "milestones": milestones,
                "counters": counters,
                "layout": final_area,
                "churn": {
                    "mutation_count_total": churn_snapshot.get("mutation_count_total"),
                    "last_mutation_batch_size": churn_snapshot.get("last_mutation_batch_size"),
                },
            }
        ),
    }


def _metric_ms(row: dict[str, Any], milestone: str) -> float:
    value = ((row.get("milestones") or {}).get(milestone) or {}).get("elapsed_ms")
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _classify_hotspots(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stable_rows = [row for row in scenarios if row.get("scenario_id") in {"stable_no_input_reload_1", "stable_no_input_reload_2"}]
    post_click_rows = [row for row in scenarios if row.get("scenario_id") == "post_click_apply"]
    all_rows = list(scenarios)

    candidate_count = sum(int(((row.get("counters") or {}).get("candidate_evaluation") or {}).get("count") or 0) for row in all_rows)
    candidate_misses = sum(int(((row.get("counters") or {}).get("candidate_evaluation") or {}).get("cache_misses") or 0) for row in all_rows)
    candidate_ms = sum(float(((row.get("counters") or {}).get("candidate_evaluation") or {}).get("total_ms") or 0.0) for row in all_rows)
    browser_probe_candidate_ms = 0.0
    browser_probe_candidate_sections = []
    for row in all_rows:
        for section in list(((row.get("counters") or {}).get("speed_profile_last_run_top") or [])):
            if not isinstance(section, dict):
                continue
            name = str(section.get("name") or "")
            if not name.startswith("browser_probe."):
                continue
            try:
                section_ms = float(section.get("total_ms") or 0.0)
            except Exception:
                section_ms = 0.0
            if section_ms <= 0:
                continue
            browser_probe_candidate_ms += section_ms
            if len(browser_probe_candidate_sections) < 8:
                browser_probe_candidate_sections.append(
                    {
                        "scenario_id": row.get("scenario_id"),
                        "name": name,
                        "total_ms": round(section_ms, 3),
                        "count": section.get("count"),
                    }
                )
    product_candidate_ms = max(0.0, candidate_ms - browser_probe_candidate_ms)
    candidate_probe_dominated = bool(browser_probe_candidate_ms > 0 and browser_probe_candidate_ms >= candidate_ms * 0.5)
    candidate_product_hotspot = bool(product_candidate_ms > 0.0 or candidate_misses > 0)
    publication_rebuilds = sum(int((row.get("counters") or {}).get("publication_rebuild_count") or 0) for row in all_rows)
    duplicate_publication_stamp_rebuilds = sum(
        int((row.get("counters") or {}).get("duplicate_publication_stamp_rebuild_count") or 0)
        for row in all_rows
    )
    publication_stamp_bypasses = sum(
        int((row.get("counters") or {}).get("publication_stamp_bypass_count") or 0)
        for row in all_rows
    )
    card_rebuilds = sum(int((row.get("counters") or {}).get("card_render_model_rebuild_count") or 0) for row in all_rows)
    debug_stamp_field_count = sum(
        int((row.get("counters") or {}).get("session_debug_stamp_field_count") or 0)
        for row in all_rows
    )
    stable_duplicate_publication_stamp_rebuilds = sum(
        int((row.get("counters") or {}).get("duplicate_publication_stamp_rebuild_count") or 0)
        for row in stable_rows
    )
    post_click_duplicate_publication_stamp_rebuilds = sum(
        int((row.get("counters") or {}).get("duplicate_publication_stamp_rebuild_count") or 0)
        for row in post_click_rows
    )
    avg_dg_card_ms = (
        sum(_metric_ms(row, "rendered_design_guide_card") for row in stable_rows) / len(stable_rows)
        if stable_rows
        else 0.0
    )
    avg_shell_gap_ms = (
        sum(max(0.0, _metric_ms(row, "rendered_design_guide_card") - _metric_ms(row, "design_guide_shell")) for row in stable_rows)
        / len(stable_rows)
        if stable_rows
        else 0.0
    )
    max_cls = max([float(((row.get("layout") or {}).get("layout_shift_total") or 0.0)) for row in all_rows] or [0.0])
    max_mutation = max([int(((row.get("churn") or {}).get("last_mutation_batch_size") or 0)) for row in all_rows] or [0])
    reruns = len({row.get("rerun_seq") for row in all_rows if row.get("rerun_seq") is not None})
    post_click_elapsed = max([float(row.get("elapsed_ms") or 0.0) for row in post_click_rows] or [0.0])
    rerun_trigger_events = []
    for row in all_rows:
        for event in list(((row.get("counters") or {}).get("rerun_trigger_events") or [])):
            if isinstance(event, dict):
                name = str(event.get("event") or "").strip()
            else:
                name = str(event or "").strip()
            if name and name not in rerun_trigger_events:
                rerun_trigger_events.append(name)
    post_apply_state_profile = _latest_artifact("design_guide_same_session_post_apply_state_write_profile")
    post_apply_state_payload = dict(post_apply_state_profile.get("payload") or {})
    post_apply_state_classification = dict(post_apply_state_payload.get("classification") or {})
    post_apply_state_decision = str(post_apply_state_classification.get("decision") or "")
    post_apply_rerun_already_classified = post_apply_state_decision in {
        "NO_PATCH_DEBUG_ONLY_STAMP_DELTA",
        "POST_APPLY_REFRESH_QUEUE_CONSUMED_NO_PATCH",
    }
    rerun_score = round(reruns * 40 + post_click_elapsed * 0.1, 3)
    if post_apply_rerun_already_classified:
        rerun_score = 0.0

    hotspots = [
        {
            "class": "B",
            "name": "candidate evaluation/search",
            "score": round(
                (
                    product_candidate_ms
                    + candidate_misses * 50
                    + candidate_count * (1 if candidate_probe_dominated else 5)
                )
                if candidate_product_hotspot
                else 0.0,
                3,
            ),
            "evidence": {
                "candidate_evaluation_count": candidate_count,
                "candidate_cache_misses": candidate_misses,
                "candidate_total_ms": round(candidate_ms, 3),
                "product_candidate_total_ms": round(product_candidate_ms, 3),
                "browser_probe_candidate_total_ms": round(browser_probe_candidate_ms, 3),
                "browser_probe_dominated": candidate_probe_dominated,
                "product_hotspot": candidate_product_hotspot,
                "browser_probe_sections": browser_probe_candidate_sections,
            },
        },
        {
            "class": "C",
            "name": "publication/card rebuild",
            "score": round(publication_rebuilds * 80 + card_rebuilds * 120 + avg_dg_card_ms * 0.25, 3),
            "evidence": {
                "publication_rebuild_count": publication_rebuilds,
                "card_render_model_rebuild_count": card_rebuilds,
                "avg_stable_time_to_rendered_design_guide_card_ms": round(avg_dg_card_ms, 3),
            },
        },
        {
            "class": "D",
            "name": "session/debug stamping",
            "score": round(stable_duplicate_publication_stamp_rebuilds * 25, 3),
            "evidence": {
                "debug_publication_stamp_rebuild_decisions": duplicate_publication_stamp_rebuilds,
                "stable_no_input_debug_publication_stamp_rebuild_decisions": stable_duplicate_publication_stamp_rebuilds,
                "post_click_debug_publication_stamp_rebuild_decisions": post_click_duplicate_publication_stamp_rebuilds,
                "debug_publication_stamp_bypass_decisions": publication_stamp_bypasses,
                "session_debug_stamp_field_count": debug_stamp_field_count,
                "field_count_is_not_churn": True,
            },
        },
        {
            "class": "E",
            "name": "layout placeholder/first-paint gap",
            "score": round(max_cls * 4000 + avg_shell_gap_ms * 0.6 + max_mutation * 0.5, 3),
            "evidence": {
                "max_layout_shift_total": round(max_cls, 6),
                "avg_shell_to_card_gap_ms": round(avg_shell_gap_ms, 3),
                "largest_last_mutation_batch_size": max_mutation,
            },
        },
        {
            "class": "A",
            "name": "rerun trigger",
            "score": rerun_score,
            "evidence": {
                "distinct_rerun_seq_count": reruns,
                "post_click_elapsed_ms": round(post_click_elapsed, 3),
                "rerun_trigger_events": rerun_trigger_events,
                "post_apply_state_write_profile_decision": post_apply_state_decision or None,
                "post_apply_rerun_already_classified": bool(post_apply_rerun_already_classified),
            },
        },
    ]
    hotspots.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("name") or "")))
    return hotspots


def _recommended_fix(top_hotspots: list[dict[str, Any]]) -> str:
    if not top_hotspots:
        return "No measured hotspot was strong enough to recommend a fix; rerun the browser/live profile with a headed browser."
    top = top_hotspots[0]
    cls = top.get("class")
    if cls == "B":
        evidence = dict(top.get("evidence") or {})
        if bool(evidence.get("browser_probe_dominated")):
            return (
                "Candidate evaluation is dominated by browser/proof probe work; do not add a product cache yet. "
                "Create a focused browser-probe overhead proof and then target the highest non-probe hotspot."
            )
        return (
            "Add proof-only readiness for no-input-change candidate evaluation/search reuse keyed by the existing "
            "guidance/input fingerprint before implementing any cache or bypass."
        )
    if cls == "C":
        return (
            "Create a targeted readiness snapshot for the remaining publication/card rebuild source with the highest "
            "measured rebuild count, keyed by the existing publication/display hash."
        )
    if cls == "D":
        return (
            "Add a narrow readiness snapshot for duplicate session/debug payload stamping keyed by publication_hash; "
            "keep debug mode force-rebuild semantics."
        )
    if cls == "E":
        latest_source = _latest_artifact("design_guide_streamlit_layout_shift_source_node")
        latest_dom_gap = _latest_artifact("design_guide_browser_dom_gap_source")
        latest_gap_matrix = _latest_artifact("design_guide_layout_gap_reproduction_matrix")
        latest_summary_height = _latest_artifact("design_guide_summary_first_paint_shell_height_readiness")
        latest_second_rerun = _latest_artifact("design_guide_second_same_session_no_change_rerun_profile")
        source_summary = dict(dict(latest_source.get("payload") or {}).get("summary") or {})
        dom_payload = dict(latest_dom_gap.get("payload") or {})
        dom_classification = dict(dom_payload.get("classification") or {})
        matrix_payload = dict(latest_gap_matrix.get("payload") or {})
        matrix_classification = dict(matrix_payload.get("classification") or {})
        matrix_decision = str(matrix_payload.get("decision") or matrix_classification.get("decision") or "")
        matrix_safe_patch_count = int(
            matrix_payload.get("safe_patch_case_count")
            or matrix_classification.get("safe_patch_case_count")
            or 0
        )
        summary_height_payload = dict(latest_summary_height.get("payload") or {})
        summary_height_summary = dict(summary_height_payload.get("summary") or {})
        summary_height_classification = dict(summary_height_payload.get("classification") or {})
        second_payload = dict(latest_second_rerun.get("payload") or {})
        second_classification = dict(second_payload.get("classification") or {})
        second_sources = set(str(item) for item in second_classification.get("likely_sources") or [])
        source_target = str(source_summary.get("candidate_patch_target") or "")
        dom_result = str(
            dom_payload.get("audit_result")
            or dom_classification.get("audit_result")
            or ""
        )
        dom_diagnostics = set(str(item) for item in dom_classification.get("diagnostics") or [])
        summary_height_decision = str(
            summary_height_payload.get("decision")
            or summary_height_summary.get("decision")
            or summary_height_classification.get("decision")
            or ""
        )
        if (
            dom_result == "DOWNSTREAM_DESIGN_GUIDE_NOT_MATERIALIZED"
            or "design_guide_slot_or_card_not_materialized_after_summary" in dom_diagnostics
        ):
            return (
                "Layout remains the largest measured class, but the latest DOM-gap proof shows the downstream "
                "Design Guide slot/card is not materialized after the summary. Do not patch CSS or add a render "
                "reuse cache yet; trace the live render eligibility/materialization gate for non-test pages."
            )
        if (
            source_target in {"unreproduced_or_unknown", "unproven_streamlit_wrapper", "streamlit_chrome"}
            and dom_result in {"NO_REAL_DOM_GAP_SOURCE_DETECTED", "INSUFFICIENT_DOM_TARGETS_FOR_GAP_MEASUREMENT"}
            and matrix_decision in {"", "DOWNSTREAM_PANELS_NOT_MATERIALIZED_IN_MATRIX"}
            and matrix_safe_patch_count == 0
            and summary_height_decision == "NO_MATERIAL_HEIGHT_MISMATCH"
        ):
            if "second_same_session_no_major_rebuild_source_detected" in second_sources:
                return (
                    "Layout remains the largest measured class, but source-node, DOM-gap, shell-height, "
                    "and matrix proofs do not identify a safe app-owned CSS/layout patch. The second "
                    "same-session no-change rerun also found no remaining non-layout rebuild source. "
                    "Next evidence should come from a headed/user-specific reproduction of the visible gap."
                )
            return (
                "Layout remains the largest measured class, but the focused source-node, DOM-gap, "
                "and shell-height proofs do not identify a safe app-owned CSS/layout patch. Capture a "
                "headed user-specific reproduction before changing layout; otherwise move to the next "
                "non-layout hotspot."
            )
        return (
            "Profile the first-paint placeholder and Design Guide card container heights; the first fix should reserve "
            "stable space for the shell/card rather than changing publication truth."
        )
    if cls == "A":
        return (
            "Audit the rerun trigger around Apply/no-input reruns; keep apply routing unchanged and first prove which "
            "state write causes the extra rerun."
        )
    return "Create a focused proof snapshot for the top unknown browser/render hotspot before changing code."


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Browser/Live Smoothness Profile",
        "",
        f"- Status: `{payload['status']}`",
        f"- Recipe: `{payload['recipe']}`",
        f"- Browser/live mode: `{payload['browser_live_mode']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Action | Rerun seq | Inputs heading ms | Summary cards ms | DG shell ms | Publication ms | Card model ms | Rendered DG card ms | Candidate evals | Pub rebuilds | Card rebuilds | Layout shift |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("scenarios") or []:
        counters = row.get("counters") or {}
        candidate = counters.get("candidate_evaluation") or {}
        layout = row.get("layout") or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("scenario_id")),
                    str(row.get("action")),
                    str(row.get("rerun_seq")),
                    str(((row.get("milestones") or {}).get("inputs_heading") or {}).get("elapsed_ms")),
                    str(((row.get("milestones") or {}).get("summary_cards") or {}).get("elapsed_ms")),
                    str(((row.get("milestones") or {}).get("design_guide_shell") or {}).get("elapsed_ms")),
                    str(((row.get("milestones") or {}).get("final_design_guide_publication") or {}).get("elapsed_ms")),
                    str(((row.get("milestones") or {}).get("card_render_model") or {}).get("elapsed_ms")),
                    str(((row.get("milestones") or {}).get("rendered_design_guide_card") or {}).get("elapsed_ms")),
                    str(candidate.get("count")),
                    str(counters.get("publication_rebuild_count")),
                    str(counters.get("card_render_model_rebuild_count")),
                    str(layout.get("layout_shift_total")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Top Hotspots", ""])
    for idx, item in enumerate(payload.get("top_hotspots") or [], start=1):
        lines.append(
            f"{idx}. `{item.get('class')}` {item.get('name')} - score `{item.get('score')}`; evidence `{json.dumps(item.get('evidence'), sort_keys=True)}`"
        )
    lines.extend(
        [
            "",
            "## Recommended First Fix",
            "",
            str(payload.get("recommended_first_fix") or ""),
            "",
            "## Guard Results",
            "",
        ]
    )
    for name, artifact in (payload.get("supporting_artifacts") or {}).items():
        lines.append(f"- {name}: found `{artifact.get('found')}`, status `{artifact.get('status')}`, path `{artifact.get('path')}`")
    lines.extend(["", "## Notes", ""])
    lines.append("This profiler is measurement-only. It does not prove new bypass safety and does not implement optimizations.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8526)
    parser.add_argument("--base-url", default=None, help="Use an already-running app instead of starting Streamlit.")
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime_stamp()
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    process: subprocess.Popen | None = None
    scenarios: list[dict[str, Any]] = []
    browser_live_mode = "started_streamlit"
    errors: list[str] = []

    try:
        if args.base_url:
            browser_live_mode = "attached_to_existing_streamlit"
            _wait_for_http(base_url)
        else:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["CODEX_RENDER_TIMING_TRACE"] = "1"
            os.environ["AUTO_DESIGN_SPEED_PROFILE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1440, "height": 1100})
            _install_layout_probe(context)
            page = context.new_page()
            page.set_default_timeout(30_000)
            scenarios.append(
                _run_live_scenario(
                    page,
                    scenario_id="initial_recipe_load",
                    action="goto",
                    base_url=base_url,
                    recipe=args.recipe,
                    timeout_s=args.timeout_s,
                )
            )
            scenarios.append(
                _run_live_scenario(
                    page,
                    scenario_id="stable_no_input_reload_1",
                    action="reload",
                    base_url=base_url,
                    recipe=args.recipe,
                    timeout_s=args.timeout_s,
                )
            )
            scenarios.append(
                _run_live_scenario(
                    page,
                    scenario_id="stable_no_input_reload_2",
                    action="reload",
                    base_url=base_url,
                    recipe=args.recipe,
                    timeout_s=args.timeout_s,
                )
            )
            try:
                scenarios.append(
                    _run_live_scenario(
                        page,
                        scenario_id="post_click_apply",
                        action="click_apply",
                        base_url=base_url,
                        recipe=args.recipe,
                        timeout_s=args.timeout_s,
                    )
                )
            except PlaywrightTimeoutError as exc:
                no_action_available = "no_visible_design_guide_action_button" in str(exc)
                if not no_action_available:
                    errors.append(f"post_click_apply_unavailable:{type(exc).__name__}:{exc}")
                scenarios.append(
                    {
                        "scenario_id": "post_click_apply",
                        "action": "click_apply",
                        "skipped": True,
                        "skip_reason": (
                            "No Design Guide action CTA is available in this terminal live state."
                            if no_action_available
                            else "Run one-click auto design button not visible/actionable in this live state."
                        ),
                        "post_click_apply_applicable": not no_action_available,
                        "skip_error": f"{type(exc).__name__}:{exc}",
                    }
                )
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    top_hotspots = _classify_hotspots([row for row in scenarios if not row.get("skipped")])
    supporting_artifacts = {
        "duplicate_publication_stamp_bypass_live_impact": _latest_artifact(
            "design_guide_duplicate_publication_stamp_bypass_live_impact"
        ),
        "card_render_model_bypass_live_impact": _latest_artifact(
            "design_guide_card_render_model_bypass_live_impact"
        ),
        "same_session_post_apply_state_write_profile": _latest_artifact(
            "design_guide_same_session_post_apply_state_write_profile"
        ),
        "layout_shift_source_node": _latest_artifact(
            "design_guide_streamlit_layout_shift_source_node"
        ),
        "browser_dom_gap_source": _latest_artifact("design_guide_browser_dom_gap_source"),
        "layout_gap_reproduction_matrix": _latest_artifact(
            "design_guide_layout_gap_reproduction_matrix"
        ),
        "summary_first_paint_shell_height_readiness": _latest_artifact(
            "design_guide_summary_first_paint_shell_height_readiness"
        ),
        "second_same_session_no_change_rerun_profile": _latest_artifact(
            "design_guide_second_same_session_no_change_rerun_profile"
        ),
        "design_guide_independence_lock": _latest_artifact("design_guide_independence_lock"),
        "render_bridge_lock": _latest_artifact("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest_artifact(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
    }
    non_post_click_skips = [
        row for row in scenarios if row.get("scenario_id") != "post_click_apply" and row.get("skipped")
    ]
    status = "PASS" if scenarios and not non_post_click_skips and not errors else "PARTIAL"
    payload = {
        "schema": "design_guide_browser_live_smoothness_profile.v1",
        "status": status,
        "created_at": stamp,
        "recipe": args.recipe,
        "base_url": base_url,
        "browser_live_mode": browser_live_mode,
        "product_behaviour_changed": False,
        "new_bypasses_implemented": False,
        "code_deleted": False,
        "scenarios": scenarios,
        "post_click_apply_applicable": not any(
            row.get("scenario_id") == "post_click_apply"
            and row.get("skipped")
            and row.get("post_click_apply_applicable") is False
            for row in scenarios
        ),
        "top_hotspots": top_hotspots[:3],
        "all_hotspot_scores": top_hotspots,
        "recommended_first_fix": _recommended_fix(top_hotspots),
        "supporting_artifacts": supporting_artifacts,
        "errors": errors,
        "profile_hash": _stable_hash(
            {
                "recipe": args.recipe,
                "scenarios": scenarios,
                "top_hotspots": top_hotspots[:3],
                "errors": errors,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_browser_live_smoothness_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_browser_live_smoothness_profile_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_browser_live_smoothness_profile {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    for idx, hotspot in enumerate(payload["top_hotspots"], start=1):
        print(f"hotspot_{idx}={hotspot.get('class')}:{hotspot.get('name')}:score={hotspot.get('score')}")
    if errors:
        print("errors=" + json.dumps(errors, default=str))
    return 0 if status in {"PASS", "PARTIAL"} else 1


def datetime_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


if __name__ == "__main__":
    raise SystemExit(main())
