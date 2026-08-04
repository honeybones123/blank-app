"""Probe browser recipes for a family/action runtime tuple.

Verifier-only helper. It starts an isolated CODEX_BROWSER_TEST_MODE app unless
--base-url is supplied, opens each recipe through the production Inputs route,
captures the rendered runtime tuple, and reports which recipes satisfy the
expected family/action/CTA/apply contract.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _load_browser_state,
    _query,
    _start_streamlit,
    _wait_for_http,
)
from tools.verification.runtime_outcome_coverage_investigation import (  # noqa: E402
    _capture_page_payload,
    _tuple_from_capture,
)


AUDIT_DIR = ROOT / "artifacts" / "audits"
SCREENSHOT_DIR = ROOT / "artifacts" / "runtime_screenshots"

DEFAULT_COMBINED_RECIPES = (
    "C_combined_underdesign",
    "R3A_M300_V400",
    "R3B_M600_V600",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_01",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_02",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_03",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_04",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_05",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_06",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_07",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_08",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_09",
    "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_10",
)


def _stamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat().replace(":", "-")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _certifiable_action(row: dict[str, Any], accepted_families: set[str]) -> bool:
    return bool(
        str(row.get("family_code") or "") in accepted_families
        and row.get("outcome_code") == "ACTION"
        and row.get("cta_state") == "ENABLED"
        and row.get("apply_state") == "ENABLED"
        and row.get("publication_builder") == "FinalDesignGuidePublication"
        and row.get("display_builder") == "FinalDesignGuideDisplay"
        and row.get("publication_authority_hash")
        and (row.get("visible") or {}).get("final_card_ready")
        and not row.get("fallback_path_used")
        and not row.get("compatibility_path_used")
    )


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Family Action Recipe Probe",
        "",
        f"Status: `{payload['status']}`",
        "",
        f"- Expected family: `{payload['expected_family']}`",
        f"- Recipes probed: `{len(payload.get('rows') or [])}`",
        f"- Certifiable ACTION recipes: `{len(payload.get('certifiable_recipes') or [])}`",
        "",
        "| Recipe | Family | Outcome | CTA | Apply | Card | Publication | Certifiable |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows") or []:
        tup = dict(row.get("tuple") or {})
        lines.append(
            "|"
            + "|".join(
                str(value).replace("|", "/")
                for value in (
                    row.get("recipe"),
                    tup.get("family_code") or "",
                    tup.get("outcome_code") or "",
                    tup.get("cta_state") or "",
                    tup.get("apply_state") or "",
                    bool((tup.get("visible") or {}).get("final_card_ready")),
                    bool(tup.get("publication_authority_hash")),
                    row.get("certifiable"),
                )
            )
            + "|"
        )
    if payload.get("certifiable_recipes"):
        lines.extend(["", "## Certifiable Recipes", "", "```json", json.dumps(payload["certifiable_recipes"], indent=2), "```"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", default="COMBINED_BENDING_SHEAR_FAIL")
    parser.add_argument("--accepted-family", action="append", default=[])
    parser.add_argument("--recipe", action="append", default=[])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=9340)
    parser.add_argument("--timeout-s", type=float, default=35.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    stamp = _stamp()
    expected_family = str(args.family)
    accepted_families = {expected_family, *[str(item) for item in args.accepted_family]}
    recipes = tuple(args.recipe or DEFAULT_COMBINED_RECIPES)
    rows: list[dict[str, Any]] = []
    process: subprocess.Popen | None = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    try:
        if args.base_url:
            _wait_for_http(base_url)
        else:
            process = _start_streamlit(args.port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            try:
                for recipe in recipes:
                    context = browser.new_context(viewport={"width": 1600, "height": 1100})
                    page = context.new_page()
                    page.set_default_timeout(20_000)
                    target_url = _query(
                        base_url,
                        {"page": "inputs", "browser_recipe": recipe, "browser_test_mode": "1", "cid": f"probe_{recipe}"},
                    )
                    capture_error = ""
                    tuple_row: dict[str, Any] = {}
                    screenshot = SCREENSHOT_DIR / f"probe_{expected_family}_{recipe}_{stamp}.png"
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
                        try:
                            page.wait_for_selector(
                                "[data-testid='design-guide-card'], [data-outcome-state], [data-publication-hash], .fast-guidance-item",
                                timeout=int(max(5.0, args.timeout_s) * 1000),
                            )
                        except PlaywrightTimeoutError:
                            pass
                        page.wait_for_timeout(1_000)
                        payload = _capture_page_payload(page)
                        state = _load_browser_state(page, fallback_timeout_ms=5_000)
                        tuple_row = _tuple_from_capture(
                            scenario_id=f"probe_{recipe}",
                            recipe_id=str(recipe),
                            payload=payload,
                            state=state,
                        )
                        tuple_row["browser_recipe_probe"] = {
                            "requested_browser_recipe": recipe,
                            "applied_browser_recipe": state.get("browser_recipe"),
                            "browser_recipe_error": state.get("browser_recipe_error"),
                            "browser_recipe_kind": state.get("browser_recipe_kind"),
                        }
                        screenshot.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(screenshot), full_page=True)
                    except Exception as exc:
                        capture_error = f"{type(exc).__name__}: {exc}"
                    finally:
                        context.close()
                    certifiable = _certifiable_action(tuple_row, accepted_families)
                    rows.append(
                        {
                            "recipe": recipe,
                            "tuple": tuple_row,
                            "certifiable": certifiable,
                            "capture_error": capture_error,
                            "screenshot": str(screenshot.relative_to(ROOT)) if screenshot.exists() else "",
                        }
                    )
            finally:
                browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    certifiable = [row["recipe"] for row in rows if row.get("certifiable")]
    payload = {
        "status": "PASS" if certifiable else "FAIL",
        "generated_at": stamp,
        "expected_family": expected_family,
        "accepted_families": sorted(accepted_families),
        "certifiable_recipes": certifiable,
        "rows": rows,
    }
    json_path = AUDIT_DIR / f"family_action_recipe_probe_{expected_family}_{stamp}.json"
    md_path = AUDIT_DIR / f"family_action_recipe_probe_{expected_family}_{stamp}.md"
    _write_json(json_path, payload)
    _write_text(md_path, _markdown(payload))
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path), "certifiable_recipes": certifiable}, indent=2))
    return 0 if certifiable else 1


if __name__ == "__main__":
    raise SystemExit(main())
