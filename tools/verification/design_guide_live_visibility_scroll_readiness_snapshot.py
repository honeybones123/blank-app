"""Browser/live Design Guide visibility and scroll-readiness audit.

Audit-only. This verifier inspects the already-running live app path and records
why the real Design Guide card is or is not browser-visible while summary cards
are visible. It does not change family runtimes, contracts, CTA/publication/apply
semantics, visible wording, or final publication authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_URL = "http://localhost:8504/?page=inputs"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _datetime_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _wait_for_live_url(url: str, *, timeout_s: float = 30.0) -> None:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(base) as response:  # noqa: S310 - local verifier only
                if 200 <= int(response.status) < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for live app at {base}: {last_error}")


def _install_probe(context) -> None:
    context.add_init_script(
        r"""
        (() => {
          window.__dgVisibilityAudit = {
            installedAt: Date.now(),
            mutationBatches: [],
            scrollEvents: []
          };
          try {
            const observer = new MutationObserver((records) => {
              const audit = window.__dgVisibilityAudit;
              audit.mutationBatches.push({
                at: Date.now(),
                count: records.length,
                added: records.reduce((n, r) => n + (r.addedNodes ? r.addedNodes.length : 0), 0),
                removed: records.reduce((n, r) => n + (r.removedNodes ? r.removedNodes.length : 0), 0),
                bodyTextLength: String(document.body && document.body.innerText || "").length
              });
              if (audit.mutationBatches.length > 120) {
                audit.mutationBatches = audit.mutationBatches.slice(-120);
              }
            });
            observer.observe(document.documentElement || document.body, {subtree: true, childList: true, attributes: true});
            window.__dgVisibilityAudit.mutationObserverInstalled = true;
          } catch (err) {
            window.__dgVisibilityAudit.mutationObserverError = String(err && err.message ? err.message : err);
          }
          try {
            window.addEventListener("scroll", () => {
              const audit = window.__dgVisibilityAudit;
              audit.scrollEvents.push({
                at: Date.now(),
                scrollY: Math.round(window.scrollY || 0),
                scrollHeight: Math.round(document.documentElement.scrollHeight || document.body.scrollHeight || 0)
              });
              if (audit.scrollEvents.length > 120) {
                audit.scrollEvents = audit.scrollEvents.slice(-120);
              }
            }, {passive: true});
          } catch (err) {
            window.__dgVisibilityAudit.scrollObserverError = String(err && err.message ? err.message : err);
          }
        })();
        """
    )


def _page_snapshot(page, *, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const rectPayload = (rect) => ({
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                top: Math.round(rect.top),
                bottom: Math.round(rect.bottom),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
              });
              const stylePayload = (el) => {
                const style = window.getComputedStyle(el);
                return {
                  display: style.display,
                  visibility: style.visibility,
                  opacity: style.opacity,
                  position: style.position,
                  overflow: style.overflow,
                  overflowY: style.overflowY,
                  pointerEvents: style.pointerEvents,
                  color: style.color,
                  backgroundColor: style.backgroundColor,
                  borderColor: style.borderColor
                };
              };
              const isVisible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                if (el.hasAttribute && (el.hasAttribute("hidden") || el.hasAttribute("inert") || el.closest("[inert]"))) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const ancestry = (el) => {
                const rows = [];
                let cur = el;
                while (cur && rows.length < 8) {
                  const rect = cur.getBoundingClientRect ? cur.getBoundingClientRect() : null;
                  const style = cur.nodeType === 1 ? window.getComputedStyle(cur) : null;
                  rows.push({
                    tag: String(cur.tagName || "").toLowerCase(),
                    cls: String(cur.className || "").slice(0, 140),
                    testid: cur.getAttribute ? cur.getAttribute("data-testid") : null,
                    text: clean(cur.innerText || cur.textContent).slice(0, 180),
                    rect: rect ? rectPayload(rect) : null,
                    display: style ? style.display : null,
                    visibility: style ? style.visibility : null,
                    overflow: style ? style.overflow : null,
                    overflowY: style ? style.overflowY : null
                  });
                  cur = cur.parentElement;
                }
                return rows;
              };
              const elementPayload = (el) => {
                const rect = el.getBoundingClientRect();
                const cx = Math.max(0, Math.min(window.innerWidth - 1, rect.left + rect.width / 2));
                const cy = Math.max(0, Math.min(window.innerHeight - 1, rect.top + rect.height / 2));
                const topAtCenter = document.elementFromPoint(cx, cy);
                const inViewport = rect.bottom >= 0 && rect.top <= window.innerHeight && rect.right >= 0 && rect.left <= window.innerWidth;
                return {
                  tag: String(el.tagName || "").toLowerCase(),
                  text: clean(el.innerText || el.textContent).slice(0, 800),
                  cls: String(el.className || "").slice(0, 200),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  role: el.getAttribute ? el.getAttribute("role") : null,
                  ariaLabel: el.getAttribute ? el.getAttribute("aria-label") : null,
                  rect: rectPayload(rect),
                  style: stylePayload(el),
                  visible: isVisible(el),
                  inViewport,
                  hiddenAttribute: Boolean(el.hasAttribute && el.hasAttribute("hidden")),
                  inertAncestor: Boolean(el.closest && el.closest("[inert]")),
                  coveredAtCenter: Boolean(topAtCenter && topAtCenter !== el && !el.contains(topAtCenter)),
                  topElementAtCenter: topAtCenter ? {
                    tag: String(topAtCenter.tagName || "").toLowerCase(),
                    cls: String(topAtCenter.className || "").slice(0, 120),
                    text: clean(topAtCenter.innerText || topAtCenter.textContent).slice(0, 120),
                    testid: topAtCenter.getAttribute ? topAtCenter.getAttribute("data-testid") : null
                  } : null,
                  ancestry: ancestry(el)
                };
              };
              const scrollableElements = Array.from(document.querySelectorAll("body, body *"))
                .filter((el) => {
                  if (!el || !el.getBoundingClientRect) return false;
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  const canScroll = (el.scrollHeight || 0) > (el.clientHeight || 0) + 8;
                  const scrollStyle = /(auto|scroll|overlay)/i.test(String(style.overflowY || style.overflow || ""));
                  return canScroll && (scrollStyle || rect.height >= window.innerHeight * 0.45);
                })
                .map((el, index) => {
                  const rect = el.getBoundingClientRect();
                  return {
                    index,
                    tag: String(el.tagName || "").toLowerCase(),
                    cls: String(el.className || "").slice(0, 180),
                    testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                    text: clean(el.innerText || el.textContent).slice(0, 220),
                    rect: rectPayload(rect),
                    scrollTop: Math.round(el.scrollTop || 0),
                    scrollHeight: Math.round(el.scrollHeight || 0),
                    clientHeight: Math.round(el.clientHeight || 0),
                    overflowY: window.getComputedStyle(el).overflowY,
                    score: Math.round(((el.scrollHeight || 0) - (el.clientHeight || 0)) + Math.max(0, rect.height))
                  };
                })
                .sort((a, b) => b.score - a.score)
                .slice(0, 20);
              const bodyText = String(document.body && document.body.innerText || "");
              const all = Array.from(document.querySelectorAll("body *"));
              const exactDesignGuide = all.filter((el) => clean(el.innerText || el.textContent) === "Design Guide");
              const designGuideTextMatches = all
                .filter((el) => /Design Guide/i.test(clean(el.innerText || el.textContent)))
                .slice(0, 80);
              const productHeadingCandidates = exactDesignGuide.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                const parentText = clean(el.parentElement ? el.parentElement.innerText || el.parentElement.textContent : "");
                const ancestorText = clean(el.closest("[data-testid], section, main, div") ? el.closest("[data-testid], section, main, div").innerText || "" : "");
                return text === "Design Guide" && !/Design Guide Debug|Debug session state/i.test(parentText) && !/Design Guide Debug|Debug session state/i.test(ancestorText.slice(0, 240));
              });
              const cardCandidates = all
                .filter((el) => {
                  const text = clean(el.innerText || el.textContent);
                  const id = String(el.getAttribute ? el.getAttribute("data-testid") || "" : "");
                  const cls = String(el.className || "");
                  return /design-guide|fast-guidance|final-publication/i.test(id + " " + cls)
                    || /Run one-click auto design|Apply recommendation|Design is efficient|Design Guide family contract|repair is blocked|cleanup required|Review Design Guide recommendation/i.test(text);
                })
                .slice(0, 80);
              const summaryCandidates = all
                .filter((el) => {
                  const text = clean(el.innerText || el.textContent);
                  return /Bending.*ULS|Shear.*ULS|Utilisation|Capacity/i.test(text);
                })
                .slice(0, 80);
              const placeholderCandidates = all
                .filter((el) => /stable rerun shell|fallback|placeholder|loading|spinner|skeleton|shell/i.test(clean(el.innerText || el.textContent)))
                .slice(0, 80);
              const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,[role='heading']"))
                .filter((el) => /Design Guide|Inputs|Batch design|Debug/i.test(clean(el.innerText || el.textContent)))
                .slice(0, 80);
              const buttons = Array.from(document.querySelectorAll("button"))
                .filter(isVisible)
                .map((el) => ({
                  text: clean(el.innerText || el.textContent).slice(0, 160),
                  disabled: Boolean(el.disabled || el.getAttribute("aria-disabled") === "true"),
                  rect: rectPayload(el.getBoundingClientRect()),
                  cls: String(el.className || "").slice(0, 120),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null
                }))
                .slice(0, 80);
              return {
                label,
                url: window.location.href,
                title: document.title,
                timestampMs: Date.now(),
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scroll: {
                  x: Math.round(window.scrollX || 0),
                  y: Math.round(window.scrollY || 0),
                  height: Math.round(document.documentElement.scrollHeight || document.body.scrollHeight || 0),
                  width: Math.round(document.documentElement.scrollWidth || document.body.scrollWidth || 0),
                  clientHeight: Math.round(document.documentElement.clientHeight || 0),
                  bodyHeight: Math.round(document.body ? document.body.scrollHeight || 0 : 0)
                },
                scrollableElements,
                bodyTextLength: bodyText.length,
                bodyTextHashSeed: bodyText.slice(0, 4000),
                exactDesignGuideCount: exactDesignGuide.length,
                productDesignGuideHeadingCount: productHeadingCandidates.length,
                designGuideTextMatchCount: designGuideTextMatches.length,
                cardCandidateCount: cardCandidates.length,
                summaryCandidateCount: summaryCandidates.length,
                placeholderCandidateCount: placeholderCandidates.length,
                productDesignGuideHeadings: productHeadingCandidates.slice(0, 20).map(elementPayload),
                designGuideTextMatches: designGuideTextMatches.slice(0, 24).map(elementPayload),
                cardCandidates: cardCandidates.slice(0, 24).map(elementPayload),
                summaryCandidates: summaryCandidates.slice(0, 14).map(elementPayload),
                placeholderCandidates: placeholderCandidates.slice(0, 20).map(elementPayload),
                headings: headings.map(elementPayload),
                buttons,
                auditProbe: window.__dgVisibilityAudit || null
              };
            }
            """,
            label,
        )
    )


