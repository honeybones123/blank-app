"""Slot/DOM replacement proof for SHEAR_FAIL_BENDING_OVERDESIGN after Apply.

Proof-only. This verifier continues the pending-shell completion audit by
checking the browser DOM after the server-side final Design Guide render has
completed. It answers whether:

* the pre-widget pending shell remains mounted,
* a final Design Guide card exists but is hidden/outside the viewport,
* final-publication/card readiness markers exist without a card,
* the visible Design Guide region is only placeholder text, or
* browser-state publication/debug probes are absent after render completion.

It does not change family runtimes, contracts, CTA rendering, publication
semantics, apply routing, visible wording, or product behaviour.
"""

from __future__ import annotations

import argparse
import json
import os
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
    _click_first_enabled_action,
    _enabled_action_buttons,
    _family_matches,
    _family_selection,
    _goto_recipe,
    _output_fingerprint,
    _selected_family_ids,
    _stable_hash,
)
from tools.verification.design_guide_shear_fail_bending_overdesign_pending_completion_gate_audit import (  # noqa: E402
    _classify_completion_gate,
    _created_or_modified_trace_files,
    _parse_trace_rows,
    _trace_files,
    _trace_summary,
)
from tools.verification.design_guide_shear_fail_bending_overdesign_post_click_card_readiness_snapshot import (  # noqa: E402
    _classify as _classify_readiness,
    _compact_text,
    _sample,
)
from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PERF_DIR = ROOT / "artifacts" / "performance"

FAMILY_ID = "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
ATTEMPT = ReplayAttempt(
    name="shear_fail_bending_overdesign_slot_dom_replacement",
    family_id=FAMILY_ID,
    recipe="B_shear_under_only",
)


def _dom_slot_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            """
            () => {
              const text = (el) => (el && (el.innerText || el.textContent || '').trim()) || '';
              const norm = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
              const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.visibility !== 'hidden' && style.display !== 'none' &&
                  rect.width > 0 && rect.height > 0;
              };
              const rectObj = (el) => {
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {
                  x: Math.round(r.x * 100) / 100,
                  y: Math.round(r.y * 100) / 100,
                  width: Math.round(r.width * 100) / 100,
                  height: Math.round(r.height * 100) / 100,
                  top: Math.round(r.top * 100) / 100,
                  bottom: Math.round(r.bottom * 100) / 100,
                  inViewport: r.bottom > 0 && r.top < window.innerHeight,
                };
              };
              const signature = (el) => {
                if (!el) return {};
                return {
                  tag: el.tagName,
                  testid: el.getAttribute('data-testid') || '',
                  cls: String(el.className || ''),
                  id: el.id || '',
                  rect: rectObj(el),
                  visible: visible(el),
                  text: norm(text(el)).slice(0, 900),
                };
              };
              const allCards = Array.from(document.querySelectorAll("[data-testid='design-guide-card'], .fast-guidance-item"));
              const pendingShells = Array.from(document.querySelectorAll(
                "[data-testid='design-guide-proof-pending'], .dg-proof-pending-shell, [aria-busy='true']"
              )).filter((el) => /Design Guide|Checking design guidance|Reviewing strength|StrengthDetailingServiceabilityCleanup/i.test(text(el)));
              const readyMarkers = Array.from(document.querySelectorAll(
                "[data-final-publication-authority-hash], [data-final-publication-display-hash], [data-final-publication-cta-hash], [data-render-contract-enabled], [data-render-cta-enabled]"
              ));
              const textNodes = Array.from(document.querySelectorAll("section, div, article, [data-testid='stMarkdownContainer'], [data-testid='stElementContainer']"))
                .filter((el) => /Design Guide|Checking design guidance|Strengthening required|Design is efficient|Why no further cleanup|Why action is required/i.test(text(el)))
                .map((el) => signature(el));
              const focusedTextNodes = textNodes
                .filter((row) => /Design Guide|Checking design guidance|Strengthening required|Design is efficient/i.test(row.text))
                .slice(0, 18);
              const cardOwners = allCards.map((el) => {
                const ancestors = [];
                let cur = el.parentElement;
                for (let i = 0; cur && i < 5; i += 1, cur = cur.parentElement) {
                  ancestors.push(signature(cur));
                }
                return { card: signature(el), ancestors };
              });
              const pendingOwners = pendingShells.map((el) => {
                const ancestors = [];
                let cur = el.parentElement;
                for (let i = 0; cur && i < 5; i += 1, cur = cur.parentElement) {
                  ancestors.push(signature(cur));
                }
                return { pending: signature(el), ancestors };
              });
              const bodyText = norm(text(document.body));
              return {
                body_text_length: bodyText.length,
                body_text_sample: bodyText.slice(0, 1800),
                design_guide_heading_count: (bodyText.match(/Design Guide/g) || []).length,
                card_count: allCards.length,
                visible_card_count: allCards.filter(visible).length,
                hidden_card_count: allCards.filter((el) => !visible(el)).length,
                card_owners: cardOwners.slice(0, 4),
                pending_shell_count: pendingShells.length,
                visible_pending_shell_count: pendingShells.filter(visible).length,
                pending_owners: pendingOwners.slice(0, 4),
                ready_marker_count: readyMarkers.length,
                visible_ready_marker_count: readyMarkers.filter(visible).length,
                ready_marker_signatures: readyMarkers.slice(0, 8).map(signature),
                design_guide_related_nodes: focusedTextNodes,
                window_scroll_y: window.scrollY,
                viewport_height: window.innerHeight,
                document_height: document.documentElement.scrollHeight,
              };
            }
            """
        )
    )


