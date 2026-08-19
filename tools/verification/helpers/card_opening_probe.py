"""Temporary browser probe for production input-card and calc-box opening behaviour."""
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


def _first_numeric_widget(body):
    widget = body.locator('input[type="number"]').first
    if widget.count() == 0:
        widget = body.locator('input').first
    return widget


def sample_mounted_input_shell(page) -> dict:
    shell_sel = '[class*="st-key-compact_check_inputs_bending_"][class*="__shell"]'
    body_sel = '[class*="st-key-compact_check_inputs_bending_"][class*="__body"]'

    shell = page.locator(shell_sel).first
    shell.wait_for(state="attached", timeout=30_000)
    button = shell.locator('div[data-testid="stButton"] > button').first
    body = page.locator(body_sel).first
    body.wait_for(state="attached", timeout=30_000)

    if body.evaluate("el => getComputedStyle(el).display !== 'none'"):
        button.click()
        page.wait_for_function(
            "el => getComputedStyle(el).display === 'none'",
            arg=body.element_handle(),
            timeout=10_000,
        )

    samples = page.evaluate(
        """({shell, body, button}) => new Promise(resolve => {
          const out=[];
          const t0=performance.now();
          let frames=0;
          function snap(tag){
            const sr=shell.getBoundingClientRect();
            const br=body.getBoundingClientRect();
            const bs=getComputedStyle(body);
            out.push({
              t:+(performance.now()-t0).toFixed(2), tag,
              shellHeight:+sr.height.toFixed(2),
              bodyHeight:+br.height.toFixed(2),
              bodyDisplay:bs.display,
              bodyVisibility:bs.visibility,
            });
          }
          snap('before');
          button.click();
          snap('after_click');
          function frame(){
            frames++;
            snap('raf');
            if (performance.now()-t0 < 650 && frames < 60) requestAnimationFrame(frame);
            else resolve(out);
          }
          requestAnimationFrame(frame);
        })""",
        {"shell": shell.element_handle(), "body": body.element_handle(), "button": button.element_handle()},
    )

    visible_samples = [x for x in samples if x["bodyDisplay"] != "none"]
    heights = [x["bodyHeight"] for x in visible_samples]
    distinct = []
    for h in heights:
        if not distinct or abs(h - distinct[-1]) > 0.5:
            distinct.append(h)

    body = page.locator(body_sel).first
    page.wait_for_function(
        "el => getComputedStyle(el).display !== 'none'",
        arg=body.element_handle(),
        timeout=10_000,
    )

    # Use the real production widget and prove that whatever value the app
    # accepts after an edit remains identical after shell-only close/reopen.
    widget = _first_numeric_widget(body)
    widget.wait_for(state="visible", timeout=10_000)
    original = widget.input_value()

    # ArrowUp respects the widget's configured step/min/max better than forcing
    # an arbitrary engineering value such as 425 into whichever field happens
    # to be first on the page.
    widget.focus()
    widget.press("ArrowUp")
    widget.press("Enter")
    page.wait_for_timeout(500)

    shell = page.locator(shell_sel).first
    button = shell.locator('div[data-testid="stButton"] > button').first
    body = page.locator(body_sel).first
    widget = _first_numeric_widget(body)
    value_after_edit = widget.input_value()
    edit_committed = value_after_edit != original

    button.click()
    body = page.locator(body_sel).first
    page.wait_for_function(
        "el => getComputedStyle(el).display === 'none'",
        arg=body.element_handle(),
        timeout=10_000,
    )

    shell = page.locator(shell_sel).first
    button = shell.locator('div[data-testid="stButton"] > button').first
    button.click()
    body = page.locator(body_sel).first
    page.wait_for_function(
        "el => getComputedStyle(el).display !== 'none'",
        arg=body.element_handle(),
        timeout=10_000,
    )

    widget = _first_numeric_widget(body)
    value_after_reopen = widget.input_value()

    return {
        "samples": samples,
        "distinct_visible_body_height_steps": distinct,
        "height_step_count": len(distinct),
        "original_widget_value": original,
        "value_after_edit": value_after_edit,
        "value_after_reopen": value_after_reopen,
        "edit_committed": edit_committed,
        "state_persisted": edit_committed and value_after_reopen == value_after_edit,
        "one_step_open": len(distinct) <= 1,
    }


def sample_calc_expander(page) -> dict:
    details = page.locator(
        'div[data-testid="stVerticalBlock"]:has([data-calc-uid]) '
        'div[data-testid="stExpander"] > details'
    ).first
    details.wait_for(state="attached", timeout=30_000)
    summary = details.locator("summary").first
    body = details.locator('[data-testid="stExpanderDetails"]').first
    if details.evaluate("el => el.open"):
        summary.click()
        page.wait_for_timeout(80)
    samples = details.evaluate(
        """el => new Promise(resolve => {
          const summary=el.querySelector('summary');
          const body=el.querySelector('[data-testid="stExpanderDetails"]');
          const out=[]; const t0=performance.now(); let frames=0;
          function snap(tag){
            const r=el.getBoundingClientRect();
            const br=body ? body.getBoundingClientRect() : {height:null};
            out.push({t:+(performance.now()-t0).toFixed(2),tag,open:el.open,height:+r.height.toFixed(2),bodyHeight:br.height===null?null:+br.height.toFixed(2)});
          }
          snap('before'); summary.click(); snap('after_click');
          function frame(){frames++;snap('raf');if(performance.now()-t0<650&&frames<60)requestAnimationFrame(frame);else resolve(out)}
          requestAnimationFrame(frame);
        })"""
    )
    return {"samples": samples}


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

            production_input = sample_mounted_input_shell(page)
            calc_box = sample_calc_expander(page)
            result = {"production_input_card": production_input, "calc_box": calc_box}

            print(json.dumps(result, indent=2))
            out = root / "artifacts" / "card-opening-probe.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")

            if not production_input["one_step_open"]:
                raise RuntimeError(
                    f"Mounted production input card opened in {production_input['height_step_count']} visible height steps"
                )
            if not production_input["state_persisted"]:
                raise RuntimeError(
                    "Mounted production input card did not preserve an accepted widget edit through close/reopen"
                )

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
