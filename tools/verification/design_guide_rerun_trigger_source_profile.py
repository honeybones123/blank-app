"""Browser/live rerun-trigger source profile for Design Guide smoothness.

Proof-only. This verifier samples the same Inputs recipe across a stable reload
and compares browser-state probes, render timing markers, publication/display
hashes, pending action flags, and DOM gaps. It does not change rendering,
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

from tools.verification.helpers.browser_helpers import _browser_state_raw_candidates  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS"

PENDING_FLAG_KEYS = (
    "pending_inputs_apply_refresh",
    "inputs_action_apply_recommendation",
    "inputs_action_run_auto_design",
    "run_design_clicked",
)

IMPORTANT_HASH_KEYS = (
    "publication_hash",
    "final_publication_authority_hash",
    "final_publication_cta_hash",
    "final_publication_display_hash",
    "final_publication_evidence_hash",
    "final_publication_hash",
    "publication_fingerprint",
    "design_guide_publication_fingerprint",
    "panel_baseline_fingerprint",
    "state_fingerprint",
)

AUTHORITY_STABILITY_HASH_KEYS = (
    "design_guide_publication_fingerprint",
    "final_publication_authority_hash",
    "final_publication_display_hash",
    "state_fingerprint",
)

TIMING_PREFIXES = (
    "app.page_dispatch",
    "app.pre_dispatch.page_content_slot",
    "inputs_page.summary_render",
    "inputs_page.design_guide_build",
    "app.browser_test_state_emit",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _compact(value: Any, *, depth: int = 4, max_items: int = 18) -> Any:
    if depth <= 0:
        if isinstance(value, (dict, list, tuple, set)):
            return f"<{type(value).__name__}>"
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                out["..."] = f"{len(value) - max_items} more"
                break
            out[str(key)] = _compact(item, depth=depth - 1, max_items=max_items)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [_compact(item, depth=depth - 1, max_items=max_items) for item in seq[:max_items]]
        if len(seq) > max_items:
            out.append(f"... {len(seq) - max_items} more")
        return out
    return value


def _find_key_values(value: Any, wanted: set[str], *, depth: int = 8, prefix: str = "$") -> dict[str, Any]:
    if depth < 0:
        return {}
    found: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}"
            if str(key) in wanted and item not in (None, "", [], {}):
                found.setdefault(str(key), []).append({"path": child, "value": item})
            nested = _find_key_values(item, wanted, depth=depth - 1, prefix=child)
            for nested_key, nested_items in nested.items():
                found.setdefault(nested_key, []).extend(nested_items)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(list(value)[:80]):
            nested = _find_key_values(item, wanted, depth=depth - 1, prefix=f"{prefix}[{index}]")
            for nested_key, nested_items in nested.items():
                found.setdefault(nested_key, []).extend(nested_items)
    return found


def _extract_hashes(state: dict[str, Any]) -> dict[str, Any]:
    values = _find_key_values(state, set(IMPORTANT_HASH_KEYS), depth=8)
    compacted: dict[str, Any] = {}
    for key, rows in values.items():
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        paths: list[str] = []
        for row in rows:
            text = str(row.get("value") or "")
            digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
            if text and digest not in seen:
                seen.add(digest)
                unique.append(
                    {
                        "digest": digest,
                        "preview": text[:180] + ("..." if len(text) > 180 else ""),
                        "length": len(text),
                    }
                )
            path = str(row.get("path") or "")
            if path and path not in paths:
                paths.append(path)
        compacted[key] = {"values": unique[:8], "paths": paths[:8], "count": len(rows)}
    return compacted


def _extract_timing_names(value: Any) -> list[str]:
    names: set[str] = set()

    def visit(item: Any, *, depth: int = 7) -> None:
        if depth < 0:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                child_text = str(child)
                for prefix in TIMING_PREFIXES:
                    if key_text.startswith(prefix):
                        names.add(key_text)
                    if child_text.startswith(prefix):
                        names.add(child_text)
                visit(child, depth=depth - 1)
        elif isinstance(item, (list, tuple)):
            for child in list(item)[:200]:
                visit(child, depth=depth - 1)

    visit(value)
    return sorted(names)


def _top_speed_entries(state: dict[str, Any]) -> list[dict[str, Any]]:
    probe = state.get("speed_profile_probe")
    entries: list[dict[str, Any]] = []

    def visit(item: Any, *, depth: int = 5) -> None:
        if depth < 0:
            return
        if isinstance(item, dict):
            text = _stable_json(item)
            if any(token in text.lower() for token in ("candidate", "eval", "search", "render", "publication")):
                entries.append(_compact(item, depth=2, max_items=10))
            for child in item.values():
                visit(child, depth=depth - 1)
        elif isinstance(item, (list, tuple)):
            for child in list(item)[:80]:
                visit(child, depth=depth - 1)

    visit(probe)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        key = _stable_hash(entry)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
        if len(deduped) >= 12:
            break
    return deduped


def _best_browser_state(page, recipe: str, *, timeout_s: float = 12.0) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + max(0.5, timeout_s)
    best: dict[str, Any] = {}
    best_score = (-1, -1, -1, -1)
    while datetime.now().timestamp() < deadline:
        for raw in _browser_state_raw_candidates(page, timeout_ms=2_000):
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if not isinstance(parsed, dict):
                continue
            phase = str(parsed.get("browser_probe_phase") or parsed.get("probe_phase") or "")
            score = (
                1 if parsed.get("browser_recipe") == recipe else 0,
                1 if phase in {"post_page_render", "final"} else 0,
                1 if parsed.get("render_timing_probe") else 0,
                len(raw),
            )
            if score > best_score:
                best = parsed
                best_score = score
            if score[:3] == (1, 1, 1):
                return parsed
        page.wait_for_timeout(250)
    return best


def _dom_snapshot(page, *, label: str) -> dict[str, Any]:
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
              const payload = (el) => {
                if (!el) return {exists: false, visible: false};
                const rect = el.getBoundingClientRect();
                return {
                  exists: true,
                  visible: visible(el),
                  text: clean(el.innerText || el.textContent).slice(0, 240),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 140),
                  rect: {
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom),
                    height: Math.round(rect.height),
                    width: Math.round(rect.width)
                  }
                };
              };
              const elements = {
                beam_heading: payload(shortestMatch(/^Beam design$/i)),
                nav_tabs: payload(shortestMatch(/Inputs\s+Design\s+Bending\s+Shear/i)),
                inputs_heading: payload(shortestMatch(/^Inputs$/i)),
                summary_band: payload(shortestMatch(/Bending\s+.\s+ULS|Shear\s+.\s+ULS|Crack control\s+.\s+SLS|Deflection\s+.\s+SLS/i)),
                batch_design: payload(shortestMatch(/^Batch design$/i)),
                design_guide_heading: payload(shortestMatch(/^Design Guide$/i, /Design Guide Debug|Debug session state/i)),
                design_guide_card: payload(shortestMatch(/Design is efficient|Strengthening required|repair is blocked|cleanup required|Design Guide blocker proof incomplete|Apply recommendation|Run one-click auto design/i, /Design Guide Debug|Debug session state/i)),
                proof_pending_shell: payload(shortestMatch(/Checking design guidance|Reviewing strength|StrengthDetailingServiceabilityCleanup options/i)),
                stable_root_shell: payload(document.querySelector('[data-testid="inputs-root-dispatch-stable-shell"]'))
              };
              const gap = (upper, lower) => {
                if (!upper || !lower || !upper.exists || !lower.exists) return null;
                return Math.round((lower.rect.top || 0) - (upper.rect.bottom || 0));
              };
              const bodyText = clean(document.body ? document.body.innerText : "");
              return {
                label,
                timestamp_ms: Date.now(),
                performance_now_ms: Math.round(performance.now()),
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scroll_y: Math.round(window.scrollY || 0),
                body_text_length: bodyText.length,
                body_text_hash: Array.from(bodyText.slice(0, 2500)).reduce((h, ch) => ((h * 31 + ch.charCodeAt(0)) >>> 0), 0).toString(16),
                elements,
                gaps: {
                  nav_to_inputs: gap(elements.nav_tabs, elements.inputs_heading),
                  inputs_to_summary: gap(elements.inputs_heading, elements.summary_band),
                  summary_to_batch: gap(elements.summary_band, elements.batch_design),
                  batch_to_design_guide: gap(elements.batch_design, elements.design_guide_heading),
                  design_guide_heading_to_card: gap(elements.design_guide_heading, elements.design_guide_card)
                },
                visible_text_flags: {
                  checking_design_guidance: /Checking design guidance/i.test(bodyText),
                  stable_shell_text: /Inputs page stable rerun shell/i.test(bodyText),
                  batch_design: /Batch design/i.test(bodyText),
                  design_guide: /Design Guide/i.test(bodyText)
                }
              };
            }
            """,
            label,
        )
        or {}
    )


