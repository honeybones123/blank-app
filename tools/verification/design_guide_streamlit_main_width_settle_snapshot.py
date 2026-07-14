"""Browser/live snapshot for early Streamlit main-block width settling.

Proof-only. This verifier samples the Streamlit main block from earliest page
load through first content paint so smoothness work can tell whether residual
layout shift is caused by app panels or by Streamlit's own initial width
hydration. It does not change product behaviour.
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
APP_PY = ROOT / "app.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


INIT_SCRIPT = r"""
(() => {
  window.__dgMainWidthSettleProbe = {
    samples: [],
    layoutShifts: [],
    errors: []
  };
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const rectPayload = (el) => {
    if (!el || !el.getBoundingClientRect) return {exists: false};
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return {
      exists: true,
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      top: Math.round(rect.top),
      bottom: Math.round(rect.bottom),
      maxWidth: String(style.maxWidth || ""),
      paddingLeft: String(style.paddingLeft || ""),
      paddingRight: String(style.paddingRight || ""),
      cls: String(el.className || "").slice(0, 180),
      testid: el.getAttribute ? String(el.getAttribute("data-testid") || "") : ""
    };
  };
  const sample = () => {
    try {
      const main = document.querySelector("[data-testid='stMainBlockContainer']")
        || document.querySelector(".block-container");
      const app = document.querySelector("[data-testid='stApp']")
        || document.querySelector(".stApp");
      const bodyText = clean(document.body ? document.body.innerText : "");
      const appStyles = Array.from(document.querySelectorAll("style")).filter((style) => {
        const text = String(style.textContent || "");
        return text.includes("stMainBlockContainer") || text.includes("beam-app-compact-density");
      }).length;
      window.__dgMainWidthSettleProbe.samples.push({
        at: Math.round(performance.now()),
        main: rectPayload(main),
        app: rectPayload(app),
        bodyTextLen: bodyText.length,
        inputsVisible: /Inputs|Beam design/i.test(bodyText),
        summaryVisible: /Bending\s+[-—]\s+ULS|summary-check-card/i.test(bodyText),
        appStyleTagCount: appStyles,
        viewportWidth: Math.round(window.innerWidth || 0)
      });
    } catch (err) {
      window.__dgMainWidthSettleProbe.errors.push(String(err && err.message || err));
    }
  };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        window.__dgMainWidthSettleProbe.layoutShifts.push({
          at: Math.round(entry.startTime || 0),
          value: Number(entry.value || 0),
          sourceCount: (entry.sources || []).length,
          sources: Array.from(entry.sources || []).slice(0, 8).map((source) => {
            const node = source.node && source.node.nodeType === 1 ? source.node : source.node && source.node.parentElement;
            return rectPayload(node);
          })
        });
      }
    }).observe({type: "layout-shift", buffered: true});
  } catch (err) {
    window.__dgMainWidthSettleProbe.errors.push("layout_shift_observer:" + String(err && err.message || err));
  }
  sample();
  const timer = setInterval(sample, 35);
  setTimeout(() => clearInterval(timer), 5000);
})();
"""


def _capture(base_url: str, *, recipe: str, headed: bool, wait_ms: int) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        context.add_init_script(INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe, "batch_design_open": "0"})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(max(1800, wait_ms))
        capture = dict(page.evaluate("() => window.__dgMainWidthSettleProbe || {}") or {})
        browser.close()
    capture["requested_url"] = url
    capture["recipe"] = recipe
    return capture


def _app_source_markers() -> dict[str, Any]:
    source = APP_PY.read_text(encoding="utf-8", errors="replace")
    return {
        "set_page_config_wide": 'layout="wide"' in source,
        "top_css_function_exists": "def _apply_sharp_embed_css" in source,
        "top_css_called_before_import_inputs": source.find("_apply_sharp_embed_css()") < source.find("import inputs_page"),
        "main_block_container_css": '[data-testid="stMainBlockContainer"]' in source,
        "block_container_max_width_1180": "max-width: 1180px" in source,
    }


def _first(samples: list[dict[str, Any]], predicate) -> dict[str, Any] | None:
    for row in samples:
        try:
            if predicate(row):
                return row
        except Exception:
            continue
    return None


def _summarise(capture: dict[str, Any]) -> dict[str, Any]:
    samples = [dict(row or {}) for row in list(capture.get("samples") or [])]
    shifts = [dict(row or {}) for row in list(capture.get("layoutShifts") or [])]
    widths = [
        int((row.get("main") or {}).get("width") or 0)
        for row in samples
        if (row.get("main") or {}).get("exists")
    ]
    xs = [
        int((row.get("main") or {}).get("x") or 0)
        for row in samples
        if (row.get("main") or {}).get("exists")
    ]
    first_sample = samples[0] if samples else {}
    first_main = dict(first_sample.get("main") or {})
    final_sample = samples[-1] if samples else {}
    final_main = dict(final_sample.get("main") or {})
    min_width = min(widths or [0])
    max_width = max(widths or [0])
    final_width = int(final_main.get("width") or 0)
    width_delta = max_width - min_width
    first_style = _first(samples, lambda row: int(row.get("appStyleTagCount") or 0) > 0)
    first_inputs = _first(samples, lambda row: bool(row.get("inputsVisible")))
    first_summary = _first(samples, lambda row: bool(row.get("summaryVisible")))
    shift_total = round(sum(float(row.get("value") or 0.0) for row in shifts), 6)
    early_wrapper_shift = round(
        sum(
            float(row.get("value") or 0.0)
            for row in shifts
            if int(row.get("at") or 0) < int((first_summary or {}).get("at") or 999999)
        ),
        6,
    )

    if width_delta >= 200 and first_style and first_inputs:
        decision = "STREAMLIT_WIDTH_HYDRATION_OR_APP_CSS_SETTLE"
        next_slice = "Do not patch panel layout; create readiness for earlier root/main width CSS only if source proof shows app CSS arrives after initial narrow paint."
    elif width_delta >= 200:
        decision = "WIDTH_SETTLE_UNATTRIBUTED"
        next_slice = "Capture headed/user-session proof before changing global layout CSS."
    else:
        decision = "NO_MATERIAL_WIDTH_SETTLE"
        next_slice = "Return to model/Plotly or remaining summary-card shift owners."

    return {
        "status": "PASS",
        "decision": decision,
        "sample_count": len(samples),
        "layout_shift_total": shift_total,
        "early_pre_summary_layout_shift_total": early_wrapper_shift,
        "first_main": first_main,
        "final_main": final_main,
        "min_main_width_px": min_width,
        "max_main_width_px": max_width,
        "final_main_width_px": final_width,
        "main_width_delta_px": width_delta,
        "min_main_x_px": min(xs or [0]),
        "max_main_x_px": max(xs or [0]),
        "first_app_style_at_ms": (first_style or {}).get("at"),
        "first_inputs_visible_at_ms": (first_inputs or {}).get("at"),
        "first_summary_visible_at_ms": (first_summary or {}).get("at"),
        "source_markers": _app_source_markers(),
        "recommended_next_slice": next_slice,
        "observer_errors": list(capture.get("errors") or []),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_streamlit_main_width_settle_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_streamlit_main_width_settle_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Design Guide Streamlit Main Width Settle Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{summary.get('decision')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Width delta: `{summary.get('main_width_delta_px')}` px",
        f"- Early pre-summary shift: `{summary.get('early_pre_summary_layout_shift_total')}`",
        f"- First app style: `{summary.get('first_app_style_at_ms')}` ms",
        f"- First inputs visible: `{summary.get('first_inputs_visible_at_ms')}` ms",
        f"- Recommended next slice: `{summary.get('recommended_next_slice')}`",
        "",
        "## Summary Evidence",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Rules",
        "- Snapshot-only.",
        "- No engineering behaviour, visible wording, CTA/apply, publication, render ownership, or family runtime changed.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8671)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_MAIN_WIDTH_SETTLE_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=5500)
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
            "schema": "design_guide_streamlit_main_width_settle.v1",
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
