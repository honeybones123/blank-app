"""Focused browser/live no-button root audit for BENDING_FAIL_GOVERNS.

Audit-only. This captures why a bending-fail Design Guide card can reach the
visible page as "Design Guide blocker proof incomplete" with no Apply button.
It does not change family runtimes, contracts, CTA/publication/apply routing,
rendering, session state, or visible wording.
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
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "A_bending_under_only"


def _query(url: str, params: dict[str, Any]) -> str:
    return f"{str(url).rstrip('/')}/?{urlencode({k: v for k, v in params.items() if v is not None})}"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _short(value: Any, limit: int = 900) -> Any:
    if isinstance(value, dict):
        return {str(k): _short(v, limit=limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_short(item, limit=limit) for item in value[:40]]
    text = str(value) if value is not None else None
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _bending_fail_no_valid_repair_resolved(final_item: dict[str, Any], debug: dict[str, Any]) -> bool:
    for surface in (
        _as_dict(final_item.get("candidate_search_evidence")),
        _as_dict(debug.get("candidate_search_evidence")),
        final_item,
        debug,
    ):
        proof = _as_dict(surface.get("bending_fail_blocked_ownership_proof"))
        if not proof:
            proof = _as_dict(_as_dict(surface.get("repair_reason_proof")).get("blocked_ownership_proof"))
        if (
            str(proof.get("family_id") or "").strip() == "BENDING_FAIL_GOVERNS"
            and _truthy(proof.get("repair_blocked"))
            and _truthy(proof.get("contract_strategy_exhaustion_proven"))
            and not _truthy(proof.get("internal_cap_only"))
        ):
            return True
    return False


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}
    return {"found": True, "path": str(path), "status": payload.get("status"), "path_name": path.name}


def _visible_dom_capture(page) -> dict[str, Any]:
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
              const payloadFor = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const attrs = {};
                for (const attr of Array.from(el.attributes || [])) {
                  const key = String(attr.name || "");
                  const val = String(attr.value || "");
                  if (/design|guide|final|publication|button|cta|apply|authority|hash|state|family/i.test(key + " " + val)) {
                    attrs[key] = val.slice(0, 500);
                  }
                }
                return {
                  tag: String(el.tagName || "").toLowerCase(),
                  text: clean(el.innerText || el.textContent).slice(0, 900),
                  cls: String(el.className || "").slice(0, 240),
                  attrs,
                  disabled: Boolean(el.disabled || el.getAttribute("aria-disabled") === "true"),
                  rect: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom)
                  },
                  style: {
                    color: style.color,
                    backgroundColor: style.backgroundColor,
                    borderColor: style.borderColor
                  }
                };
              };
              const all = Array.from(document.querySelectorAll("body *")).filter(visible);
              const bodyText = String(document.body && document.body.innerText || "");
              const app = document.querySelector(".stApp");
              const scriptState = app && app.getAttribute ? app.getAttribute("data-test-script-state") : null;
              const guideNodes = all
                .filter((el) => /Design Guide|blocker proof incomplete|Bending capacity|Strengthening|required|Repair required|Run one-click|Apply/i.test(clean(el.innerText || el.textContent)))
                .slice(0, 80)
                .map(payloadFor);
              const buttons = Array.from(document.querySelectorAll("button"))
                .filter(visible)
                .map(payloadFor);
              const actionButtons = buttons.filter((button) => /Run one-click|Apply|Use this design|Update design|repair|cleanup/i.test(button.text));
              return {
                url: window.location.href,
                title: document.title,
                scriptState,
                scriptRunning: scriptState === "running",
                hasLoadingShell: /Checking design guidance/i.test(bodyText),
                bodyHasNoButtonCard: /Design Guide blocker proof incomplete/i.test(bodyText) && /Repair required/i.test(bodyText),
                bodyHasBendingRepairProofIncomplete: /Bending repair proof incomplete/i.test(bodyText)
                  && /Family-owned repair proof is incomplete/i.test(bodyText),
                bodyHasApplyButton: actionButtons.length > 0,
                designGuideTextSample: (() => {
                  const idx = bodyText.lastIndexOf("Design Guide");
                  return idx >= 0 ? bodyText.slice(idx, idx + 1600) : bodyText.slice(0, 1600);
                })(),
                guideNodes,
                buttons,
                actionButtons,
                scroll: {
                  x: window.scrollX,
                  y: window.scrollY,
                  innerWidth: window.innerWidth,
                  innerHeight: window.innerHeight,
                  bodyHeight: document.body ? document.body.scrollHeight : null
                }
              };
            }
            """
        )
    )