def _state_summary(state: dict[str, Any], *, label: str, recipe: str) -> dict[str, Any]:
    debug_probe = dict(state.get("browser_debug_probe") or {})
    post_cleanup = dict(state.get("post_cleanup_acceptance_probe") or {})
    dg_probe = dict(state.get("design_guide_probe") or {})
    debug_bundle = dict(dg_probe.get("debug_bundle") or {})
    render_trace = dict(dg_probe.get("render_eligibility_trace") or debug_bundle.get("design_guide_render_eligibility_trace") or {})
    pending_flags = {}
    for key in PENDING_FLAG_KEYS:
        pending_flags[key] = debug_probe.get(key, post_cleanup.get(key))
    timing_names = _extract_timing_names(state.get("render_timing_probe"))
    return {
        "label": label,
        "browser_recipe": state.get("browser_recipe"),
        "recipe_matches": state.get("browser_recipe") == recipe,
        "browser_probe_phase": state.get("browser_probe_phase") or state.get("probe_phase"),
        "results_version": state.get("results_version"),
        "pending_flags": pending_flags,
        "any_pending_flag": any(bool(value) for value in pending_flags.values()),
        "rerun_triggers": (
            list(debug_probe.get("inputs_rerun_trigger_events") or [])
            + list(debug_probe.get("ssl_rerun_triggers") or [])
        )[-24:],
        "render_eligibility": {
            "should_render_design_guide_slot": render_trace.get("should_render_design_guide_slot"),
            "design_guide_slot_created": render_trace.get("design_guide_slot_created"),
            "contract_required": render_trace.get("contract_required"),
            "current_page_gate_allows": render_trace.get("current_page_gate_allows"),
            "inputs_has_design_actions_or_loads": render_trace.get("inputs_has_design_actions_or_loads"),
            "reasons": render_trace.get("reasons"),
        },
        "stable_render_reuse_trace": _compact(
            debug_probe.get("inputs_stable_render_reuse_trace") or {},
            depth=4,
            max_items=8,
        ),
        "summary_card_html_bypass_debug": _compact(
            debug_probe.get("final_publication_summary_card_html_bypass_debug") or {},
            depth=3,
            max_items=12,
        ),
        "design_guide": {
            "needs_refresh": dg_probe.get("needs_refresh"),
            "primary_card_title": dg_probe.get("primary_card_title"),
            "primary_card_intent": dg_probe.get("primary_card_intent"),
            "button_contract_enabled": dg_probe.get("button_contract_enabled"),
            "button_contract_preview_pass": dg_probe.get("button_contract_preview_pass"),
            "button_contract_update_count": len(dict(dg_probe.get("button_contract_updates") or {})),
            "terminal_state": dg_probe.get("terminal_state"),
            "guidance_branch": dg_probe.get("guidance_branch"),
        },
        "hashes": _extract_hashes(state),
        "timing": {
            "important_mark_count": len(timing_names),
            "important_marks": timing_names[:80],
            "raw_compact": _compact(state.get("render_timing_probe"), depth=3, max_items=16),
        },
        "speed_profile_top": _top_speed_entries(state),
        "ux_latency_probe": _compact(state.get("ux_latency_probe"), depth=3, max_items=16),
    }


