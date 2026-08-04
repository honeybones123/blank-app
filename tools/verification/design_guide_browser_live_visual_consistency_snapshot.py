"""Browser/live Design Guide visual consistency snapshot.

Proof-only verifier. It captures the browser-visible relationship between the
summary cards, Final Design Guide card, CTA/action state, fallback/stale shell
markers, and state/hash probes. It does not change product behaviour, family
runtimes, contracts, CTA routing, apply routing, or visible wording.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import (  # noqa: E402
    _browser_state_raw_candidates,
    _load_browser_state,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)
from tools.verification.verification_run_manifest import current_run_artifact  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "R1A_M300_V0"

ACTION_BUTTON_RE = re.compile(
    r"(Run one-click auto design|Apply:|Apply recommendation|Apply Design Guide|Apply selected|"
    r"Apply repair|Apply cleanup|Use this design|Update design)",
    re.IGNORECASE,
)
PASSIVE_BUTTON_RE = re.compile(r"(Re-evaluate|Review|Show|Hide|Manager|Export|Duplicate|Add)", re.IGNORECASE)
STATUS_RE = re.compile(
    r"\b(PASS|FAIL|ACTION|RECOMMEND|BLOCKED|ERROR|PROOF_PENDING|CAPACITY|NOT RUN|NEXT|INFO)\b",
    re.IGNORECASE,
)
UTIL_RE = re.compile(r"Utilisation\s*[\r\n ]+([0-9]+(?:\.[0-9]+)?|[-\u2014])", re.IGNORECASE)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _datetime_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _section(text: str, start_marker: str, end_markers: list[str] | None = None) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = len(text)
    for marker in end_markers or []:
        idx = text.find(marker, start + len(start_marker))
        if idx >= 0:
            end = min(end, idx)
    return text[start:end].strip()


def _design_guide_section(text: str) -> str:
    """Return the product Design Guide section, excluding debug/sidebar labels."""

    if not text:
        return ""
    candidates: list[int] = []
    for match in re.finditer(r"(?m)^Design Guide\s*$", text):
        start = match.start()
        nearby = text[max(0, start - 80) : min(len(text), start + 120)]
        if re.search(r"Design Guide Debug|Debug session state", nearby, re.IGNORECASE):
            continue
        candidates.append(start)
    if not candidates:
        return ""
    start = candidates[-1]
    end = len(text)
    for marker in ("Manager", "Browser state", "Design Guide Debug"):
        idx = text.find(marker, start + len("Design Guide"))
        if idx >= 0:
            end = min(end, idx)
    return text[start:end].strip()


def _slice_after(text: str, marker: str, next_markers: list[str]) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    end = len(text)
    for next_marker in next_markers:
        idx = text.find(next_marker, start + len(marker))
        if idx >= 0:
            end = min(end, idx)
    return text[start:end].strip()


def _parse_summary_cards(body_text: str) -> dict[str, dict[str, Any]]:
    card_markers = [
        ("bending_uls", "Bending"),
        ("shear_uls", "Shear"),
        ("crack_control_sls", "Crack control"),
        ("deflection_sls", "Deflection"),
    ]
    cards: dict[str, dict[str, Any]] = {}
    marker_texts = [marker for _, marker in card_markers] + ["Batch design", "Design Guide"]
    for card_id, marker in card_markers:
        other_markers = [item for item in marker_texts if item != marker]
        text = _slice_after(body_text, marker, other_markers)
        statuses = [match.group(1).upper().replace(" ", "_") for match in STATUS_RE.finditer(text)]
        util_match = UTIL_RE.search(text)
        cards[card_id] = {
            "found": bool(text),
            "text_hash": _stable_hash(text) if text else None,
            "text_sample": text[:700],
            "statuses": statuses,
            "primary_status": statuses[-1] if statuses else None,
            "utilisation": util_match.group(1) if util_match else None,
        }
    return cards


def _classify_rgb(color: str | None) -> str:
    if not color:
        return "unknown"
    nums = [int(part) for part in re.findall(r"\d+", str(color))[:3]]
    if len(nums) < 3:
        return "unknown"
    r, g, b = nums
    if r >= 160 and g <= 120 and b <= 120:
        return "red"
    if b >= 150 and r <= 130:
        return "blue"
    if g >= 130 and r <= 140 and b <= 140:
        return "green"
    if r >= 180 and g >= 130 and b <= 80:
        return "amber"
    return "neutral"


def _browser_visible_payload(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                if (el.hasAttribute && (el.hasAttribute("hidden") || el.hasAttribute("inert") || el.closest("[inert]"))) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const attrMap = (el) => {
                const attrs = {};
                if (!el || !el.attributes) return attrs;
                for (const attr of Array.from(el.attributes)) {
                  const key = String(attr.name || "");
                  const val = String(attr.value || "");
                  if (/final|publication|authority|design|guide|card|cta|button|apply|state|hash|family|selected|published|outcome|status|blocker|render/i.test(key + " " + val)) {
                    attrs[key] = val.slice(0, 400);
                  }
                }
                return attrs;
              };
              const elementPayload = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return {
                  tag: String(el.tagName || "").toLowerCase(),
                  text: clean(el.innerText || el.textContent).slice(0, 500),
                  cls: String(el.className || "").slice(0, 220),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  attrs: attrMap(el),
                  ariaLabel: el.getAttribute ? el.getAttribute("aria-label") : null,
                  disabled: Boolean(el.disabled || el.getAttribute("aria-disabled") === "true"),
                  style: {
                    color: style.color,
                    backgroundColor: style.backgroundColor,
                    borderColor: style.borderColor,
                    outlineColor: style.outlineColor
                  },
                  rect: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom)
                  }
                };
              };
              const all = Array.from(document.querySelectorAll("body *")).filter(visible);
              const bodyText = String(document.body && document.body.innerText || "");
              const buttons = Array.from(document.querySelectorAll("button")).filter(visible).map(elementPayload);
              const designGuideCards = Array.from(document.querySelectorAll("[data-testid='design-guide-card'], .fast-guidance-item"))
                .filter(visible)
                .map((el) => ({
                  ...elementPayload(el),
                  title: clean((el.querySelector && el.querySelector('.fast-guidance-title') || el).innerText || el.textContent)
                }));
              const statusPills = all
                .filter((el) => /^(PASS|FAIL|ACTION|BLOCKED|ERROR|PROOF_PENDING|CAPACITY|NOT RUN|NEXT|INFO|GOVERNING UTILISATION|GOVERNING UTILIZATION)$/i.test(clean(el.innerText || el.textContent)))
                .slice(0, 80)
                .map(elementPayload);
              const guideRelated = all
                .filter((el) => /Design Guide|Run one-click|Apply|Strengthening|required|cleanup|blocked|stale|fallback|governing utilisation|governing utilization/i.test(clean(el.innerText || el.textContent)))
                .slice(0, 80)
                .map(elementPayload);
              const hashRelated = all
                .filter((el) => Object.keys(attrMap(el)).length > 0)
                .slice(0, 400)
                .map(elementPayload);
              const selects = Array.from(document.querySelectorAll("select")).filter(visible).map((el) => ({
                value: el.value,
                selectedText: el.options && el.selectedIndex >= 0 ? clean(el.options[el.selectedIndex].text) : "",
                attrs: attrMap(el),
                rect: elementPayload(el).rect
              }));
              return {
                bodyText,
                bodyTextLength: bodyText.length,
                buttons,
                designGuideCards,
                statusPills,
                guideRelated,
                hashRelated,
                selects,
                url: window.location.href,
                title: document.title,
                viewport: {width: window.innerWidth, height: window.innerHeight}
              };
            }
            """
        )
    )


