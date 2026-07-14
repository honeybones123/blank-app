"""Audit browser/live Design Guide actionable-card coverage.

Proof-only. Samples frozen browser recipes and records whether each produces
an enabled publication CTA, a visible action button, both, or neither. This
does not click buttons and does not change product behaviour.
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
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)
from tools.verification.recipes.one_click_recipe_defs import FROZEN_RECIPES  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPES = [
    "R1A_M300_V0",
    "R2A_M0_V400",
    "R3A_M300_V400",
    "R4A_M45_V0",
    "R5A_M0_V150",
    "R6A_M45_V150",
    "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS",
]


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _query(url: str, params: dict[str, Any]) -> str:
    return f"{str(url).rstrip('/')}/?{urlencode({k: v for k, v in params.items() if v is not None})}"


def _known_recipe_names() -> set[str]:
    names: set[str] = set()
    for recipe in FROZEN_RECIPES:
        for subcase in list(recipe.get("subcases") or []):
            name = str(subcase.get("name") or "").strip()
            if name:
                names.add(name)
    return names


def _dom_action_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
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
              const enabled = (el) => visible(el) && !el.disabled && el.getAttribute("aria-disabled") !== "true";
              const actionPattern = /(Run one-click auto design|Apply recommendation|Apply Design Guide|Apply selected|Apply repair|Apply cleanup|Use this design|Update design|Apply)/i;
              const rejectPattern = /(debug|show|hide|download|export|copy|reset|clear|reload|browse|select|previous|next)$/i;
              const buttons = Array.from(document.querySelectorAll("button,[role='button']"))
                .map((el) => ({el, text: clean(el.innerText || el.textContent || el.getAttribute("aria-label"))}))
                .filter((item) => item.text && visible(item.el));
              const actionButtons = buttons
                .filter((item) => actionPattern.test(item.text) && !rejectPattern.test(item.text))
                .map((item) => ({
                  text: item.text,
                  enabled: enabled(item.el),
                  disabled: !!item.el.disabled || item.el.getAttribute("aria-disabled") === "true"
                }));
              const cardCandidates = Array.from(document.querySelectorAll('[data-testid="design-guide-card"], details.fast-guidance-item, .fast-guidance-item, .dg-card'))
                .filter(visible)
                .map((el) => clean(el.innerText || el.textContent).slice(0, 220));
              return {
                visible_button_texts: buttons.map((item) => item.text).slice(0, 40),
                action_button_count: actionButtons.length,
                enabled_action_button_count: actionButtons.filter((item) => item.enabled).length,
                action_buttons: actionButtons.slice(0, 12),
                design_guide_card_count: cardCandidates.length,
                design_guide_card_texts: cardCandidates.slice(0, 4)
              };
            }
            """
        )
        or {}
    )


