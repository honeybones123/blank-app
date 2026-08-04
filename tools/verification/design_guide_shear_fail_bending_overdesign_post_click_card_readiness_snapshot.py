"""Post-click card readiness snapshot for SHEAR_FAIL_BENDING_OVERDESIGN.

Proof-only. This browser/live verifier targets the remaining architecture
partial:

    SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS

It proves what happens after the real Apply/one-click CTA is clicked:

* whether the Apply changes page/check output,
* whether the post-click Design Guide card becomes verifier-ready,
* whether the page is stuck in a pending shell,
* whether a card exists but is out of viewport,
* whether DOM readiness markers are missing,
* whether rebuild/sampling keeps running too long, and
* whether browser-state/final-publication hashes look stale or non-final.

It does not change family runtimes, contracts, CTA rendering, publication,
apply routing, visible wording, or product behaviour.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification import design_guide_product_path_gate as product_gate  # noqa: E402
from tools.verification.design_guide_partial_family_browser_apply_noop_replay import (  # noqa: E402
    ReplayAttempt,
    _browser_recipe_probe,
    _click_first_enabled_action,
    _enabled_action_buttons,
    _family_matches,
    _family_selection,
    _goto_recipe,
    _output_fingerprint,
    _selected_family_ids,
    _stable_hash,
)
from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FAMILY_ID = "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
ATTEMPT = ReplayAttempt(
    name="shear_fail_bending_overdesign_shear_only",
    family_id=FAMILY_ID,
    recipe="B_shear_under_only",
)


def _compact_text(value: Any, limit: int = 420) -> str:
    return " ".join(str(value or "").split())[:limit]


def _dom_readiness_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            """
            () => {
              const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style && style.visibility !== 'hidden' && style.display !== 'none' &&
                  rect.width > 0 && rect.height > 0;
              };
              const rectObj = (el) => {
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {
                  x: r.x, y: r.y, width: r.width, height: r.height,
                  top: r.top, bottom: r.bottom,
                  inViewport: r.bottom > 0 && r.top < window.innerHeight,
                };
              };
              const text = (el) => (el && (el.innerText || el.textContent || '').trim()) || '';
              const body = text(document.body);
              const allCards = Array.from(document.querySelectorAll("[data-testid='design-guide-card'], .fast-guidance-item"));
              const visibleCards = allCards.filter(visible);
              const pendingNodes = Array.from(document.querySelectorAll(
                "[data-testid='design-guide-pending-shell'], .design-guide-pending-shell, .dg-pending-shell, [data-design-guide-pending]"
              ));
              const readyMarkers = Array.from(document.querySelectorAll(
                "[data-final-publication-authority-hash], [data-final-publication-display-hash], [data-final-publication-cta-hash], [data-render-contract-enabled], [data-render-cta-enabled]"
              ));
              const buttons = Array.from(document.querySelectorAll("button"))
                .filter(visible)
                .map((el) => ({text: text(el), disabled: !!el.disabled, rect: rectObj(el)}));
              const scrollEls = Array.from(document.querySelectorAll("main, section, div"))
                .filter((el) => el.scrollHeight > el.clientHeight + 40)
                .map((el) => ({
                  tag: el.tagName,
                  testid: el.getAttribute('data-testid') || '',
                  className: String(el.className || ''),
                  scrollTop: el.scrollTop,
                  scrollHeight: el.scrollHeight,
                  clientHeight: el.clientHeight,
                }))
                .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
              return {
                body_text_length: body.length,
                body_text_sample: body.replace(/\\s+/g, ' ').trim().slice(0, 900),
                contains_design_guide_heading: /Design Guide/i.test(body),
                contains_pending_text: /Checking design guidance|Reviewing strength|StrengthDetailingServiceabilityCleanup options/i.test(body),
                contains_apply_feedback: /Applying one-click design|Applying|queued/i.test(body),
                contains_error_text: /Traceback|RuntimeError|Exception|policy violation/i.test(body),
                all_card_count: allCards.length,
                visible_card_count: visibleCards.length,
                card_text_samples: visibleCards.slice(0, 3).map((el) => text(el).replace(/\\s+/g, ' ').trim().slice(0, 700)),
                card_rects: visibleCards.slice(0, 3).map(rectObj),
                pending_node_count: pendingNodes.length,
                visible_pending_node_count: pendingNodes.filter(visible).length,
                pending_text_samples: pendingNodes.filter(visible).slice(0, 3).map((el) => text(el).replace(/\\s+/g, ' ').trim().slice(0, 500)),
                ready_marker_count: readyMarkers.length,
                visible_ready_marker_count: readyMarkers.filter(visible).length,
                button_texts: buttons.map((row) => row.text).filter(Boolean),
                window_scroll_y: window.scrollY,
                viewport_height: window.innerHeight,
                document_height: document.documentElement.scrollHeight,
                primary_scroll_top: scrollEls.length ? scrollEls[0].scrollTop : window.scrollY,
                scroll_containers: scrollEls.slice(0, 4),
              };
            }
            """
        )
    )


def _publication_probe(browser_state: dict[str, Any]) -> dict[str, Any]:
    publication = dict(browser_state.get("final_design_guide_publication") or {})
    guidance = dict(browser_state.get("guidance_probe") or {})
    compute = dict(browser_state.get("guidance_compute_probe") or {})
    render = dict(browser_state.get("design_guide_render_probe") or {})
    session = dict(browser_state.get("final_publication_verifier_payload") or {})
    return {
        "browser_state_keys": sorted(str(key) for key in browser_state.keys())[:120],
        "browser_recipe_probe": _browser_recipe_probe(browser_state),
        "final_publication_present": bool(publication),
        "publication_hash": str(
            publication.get("publication_hash")
            or session.get("publication_hash")
            or guidance.get("publication_hash")
            or ""
        ),
        "final_publication_authority_hash": str(
            publication.get("final_publication_authority_hash")
            or session.get("final_publication_authority_hash")
            or ""
        ),
        "display_hash": str(
            publication.get("display_hash")
            or publication.get("final_publication_display_hash")
            or session.get("display_hash")
            or session.get("final_publication_display_hash")
            or render.get("final_publication_display_hash")
            or ""
        ),
        "cta_hash": str(
            publication.get("cta_hash")
            or publication.get("final_publication_cta_hash")
            or session.get("cta_hash")
            or session.get("final_publication_cta_hash")
            or render.get("final_publication_cta_hash")
            or ""
        ),
        "selected_family_id": str(
            publication.get("selected_family_id")
            or guidance.get("selected_family_id")
            or guidance.get("selected_family")
            or compute.get("selected_family_id")
            or compute.get("selected_family")
            or ""
        ),
        "outcome_state": str(publication.get("outcome_state") or guidance.get("outcome_state") or ""),
        "post_click_state": str(
            publication.get("post_click_design_guide_state")
            or guidance.get("post_click_design_guide_state")
            or ""
        ),
        "render_probe_keys": sorted(str(key) for key in render.keys())[:80],
    }


def _sample(page, *, label: str, elapsed_s: float, before_hash: str | None = None) -> dict[str, Any]:
    state_error = ""
    browser_state: dict[str, Any] = {}
    try:
        browser_state = _load_browser_state(page, timeout_s=3.0)
    except Exception as exc:  # proof-only: capture, do not fail the run.
        state_error = f"{type(exc).__name__}: {exc}"
    snapshot = product_gate._snapshot(page)
    dom = _dom_readiness_probe(page)
    output_hash = _stable_hash(_output_fingerprint(snapshot, browser_state))
    return {
        "label": label,
        "elapsed_seconds": round(elapsed_s, 3),
        "snapshot_card_count": int(snapshot.get("card_count") or 0),
        "snapshot_first_card_text": _compact_text(snapshot.get("first_card_text"), 620),
        "snapshot_family_selection": _family_selection(snapshot),
        "selected_family_ids": _selected_family_ids(snapshot, browser_state),
        "visible_cta_buttons": _enabled_action_buttons(snapshot),
        "output_hash": output_hash,
        "output_changed_from_before": bool(before_hash and output_hash != before_hash),
        "dom": dom,
        "publication": _publication_probe(browser_state),
        "browser_state_error": state_error,
    }


def _classify(
    samples: list[dict[str, Any]],
    *,
    before_hash: str,
    before_card_text_hash: str,
    min_ready_elapsed_s: float,
) -> dict[str, Any]:
    post_samples = [sample for sample in samples if sample["label"].startswith("post_click")]
    final = post_samples[-1] if post_samples else samples[-1]
    ready_samples = [
        sample
        for sample in post_samples
        if int(sample.get("snapshot_card_count") or 0) > 0
        and str(sample.get("snapshot_first_card_text") or "").strip()
        and float(sample.get("elapsed_seconds") or 0.0) >= min_ready_elapsed_s
        and _stable_hash(sample.get("snapshot_first_card_text") or "") != before_card_text_hash
    ]
    stale_card_samples = [
        sample
        for sample in post_samples
        if int(sample.get("snapshot_card_count") or 0) > 0
        and str(sample.get("snapshot_first_card_text") or "").strip()
        and _stable_hash(sample.get("snapshot_first_card_text") or "") == before_card_text_hash
    ]
    pending_samples = [
        sample
        for sample in post_samples
        if bool(((sample.get("dom") or {}).get("contains_pending_text")))
        or int(((sample.get("dom") or {}).get("visible_pending_node_count") or 0)) > 0
    ]
    card_dom_samples = [
        sample
        for sample in post_samples
        if int(((sample.get("dom") or {}).get("all_card_count") or 0)) > 0
    ]
    visible_card_samples = [
        sample
        for sample in post_samples
        if int(((sample.get("dom") or {}).get("visible_card_count") or 0)) > 0
    ]
    ready_marker_samples = [
        sample
        for sample in post_samples
        if int(((sample.get("dom") or {}).get("ready_marker_count") or 0)) > 0
    ]
    output_changed_samples = [
        sample for sample in post_samples if bool(sample.get("output_changed_from_before"))
    ]
    publication_hashes = [
        str(((sample.get("publication") or {}).get("publication_hash") or ""))
        for sample in post_samples
    ]
    non_empty_publication_hashes = [value for value in publication_hashes if value]
    unique_publication_hashes = sorted(set(non_empty_publication_hashes))

    if ready_samples:
        classification = "POST_CLICK_CARD_READY"
        reason = "A visible non-empty Design Guide card became available after Apply."
    elif output_changed_samples and stale_card_samples and not ready_samples:
        classification = "STALE_PRE_CLICK_CARD_AFTER_OUTPUT_CHANGE"
        reason = "Apply changed output, but the visible Design Guide card text stayed identical to the pre-click card."
    elif pending_samples and not card_dom_samples:
        classification = "STUCK_PENDING_SHELL"
        reason = "Post-click samples kept showing pending-shell text and no card DOM."
    elif card_dom_samples and not visible_card_samples:
        classification = "CARD_OUT_OF_VIEW_OR_HIDDEN"
        reason = "Card DOM existed after Apply but no visible card was exposed to the verifier."
    elif output_changed_samples and not ready_marker_samples:
        classification = "MISSING_DOM_READY_MARKER_AFTER_OUTPUT_CHANGE"
        reason = "Apply changed output, but no final publication/card readiness DOM markers appeared."
    elif output_changed_samples and not ready_samples:
        classification = "REBUILDING_TOO_LONG_AFTER_OUTPUT_CHANGE"
        reason = "Apply changed output, but no verifier-ready card appeared during the sampling window."
    elif unique_publication_hashes and len(unique_publication_hashes) > 1:
        classification = "POSSIBLE_STALE_OR_NON_FINAL_PUBLICATION_CHURN"
        reason = "Final-publication hashes changed across post-click samples without a verifier-ready card."
    else:
        classification = "POST_CLICK_CARD_READINESS_UNCLASSIFIED"
        reason = "The snapshot did not prove card readiness, pending shell, hidden card, or publication churn."

    return {
        "classification": classification,
        "reason": reason,
        "post_click_card_ready": bool(ready_samples),
        "apply_output_changed": bool(output_changed_samples),
        "stuck_pending_shell": bool(pending_samples and not card_dom_samples),
        "card_dom_present": bool(card_dom_samples),
        "visible_card_present": bool(visible_card_samples),
        "ready_markers_present": bool(ready_marker_samples),
        "publication_hash_churn": len(unique_publication_hashes) > 1,
        "unique_publication_hashes": unique_publication_hashes,
        "before_output_hash": before_hash,
        "before_card_text_hash": before_card_text_hash,
        "final_output_hash": final.get("output_hash"),
        "final_sample_label": final.get("label"),
        "stale_pre_click_card_samples": len(stale_card_samples),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    classification = dict(payload.get("classification") or {})
    lines = [
        "# SHEAR_FAIL_BENDING_OVERDESIGN Post-Click Card Readiness Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Classification: `{classification.get('classification')}`",
        f"Reason: {classification.get('reason')}",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        f"- Apply output changed: `{classification.get('apply_output_changed')}`",
        f"- Post-click card ready: `{classification.get('post_click_card_ready')}`",
        f"- Stuck pending shell: `{classification.get('stuck_pending_shell')}`",
        f"- Card DOM present: `{classification.get('card_dom_present')}`",
        f"- Visible card present: `{classification.get('visible_card_present')}`",
        f"- Ready markers present: `{classification.get('ready_markers_present')}`",
        f"- Publication hash churn: `{classification.get('publication_hash_churn')}`",
        "",
        "## Samples",
        "",
        "| Label | Elapsed s | Card Count | Pending Text | Output Changed | Publication Hash | Card Text |",
        "| --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for sample in payload.get("samples") or []:
        dom = dict(sample.get("dom") or {})
        publication = dict(sample.get("publication") or {})
        lines.append(
            "| `{label}` | `{elapsed}` | `{count}` | `{pending}` | `{changed}` | `{pub}` | {text} |".format(
                label=sample.get("label"),
                elapsed=sample.get("elapsed_seconds"),
                count=sample.get("snapshot_card_count"),
                pending=dom.get("contains_pending_text"),
                changed=sample.get("output_changed_from_before"),
                pub=publication.get("publication_hash"),
                text=_compact_text(sample.get("snapshot_first_card_text"), 180).replace("|", "\\|"),
            )
        )
    lines.extend(["", "## Screenshots", ""])
    for name, screenshot in (payload.get("screenshots") or {}).items():
        lines.append(f"- `{name}`: `{screenshot}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8571)
    parser.add_argument("--reuse-existing-server", action="store_true", default=False)
    parser.add_argument("--headed", action="store_true", default=False)
    parser.add_argument("--sample-window-sec", type=float, default=95.0)
    parser.add_argument("--sample-interval-sec", type=float, default=5.0)
    parser.add_argument("--ready-timeout-sec", type=float, default=75.0)
    parser.add_argument("--card-timeout-sec", type=float, default=75.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = ARTIFACT_DIR / f"design_guide_shear_fail_bending_overdesign_post_click_card_readiness_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{args.port}"

    process = None
    if not args.reuse_existing_server:
        process = _start_streamlit(args.port)
    else:
        _wait_for_http(base_url, timeout_s=45.0)

    payload: dict[str, Any] = {
        "schema": "design_guide_shear_fail_bending_overdesign_post_click_card_readiness_snapshot.v1",
        "status": "PASS",
        "created_at": stamp,
        "family_id": FAMILY_ID,
        "attempt": {
            "name": ATTEMPT.name,
            "recipe": ATTEMPT.recipe,
        },
        "product_behaviour_changed": False,
        "browser_test_mode": True,
        "samples": [],
        "screenshots": {},
        "failures": [],
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = context.new_page()
            try:
                _goto_recipe(
                    page,
                    base_url,
                    ATTEMPT.recipe,
                    ready_timeout_ms=int(max(args.ready_timeout_sec, 5.0) * 1000),
                    card_timeout_ms=int(max(args.card_timeout_sec, 5.0) * 1000),
                )
                before_state = _load_browser_state(page, timeout_s=45.0)
                before_snapshot = product_gate._snapshot(page)
                if before_state.get("browser_recipe") != ATTEMPT.recipe:
                    payload["failures"].append(
                        f"requested_browser_recipe_mismatch:requested={ATTEMPT.recipe}:applied={before_state.get('browser_recipe')}"
                    )
                if before_state.get("browser_recipe_error"):
                    payload["failures"].append(f"browser_recipe_error:{before_state.get('browser_recipe_error')}")
                if not _family_matches(FAMILY_ID, before_snapshot, before_state):
                    payload["failures"].append(f"target_family_not_selected:{FAMILY_ID}")
                before_hash = _stable_hash(_output_fingerprint(before_snapshot, before_state))
                before_card_text_hash = _stable_hash(before_snapshot.get("first_card_text") or "")
                payload["before"] = {
                    "output_hash": before_hash,
                    "family_ids": _selected_family_ids(before_snapshot, before_state),
                    "family_selection": _family_selection(before_snapshot),
                    "visible_cta_buttons": _enabled_action_buttons(before_snapshot),
                    "card_text_sample": _compact_text(before_snapshot.get("first_card_text"), 620),
                }
                payload["screenshots"]["before"] = product_gate._save_screenshot(page, run_dir, ATTEMPT.name, "before")
                payload["samples"].append(_sample(page, label="before_click", elapsed_s=0.0, before_hash=before_hash))

                click = _click_first_enabled_action(page)
                payload["click"] = click
                if not click.get("clicked"):
                    payload["failures"].append("enabled_cta_detected_but_click_failed")
                    classification = {
                        "classification": "CLICK_NOT_PERFORMED",
                        "reason": "No enabled Apply/one-click CTA was clicked.",
                        "post_click_card_ready": False,
                        "apply_output_changed": False,
                    }
                else:
                    start = time.monotonic()
                    page.wait_for_timeout(1000)
                    next_sample = 0.0
                    while True:
                        elapsed = time.monotonic() - start
                        if elapsed >= next_sample:
                            payload["samples"].append(
                                _sample(
                                    page,
                                    label=f"post_click_{len(payload['samples'])}",
                                    elapsed_s=elapsed,
                                    before_hash=before_hash,
                                )
                            )
                            next_sample += max(args.sample_interval_sec, 1.0)
                        latest = payload["samples"][-1]
                        if (
                            latest["label"].startswith("post_click")
                            and int(latest.get("snapshot_card_count") or 0) > 0
                            and str(latest.get("snapshot_first_card_text") or "").strip()
                            and bool(latest.get("output_changed_from_before"))
                            and elapsed >= max(args.sample_interval_sec, 1.0)
                            and _stable_hash(latest.get("snapshot_first_card_text") or "") != before_card_text_hash
                        ):
                            break
                        if elapsed >= max(args.sample_window_sec, 5.0):
                            break
                        page.wait_for_timeout(500)
                    payload["screenshots"]["after_sampling"] = product_gate._save_screenshot(
                        page,
                        run_dir,
                        ATTEMPT.name,
                        "after_sampling",
                    )
                    classification = _classify(
                        payload["samples"],
                        before_hash=before_hash,
                        before_card_text_hash=before_card_text_hash,
                        min_ready_elapsed_s=max(args.sample_interval_sec, 1.0),
                    )

                payload["classification"] = classification
                if payload["failures"] and classification.get("classification") in {"CLICK_NOT_PERFORMED"}:
                    payload["status"] = "PARTIAL"
            except PlaywrightTimeoutError as exc:
                payload["status"] = "PARTIAL"
                payload["failures"].append(f"initial_ready_or_card_timeout:{type(exc).__name__}: {exc}")
                try:
                    payload["samples"].append(_sample(page, label="initial_timeout", elapsed_s=0.0))
                    payload["screenshots"]["initial_timeout"] = product_gate._save_screenshot(
                        page,
                        run_dir,
                        ATTEMPT.name,
                        "initial_timeout",
                    )
                except Exception as nested:
                    payload["failures"].append(f"initial_timeout_snapshot_failed:{type(nested).__name__}: {nested}")
                payload["classification"] = {
                    "classification": "INITIAL_CARD_NOT_READY",
                    "reason": "The initial recipe did not reach a verifier-ready Design Guide card.",
                    "post_click_card_ready": False,
                    "apply_output_changed": False,
                }
            finally:
                context.close()
                browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    artifact_path = ARTIFACT_DIR / f"design_guide_shear_fail_bending_overdesign_post_click_card_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_fail_bending_overdesign_post_click_card_readiness_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": (payload.get("classification") or {}).get("classification"),
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": payload.get("failures"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
