"""Normal product-path Design Guide browser gate.

This gate proves user-visible behaviour through the normal Streamlit product
path. It does not use replay-case injection or hidden browser-state probes for
pass/fail decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = REPO / "artifacts" / "verification"
FORBIDDEN_DEBUG_TOKENS = (
    "candidate_evidence",
    "search_evidence",
    "current_state",
    "hidden browser-state",
    "_browser_state_probe",
    "guidance_compute_probe",
    "design_guide_probe",
    "candidate_search_evidence",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
)


@dataclass
class ScenarioResult:
    name: str
    status: str = "PASS"
    failures: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    screenshots: dict[str, str] = field(default_factory=dict)


def _visible_js() -> str:
    return """
    (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' &&
        rect.width > 0 && rect.height > 0;
    }
    """


def _snapshot(page: Page) -> dict[str, Any]:
    snapshot = page.evaluate(
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
            return {x: r.x, y: r.y, width: r.width, height: r.height, top: r.top, bottom: r.bottom};
          };
          const all = (selector) => Array.from(document.querySelectorAll(selector)).filter(visible);
          const text = (el) => (el && (el.innerText || el.textContent || '').trim()) || '';
          const norm = (value) => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
          const readControl = (key, labelMatchers) => {
            const labelNodes = Array.from(document.querySelectorAll("label, [data-testid='stWidgetLabel'], p, span, div"))
              .filter((el) => visible(el))
              .map((el) => ({el, label: text(el)}))
              .filter((row) => row.label && labelMatchers.some((matcher) => matcher.every((part) => norm(row.label).includes(part))))
              .sort((a, b) => a.label.length - b.label.length);
            for (const row of labelNodes) {
              let root = row.el.closest('[data-testid="stNumberInput"], [data-testid="stSelectbox"], [data-testid="stVerticalBlock"], section, div');
              for (let depth = 0; root && depth < 7; depth += 1, root = root.parentElement) {
                const rootText = text(root);
                const input = root.querySelector('input');
                const combo = root.querySelector('[role="combobox"], [data-baseweb="select"]');
                const value = input ? input.value : "";
                if (rootText || value || combo) {
                  return {
                    key,
                    label: row.label,
                    container_text: rootText,
                    input_value: value || "",
                    combo_text: combo ? text(combo) : "",
                    rect: rectObj(root),
                  };
                }
              }
            }
            return {key, label: "", container_text: "", input_value: "", combo_text: "", rect: null};
          };
          const cards = all("[data-testid='design-guide-card'], .fast-guidance-item")
            .map((el) => ({
              text: text(el),
              rect: rectObj(el),
              className: el.className || '',
              testid: el.getAttribute('data-testid') || '',
              selected_family_id: el.getAttribute('data-selected-family-id') || '',
              selected_family: el.getAttribute('data-selected-family') || '',
              selection_reason: el.getAttribute('data-selection-reason') || '',
              published_family_id: el.getAttribute('data-published-family-id') || '',
              cta_family_id: el.getAttribute('data-cta-family-id') || '',
              apply_payload_family_id: el.getAttribute('data-apply-payload-family-id') || '',
              candidate_family_id: el.getAttribute('data-candidate-family-id') || '',
              card_family_id: el.getAttribute('data-card-family-id') || '',
              family_selection_source: el.getAttribute('data-family-selection-source') || '',
              family_selection_contract: el.getAttribute('data-family-selection-contract') || '',
              family_chooser_contract: el.getAttribute('data-family-chooser-contract') || '',
              rejected_families: el.getAttribute('data-rejected-families') || '',
              selection_evidence: el.getAttribute('data-selection-evidence') || '',
              matched_family_ids: el.getAttribute('data-matched-family-ids') || '',
              raw_state_flags: el.getAttribute('data-raw-state-flags') || '',
              family_match_passed: el.getAttribute('data-family-match-passed') || '',
              family_match_violation_reason: el.getAttribute('data-family-match-violation-reason') || '',
              family_route_owner: el.getAttribute('data-family-route-owner') || '',
              family_early_dispatch_used: el.getAttribute('data-family-early-dispatch-used') || '',
              generic_one_click_solver_skipped: el.getAttribute('data-generic-one-click-solver-skipped') || '',
              generic_target_band_search_skipped: el.getAttribute('data-generic-target-band-search-skipped') || '',
              generic_optimisation_cleanup_skipped: el.getAttribute('data-generic-optimisation-cleanup-skipped') || '',
              generic_publication_fallback_skipped: el.getAttribute('data-generic-publication-fallback-skipped') || '',
              direct_target_band_bypassed_by_family_owner: el.getAttribute('data-direct-target-band-bypassed-by-family-owner') || '',
              family_ladder_candidate_count: el.getAttribute('data-family-ladder-candidate-count') || '',
              render_contract_enabled: el.getAttribute('data-render-contract-enabled') || '',
              render_cta_enabled: el.getAttribute('data-render-cta-enabled') || '',
              render_action_type: el.getAttribute('data-render-action-type') || '',
              render_update_count: el.getAttribute('data-render-update-count') || '',
              render_blocking_reason: el.getAttribute('data-render-blocking-reason') || '',
              render_cta_payload_id: el.getAttribute('data-render-cta-payload-id') || '',
              render_gate_condition: el.getAttribute('data-render-gate-condition') || '',
              render_gate_pres_show_apply: el.getAttribute('data-render-gate-pres-show-apply') || '',
              render_gate_effective_action: el.getAttribute('data-render-gate-effective-action') || '',
              render_gate_terminal_exact: el.getAttribute('data-render-gate-terminal-exact') || '',
              render_gate_button_enabled: el.getAttribute('data-render-gate-button-enabled') || '',
              render_gate_vm_cta_enabled: el.getAttribute('data-render-gate-vm-cta-enabled') || '',
            }));
          const buttons = all("button").map((el) => ({text: text(el), rect: rectObj(el), disabled: !!el.disabled}));
          const codeBlocks = all("pre, code, [data-testid='stCodeBlock'], textarea").map((el) => text(el)).filter(Boolean);
          const inputLabel = Array.from(document.querySelectorAll("label, [data-testid='stWidgetLabel']"))
            .find((el) => visible(el) && text(el).includes("Positive design moment"));
          const guide = cards[0] || null;
          const scrollEls = Array.from(document.querySelectorAll("main, section, div"))
            .filter((el) => el.scrollHeight > el.clientHeight + 40)
            .map((el) => ({tag: el.tagName, testid: el.getAttribute('data-testid') || '', className: String(el.className || ''), scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight}))
            .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
          const plot = all("[data-testid='stPlotlyChart']").at(0) || null;
          return {
            url: window.location.href,
            title: document.title,
            body_text: text(document.body),
            body_text_length: text(document.body).length,
            visible_control_values: {
              positive_moment: readControl("positive_moment", [["positive", "moment"], ["mu*+"]]),
              design_shear: readControl("design_shear", [["design", "shear"], ["vu*"]]),
              width: readControl("width", [["width"], ["b", "mm"]]),
              depth: readControl("depth", [["depth"], ["d", "mm"]]),
              link_dia: readControl("link_dia", [["link", "ø"], ["link", "dia"], ["link"]]),
              link_legs: readControl("link_legs", [["no.", "legs"], ["legs"]]),
              link_spacing: readControl("link_spacing", [["link", "spacing"], ["spacing"]]),
            },
            cards,
            card_count: cards.length,
            first_card_text: guide ? guide.text : "",
            family_selection: guide ? {
              selected_family_id: guide.selected_family_id || "",
              selected_family: guide.selected_family || "",
              selection_reason: guide.selection_reason || "",
              published_family_id: guide.published_family_id || "",
              cta_family_id: guide.cta_family_id || "",
              apply_payload_family_id: guide.apply_payload_family_id || "",
              candidate_family_id: guide.candidate_family_id || "",
              card_family_id: guide.card_family_id || "",
              family_selection_source: guide.family_selection_source || "",
              family_selection_contract: guide.family_selection_contract || "",
              family_chooser_contract: guide.family_chooser_contract || "",
              rejected_families: guide.rejected_families || "",
              selection_evidence: guide.selection_evidence || "",
              matched_family_ids: guide.matched_family_ids || "",
              raw_state_flags: guide.raw_state_flags || "",
              family_match_passed: guide.family_match_passed || "",
              family_match_violation_reason: guide.family_match_violation_reason || "",
              family_route_owner: guide.family_route_owner || "",
              family_early_dispatch_used: guide.family_early_dispatch_used || "",
              generic_one_click_solver_skipped: guide.generic_one_click_solver_skipped || "",
              generic_target_band_search_skipped: guide.generic_target_band_search_skipped || "",
              generic_optimisation_cleanup_skipped: guide.generic_optimisation_cleanup_skipped || "",
              generic_publication_fallback_skipped: guide.generic_publication_fallback_skipped || "",
              direct_target_band_bypassed_by_family_owner: guide.direct_target_band_bypassed_by_family_owner || "",
              family_ladder_candidate_count: guide.family_ladder_candidate_count || "",
              render_contract_enabled: guide.render_contract_enabled || "",
              render_cta_enabled: guide.render_cta_enabled || "",
              render_action_type: guide.render_action_type || "",
              render_update_count: guide.render_update_count || "",
              render_blocking_reason: guide.render_blocking_reason || "",
              render_cta_payload_id: guide.render_cta_payload_id || "",
              render_gate_condition: guide.render_gate_condition || "",
              render_gate_pres_show_apply: guide.render_gate_pres_show_apply || "",
              render_gate_effective_action: guide.render_gate_effective_action || "",
              render_gate_terminal_exact: guide.render_gate_terminal_exact || "",
              render_gate_button_enabled: guide.render_gate_button_enabled || "",
              render_gate_vm_cta_enabled: guide.render_gate_vm_cta_enabled || "",
            } : {},
            buttons,
            button_texts: buttons.map((b) => b.text).filter(Boolean),
            code_blocks: codeBlocks,
            input_label_rect: rectObj(inputLabel),
            design_guide_rect: guide ? guide.rect : null,
            window_scroll_y: window.scrollY,
            scroll_containers: scrollEls.slice(0, 5),
            primary_scroll_top: scrollEls.length ? scrollEls[0].scrollTop : window.scrollY,
            document_height: document.documentElement.scrollHeight,
            viewport_height: window.innerHeight,
            plotly_visible: !!plot,
            plotly_rect: rectObj(plot),
          };
        }
        """
    )
    iframe_buttons: list[dict[str, Any]] = []
    for index, frame in enumerate(page.frames):
        if frame == page.main_frame:
            continue
        try:
            rows = frame.evaluate(
                """
                () => {
                  const visible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
                      rect.width > 0 && rect.height > 0;
                  };
                  return Array.from(document.querySelectorAll("button"))
                    .filter(visible)
                    .map((el) => ({
                      text: (el.innerText || el.textContent || '').trim(),
                      disabled: !!el.disabled,
                      frame_title: document.title || '',
                    }));
                }
                """
            )
        except Exception:
            rows = []
        for row in rows or []:
            if isinstance(row, dict) and str(row.get("text") or "").strip():
                row["frame_index"] = index
                iframe_buttons.append(row)
    if iframe_buttons:
        buttons = list(snapshot.get("buttons") or [])
        buttons.extend(iframe_buttons)
        snapshot["buttons"] = buttons
        snapshot["iframe_buttons"] = iframe_buttons
        snapshot["button_texts"] = [str(button.get("text") or "") for button in buttons if str(button.get("text") or "")]
    else:
        snapshot["iframe_buttons"] = []
    return snapshot