def _hash_value_digests(summary: dict[str, Any], key: str) -> list[str]:
    rows = ((summary.get("hashes") or {}).get(key) or {}).get("values") or []
    digests: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            digest = str(row.get("digest") or "").strip()
        else:
            digest = hashlib.sha256(str(row).encode("utf-8", errors="ignore")).hexdigest()
        if digest and digest not in digests:
            digests.append(digest)
    return digests


def _classify(samples: list[dict[str, Any]]) -> dict[str, Any]:
    state_samples = [sample for sample in samples if sample.get("state_summary")]
    before = state_samples[1] if len(state_samples) > 1 else (state_samples[0] if state_samples else {})
    after = state_samples[-1] if state_samples else {}
    before_state = dict(before.get("state_summary") or {})
    after_state = dict(after.get("state_summary") or {})
    before_dom = dict(before.get("dom") or {})
    after_dom = dict(after.get("dom") or {})

    stable_publication = True
    compared_hashes: dict[str, Any] = {}
    for key in IMPORTANT_HASH_KEYS:
        left_values = _hash_value_digests(before_state, key)
        right_values = _hash_value_digests(after_state, key)
        left = left_values[0] if left_values else None
        right = right_values[0] if right_values else None
        if left or right:
            matches = bool(set(left_values) & set(right_values)) if left_values and right_values else left == right
            compared_hashes[key] = {
                "before": left_values[:6],
                "after": right_values[:6],
                "matches": matches,
            }
            if key in AUTHORITY_STABILITY_HASH_KEYS and not matches:
                stable_publication = False

    marks_after = set(((after_state.get("timing") or {}).get("important_marks")) or [])
    stable_slot_shell = any("app.page_dispatch.inputs_root_stable_shell" in mark for mark in marks_after)
    page_content_cleared = any("app.page_dispatch.page_content_slot.clear" in mark for mark in marks_after)
    summary_rebuilt = any("inputs_page.summary_render" in mark for mark in marks_after)
    design_guide_rebuilt = any("inputs_page.design_guide_build" in mark for mark in marks_after)
    probe_rebuilt = any("app.browser_test_state_emit" in mark for mark in marks_after)
    summary_bypass_debug = dict(after_state.get("summary_card_html_bypass_debug") or {})
    summary_html_bypassed = bool(summary_bypass_debug.get("summary_card_html_bypassed"))
    summary_html_cache_warmup = bool(
        "missing_cached_summary_html" in str(summary_bypass_debug.get("bypass_reason") or "")
    )
    summary_visible_render_only = bool(
        summary_rebuilt
        and summary_html_bypassed
        and summary_bypass_debug.get("visible_render_still_called") is True
    )
    pending_after = bool(after_state.get("any_pending_flag"))
    proof_pending_visible = bool(((after_dom.get("elements") or {}).get("proof_pending_shell") or {}).get("visible"))
    card_visible = bool(((after_dom.get("elements") or {}).get("design_guide_card") or {}).get("visible"))
    dg_heading_visible = bool(((after_dom.get("elements") or {}).get("design_guide_heading") or {}).get("visible"))
    stable_render_trace = dict(after_state.get("stable_render_reuse_trace") or {})
    stable_trace_missing_previous = [
        surface
        for surface, row in stable_render_trace.items()
        if isinstance(row, dict)
        and "missing_previous_render_fingerprint_hash" in str(row.get("reason") or "")
    ]
    stable_trace_reuse_eligible = [
        surface
        for surface, row in stable_render_trace.items()
        if isinstance(row, dict) and bool(row.get("reuse_eligible"))
    ]
    stable_trace_missing_required = [
        surface
        for surface, row in stable_render_trace.items()
        if isinstance(row, dict) and list(row.get("missing_required_fingerprint_keys") or [])
    ]
    trigger_events: list[str] = []
    for sample in state_samples:
        for row in list((dict(sample.get("state_summary") or {})).get("rerun_triggers") or []):
            if not isinstance(row, dict):
                continue
            event = str(row.get("event") or "").strip()
            if event and event not in trigger_events:
                trigger_events.append(event)

    gap_values = []
    for sample in samples:
        gaps = dict((sample.get("dom") or {}).get("gaps") or {})
        for gap_name, gap_value in gaps.items():
            if isinstance(gap_value, (int, float)):
                gap_values.append({"sample": sample.get("label"), "gap": gap_name, "px": gap_value})
    largest_gap = max(gap_values, key=lambda row: abs(float(row["px"])), default={})

    likely_sources: list[str] = []
    if pending_after:
        likely_sources.append("pending_apply_or_action_flag")
    if not stable_publication:
        likely_sources.append("publication_or_state_hash_changed")
    if stable_publication and design_guide_rebuilt and "design_guide_panel" not in stable_trace_missing_required:
        likely_sources.append("design_guide_rebuild_with_stable_publication")
    if stable_publication and summary_rebuilt and not summary_visible_render_only and not summary_html_cache_warmup:
        likely_sources.append("summary_rebuild_with_stable_publication")
    if stable_publication and summary_rebuilt and summary_html_cache_warmup:
        likely_sources.append("summary_html_cache_warmup_first_render")
    if stable_publication and design_guide_rebuilt and "design_guide_panel" in stable_trace_missing_required:
        likely_sources.append("design_guide_publication_hash_hydration_first_render")
    if stable_publication and summary_visible_render_only:
        likely_sources.append("summary_html_build_bypassed_visible_render_only")
    if stable_slot_shell:
        likely_sources.append("same_page_inputs_root_shell_path")
    if page_content_cleared:
        likely_sources.append("page_content_slot_clear_path")
    if proof_pending_visible and not card_visible:
        likely_sources.append("proof_pending_shell_visible_without_final_card")
    if probe_rebuilt:
        likely_sources.append("browser_probe_payload_rebuild")
    if stable_trace_missing_previous:
        likely_sources.append("browser_reload_missing_previous_render_fingerprint")
    if stable_trace_reuse_eligible:
        likely_sources.append("stable_render_reuse_eligible_but_rendered")

    if not likely_sources:
        likely_sources.append("no_source_identified")

    if "publication_or_state_hash_changed" in likely_sources:
        recommended = "Trace which state field changes the publication/request hash before adding another bypass."
    elif "stable_render_reuse_eligible_but_rendered" in likely_sources:
        recommended = "Create guarded render reuse for the eligible stable surfaces reported by inputs_stable_render_reuse_trace."
    elif "browser_reload_missing_previous_render_fingerprint" in likely_sources:
        recommended = "Do not add another session render cache for browser reloads yet; profile same-session no-change rerun triggers or the root-shell/browser-probe path first."
    elif "summary_rebuild_with_stable_publication" in likely_sources and "design_guide_rebuild_with_stable_publication" in likely_sources:
        recommended = "Add proof-only readiness for stable-publication summary/render rebuild reuse keyed by summary fingerprint and final publication authority/display hashes."
    elif "design_guide_rebuild_with_stable_publication" in likely_sources:
        recommended = "Add proof-only readiness for stable-publication Design Guide render/build reuse keyed by final publication authority/display hashes."
    elif "summary_rebuild_with_stable_publication" in likely_sources:
        recommended = "Add proof-only readiness for summary-band render reuse keyed by summary state fingerprint."
    elif "summary_html_cache_warmup_first_render" in likely_sources or "design_guide_publication_hash_hydration_first_render" in likely_sources:
        recommended = "Do not add another stable-rerun cache from this browser-reload sample; profile same-session post-Apply state writes or first-paint/layout instead."
    elif "proof_pending_shell_visible_without_final_card" in likely_sources:
        recommended = "Audit final-card readiness after placeholder render before changing shell/layout behavior."
    elif "same_page_inputs_root_shell_path" in likely_sources:
        recommended = "Profile same-page root-shell duration and prove it is zero-layout before changing dispatch."
    else:
        recommended = "Run a deeper browser live profile around Streamlit rerun triggers and state writes."

    return {
        "status": "PASS",
        "likely_sources": likely_sources,
        "stable_publication_or_state_hashes": stable_publication,
        "compared_hashes": compared_hashes,
        "stable_slot_shell_path_seen": stable_slot_shell,
        "page_content_slot_clear_path_seen": page_content_cleared,
        "summary_rebuilt": summary_rebuilt,
        "summary_html_bypassed": summary_html_bypassed,
        "summary_html_cache_warmup": summary_html_cache_warmup,
        "summary_visible_render_only": summary_visible_render_only,
        "summary_card_html_bypass_debug": summary_bypass_debug,
        "design_guide_rebuilt": design_guide_rebuilt,
        "browser_probe_rebuilt": probe_rebuilt,
        "stable_render_reuse_trace": stable_render_trace,
        "stable_trace_missing_previous_surfaces": stable_trace_missing_previous,
        "stable_trace_reuse_eligible_surfaces": stable_trace_reuse_eligible,
        "stable_trace_missing_required_surfaces": stable_trace_missing_required,
        "pending_flags_after_reload": dict(after_state.get("pending_flags") or {}),
        "rerun_trigger_events": trigger_events,
        "final_card_visible_after_reload": card_visible,
        "design_guide_heading_visible_after_reload": dg_heading_visible,
        "proof_pending_shell_visible_after_reload": proof_pending_visible,
        "largest_gap": largest_gap,
        "recommended_next_slice": recommended,
    }


