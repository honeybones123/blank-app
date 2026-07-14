"""Live regression for shear-cleanup ACTION cards rendering an Apply button.

This intentionally checks the browser-visible Design Guide path. The bug this
guards against is an ACTION shear cleanup publication whose text says the
cleanup is executable, while the Streamlit Apply button is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

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


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "R5A_M0_V150"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_cleanup_apply_button_visibility_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_shear_cleanup_apply_button_visibility_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Shear Cleanup Apply Button Visibility",
                "",
                f"Result: `{snapshot['result']}`",
                f"Recipe: `{snapshot['recipe']}`",
                f"URL: `{snapshot['url']}`",
                "",
                "## Checks",
                "",
                *[f"- `{name}`: `{value}`" for name, value in snapshot["checks"].items()],
                "",
                "## Visible Apply Buttons",
                "",
                *(
                    [
                        f"- `{button.get('text')}` enabled=`{button.get('enabled')}`"
                        for button in snapshot["visible_apply_buttons"]
                    ]
                    or ["- none"]
                ),
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, md_path


def _visible_buttons(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('button')).map((button, index) => ({
            index,
            text: (button.innerText || button.textContent || '').trim(),
            enabled: !button.disabled,
            visible: !!(button.offsetWidth || button.offsetHeight),
            testid: button.getAttribute('data-testid'),
            aria: button.getAttribute('aria-label')
        }))"""
    )


def _body_text(page) -> str:
    return page.evaluate("() => document.body ? document.body.innerText : ''")


def _wait_for_body_terms(page, terms: tuple[str, ...], *, timeout_s: float = 30.0) -> str:
    deadline = time.time() + timeout_s
    latest = ""
    while time.time() < deadline:
        latest = _body_text(page)
        if all(term in latest for term in terms):
            return latest
        time.sleep(0.4)
    missing = [term for term in terms if term not in latest]
    raise RuntimeError(f"Timed out waiting for page terms: {missing}")


