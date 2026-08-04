"""Prove repeated Inputs edits commit one sibling-fragment transaction."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _terminate_process_tree,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
PROBE_SELECTOR = "textarea[aria-label='Inputs workspace state']"


def _read_probe(page) -> dict[str, Any]:
    return json.loads(page.locator(PROBE_SELECTOR).input_value())


def _wait_for_revision(page, revision: int, timeout_ms: int) -> None:
    page.wait_for_function(
        """([selector, revision]) => {
          const element = document.querySelector(selector);
          if (!element) return false;
          try {
            return JSON.parse(element.value).workspace_revision > revision;
          } catch (_) {
            return false;
          }
        }""",
        arg=[PROBE_SELECTOR, revision],
        timeout=timeout_ms,
    )


def _run(base_url: str, *, timeout_ms: int) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(
            _query(
                base_url,
                {
                    "page": "inputs",
                    "browser_test_mode": "1",
                    "browser_recipe": "AB_IN_TARGET_BAND",
                },
            ),
            wait_until="domcontentloaded",
            timeout=90_000,
        )
        probe = page.locator(PROBE_SELECTOR)
        probe.wait_for(state="attached", timeout=timeout_ms)
        initial = _read_probe(page)
        width = page.get_by_label("Width b (mm)")
        depth = page.get_by_label("Depth D (mm)")
        edits: list[dict[str, Any]] = []
        for value in ("310", "320", "300", "310"):
            before = _read_probe(page)
            started = time.perf_counter()
            width.fill(value)
            width.press("Enter")
            depth.click()
            _wait_for_revision(
                page,
                int(before["workspace_revision"]),
                timeout_ms,
            )
            after = _read_probe(page)
            edits.append(
                {
                    "value": value,
                    "elapsed_ms": round(
                        (time.perf_counter() - started) * 1000,
                        1,
                    ),
                    "before": before,
                    "after": after,
                }
            )
        exception_count = page.locator(
            "[data-testid='stException']"
        ).count()
        browser.close()

    failures: list[str] = []
    for index, edit in enumerate(edits, start=1):
        before = edit["before"]
        after = edit["after"]
        if int(after["workspace_revision"]) != (
            int(before["workspace_revision"]) + 1
        ):
            failures.append(f"edit_{index}_revision_not_incremented_once")
        if int(after["workspace_fragment_render_count"]) != (
            int(before["workspace_fragment_render_count"]) + 1
        ):
            failures.append(
                f"edit_{index}_workspace_transaction_not_incremented_once"
            )
        if int(after["page_shell_render_count"]) != (
            int(before["page_shell_render_count"]) + 1
        ):
            failures.append(f"edit_{index}_app_commit_not_exactly_once")
        if int(after["last_rendered_revision"]) != int(
            after["workspace_revision"]
        ):
            failures.append(f"edit_{index}_revision_not_rendered")
        fragment_modes = dict(after.get("fragment_modes") or {})
        for fragment_name in (
            "summary",
            "calculation",
            "design_guide",
            "input",
            "diagram_2d",
        ):
            if fragment_modes.get(fragment_name) != "fragment":
                failures.append(
                    f"edit_{index}_{fragment_name}_fragment_not_enabled"
                )
        if fragment_modes.get("diagram_3d") not in (None, "fragment"):
            failures.append(
                f"edit_{index}_diagram_3d_fragment_invalid_mode"
            )
        browser_overlay = dict(after.get("browser_state_overlay") or {})
        authoritative_probe = dict(
            browser_overlay.get("authoritative_result_probe") or {}
        )
        if not authoritative_probe.get("stored_engineering_hash"):
            failures.append(
                f"edit_{index}_authoritative_engineering_hash_missing"
            )
        summary_probe = dict(
            browser_overlay.get("summary_state_probe") or {}
        )
        try:
            summary_width = float(summary_probe.get("b"))
        except (TypeError, ValueError):
            summary_width = None
        if summary_width != float(edit["value"]):
            failures.append(
                f"edit_{index}_summary_not_committed_width"
            )
    if exception_count:
        failures.append(f"streamlit_exception_count:{exception_count}")

    return {
        "schema": "inputs_workspace_repeated_edit_browser.v1",
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now().astimezone().isoformat(),
        "initial": initial,
        "edits": edits,
        "exception_count": exception_count,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9404)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    args = parser.parse_args(argv)
    process = _start_streamlit(args.port)
    try:
        payload = _run(
            f"http://127.0.0.1:{args.port}",
            timeout_ms=int(args.timeout_s * 1000),
        )
    finally:
        _terminate_process_tree(process)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact = (
        ARTIFACT_DIR
        / f"inputs_workspace_repeated_edit_browser_{stamp}.json"
    )
    artifact.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"{payload['status']}: repeated edits committed one authoritative "
        f"sibling-fragment transaction; "
        f"artifact={artifact}"
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