def _browser_probe_summary(browser_state: dict[str, Any]) -> dict[str, Any]:
    interesting_keys = [
        "final_design_guide_publication",
        "final_publication_verifier_payload",
        "design_guide_probe",
        "guidance_probe",
        "guidance_compute_probe",
        "design_guide_render_probe",
        "render_timing_probe",
        "design_guide_primary_apply_payload",
        "design_guide_primary_payload_binding_audit",
    ]
    summary: dict[str, Any] = {
        "browser_state_key_count": len(browser_state),
        "browser_state_keys": sorted(str(key) for key in browser_state.keys())[:160],
        "interesting_key_presence": {key: key in browser_state for key in interesting_keys},
    }
    for key in interesting_keys:
        value = browser_state.get(key)
        if isinstance(value, dict):
            summary[key] = {
                "key_count": len(value),
                "keys": sorted(str(k) for k in value.keys())[:80],
                "selected_family_id": value.get("selected_family_id") or value.get("selected_family"),
                "publication_hash": value.get("publication_hash"),
                "final_publication_authority_hash": value.get("final_publication_authority_hash"),
                "display_hash": value.get("display_hash") or value.get("final_publication_display_hash"),
                "cta_hash": value.get("cta_hash") or value.get("final_publication_cta_hash"),
                "outcome_state": value.get("outcome_state"),
            }
        elif value is not None:
            summary[key] = str(type(value).__name__)
    return summary


def _classify_slot_dom(readiness: dict[str, Any], completion: dict[str, Any], dom: dict[str, Any], browser: dict[str, Any]) -> dict[str, Any]:
    final_completed = str(completion.get("completion_gate") or "") == "FINAL_RENDER_COMPLETED_BUT_PENDING_SHELL_REMAINED"
    pending_count = int(dom.get("pending_shell_count") or 0)
    visible_pending_count = int(dom.get("visible_pending_shell_count") or 0)
    card_count = int(dom.get("card_count") or 0)
    visible_card_count = int(dom.get("visible_card_count") or 0)
    ready_marker_count = int(dom.get("ready_marker_count") or 0)
    final_pub_present = bool((browser.get("interesting_key_presence") or {}).get("final_design_guide_publication"))
    verifier_payload_present = bool((browser.get("interesting_key_presence") or {}).get("final_publication_verifier_payload"))

    if final_completed and visible_pending_count > 0 and card_count == 0:
        classification = "VISIBLE_PENDING_SHELL_SURVIVED_COMPLETED_FINAL_RENDER"
        reason = "Final render completed, but the browser DOM still contains a visible pending shell and no card element."
    elif final_completed and card_count > 0 and visible_card_count == 0:
        classification = "FINAL_CARD_DOM_EXISTS_BUT_HIDDEN"
        reason = "Final render completed and card DOM exists, but no card is visible."
    elif final_completed and ready_marker_count > 0 and card_count == 0:
        classification = "READY_MARKERS_WITHOUT_CARD_DOM"
        reason = "Final render readiness markers exist, but card DOM is absent."
    elif final_completed and not final_pub_present and not verifier_payload_present:
        classification = "FINAL_RENDER_COMPLETED_WITHOUT_BROWSER_PUBLICATION_PROBE"
        reason = "Final render completed, but browser-state publication/verifier probes were absent."
    elif final_completed and pending_count == 0 and card_count == 0:
        classification = "FINAL_RENDER_COMPLETED_EMPTY_DESIGN_GUIDE_REGION"
        reason = "Final render completed, but neither pending shell nor card DOM remained."
    elif str(readiness.get("classification") or "") != "STUCK_PENDING_SHELL":
        classification = "SLOT_DOM_NOT_STUCK_PENDING_IN_THIS_RUN"
        reason = "This run did not reproduce the stuck pending shell."
    else:
        classification = "SLOT_DOM_REPLACEMENT_UNCLASSIFIED"
        reason = "The DOM proof did not match a known slot/replacement state."

    return {
        "classification": classification,
        "reason": reason,
        "final_render_completed": final_completed,
        "pending_shell_count": pending_count,
        "visible_pending_shell_count": visible_pending_count,
        "card_count": card_count,
        "visible_card_count": visible_card_count,
        "ready_marker_count": ready_marker_count,
        "final_publication_probe_present": final_pub_present,
        "final_publication_verifier_payload_present": verifier_payload_present,
    }


