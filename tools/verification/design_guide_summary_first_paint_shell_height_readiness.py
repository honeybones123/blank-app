"""Proof-only readiness for Inputs summary first-paint shell height tuning.

The broad smoothness profile shows first-paint/layout shift. This verifier
checks whether the temporary Inputs summary shell reserves substantially less
height than the final summary card block, which would cause Batch design and
Design Guide content to move when the summary replaces the shell.

No product code is changed by this verifier.
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
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


POLL_SCRIPT = r"""
(() => {
  window.__summaryShellHeightAudit = [];
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
    if (!el || !el.getBoundingClientRect) return null;
    const rect = el.getBoundingClientRect();
    return {
      top: Math.round(rect.top),
      bottom: Math.round(rect.bottom),
      height: Math.round(rect.height),
      width: Math.round(rect.width),
      visible: visible(el),
      text: clean(el.innerText || el.textContent).slice(0, 120)
    };
  };
  const sample = () => {
    try {
      const shell = document.querySelector(".inputs-first-paint-shell");
      const cards = Array.from(document.querySelectorAll(".summary-check-card"))
        .filter(visible);
      const cardRects = cards.map(rectPayload).filter(Boolean);
      let envelope = null;
      if (cardRects.length) {
        const top = Math.min(...cardRects.map((r) => r.top));
        const bottom = Math.max(...cardRects.map((r) => r.bottom));
        envelope = {top, bottom, height: Math.max(0, bottom - top), count: cardRects.length};
      }
      window.__summaryShellHeightAudit.push({
        at: Math.round(performance.now()),
        shell: rectPayload(shell),
        summaryEnvelope: envelope,
        bodyText: clean(document.body ? document.body.innerText : "").slice(0, 260)
      });
    } catch (err) {
      window.__summaryShellHeightAudit.push({at: Math.round(performance.now()), error: String(err && err.message || err)});
    }
  };
  sample();
  const timer = setInterval(sample, 80);
  setTimeout(() => clearInterval(timer), 7000);
})();
"""


def _capture(base_url: str, *, recipe: str, headed: bool, wait_ms: int) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.add_init_script(POLL_SCRIPT)
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe, "batch_design_open": "0"})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(max(1800, wait_ms))
        samples = list(page.evaluate("() => window.__summaryShellHeightAudit || []") or [])
        browser.close()
    return {"url": url, "recipe": recipe, "samples": samples}


def _source_current_heights() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    return {
        "normal_shell_24_5rem": '"24.5rem"' in source,
        "landing_shell_30_5rem": '"30.5rem"' in source,
        "mobile_normal_28rem": '"28rem"' in source,
        "mobile_landing_34rem": '"34rem"' in source,
    }


def _summarise(capture: dict[str, Any]) -> dict[str, Any]:
    samples = list(capture.get("samples") or [])
    shell_heights = [
        int((row.get("shell") or {}).get("height") or 0)
        for row in samples
        if isinstance(row.get("shell"), dict) and (row.get("shell") or {}).get("visible")
    ]
    envelope_heights = [
        int((row.get("summaryEnvelope") or {}).get("height") or 0)
        for row in samples
        if isinstance(row.get("summaryEnvelope"), dict) and (row.get("summaryEnvelope") or {}).get("height")
    ]
    max_shell = max(shell_heights) if shell_heights else 0
    final_envelope = envelope_heights[-1] if envelope_heights else 0
    max_envelope = max(envelope_heights) if envelope_heights else 0
    target = max(final_envelope, max_envelope)
    shortfall = max(0, int(target) - int(max_shell))
    ready = bool(max_shell and target and shortfall >= 80)
    if ready:
        decision = "READY_TO_RESERVE_SUMMARY_ENVELOPE_HEIGHT"
        next_slice = "Increase only the normal first-paint summary shell reserved height, then prove lower layout shift."
    elif max_shell and target:
        decision = "NO_MATERIAL_HEIGHT_MISMATCH"
        next_slice = "Do not tune shell height; inspect Streamlit wrapper or model-panel remount."
    else:
        decision = "INSUFFICIENT_LIVE_HEIGHT_EVIDENCE"
        next_slice = "Rerun with a slower sample interval or a live user session URL."
    return {
        "status": "PASS",
        "decision": decision,
        "ready_for_height_tuning": ready,
        "max_shell_height_px": max_shell,
        "final_summary_envelope_height_px": final_envelope,
        "max_summary_envelope_height_px": max_envelope,
        "height_shortfall_px": shortfall,
        "sample_count": len(samples),
        "source_heights": _source_current_heights(),
        "recommended_next_slice": next_slice,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_summary_first_paint_shell_height_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_summary_first_paint_shell_height_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Design Guide Summary First-Paint Shell Height Readiness",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{summary.get('decision')}`",
        f"- Ready for height tuning: `{summary.get('ready_for_height_tuning')}`",
        f"- Max shell height: `{summary.get('max_shell_height_px')}` px",
        f"- Final summary envelope: `{summary.get('final_summary_envelope_height_px')}` px",
        f"- Height shortfall: `{summary.get('height_shortfall_px')}` px",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Next Safe Slice",
        "",
        str(summary.get("recommended_next_slice") or ""),
        "",
        "## Rules",
        "- Proof-only.",
        "- No engineering behaviour, visible wording, CTA/apply, publication, render ownership, or family runtime changed.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8648)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_SUMMARY_SHELL_HEIGHT_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=7500)
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
            "schema": "design_guide_summary_first_paint_shell_height_readiness.v1",
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
