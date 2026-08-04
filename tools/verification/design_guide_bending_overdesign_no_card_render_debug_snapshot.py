"""Focused live debug snapshot for BENDING_OVERDESIGN_GOVERNS no-card rendering.

This verifier is proof-only. It opens the known BENDING_OVERDESIGN live recipe
and records the publication payload, DOM card/button state, and render debug
markers that decide whether the final Design Guide card is painted.
"""

from __future__ import annotations

import json
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

from tools.verification.design_guide_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _browser_visible_payload,
    _capture_visual_snapshot,
    _datetime_stamp,
)
from tools.verification.design_guide_family_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _wait_for_final_design_guide_card,
)
from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    TRACER_PATH,
    _query,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
)
from tools.verification.run_family_10_fuzz_audit import (  # noqa: E402
    _action_button_probe,
    _extract_publication_probe,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
RECIPE = "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED"
SCENARIO_ID = "BENDING_OVERDESIGN_NO_CARD_RENDER_DEBUG"


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dig(source: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _interesting_debug_sources(state: dict[str, Any]) -> dict[str, Any]:
    debug_sources = _safe_dict(state.get("browser_debug_sources"))
    interesting: dict[str, Any] = {}
    for source_name, source_value in debug_sources.items():
        source = _safe_dict(source_value)
        if not source:
            continue
        interesting[source_name] = {
            "keys": sorted(source.keys()),
            "final_publication_verifier_payload": _safe_dict(
                source.get("final_publication_verifier_payload")
            ),
            "actual_card_render_probe": _safe_dict(source.get("actual_card_render_probe")),
            "button_contract": _safe_dict(
                source.get("button_contract") or source.get("primary_button_contract")
            ),
            "display_truth": _safe_dict(source.get("display_truth")),
            "render_markers": {
                key: source.get(key)
                for key in sorted(source.keys())
                if "render" in str(key).lower()
                or "card" in str(key).lower()
                or "publication" in str(key).lower()
                or "shell" in str(key).lower()
                or "slot" in str(key).lower()
            },
        }
    return interesting


def _publication_debug_markers(state: dict[str, Any]) -> dict[str, Any]:
    bundle = _safe_dict(_dig(state, ("design_guide_probe", "debug_bundle")))
    browser_debug = _safe_dict(state.get("browser_debug_probe"))
    shared = _safe_dict(state.get("browser_shared_probe"))
    marker_sources = {
        "debug_bundle": bundle,
        "browser_debug_probe": browser_debug,
        "browser_shared_probe": shared,
        "top_level": state,
    }
    wanted_fragments = (
        "render_final_publication_payload",
        "final_publication",
        "actual_card",
        "design_guide_final_panel",
        "pre_widget",
        "rendered",
        "deleted",
        "shell",
        "slot",
        "button_contract",
        "card",
    )
    markers: dict[str, Any] = {}
    for source_name, source in marker_sources.items():
        if not isinstance(source, dict):
            continue
        markers[source_name] = {
            key: source.get(key)
            for key in sorted(source.keys())
            if any(fragment in str(key) for fragment in wanted_fragments)
        }
    return markers


def _dom_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const bodyText = String(document.body && document.body.innerText || "");
              const headings = Array.from(document.querySelectorAll("h1,h2,h3,[role='heading']"))
                .filter(visible)
                .map((el) => ({text: clean(el.innerText || el.textContent), rect: el.getBoundingClientRect().toJSON ? el.getBoundingClientRect().toJSON() : {}}));
              const guideCards = Array.from(document.querySelectorAll("[data-testid='design-guide-card'],[data-final-publication-hash],[data-publication-hash]"))
                .filter(visible)
                .map((el) => ({
                  tag: String(el.tagName || "").toLowerCase(),
                  text: clean(el.innerText || el.textContent).slice(0, 600),
                  attrs: Object.fromEntries(Array.from(el.attributes || []).map((attr) => [attr.name, attr.value]).filter(([k, v]) => /guide|publication|authority|card|cta|hash|state/i.test(k + " " + v))),
                  rect: (() => { const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}; })()
                }));
              const designGuideIndex = bodyText.lastIndexOf("Design Guide");
              return {
                url: window.location.href,
                body_text_sample: designGuideIndex >= 0 ? bodyText.slice(designGuideIndex, designGuideIndex + 1600) : bodyText.slice(0, 1600),
                design_guide_heading_count: (bodyText.match(/Design Guide/g) || []).length,
                headings,
                guide_cards: guideCards,
                action_button_texts: Array.from(document.querySelectorAll("button"))
                  .filter(visible)
                  .map((el) => clean(el.innerText || el.textContent))
                  .filter((text) => /Apply|Run one-click|Design Guide|cleanup|repair/i.test(text)),
              };
            }
            """
        )
    )


def _wait_for_settled_browser_publication(page, *, timeout_s: float = 45.0) -> dict[str, Any]:
    deadline = time.monotonic() + max(5.0, float(timeout_s or 45.0))
    last_state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            state = _load_browser_state(page, timeout_s=2.0)
        except Exception:
            time.sleep(0.5)
            continue
        last_state = state
        final_payload = _safe_dict(state.get("final_publication_verifier_payload"))
        debug_bundle = _safe_dict(_dig(state, ("design_guide_probe", "debug_bundle")))
        if final_payload.get("publication_hash"):
            return state
        if _safe_dict(debug_bundle.get("final_publication_verifier_payload")).get("publication_hash"):
            return state
        if state.get("browser_shared_probe") and state.get("summary_state_probe"):
            # The page has settled enough to expose the shared probes; keep
            # polling briefly for publication because this debug snapshot is
            # specifically about a missing rendered publication.
            time.sleep(0.75)
            continue
        time.sleep(0.5)
    return last_state


def _write_artifacts(result: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _datetime_stamp()
    json_path = ARTIFACT_DIR / f"design_guide_bending_overdesign_no_card_render_debug_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_bending_overdesign_no_card_render_debug_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# BENDING_OVERDESIGN No-Card Render Debug Snapshot",
                "",
                f"Result: **{result.get('status')}**",
                f"Recipe: `{RECIPE}`",
                "",
                "## Key Findings",
                f"- Final publication present: `{result.get('final_publication_present')}`",
                f"- Final publication selected family: `{result.get('publication_probe', {}).get('selected_family_id')}`",
                f"- Final publication outcome: `{result.get('publication_probe', {}).get('outcome_state')}`",
                f"- Final publication CTA enabled: `{result.get('publication_probe', {}).get('cta', {}).get('enabled')}`",
                f"- Visible final card ready: `{result.get('final_card_probe', {}).get('final_card_ready')}`",
                f"- Enabled visible action buttons: `{result.get('button_probe', {}).get('enabled_action_count')}`",
                f"- Render drop classification: `{result.get('render_drop_classification')}`",
                "",
                "## Artifacts",
                f"- JSON: `{json_path}`",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    port = 8527
    base_url = f"http://127.0.0.1:{port}"
    process: subprocess.Popen | None = None
    result: dict[str, Any] = {
        "recipe": RECIPE,
        "scenario_id": SCENARIO_ID,
        "status": "FAIL",
    }
    try:
        process = _start_streamlit(port)
        _wait_for_http(base_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport={"width": 1600, "height": 1100})
                page = context.new_page()
                page.set_default_timeout(30_000)
                tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
                page.goto(
                    _query(
                        base_url,
                        {
                            "page": "inputs",
                            "browser_recipe": RECIPE,
                            "browser_test_mode": "1",
                            "cid": SCENARIO_ID,
                        },
                    ),
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )
                run_end_event, _ = _wait_for_run_end(tracer_offset, timeout_s=20.0)
                try:
                    page.get_by_label("Browser state").wait_for(state="attached", timeout=30_000)
                except PlaywrightTimeoutError:
                    pass
                state = _wait_for_settled_browser_publication(page, timeout_s=45.0)
                final_card_probe = _wait_for_final_design_guide_card(page, timeout_s=12.0)
                # Re-read after the card wait because the hidden browser probe is
                # stamped late in Streamlit's render cycle.
                refreshed_state = _wait_for_settled_browser_publication(page, timeout_s=5.0)
                if _safe_dict(refreshed_state.get("final_publication_verifier_payload")).get("publication_hash"):
                    state = refreshed_state
                screenshot = ARTIFACT_DIR / f"design_guide_bending_overdesign_no_card_render_debug_{_datetime_stamp()}.png"
                visual_snapshot = _capture_visual_snapshot(
                    page,
                    scenario_id=SCENARIO_ID,
                    screenshot_path=screenshot,
                )
                visible_payload = _browser_visible_payload(page)
                publication_probe = _extract_publication_probe(state)
                button_probe = _action_button_probe(page)
                dom_probe = _dom_probe(page)
                final_payload = _safe_dict(state.get("final_publication_verifier_payload"))
                cta = _safe_dict(final_payload.get("cta"))
                final_publication_present = bool(final_payload.get("publication_hash"))
                visible_card_ready = bool(final_card_probe.get("final_card_ready"))
                enabled_action_count = int(button_probe.get("enabled_action_count") or 0)
                guide_cards = list(dom_probe.get("guide_cards") or [])
                guide_card_count = len(guide_cards)
                visible_text = str(final_card_probe.get("text_sample") or "")
                duplicate_terminal_title_count = visible_text.count(
                    "Bending cleanup - one-click terminal optimisation"
                )
                strict_failures: list[str] = []
                if final_publication_present and not visible_card_ready:
                    classification = "PUBLICATION_PRESENT_BUT_CARD_NOT_RENDERED"
                elif final_publication_present and visible_card_ready and enabled_action_count <= 0 and cta.get("enabled"):
                    classification = "PUBLICATION_PRESENT_CARD_RENDERED_BUT_CTA_NOT_RENDERED"
                elif final_publication_present and visible_card_ready:
                    classification = "PUBLICATION_RENDERED"
                else:
                    classification = "PUBLICATION_MISSING"
                if not final_publication_present:
                    strict_failures.append("final_publication_missing")
                if not visible_card_ready:
                    strict_failures.append("visible_final_card_missing")
                if guide_card_count != 1:
                    strict_failures.append(f"expected_one_visible_design_guide_card_got_{guide_card_count}")
                if duplicate_terminal_title_count > 2:
                    # The title appears once in the card and once in the Apply
                    # button label. More than that means the same card has been
                    # rendered twice in the live DOM.
                    strict_failures.append(
                        f"duplicated_terminal_card_title_count_{duplicate_terminal_title_count}"
                    )
                if enabled_action_count != 1:
                    strict_failures.append(f"expected_one_enabled_apply_action_got_{enabled_action_count}")
                result.update(
                    {
                        "status": "PASS" if not strict_failures else "FAIL",
                        "final_publication_present": final_publication_present,
                        "publication_probe": publication_probe,
                        "final_publication_verifier_payload": final_payload,
                        "final_card_probe": final_card_probe,
                        "button_probe": button_probe,
                        "dom_probe": dom_probe,
                        "strict_live_render_assertions": {
                            "guide_card_count": guide_card_count,
                            "duplicate_terminal_title_count": duplicate_terminal_title_count,
                            "enabled_action_count": enabled_action_count,
                            "failures": list(strict_failures),
                        },
                        "visible_payload_summary": {
                            "designGuideCards": visible_payload.get("designGuideCards"),
                            "buttons": visible_payload.get("buttons"),
                            "guideRelated": visible_payload.get("guideRelated"),
                            "bodyTextLength": visible_payload.get("bodyTextLength"),
                        },
                        "visual_snapshot_summary": {
                            "design_guide": _safe_dict(visual_snapshot.get("design_guide")),
                            "checks": _safe_dict(visual_snapshot.get("checks")),
                            "screenshot": str(screenshot),
                        },
                        "publication_debug_markers": _publication_debug_markers(state),
                        "interesting_debug_sources": _interesting_debug_sources(state),
                        "render_drop_classification": classification,
                        "run_end_event": run_end_event,
                        "browser_state_keys": sorted(state.keys()),
                    }
                )
                context.close()
            finally:
                browser.close()
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
    json_path, md_path = _write_artifacts(result)
    print(json.dumps({"status": result.get("status"), "json": str(json_path), "md": str(md_path)}, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