def _state_probe(page) -> dict[str, Any]:
    try:
        state = _load_browser_state(page, timeout_s=12.0)
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    def _mapping(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _find_mapping_with_key(value: Any, key: str, *, depth: int = 0) -> dict[str, Any]:
        if depth > 4:
            return {}
        if isinstance(value, dict):
            if isinstance(value.get(key), dict):
                return dict(value.get(key) or {})
            for nested in value.values():
                found = _find_mapping_with_key(nested, key, depth=depth + 1)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = _find_mapping_with_key(nested, key, depth=depth + 1)
                if found:
                    return found
        return {}

    debug_sources = {
        "top_level_publication_probe": {
            "selected_family_id": state.get("selected_family_id"),
            "final_publication_verifier_payload": state.get("final_publication_verifier_payload"),
            "final_publication_hashes": state.get("final_publication_hashes"),
        },
        "design_guide_debug": _mapping(state.get("design_guide_debug")),
        "guidance_debug": _mapping(state.get("guidance_debug")),
        "design_guide_probe": _mapping(state.get("design_guide_probe")),
        "guidance_compute_probe": _mapping(state.get("guidance_compute_probe")),
        "browser_debug_probe": _mapping(state.get("browser_debug_probe")),
        "design_guide_primary_payload_binding_audit": _mapping(
            state.get("design_guide_primary_payload_binding_audit")
        ),
        "pending_recommendation_meta": _mapping(state.get("pending_recommendation_meta")),
        "post_cleanup_acceptance_probe": _mapping(state.get("post_cleanup_acceptance_probe")),
    }
    debug = {}
    for source in debug_sources.values():
        if source:
            debug = dict(source)
            if source.get("final_publication_verifier_payload"):
                break
    final_payload = _mapping(state.get("final_publication_verifier_payload"))
    for source in debug_sources.values():
        if final_payload:
            break
        final_payload = _find_mapping_with_key(source, "final_publication_verifier_payload")
        if final_payload:
            break
    primary_contract = dict(state.get("design_guide_primary_button_contract") or {})
    shared = dict(state.get("browser_shared_probe") or {})
    summary = dict(state.get("summary_state_probe") or {})
    summary_overview = dict(state.get("summary_overview_probe") or {})
    top_level_hashes = _mapping(state.get("final_publication_hashes"))
    candidate_diagnostics: list[dict[str, Any]] = []
    for index, raw in enumerate(
        _browser_state_raw_candidates(page, timeout_ms=1_500)
    ):
        try:
            parsed_candidate = json.loads(raw)
        except Exception:
            continue
        if not isinstance(parsed_candidate, dict):
            continue
        candidate_timing = _mapping(
            parsed_candidate.get("render_timing_probe")
        )
        candidate_shared = _mapping(
            parsed_candidate.get("browser_shared_probe")
        )
        candidate_debug = _mapping(
            parsed_candidate.get("browser_debug_probe")
        )
        candidate_diagnostics.append(
            {
                "index": index,
                "raw_length": len(raw),
                "probe_phase": parsed_candidate.get("browser_probe_phase"),
                "pre_page_render_lightweight": bool(
                    parsed_candidate.get("pre_page_render_lightweight")
                ),
                "rerun_seq": candidate_timing.get("rerun_seq"),
                "event_count": candidate_timing.get("event_count"),
                "results_version": parsed_candidate.get("results_version"),
                "shared_shear": {
                    "lig_d": candidate_shared.get("lig_d"),
                    "lig_legs": candidate_shared.get("lig_legs"),
                    "s_lig": candidate_shared.get("s_lig"),
                },
                "typed_inputs_apply_probe": _mapping(
                    candidate_debug.get("typed_inputs_apply_probe")
                ),
                "typed_post_apply_rehydrate_probe": _mapping(
                    candidate_debug.get("typed_post_apply_rehydrate_probe")
                ),
            }
        )
    return {
        "available": True,
        "state_hash": _stable_hash(state),
        "top_level_keys": sorted(str(key) for key in state.keys())[:120],
        "browser_recipe": state.get("browser_recipe"),
        "browser_recipe_kind": state.get("browser_recipe_kind"),
        "browser_recipe_error": state.get("browser_recipe_error"),
        "browser_recipe_applied_state": state.get("browser_recipe_applied_state"),
        "final_publication_verifier_payload": final_payload,
        "primary_button_contract": primary_contract,
        "button_contract": dict(state.get("button_contract") or primary_contract or {}),
        "design_guide_primary_button_contract": dict(
            state.get("design_guide_primary_button_contract") or primary_contract or {}
        ),
        "design_guide_primary_button_contract_enabled": state.get(
            "design_guide_primary_button_contract_enabled"
        ),
        "browser_shared_probe": shared,
        "summary_state_probe": summary,
        "summary_overview_probe": summary_overview,
        "_inputs_engineering_input_transaction_probe": dict(
            state.get("_inputs_engineering_input_transaction_probe") or {}
        ),
        "_authoritative_design_result_runtime_probe": dict(
            state.get("_authoritative_design_result_runtime_probe") or {}
        ),
        "_typed_inputs_apply_probe": dict(
            state.get("_typed_inputs_apply_probe") or {}
        ),
        "_finalize_auto_design_publish_latest": dict(
            state.get("_finalize_auto_design_publish_latest") or {}
        ),
        "_inputs_apply_refresh_cycle_latest": dict(
            state.get("_inputs_apply_refresh_cycle_latest") or {}
        ),
        "_shared_write_audit": [
            dict(row)
            for row in list(state.get("_shared_write_audit") or [])[-20:]
            if isinstance(row, dict)
        ],
        "browser_debug_sources": debug_sources,
        "browser_state_candidate_diagnostics": candidate_diagnostics,
        "final_publication_hashes": {
            "publication_hash": final_payload.get("publication_hash")
            or top_level_hashes.get("publication_hash")
            or debug.get("publication_hash"),
            "authority_hash": final_payload.get("final_publication_authority_hash")
            or top_level_hashes.get("authority_hash")
            or debug.get("final_publication_authority_hash"),
            "cta_hash": final_payload.get("final_publication_cta_hash")
            or final_payload.get("cta_authority_hash")
            or final_payload.get("cta_hash")
            or top_level_hashes.get("cta_hash"),
            "display_hash": final_payload.get("final_publication_display_hash")
            or final_payload.get("display_authority_hash")
            or final_payload.get("display_hash")
            or top_level_hashes.get("display_hash"),
        },
    }


def _publication_card_attrs_from_visible_payloads(*payloads: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for element in (
            list(payload.get("designGuideCards") or [])
            + list(payload.get("hashRelated") or [])
            + list(payload.get("guideRelated") or [])
        ):
            attrs = dict((element or {}).get("attrs") or {})
            if attrs:
                candidates.append(attrs)
    for attrs in candidates:
        if (
            attrs.get("data-publication-hash")
            or attrs.get("data-final-publication-authority-hash")
            or attrs.get("data-final-publication-cta-hash")
            or attrs.get("data-final-publication-display-hash")
            or attrs.get("data-selected-family-id")
        ):
            return {
                "publication_hash": attrs.get("data-publication-hash") or "",
                "authority_hash": attrs.get("data-final-publication-authority-hash") or "",
                "cta_hash": attrs.get("data-final-publication-cta-hash") or "",
                "display_hash": attrs.get("data-final-publication-display-hash") or "",
                "outcome_state": attrs.get("data-outcome-state") or "",
                "status": attrs.get("data-status") or "",
                "title": attrs.get("data-title") or "",
                "blocker_reason": attrs.get("data-blocker-reason") or "",
                "selected_family_id": attrs.get("data-selected-family-id") or "",
                "selected_family": attrs.get("data-selected-family") or "",
                "published_family_id": attrs.get("data-published-family-id") or "",
                "cta_family_id": attrs.get("data-cta-family-id") or "",
                "card_family_id": attrs.get("data-card-family-id") or "",
                "source": "design_guide_card_data_attributes",
            }
    return {}


def _design_guide_card_text_from_visible_payloads(*payloads: dict[str, Any]) -> str:
    texts: list[str] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for element in payload.get("designGuideCards") or []:
            text = str((element or {}).get("text") or "").strip()
            if text:
                texts.append(text)
    if not texts:
        return ""
    return max(texts, key=len)


def _normalise_button(button: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": str(button.get("text") or "").strip(),
        "disabled": bool(button.get("disabled")),
        "style_family": {
            "background": _classify_rgb((button.get("style") or {}).get("backgroundColor")),
            "color": _classify_rgb((button.get("style") or {}).get("color")),
            "border": _classify_rgb((button.get("style") or {}).get("borderColor")),
        },
        "rect": button.get("rect"),
        "attrs": button.get("attrs") or {},
    }


def _visual_consistency_checks(
    *,
    body_text: str,
    summary_cards: dict[str, dict[str, Any]],
    design_guide_text: str,
    design_guide_cards: list[dict[str, Any]],
    buttons: list[dict[str, Any]],
    pills: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    hard_failures: list[str] = []
    warnings: list[str] = []
    observations: list[str] = []

    bending_found = bool(summary_cards.get("bending_uls", {}).get("found"))
    shear_found = bool(summary_cards.get("shear_uls", {}).get("found"))
    if not bending_found:
        hard_failures.append("bending_summary_card_not_found")
    if not shear_found:
        hard_failures.append("shear_summary_card_not_found")
    if not design_guide_text:
        hard_failures.append("design_guide_section_not_found")

    visible_design_guide_cards = [
        card for card in design_guide_cards if isinstance(card, dict)
    ]
    visible_design_guide_card_count = len(visible_design_guide_cards)
    visible_design_guide_card_hashes = [
        str((card.get("attrs") or {}).get("data-publication-hash") or "").strip()
        for card in visible_design_guide_cards
    ]
    duplicate_visible_publication_hashes = sorted(
        {
            card_hash
            for card_hash in visible_design_guide_card_hashes
            if card_hash and visible_design_guide_card_hashes.count(card_hash) > 1
        }
    )
    if visible_design_guide_card_count > 1:
        hard_failures.append("duplicate_visible_design_guide_cards")
    if duplicate_visible_publication_hashes:
        hard_failures.append("duplicate_visible_design_guide_publication_hash")
    visible_design_guide_titles = [
        re.sub(r"\s+", " ", str(card.get("title") or "")).strip()
        for card in visible_design_guide_cards
        if str(card.get("title") or "").strip()
    ]
    duplicate_visible_design_guide_titles = sorted(
        {
            title
            for title in visible_design_guide_titles
            if visible_design_guide_titles.count(title) > 1
        }
    )
    if duplicate_visible_design_guide_titles:
        hard_failures.append("duplicate_visible_design_guide_card_title")

    normal_buttons = [_normalise_button(button) for button in buttons]
    action_buttons = [button for button in normal_buttons if ACTION_BUTTON_RE.search(button["text"])]
    passive_buttons = [button for button in normal_buttons if PASSIVE_BUTTON_RE.search(button["text"])]
    enabled_action_buttons = [button for button in action_buttons if not button["disabled"]]

    guide_statuses = [match.group(1).upper().replace(" ", "_") for match in STATUS_RE.finditer(design_guide_text)]
    guide_has_action = bool(
        {"ACTION", "RECOMMEND"} & set(guide_statuses)
        or re.search(r"\bApply\b|Run one-click auto design", design_guide_text, re.I)
    )
    guide_has_blocked = bool(
        {"BLOCKED", "ERROR", "PROOF_PENDING"} & set(guide_statuses)
        or re.search(
            r"Design Guide blocker proof incomplete|Why repair is blocked|Repair blocked|Publication blocked|Family mismatch blocked",
            design_guide_text,
            re.I,
        )
    )
    guide_has_pass = bool(
        "PASS" in set(guide_statuses)
        or re.search(r"Design is efficient|All checks passed|Design accepted", design_guide_text, re.I)
    )

    if guide_has_action and not enabled_action_buttons:
        hard_failures.append("design_guide_action_state_without_visible_enabled_apply_button")
    if guide_has_pass and enabled_action_buttons:
        warnings.append("pass_design_guide_has_enabled_apply_style_action_button")
    if guide_has_blocked and enabled_action_buttons:
        warnings.append("blocked_design_guide_has_enabled_action_button")

    blue_action_pills = []
    red_tone_evidence = []
    design_guide_pill_text = str(design_guide_text or "")
    for pill in pills:
        text = str(pill.get("text") or "").strip()
        if text and text not in design_guide_pill_text:
            continue
        bg_family = _classify_rgb((pill.get("style") or {}).get("backgroundColor"))
        border_family = _classify_rgb((pill.get("style") or {}).get("borderColor"))
        color_family = _classify_rgb((pill.get("style") or {}).get("color"))
        if re.search(r"ACTION|GOVERNING UTILISATION|GOVERNING UTILIZATION", text, re.I) and (
            bg_family == "blue" or border_family == "blue" or color_family == "blue"
        ):
            blue_action_pills.append(
                {
                    "text": text,
                    "background_family": bg_family,
                    "border_family": border_family,
                    "color_family": color_family,
                    "rect": pill.get("rect"),
                }
            )
        if bg_family == "red" or border_family == "red" or color_family == "red":
            red_tone_evidence.append(
                {
                    "text": text,
                    "background_family": bg_family,
                    "border_family": border_family,
                    "color_family": color_family,
                    "rect": pill.get("rect"),
                }
            )
    if blue_action_pills and (guide_has_blocked or red_tone_evidence):
        warnings.append("red_or_blocked_design_guide_with_blue_action_or_governing_utilisation_pill")

    fallback_markers = [
        marker
        for marker in ("fallback", "stale", "shell", "PROOF_PENDING", "missing publication")
        if re.search(marker, design_guide_text, re.I)
    ]
    if fallback_markers:
        warnings.append("browser_visible_fallback_or_stale_publication_marker")

    state_hashes = dict((state.get("final_publication_hashes") or {})) if state.get("available") else {}
    browser_exposed_publication_hash = bool(
        state_hashes.get("publication_hash") or state_hashes.get("authority_hash")
    )
    if not browser_exposed_publication_hash:
        warnings.append("browser_state_final_publication_hash_not_available")
    else:
        observations.append("browser_state_exposes_final_publication_hash")

    shared = dict(state.get("browser_shared_probe") or {}) if state.get("available") else {}
    summary_probe = dict(state.get("summary_state_probe") or {}) if state.get("available") else {}
    fingerprint = {
        "visible_summary_hash": _stable_hash(summary_cards),
        "visible_design_guide_hash": _stable_hash(design_guide_text),
        "browser_shared_probe_hash": _stable_hash(shared) if shared else None,
        "summary_state_probe_hash": _stable_hash(summary_probe) if summary_probe else None,
        "final_publication_hashes": state_hashes,
    }
    same_state_probe_available = bool(shared and summary_probe)
    if same_state_probe_available:
        observations.append("summary_and_design_guide_browser_state_probes_available")
    else:
        warnings.append("same_beam_state_fingerprint_only_partially_browser_exposed")

    return {
        "hard_failures": hard_failures,
        "warnings": warnings,
        "observations": observations,
        "summary_cards_present": {"bending": bending_found, "shear": shear_found},
        "design_guide_statuses": guide_statuses,
        "visible_design_guide_cards": {
            "count": visible_design_guide_card_count,
            "publication_hashes": visible_design_guide_card_hashes,
            "duplicate_publication_hashes": duplicate_visible_publication_hashes,
            "titles": visible_design_guide_titles,
            "duplicate_titles": duplicate_visible_design_guide_titles,
        },
        "cta": {
            "all_buttons": normal_buttons,
            "action_buttons": action_buttons,
            "passive_buttons": passive_buttons,
            "enabled_action_buttons": enabled_action_buttons,
            "missing_or_hidden_apply_button": bool(guide_has_action and not enabled_action_buttons),
        },
        "tone": {
            "blue_action_or_governing_utilisation_pills": blue_action_pills,
            "red_tone_evidence": red_tone_evidence,
            "red_card_blue_action_pill_risk": bool(
                blue_action_pills and (guide_has_blocked or red_tone_evidence)
            ),
        },
        "stale_fallback_publication_shell": {
            "visible_markers": fallback_markers,
            "risk": bool(fallback_markers),
        },
        "same_beam_state_fingerprint": {
            "probe_available": same_state_probe_available,
            "browser_exposed_publication_hash": browser_exposed_publication_hash,
            "fingerprint": fingerprint,
        },
        "result_hash": _stable_hash(
            {
                "summary_cards": summary_cards,
                "design_guide_text": design_guide_text,
                "buttons": normal_buttons,
                "state_hashes": state_hashes,
                "failures": hard_failures,
                "warnings": warnings,
            }
        ),
    }


def _capture_visual_snapshot(page, *, scenario_id: str, screenshot_path: Path | None = None) -> dict[str, Any]:
    page.wait_for_timeout(900)
    try:
        page.evaluate("() => window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_timeout(500)
    except Exception:
        pass
    top_visible = _browser_visible_payload(page)
    top_body_text = str(top_visible.get("bodyText") or "")
    scroll_probe = _scroll_until_design_guide_probe(page, timeout_s=20.0)
    guide_visible = _browser_visible_payload(page)
    guide_body_text = str(guide_visible.get("bodyText") or "")
    body_text = "\n".join(part for part in (top_body_text, guide_body_text) if part)
    summary_cards = _parse_summary_cards(body_text)
    design_guide_text = _design_guide_section(guide_body_text) or _design_guide_section(top_body_text)
    if not design_guide_text:
        design_guide_text = _design_guide_card_text_from_visible_payloads(guide_visible, top_visible)
    state = _state_probe(page)
    card_attrs = _publication_card_attrs_from_visible_payloads(top_visible, guide_visible)
    if card_attrs:
        state["card_data_attributes"] = dict(card_attrs)
        state_hashes = dict(state.get("final_publication_hashes") or {})
        for key in ("publication_hash", "authority_hash", "cta_hash", "display_hash"):
            if not state_hashes.get(key) and card_attrs.get(key):
                state_hashes[key] = card_attrs.get(key)
        state["final_publication_hashes"] = state_hashes
    combined_buttons = list(top_visible.get("buttons") or []) + list(guide_visible.get("buttons") or [])
    combined_pills = list(top_visible.get("statusPills") or []) + list(guide_visible.get("statusPills") or [])
    checks = _visual_consistency_checks(
        body_text=body_text,
        summary_cards=summary_cards,
        design_guide_text=design_guide_text,
        design_guide_cards=list(guide_visible.get("designGuideCards") or []),
        buttons=combined_buttons,
        pills=combined_pills,
        state=state,
    )
    if screenshot_path is not None:
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            screenshot_path = None
    return {
        "scenario_id": scenario_id,
        "url": guide_visible.get("url") or top_visible.get("url"),
        "title": guide_visible.get("title") or top_visible.get("title"),
        "viewport": guide_visible.get("viewport") or top_visible.get("viewport"),
        "body_text_hash": _stable_hash(body_text),
        "top_body_text_hash": _stable_hash(top_body_text),
        "guide_body_text_hash": _stable_hash(guide_body_text),
        "scroll_probe": scroll_probe,
        "summary_cards": summary_cards,
        "design_guide": {
            "found": bool(design_guide_text),
            "text_hash": _stable_hash(design_guide_text) if design_guide_text else None,
            "text_sample": design_guide_text[:1200],
            "guide_related_elements": list(guide_visible.get("guideRelated") or [])[:30],
            "card_elements": list(guide_visible.get("designGuideCards") or [])[:10],
            "status_pills": combined_pills[:40],
            "hash_related_elements": (
                list(top_visible.get("hashRelated") or []) + list(guide_visible.get("hashRelated") or [])
            )[:40],
        },
        "buttons": combined_buttons[:80],
        "selects": (list(top_visible.get("selects") or []) + list(guide_visible.get("selects") or []))[:20],
        "browser_state": state,
        "checks": checks,
        "screenshot_path": str(screenshot_path) if screenshot_path else None,
        "scenario_hash": _stable_hash(
            {
                "summary_cards": summary_cards,
                "design_guide_text": design_guide_text,
                "checks": checks,
                "state": state,
            }
        ),
    }


def _scroll_until_design_guide_probe(page, *, timeout_s: float) -> dict[str, Any]:
    """Scroll the live page enough to materialize lower Inputs sections.

    Streamlit can keep lower blocks out of the immediate rendered viewport while
    the top of the page is stable. This helper does not click or mutate app
    state; it only scrolls and waits so the browser snapshot can inspect the
    Design Guide region when the app has rendered it.
    """

    deadline = time.time() + max(1.0, float(timeout_s))
    snapshots: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            probe = dict(
                page.evaluate(
                    r"""
                    () => {
                      const text = String(document.body && document.body.innerText || "");
                      const lines = text.split(/\r?\n/).map((line) => line.trim());
                      const hasProductDesignGuide = lines.some((line, index) => {
                        if (line !== "Design Guide") return false;
                        const next = lines[index + 1] || "";
                        const prev = lines[index - 1] || "";
                        return next !== "Debug" && !/Debug session state/i.test(next) && !/Debug$/i.test(prev);
                      });
                      const card = document.querySelector("[data-testid='design-guide-card'], .fast-guidance-item");
                      const cardRect = card && card.getBoundingClientRect ? card.getBoundingClientRect() : null;
                      const cardInViewport = Boolean(
                        cardRect && cardRect.width > 2 && cardRect.height > 2
                        && cardRect.bottom > 0 && cardRect.top < (window.innerHeight || 0)
                      );
                      return {
                        hasInputs: /Inputs/i.test(text),
                        hasBatchDesign: /Batch design/i.test(text),
                        hasDesignGuide: hasProductDesignGuide && Boolean(card),
                        hasDesignGuideCard: Boolean(card),
                        designGuideCardInViewport: cardInViewport,
                        textLength: text.length,
                        scrollY: Math.round(window.scrollY || 0),
                        scrollHeight: Math.round(document.documentElement.scrollHeight || document.body.scrollHeight || 0),
                        viewportHeight: Math.round(window.innerHeight || 0)
                      };
                    }
                    """
                )
            )
            snapshots.append(probe)
            if probe.get("hasDesignGuide") and probe.get("designGuideCardInViewport"):
                return {"found": True, "snapshots": snapshots[-8:]}
            page.evaluate(
                r"""
                () => {
                  const card = document.querySelector("[data-testid='design-guide-card'], .fast-guidance-item");
                  if (card && card.scrollIntoView) {
                    const rect = card.getBoundingClientRect();
                    const viewportHeight = window.innerHeight || 0;
                    if (rect.bottom <= 0 || rect.top >= viewportHeight) {
                      card.scrollIntoView({block: "center", behavior: "instant"});
                      return;
                    }
                  }
                  const maxScroll = Math.max(
                    document.documentElement.scrollHeight || 0,
                    document.body.scrollHeight || 0
                  );
                  const current = window.scrollY || 0;
                  const next = Math.min(maxScroll, current + Math.max(420, Math.round(window.innerHeight * 0.7)));
                  window.scrollTo({top: next, behavior: "instant"});
                }
                """
            )
            page.wait_for_timeout(450)
        except Exception as exc:
            snapshots.append({"error": f"{type(exc).__name__}: {exc}"})
            page.wait_for_timeout(450)
    return {"found": False, "snapshots": snapshots[-12:]}


def _wait_for_live_inputs_content(page, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(5.0, float(timeout_s))
    last_probe: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            body_text = str(page.locator("body").inner_text(timeout=2_000) or "")
        except Exception as exc:
            last_probe = {"ready": False, "error": f"{type(exc).__name__}: {exc}"}
            time.sleep(0.5)
            continue
        guide_text = _design_guide_section(body_text)
        has_summary = bool(
            re.search(r"Bending\s+[\u2014-]\s+ULS", body_text, re.I)
            and re.search(r"Shear\s+[\u2014-]\s+ULS", body_text, re.I)
        )
        has_final_guide = bool(
            guide_text
            and re.search(r"\b(PASS|ACTION|RECOMMEND|BLOCKED|ERROR|PROOF_PENDING|NEXT|INFO)\b", guide_text, re.I)
            and not re.search(r"Checking design guidance|Reviewing strength, detailing, serviceability", guide_text, re.I)
        )
        last_probe = {
            "ready": bool(has_summary and has_final_guide),
            "has_summary": has_summary,
            "has_final_guide": has_final_guide,
            "body_text_length": len(body_text),
            "guide_text_sample": guide_text[:500],
        }
        if last_probe["ready"]:
            return last_probe
        time.sleep(0.75)
    return last_probe


def _latest_artifact(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        path, payload = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "status": None, "current_run": True}
        return {"found": True, "path": str(path), "status": payload.get("status"), "path_obj": path.name, "current_run": True}
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}
    return {"found": True, "path": str(path), "status": payload.get("status"), "path_obj": path.name}


def _markdown(payload: dict[str, Any]) -> str:
    scenario = payload["scenarios"][0] if payload.get("scenarios") else {}
    checks = scenario.get("checks") or {}
    lines = [
        "# Design Guide Browser/Live Visual Consistency Snapshot",
        "",
        f"- Result: `{payload['status']}`",
        f"- Created: `{payload['created_at']}`",
        f"- Browser mode: `{payload['browser_live_mode']}`",
        f"- URL: `{payload['base_url']}`",
        f"- Recipe: `{payload['recipe']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        f"- Summary cards present: `{checks.get('summary_cards_present')}`",
        f"- Design Guide statuses: `{checks.get('design_guide_statuses')}`",
        f"- Visible Design Guide card count: `{((checks.get('visible_design_guide_cards') or {}).get('count'))}`",
        f"- Missing or hidden Apply button: `{((checks.get('cta') or {}).get('missing_or_hidden_apply_button'))}`",
        f"- Red card / blue ACTION pill risk: `{((checks.get('tone') or {}).get('red_card_blue_action_pill_risk'))}`",
        f"- Fallback/stale shell risk: `{((checks.get('stale_fallback_publication_shell') or {}).get('risk'))}`",
        f"- Browser publication hash exposed: `{((checks.get('same_beam_state_fingerprint') or {}).get('browser_exposed_publication_hash'))}`",
        "",
        "## Hard Failures",
        "",
    ]
    failures = list(checks.get("hard_failures") or [])
    lines.extend([f"- `{item}`" for item in failures] or ["- None"])
    lines.extend(["", "## Warnings", ""])
    warnings = list(checks.get("warnings") or [])
    lines.extend([f"- `{item}`" for item in warnings] or ["- None"])
    lines.extend(["", "## Visible Summary Cards", ""])
    for card_id, card in (scenario.get("summary_cards") or {}).items():
        lines.append(
            f"- `{card_id}`: found `{card.get('found')}`, status `{card.get('primary_status')}`, "
            f"utilisation `{card.get('utilisation')}`, hash `{card.get('text_hash')}`"
        )
    lines.extend(["", "## CTA Buttons", ""])
    for button in ((checks.get("cta") or {}).get("all_buttons") or [])[:12]:
        lines.append(
            f"- `{button.get('text')}` disabled `{button.get('disabled')}` style `{button.get('style_family')}`"
        )
    lines.extend(["", "## Supporting Locks", ""])
    for name, artifact in (payload.get("supporting_artifacts") or {}).items():
        lines.append(f"- `{name}`: found `{artifact.get('found')}`, status `{artifact.get('status')}`")
    lines.extend(["", "## Recommendation", ""])
    lines.append(payload.get("recommendation") or "No recommendation recorded.")
    return "\n".join(lines) + "\n"


def _recommendation(status: str, scenario: dict[str, Any]) -> str:
    checks = scenario.get("checks") or {}
    failures = list(checks.get("hard_failures") or [])
    warnings = list(checks.get("warnings") or [])
    if failures:
        return (
            "Do not move more authority yet. First inspect the browser-visible mismatch recorded in this "
            "snapshot, starting with missing summary/Design Guide sections or the missing Apply-button case."
        )
    if "red_or_blocked_design_guide_with_blue_action_or_governing_utilisation_pill" in warnings:
        return (
            "Next slice should be a focused tone/status parity proof between FinalDesignGuidePublication.display "
            "and the rendered pill/card colour system."
        )
    if "browser_state_final_publication_hash_not_available" in warnings:
        return (
            "Next slice should expose or verify the same final publication hash in the browser/debug payload "
            "used by live visual consistency checks."
        )
    return (
        "No hard visual consistency mismatch was detected in this browser/live snapshot. Continue with focused "
        "scenario expansion if the issue only appears in a different beam state."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8528)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_VISUAL_SNAPSHOT_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _datetime_stamp()
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    process: subprocess.Popen | None = None
    browser_live_mode = "started_streamlit"
    errors: list[str] = []
    scenarios: list[dict[str, Any]] = []

    try:
        if args.base_url:
            browser_live_mode = "attached_to_existing_streamlit"
            _wait_for_http(base_url)
        else:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1100})
            page = context.new_page()
            page.set_default_timeout(30_000)
            page.goto(
                _query(
                    base_url,
                    {
                        "page": "inputs",
                        "browser_recipe": args.recipe,
                        "browser_test_mode": "1",
                        "batch_design_open": "0",
                    },
                ),
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            try:
                page.get_by_text("Inputs", exact=True).first.wait_for(state="visible", timeout=min(30_000, int(args.timeout_s * 1000)))
            except PlaywrightTimeoutError:
                pass
            ready_probe = _wait_for_live_inputs_content(page, timeout_s=args.timeout_s)
            screenshot_path = ARTIFACT_DIR / f"design_guide_browser_live_visual_consistency_{stamp}.png"
            scenarios.append(_capture_visual_snapshot(page, scenario_id="initial_live_inputs", screenshot_path=screenshot_path))
            scenarios[-1]["ready_probe"] = ready_probe
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    supporting_artifacts = {
        "design_guide_independence_lock": _latest_artifact("design_guide_independence_lock"),
        "design_guide_render_bridge_lock": _latest_artifact("design_guide_render_bridge_lock"),
        "design_guide_compute_resolver_publication_bridge_lock": _latest_artifact(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
    }
    first = scenarios[0] if scenarios else {}
    hard_failures = list(((first.get("checks") or {}).get("hard_failures") or []))
    status = "PASS" if scenarios and not hard_failures and not errors else "FAIL"
    payload = {
        "schema": "design_guide_browser_live_visual_consistency_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "browser_live_mode": browser_live_mode,
        "base_url": base_url,
        "recipe": args.recipe,
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_routing_changed": False,
        "apply_routing_changed": False,
        "visible_wording_changed": False,
        "scenarios": scenarios,
        "supporting_artifacts": supporting_artifacts,
        "errors": errors,
        "recommendation": _recommendation(status, first) if first else "Snapshot could not capture a browser scenario.",
        "snapshot_hash": _stable_hash(
            {
                "status": status,
                "scenario_hashes": [row.get("scenario_hash") for row in scenarios],
                "errors": errors,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_browser_live_visual_consistency_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_browser_live_visual_consistency_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_browser_live_visual_consistency_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if scenarios:
        checks = scenarios[0].get("checks") or {}
        print("hard_failures=" + json.dumps(checks.get("hard_failures") or []))
        print("warnings=" + json.dumps(checks.get("warnings") or []))
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
