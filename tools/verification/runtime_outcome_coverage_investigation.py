"""Verifier-only runtime outcome coverage and sensitivity investigation.

This script opens the real Inputs page in a browser, captures the rendered
Design Guide card contract attributes, compares them to an investigation
registry, and writes audit artifacts. It intentionally does not modify product
code or click CTA/apply controls by default.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.families.registry import (  # noqa: E402
    GOVERNING_FAMILY_ALIASES,
    GOVERNING_FAMILY_REGISTRY,
    normalise_governing_family,
)


AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTRACT_DIR = ROOT / "artifacts" / "contracts"

OUTCOMES = ("PASS", "ACTION", "BLOCKED", "ERROR", "PROOF_PENDING")
ACTION_OUTCOMES = {"ACTION"}
NON_ACTION_OUTCOMES = {"PASS", "BLOCKED", "ERROR", "PROOF_PENDING", ""}
GENERIC_REASON_MARKERS = (
    "repair blocked:",
    "no one-click repair is executable because",
    "cannot generate a safe one-click repair",
    "run one-click optimization",
    "run one-click optimisation",
)


def _stamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat().replace(":", "-")


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _with_query(url: str, params: dict[str, Any]) -> str:
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            continue
        query[key] = str(value)
    return urlunsplit((split.scheme, split.netloc, split.path or "/", urlencode(query), split.fragment))


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "enabled", "action", "actionable"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _capture_page_payload(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                if (el.hasAttribute && (el.hasAttribute("hidden") || el.closest("[inert]"))) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const attrs = (el) => {
                const out = {};
                if (!el || !el.attributes) return out;
                for (const attr of Array.from(el.attributes)) {
                  const key = String(attr.name || "");
                  if (key.startsWith("data-")) out[key] = String(attr.value || "");
                }
                return out;
              };
              const elem = (el) => ({
                text: clean(el.innerText || el.textContent).slice(0, 4000),
                attrs: attrs(el),
                disabled: Boolean(el.disabled || el.getAttribute("aria-disabled") === "true"),
                testid: el.getAttribute ? el.getAttribute("data-testid") : "",
                cls: String(el.className || "").slice(0, 240)
              });
              const cardSelectors = [
                "[data-testid='design-guide-card']",
                "[data-outcome-state]",
                "[data-publication-hash]",
                ".fast-guidance-item"
              ];
              const cards = Array.from(document.querySelectorAll(cardSelectors.join(",")))
                .filter(visible)
                .map(elem);
              const buttons = Array.from(document.querySelectorAll("button"))
                .filter(visible)
                .map(elem);
              const bodyText = String(document.body && document.body.innerText || "");
              const summaries = {};
              for (const label of ["Bending", "Shear", "Crack control", "Deflection"]) {
                const match = bodyText.match(new RegExp(label + "[\\s\\S]{0,700}", "i"));
                summaries[label] = match ? clean(match[0]) : "";
              }
              return {
                url: window.location.href,
                title: document.title,
                body_text: clean(bodyText).slice(0, 12000),
                body_text_hash: clean(bodyText) ? null : "",
                card_count: cards.length,
                cards,
                buttons,
                summary_sections: summaries,
                viewport: {width: window.innerWidth, height: window.innerHeight}
              };
            }
            """
        )
    )


def _visible_status(text: str) -> str:
    upper = str(text or "").upper()
    for status in OUTCOMES:
        if status in upper:
            return status
    if "APPLY" in upper or "RECOMMEND" in upper or "REPAIR REQUIRED" in upper:
        return "ACTION"
    if "BLOCK" in upper:
        return "BLOCKED"
    if "ALL CHECKS PASS" in upper or "DESIGN ACCEPTED" in upper:
        return "PASS"
    return ""