def _final_publication_ready(state: dict[str, Any]) -> bool:
    for key in (
        "guidance_debug",
        "debug_trace",
        "design_guide_debug_bundle",
        "design_guide_debug",
        "guidance_compute_probe",
    ):
        value = state.get(key)
        if not isinstance(value, dict):
            continue
        verifier = value.get("final_publication_verifier_payload")
        if isinstance(verifier, dict) and verifier.get("publication_hash"):
            return True
        if value.get("final_publication_publication_hash") or value.get("publication_hash"):
            return True
    return False


def _wait_for_final_design_guide_state(page, *, timeout_s: float) -> dict[str, Any]:
    import time

    deadline = time.monotonic() + max(1.0, float(timeout_s or 1.0))
    last_dom: dict[str, Any] = {}
    last_state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last_dom = _visible_dom_capture(page)
        except Exception:
            last_dom = {}
        try:
            last_state = _load_browser_state(page, timeout_s=1.0)
        except Exception:
            last_state = {}
        if (
            not bool(last_dom.get("scriptRunning"))
            and (
                _final_publication_ready(last_state)
                or not bool(last_dom.get("hasLoadingShell"))
                or bool(last_dom.get("bodyHasNoButtonCard"))
                or bool(last_dom.get("bodyHasBendingRepairProofIncomplete"))
            )
        ):
            return {
                "ready": True,
                "dom": last_dom,
                "state_available": bool(last_state),
                "reason": "final_or_non_loading_design_guide_state",
            }
        time.sleep(0.5)
    return {
        "ready": False,
        "dom": last_dom,
        "state_available": bool(last_state),
        "reason": "timeout_waiting_for_final_design_guide_state",
    }


