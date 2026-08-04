"""Browser/live render-layout emission cost profile for Design Guide.

Proof-only. Measures layout/visibility around Summary, Batch design, and
Design Guide after a stable same-input reload. It does not change UI layout,
publication, CTA/apply, family runtimes, visible wording, or engineering
behaviour.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
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
    _best_browser_state,
    _query,
    _start_streamlit,
    _stable_hash,
    _stable_json,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _install_layout_shift_probe(page) -> None:
    page.add_init_script(
        r"""
        (() => {
          if (window.__dgEmissionCostProbe) return;
          const probe = {layoutShiftTotal: 0, entries: [], installedAt: Date.now()};
          window.__dgEmissionCostProbe = probe;
          try {
            const observer = new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                if (entry.hadRecentInput) continue;
                probe.layoutShiftTotal += Number(entry.value || 0);
                probe.entries.push({
                  value: Number(entry.value || 0),
                  startTime: Number(entry.startTime || 0),
                  sources: Array.from(entry.sources || []).slice(0, 5).map((source) => ({
                    text: source.node ? String(source.node.innerText || source.node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120) : null,
                    tag: source.node ? String(source.node.tagName || "").toLowerCase() : null
                  }))
                });
              }
            });
            observer.observe({type: "layout-shift", buffered: true});
          } catch (err) {
            probe.error = String(err && err.message ? err.message : err);
          }
        })();
        """
    )


def _layout_snapshot(page, *, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
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
              const payload = (el) => {
                if (!el) return {exists: false, visible: false};
                const rect = el.getBoundingClientRect();
                return {
                  exists: true,
                  visible: visible(el),
                  in_viewport: rect.bottom >= 0 && rect.top <= window.innerHeight,
                  fully_in_viewport: rect.top >= 0 && rect.bottom <= window.innerHeight,
                  text: clean(el.innerText || el.textContent).slice(0, 260),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 160),
                  rect: {
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom),
                    left: Math.round(rect.left),
                    right: Math.round(rect.right),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                  }
                };
              };
              const all = Array.from(document.querySelectorAll("body *")).filter(visible);
              const shortestMatch = (regex, rejectRegex = null) => {
                const matches = all.filter((el) => {
                  const text = clean(el.innerText || el.textContent);
                  return regex.test(text) && !(rejectRegex && rejectRegex.test(text));
                }).sort((a, b) => {
                  const at = clean(a.innerText || a.textContent);
                  const bt = clean(b.innerText || b.textContent);
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return at.length - bt.length || ar.top - br.top || ar.height - br.height;
                });
                return matches[0] || null;
              };
              const summaryCards = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                if (!/Bending\s+.\s+ULS|Shear\s+.\s+ULS|Crack control\s+.\s+SLS|Deflection\s+.\s+SLS/i.test(text)) return false;
                if (/Beam design|Inputs|Batch design|Design Guide/i.test(text) && text.length > 900) return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 300 && rect.height >= 35;
              });
              const explicitDgCards = Array.from(document.querySelectorAll('[data-testid="design-guide-card"], details.fast-guidance-item, .fast-guidance-item, .dg-card')).filter(visible);
              const fallbackDgCards = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                if (/Debug session state|Design Guide Debug/i.test(text)) return false;
                if (!/Design is efficient|Strengthening required|Bending repair blocked|Shear repair blocked|repair blocked|repair is blocked|cleanup required|Cleanup required|Design Guide blocker proof incomplete|Apply recommendation|Run one-click auto design/i.test(text)) return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 300 && rect.height >= 35 && text.length < 2500;
              });
              const dgCards = explicitDgCards.length ? explicitDgCards : fallbackDgCards;
              const elements = {
                inputs_heading: payload(shortestMatch(/^Inputs$/i)),
                summary_band: payload(summaryCards.sort((a, b) => b.getBoundingClientRect().height - a.getBoundingClientRect().height)[0] || null),
                batch_design_heading: payload(shortestMatch(/^Batch design$/i)),
                batch_design_card: payload(shortestMatch(/Active set|Active beam|Show Manager|Hide Manager/i)),
                design_guide_heading: payload(shortestMatch(/^Design Guide$/i, /Debug session state|Design Guide Debug/i)),
                design_guide_card: payload(dgCards.sort((a, b) => b.getBoundingClientRect().height - a.getBoundingClientRect().height)[0] || null),
                proof_pending_shell: payload(shortestMatch(/Checking design guidance|Reviewing strength|StrengthDetailingServiceabilityCleanup options/i))
              };
              const gap = (upper, lower) => {
                if (!upper || !lower || !upper.exists || !lower.exists) return null;
                return Math.round((lower.rect.top || 0) - (upper.rect.bottom || 0));
              };
              const probe = window.__dgEmissionCostProbe || {};
              return {
                label,
                performance_now_ms: Math.round(performance.now()),
                timestamp_ms: Date.now(),
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scroll: {x: Math.round(window.scrollX || 0), y: Math.round(window.scrollY || 0)},
                elements,
                counts: {
                  visible_summary_candidates: summaryCards.length,
                  visible_design_guide_card_candidates: dgCards.length
                },
                gaps: {
                  inputs_to_summary: gap(elements.inputs_heading, elements.summary_band),
                  summary_to_batch: gap(elements.summary_band, elements.batch_design_heading),
                  batch_card_to_design_guide: gap(elements.batch_design_card, elements.design_guide_heading),
                  design_guide_heading_to_card: gap(elements.design_guide_heading, elements.design_guide_card)
                },
                layout_shift_total: Number(probe.layoutShiftTotal || 0),
                layout_shift_entries: Array.from(probe.entries || []).slice(-20),
                layout_probe_error: probe.error || null
              };
            }
            """,
            label,
        )
        or {}
    )