def _attempt_scroll(page, *, index: int) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (index) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const candidates = Array.from(document.querySelectorAll("body, body *"))
                .filter((el) => {
                  if (!el || !el.getBoundingClientRect) return false;
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  const canScroll = (el.scrollHeight || 0) > (el.clientHeight || 0) + 8;
                  const scrollStyle = /(auto|scroll|overlay)/i.test(String(style.overflowY || style.overflow || ""));
                  return canScroll && (scrollStyle || rect.height >= window.innerHeight * 0.45);
                })
                .sort((a, b) => {
                  const as = ((a.scrollHeight || 0) - (a.clientHeight || 0)) + Math.max(0, a.getBoundingClientRect().height);
                  const bs = ((b.scrollHeight || 0) - (b.clientHeight || 0)) + Math.max(0, b.getBoundingClientRect().height);
                  return bs - as;
                });
              const target = candidates[0] || document.scrollingElement || document.documentElement;
              const before = {
                y: Math.round(window.scrollY || 0),
                height: Math.round(document.documentElement.scrollHeight || document.body.scrollHeight || 0),
                viewport: Math.round(window.innerHeight || 0),
                targetScrollTop: Math.round(target.scrollTop || 0),
                targetScrollHeight: Math.round(target.scrollHeight || 0),
                targetClientHeight: Math.round(target.clientHeight || 0)
              };
              const next = Math.min(before.targetScrollHeight, before.targetScrollTop + Math.max(360, Math.round(before.viewport * 0.75)));
              target.scrollTop = next;
              if (target === document.scrollingElement || target === document.documentElement || target === document.body) {
                window.scrollTo({top: next, behavior: "instant"});
              }
              const after = {
                y: Math.round(window.scrollY || 0),
                height: Math.round(document.documentElement.scrollHeight || document.body.scrollHeight || 0),
                viewport: Math.round(window.innerHeight || 0),
                targetScrollTop: Math.round(target.scrollTop || 0),
                targetScrollHeight: Math.round(target.scrollHeight || 0),
                targetClientHeight: Math.round(target.clientHeight || 0)
              };
              return {
                index,
                before,
                requestedY: next,
                after,
                moved: after.y !== before.y || after.targetScrollTop !== before.targetScrollTop,
                locked: next > before.targetScrollTop && after.targetScrollTop === before.targetScrollTop,
                target: {
                  tag: String(target.tagName || "").toLowerCase(),
                  cls: String(target.className || "").slice(0, 180),
                  testid: target.getAttribute ? target.getAttribute("data-testid") : null,
                  text: clean(target.innerText || target.textContent).slice(0, 180)
                },
                candidateCount: candidates.length
              };
            }
            """,
            index,
        )
    )


def _classify(payload: dict[str, Any]) -> dict[str, Any]:
    snapshots = list(payload.get("snapshots") or [])
    top = snapshots[0] if snapshots else {}
    all_headings = [heading for snap in snapshots for heading in (snap.get("productDesignGuideHeadings") or [])]
    all_cards = [card for snap in snapshots for card in (snap.get("cardCandidates") or [])]
    all_placeholders = [item for snap in snapshots for item in (snap.get("placeholderCandidates") or [])]
    product_heading_visible = any(item.get("visible") for item in all_headings)
    product_card_visible = any(item.get("visible") for item in all_cards)
    product_heading_in_dom = bool(all_headings)
    product_card_in_dom = bool(all_cards)
    scroll_attempts = list(payload.get("scroll_attempts") or [])
    scroll_locked = bool(scroll_attempts and not any(attempt.get("moved") for attempt in scroll_attempts))
    initial_scroll_lock_or_late_container = bool(
        scroll_attempts
        and any(attempt.get("locked") for attempt in scroll_attempts)
        and any(attempt.get("moved") for attempt in scroll_attempts)
    )
    def _container_bottom_reached(snap: dict[str, Any]) -> bool:
        scrollables = list(snap.get("scrollableElements") or [])
        if scrollables:
            target = scrollables[0]
            return int(target.get("scrollTop") or 0) + int(target.get("clientHeight") or 0) >= int(
                target.get("scrollHeight") or 0
            ) - 8
        scroll = snap.get("scroll") or {}
        viewport = snap.get("viewport") or {}
        return int(scroll.get("y") or 0) + int(viewport.get("height") or 0) >= int(scroll.get("height") or 0) - 8

    reached_bottom = any(_container_bottom_reached(snap) for snap in snapshots)
    mutation_batches = []
    for snap in snapshots:
        probe = snap.get("auditProbe") or {}
        mutation_batches.extend(probe.get("mutationBatches") or [])
    scroll_height_values = []
    for snap in snapshots:
        scrollables = list(snap.get("scrollableElements") or [])
        if scrollables:
            scroll_height_values.append(scrollables[0].get("scrollHeight"))
        elif snap.get("scroll"):
            scroll_height_values.append((snap.get("scroll") or {}).get("height"))
    scroll_height_changed = len(set(str(value) for value in scroll_height_values)) > 1
    debug_heading_matches = [
        match
        for snap in snapshots
        for match in (snap.get("designGuideTextMatches") or [])
        if re.search(r"Design Guide Debug|Debug session state", str(match.get("text") or ""), re.IGNORECASE)
    ]
    summary_visible_initially = bool((top.get("summaryCandidateCount") or 0) > 0)
    summary_visible_any = any(bool((snap.get("summaryCandidateCount") or 0) > 0) for snap in snapshots)

    if product_card_visible or product_heading_visible:
        diagnosis = "product_design_guide_visible"
    elif product_card_in_dom or product_heading_in_dom:
        diagnosis = "product_design_guide_in_dom_but_not_visible"
    elif scroll_locked:
        diagnosis = "scroll_locked_before_product_design_guide_rendered"
    elif reached_bottom:
        diagnosis = "product_design_guide_not_rendered_in_reachable_dom"
    else:
        diagnosis = "product_design_guide_not_found_before_scroll_exhaustion"

    blockers: list[str] = []
    if not summary_visible_any:
        blockers.append("summary_cards_not_visible_at_initial_capture")
    if not (product_card_visible or product_heading_visible):
        blockers.append("real_design_guide_card_not_browser_visible")
    if debug_heading_matches:
        blockers.append("duplicate_debug_design_guide_heading_present")
    if all_placeholders:
        blockers.append("placeholder_or_shell_text_present")
    if scroll_locked:
        blockers.append("scroll_position_locked_during_probe")

    return {
        "diagnosis": diagnosis,
        "summary_visible_initially": summary_visible_initially,
        "summary_visible_during_probe": summary_visible_any,
        "product_design_guide_heading_in_dom": product_heading_in_dom,
        "product_design_guide_heading_visible": product_heading_visible,
        "product_card_candidate_in_dom": product_card_in_dom,
        "product_card_candidate_visible": product_card_visible,
        "reached_bottom": reached_bottom,
        "scroll_locked": scroll_locked,
        "initial_scroll_lock_or_late_container": initial_scroll_lock_or_late_container,
        "scroll_height_changed_during_probe": scroll_height_changed,
        "mutation_batch_count": len(mutation_batches),
        "debug_design_guide_heading_count": len(debug_heading_matches),
        "placeholder_or_shell_count": len(all_placeholders),
        "blockers": blockers,
        "next_recommendation": _recommendation_from_diagnosis(diagnosis, blockers),
    }


def _recommendation_from_diagnosis(diagnosis: str, blockers: list[str]) -> str:
    if diagnosis == "product_design_guide_visible":
        return "The live card is visible; next inspect why the previous visual consistency verifier missed it."
    if diagnosis == "product_design_guide_in_dom_but_not_visible":
        return "Next slice should inspect the hidden/clipped/covered ancestor chain for the captured Design Guide card candidate."
    if diagnosis == "scroll_locked_before_product_design_guide_rendered":
        return "Next slice should audit scroll lock/loading shell ownership around Inputs page render completion."
    if diagnosis == "product_design_guide_not_rendered_in_reachable_dom":
        return "Next slice should audit the render gate that decides whether the Design Guide section is created after Batch design."
    if "duplicate_debug_design_guide_heading_present" in blockers:
        return "Keep product/debug Design Guide headings separated in browser probes; debug headings are present and can confuse selectors."
    return "Next slice should add a focused live render-gate trace for the missing Design Guide section."


def _markdown(payload: dict[str, Any]) -> str:
    result = payload.get("classification") or {}
    lines = [
        "# Design Guide Live Visibility / Scroll Readiness Audit",
        "",
        f"- Result: `{payload.get('status')}`",
        f"- Created: `{payload.get('created_at')}`",
        f"- URL: `{payload.get('url')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Diagnosis",
        "",
        f"- Diagnosis: `{result.get('diagnosis')}`",
        f"- Summary visible initially: `{result.get('summary_visible_initially')}`",
        f"- Summary visible during probe: `{result.get('summary_visible_during_probe')}`",
        f"- Product Design Guide heading in DOM: `{result.get('product_design_guide_heading_in_dom')}`",
        f"- Product Design Guide heading visible: `{result.get('product_design_guide_heading_visible')}`",
        f"- Product card candidate in DOM: `{result.get('product_card_candidate_in_dom')}`",
        f"- Product card candidate visible: `{result.get('product_card_candidate_visible')}`",
        f"- Reached bottom: `{result.get('reached_bottom')}`",
        f"- Scroll locked: `{result.get('scroll_locked')}`",
        f"- Initial scroll lock / late container: `{result.get('initial_scroll_lock_or_late_container')}`",
        f"- Scroll height changed during probe: `{result.get('scroll_height_changed_during_probe')}`",
        f"- Mutation batches observed: `{result.get('mutation_batch_count')}`",
        f"- Debug Design Guide heading count: `{result.get('debug_design_guide_heading_count')}`",
        f"- Placeholder/shell count: `{result.get('placeholder_or_shell_count')}`",
        "",
        "## Blockers / Evidence",
        "",
    ]
    blockers = list(result.get("blockers") or [])
    lines.extend([f"- `{item}`" for item in blockers] or ["- None"])
    lines.extend(["", "## Scroll Attempts", ""])
    for attempt in payload.get("scroll_attempts", [])[:12]:
        before = attempt.get("before") or {}
        after = attempt.get("after") or {}
        lines.append(
            f"- `{attempt.get('index')}` window y `{before.get('y')}` -> `{after.get('y')}`, "
            f"target scroll `{before.get('targetScrollTop')}` -> `{after.get('targetScrollTop')}`, "
            f"target height `{after.get('targetScrollHeight')}`, locked `{attempt.get('locked')}`"
        )
    lines.extend(["", "## Snapshot Summary", ""])
    for snap in payload.get("snapshots", [])[:12]:
        scroll = snap.get("scroll") or {}
        top_scrollable = (list(snap.get("scrollableElements") or [])[:1] or [{}])[0]
        lines.append(
            f"- `{snap.get('label')}`: y `{scroll.get('y')}`, height `{scroll.get('height')}`, "
            f"target scroll `{top_scrollable.get('scrollTop')}`, target height `{top_scrollable.get('scrollHeight')}`, "
            f"summary candidates `{snap.get('summaryCandidateCount')}`, product headings "
            f"`{snap.get('productDesignGuideHeadingCount')}`, card candidates `{snap.get('cardCandidateCount')}`, "
            f"placeholders `{snap.get('placeholderCandidateCount')}`"
        )
    lines.extend(["", "## Recommendation", ""])
    lines.append(str(result.get("next_recommendation") or "No recommendation recorded."))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--settle-ms", type=int, default=900)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _datetime_stamp()
    snapshots: list[dict[str, Any]] = []
    scroll_attempts: list[dict[str, Any]] = []
    errors: list[str] = []
    screenshot_paths: dict[str, str] = {}

    try:
        _wait_for_live_url(args.url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1100})
            _install_probe(context)
            page = context.new_page()
            page.set_default_timeout(25_000)
            page.goto(args.url, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(args.settle_ms)
            try:
                page.evaluate("() => window.scrollTo({top: 0, behavior: 'instant'})")
                page.wait_for_timeout(500)
            except Exception:
                pass
            snapshots.append(_page_snapshot(page, label="initial_top"))
            top_png = ARTIFACT_DIR / f"design_guide_live_visibility_scroll_readiness_top_{stamp}.png"
            page.screenshot(path=str(top_png), full_page=False)
            screenshot_paths["top"] = str(top_png)
            for index in range(max(1, args.steps)):
                scroll_attempts.append(_attempt_scroll(page, index=index))
                page.wait_for_timeout(550)
                snap = _page_snapshot(page, label=f"scroll_step_{index}")
                snapshots.append(snap)
                if snap.get("productDesignGuideHeadingCount") or snap.get("cardCandidateCount"):
                    break
                scrollables = list(snap.get("scrollableElements") or [])
                if scrollables:
                    target = scrollables[0]
                    reached_container_bottom = int(target.get("scrollTop") or 0) + int(
                        target.get("clientHeight") or 0
                    ) >= int(target.get("scrollHeight") or 0) - 8
                else:
                    scroll = snap.get("scroll") or {}
                    reached_container_bottom = int(scroll.get("y") or 0) + int(
                        (snap.get("viewport") or {}).get("height") or 0
                    ) >= int(scroll.get("height") or 0) - 8
                if reached_container_bottom:
                    break
            bottom_png = ARTIFACT_DIR / f"design_guide_live_visibility_scroll_readiness_bottom_{stamp}.png"
            page.screenshot(path=str(bottom_png), full_page=False)
            screenshot_paths["bottom"] = str(bottom_png)
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    payload: dict[str, Any] = {
        "schema": "design_guide_live_visibility_scroll_readiness.v1",
        "status": "PASS" if snapshots and not errors else "FAIL",
        "created_at": stamp,
        "url": args.url,
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_publication_apply_semantics_changed": False,
        "visible_wording_changed": False,
        "final_publication_authority_changed": False,
        "snapshots": snapshots,
        "scroll_attempts": scroll_attempts,
        "screenshots": screenshot_paths,
        "errors": errors,
    }
    payload["classification"] = _classify(payload) if snapshots else {
        "diagnosis": "snapshot_failed",
        "blockers": errors,
        "next_recommendation": "Fix the live app/probe availability before auditing visibility.",
    }
    payload["audit_hash"] = _stable_hash(
        {
            "url": args.url,
            "classification": payload["classification"],
            "scroll_attempts": scroll_attempts,
            "snapshot_counts": [
                {
                    "label": snap.get("label"),
                    "productHeadings": snap.get("productDesignGuideHeadingCount"),
                    "cardCandidates": snap.get("cardCandidateCount"),
                    "summaryCandidates": snap.get("summaryCandidateCount"),
                    "placeholders": snap.get("placeholderCandidateCount"),
                }
                for snap in snapshots
            ],
            "errors": errors,
        }
    )
    json_path = ARTIFACT_DIR / f"design_guide_live_visibility_scroll_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_visibility_scroll_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_live_visibility_scroll_readiness {payload['status']}")
    print(f"diagnosis={payload['classification'].get('diagnosis')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
