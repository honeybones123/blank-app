"""Browser/live first-paint layout hotspot owner audit.

Audit-only. This verifier separates the current smoothness profile's
layout/first-paint score into likely owner surfaces: Inputs summary shell,
Design Guide pending shell/card swap, model/Plotly remount, or Streamlit wrapper
chrome. It does not change product behaviour, engineering logic, publication,
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
  window.__dgFirstPaintAudit = {
    layoutShifts: [],
    mutations: [],
    paints: [],
    errors: []
  };
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const ownerOf = (target) => {
    try {
      let el = target && target.nodeType === 1 ? target : target && target.parentElement;
      for (let depth = 0; el && depth < 6; depth += 1, el = el.parentElement) {
        const cls = String(el.className || "");
        const testid = el.getAttribute ? String(el.getAttribute("data-testid") || "") : "";
        const text = clean(el.innerText || el.textContent).slice(0, 180);
        if (/js-plotly-plot|plotly|svg-container/i.test(cls)) return "model_plotly";
        if (/inputs_section_2d_diagram_chart|inputs_section_3d_diagram/i.test(cls + " " + testid)) return "model_panel";
        if (/design-guide-proof-pending|design-guide-card/i.test(testid)) return "design_guide_shell_or_card";
        if (/dg-proof-pending|fast-guidance-item|dg-card/i.test(cls)) return "design_guide_shell_or_card";
        if (/summary-check-card|summary-skeleton|inputs-first-paint-shell/i.test(cls)) return "summary_first_paint_or_cards";
        if (/Batch design|Active set|Active beam/i.test(text)) return "batch_design_panel";
        if (/stMainBlockContainer|stVerticalBlock|stElementContainer|stLayoutWrapper|stColumn/i.test(cls + " " + testid)) return "streamlit_layout_wrapper";
      }
    } catch (err) {
      window.__dgFirstPaintAudit.errors.push(String(err && err.message || err));
    }
    return "unknown";
  };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        window.__dgFirstPaintAudit.layoutShifts.push({
          value: Number(entry.value || 0),
          startTime: Number(entry.startTime || 0),
          owners: (entry.sources || []).map((source) => ownerOf(source.node)),
          sourceCount: (entry.sources || []).length
        });
      }
    }).observe({type: "layout-shift", buffered: true});
  } catch (err) {
    window.__dgFirstPaintAudit.errors.push("layout_shift_observer:" + String(err && err.message || err));
  }
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        window.__dgFirstPaintAudit.paints.push({
          name: String(entry.name || ""),
          startTime: Number(entry.startTime || 0)
        });
      }
    }).observe({type: "paint", buffered: true});
  } catch (err) {
    window.__dgFirstPaintAudit.errors.push("paint_observer:" + String(err && err.message || err));
  }
  try {
    const observer = new MutationObserver((records) => {
      const counts = {};
      let added = 0;
      let removed = 0;
      let attributes = 0;
      for (const record of records) {
        added += record.addedNodes ? record.addedNodes.length : 0;
        removed += record.removedNodes ? record.removedNodes.length : 0;
        attributes += record.type === "attributes" ? 1 : 0;
        const owner = ownerOf(record.target);
        counts[owner] = (counts[owner] || 0) + 1;
      }
      window.__dgFirstPaintAudit.mutations.push({
        at: Date.now(),
        recordCount: records.length,
        added,
        removed,
        attributes,
        owners: counts
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
    window.__dgFirstPaintAudit.errors.push("mutation_observer:" + String(err && err.message || err));
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
              const summary = all.find((el) => /summary-check-card/.test(String(el.className || "")))
                || byText(/Bending\s+[-—]\s+ULS/i);
              const model = document.querySelector(".js-plotly-plot")
                || document.querySelector("[class*='inputs_section_2d_diagram_chart']");
              const firstPaintShell = document.querySelector(".inputs-first-paint-shell");
              const dgPending = document.querySelector("[data-testid='design-guide-proof-pending']");
              const dgCard = document.querySelector("[data-testid='design-guide-card']")
                || document.querySelector(".fast-guidance-item");
              return {
                url: window.location.href,
                scrollY: Math.round(window.scrollY || 0),
                bodyHeight: Math.round(document.body ? document.body.scrollHeight : 0),
                viewportHeight: Math.round(window.innerHeight || 0),
                areas: {
                  summary_card: rectPayload(summary),
                  model_plotly: rectPayload(model),
                  first_paint_shell: rectPayload(firstPaintShell),
                  design_guide_pending: rectPayload(dgPending),
                  design_guide_card: rectPayload(dgCard),
                  batch_design: rectPayload(byText(/^Batch design$/i))
                },
                audit: window.__dgFirstPaintAudit || {}
              };
            }
            """
        )
        or {}
    )