def _capture(base_url: str, *, recipe: str, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        _install_layout_shift_probe(page)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        samples: list[dict[str, Any]] = []
        for label, wait_ms, reload_first in (
            ("initial_settled", 3500, False),
            ("reload_early", 700, True),
            ("reload_settled", 3500, False),
            ("reload_scrolled_to_design_guide", 700, False),
        ):
            if reload_first:
                page.reload(wait_until="domcontentloaded", timeout=90_000)
            if label == "reload_scrolled_to_design_guide":
                page.evaluate(
                    r"""
                    () => {
                      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
                      const matches = Array.from(document.querySelectorAll("body *")).filter((el) => clean(el.innerText || el.textContent) === "Design Guide");
                      const target = matches.find((el) => !/Debug/i.test(clean(el.parentElement ? el.parentElement.innerText || "" : ""))) || matches[0];
                      if (target && target.scrollIntoView) target.scrollIntoView({block: "start", inline: "nearest"});
                    }
                    """
                )
            page.wait_for_timeout(wait_ms)
            state = _best_browser_state(page, recipe, timeout_s=8.0)
            samples.append(
                {
                    "label": label,
                    "layout": _layout_snapshot(page, label=label),
                    "browser_state": {
                        "recipe": state.get("browser_recipe"),
                        "phase": state.get("browser_probe_phase") or state.get("probe_phase"),
                        "authority_hash_values": (
                            ((state.get("design_guide_probe") or {}).get("debug_bundle") or {}).get("final_publication_authority_hash"),
                            (((state.get("design_guide_probe") or {}).get("debug_bundle") or {}).get("final_publication_verifier_payload") or {}).get("final_publication_authority_hash"),
                        ),
                        "display_hash_values": (
                            ((state.get("design_guide_probe") or {}).get("debug_bundle") or {}).get("final_publication_display_hash"),
                            (((state.get("design_guide_probe") or {}).get("debug_bundle") or {}).get("final_publication_verifier_payload") or {}).get("final_publication_display_hash"),
                        ),
                    },
                }
            )
        browser.close()
    return {"url": url, "recipe": recipe, "samples": samples}


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    samples = list(capture.get("samples") or [])
    settled = next((sample for sample in samples if sample.get("label") == "reload_settled"), samples[-1] if samples else {})
    scrolled = next((sample for sample in samples if sample.get("label") == "reload_scrolled_to_design_guide"), {})
    layout = dict(settled.get("layout") or {})
    elements = dict(layout.get("elements") or {})
    dg_card = dict(elements.get("design_guide_card") or {})
    dg_heading = dict(elements.get("design_guide_heading") or {})
    proof_shell = dict(elements.get("proof_pending_shell") or {})
    card_exists = bool(dg_card.get("exists"))
    card_in_viewport = bool(dg_card.get("in_viewport"))
    card_visible = bool(dg_card.get("visible"))
    card_visible_after_scroll = bool((((scrolled.get("layout") or {}).get("elements") or {}).get("design_guide_card") or {}).get("visible"))
    layout_shift = float(layout.get("layout_shift_total") or 0.0)
    gaps = dict(layout.get("gaps") or {})

    if card_exists and not card_in_viewport and card_visible_after_scroll:
        diagnosis = "CARD_RENDERED_BELOW_VIEWPORT"
        next_slice = "Tune scroll/anchor behavior or viewport tests; do not change publication/render truth."
    elif not card_exists and bool(dg_heading.get("exists")):
        diagnosis = "DESIGN_GUIDE_HEADING_WITHOUT_CARD"
        next_slice = "Audit final-card DOM emission after Design Guide heading before layout bypass work."
    elif proof_shell.get("visible"):
        diagnosis = "PROOF_PENDING_SHELL_VISIBLE"
        next_slice = "Audit final-card readiness gate; shell is visible after stable publication."
    elif layout_shift > 0.1:
        diagnosis = "LAYOUT_SHIFT_DURING_STABLE_RELOAD"
        next_slice = "Identify layout-shift source entries before changing CSS/layout."
    else:
        diagnosis = "STABLE_RENDER_LAYOUT_OK"
        next_slice = "Move to targeted candidate-evaluation unique-work profile or browser-probe payload rebuild reduction."

    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "design_guide_heading_exists": bool(dg_heading.get("exists")),
        "design_guide_card_exists": card_exists,
        "design_guide_card_visible": card_visible,
        "design_guide_card_in_viewport": card_in_viewport,
        "design_guide_card_visible_after_scroll": card_visible_after_scroll,
        "proof_pending_shell_visible": bool(proof_shell.get("visible")),
        "layout_shift_total": layout_shift,
        "gaps": gaps,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Render/Layout Emission Cost Profile",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Card exists: `{cls.get('design_guide_card_exists')}`",
        f"- Card visible: `{cls.get('design_guide_card_visible')}`",
        f"- Card in viewport: `{cls.get('design_guide_card_in_viewport')}`",
        f"- Card visible after scroll: `{cls.get('design_guide_card_visible_after_scroll')}`",
        f"- Layout shift total: `{cls.get('layout_shift_total')}`",
        "",
        "## Gaps",
        "",
        "```json",
        json.dumps(cls.get("gaps") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_render_layout_emission_cost_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_layout_emission_cost_profile_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8620)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_LAYOUT_EMISSION_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
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
        capture = _capture(base_url, recipe=str(args.recipe), headed=bool(args.headed))
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_render_layout_emission_cost_profile.v1",
            "created_at": created_at,
            "status": classification.get("status"),
            "product_behaviour_changed": False,
            "base_url": base_url,
            "classification": classification,
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps(classification, indent=2, sort_keys=True))
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