def _read_browser_state_from_dom(page) -> dict[str, Any]:
    try:
        raw_values = page.evaluate(
            r"""
            () => {
              const values = [];
              const selectors = [
                "textarea[aria-label='Browser state']",
                "[data-testid='stTextArea'] textarea",
                "[aria-label='Browser state']",
                "[data-testid='stCodeBlock']"
              ];
              for (const selector of selectors) {
                for (const el of Array.from(document.querySelectorAll(selector))) {
                  const raw = "value" in el ? el.value : (el.textContent || "");
                  if (raw && raw.trim().startsWith("{")) values.push(raw.trim());
                }
              }
              values.sort((a, b) => b.length - a.length);
              return values;
            }
            """
        )
    except Exception:
        return {}
    for raw in raw_values or []:
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _tuple_from_capture(*, scenario_id: str, recipe_id: str, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    cards = [card for card in payload.get("cards") or [] if isinstance(card, dict)]
    card = cards[0] if cards else {}
    attrs = dict(card.get("attrs") or {})
    text = _clean(card.get("text") or payload.get("body_text") or "")
    buttons = [button for button in payload.get("buttons") or [] if isinstance(button, dict)]
    button_texts = [_clean(button.get("text")) for button in buttons]
    visible_apply_buttons = [
        button
        for button in buttons
        if re.search(r"\b(apply|run one-click|one-click)\b", _clean(button.get("text")), re.I)
    ]
    enabled_apply_buttons = [button for button in visible_apply_buttons if not bool(button.get("disabled"))]

    selected_family = normalise_governing_family(
        attrs.get("data-selected-family-id")
        or attrs.get("data-selected-family")
        or attrs.get("data-published-family-id")
        or attrs.get("data-cta-family-id")
        or ""
    )
    raw_outcome = str(attrs.get("data-outcome-state") or attrs.get("data-status") or _visible_status(text)).upper()
    visible_publication_state = str(attrs.get("data-visible-publication-state") or "").upper()
    outcome = (
        visible_publication_state
        if raw_outcome not in OUTCOMES and visible_publication_state in OUTCOMES
        else raw_outcome
    )
    cta_state = (
        "ENABLED"
        if _truthy(attrs.get("data-render-cta-enabled")) or enabled_apply_buttons
        else "DISABLED"
        if visible_apply_buttons
        else "ABSENT"
    )
    apply_state = (
        "ENABLED"
        if enabled_apply_buttons
        else "DISABLED"
        if visible_apply_buttons
        else "ABSENT"
    )
    candidate_id = attrs.get("data-render-cta-payload-id") or "rendered_primary_candidate"
    publication_hash = attrs.get("data-publication-hash") or ""
    authority_hash = attrs.get("data-authority-hash") or attrs.get("data-final-publication-authority-hash") or ""
    debug_payload = state.get("final_publication_verifier_payload") if isinstance(state, dict) else {}
    if not isinstance(debug_payload, dict):
        debug_payload = {}
    visible_owner = "family_or_final_publication"
    lowered = text.lower()
    if any(marker in lowered for marker in GENERIC_REASON_MARKERS):
        visible_owner = "page_or_shared_generic_wording_detected"
    if selected_family and (
        attrs.get("data-family-route-owner")
        or "family-owned blocker proof" in lowered
        or attrs.get("data-visible-exact-blocker") == "true"
    ):
        visible_owner = "family_or_final_publication"
    if not selected_family:
        visible_owner = "not_proven"

    surface = {
        "attrs": attrs,
        "text_hash": _stable_hash(text),
        "summary_sections": payload.get("summary_sections") or {},
        "buttons": [{"text": _clean(button.get("text")), "disabled": bool(button.get("disabled"))} for button in buttons],
    }
    tuple_payload = {
        "scenario_id": scenario_id,
        "recipe_id": recipe_id,
        "url": payload.get("url") or "",
        "engineering_hash": _stable_hash(surface),
        "family_code": selected_family,
        "outcome_code": outcome,
        "sub_outcome_code": attrs.get("data-blocker-reason") or attrs.get("data-render-blocking-reason") or "",
        "template_code": attrs.get("data-template-code") or attrs.get("data-title") or "",
        "candidate_id": candidate_id,
        "evidence_candidate_id": debug_payload.get("candidate_id") or debug_payload.get("source_candidate_id") or "",
        "blocker_or_proof_id": attrs.get("data-blocker-reason") or attrs.get("data-selection-reason") or "",
        "publication_authority_hash": authority_hash or publication_hash,
        "publication_builder": "FinalDesignGuidePublication" if publication_hash or authority_hash else "NOT_PROVEN",
        "display_builder": "FinalDesignGuideDisplay" if attrs.get("data-final-publication-display-hash") else "NOT_PROVEN",
        "renderer_path": "inputs_page_modules.design_guide.current_coordinators._design_guide_card_contract_attrs"
        if attrs
        else "NOT_PROVEN",
        "visible_explanation_owner": visible_owner,
        "cta_state": cta_state,
        "cta_candidate_id": attrs.get("data-render-cta-payload-id") or "",
        "apply_state": apply_state,
        "apply_payload_candidate_id": attrs.get("data-render-cta-payload-id") if apply_state != "ABSENT" else "",
        "compatibility_path_used": _truthy(attrs.get("data-compatibility-path-used")),
        "fallback_path_used": "fallback" in lowered and "fallback-skipped" not in lowered,
        "visible": {
            "title": attrs.get("data-title") or "",
            "summary": text[:1200],
            "dimensions_reo_checks": payload.get("summary_sections") or {},
            "button_texts": button_texts,
            "final_card_ready": bool(cards and outcome in OUTCOMES),
            "post_apply_hash": "",
        },
        "source": {
            "card_count": payload.get("card_count"),
            "card_attrs": attrs,
            "browser_state_available": bool(state),
            "browser_state_keys": sorted(str(key) for key in state.keys())[:80] if isinstance(state, dict) else [],
        },
    }
    tuple_payload["tuple_hash"] = _stable_hash({key: tuple_payload[key] for key in tuple_payload if key != "source"})
    return tuple_payload


def _investigation_registry() -> dict[str, Any]:
    family_rows = {}
    for family, cls in GOVERNING_FAMILY_REGISTRY.items():
        legal = list(OUTCOMES)
        family_rows[family] = {
            "strategy_class": f"{cls.__module__}.{cls.__name__}",
            "legal_outcomes": legal,
            "legal_publication_builders": ["FinalDesignGuidePublication"],
            "legal_display_builders": ["FinalDesignGuideDisplay"],
            "legal_renderer_paths": [
                "inputs_page_modules.design_guide.current_coordinators._design_guide_card_contract_attrs"
            ],
            "runtime_fixture_status": "REQUIRED_NOT_FULLY_PROVEN_BY_THIS_INVESTIGATION",
        }
    return {
        "status": "INVESTIGATION_ONLY",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "families": family_rows,
        "aliases": dict(GOVERNING_FAMILY_ALIASES),
        "tuple_fields": [
            "engineering_hash",
            "family_code",
            "outcome_code",
            "sub_outcome_code",
            "template_code",
            "candidate_id",
            "evidence_candidate_id",
            "blocker_or_proof_id",
            "publication_authority_hash",
            "publication_builder",
            "display_builder",
            "renderer_path",
            "visible_explanation_owner",
            "cta_state",
            "cta_candidate_id",
            "apply_state",
            "apply_payload_candidate_id",
            "compatibility_path_used",
            "fallback_path_used",
        ],
    }


def _lock_results_for_tuple(row: dict[str, Any], registry: dict[str, Any]) -> list[dict[str, Any]]:
    family = str(row.get("family_code") or "")
    outcome = str(row.get("outcome_code") or "")
    cta = str(row.get("cta_state") or "")
    apply = str(row.get("apply_state") or "")
    candidate = str(row.get("candidate_id") or "")
    cta_candidate = str(row.get("cta_candidate_id") or "")
    apply_candidate = str(row.get("apply_payload_candidate_id") or "")
    families = registry.get("families") or {}

    def result(lock: str, ok: bool, fail: str, *, status_if_missing: str = "FAIL") -> dict[str, Any]:
        status = "PASS" if ok else status_if_missing
        return {"lock": lock, "status": status, "failure": "" if ok else fail}

    known_family = family in families
    legal_outcome = known_family and outcome in set((families.get(family) or {}).get("legal_outcomes") or [])
    action = outcome in ACTION_OUTCOMES
    non_action = outcome in NON_ACTION_OUTCOMES
    return [
        result("registry_family_present", known_family, f"unregistered family `{family}`"),
        result("registered_outcome_only", legal_outcome, f"illegal outcome `{family}:{outcome}`"),
        result("template_code_present", bool(row.get("template_code")), "template/title code not browser-exposed"),
        result("publication_authority_hash_present", bool(row.get("publication_authority_hash")), "publication authority hash missing"),
        result("publication_builder_canonical", row.get("publication_builder") == "FinalDesignGuidePublication", "non-canonical publication builder"),
        result("display_builder_canonical", row.get("display_builder") == "FinalDesignGuideDisplay", "non-canonical display builder"),
        result("renderer_path_canonical", row.get("renderer_path", "").endswith("_design_guide_card_contract_attrs"), "renderer path not card contract"),
        result("visible_explanation_owner_not_generic", row.get("visible_explanation_owner") == "family_or_final_publication", "visible reason appears page/shared-generic or unproven"),
        result("action_requires_enabled_cta", not action or cta == "ENABLED", "ACTION outcome does not expose enabled CTA"),
        result("action_requires_apply_payload", not action or bool(apply_candidate), "ACTION outcome has no Apply payload candidate id"),
        result("non_action_forbids_apply", not non_action or apply == "ABSENT", f"{outcome or 'non-action'} outcome exposes Apply state `{apply}`"),
        result("cta_candidate_matches_selection", not cta_candidate or cta_candidate == candidate, "CTA candidate does not match selected candidate"),
        result("apply_payload_matches_cta", not apply_candidate or not cta_candidate or apply_candidate == cta_candidate, "Apply payload candidate does not match CTA candidate"),
        result("compatibility_path_absent", not bool(row.get("compatibility_path_used")), "compatibility path used in live route"),
        result("fallback_path_absent", not bool(row.get("fallback_path_used")), "fallback path used in live route"),
        result("browser_final_card_ready", bool((row.get("visible") or {}).get("final_card_ready")), "browser final card not ready"),
    ]


def _scenario_status(lock_results: list[dict[str, Any]]) -> str:
    if any(row.get("status") == "FAIL" for row in lock_results):
        return "FAIL"
    if any(row.get("status") == "NOT_PROVEN" for row in lock_results):
        return "NOT_PROVEN"
    return "PASS"


def _mutations(base_row: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [
        ("unregistered_family", {"family_code": "UNKNOWN_FAMILY"}),
        ("illegal_outcome", {"outcome_code": "BOGUS"}),
        ("missing_template", {"template_code": ""}),
        ("missing_authority_hash", {"publication_authority_hash": ""}),
        ("wrong_publication_builder", {"publication_builder": "inputs_page_local_builder"}),
        ("wrong_display_builder", {"display_builder": "page_display_builder"}),
        ("wrong_renderer", {"renderer_path": "inputs_page.py.local_renderer"}),
        ("generic_visible_reason", {"visible_explanation_owner": "page_or_shared_generic_wording_detected"}),
        ("action_without_cta", {"outcome_code": "ACTION", "cta_state": "ABSENT", "apply_state": "ABSENT", "apply_payload_candidate_id": ""}),
        ("action_without_apply_payload", {"outcome_code": "ACTION", "cta_state": "ENABLED", "apply_state": "ENABLED", "apply_payload_candidate_id": ""}),
        ("pass_with_apply", {"outcome_code": "PASS", "apply_state": "ENABLED", "apply_payload_candidate_id": "bad"}),
        ("blocked_with_apply", {"outcome_code": "BLOCKED", "apply_state": "ENABLED", "apply_payload_candidate_id": "bad"}),
        ("error_with_apply", {"outcome_code": "ERROR", "apply_state": "ENABLED", "apply_payload_candidate_id": "bad"}),
        ("proof_pending_with_apply", {"outcome_code": "PROOF_PENDING", "apply_state": "ENABLED", "apply_payload_candidate_id": "bad"}),
        ("cta_candidate_mismatch", {"candidate_id": "selected-a", "cta_candidate_id": "selected-b"}),
        ("apply_candidate_mismatch", {"cta_candidate_id": "selected-a", "apply_payload_candidate_id": "selected-b"}),
        ("compatibility_path_used", {"compatibility_path_used": True}),
        ("fallback_path_used", {"fallback_path_used": True}),
        ("browser_card_not_ready", {"visible": {**dict(base_row.get("visible") or {}), "final_card_ready": False}}),
        ("unregistered_action_tuple", {"family_code": "UNKNOWN_FAMILY", "outcome_code": "ACTION", "cta_state": "ENABLED"}),
    ]
    rows = []
    for name, patch in specs:
        mutated = json.loads(json.dumps(base_row, default=str))
        mutated.update(patch)
        rows.append({"mutation": name, "tuple": mutated})
    return rows


def _run_mutation_sensitivity(base_rows: list[dict[str, Any]], registry: dict[str, Any]) -> dict[str, Any]:
    if not base_rows:
        return {"status": "FAIL", "mutation_rows": [], "escaped_mutations": ["runtime_tuple_capture_empty"]}
    rows = []
    escaped = []
    for mutation in _mutations(base_rows[0]):
        lock_rows = _lock_results_for_tuple(mutation["tuple"], registry)
        failed_locks = [row["lock"] for row in lock_rows if row.get("status") == "FAIL"]
        if not failed_locks:
            escaped.append(mutation["mutation"])
        rows.append(
            {
                "mutation": mutation["mutation"],
                "status": "CAUGHT" if failed_locks else "ESCAPED",
                "failed_locks": failed_locks,
            }
        )
    return {
        "status": "PASS" if not escaped else "FAIL",
        "mutation_rows": rows,
        "escaped_mutations": escaped,
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("|" + "|".join(_clean(cell).replace("|", "/") for cell in row) + "|")
    return out


def _write_reports(*, stamp: str, observations: list[dict[str, Any]], registry: dict[str, Any], base_url: str) -> dict[str, Path]:
    comparison_rows = []
    fallback_rows = []
    lock_rows_all = []
    illegal_rows = []
    for row in observations:
        locks = _lock_results_for_tuple(row, registry)
        status = _scenario_status(locks)
        row["investigation_lock_status"] = status
        row["investigation_locks"] = locks
        if status != "PASS":
            illegal_rows.append(row)
        comparison_rows.append(
            [
                row.get("scenario_id"),
                row.get("recipe_id"),
                row.get("family_code") or "MISSING",
                row.get("outcome_code") or "MISSING",
                status,
                "; ".join(lock["failure"] for lock in locks if lock.get("failure")),
            ]
        )
        fallback_rows.append(
            [
                row.get("scenario_id"),
                row.get("recipe_id"),
                row.get("compatibility_path_used"),
                row.get("fallback_path_used"),
                row.get("visible_explanation_owner"),
            ]
        )
        for lock in locks:
            lock_rows_all.append([row.get("scenario_id"), lock.get("lock"), lock.get("status"), lock.get("failure")])

    mutation = _run_mutation_sensitivity(observations, registry)
    duplicate_groups: dict[str, list[dict[str, Any]]] = {}
    for row in observations:
        if row.get("investigation_lock_status") != "PASS":
            continue
        if not row.get("family_code") or not row.get("outcome_code") or not row.get("publication_authority_hash"):
            continue
        key = "|".join(
            str(row.get(name) or "")
            for name in ("family_code", "outcome_code", "template_code", "publication_authority_hash")
        )
        duplicate_groups.setdefault(key, []).append(row)
    duplicates = [
        {"group": key, "scenario_ids": [item.get("scenario_id") for item in items]}
        for key, items in duplicate_groups.items()
        if len(items) > 1
    ]

    paths = {
        "observations": AUDIT_DIR / f"runtime_outcome_tuple_observations_{stamp}.json",
        "registry": CONTRACT_DIR / f"design_brain_family_outcome_registry_investigation_{stamp}.json",
        "comparison": AUDIT_DIR / f"runtime_tuple_registry_comparison_{stamp}.md",
        "duplicate": AUDIT_DIR / f"duplicate_runtime_authority_routes_{stamp}.md",
        "identity": AUDIT_DIR / f"publication_to_browser_runtime_identity_{stamp}.md",
        "fallback": AUDIT_DIR / f"runtime_fallback_usage_matrix_{stamp}.md",
        "mutation": AUDIT_DIR / f"deliberate_failure_detection_runtime_{stamp}.md",
        "locks": AUDIT_DIR / f"investigation_lock_results_{stamp}.md",
        "scope": AUDIT_DIR / f"verifier_scope_truthfulness_runtime_{stamp}.md",
        "illegal": AUDIT_DIR / f"missing_or_illegal_runtime_paths_{stamp}.md",
        "remaining": AUDIT_DIR / f"remaining_unproven_paths_{stamp}.md",
        "remediation": AUDIT_DIR / f"minimum_production_remediation_plan_{stamp}.md",
        "scorecard": AUDIT_DIR / f"final_runtime_and_verifier_trust_scorecard_{stamp}.md",
    }

    _write_json(paths["observations"], {"status": "PASS" if observations else "FAIL", "base_url": base_url, "observations": observations})
    _write_json(paths["registry"], registry)

    comparison = [
        "# Runtime Tuple Registry Comparison",
        "",
        f"Status: `{'PASS' if observations and not illegal_rows else 'FAIL'}`",
        "",
        *_markdown_table(
            ["Scenario", "Recipe", "Family", "Outcome", "Lock Status", "Failures"],
            comparison_rows or [["NONE", "NONE", "NONE", "NONE", "FAIL", "runtime_tuple_capture_empty"]],
        ),
    ]
    _write_text(paths["comparison"], "\n".join(comparison))

    duplicate_status = "FAIL" if duplicates else ("PASS" if observations else "FAIL")
    _write_text(
        paths["duplicate"],
        "\n".join(
            [
                "# Duplicate Runtime Authority Routes",
                "",
                f"Status: `{duplicate_status}`",
                "",
                "Duplicate groups:",
                "```json",
                json.dumps(duplicates, indent=2, sort_keys=True, default=str),
                "```",
                "",
                "One observed tuple cannot prove the absence of duplicate routes across all families.",
            ]
        ),
    )

    identity_rows = []
    for row in observations:
        source = row.get("source") or {}
        attrs = source.get("card_attrs") or {}
        identity_rows.append(
            [
                row.get("scenario_id"),
                attrs.get("data-selected-family-id") or "",
                attrs.get("data-published-family-id") or "",
                attrs.get("data-cta-family-id") or "",
                row.get("candidate_id") or "",
                row.get("cta_candidate_id") or "",
                row.get("apply_payload_candidate_id") or "",
            ]
        )
    _write_text(
        paths["identity"],
        "\n".join(
            [
                "# Publication To Browser Runtime Identity",
                "",
                f"Status: `{'PASS' if observations else 'FAIL'}`",
                "",
                *_markdown_table(
                    ["Scenario", "Selected family", "Published family", "CTA family", "Selected candidate", "CTA candidate", "Apply candidate"],
                    identity_rows or [["NONE", "", "", "", "", "", ""]],
                ),
            ]
        ),
    )

    _write_text(
        paths["fallback"],
        "\n".join(
            [
                "# Runtime Fallback Usage Matrix",
                "",
                f"Status: `{'PASS' if observations and not any(row.get('fallback_path_used') or row.get('compatibility_path_used') for row in observations) else 'FAIL'}`",
                "",
                *_markdown_table(
                    ["Scenario", "Recipe", "Compatibility path", "Fallback path", "Visible explanation owner"],
                    fallback_rows or [["NONE", "NONE", "UNKNOWN", "UNKNOWN", "UNKNOWN"]],
                ),
            ]
        ),
    )

    _write_text(
        paths["mutation"],
        "\n".join(
            [
                "# Deliberate Failure Detection Runtime",
                "",
                f"Status: `{mutation['status']}`",
                "",
                "These are verifier-only mutated runtime tuples. Production behavior was not changed.",
                "",
                *_markdown_table(
                    ["Mutation", "Status", "Failed locks"],
                    [[row["mutation"], row["status"], ", ".join(row["failed_locks"])] for row in mutation["mutation_rows"]],
                ),
                "",
                "Escaped mutations:",
                "```json",
                json.dumps(mutation["escaped_mutations"], indent=2, sort_keys=True),
                "```",
            ]
        ),
    )

    _write_text(
        paths["locks"],
        "\n".join(
            [
                "# Investigation Lock Results",
                "",
                f"Status: `{'PASS' if observations and not illegal_rows and mutation['status'] == 'PASS' else 'FAIL'}`",
                "",
                *_markdown_table(
                    ["Scenario", "Lock", "Status", "Failure"],
                    lock_rows_all or [["NONE", "runtime_tuple_capture", "FAIL", "runtime_tuple_capture_empty"]],
                ),
            ]
        ),
    )

    _write_text(
        paths["scope"],
        "\n".join(
            [
                "# Verifier Scope Truthfulness Runtime",
                "",
                "Status: `FAIL`",
                "",
                "The new investigation runner proves only the browser routes it captures in this run.",
                "It does not prove all family-outcome paths unless every required recipe/path is executed and all tuples pass.",
                "Existing green-board verifiers must not claim full runtime coverage from stale artifacts or partial browser sampling.",
            ]
        ),
    )

    all_families = sorted((registry.get("families") or {}).keys())
    observed_families = sorted({str(row.get("family_code") or "") for row in observations if row.get("family_code")})
    remaining_families = [family for family in all_families if family not in observed_families]
    _write_text(
        paths["illegal"],
        "\n".join(
            [
                "# Missing Or Illegal Runtime Paths",
                "",
                f"Status: `{'FAIL' if illegal_rows or remaining_families or not observations else 'PASS'}`",
                "",
                "Illegal or failing observed paths:",
                "```json",
                json.dumps(
                    [
                        {
                            "scenario_id": row.get("scenario_id"),
                            "family_code": row.get("family_code"),
                            "outcome_code": row.get("outcome_code"),
                            "failures": [lock.get("failure") for lock in row.get("investigation_locks") or [] if lock.get("failure")],
                        }
                        for row in illegal_rows
                    ],
                    indent=2,
                    sort_keys=True,
                    default=str,
                ),
                "```",
            ]
        ),
    )

    _write_text(
        paths["remaining"],
        "\n".join(
            [
                "# Remaining Unproven Paths",
                "",
                f"Status: `{'FAIL' if remaining_families else ('PASS' if observations else 'FAIL')}`",
                "",
                "Observed families:",
                "```json",
                json.dumps(observed_families, indent=2),
                "```",
                "Families not observed in this runtime capture:",
                "```json",
                json.dumps(remaining_families, indent=2),
                "```",
            ]
        ),
    )

    _write_text(
        paths["remediation"],
        "\n".join(
            [
                "# Minimum Production Remediation Plan",
                "",
                "Status: `ACTION_REQUIRED`",
                "",
                "1. Add a stable browser recipe for every registered family and each legal outcome state used by that family.",
                "2. Expose canonical template/sub-outcome/proof ids on the final card contract where currently absent.",
                "3. Wire the shared green-board to require current runtime tuple artifacts, not just static inspection.",
                "4. Promote the isolated mutation predicates into named verifier locks once each path has a browser fixture.",
                "5. Only mark the app green when runtime coverage, identity parity, fallback absence, and mutation sensitivity all pass.",
            ]
        ),
    )

    score_status = "PASS"
    if not observations or illegal_rows or duplicates or mutation["status"] != "PASS":
        score_status = "FAIL"
    elif remaining_families:
        score_status = "PARTIAL"
    _write_text(
        paths["scorecard"],
        "\n".join(
            [
                "# Final Runtime And Verifier Trust Scorecard",
                "",
                f"Status: `{score_status}`",
                "",
                f"- Runtime tuples captured: `{len(observations)}`",
                f"- Observed families: `{len(observed_families)}` of `{len(all_families)}`",
                f"- Registry/lock failing tuples: `{len(illegal_rows)}`",
                f"- Duplicate authority route groups: `{len(duplicates)}`",
                f"- Deliberate mutation status: `{mutation['status']}`",
                "",
                "Conclusion: the app is not runtime-green until all registered family outcome paths are observed live and the investigation locks pass against current-code artifacts.",
            ]
        ),
    )

    unknown_path = AUDIT_DIR / "unknown_path_runtime_observations_2026-07-23T17-45-00.json"
    if unknown_path.exists():
        _write_json(
            unknown_path,
            {
                "status": "UPDATED_WITH_RUNTIME_OBSERVATIONS",
                "updated_by": Path(__file__).name,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "source_artifact": str(paths["observations"].relative_to(ROOT)),
                "observations": observations,
            },
        )

    return paths


def _capture_observations(*, url: str, recipes: list[str], timeout_s: float, headed: bool) -> list[dict[str, Any]]:
    scenarios = recipes or ["CURRENT_LIVE_ROUTE"]
    observations: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        try:
            for index, recipe in enumerate(scenarios, start=1):
                context = browser.new_context(viewport={"width": 1600, "height": 1050})
                page = context.new_page()
                page.set_default_timeout(20_000)
                target_url = url if recipe == "CURRENT_LIVE_ROUTE" else _with_query(url, {"page": "inputs", "browser_recipe": recipe})
                scenario_id = f"runtime_{index:02d}_{recipe}"
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
                    try:
                        page.wait_for_selector(
                            "[data-testid='design-guide-card'], [data-outcome-state], [data-publication-hash], .fast-guidance-item",
                            timeout=int(max(5.0, timeout_s) * 1000),
                        )
                    except PlaywrightTimeoutError:
                        pass
                    time.sleep(1.0)
                    payload = _capture_page_payload(page)
                    payload["body_text_hash"] = _stable_hash(payload.get("body_text") or "")
                    state = _read_browser_state_from_dom(page)
                    observations.append(
                        _tuple_from_capture(
                            scenario_id=scenario_id,
                            recipe_id=recipe,
                            payload=payload,
                            state=state,
                        )
                    )
                except Exception as exc:
                    observations.append(
                        {
                            "scenario_id": scenario_id,
                            "recipe_id": recipe,
                            "url": target_url,
                            "engineering_hash": "",
                            "family_code": "",
                            "outcome_code": "",
                            "sub_outcome_code": "",
                            "template_code": "",
                            "candidate_id": "",
                            "evidence_candidate_id": "",
                            "blocker_or_proof_id": "",
                            "publication_authority_hash": "",
                            "publication_builder": "NOT_PROVEN",
                            "display_builder": "NOT_PROVEN",
                            "renderer_path": "NOT_PROVEN",
                            "visible_explanation_owner": "not_proven",
                            "cta_state": "UNKNOWN",
                            "cta_candidate_id": "",
                            "apply_state": "UNKNOWN",
                            "apply_payload_candidate_id": "",
                            "compatibility_path_used": False,
                            "fallback_path_used": False,
                            "visible": {"final_card_ready": False, "error": f"{type(exc).__name__}: {exc}"},
                            "source": {"capture_error": f"{type(exc).__name__}: {exc}"},
                            "tuple_hash": "",
                        }
                    )
                finally:
                    context.close()
        finally:
            browser.close()
    return observations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8504/?page=inputs&batch_design_open=0",
        help="Live Inputs page URL to capture.",
    )
    parser.add_argument("--recipe", action="append", default=[], help="Optional browser_recipe values to capture.")
    parser.add_argument("--timeout-s", type=float, default=35.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    stamp = _stamp()
    registry = _investigation_registry()
    observations = _capture_observations(
        url=str(args.url),
        recipes=[str(item) for item in args.recipe if str(item).strip()],
        timeout_s=float(args.timeout_s),
        headed=bool(args.headed),
    )
    # Treat pages without a final card as empty for the stop condition.
    if observations and not any((row.get("visible") or {}).get("final_card_ready") for row in observations):
        observations = observations
    paths = _write_reports(stamp=stamp, observations=observations, registry=registry, base_url=str(args.url))
    has_ready_tuple = any((row.get("visible") or {}).get("final_card_ready") for row in observations)
    has_failing_tuple = any(row.get("investigation_lock_status") == "FAIL" for row in observations)
    missing_family_coverage = len({row.get("family_code") for row in observations if row.get("family_code")}) < len(
        registry.get("families") or {}
    )
    status = "FAIL" if not has_ready_tuple or has_failing_tuple else "PARTIAL" if missing_family_coverage else "PASS"
    print(json.dumps({"status": status, "paths": {k: str(v) for k, v in paths.items()}}, indent=2))
    return 0 if has_ready_tuple else 1


if __name__ == "__main__":
    raise SystemExit(main())