def _run_live_check(base_url: str, recipe: str, *, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        url = _query(
            base_url,
            {
                "page": "inputs",
                "browser_recipe": recipe,
                "browser_test_mode": "1",
            },
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.get_by_label("Browser state").wait_for(state="attached", timeout=30_000)
        body = _wait_for_body_terms(
            page,
            (
                "Shear cleanup - best safe one-click reduction",
                "ACTION",
                "Apply: Shear cleanup",
            ),
            timeout_s=30.0,
        )

        buttons = _visible_buttons(page)
        visible_apply_buttons = [
            button
            for button in buttons
            if button.get("visible")
            and str(button.get("text") or "").strip().lower().startswith("apply:")
        ]
        enabled_apply_buttons = [
            button for button in visible_apply_buttons if bool(button.get("enabled"))
        ]
        browser_state = _load_browser_state(page)
        final_hashes = dict(browser_state.get("final_publication_hashes") or {})

        context.close()
        browser.close()

    checks = {
        "shear_cleanup_action_card_visible": "Shear cleanup - best safe one-click reduction" in body
        and "ACTION" in body,
        "card_declares_cleanup_executable": (
            "executable" in body
            or "one-click" in body
            or "Apply: Shear cleanup" in body
        ),
        "card_declares_expected_util": (
            "Expected util:" in body
            or "preview utilisation" in body
            or "utilisation =" in body
        ),
        "enabled_apply_button_visible": len(enabled_apply_buttons) == 1,
        "no_duplicate_visible_apply_buttons": len(visible_apply_buttons) == 1,
        "apply_button_is_shear_cleanup": bool(
            enabled_apply_buttons
            and "shear" in str(enabled_apply_buttons[0].get("text") or "").lower()
        ),
        "publication_hash_present": bool(final_hashes.get("publication_hash")),
        "cta_hash_present": bool(final_hashes.get("cta_hash")),
        "display_hash_present": bool(final_hashes.get("display_hash")),
    }
    failures = [name for name, value in checks.items() if not value]
    return {
        "schema": "design_guide_shear_cleanup_apply_button_visibility.v1",
        "result": "PASS" if not failures else "FAIL",
        "recipe": recipe,
        "url": url,
        "checks": checks,
        "failures": failures,
        "visible_apply_buttons": visible_apply_buttons,
        "enabled_apply_buttons": enabled_apply_buttons,
        "final_publication_hashes": final_hashes,
        "product_behavior_changed": False,
        "body_excerpt": body[body.find("Design Guide") : body.find("Design Actions")]
        if "Design Guide" in body and "Design Actions" in body
        else body[:2000],
    }


def _run_static_check() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    render_slice = source.split("def _render_guidance_secondary_items", 1)[-1].split(
        "\ndef _resolve_recommendation_updates",
        1,
    )[0]
    checks = {
        "primary_button_visibility_uses_button_contract_authority": (
            "_pres_show_apply = bool(_design_guide_button_contract_enabled(button_contract))"
            in render_slice
        ),
        "primary_button_renders_when_action_type_and_cta_enabled": (
            "if item.get(\"action_type\") and _pres_show_apply:" in render_slice
            and "guidance_pressed = st.button(" in render_slice
            and 'key="apply_design_guide"' in render_slice
        ),
        "primary_button_records_actual_render_probe": (
            '"marker": "primary_design_guide_apply_button_rendered"' in render_slice
            and '"render_button_contract_enabled": True' in render_slice
        ),
        "final_publication_cta_fallback_branch_present": (
            "not _primary_apply_button_rendered" in render_slice
            and "_design_guide_button_contract_enabled(button_contract)" in render_slice
            and '"_source": "final_publication_cta_contract_render_fallback"' in render_slice
        ),
        "fallback_branch_requires_updates_and_non_terminal_cta": (
            "dict(button_contract.get(\"updates\") or {})" in render_slice
            and "not _publication_cta_terminal_no_action" in render_slice
        ),
        "fallback_button_has_unique_key": (
            'key="apply_design_guide_final_publication_cta_fallback"' in render_slice
        ),
        "fallback_button_records_actual_render_probe": (
            '"marker": "primary_final_publication_cta_render_fallback"' in render_slice
            and '"rendered_primary_apply_button_from_final_publication_cta_fallback"' in render_slice
        ),
        "shear_overdesign_best_safe_contract_not_blocked_by_final_floor": (
            '_render_family_owner != "SHEAR_OVERDESIGN_GOVERNS"' in render_slice
            and "_best_safe_cleanup_action_proof_allows_executable_cta" in render_slice
        ),
    }
    failures = [name for name, value in checks.items() if not value]
    return {
        "schema": "design_guide_shear_cleanup_apply_button_visibility.v1",
        "result": "PASS" if not failures else "FAIL",
        "recipe": "static_render_invariant",
        "url": None,
        "checks": checks,
        "failures": failures,
        "visible_apply_buttons": [],
        "enabled_apply_buttons": [],
        "final_publication_hashes": {},
        "body_excerpt": "",
        "product_behavior_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None, help="Use an existing local app.")
    parser.add_argument("--port", type=int, default=8536, help="Port to use when starting Streamlit.")
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run a browser recipe check in addition to source invariant checks.",
    )
    args = parser.parse_args(argv)

    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    try:
        if args.live:
            if args.base_url:
                _wait_for_http(base_url)
            else:
                process = _start_streamlit(args.port)
            snapshot = _run_live_check(base_url, args.recipe, headed=args.headed)
        else:
            snapshot = _run_static_check()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    json_path, md_path = _write_outputs(snapshot)
    print(f"Design Guide shear cleanup apply button visibility {snapshot['result']}")
    print(f"JSON: {json_path}")
    print(f"Report: {md_path}")
    if snapshot["result"] != "PASS":
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
