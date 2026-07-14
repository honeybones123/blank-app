"""Browser/live source-node snapshot for Inputs page layout shifts.

Proof-only. This verifier records layout-shift source node ancestry so the
smoothness work can target a proven owner instead of patching generic Streamlit
wrappers. It does not change product behaviour, engineering logic, publication,
CTA/apply semantics, visible wording, or family runtimes.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_rerun_trigger_source_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


INIT_SCRIPT = r"""
(() => {
  window.__dgLayoutSourceNodeProbe = {
    layoutShifts: [],
    mutations: [],
    errors: []
  };
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const nodePayload = (node) => {
    try {
      if (!node) return null;
      const el = node.nodeType === 1 ? node : node.parentElement;
      if (!el) return null;
      const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
      return {
        tag: String(el.tagName || "").toLowerCase(),
        cls: String(el.className || "").slice(0, 180),
        testid: el.getAttribute ? String(el.getAttribute("data-testid") || "") : "",
        id: String(el.id || "").slice(0, 120),
        role: el.getAttribute ? String(el.getAttribute("role") || "") : "",
        aria: el.getAttribute ? String(el.getAttribute("aria-label") || "") : "",
        text: clean(el.innerText || el.textContent).slice(0, 240),
        rect: rect ? {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          top: Math.round(rect.top),
          bottom: Math.round(rect.bottom)
        } : null
      };
    } catch (err) {
      window.__dgLayoutSourceNodeProbe.errors.push(String(err && err.message || err));
      return null;
    }
  };
  const ancestorChain = (node) => {
    const chain = [];
    try {
      let el = node && node.nodeType === 1 ? node : node && node.parentElement;
      for (let depth = 0; el && depth < 8; depth += 1, el = el.parentElement) {
        const payload = nodePayload(el);
        if (payload) {
          payload.depth = depth;
          chain.push(payload);
        }
      }
    } catch (err) {
      window.__dgLayoutSourceNodeProbe.errors.push(String(err && err.message || err));
    }
    return chain;
  };
  const ownerFromChain = (chain) => {
    const haystack = clean((chain || []).map((row) => [
      row && row.cls,
      row && row.testid,
      row && row.id,
      row && row.role,
      row && row.aria,
      row && row.text
    ].join(" ")).join(" "));
    if (/summary-check-card|summary-card-stack|inputs-first-paint-shell|Bending\s+[-—]\s+ULS|Shear\s+[-—]\s+ULS/i.test(haystack)) {
      return "summary_first_paint_or_cards";
    }
    if (/Batch design|Active set|Active beam|Bulk Beam Manager/i.test(haystack)) {
      return "batch_design_panel";
    }
    if (/js-plotly-plot|plotly|svg-container/i.test(haystack)) {
      return "model_plotly";
    }
    if (/inputs_section_2d_diagram_chart|inputs_section_3d_diagram|Model/i.test(haystack)) {
      return "model_panel";
    }
    if (/stStatusWidget|stToolbar|stHeader|Stop Deploy|Deploy/i.test(haystack)) {
      return "streamlit_chrome";
    }
    if (/design-guide-proof-pending|design-guide-card|fast-guidance-item|Design Guide|Checking design guidance/i.test(haystack)) {
      return "design_guide_panel";
    }
    if (/stMainBlockContainer|stVerticalBlock|stElementContainer|stLayoutWrapper|stColumn|stMarkdownContainer/i.test(haystack)) {
      return "streamlit_layout_wrapper";
    }
    if (/root|stApp|body|html/i.test(haystack)) {
      return "app_root";
    }
    return "unknown";
  };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        const sources = Array.from(entry.sources || []).slice(0, 12).map((source) => {
          const chain = ancestorChain(source.node);
          return {
            owner: ownerFromChain(chain),
            currentRect: source.currentRect ? {
              x: Math.round(source.currentRect.x),
              y: Math.round(source.currentRect.y),
              width: Math.round(source.currentRect.width),
              height: Math.round(source.currentRect.height),
              top: Math.round(source.currentRect.top),
              bottom: Math.round(source.currentRect.bottom)
            } : null,
            previousRect: source.previousRect ? {
              x: Math.round(source.previousRect.x),
              y: Math.round(source.previousRect.y),
              width: Math.round(source.previousRect.width),
              height: Math.round(source.previousRect.height),
              top: Math.round(source.previousRect.top),
              bottom: Math.round(source.previousRect.bottom)
            } : null,
            chain
          };
        });
        window.__dgLayoutSourceNodeProbe.layoutShifts.push({
          value: Number(entry.value || 0),
          startTime: Number(entry.startTime || 0),
          sourceCount: sources.length,
          sources
        });
      }
    }).observe({type: "layout-shift", buffered: true});
  } catch (err) {
    window.__dgLayoutSourceNodeProbe.errors.push("layout_shift_observer:" + String(err && err.message || err));
  }
  try {
    const observer = new MutationObserver((records) => {
      const owners = {};
      for (const record of records) {
        const chain = ancestorChain(record.target);
        const owner = ownerFromChain(chain);
        owners[owner] = (owners[owner] || 0) + 1;
      }
      window.__dgLayoutSourceNodeProbe.mutations.push({
        at: Date.now(),
        recordCount: records.length,
        owners
      });
    });
    const start = () => {
      if (document.body) {
        observer.observe(document.body, {subtree: true, childList: true, attributes: true});
      } else {
        setTimeout(start, 25);
      }
    };
    start();
  } catch (err) {
    window.__dgLayoutSourceNodeProbe.errors.push("mutation_observer:" + String(err && err.message || err));
  }
})();
"""


def _capture_dom_state(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && rect.width > 2
                  && rect.height > 2;
              };
              const rectPayload = (el) => {
                if (!el) return {exists: false, visible: false};
                const rect = el.getBoundingClientRect();
                return {
                  exists: true,
                  visible: visible(el),
                  top: Math.round(rect.top),
                  bottom: Math.round(rect.bottom),
                  height: Math.round(rect.height),
                  width: Math.round(rect.width),
                  text: clean(el.innerText || el.textContent).slice(0, 220),
                  cls: String(el.className || "").slice(0, 160),
                  testid: el.getAttribute ? String(el.getAttribute("data-testid") || "") : null
                };
              };
              const all = Array.from(document.querySelectorAll("body *"));
              const byText = (regex) => all.find((el) => regex.test(clean(el.innerText || el.textContent))) || null;
              return {
                url: window.location.href,
                scrollY: Math.round(window.scrollY || 0),
                bodyHeight: Math.round(document.body ? document.body.scrollHeight : 0),
                viewportHeight: Math.round(window.innerHeight || 0),
                areas: {
                  inputs_heading: rectPayload(byText(/^(Beam design|Inputs)$/i)),
                  summary_card: rectPayload(document.querySelector(".summary-check-card") || byText(/Bending\s+[-—]\s+ULS/i)),
                  batch_design_heading: rectPayload(byText(/^Batch design$/i)),
                  batch_design_panel: rectPayload(byText(/Active set|Active beam|Bulk Beam Manager/i)),
                  model_plotly: rectPayload(document.querySelector(".js-plotly-plot")),
                  design_guide_heading: rectPayload(byText(/^Design Guide$/i)),
                  design_guide_card: rectPayload(document.querySelector("[data-testid='design-guide-card']") || document.querySelector(".fast-guidance-item")),
                  design_guide_pending: rectPayload(document.querySelector("[data-testid='design-guide-proof-pending']") || byText(/Checking design guidance/i))
                },
                probe: window.__dgLayoutSourceNodeProbe || {}
              };
            }
            """
        )
        or {}
    )


