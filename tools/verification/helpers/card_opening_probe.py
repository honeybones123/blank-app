"""Temporary browser probe for calc/input-card opening behaviour."""
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
            with urlopen(url) as r:
                if r.status < 500:
                    return
        except Exception:
            pass
        time.sleep(0.05)
    raise RuntimeError("Streamlit server did not become ready")


def sample_opening(page, selector: str, label: str) -> dict:
    details = page.locator(selector).first
    details.wait_for(state="attached", timeout=30_000)
    summary = details.locator("summary").first
    body = details.locator('[data-testid="stExpanderDetails"]').first
    if body.count() == 0:
        body = details.locator(":scope > div").first

    if details.evaluate("el => el.open"):
        summary.click()
        page.wait_for_timeout(80)

    style = details.evaluate(
        """el => {
          const s = getComputedStyle(el);
          const summary = el.querySelector('summary');
          const body = el.querySelector('[data-testid="stExpanderDetails"]') || el.querySelector(':scope > div');
          const ss = summary ? getComputedStyle(summary) : null;
          const bs = body ? getComputedStyle(body) : null;
          const pick = x => x ? ({
            transitionProperty:x.transitionProperty,
            transitionDuration:x.transitionDuration,
            transitionTimingFunction:x.transitionTimingFunction,
            animationName:x.animationName,
            animationDuration:x.animationDuration,
            overflow:x.overflow,
            display:x.display,
          }) : null;
          return {details:pick(s), summary:pick(ss), body:pick(bs)};
        }"""
    )

    samples = details.evaluate(
        """el => new Promise(resolve => {
          const summary = el.querySelector('summary');
          const body = el.querySelector('[data-testid="stExpanderDetails"]') || el.querySelector(':scope > div');
          const out=[];
          const t0=performance.now();
          let frames=0;
          function snap(tag){
            const r=el.getBoundingClientRect();
            const br=body ? body.getBoundingClientRect() : {height:null};
            out.push({t:+(performance.now()-t0).toFixed(2), tag, open:el.open, height:+r.height.toFixed(2), bodyHeight:br.height===null?null:+br.height.toFixed(2)});
          }
          snap('before');
          summary.click();
          snap('after_click');
          function frame(){
            frames++;
            snap('raf');
            if (performance.now()-t0 < 650 && frames < 60) requestAnimationFrame(frame);
            else resolve(out);
          }
          requestAnimationFrame(frame);
        })"""
    )
    heights = [x["height"] for x in samples]
    distinct = []
    for h in heights:
        if not distinct or abs(h - distinct[-1]) > 0.5:
            distinct.append(h)
    return {
        "label": label,
        "styles": style,
        "samples": samples,
        "distinct_height_steps": distinct,
        "height_step_count": len(distinct),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    port = 9471
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless=true", "--server.fileWatcherType=none", f"--server.port={port}"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait_http(base)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{base}/?page=bending&fresh=1&cid=card-probe", wait_until="domcontentloaded", timeout=60_000)
            page.get_by_role("heading", name="Bending capacity", exact=False).first.wait_for(state="visible", timeout=60_000)
            page.wait_for_timeout(800)

            input_selector = '[class*="st-key-compact_check_inputs_bending_"] div[data-testid="stExpander"] > details'
            input_result = sample_opening(page, input_selector, "input_card")

            calc_selector = 'div[data-testid="stVerticalBlock"]:has([data-calc-uid]) div[data-testid="stExpander"] > details'
            calc_result = sample_opening(page, calc_selector, "calc_box")

            result = {"input_card": input_result, "calc_box": calc_result}
            print(json.dumps(result, indent=2))
            out = root / "artifacts" / "card-opening-probe.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