def _publication_probe(state: dict[str, Any]) -> dict[str, Any]:
    dg_probe = dict(state.get("design_guide_probe") or {})
    debug = dict(dg_probe.get("debug_bundle") or {})
    verifier_payload = dict(debug.get("final_publication_verifier_payload") or {})
    cta = dict(verifier_payload.get("cta") or {})
    button_contract = dict(
        debug.get("displayed_primary_button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
        or {}
    )
    return {
        "browser_recipe": state.get("browser_recipe"),
        "browser_recipe_error": state.get("browser_recipe_error"),
        "primary_card_title": dg_probe.get("primary_card_title") or debug.get("primary_card_title"),
        "guidance_branch": dg_probe.get("guidance_branch") or debug.get("guidance_branch"),
        "publication_hash": verifier_payload.get("publication_hash") or debug.get("publication_hash"),
        "final_publication_authority_hash": (
            verifier_payload.get("final_publication_authority_hash")
            or debug.get("final_publication_authority_hash")
        ),
        "cta": {
            "enabled": cta.get("enabled"),
            "actionable": cta.get("actionable"),
            "action_type": cta.get("action_type"),
            "updates_count": len(dict(cta.get("updates") or {})),
            "blocking_reason": cta.get("blocking_reason"),
        },
        "button_contract": {
            "enabled": button_contract.get("enabled"),
            "actionable": button_contract.get("actionable"),
            "action_type": button_contract.get("action_type"),
            "updates_count": len(dict(button_contract.get("updates") or {})),
            "blocking_reason": button_contract.get("blocking_reason"),
        },
    }


def _sample_recipe(page, *, base_url: str, recipe: str, wait_ms: int) -> dict[str, Any]:
    page.goto(_query(base_url, {"page": "inputs", "browser_recipe": recipe}), wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(wait_ms)
    try:
        state = _load_browser_state(page, timeout_s=4.0)
    except Exception as exc:
        state = {"browser_state_error": f"{type(exc).__name__}: {exc}"}
    return {
        "recipe": recipe,
        "publication": _publication_probe(state),
        "dom": _dom_action_probe(page),
    }


def _capture(base_url: str, *, recipes: list[str], wait_ms: int, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        rows = [_sample_recipe(page, base_url=base_url, recipe=recipe, wait_ms=wait_ms) for recipe in recipes]
        browser.close()
    return {"base_url": base_url, "recipes": recipes, "rows": rows}


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    rows = list(capture.get("rows") or [])
    actionable_rows: list[str] = []
    selector_gap_rows: list[str] = []
    intentionally_non_actionable_rows: list[str] = []
    no_publication_rows: list[str] = []
    for row in rows:
        recipe = str(row.get("recipe") or "")
        pub = dict(row.get("publication") or {})
        dom = dict(row.get("dom") or {})
        cta = dict(pub.get("cta") or {})
        button = dict(pub.get("button_contract") or {})
        publication_ready = bool(pub.get("publication_hash") or pub.get("final_publication_authority_hash"))
        cta_enabled = bool(cta.get("enabled") or button.get("enabled"))
        visible_enabled_button = int(dom.get("enabled_action_button_count") or 0) > 0
        if cta_enabled and visible_enabled_button:
            actionable_rows.append(recipe)
        elif cta_enabled and not visible_enabled_button:
            selector_gap_rows.append(recipe)
        elif publication_ready:
            intentionally_non_actionable_rows.append(recipe)
        else:
            no_publication_rows.append(recipe)

    if actionable_rows:
        diagnosis = "ACTIONABLE_RECIPE_AVAILABLE"
        next_slice = "Run browser/live smoothness profile against an actionable recipe."
    elif selector_gap_rows:
        diagnosis = "CTA_ENABLED_BUT_NO_VISIBLE_ACTION_BUTTON"
        next_slice = "Audit CTA render binding/button selector before post-click smoothness profiling."
    elif intentionally_non_actionable_rows and not no_publication_rows:
        diagnosis = "SAMPLED_RECIPES_NON_ACTIONABLE"
        next_slice = "Add or select a frozen recipe with enabled FinalDesignGuidePublication.cta for post-click profiling."
    else:
        diagnosis = "PUBLICATION_COVERAGE_GAP"
        next_slice = "Audit recipe application and render eligibility before post-click profiling."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "actionable_recipe_count": len(actionable_rows),
        "actionable_recipes": actionable_rows,
        "selector_gap_recipes": selector_gap_rows,
        "intentionally_non_actionable_recipes": intentionally_non_actionable_rows,
        "no_publication_recipes": no_publication_rows,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Actionable Card Coverage Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Actionable recipes: `{cls.get('actionable_recipes')}`",
        f"- Selector gap recipes: `{cls.get('selector_gap_recipes')}`",
        f"- Non-actionable publication recipes: `{cls.get('intentionally_non_actionable_recipes')}`",
        f"- No-publication recipes: `{cls.get('no_publication_recipes')}`",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
        "## Sample Rows",
        "",
        "```json",
        json.dumps(payload.get("rows") or [], indent=2, sort_keys=True, default=str)[:12000],
        "```",
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_actionable_card_coverage_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_actionable_card_coverage_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8630)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_ACTIONABLE_COVERAGE_URL"))
    parser.add_argument("--recipes", nargs="*", default=DEFAULT_RECIPES)
    parser.add_argument("--wait-ms", type=int, default=3500)
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
        recipes = [str(recipe) for recipe in list(args.recipes or []) if str(recipe).strip()]
        unknown = [recipe for recipe in recipes if recipe not in _known_recipe_names() and recipe != "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS"]
        capture = _capture(base_url, recipes=recipes, wait_ms=int(args.wait_ms), headed=bool(args.headed))
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_actionable_card_coverage_audit.v1",
            "created_at": created_at,
            "status": classification["status"],
            "product_behaviour_changed": False,
            "unknown_recipes": unknown,
            "classification": classification,
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"design_guide_actionable_card_coverage_audit {payload['status']}")
        print(f"json={json_path}")
        print(f"report={md_path}")
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