def _summarise(capture: dict[str, Any]) -> dict[str, Any]:
    audit = dict(capture.get("audit") or {})
    layout_shifts = list(audit.get("layoutShifts") or [])
    mutations = list(audit.get("mutations") or [])
    shift_total = round(sum(float(row.get("value") or 0.0) for row in layout_shifts), 6)
    shift_owner_counts: dict[str, int] = {}
    for row in layout_shifts:
        for owner in list(row.get("owners") or []):
            shift_owner_counts[str(owner)] = shift_owner_counts.get(str(owner), 0) + 1
    mutation_owner_counts: dict[str, int] = {}
    mutation_owner_records: dict[str, int] = {}
    for batch in mutations:
        owners = dict(batch.get("owners") or {})
        for owner, count in owners.items():
            mutation_owner_counts[str(owner)] = mutation_owner_counts.get(str(owner), 0) + 1
            mutation_owner_records[str(owner)] = mutation_owner_records.get(str(owner), 0) + int(count or 0)
    areas = dict(capture.get("areas") or {})
    top_mutation_owner = max(mutation_owner_records, key=mutation_owner_records.get, default="")
    top_shift_owner = max(shift_owner_counts, key=shift_owner_counts.get, default="")
    model_visible = bool((areas.get("model_plotly") or {}).get("visible"))
    first_paint_shell_visible = bool((areas.get("first_paint_shell") or {}).get("visible"))
    dg_pending_visible = bool((areas.get("design_guide_pending") or {}).get("visible"))
    dg_card_visible = bool((areas.get("design_guide_card") or {}).get("visible"))

    if top_mutation_owner in {"model_plotly", "model_panel"} and mutation_owner_records.get(top_mutation_owner, 0) >= 50:
        owner = "MODEL_DIAGRAM_PLOTLY_FIRST_PAINT"
        next_slice = "Create model/diagram render-data reuse or stable-height readiness before changing Design Guide card layout."
    elif first_paint_shell_visible or mutation_owner_records.get("summary_first_paint_or_cards", 0) > 0:
        owner = "INPUTS_SUMMARY_FIRST_PAINT_SHELL"
        next_slice = "Audit summary first-paint shell height/key before changing model or Design Guide layout."
    elif dg_pending_visible or (not dg_card_visible and mutation_owner_records.get("design_guide_shell_or_card", 0) > 0):
        owner = "DESIGN_GUIDE_PENDING_SHELL"
        next_slice = "Audit Design Guide pending shell/card stable height readiness."
    elif top_shift_owner:
        owner = f"LAYOUT_SHIFT_SOURCE_{top_shift_owner.upper()}"
        next_slice = "Add a narrower owner probe for the reported layout-shift source."
    else:
        owner = "UNREPRODUCED_OR_STREAMLIT_CHROME"
        next_slice = "Use a user-reported live URL/session to reproduce the visual gap."

    return {
        "status": "PASS",
        "classification": owner,
        "layout_shift_total": shift_total,
        "layout_shift_count": len(layout_shifts),
        "layout_shift_owner_counts": shift_owner_counts,
        "top_shift_owner": top_shift_owner,
        "mutation_batch_count": len(mutations),
        "mutation_owner_records": mutation_owner_records,
        "top_mutation_owner": top_mutation_owner,
        "model_plotly_visible": model_visible,
        "first_paint_shell_visible": first_paint_shell_visible,
        "design_guide_pending_visible": dg_pending_visible,
        "design_guide_card_visible": dg_card_visible,
        "observer_errors": list(audit.get("errors") or []),
        "recommended_next_slice": next_slice,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_first_paint_layout_hotspot_owner_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_first_paint_layout_hotspot_owner_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Design Guide First-Paint Layout Hotspot Owner Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{summary.get('classification')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Layout shift total: `{summary.get('layout_shift_total')}`",
        f"- Top mutation owner: `{summary.get('top_mutation_owner')}`",
        f"- Top shift owner: `{summary.get('top_shift_owner')}`",
        f"- Recommended next slice: `{summary.get('recommended_next_slice')}`",
        "",
        "## Owner Evidence",
        "",
        "```json",
        json.dumps(
            {
                "layout_shift_owner_counts": summary.get("layout_shift_owner_counts"),
                "mutation_owner_records": summary.get("mutation_owner_records"),
                "areas": payload.get("capture", {}).get("areas"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )[:12000],
        "```",
        "",
        "## Rules",
        "- Audit-only.",
        "- No engineering behaviour, visible wording, CTA/apply, publication, render ownership, or family runtime changed.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _capture(base_url: str, *, recipe: str, headed: bool, wait_ms: int) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.add_init_script(INIT_SCRIPT)
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe, "batch_design_open": "0"})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(max(1500, wait_ms))
        capture = _capture_dom_state(page)
        browser.close()
    capture["requested_url"] = url
    capture["recipe"] = recipe
    return capture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8647)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_LAYOUT_HOTSPOT_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=6500)
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
        capture = _capture(base_url, recipe=str(args.recipe), headed=bool(args.headed), wait_ms=int(args.wait_ms))
        summary = _summarise(capture)
        payload = {
            "schema": "design_guide_first_paint_layout_hotspot_owner.v1",
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