def _pick_final_item(state: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for key in (
        "final_visible_design_guide_item",
        "displayed_primary_item",
        "primary_design_guide_item",
        "primary_guidance_item",
        "final_visible_item",
    ):
        value = state.get(key)
        if isinstance(value, dict):
            candidates.append(dict(value))
    debug = _as_dict(state.get("guidance_debug") or state.get("debug_trace") or state.get("design_guide_debug_bundle"))
    for key in ("final_visible_item", "displayed_primary_item", "primary_item", "primary_guidance_item"):
        value = debug.get(key)
        if isinstance(value, dict):
            candidates.append(dict(value))
    browser_probe = _as_dict(state.get("browser_shared_probe"))
    for key in ("final_visible_item", "displayed_primary_item", "primary_guidance_item"):
        value = browser_probe.get(key)
        if isinstance(value, dict):
            candidates.append(dict(value))
    for candidate in candidates:
        title = str(candidate.get("title_main") or candidate.get("title") or "")
        if "Design Guide blocker proof incomplete" in title or candidate.get("button_contract") or candidate.get("selected_family_id"):
            return candidate
    return candidates[0] if candidates else {}


def _pick_debug(state: dict[str, Any]) -> dict[str, Any]:
    debug = {}
    for key in (
        "guidance_debug",
        "debug_trace",
        "design_guide_debug_bundle",
        "design_guide_debug",
        "guidance_compute_probe",
    ):
        value = state.get(key)
        if isinstance(value, dict):
            debug.update(value)
    return debug


def _active_failures_from_state(state: dict[str, Any], debug: dict[str, Any]) -> list[str]:
    candidates = []
    overview = _as_dict(debug.get("overview") or state.get("overview") or _as_dict(state.get("guidance_compute_probe")).get("overview"))
    statuses = _as_dict(overview.get("statuses"))
    utils = _as_dict(overview.get("utils"))
    for family in ("bending", "shear"):
        status = str(statuses.get(family) or "").strip().upper()
        try:
            util = float(utils.get(family))
        except Exception:
            util = None
        if status == "FAIL" or (util is not None and util > 1.0):
            candidates.append(family)
    explicit = debug.get("active_failures") or state.get("active_failures")
    if isinstance(explicit, list):
        for item in explicit:
            fam = str(item or "").strip().lower()
            if fam in {"bending", "shear"} and fam not in candidates:
                candidates.append(fam)
    return candidates


def _runtime_blocker_proof_fields(exact_blockers: dict[str, Any], final_item: dict[str, Any], debug: dict[str, Any]) -> dict[str, Any]:
    surfaces = {
        "final_item_candidate_search_evidence": _as_dict(final_item.get("candidate_search_evidence")),
        "debug_candidate_search_evidence": _as_dict(debug.get("candidate_search_evidence")),
        "exact_blockers": _as_dict(exact_blockers),
    }
    tokens = (
        "runtime_authority",
        "contract_authority",
        "ladder_hash",
        "ladder_trace",
        "runtime_evidence",
        "family_runtime_evidence",
        "contract_runtime_evidence",
        "selected_strategy_lane",
        "repair_reason_proof",
        "blocked_reason",
        "lock_verifier",
    )
    found: dict[str, Any] = {}
    for surface_name, surface in surfaces.items():
        found[surface_name] = {
            key: _short(value)
            for key, value in surface.items()
            if any(token in str(key) for token in tokens)
        }
    for family, row in _as_dict(exact_blockers).items():
        if isinstance(row, dict):
            found[f"exact_blocker_{family}"] = {
                key: _short(value)
                for key, value in row.items()
                if any(token in str(key) for token in tokens)
            }
    return found


def _capture_root(page, *, scenario_id: str) -> dict[str, Any]:
    browser_state_error = None
    try:
        browser_state = _load_browser_state(page, timeout_s=45.0)
    except Exception as exc:
        browser_state = {}
        browser_state_error = f"{type(exc).__name__}: {exc}"
    debug = _pick_debug(browser_state)
    final_item = _pick_final_item(browser_state)
    contract = _as_dict(
        final_item.get("button_contract")
        or debug.get("displayed_primary_button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
    )
    exact_blockers = _as_dict(
        final_item.get("exact_blockers_by_family")
        or final_item.get("post_click_exact_blockers_by_family")
        or debug.get("exact_blockers_by_family")
        or debug.get("post_click_exact_blockers_by_family")
    )
    cta_payload = _as_dict(
        _as_dict(debug.get("final_publication_verifier_payload")).get("cta")
        or debug.get("final_publication_cta")
    )
    controller_trace = _as_dict(debug.get("design_guide_controller_trace_only_parity"))
    dom = _visible_dom_capture(page)
    active_failures = _active_failures_from_state(browser_state, debug)
    if not active_failures and dom.get("bodyHasBendingRepairProofIncomplete"):
        active_failures = ["bending"]
    selected_family = str(
        final_item.get("selected_family_id")
        or final_item.get("published_family_id")
        or final_item.get("family")
        or debug.get("selected_family_id")
        or debug.get("published_family_id")
        or ""
    ).strip()
    resolved_bending_no_valid_repair = _bending_fail_no_valid_repair_resolved(final_item, debug)
    if not selected_family and resolved_bending_no_valid_repair:
        selected_family = "BENDING_FAIL_GOVERNS"
    final_title = str(final_item.get("title_main") or final_item.get("title") or "").strip()
    if not final_title and dom.get("bodyHasBendingRepairProofIncomplete"):
        final_title = "Bending repair proof incomplete"
    promotion_skip = debug.get("bending_fail_preview_pass_promotion_skipped")
    policy = (
        final_item.get("design_guide_publication_policy")
        or debug.get("design_guide_publication_policy")
        or debug.get("guidance_branch")
    )
    no_button_root_class = "UNKNOWN"
    if "bending" in active_failures and not bool(contract.get("enabled") or contract.get("actionable")):
        if promotion_skip:
            no_button_root_class = "BENDING_PROMOTION_SKIPPED"
        elif str(policy or "") in {
            "locked_active_failure_missing_exact_proof",
            "unlocked_active_failure_missing_runtime_proof",
            "unlocked_active_failure_missing_apply_cta",
        }:
            no_button_root_class = str(policy)
        elif "Design Guide blocker proof incomplete" in final_title or dom.get("bodyHasNoButtonCard"):
            no_button_root_class = "NO_BUTTON_BLOCKER_CARD_VISIBLE"
        elif dom.get("bodyHasBendingRepairProofIncomplete") and not dom.get("bodyHasApplyButton"):
            no_button_root_class = "BENDING_REPAIR_PROOF_INCOMPLETE_DOM_ONLY"
        elif (
            resolved_bending_no_valid_repair
            and str(contract.get("blocking_reason") or contract.get("disabled_reason") or "").strip() == "no_apply_locked"
        ):
            no_button_root_class = "RESOLVED_BENDING_FAIL_NO_VALID_REPAIR_NO_APPLY_LOCKED"
    elif bool(contract.get("enabled") or contract.get("actionable")):
        no_button_root_class = "BUTTON_CONTRACT_ENABLED"
    return {
        "scenario_id": scenario_id,
        "browser_recipe": browser_state.get("browser_recipe"),
        "browser_recipe_error": browser_state.get("browser_recipe_error"),
        "browser_state_available": bool(browser_state),
        "browser_state_error": browser_state_error,
        "url": dom.get("url"),
        "active_failures": active_failures,
        "selected_family_id": selected_family,
        "final_visible_item": {
            "title": final_title,
            "status": final_item.get("status")
            or final_item.get("critical_status")
            or ("ERROR" if dom.get("bodyHasBendingRepairProofIncomplete") else None),
            "bucket": final_item.get("bucket"),
            "guidance_intent": final_item.get("guidance_intent"),
            "design_guide_publication_policy": final_item.get("design_guide_publication_policy"),
            "candidate_id": final_item.get("candidate_id") or final_item.get("source_candidate_id"),
        },
        "button_contract": {
            "enabled": bool(contract.get("enabled")),
            "actionable": bool(contract.get("actionable")),
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "selected_family_id": contract.get("selected_family_id"),
            "updates": _short(_as_dict(contract.get("updates"))),
            "blocking_reason": contract.get("blocking_reason") or contract.get("disabled_reason"),
            "preview_pass": contract.get("preview_pass"),
            "expected_util": contract.get("expected_util"),
        },
        "bending_fail_preview_pass_promotion_skipped": promotion_skip,
        "bending_fail_preview_pass_probe_statuses": _short(debug.get("bending_fail_preview_pass_probe_statuses")),
        "bending_fail_preview_pass_promotion_flags": {
            key: _short(value)
            for key, value in debug.items()
            if str(key).startswith("bending_fail_preview_pass")
        },
        "exact_blockers_by_family": _short(exact_blockers, limit=1200),
        "runtime_blocker_proof_fields": _runtime_blocker_proof_fields(exact_blockers, final_item, debug),
        "final_publication_cta": _short(cta_payload),
        "controller_trace_parity_payload": _short(controller_trace),
        "dom": {
            "body_has_no_button_card": dom.get("bodyHasNoButtonCard"),
            "body_has_bending_repair_proof_incomplete": dom.get("bodyHasBendingRepairProofIncomplete"),
            "body_has_apply_button": dom.get("bodyHasApplyButton"),
            "design_guide_text_sample": dom.get("designGuideTextSample"),
            "action_buttons": dom.get("actionButtons"),
            "guide_nodes": dom.get("guideNodes"),
        },
        "policy": policy,
        "no_button_root_class": "BROWSER_STATE_UNAVAILABLE_DOM_ONLY"
        if browser_state_error and dom.get("bodyHasNoButtonCard")
        else "BENDING_REPAIR_PROOF_INCOMPLETE_DOM_ONLY"
        if browser_state_error
        and dom.get("bodyHasBendingRepairProofIncomplete")
        and not dom.get("bodyHasApplyButton")
        else no_button_root_class,
        "capture_hash": _stable_hash(
            {
                "active_failures": active_failures,
                "selected_family": selected_family,
                "final_title": final_title,
                "button_contract": contract,
                "promotion_skip": promotion_skip,
                "policy": policy,
                "controller_trace": controller_trace,
            }
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    scenario = (payload.get("scenarios") or [{}])[0]
    lines = [
        "# BENDING_FAIL_GOVERNS No-Button Root Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Root class: `{scenario.get('no_button_root_class')}`",
        f"Recipe: `{payload.get('recipe')}`",
        f"URL: `{scenario.get('url')}`",
        "",
        "## Captured State",
        "",
        f"- Active failures: `{scenario.get('active_failures')}`",
        f"- Selected family: `{scenario.get('selected_family_id')}`",
        f"- Final visible item: `{scenario.get('final_visible_item')}`",
        f"- Button contract: `{scenario.get('button_contract')}`",
        f"- Promotion skipped reason: `{scenario.get('bending_fail_preview_pass_promotion_skipped')}`",
        f"- Policy: `{scenario.get('policy')}`",
        "",
        "## Exact Blockers",
        "",
        "```json",
        json.dumps(scenario.get("exact_blockers_by_family"), indent=2, sort_keys=True, default=str)[:6000],
        "```",
        "",
        "## Runtime Blocker Proof Fields",
        "",
        "```json",
        json.dumps(scenario.get("runtime_blocker_proof_fields"), indent=2, sort_keys=True, default=str)[:6000],
        "```",
        "",
        "## Final Publication CTA",
        "",
        "```json",
        json.dumps(scenario.get("final_publication_cta"), indent=2, sort_keys=True, default=str)[:4000],
        "```",
        "",
        "## Controller Trace Parity",
        "",
        "```json",
        json.dumps(scenario.get("controller_trace_parity_payload"), indent=2, sort_keys=True, default=str)[:4000],
        "```",
        "",
        "## Recommendation",
        "",
        payload.get("recommendation") or "",
        "",
    ]
    if payload.get("errors"):
        lines.extend(["## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```", ""])
    return "\n".join(lines)


def _recommendation(scenario: dict[str, Any]) -> str:
    root = str(scenario.get("no_button_root_class") or "")
    if root == "BENDING_PROMOTION_SKIPPED":
        return (
            "Next fix should focus on why `_promote_bending_fail_family_repair_before_blocker_policy(...)` "
            "skipped promotion. The family may have a repair candidate, but the page did not convert it "
            "into an executor-backed Apply contract."
        )
    if root == "unlocked_active_failure_missing_runtime_proof":
        return (
            "Next fix should prove whether `BENDING_FAIL_GOVERNS` runtime blocker evidence is missing "
            "from exact blockers, or whether publication is reading the wrong blocker surface."
        )
    if root == "unlocked_active_failure_missing_apply_cta":
        return (
            "Next fix should trace candidate generation and CTA binding: active bending failed, but no "
            "executor-backed Apply CTA or complete blocker proof reached final publication."
        )
    if root == "locked_active_failure_missing_exact_proof":
        return (
            "Next fix should focus on exact blocker fields. Geometry lock or active blocker state exists, "
            "but visible exact proof did not cover the active bending failure."
        )
    if root == "BENDING_REPAIR_PROOF_INCOMPLETE_DOM_ONLY":
        return (
            "The live card is a bending-only active failure shell with no visible Apply button, but this "
            "server did not expose browser-state probes. Next run should reproduce the same state on a "
            "test-mode/browser-state-enabled server so promotion skip reason, exact blockers, runtime proof, "
            "CTA authority, and controller parity can be captured before fixing behavior."
        )
    if root == "BUTTON_CONTRACT_ENABLED":
        return (
            "The data says an Apply contract exists. If no button is visible, the next fix belongs in render "
            "visibility/CTA display rather than family runtime or publication selection."
        )
    return (
        "Capture succeeded but did not classify a known root. Inspect the JSON fields for selected family, "
        "button contract, promotion skip, exact blockers, and controller trace parity."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8528)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_NO_BUTTON_AUDIT_URL"))
    parser.add_argument("--url", default=os.environ.get("DESIGN_GUIDE_NO_BUTTON_AUDIT_EXPLICIT_URL"))
    parser.add_argument("--recipe", default=os.environ.get("DESIGN_GUIDE_NO_BUTTON_AUDIT_RECIPE") or DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=75.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    process: subprocess.Popen | None = None
    browser_live_mode = "started_streamlit"
    errors: list[str] = []
    scenarios: list[dict[str, Any]] = []

    try:
        if args.url:
            browser_live_mode = "attached_to_explicit_url"
            _wait_for_http(args.url)
        elif args.base_url:
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
            context = browser.new_context(viewport={"width": 1800, "height": 1000})
            page = context.new_page()
            page.set_default_timeout(30_000)
            target = args.url or _query(base_url, {"page": "inputs", "browser_recipe": args.recipe})
            page.goto(target, wait_until="domcontentloaded", timeout=90_000)
            try:
                page.get_by_text("Design Guide", exact=True).first.wait_for(
                    state="visible",
                    timeout=min(45_000, int(args.timeout_s * 1000)),
                )
            except PlaywrightTimeoutError:
                pass
            readiness = _wait_for_final_design_guide_state(page, timeout_s=args.timeout_s)
            capture = _capture_root(page, scenario_id="initial_bending_fail_no_button_state")
            capture["post_ready_wait"] = readiness
            capture["post_ready_capture"] = bool(readiness.get("ready"))
            scenarios.append(capture)
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

    first = scenarios[0] if scenarios else {}
    status = "PASS" if scenarios and not errors else "FAIL"
    if status == "PASS" and any(not row.get("browser_state_available") for row in scenarios):
        status = "PARTIAL"
    if status == "PASS" and any(not row.get("post_ready_capture") for row in scenarios):
        status = "PARTIAL"
    payload = {
        "schema": "design_guide_bending_fail_no_button_root_audit.v1",
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
        "supporting_artifacts": {
            "controller_live_trace_wiring": _latest_artifact("design_guide_controller_live_trace_wiring"),
            "design_guide_independence_lock": _latest_artifact("design_guide_independence_lock"),
            "render_bridge_lock": _latest_artifact("design_guide_render_bridge_lock"),
            "compute_resolver_publication_bridge_lock": _latest_artifact(
                "design_guide_compute_resolver_publication_bridge_lock"
            ),
        },
        "errors": errors,
        "recommendation": _recommendation(first) if first else "No browser state was captured.",
        "audit_hash": _stable_hash(
            {
                "status": status,
                "scenario_hashes": [row.get("capture_hash") for row in scenarios],
                "errors": errors,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_bending_fail_no_button_root_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_bending_fail_no_button_root_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_bending_fail_no_button_root_audit {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if first:
        print("root_class=" + str(first.get("no_button_root_class")))
        print("active_failures=" + json.dumps(first.get("active_failures") or []))
        print("selected_family_id=" + str(first.get("selected_family_id")))
        print("button_contract=" + json.dumps(first.get("button_contract") or {}, default=str))
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if status in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