def _reset_probe(page) -> None:
    page.evaluate(
        r"""
        () => {
          if (window.__dgLayoutSourceNodeProbe) {
            window.__dgLayoutSourceNodeProbe.layoutShifts = [];
            window.__dgLayoutSourceNodeProbe.mutations = [];
            window.__dgLayoutSourceNodeProbe.errors = [];
          }
        }
        """
    )


def _click_live_design_guide_action(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                if (el.disabled || el.getAttribute("aria-disabled") === "true") return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && rect.width > 2
                  && rect.height > 2;
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


def _summarise(capture: dict[str, Any]) -> dict[str, Any]:
    probe = dict(capture.get("probe") or {})
    shifts = list(probe.get("layoutShifts") or [])
    mutations = list(probe.get("mutations") or [])
    owner_counts: dict[str, int] = {}
    owner_values: dict[str, float] = {}
    largest_shift: dict[str, Any] | None = None
    for shift in shifts:
        value = float(shift.get("value") or 0.0)
        if largest_shift is None or value > float(largest_shift.get("value") or 0.0):
            largest_shift = shift
        for source in list(shift.get("sources") or []):
            owner = str(source.get("owner") or "unknown")
            owner_counts[owner] = owner_counts.get(owner, 0) + 1
            owner_values[owner] = round(owner_values.get(owner, 0.0) + value, 6)
    mutation_owner_records: dict[str, int] = {}
    for batch in mutations:
        for owner, count in dict(batch.get("owners") or {}).items():
            mutation_owner_records[str(owner)] = mutation_owner_records.get(str(owner), 0) + int(count or 0)

    top_owner_by_value = max(owner_values, key=owner_values.get, default="")
    top_owner_by_count = max(owner_counts, key=owner_counts.get, default="")
    shift_total = round(sum(float(row.get("value") or 0.0) for row in shifts), 6)
    areas = dict(capture.get("areas") or {})
    fixed_gap_observed = False
    try:
        heading_bottom = float((areas.get("inputs_heading") or {}).get("bottom") or 0)
        summary_top = float((areas.get("summary_card") or {}).get("top") or 0)
        fixed_gap_observed = bool(heading_bottom and summary_top and (summary_top - heading_bottom) > 180)
    except Exception:
        fixed_gap_observed = False

    if top_owner_by_value in {"summary_first_paint_or_cards", "batch_design_panel", "model_panel", "model_plotly", "design_guide_panel"}:
        patch_target = top_owner_by_value
        recommendation = f"Create guarded layout containment readiness for {top_owner_by_value} before product CSS changes."
    elif top_owner_by_value in {"streamlit_layout_wrapper", "app_root"}:
        patch_target = "unproven_streamlit_wrapper"
        recommendation = "Do not patch product layout yet; reproduce the user-visible jump or add wrapper-specific source proof."
    else:
        patch_target = "unreproduced_or_unknown"
        recommendation = "No safe product patch target proven; capture a user-specific interaction recipe."

    return {
        "status": "PASS",
        "classification": "LAYOUT_SHIFT_SOURCE_NODE_SNAPSHOT",
        "layout_shift_total": shift_total,
        "layout_shift_count": len(shifts),
        "layout_shift_owner_counts": owner_counts,
        "layout_shift_owner_values": owner_values,
        "top_owner_by_value": top_owner_by_value,
        "top_owner_by_count": top_owner_by_count,
        "mutation_owner_records": mutation_owner_records,
        "largest_shift": largest_shift,
        "fixed_gap_observed": fixed_gap_observed,
        "candidate_patch_target": patch_target,
        "recommended_next_slice": recommendation,
        "observer_errors": list(probe.get("errors") or []),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_streamlit_layout_shift_source_node_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_streamlit_layout_shift_source_node_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Design Guide Streamlit Layout Shift Source Node Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{summary.get('classification')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Layout shift total: `{summary.get('layout_shift_total')}`",
        f"- Top owner by value: `{summary.get('top_owner_by_value')}`",
        f"- Top owner by count: `{summary.get('top_owner_by_count')}`",
        f"- Fixed gap observed: `{summary.get('fixed_gap_observed')}`",
        f"- Candidate patch target: `{summary.get('candidate_patch_target')}`",
        f"- Recommended next slice: `{summary.get('recommended_next_slice')}`",
        "",
        "## Owner Evidence",
        "",
        "```json",
        json.dumps(
            {
                "layout_shift_owner_counts": summary.get("layout_shift_owner_counts"),
                "layout_shift_owner_values": summary.get("layout_shift_owner_values"),
                "mutation_owner_records": summary.get("mutation_owner_records"),
                "areas": payload.get("capture", {}).get("areas"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )[:12000],
        "```",
        "",
        "## Largest Shift Source Chains",
        "",
        "```json",
        json.dumps(summary.get("largest_shift"), indent=2, sort_keys=True, default=str)[:14000],
        "```",
        "",
        "## Rules",
        "- Snapshot-only.",
        "- No engineering behaviour, visible wording, CTA/apply, publication, render ownership, or family runtime changed.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _capture(
    base_url: str,
    *,
    recipe: str,
    headed: bool,
    wait_ms: int,
    click_apply: bool,
    post_click_wait_ms: int,
) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        context.add_init_script(INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe, "batch_design_open": "0"})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(max(1500, wait_ms))
        action_result: dict[str, Any] = {"clicked": False, "skipped": True}
        if click_apply:
            _reset_probe(page)
            action_result = _click_live_design_guide_action(page)
            page.wait_for_timeout(max(1500, post_click_wait_ms))
        capture = _capture_dom_state(page)
        browser.close()
    capture["requested_url"] = url
    capture["recipe"] = recipe
    capture["capture_mode"] = "post_click_apply" if click_apply else "initial_load"
    capture["action_result"] = action_result
    return capture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8665)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_LAYOUT_SOURCE_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=7000)
    parser.add_argument("--click-apply", action="store_true")
    parser.add_argument("--post-click-wait-ms", type=int, default=7000)
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=70.0)
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            headed=bool(args.headed),
            wait_ms=int(args.wait_ms),
            click_apply=bool(args.click_apply),
            post_click_wait_ms=int(args.post_click_wait_ms),
        )
        summary = _summarise(capture)
        payload = {
            "schema": "design_guide_streamlit_layout_shift_source_node.v1",
            "created_at": created_at,
            "status": summary["status"],
            "summary": summary,
            "capture": capture,
            "product_behaviour_changed": False,
            "behaviour_scope": {
                "engineering_behaviour_changed": False,
                "visible_wording_changed": False,
                "cta_apply_changed": False,
                "publication_changed": False,
                "family_runtime_changed": False,
                "render_ownership_changed": False,
            },
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], **summary}, indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