def _render_visible_payload_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload_rows: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("block") or "") != "_render_fast_design_guidance_panel.render_visible_items_payload":
            continue
        payload_rows.append(
            {
                "timestamp": row.get("timestamp"),
                "item_count": row.get("item_count"),
                "first_title": row.get("first_title"),
                "first_family": row.get("first_family"),
                "first_guidance_intent": row.get("first_guidance_intent"),
                "first_action_type": row.get("first_action_type"),
                "first_bucket": row.get("first_bucket"),
                "first_button_contract_enabled": row.get("first_button_contract_enabled"),
                "render_plan_reason": row.get("render_plan_reason"),
                "has_primary_card_presentation": row.get("has_primary_card_presentation"),
            }
        )
    return payload_rows


def _write_report(payload: dict[str, Any], path: Path) -> None:
    readiness = dict(payload.get("readiness_classification") or {})
    completion = dict(payload.get("completion_gate_classification") or {})
    slot = dict(payload.get("slot_dom_classification") or {})
    dom = dict(payload.get("final_dom_probe") or {})
    browser = dict(payload.get("final_browser_state_summary") or {})
    lines = [
        "# SHEAR_FAIL_BENDING_OVERDESIGN Slot/DOM Replacement Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Readiness classification: `{readiness.get('classification')}`",
        f"Completion gate: `{completion.get('completion_gate')}`",
        f"Slot/DOM classification: `{slot.get('classification')}`",
        f"Reason: {slot.get('reason')}",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## DOM Summary",
        "",
        f"- Pending shell count: `{dom.get('pending_shell_count')}`",
        f"- Visible pending shell count: `{dom.get('visible_pending_shell_count')}`",
        f"- Card count: `{dom.get('card_count')}`",
        f"- Visible card count: `{dom.get('visible_card_count')}`",
        f"- Ready marker count: `{dom.get('ready_marker_count')}`",
        f"- Design Guide heading count: `{dom.get('design_guide_heading_count')}`",
        "",
        "## Browser-State Probe Summary",
        "",
        f"- Browser-state key count: `{browser.get('browser_state_key_count')}`",
        f"- Interesting key presence: `{json.dumps(browser.get('interesting_key_presence') or {}, sort_keys=True)}`",
        "",
        "## Pending Shell Owners",
        "",
    ]
    for owner in dom.get("pending_owners") or []:
        pending = dict(owner.get("pending") or {})
        lines.append(f"- `{pending.get('tag')}` `{pending.get('testid')}` `{pending.get('cls')}` text: {str(pending.get('text') or '')[:220]}")
    lines.extend(["", "## Card Owners", ""])
    for owner in dom.get("card_owners") or []:
        card = dict(owner.get("card") or {})
        lines.append(f"- `{card.get('tag')}` `{card.get('testid')}` `{card.get('cls')}` text: {str(card.get('text') or '')[:220]}")
    lines.extend(["", "## Render Visible Items Payload", ""])
    for row in (payload.get("trace_summary") or {}).get("render_visible_items_payload_rows") or []:
        lines.append(
            "- item_count=`{item_count}` title=`{title}` family=`{family}` intent=`{intent}` "
            "action_type=`{action}` bucket=`{bucket}` button_enabled=`{enabled}` reason=`{reason}`".format(
                item_count=row.get("item_count"),
                title=row.get("first_title"),
                family=row.get("first_family"),
                intent=row.get("first_guidance_intent"),
                action=row.get("first_action_type"),
                bucket=row.get("first_bucket"),
                enabled=row.get("first_button_contract_enabled"),
                reason=row.get("render_plan_reason"),
            )
        )
    lines.extend(["", "## Design Guide Related Nodes", ""])
    for node in dom.get("design_guide_related_nodes") or []:
        lines.append(f"- `{node.get('tag')}` `{node.get('testid')}` `{node.get('cls')}` text: {str(node.get('text') or '')[:260]}")
    lines.extend(["", "## Next Safe Step", "", str(payload.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8574)
    parser.add_argument("--reuse-existing-server", action="store_true", default=False)
    parser.add_argument("--headed", action="store_true", default=False)
    parser.add_argument("--sample-window-sec", type=float, default=95.0)
    parser.add_argument("--sample-interval-sec", type=float, default=5.0)
    parser.add_argument("--ready-timeout-sec", type=float, default=75.0)
    parser.add_argument("--card-timeout-sec", type=float, default=75.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = ARTIFACT_DIR / f"design_guide_shear_fail_bending_overdesign_slot_dom_replacement_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{args.port}"

    previous_perf_trace = os.environ.get("PERF_TRACE_INPUTS")
    os.environ["PERF_TRACE_INPUTS"] = "1"
    trace_before = _trace_files()
    started_at = time.time()
    process = None
    if not args.reuse_existing_server:
        process = _start_streamlit(args.port)
    else:
        _wait_for_http(base_url, timeout_s=45.0)

    payload: dict[str, Any] = {
        "schema": "design_guide_shear_fail_bending_overdesign_slot_dom_replacement_snapshot.v1",
        "status": "PASS",
        "created_at": stamp,
        "family_id": FAMILY_ID,
        "attempt": {"name": ATTEMPT.name, "recipe": ATTEMPT.recipe},
        "product_behaviour_changed": False,
        "browser_test_mode": True,
        "samples": [],
        "screenshots": {},
        "failures": [],
    }

    click_wall_time: datetime | None = None
    final_browser_state: dict[str, Any] = {}
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

                click_wall_time = datetime.now()
                click = _click_first_enabled_action(page)
                payload["click"] = click
                if not click.get("clicked"):
                    payload["status"] = "PARTIAL"
                    payload["failures"].append("enabled_cta_detected_but_click_failed")
                    readiness = {
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
                    final_browser_state = _load_browser_state(page, timeout_s=8.0)
                    payload["final_dom_probe"] = _dom_slot_probe(page)
                    payload["final_browser_state_summary"] = _browser_probe_summary(final_browser_state)
                    payload["screenshots"]["after_sampling"] = product_gate._save_screenshot(
                        page,
                        run_dir,
                        ATTEMPT.name,
                        "after_sampling",
                    )
                    readiness = _classify_readiness(
                        payload["samples"],
                        before_hash=before_hash,
                        before_card_text_hash=before_card_text_hash,
                        min_ready_elapsed_s=max(args.sample_interval_sec, 1.0),
                    )
                payload["readiness_classification"] = readiness
            except PlaywrightTimeoutError as exc:
                payload["status"] = "PARTIAL"
                payload["failures"].append(f"initial_ready_or_card_timeout:{type(exc).__name__}: {exc}")
                payload["readiness_classification"] = {
                    "classification": "INITIAL_CARD_NOT_READY",
                    "reason": "The initial recipe did not reach a verifier-ready Design Guide card.",
                    "post_click_card_ready": False,
                    "apply_output_changed": False,
                }
                payload["final_dom_probe"] = _dom_slot_probe(page)
                try:
                    final_browser_state = _load_browser_state(page, timeout_s=3.0)
                    payload["final_browser_state_summary"] = _browser_probe_summary(final_browser_state)
                except Exception as nested:
                    payload["failures"].append(f"initial_timeout_browser_state_failed:{type(nested).__name__}: {nested}")
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
        if previous_perf_trace is None:
            os.environ.pop("PERF_TRACE_INPUTS", None)
        else:
            os.environ["PERF_TRACE_INPUTS"] = previous_perf_trace

    trace_paths = _created_or_modified_trace_files(trace_before, started_at=started_at)
    trace_rows = _parse_trace_rows(trace_paths)
    trace = _trace_summary(trace_rows, click_wall_time=click_wall_time)
    trace["render_visible_items_payload_rows"] = _render_visible_payload_rows(trace_rows)
    payload["trace_summary"] = trace
    payload["completion_gate_classification"] = _classify_completion_gate(
        dict(payload.get("readiness_classification") or {}),
        trace,
    )
    payload["slot_dom_classification"] = _classify_slot_dom(
        dict(payload.get("readiness_classification") or {}),
        dict(payload.get("completion_gate_classification") or {}),
        dict(payload.get("final_dom_probe") or {}),
        dict(payload.get("final_browser_state_summary") or {}),
    )
    payload["next_safe_step"] = (
        "If the pending shell survives completed final render, inspect the Streamlit slot replacement "
        "and render-visible-items branch with a minimal proof/fix at that handoff only. Do not alter "
        "family runtime, contracts, CTA rendering, publication semantics, apply routing, or visible wording."
    )

    artifact_path = ARTIFACT_DIR / f"design_guide_shear_fail_bending_overdesign_slot_dom_replacement_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_fail_bending_overdesign_slot_dom_replacement_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "readiness_classification": (payload.get("readiness_classification") or {}).get("classification"),
                "completion_gate": (payload.get("completion_gate_classification") or {}).get("completion_gate"),
                "slot_dom_classification": (payload.get("slot_dom_classification") or {}).get("classification"),
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
