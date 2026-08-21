"""Browser regression for the live Bending diagram and material lesson.

Run against an already-started app.  The verifier measures the loading-to-live
geometry transition, rejects blank Plotly hosts, exercises every diagram/state
tab, and confirms the lazy material lesson mounts its live Plotly chart.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from playwright.async_api import async_playwright


VIEWPORTS = {
    "desktop": {"width": 1365, "height": 768},
    "narrow": {"width": 768, "height": 900},
}


async def _plot_state(page) -> dict:
    return await page.evaluate(
        """
        () => {
          const plot = document.querySelector(
            '.js-plotly-plot[data-sb-preloaded-plotly-state]'
          );
          if (!plot) return {mounted: false};
          const visible = (node) => {
            const css = getComputedStyle(node);
            return css.display !== 'none'
              && css.visibility !== 'hidden'
              && Number(css.opacity || 1) > 0;
          };
          const traces = [...plot.querySelectorAll('.scatterlayer .trace')];
          const shapes = [...plot.querySelectorAll('g.shapelayer .shape-group')];
          const annotations = [...plot.querySelectorAll('.annotation')];
          const box = plot.getBoundingClientRect();
          return {
            mounted: true,
            width: box.width,
            height: box.height,
            state: plot.getAttribute('data-sb-preloaded-plotly-state'),
            ready: plot.getAttribute('data-sb-plotly-visibility-ready'),
            visible_traces: traces.filter(visible).length,
            visible_shapes: shapes.filter(visible).length,
            visible_annotations: annotations.filter(visible).length,
            visible_trace_states: traces.filter(visible).map(
              node => node.getAttribute('data-sb-plotly-state')
            ),
          };
        }
        """
    )


async def _inputs_heading_y(page) -> float:
    return await page.get_by_text("Inputs used for this check", exact=True).evaluate(
        "node => node.getBoundingClientRect().top"
    )


async def _capture_viewport(base_url: str, output: Path, name: str, viewport: dict) -> dict:
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
        except Exception:
            browser = await playwright.chromium.launch(headless=True, channel="msedge")
        context = await browser.new_context(viewport=viewport)
        page = await context.new_page()
        url = f"{base_url.rstrip('/')}?page=bending&cid=bending-regression-{uuid4()}"
        await page.goto(url, wait_until="domcontentloaded")
        shell = page.locator("[data-bending-diagram-shell]")
        await shell.wait_for(state="visible", timeout=30_000)
        shell_box = await shell.bounding_box()
        loading_inputs_y = await _inputs_heading_y(page)
        await page.screenshot(path=output / f"{name}-loading.png", full_page=True)

        await page.locator("[data-bending-diagram-ready]").wait_for(
            state="attached", timeout=45_000
        )
        await page.locator(
            '.js-plotly-plot[data-sb-plotly-visibility-ready="1"]'
        ).wait_for(state="visible", timeout=15_000)
        loaded_inputs_y = await _inputs_heading_y(page)
        first_plot = await _plot_state(page)
        if (
            first_plot.get("height", 0) > 100
            and not (
                first_plot.get("visible_traces", 0)
                or first_plot.get("visible_shapes", 0)
                or first_plot.get("visible_annotations", 0)
            )
        ):
            raise AssertionError("Bending Plotly host is mounted but blank")

        state_results = []
        for label, expected in (
            ("ULS", "0"),
            ("SLS (cracked)", "1"),
            ("Uncracked", "2"),
            ("ULS", "0"),
        ):
            await page.get_by_text(label, exact=True).click()
            await page.wait_for_timeout(250)
            state = await _plot_state(page)
            if state.get("state") != expected or not state.get("visible_traces"):
                raise AssertionError(f"{label} did not expose its live diagram")
            if set(state["visible_trace_states"]) != {expected}:
                raise AssertionError(f"{label} visibly overlaps another state")
            state_results.append({"label": label, **state})

        tab_results = []
        for label in ("Side view", "Bending moment", "Section & stress-strain models"):
            await page.get_by_role("tab", name=label).click()
            await page.wait_for_timeout(900)
            panel = page.locator('[role="tabpanel"]')
            plot = panel.locator(".js-plotly-plot").first
            box = await plot.bounding_box()
            if not box or box["height"] <= 100:
                raise AssertionError(f"{label} did not mount a visible Plotly diagram")
            tab_results.append({"label": label, "plot": box})

        await page.get_by_text(
            "ℹ️ From strain to stress to internal force", exact=True
        ).click()
        await page.wait_for_timeout(900)
        lesson = page.locator('[data-testid="stExpanderDetails"]:has(.sb-material-major-one)')
        await lesson.wait_for(state="visible", timeout=10_000)
        material_plot = lesson.locator(".js-plotly-plot")
        material_box = await material_plot.bounding_box()
        material_traces = await material_plot.locator(".scatterlayer .trace").count()
        if not material_box or material_box["height"] <= 100 or material_traces <= 0:
            raise AssertionError("Material lesson live Plotly chart did not mount")
        await page.screenshot(path=output / f"{name}-loaded.png", full_page=True)

        delta = loaded_inputs_y - loading_inputs_y
        if abs(delta) > 2:
            raise AssertionError(f"loading-to-live layout movement was {delta:.3f}px")
        result = {
            "viewport": viewport,
            "shell": shell_box,
            "loading_inputs_y": loading_inputs_y,
            "loaded_inputs_y": loaded_inputs_y,
            "layout_delta_px": delta,
            "first_plot": first_plot,
            "states": state_results,
            "tabs": tab_results,
            "material_plot": {"box": material_box, "traces": material_traces},
        }
        await context.close()
        await browser.close()
        return result


async def capture(base_url: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    return {
        name: await _capture_viewport(base_url, output, name, viewport)
        for name, viewport in VIEWPORTS.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8506/")
    parser.add_argument("--output", type=Path, default=Path("work/bending-diagram-regression"))
    args = parser.parse_args()
    result = asyncio.run(capture(args.base_url, args.output))
    result_path = args.output / "result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result_path)


if __name__ == "__main__":
    main()