def _capture(base_url: str, *, recipe: str, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        samples: list[dict[str, Any]] = []
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        sequence = (
            ("initial_after_load", 750, False),
            ("settled_before_reload", 3500, False),
            ("after_same_page_reload_initial", 750, True),
            ("after_same_page_reload_settled", 3500, False),
        )
        for label, wait_ms, reload_first in sequence:
            if reload_first:
                page.reload(wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(wait_ms)
            state = _best_browser_state(page, recipe, timeout_s=8.0)
            samples.append(
                {
                    "label": label,
                    "dom": _dom_snapshot(page, label=label),
                    "state_summary": _state_summary(state, label=label, recipe=recipe) if state else {},
                    "state_hash": _stable_hash(_compact(state, depth=5, max_items=24)) if state else None,
                }
            )
        browser.close()
        return {
            "url": url,
            "recipe": recipe,
            "samples": samples,
        }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Rerun Trigger Source Profile",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Likely sources: `{', '.join(cls.get('likely_sources') or [])}`",
        f"- Stable publication/state hashes: `{cls.get('stable_publication_or_state_hashes')}`",
        f"- Final card visible after reload: `{cls.get('final_card_visible_after_reload')}`",
        f"- Proof-pending shell visible after reload: `{cls.get('proof_pending_shell_visible_after_reload')}`",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
        "## Source Flags",
        "",
        "```json",
        json.dumps(
            {
                "stable_slot_shell_path_seen": cls.get("stable_slot_shell_path_seen"),
                "page_content_slot_clear_path_seen": cls.get("page_content_slot_clear_path_seen"),
                "summary_rebuilt": cls.get("summary_rebuilt"),
                "design_guide_rebuilt": cls.get("design_guide_rebuilt"),
                "browser_probe_rebuilt": cls.get("browser_probe_rebuilt"),
                "pending_flags_after_reload": cls.get("pending_flags_after_reload"),
                "rerun_trigger_events": cls.get("rerun_trigger_events"),
                "largest_gap": cls.get("largest_gap"),
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "## Samples",
        "",
        "| Sample | Recipe ok | Phase | Card | DG rebuild marks | Summary marks | Any pending |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for sample in payload.get("samples") or []:
        state = dict(sample.get("state_summary") or {})
        timing = dict(state.get("timing") or {})
        marks = list(timing.get("important_marks") or [])
        lines.append(
            "| "
            + str(sample.get("label"))
            + " | "
            + str(state.get("recipe_matches"))
            + " | "
            + str(state.get("browser_probe_phase"))
            + " | "
            + str(((sample.get("dom") or {}).get("elements") or {}).get("design_guide_card", {}).get("visible"))
            + " | "
            + str(sum(1 for mark in marks if "inputs_page.design_guide_build" in mark))
            + " | "
            + str(sum(1 for mark in marks if "inputs_page.summary_render" in mark))
            + " | "
            + str(state.get("any_pending_flag"))
            + " |"
        )
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_rerun_trigger_source_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_rerun_trigger_source_profile_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8613)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_RERUN_SOURCE_URL"))
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
        classification = _classify(list(capture.get("samples") or []))
        payload = {
            "schema": "design_guide_rerun_trigger_source_profile.v1",
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
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "likely_sources": classification.get("likely_sources"),
                    "recommended_next_slice": classification.get("recommended_next_slice"),
                },
                indent=2,
            )
        )
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