def _diagram_signature(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' &&
              rect.width > 0 && rect.height > 0;
          };
          const plot = Array.from(document.querySelectorAll("[data-testid='stPlotlyChart'], svg"))
            .filter(visible)
            .sort((a, b) => {
              const ar = a.getBoundingClientRect();
              const br = b.getBoundingClientRect();
              return (br.width * br.height) - (ar.width * ar.height);
            })[0];
          if (!plot) return {available: false, reason: "diagram_svg_not_visible"};
          const svg = plot.tagName && plot.tagName.toLowerCase() === "svg" ? plot : plot.querySelector("svg");
          if (!svg) return {available: false, reason: "svg_not_found"};
          const pointEls = Array.from(svg.querySelectorAll(".point, path.point, g.points path, circle"))
            .map((el) => ({
              tag: el.tagName,
              cls: el.getAttribute("class") || "",
              d: el.getAttribute("d") || "",
              transform: el.getAttribute("transform") || "",
              cx: el.getAttribute("cx") || "",
              cy: el.getAttribute("cy") || "",
            }));
          const shapeEls = Array.from(svg.querySelectorAll("path, rect, line, circle"))
            .slice(0, 300)
            .map((el) => ({
              tag: el.tagName,
              cls: el.getAttribute("class") || "",
              d: el.getAttribute("d") || "",
              transform: el.getAttribute("transform") || "",
              x: el.getAttribute("x") || "",
              y: el.getAttribute("y") || "",
              cx: el.getAttribute("cx") || "",
              cy: el.getAttribute("cy") || "",
              width: el.getAttribute("width") || "",
              height: el.getAttribute("height") || "",
            }));
          return {
            available: true,
            point_count: pointEls.length,
            point_signature: JSON.stringify(pointEls),
            shape_signature: JSON.stringify(shapeEls),
          };
        }
        """
    )


def _hash_dict(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _wait_for_product_ready(page: Page, timeout_ms: int = 60_000) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    page.wait_for_function(
        """
        () => {
          const text = document.body && document.body.innerText || '';
          return text.includes('Positive design moment') && text.includes('Design shear');
        }
        """,
        timeout=timeout_ms,
    )
    _wait_for_settle(page)


def _wait_for_settle(page: Page, timeout_ms: int = 45_000) -> None:
    page.wait_for_function(
        """
        () => {
          const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' &&
              rect.width > 0 && rect.height > 0;
          };
          const spinners = Array.from(document.querySelectorAll('[data-testid="stSpinner"], [data-testid="stStatusWidget"], [aria-busy="true"]')).filter(visible);
          return spinners.length === 0;
        }
        """,
        timeout=timeout_ms,
    )
    page.wait_for_timeout(1800)


def _wait_for_design_guide_card(page: Page, timeout_ms: int = 180_000) -> None:
    page.wait_for_function(
        """
        () => {
          const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' &&
              rect.width > 0 && rect.height > 0;
          };
          const cards = Array.from(document.querySelectorAll("[data-testid='design-guide-card'], .fast-guidance-item"))
            .filter(visible)
            .filter((el) => ((el.innerText || el.textContent || '').trim().length > 0));
          return cards.length > 0;
        }
        """,
        timeout=timeout_ms,
    )
    page.wait_for_timeout(1500)


def _set_number(page: Page, label: str, value: float) -> None:
    errors: list[str] = []
    try:
        loc = page.get_by_label(label).first
        loc.wait_for(state="visible", timeout=2500)
        loc.click(timeout=2500)
        page.keyboard.press("Control+A")
        loc.fill(str(value), timeout=2500)
        page.keyboard.press("Enter")
        page.keyboard.press("Tab")
        _wait_for_settle(page)
        return
    except Exception as exc:
        errors.append(f"label_fill:{type(exc).__name__}:{exc}")
    ok = page.evaluate(
        """
        ({label, value}) => {
          const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' &&
              rect.width > 0 && rect.height > 0;
          };
          const norm = (s) => String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
          const needle = norm(label);
            const selectSelector = '[role="combobox"], [data-baseweb="select"]';
            const nodes = Array.from(document.querySelectorAll("label, div, p, span"))
            .filter((el) => visible(el) && norm(el.innerText || el.textContent).includes(needle))
            .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
          const setNative = (input, val) => {
            const proto = Object.getPrototypeOf(input);
            const desc = Object.getOwnPropertyDescriptor(proto, "value") || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
            desc.set.call(input, String(val));
            input.dispatchEvent(new Event("input", {bubbles: true}));
            input.dispatchEvent(new Event("change", {bubbles: true}));
            input.dispatchEvent(new Event("blur", {bubbles: true}));
          };
          for (const node of nodes) {
            let root = node.closest('[data-testid="stNumberInput"], [data-testid="stVerticalBlock"], section, div');
            for (let depth = 0; root && depth < 6; depth += 1, root = root.parentElement) {
              const input = root.querySelector('input[type="number"], input');
              if (input && visible(input) && !input.disabled) {
                input.focus();
                setNative(input, value);
                return true;
              }
            }
          }
          return false;
        }
        """,
        {"label": label, "value": value},
    )
    if not ok:
        raise RuntimeError(f"Could not set visible number input {label!r} to {value}: {errors}")
    page.keyboard.press("Enter")
    _wait_for_settle(page)


def _set_first_matching_number(page: Page, labels: list[str], value: float) -> bool:
    for label in labels:
        try:
            _set_number(page, label, value)
            return True
        except Exception:
            continue
    return False


def _select_by_label(page: Page, label: str, option_text: str) -> None:
    def _click_visible_option() -> None:
        role_option = page.locator('[role="option"]').filter(has_text=option_text)
        if role_option.count() > 0:
            role_option.last.click(timeout=5_000)
            return
        popover_option = page.locator(
            '[data-baseweb="popover"], [role="listbox"], [data-testid="stSelectboxVirtualDropdown"]'
        ).get_by_text(option_text, exact=False)
        if popover_option.count() > 0:
            popover_option.last.click(timeout=5_000)
            return
        page.keyboard.type(str(option_text), delay=20)
        page.keyboard.press("Enter")

    try:
        combo = page.get_by_label(label).first
        combo.wait_for(state="visible", timeout=1500)
        combo.click(timeout=2500)
        page.wait_for_timeout(250)
        _click_visible_option()
        _wait_for_settle(page)
        return
    except Exception:
        pass
    rect = page.evaluate(
        """
        ({label}) => {
          const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' &&
              rect.width > 0 && rect.height > 0;
          };
          const norm = (s) => String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
          const needle = norm(label);
          const nodes = Array.from(document.querySelectorAll("label, div, p, span"))
            .filter((el) => visible(el) && norm(el.innerText || el.textContent).includes(needle))
            .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
          for (const node of nodes) {
            const nr = node.getBoundingClientRect();
              const rowCandidates = Array.from(document.querySelectorAll(selectSelector))
              .filter((combo) => visible(combo))
              .map((combo) => {
                const r = combo.getBoundingClientRect();
                const sameRow = Math.abs((r.top + r.bottom) / 2 - (nr.top + nr.bottom) / 2);
                const xPenalty = r.left < nr.right ? 500 : 0;
                return {combo, r, score: sameRow + xPenalty};
              })
              .sort((a, b) => a.score - b.score);
            if (rowCandidates.length && rowCandidates[0].score < 80) {
              const r = rowCandidates[0].r;
              return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }
            let root = node.closest('[data-testid="stSelectbox"], [data-testid="stVerticalBlock"], section, div');
            for (let depth = 0; root && depth < 6; depth += 1, root = root.parentElement) {
                const combo = root.querySelector(selectSelector);
              if (combo && visible(combo)) {
                const r = combo.getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
              }
            }
          }
          return null;
        }
        """,
        {"label": label},
    )
    if not rect:
        raise RuntimeError(f"Could not find visible selectbox for {label!r}")
    page.mouse.click(float(rect["x"]), float(rect["y"]))
    page.wait_for_timeout(300)
    _click_visible_option()
    _wait_for_settle(page)


def _select_first_matching(page: Page, labels: list[str], option_text: str) -> bool:
    for label in labels:
        try:
            _select_by_label(page, label, option_text)
            return True
        except Exception:
            continue
    return False


def _goto_inputs(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/?page=inputs", wait_until="domcontentloaded", timeout=60_000)
    try:
        page.wait_for_function(
            "() => (document.body && document.body.innerText || '').includes('Go to Design Inputs')",
            timeout=30_000,
        )
        button = page.get_by_text("Go to Design Inputs", exact=True).last
        button.scroll_into_view_if_needed(timeout=10_000)
        button.click(timeout=10_000)
        page.wait_for_timeout(1500)
    except Exception:
        pass
    _wait_for_product_ready(page)


def _save_screenshot(page: Page, artifact_dir: Path, scenario: str, name: str) -> str:
    path = artifact_dir / f"{scenario}_{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def _visible_cta_buttons(snapshot: dict[str, Any]) -> list[str]:
    labels = []
    main_labels = set()
    iframe_rows = []
    button_rows = snapshot.get("buttons") or [
        {"text": text, "disabled": False, "rect": {}}
        for text in snapshot.get("button_texts") or []
    ]
    for button in button_rows:
        if not isinstance(button, dict):
            continue
        if bool(button.get("disabled")):
            continue
        text = button.get("text")
        clean = " ".join(str(text).split())
        if not clean:
            continue
        if "one-click" in clean.lower() or "apply" in clean.lower() or "auto design" in clean.lower():
            if button.get("frame_index") is not None:
                iframe_rows.append(clean)
            else:
                labels.append(clean)
                main_labels.add(clean)
    for clean in iframe_rows:
        if clean not in main_labels:
            labels.append(clean)
    return labels


def _viewport_cta_buttons(snapshot: dict[str, Any]) -> list[str]:
    labels = []
    viewport_height = float(snapshot.get("viewport_height") or 0)
    for button in snapshot.get("buttons") or []:
        if not isinstance(button, dict) or bool(button.get("disabled")):
            continue
        rect = dict(button.get("rect") or {})
        if rect:
            bottom = float(rect.get("bottom") or 0)
            top = float(rect.get("top") or 0)
            if bottom <= 0 or (viewport_height and top >= viewport_height):
                continue
        text = button.get("text")
        clean = " ".join(str(text).split())
        if not clean:
            continue
        if "one-click" in clean.lower() or "apply" in clean.lower() or "auto design" in clean.lower():
            labels.append(clean)
    return labels


def _debug_tokens(snapshot: dict[str, Any]) -> list[str]:
    text = (snapshot.get("body_text") or "").lower()
    code_text = " ".join(snapshot.get("code_blocks") or []).lower()
    return [token for token in FORBIDDEN_DEBUG_TOKENS if token.lower() in text or token.lower() in code_text]


def _result(
    name: str,
    snapshot: dict[str, Any],
    failures: list[str],
    screenshots: dict[str, str],
    extra: dict[str, Any] | None = None,
    *,
    status: str | None = None,
) -> ScenarioResult:
    evidence = {
        "final_snapshot": snapshot,
        "visible_cta_buttons": _visible_cta_buttons(snapshot),
        "viewport_cta_buttons": _viewport_cta_buttons(snapshot),
        "debug_tokens": _debug_tokens(snapshot),
    }
    if extra:
        evidence.update(extra)
    return ScenarioResult(name=name, status=status or ("PASS" if not failures else "FAIL"), failures=failures, evidence=evidence, screenshots=screenshots)


def _assert_resolved(snapshot: dict[str, Any], failures: list[str]) -> None:
    if int(snapshot.get("card_count") or 0) < 1:
        failures.append("Design Guide has no visible final card.")
    text = str(snapshot.get("first_card_text") or "")
    if not text.strip():
        failures.append("Design Guide card is blank.")
    if any(token in text.lower() for token in ("loading", "preparing")):
        failures.append("Design Guide appears to be in a loading/preparing state.")


def _visible_shear_summary_fails(snapshot: dict[str, Any]) -> bool:
    text = str(snapshot.get("body_text") or "")
    marker = "Shear"
    idx = text.find(marker)
    while idx >= 0:
        section = text[idx: idx + 500]
        if "ULS" in section and "FAIL" in section:
            return True
        idx = text.find(marker, idx + len(marker))
    return False


def _summary_segment(snapshot: dict[str, Any], family: str) -> str:
    text = str(snapshot.get("body_text") or "")
    compact_markers = {
        "bending": (("Bending \u2014 ULS", "Bending - ULS", "Bending -- ULS"), ("Shear \u2014 ULS", "Shear - ULS", "Shear -- ULS")),
        "shear": (("Shear \u2014 ULS", "Shear - ULS", "Shear -- ULS"), ("Crack control \u2014 SLS", "Crack control - SLS", "Crack Control", "Deflection")),
        "crack": (("Crack control \u2014 SLS", "Crack control - SLS", "Crack Control"), ("Deflection \u2014 SLS", "Deflection - SLS", "Deflection")),
        "deflection": (("Deflection \u2014 SLS", "Deflection - SLS", "Deflection"), ("Batch design",)),
    }
    start_markers, end_markers = compact_markers.get(family, ((family,), ("",)))
    starts = [(text.find(marker), marker) for marker in start_markers if marker]
    starts = [(idx, marker) for idx, marker in starts if idx >= 0]
    if starts:
        start, start_marker = min(starts, key=lambda item: item[0])
    else:
        start_marker = family
        start = text.find(start_marker)
    if start < 0:
        return ""
    end_candidates = [
        text.find(marker, start + len(start_marker))
        for marker in end_markers
        if marker
    ]
    end_candidates = [idx for idx in end_candidates if idx > start]
    end = min(end_candidates) if end_candidates else -1
    return text[start : end if end > start else start + 900]


def _segment_status(segment: str) -> str | None:
    upper = segment.upper()
    for status in ("FAIL", "NEAR LIMIT", "PASS", "CAPACITY", "NOT RUN", "INFO"):
        if status in upper:
            return status
    return None


def _segment_util(segment: str) -> float | None:
    import re

    match = re.search(r"Utilisation\s+([-+]?\d+(?:\.\d+)?)", segment, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _visible_summary_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    bending = _summary_segment(snapshot, "bending")
    shear = _summary_segment(snapshot, "shear")
    return {
        "bending_status": _segment_status(bending),
        "bending_util": _segment_util(bending),
        "shear_status": _segment_status(shear),
        "shear_util": _segment_util(shear),
        "shear_segment": shear[:900],
        "bending_segment": bending[:600],
    }


def _visible_control_value(snapshot: dict[str, Any], key: str) -> str:
    control = dict((snapshot.get("visible_control_values") or {}).get(key) or {})
    raw = str(control.get("input_value") or control.get("combo_text") or control.get("container_text") or "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[-1]
    return raw.strip()


def _visible_lig_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    dia = _visible_control_value(snapshot, "link_dia")
    legs = _visible_control_value(snapshot, "link_legs")
    spacing = _visible_control_value(snapshot, "link_spacing")
    body = str(snapshot.get("body_text") or "")
    compact = " ".join(body.split())
    return {
        "link_dia_visible": dia,
        "link_legs_visible": legs,
        "link_spacing_visible": spacing,
        "body_mentions_n10_2_100": "N10-2 lig @ 100" in body or "2-leg N10 @ 100" in body or "N10 @ 100" in body,
        "body_mentions_ligatures_off": "0 (off)" in body or "0xD0" in compact,
    }


def _scenario_duplicate_cta(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    name = "scenario_a_duplicate_cta"
    _goto_inputs(page, base_url)
    _set_number(page, "Positive design moment Mu*+ (kNm)", 900)
    _set_number(page, "Design shear Vu* (kN)", 20)
    _set_first_matching_number(page, ["Width b (mm)", "Width"], 300)
    _set_first_matching_number(page, ["Depth D (mm)", "Depth"], 350)
    _wait_for_design_guide_card(page)
    snap = _snapshot(page)
    screenshots = {"final": _save_screenshot(page, artifact_dir, name, "final")}
    failures: list[str] = []
    _assert_resolved(snap, failures)
    ctas = _visible_cta_buttons(snap)
    one_click = [label for label in ctas if "run one-click auto design" in label.lower()]
    if len(one_click) > 1:
        failures.append(f"Duplicate Run one-click auto design CTAs visible: {one_click}")
    if len(ctas) != len(set(ctas)):
        failures.append(f"Duplicate equivalent primary CTA labels visible: {ctas}")
    return _result(name, snap, failures, screenshots)


def _scenario_cta_click_stability(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    name = "scenario_b_cta_click_stability"
    _goto_inputs(page, base_url)
    _set_number(page, "Positive design moment Mu*+ (kNm)", 900)
    _set_number(page, "Design shear Vu* (kN)", 20)
    _wait_for_design_guide_card(page)
    page.evaluate(
        """
        () => {
          const scrolls = Array.from(document.querySelectorAll("main, section, div"))
            .filter((el) => el.scrollHeight > el.clientHeight + 40)
            .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
          if (scrolls.length) scrolls[0].scrollTop = Math.min(900, scrolls[0].scrollHeight - scrolls[0].clientHeight);
          window.scrollTo(0, 600);
        }
        """
    )
    before = _snapshot(page)
    before_shot = _save_screenshot(page, artifact_dir, name, "before_click")
    buttons = page.get_by_role("button", name="Run one-click auto design")
    failures: list[str] = []
    if buttons.count() < 1:
        failures.append("No visible Run one-click auto design CTA available to click.")
        after = before
    else:
        buttons.first.click(timeout=10_000)
        _wait_for_settle(page, timeout_ms=90_000)
        after = _snapshot(page)
    after_shot = _save_screenshot(page, artifact_dir, name, "after_click")
    _assert_resolved(after, failures)
    if (before.get("primary_scroll_top") or 0) > 300 and (after.get("primary_scroll_top") or 0) < 50:
        failures.append(f"Scroll jumped to top after click: {before.get('primary_scroll_top')} -> {after.get('primary_scroll_top')}")
    input_rect = after.get("input_label_rect") or {}
    if input_rect and (input_rect.get("bottom", 0) < -50 or input_rect.get("top", 10_000) > (after.get("viewport_height") or 0) + 250):
        failures.append(f"Input area moved far outside viewport after click: {input_rect}")
    ctas = _visible_cta_buttons(after)
    if len(ctas) != len(set(ctas)):
        failures.append(f"Duplicate CTA labels after click: {ctas}")
    return _result(name, after, failures, {"before": before_shot, "after": after_shot}, {"before_snapshot": before})


def _scenario_underdesign_repair(
    page: Page,
    base_url: str,
    artifact_dir: Path,
    *,
    name: str,
    pure_shear: bool = False,
    pure_bending: bool = False,
) -> ScenarioResult:
    _goto_inputs(page, base_url)
    _set_number(page, "Positive design moment Mu*+ (kNm)", 900 if pure_bending else 0)
    if pure_shear:
        _set_first_matching_number(page, ["Width b (mm)", "Width"], 250)
        _set_first_matching_number(page, ["Depth D (mm)", "Depth"], 300)
    else:
        _set_first_matching_number(page, ["Width b (mm)", "Width"], 300)
        _set_first_matching_number(page, ["Depth D (mm)", "Depth"], 350)
    setup_failures: list[str] = []
    if not _select_first_matching(page, ["Link \u00d8 (mm)", "Link Ã˜ (mm)", "Link"], "10"):
        setup_failures.append("Could not set visible link diameter select to 10.")
    if not _select_first_matching(page, ["No. of legs", "legs"], "2"):
        setup_failures.append("Could not set visible leg count select to 2.")
    _set_first_matching_number(page, ["Link spacing", "spacing"], 300)
    _set_number(page, "Design shear Vu* (kN)", 20 if pure_bending else 300)
    setup_snap = _snapshot(page)
    setup_shot = _save_screenshot(page, artifact_dir, name, "after_setup")
    try:
        _wait_for_design_guide_card(page)
    except Exception as exc:
        setup_failures.append(f"Design Guide did not resolve to a visible card after normal-mode setup: {type(exc).__name__}: {exc}")
    snap = _snapshot(page)
    screenshots = {"final": _save_screenshot(page, artifact_dir, name, "final")}
    screenshots["after_setup"] = setup_shot
    failures: list[str] = []
    not_proven: list[str] = []
    _assert_resolved(snap, failures)
    text = str(snap.get("first_card_text") or snap.get("body_text") or "").lower()
    ctas = _visible_cta_buttons(snap)
    summary = _visible_summary_state(snap)
    lig_state = _visible_lig_state(snap)
    family_selection = dict(snap.get("family_selection") or {})
    selected_family_id = str(family_selection.get("selected_family_id") or "").strip()
    selected_family = str(family_selection.get("selected_family") or selected_family_id).strip()
    selection_reason = str(family_selection.get("selection_reason") or "").strip()
    published_family_id = str(family_selection.get("published_family_id") or "").strip()
    cta_family_id = str(family_selection.get("cta_family_id") or "").strip()
    apply_payload_family_id = str(family_selection.get("apply_payload_family_id") or "").strip()
    family_route_owner = str(family_selection.get("family_route_owner") or "").strip()
    family_chooser_contract = str(family_selection.get("family_chooser_contract") or "").strip()
    try:
        rejected_families = json.loads(str(family_selection.get("rejected_families") or "{}"))
        if not isinstance(rejected_families, dict):
            rejected_families = {}
    except Exception:
        rejected_families = {}
    try:
        selection_evidence = json.loads(str(family_selection.get("selection_evidence") or "{}"))
        if not isinstance(selection_evidence, dict):
            selection_evidence = {}
    except Exception:
        selection_evidence = {}
    try:
        matched_family_ids = json.loads(str(family_selection.get("matched_family_ids") or "[]"))
        if not isinstance(matched_family_ids, list):
            matched_family_ids = []
    except Exception:
        matched_family_ids = []
    try:
        raw_state_flags = json.loads(str(family_selection.get("raw_state_flags") or "{}"))
        if not isinstance(raw_state_flags, dict):
            raw_state_flags = {}
    except Exception:
        raw_state_flags = {}
    family_match_passed_raw = str(family_selection.get("family_match_passed") or "").strip().lower()
    family_match_passed = family_match_passed_raw in {"true", "1", "yes"}
    family_match_violation_reason = str(family_selection.get("family_match_violation_reason") or "").strip()
    render_cta_payload_id = str(family_selection.get("render_cta_payload_id") or "").strip()

    def _selection_bool(name: str) -> bool | None:
        raw = str(family_selection.get(name) or "").strip().lower()
        if raw in {"true", "1", "yes"}:
            return True
        if raw in {"false", "0", "no"}:
            return False
        return None

    family_early_dispatch_used = _selection_bool("family_early_dispatch_used")
    generic_one_click_solver_skipped = _selection_bool("generic_one_click_solver_skipped")
    generic_target_band_search_skipped = _selection_bool("generic_target_band_search_skipped")
    generic_optimisation_cleanup_skipped = _selection_bool("generic_optimisation_cleanup_skipped")
    generic_publication_fallback_skipped = _selection_bool("generic_publication_fallback_skipped")
    direct_target_band_bypassed_by_family_owner = _selection_bool(
        "direct_target_band_bypassed_by_family_owner"
    )
    family_ladder_candidate_count_raw = str(
        family_selection.get("family_ladder_candidate_count") or ""
    ).strip()
    try:
        family_ladder_candidate_count = (
            int(float(family_ladder_candidate_count_raw))
            if family_ladder_candidate_count_raw
            else None
        )
    except Exception:
        family_ladder_candidate_count = None
    setup_summary = _visible_summary_state(setup_snap)
    setup_lig_state = _visible_lig_state(setup_snap)
    shear_fail_visible = summary.get("shear_status") == "FAIL"
    bending_dominated = summary.get("bending_status") == "FAIL" or any(
        token in text
        for token in (
            "minimum tensile reinforcement fails",
            "bending utilisation moves",
            "bending utilization moves",
        )
    )
    bending_fail_visible = bool(bending_dominated)
    if pure_bending:
        if not bending_fail_visible:
            not_proven.append("Scenario setup did not produce a visible bending FAIL summary.")
            not_proven.extend(setup_failures)
        if shear_fail_visible:
            failures.append("Pure bending scenario setup produced an active or visible shear failure.")
    elif not shear_fail_visible:
        not_proven.append("Scenario setup did not produce a visible shear FAIL summary.")
        not_proven.extend(setup_failures)
    if pure_shear and bending_dominated:
        failures.append("Pure shear scenario setup produced an active or visible bending failure.")
    has_repair_action = bool(ctas) and (
        "cleanup" not in text
        and ("shear" in text or "repair" in text or "strengthening" in text or "increase" in text or "tighten" in text or "one-click" in text)
    )
    contract_boundary_blocked = "blocked by contract" in text or "repair required" in text
    has_no_repair_evidence = any(
        token in text
        for token in ("no-repair", "no repair", "locked_no_repair", "locked no repair", "exhaustive", "cannot")
    ) and not contract_boundary_blocked
    if "design is efficient" in text:
        failures.append("Shear underdesign reached efficient/pass text instead of repair or no-repair evidence.")
    if "cleanup" in text and shear_fail_visible:
        failures.append("Shear underdesign published cleanup text instead of repair/no-repair evidence.")
    if "pass" in text and "fail" not in text:
        failures.append("Shear underdesign published PASS terminal text without visible shear fail repair/no-repair evidence.")
    if len(ctas) != len(set(ctas)):
        failures.append(f"Duplicate CTA labels in shear underdesign scenario: {ctas}")
    forbidden_shear_fail_families = {
        "COMBINED_OVERDESIGN",
        "SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_OVERDESIGN_GOVERNS",
        "TARGET_BAND_REACHED",
        "EXACT_STOP_PROVEN",
    }
    active_fail_visible = bool(bending_fail_visible if pure_bending else shear_fail_visible)
    if active_fail_visible and not selected_family_id:
        failures.append("Visible shear FAIL did not expose selected_family_id.")
    if active_fail_visible and family_chooser_contract != "family_chooser_contract":
        failures.append("Visible shear FAIL did not expose active family_chooser_contract.")
    if active_fail_visible and len(matched_family_ids) != 1:
        failures.append(f"Family chooser did not expose exactly one matched family: {matched_family_ids!r}.")
    if active_fail_visible and selected_family_id and matched_family_ids and matched_family_ids[0] != selected_family_id:
        failures.append(
            f"Family chooser selected {selected_family_id!r} but matched_family_ids={matched_family_ids!r}."
        )
    if active_fail_visible and not raw_state_flags:
        failures.append("Family chooser did not expose raw_state_flags.")
    allowed_selected_families = (
        {"BENDING_FAIL_GOVERNS"}
        if pure_bending
        else {"SHEAR_FAIL_GOVERNS"}
        if pure_shear
        else {"COMBINED_BENDING_SHEAR_FAIL"}
    )
    if active_fail_visible and selected_family_id not in allowed_selected_families:
        failures.append(f"Visible active failure selected invalid family: {selected_family_id!r}.")
    if active_fail_visible and selected_family and selected_family != selected_family_id:
        failures.append(f"selected_family {selected_family!r} did not match selected_family_id {selected_family_id!r}.")
    if active_fail_visible and not selection_reason:
        failures.append("Visible active failure did not expose a family chooser selection reason.")
    if active_fail_visible and selected_family_id == "COMBINED_BENDING_SHEAR_FAIL":
        if "BENDING_FAIL_GOVERNS" not in rejected_families or "SHEAR_FAIL_GOVERNS" not in rejected_families:
            failures.append("Combined failure selection did not document pure bending and pure shear family rejections.")
    if active_fail_visible and selected_family_id == "BENDING_FAIL_GOVERNS":
        if "COMBINED_BENDING_SHEAR_FAIL" not in rejected_families:
            failures.append("Pure bending selection did not document combined-family rejection.")
        if "SHEAR_FAIL_GOVERNS" not in rejected_families:
            failures.append("Pure bending selection did not document shear-family rejection.")
        payload_id_lower = render_cta_payload_id.lower()
        if not render_cta_payload_id:
            failures.append("Pure bending repair CTA did not expose a render payload id.")
        elif any(token in payload_id_lower for token in ("shear_fail_governs", "combined_bending_shear_fail", "local_cleanup", "unknown", "cleanup")):
            failures.append(f"Pure bending repair CTA exposed stale non-bending payload id: {render_cta_payload_id!r}.")
        elif not render_cta_payload_id.startswith("BENDING_FAIL_GOVERNS:"):
            failures.append(
                f"Pure bending repair CTA payload id does not start with BENDING_FAIL_GOVERNS: {render_cta_payload_id!r}."
            )
    if active_fail_visible and selected_family_id == "SHEAR_FAIL_GOVERNS":
        if "COMBINED_BENDING_SHEAR_FAIL" not in rejected_families:
            failures.append("Pure shear selection did not document combined-family rejection.")
        if "BENDING_FAIL_GOVERNS" not in rejected_families:
            failures.append("Pure shear selection did not document bending-family rejection.")
        payload_id_lower = render_cta_payload_id.lower()
        if not render_cta_payload_id:
            failures.append("Pure shear repair CTA did not expose a render payload id.")
        elif "combined" in payload_id_lower or "cleanup" in payload_id_lower:
            failures.append(f"Pure shear repair CTA exposed stale non-shear payload id: {render_cta_payload_id!r}.")
        elif not (
            "SHEAR_FAIL_GOVERNS" in render_cta_payload_id
            and "shear_fail" in payload_id_lower
            and "repair" in payload_id_lower
        ):
            failures.append(f"Pure shear repair CTA payload id does not identify SHEAR_FAIL_GOVERNS/shear_fail/repair: {render_cta_payload_id!r}.")
        refined_required = {
            "active_shear_fail",
            "active_bending_fail",
            "bending_status",
            "bending_utilisation",
            "bending_target_band_status",
            "minimum_bending_reinforcement_status",
            "geometry_reduction_status",
            "geometry_detailing_blocker_status",
            "why_bending_family_rejected",
            "why_min_bending_reo_rejected_or_selected",
            "why_geometry_detailing_rejected_or_selected",
            "why_target_band_rejected_or_selected",
        }
        refined_missing = sorted(key for key in refined_required if key not in selection_evidence)
        if refined_missing:
            not_proven.append(
                "Refined SHEAR_FAIL_GOVERNS chooser diagnostics missing: "
                + ", ".join(refined_missing)
            )
        else:
            if selection_evidence.get("active_shear_fail") is not True:
                failures.append("Refined chooser did not prove active_shear_fail=true for SHEAR_FAIL_GOVERNS.")
            if selection_evidence.get("active_bending_fail") is not False:
                failures.append("Refined chooser did not prove active_bending_fail=false for SHEAR_FAIL_GOVERNS.")
            if str(selection_evidence.get("geometry_detailing_blocker_status") or "").lower() not in {
                "absent",
                "false",
                "not_active",
                "rejected",
            }:
                not_proven.append("Refined chooser did not prove geometry/detailing blocker is absent.")
    if active_fail_visible and published_family_id in forbidden_shear_fail_families:
        failures.append(f"Visible shear FAIL published forbidden family: {published_family_id}.")
    if active_fail_visible and cta_family_id in forbidden_shear_fail_families:
        failures.append(f"Visible shear FAIL exposed forbidden CTA family: {cta_family_id}.")
    if active_fail_visible and selected_family_id and published_family_id and selected_family_id != published_family_id:
        failures.append(
            "Family selection mismatch: selected_family_id "
            f"{selected_family_id} != published_family_id {published_family_id}."
        )
    if active_fail_visible and selected_family_id and cta_family_id and selected_family_id != cta_family_id:
        failures.append(
            f"Family CTA mismatch: selected_family_id {selected_family_id} != cta_family_id {cta_family_id}."
        )
    if active_fail_visible and selected_family_id and apply_payload_family_id and selected_family_id != apply_payload_family_id:
        failures.append(
            "Family apply-payload mismatch: selected_family_id "
            f"{selected_family_id} != apply_payload_family_id {apply_payload_family_id}."
        )
    if (
        active_fail_visible
        and selected_family_id == "COMBINED_BENDING_SHEAR_FAIL"
        and "combined_bending_shear_fail" not in family_route_owner.lower()
    ):
        failures.append(
            "Combined fail product path did not expose combined-family owner routing evidence."
        )
    if (
        active_fail_visible
        and selected_family_id == "BENDING_FAIL_GOVERNS"
        and "bending_fail" not in family_route_owner.lower()
        and has_repair_action
    ):
        failures.append("Pure bending repair action did not expose bending-family owner routing evidence.")
    if (
        active_fail_visible
        and selected_family_id == "SHEAR_FAIL_GOVERNS"
        and "shear_fail" not in family_route_owner.lower()
        and has_repair_action
    ):
        failures.append("Pure shear repair action did not expose shear-family owner routing evidence.")
    family_mismatch_blocked = "family mismatch blocked" in text or "publication blocked by family contract" in text
    if (
        active_fail_visible
        and family_match_passed_raw
        and not family_match_passed
        and not family_mismatch_blocked
    ):
        failures.append(
            f"Family match contract failed: {family_match_violation_reason or family_match_passed_raw}."
        )
    if active_fail_visible and contract_boundary_blocked and not has_repair_action and not has_no_repair_evidence:
        failures.append(
            "Contract boundary blocked invalid underdesign publication but did not publish repair action or legal no-repair proof."
        )
    if active_fail_visible and not has_repair_action and not has_no_repair_evidence:
        failures.append("Shear underdesign has neither visible repair action nor explicit no-repair evidence.")
    status = "NOT_PROVEN" if not_proven and not failures else None
    return _result(
        name,
        snap,
        failures + not_proven,
        screenshots,
        {
            "setup_snapshot": setup_snap,
            "setup_visible_summary": setup_summary,
            "final_visible_summary": summary,
            "setup_lig_state": setup_lig_state,
            "final_lig_state": lig_state,
            "setup_warnings": setup_failures,
            "visible_shear_fail_summary": shear_fail_visible,
            "visible_bending_fail_summary": bending_fail_visible,
            "bending_dominated_or_ambiguous": bending_dominated,
            "expected_selected_family": (
                "BENDING_FAIL_GOVERNS"
                if pure_bending
                else "SHEAR_FAIL_GOVERNS"
                if pure_shear
                else "COMBINED_BENDING_SHEAR_FAIL"
            ),
            "pure_shear_expected": pure_shear,
            "pure_bending_expected": pure_bending,
            "has_repair_action": has_repair_action,
            "has_no_repair_evidence": has_no_repair_evidence,
            "contract_boundary_blocked": contract_boundary_blocked,
            "selected_family_id": selected_family_id,
            "selected_family": selected_family,
            "selection_reason": selection_reason,
            "published_family_id": published_family_id,
            "cta_family_id": cta_family_id,
            "apply_payload_family_id": apply_payload_family_id,
            "candidate_family_id": family_selection.get("candidate_family_id"),
            "card_family_id": family_selection.get("card_family_id"),
            "family_selection_source": family_selection.get("family_selection_source"),
            "family_selection_contract": family_selection.get("family_selection_contract"),
            "family_chooser_contract": family_chooser_contract,
            "rejected_families": rejected_families,
            "selection_evidence": selection_evidence,
            "matched_family_ids": matched_family_ids,
            "raw_state_flags": raw_state_flags,
            "refined_shear_fail_selection_not_proven": [
                reason for reason in not_proven if "Refined SHEAR_FAIL_GOVERNS" in reason
            ],
            "family_match_passed": family_match_passed if family_match_passed_raw else None,
            "family_match_violation_reason": family_match_violation_reason,
            "family_route_owner": family_route_owner,
            "family_early_dispatch_used": family_early_dispatch_used,
            "generic_one_click_solver_skipped": generic_one_click_solver_skipped,
            "generic_target_band_search_skipped": generic_target_band_search_skipped,
            "generic_optimisation_cleanup_skipped": generic_optimisation_cleanup_skipped,
            "generic_publication_fallback_skipped": generic_publication_fallback_skipped,
            "direct_target_band_bypassed_by_family_owner": direct_target_band_bypassed_by_family_owner,
            "family_ladder_candidate_count": family_ladder_candidate_count,
            "render_cta_payload_id": render_cta_payload_id,
            "not_proven_reasons": not_proven,
            "product_failures": failures,
        },
        status=status,
    )


def _scenario_pure_shear_underdesign(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    return _scenario_underdesign_repair(
        page,
        base_url,
        artifact_dir,
        name="scenario_c1_pure_shear_underdesign_repair",
        pure_shear=True,
    )


def _scenario_combined_bending_shear_underdesign(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    return _scenario_underdesign_repair(
        page,
        base_url,
        artifact_dir,
        name="scenario_c2_combined_bending_shear_underdesign_repair",
        pure_shear=False,
    )


def _scenario_pure_bending_underdesign(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    return _scenario_underdesign_repair(
        page,
        base_url,
        artifact_dir,
        name="scenario_c3_pure_bending_underdesign_repair",
        pure_bending=True,
    )


def _scenario_shear_underdesign(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    return _scenario_combined_bending_shear_underdesign(page, base_url, artifact_dir)


def _scenario_shear_overdesign(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    name = "scenario_d_shear_overdesign_cleanup"
    _goto_inputs(page, base_url)
    _set_number(page, "Positive design moment Mu*+ (kNm)", 0)
    _set_number(page, "Design shear Vu* (kN)", 5)
    _set_first_matching_number(page, ["Width b (mm)", "Width"], 250)
    _set_first_matching_number(page, ["Depth D (mm)", "Depth"], 300)
    setup_failures: list[str] = []
    if not _select_first_matching(page, ["Link \u00d8 (mm)", "Link Ã˜ (mm)", "Link"], "10"):
        setup_failures.append("Could not set visible link diameter select to 10.")
    if not _select_first_matching(page, ["No. of legs", "legs"], "2"):
        setup_failures.append("Could not set visible leg count select to 2.")
    _set_first_matching_number(page, ["Link spacing", "spacing"], 100)
    setup_snap = _snapshot(page)
    setup_shot = _save_screenshot(page, artifact_dir, name, "after_setup")
    try:
        _wait_for_design_guide_card(page)
    except Exception as exc:
        setup_failures.append(f"Design Guide did not resolve to a visible card after normal-mode setup: {type(exc).__name__}: {exc}")
    page.wait_for_timeout(2500)
    snap = _snapshot(page)
    screenshots = {"after_setup": setup_shot, "final": _save_screenshot(page, artifact_dir, name, "final")}
    failures: list[str] = []
    not_proven: list[str] = list(setup_failures)
    _assert_resolved(snap, failures)
    summary = _visible_summary_state(snap)
    setup_summary = _visible_summary_state(setup_snap)
    lig_state = _visible_lig_state(snap)
    setup_lig_state = _visible_lig_state(setup_snap)
    lig_text = " ".join(
        str(lig_state.get(key) or "")
        for key in ("link_dia_visible", "link_legs_visible", "link_spacing_visible")
    ).lower()
    active_ligs_preserved = bool(
        lig_state.get("body_mentions_n10_2_100")
        or ("10" in lig_text and "2" in lig_text and "100" in lig_text)
    )
    shear_pass_visible = summary.get("shear_status") in {"PASS", "NEAR LIMIT"}
    shear_overdesigned_visible = bool(
        shear_pass_visible
        and summary.get("shear_util") is not None
        and float(summary.get("shear_util")) < 0.88
    )
    if not active_ligs_preserved:
        not_proven.append("Scenario setup did not preserve visible active N10-2 lig @ 100 or equivalent control values.")
    if not shear_pass_visible:
        not_proven.append("Scenario setup did not produce a visible passing shear state.")
    if not shear_overdesigned_visible:
        not_proven.append("Scenario setup did not prove visible shear overdesign below the target band.")
    text = str(snap.get("first_card_text") or snap.get("body_text") or "").lower()
    ctas = _visible_cta_buttons(snap)
    has_cleanup_action = bool(ctas) and any(token in " ".join(ctas).lower() for token in ("one-click", "apply", "auto design"))
    has_visible_exact_stop = any(token in text for token in ("exact", "no further", "checked", "exhaustive", "already removed", "no executor-backed", "blocked by", "cannot"))
    overdesign_state_proven = bool(active_ligs_preserved and shear_overdesigned_visible)
    if overdesign_state_proven and "blocked" in text and not has_visible_exact_stop:
        failures.append("Overdesign cleanup shows blocked text without visible exact-stop/blocker proof.")
    if overdesign_state_proven and "design is efficient" in text and not has_cleanup_action and not has_visible_exact_stop:
        failures.append("Overdesign says Design is efficient without visible cleanup action or exact-stop proof.")
    if overdesign_state_proven and not has_cleanup_action and not has_visible_exact_stop:
        failures.append("Shear overdesign has neither visible cleanup action nor visible exact-stop proof.")
    status = "NOT_PROVEN" if not_proven and not failures else None
    return _result(
        name,
        snap,
        failures + not_proven,
        screenshots,
        {
            "setup_snapshot": setup_snap,
            "setup_visible_summary": setup_summary,
            "final_visible_summary": summary,
            "setup_lig_state": setup_lig_state,
            "final_lig_state": lig_state,
            "active_ligs_preserved": active_ligs_preserved,
            "shear_pass_visible": shear_pass_visible,
            "shear_overdesigned_visible": shear_overdesigned_visible,
            "overdesign_state_proven": overdesign_state_proven,
            "has_cleanup_action": has_cleanup_action,
            "has_visible_exact_stop": has_visible_exact_stop,
            "not_proven_reasons": not_proven,
            "product_failures": failures,
        },
        status=status,
    )


def _scenario_debug_visibility(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    name = "scenario_e_debug_visibility"
    _goto_inputs(page, base_url)
    snap = _snapshot(page)
    screenshots = {"final": _save_screenshot(page, artifact_dir, name, "final")}
    failures: list[str] = []
    tokens = _debug_tokens(snap)
    if tokens:
        failures.append(f"Normal UI exposes debug/probe/details tokens: {tokens}")
    details_count = page.locator("[data-testid='design-guide-details']").count()
    visible_details = 0
    for idx in range(details_count):
        try:
            if page.locator("[data-testid='design-guide-details']").nth(idx).is_visible(timeout=100):
                visible_details += 1
        except Exception:
            pass
    if visible_details:
        failures.append(f"Normal UI has visible design-guide-details nodes: {visible_details}")
    return _result(name, snap, failures, screenshots, {"visible_design_guide_details_count": visible_details})


def _scenario_reo_refresh(page: Page, base_url: str, artifact_dir: Path) -> ScenarioResult:
    name = "scenario_f_reo_refresh"
    _goto_inputs(page, base_url)
    before_sig = _diagram_signature(page)
    before_hash = _hash_dict(before_sig)
    before_shot = _save_screenshot(page, artifact_dir, name, "before_geometry")
    _set_first_matching_number(page, ["Width b (mm)", "Width"], 650)
    _set_first_matching_number(page, ["Depth D (mm)", "Depth"], 650)
    after_sig = _diagram_signature(page)
    after_hash = _hash_dict(after_sig)
    after = _snapshot(page)
    after_shot = _save_screenshot(page, artifact_dir, name, "after_geometry")
    failures: list[str] = []
    if not before_sig.get("available") or not after_sig.get("available"):
        failures.append(f"Reo refresh could not be measured reliably: before={before_sig}, after={after_sig}")
    elif before_hash == after_hash:
        failures.append("Diagram SVG signature did not change after visible geometry edits.")
    elif before_sig.get("point_count") and before_sig.get("point_signature") == after_sig.get("point_signature"):
        failures.append("Diagram changed after geometry edit, but reinforcement point signature did not change.")
    return _result(
        name,
        after,
        failures,
        {"before": before_shot, "after": after_shot},
        {
            "before_diagram_signature_hash": before_hash,
            "after_diagram_signature_hash": after_hash,
            "before_point_count": before_sig.get("point_count"),
            "after_point_count": after_sig.get("point_count"),
            "point_signature_changed": before_sig.get("point_signature") != after_sig.get("point_signature"),
            "diagram_measurement": "visible Plotly SVG signature and reinforcement point signature",
        },
    )


SCENARIOS = (
    _scenario_duplicate_cta,
    _scenario_cta_click_stability,
    _scenario_pure_shear_underdesign,
    _scenario_combined_bending_shear_underdesign,
    _scenario_pure_bending_underdesign,
    _scenario_shear_overdesign,
    _scenario_debug_visibility,
    _scenario_reo_refresh,
)

SCENARIO_BY_NAME = {
    "scenario_a_duplicate_cta": _scenario_duplicate_cta,
    "scenario_b_cta_click_stability": _scenario_cta_click_stability,
    "scenario_c_shear_underdesign_repair": _scenario_shear_underdesign,
    "scenario_c1_pure_shear_underdesign_repair": _scenario_pure_shear_underdesign,
    "scenario_c2_combined_bending_shear_underdesign_repair": _scenario_combined_bending_shear_underdesign,
    "scenario_c3_pure_bending_underdesign_repair": _scenario_pure_bending_underdesign,
    "scenario_d_shear_overdesign_cleanup": _scenario_shear_overdesign,
    "scenario_e_debug_visibility": _scenario_debug_visibility,
    "scenario_f_reo_refresh": _scenario_reo_refresh,
}


def _start_server(port: int) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    log_dir = ARTIFACT_ROOT
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = open(log_dir / f"product_path_streamlit_{port}.log", "w", encoding="utf-8")
    stderr = open(log_dir / f"product_path_streamlit_{port}.err.log", "w", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port), "--server.headless", "true"],
        cwd=REPO,
        env=env,
        stdout=stdout,
        stderr=stderr,
        text=True,
    )


def _wait_for_server(port: int, timeout_sec: int = 60) -> None:
    import socket

    deadline = time.time() + timeout_sec
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Server on port {port} did not become reachable: {last_error}")


def _write_reports(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Product-Path Gate",
        "",
        f"- Normal product-path result: **{report['normal_product_path_result']}**",
        f"- Browser-test mode: {report['browser_test_mode']}",
        f"- Pass count: {report['pass_count']}/{report['total_count']}",
        f"- Fail count: {report.get('fail_count', 0)}",
        f"- Not proven count: {report.get('not_proven_count', 0)}",
        f"- Manual smoke: {report['manual_smoke_result']}",
        f"- Started: {report['started_at']}",
        f"- Finished: {report['finished_at']}",
        "",
        "## Scenario Results",
        "",
    ]
    for result in report["results"]:
        lines.extend(
            [
                f"### {result['name']}",
                "",
                f"- Status: {result['status']}",
                f"- Failures: {len(result['failures'])}",
            ]
        )
        for failure in result["failures"]:
            lines.append(f"  - {failure}")
        lines.append("")
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9310)
    parser.add_argument("--headed", action="store_true", default=False)
    parser.add_argument("--reuse-existing-server", action="store_true", default=False)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIO_BY_NAME),
        help="Run only the named scenario. May be provided more than once. Defaults to the full gate.",
    )
    args = parser.parse_args(argv)

    started = time.strftime("%Y-%m-%dT%H-%M-%S")
    run_id = f"{started}_pid{os.getpid()}"
    artifact_dir = ARTIFACT_ROOT / "design_guide_product_path" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    results: list[ScenarioResult] = []
    browser_test_mode = "unset"
    try:
        if args.reuse_existing_server:
            browser_test_mode = os.environ.get("CODEX_BROWSER_TEST_MODE") or "unset"
            if browser_test_mode not in ("unset", "", "0", "false", "False"):
                raise RuntimeError(f"CODEX_BROWSER_TEST_MODE is set in current environment: {browser_test_mode}")
            _wait_for_server(args.port)
        selected_scenarios = [SCENARIO_BY_NAME[name] for name in args.scenario] if args.scenario else list(SCENARIOS)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed)
            for scenario_index, scenario in enumerate(selected_scenarios):
                scenario_port = args.port if args.reuse_existing_server else args.port + scenario_index
                scenario_server: subprocess.Popen[str] | None = None
                if not args.reuse_existing_server:
                    scenario_server = _start_server(scenario_port)
                    _wait_for_server(scenario_port)
                base_url = f"http://127.0.0.1:{scenario_port}"
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                try:
                    results.append(scenario(page, base_url, artifact_dir))
                except Exception as exc:
                    shot = ""
                    try:
                        shot = _save_screenshot(page, artifact_dir, scenario.__name__, "exception")
                    except Exception:
                        pass
                    results.append(
                        ScenarioResult(
                            name=scenario.__name__,
                            status="FAIL",
                            failures=[f"{type(exc).__name__}: {exc}"],
                            evidence={"exception": repr(exc)},
                            screenshots={"exception": shot} if shot else {},
                        )
                    )
                finally:
                    context.close()
                    if scenario_server is not None:
                        scenario_server.terminate()
                        try:
                            scenario_server.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            scenario_server.kill()
            browser.close()
    finally:
        pass

    finished = time.strftime("%Y-%m-%dT%H-%M-%S")
    serialised = [
        {
            "name": result.name,
            "status": result.status,
            "failures": result.failures,
            "evidence": result.evidence,
            "screenshots": result.screenshots,
        }
        for result in results
    ]
    if results and all(result.status == "PASS" for result in results):
        normal_result = "Normal product-path PASS"
    elif any(result.status == "FAIL" for result in results):
        normal_result = "Normal product-path FAIL"
    else:
        normal_result = "Normal product-path NOT_PROVEN"
    report = {
        "phase": "Family Strategy Program - Phase 3A",
        "started_at": started,
        "finished_at": finished,
        "run_id": run_id,
        "normal_product_path_result": normal_result,
        "browser_test_mode": browser_test_mode,
        "manual_smoke_result": "manual smoke NOT RUN",
        "port": args.port,
        "used_replay_injection": False,
        "used_hidden_probe_for_pass_fail": False,
        "pass_count": sum(1 for result in results if result.status == "PASS"),
        "fail_count": sum(1 for result in results if result.status == "FAIL"),
        "not_proven_count": sum(1 for result in results if result.status == "NOT_PROVEN"),
        "total_count": len(results),
        "results": serialised,
    }
    report_path = ARTIFACT_ROOT / f"design_guide_product_path_gate_{run_id}.json"
    _write_reports(report, report_path)
    print(normal_result)
    print(f"Report: {report_path}")
    print(f"Markdown: {report_path.with_suffix('.md')}")
    return 0 if normal_result.endswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
