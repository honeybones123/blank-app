from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def wait_http(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url) as response:
                if response.status < 500:
                    return
        except Exception:
            pass
        time.sleep(0.05)
    raise RuntimeError("Streamlit server did not become ready")


def sample_height(page, selector: str, duration_ms: int = 450) -> list[dict]:
    return page.locator(selector).first.evaluate(
        """(el, duration) => new Promise(resolve => {
          const out=[]; const t0=performance.now(); let frames=0;
          function snap(){ const r=el.getBoundingClientRect(); out.push({t:+(performance.now()-t0).toFixed(2), height:+r.height.toFixed(2)}); }
          snap();
          function frame(){ frames++; snap(); if (performance.now()-t0 < duration && frames < 50) requestAnimationFrame(frame); else resolve(out); }
          requestAnimationFrame(frame);
        })""",
        duration_ms,
    )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    port = 9472
    app = root / "tools" / "verification" / "helpers" / "mounted_card_shell_demo.py"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app), "--server.headless=true", "--server.fileWatcherType=none", f"--server.port={port}"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait_http(base)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            page.goto(base, wait_until="domcontentloaded", timeout=60_000)
            page.get_by_role("heading", name="Mounted card shell probe").wait_for(timeout=30_000)
            page.wait_for_timeout(500)

            shell = '.st-key-probe_section_material__shell'
            body = '.st-key-probe_section_material__body'
            toggle = page.get_by_role("button", name="Section & material", exact=False)
            width = page.get_by_label("Width")

            closed_display = page.locator(body).evaluate("el => getComputedStyle(el).display")
            closed_height = page.locator(shell).evaluate("el => el.getBoundingClientRect().height")

            toggle.click()
            page.locator(body).wait_for(state="visible", timeout=10_000)
            opened_at = time.perf_counter()
            samples = sample_height(page, shell)
            open_height = page.locator(shell).evaluate("el => el.getBoundingClientRect().height")
            open_display = page.locator(body).evaluate("el => getComputedStyle(el).display")

            width.fill("425")
            width.press("Enter")
            page.wait_for_timeout(300)
            value_after_edit = width.input_value()

            toggle.click()
            page.wait_for_timeout(150)
            closed_again_display = page.locator(body).evaluate("el => getComputedStyle(el).display")
            toggle.click()
            page.locator(body).wait_for(state="visible", timeout=10_000)
            value_after_reopen = page.get_by_label("Width").input_value()

            distinct=[]
            for row in samples:
                h=row["height"]
                if not distinct or abs(h-distinct[-1]) > 0.5:
                    distinct.append(h)

            result = {
                "closed_display": closed_display,
                "open_display": open_display,
                "closed_again_display": closed_again_display,
                "closed_height": closed_height,
                "open_height": open_height,
                "height_steps_after_open": distinct,
                "height_step_count": len(distinct),
                "value_after_edit": value_after_edit,
                "value_after_reopen": value_after_reopen,
                "open_probe_started": opened_at,
            }
            print(json.dumps(result, indent=2))

            if closed_display != "none":
                raise AssertionError(f"closed body display was {closed_display!r}")
            if open_display == "none":
                raise AssertionError("body did not become visible")
            if closed_again_display != "none":
                raise AssertionError("body did not close")
            if value_after_edit != "425" or value_after_reopen != "425":
                raise AssertionError("widget value did not persist across close/reopen")
            if len(distinct) > 2:
                raise AssertionError(f"card still animates through {len(distinct)} height steps: {distinct}")
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
