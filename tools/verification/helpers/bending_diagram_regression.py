"""Browser regression for Bending loading and diagram interactions.

Run against an already-started app. The probe exercises the real Streamlit
page, including cold-shell scrolling, whole-diagram state switching, native
diagram tabs, material teaching content, geometry stability, and repeated
interaction stress.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from uuid import uuid4

from playwright.async_api import Page, async_playwright


VIEWPORTS = {
    "desktop": {"width": 1365, "height": 768},
    "narrow": {"width": 768, "height": 900},
}
STATE_KEYS = {
    "ULS": "uls",
    "SLS (cracked)": "sls-cracked",
    "Uncracked": "uncracked",
}
HOST_KEYS = {
    "uls": "uls",
    "sls-cracked": "sls_cracked",
    "uncracked": "uncracked",
}


async def _scroll_top(page: Page) -> float:
    return float(
        await page.evaluate(
            "() => document.querySelector('section.stMain')?.scrollTop || 0"
        )
    )


async def _document_y(locator) -> float:
    return float(
        await locator.evaluate(
            "node => node.getBoundingClientRect().top + "
            "(document.querySelector('section.stMain')?.scrollTop || 0)"
        )
    )


async def _visible_state(page: Page) -> dict:
    return await page.evaluate(
        """
        () => {
          const state = document.documentElement.getAttribute(
            'data-sb-bending-visible-state'
          );
          const hostKeys = {
            'uls': 'uls',
            'sls-cracked': 'sls_cracked',
            'uncracked': 'uncracked',
          };
          const hosts = Object.entries(hostKeys).map(([key, cssKey]) => {
            const host = document.querySelector(
              '.st-key-bending_state_plot_' + cssKey
            );
            const plot = host?.querySelector('.js-plotly-plot');
            const box = host?.getBoundingClientRect();
            const visible = Boolean(
              host
              && getComputedStyle(host).display !== 'none'
              && box.height > 100
            );
            const traces = plot?.querySelectorAll('.scatterlayer .trace').length || 0;
            const shapes = plot?.querySelectorAll(
              'g.shapelayer .shape-group'
            ).length || 0;
            const annotations = plot?.querySelectorAll('.annotation').length || 0;
            return {
              key,
              mounted: Boolean(plot),
              visible,
              width: box?.width || 0,
              height: box?.height || 0,
              traces,
              shapes,
              annotations,
              complete: traces > 0 && shapes > 0 && annotations > 0,
            };
          });
          return {
            state,
            host_switch_ms: Number(
              document.documentElement.getAttribute(
                'data-sb-last-bending-host-switch-ms'
              ) || 0
            ),
            hosts,
            visible_hosts: hosts.filter(host => host.visible),
          };
        }
        """
    )


async def _assert_state(page: Page, expected: str) -> dict:
    await page.wait_for_function(
        """
        expected => {
          if (document.documentElement.getAttribute(
            'data-sb-bending-visible-state'
          ) !== expected) return false;
          const cssKey = {
            'uls': 'uls',
            'sls-cracked': 'sls_cracked',
            'uncracked': 'uncracked',
          }[expected];
          const host = document.querySelector(
            '.st-key-bending_state_plot_' + cssKey
          );
          const plot = host?.querySelector('.js-plotly-plot');
          return Boolean(
            host
            && getComputedStyle(host).display !== 'none'
            && host.getBoundingClientRect().height > 100
            && plot?.querySelector('.scatterlayer .trace')
            && plot?.querySelector('g.shapelayer .shape-group')
            && plot?.querySelector('.annotation')
          );
        }
        """,
        arg=expected,
        timeout=15_000,
    )
    state = await _visible_state(page)
    visible = state["visible_hosts"]
    if len(visible) != 1 or visible[0]["key"] != expected:
        raise AssertionError(
            f"expected one complete {expected} host, received {visible}"
        )
    if not visible[0]["complete"]:
        raise AssertionError(f"{expected} Plotly host is incomplete: {visible[0]}")
    return state


async def _begin_frame_probe(page: Page, duration_ms: int = 450) -> None:
    await page.evaluate(
        """
        duration => {
          window.__sbBendingFrameProbe = [];
          const started = performance.now();
          const sample = () => {
            const state = document.documentElement.getAttribute(
              'data-sb-bending-visible-state'
            );
            const keys = {
              'uls': 'uls',
              'sls-cracked': 'sls_cracked',
              'uncracked': 'uncracked',
            };
            const visibleHosts = Object.entries(keys).map(([key, cssKey]) => {
              const host = document.querySelector(
                '.st-key-bending_state_plot_' + cssKey
              );
              const plot = host?.querySelector('.js-plotly-plot');
              const traces = plot?.querySelectorAll('.scatterlayer .trace').length || 0;
              const shapes = plot?.querySelectorAll(
                'g.shapelayer .shape-group'
              ).length || 0;
              const annotations = plot?.querySelectorAll('.annotation').length || 0;
              const visible = Boolean(host
                && getComputedStyle(host).display !== 'none'
                && host.getBoundingClientRect().height > 100);
              return {
                key,
                visible,
                complete: traces > 0 && shapes > 0 && annotations > 0,
              };
            }).filter(host => host.visible);
            window.__sbBendingFrameProbe.push({
              t: performance.now() - started,
              state,
              visible: visibleHosts.map(host => host.key),
              incomplete: visibleHosts.filter(host => !host.complete).map(
                host => host.key
              ),
            });
            if (performance.now() - started < duration) {
              requestAnimationFrame(sample);
            }
          };
          requestAnimationFrame(sample);
        }
        """,
        duration_ms,
    )


async def _end_frame_probe(page: Page, duration_ms: int = 450) -> list[dict]:
    await page.wait_for_timeout(duration_ms + 80)
    frames = await page.evaluate("() => window.__sbBendingFrameProbe || []")
    for frame in frames:
        if len(frame["visible"]) != 1:
            raise AssertionError(f"mixed or blank state frame: {frame}")
        if frame["incomplete"]:
            raise AssertionError(f"incomplete visible state host: {frame}")
        if frame["state"] and frame["visible"][0] != frame["state"]:
            raise AssertionError(f"visible diagram does not match state marker: {frame}")
    return frames


async def _begin_cold_paint_probe(page: Page) -> None:
    await page.evaluate(
        """
        () => {
          window.__sbBendingColdPaintProbe = [];
          const started = performance.now();
          let previous = '';
          const sample = () => {
            const state = document.documentElement.getAttribute(
              'data-sb-bending-visible-state'
            ) || 'uls';
            const cssKey = {
              'uls': 'uls',
              'sls-cracked': 'sls_cracked',
              'uncracked': 'uncracked',
            }[state] || 'uls';
            const host = document.querySelector(
              '.st-key-bending_state_plot_' + cssKey
            );
            const plot = host?.querySelector('.js-plotly-plot');
            const shell = document.querySelector('[data-bending-diagram-shell]');
            const shellVisible = Boolean(
              shell
              && getComputedStyle(shell).display !== 'none'
              && shell.getBoundingClientRect().height > 100
            );
            const hostVisible = Boolean(
              host
              && getComputedStyle(host).display !== 'none'
              && host.getBoundingClientRect().height > 100
            );
            const frame = {
              t: performance.now() - started,
              state,
              shell_visible: shellVisible,
              host_visible: hostVisible,
              traces: plot?.querySelectorAll('.scatterlayer .trace').length || 0,
              shapes: plot?.querySelectorAll(
                'g.shapelayer .shape-group'
              ).length || 0,
              annotations: plot?.querySelectorAll('.annotation').length || 0,
            };
            const signature = JSON.stringify({...frame, t: 0});
            if (signature !== previous) {
              window.__sbBendingColdPaintProbe.push(frame);
              previous = signature;
            }
            if (shellVisible && performance.now() - started < 45_000) {
              requestAnimationFrame(sample);
            }
          };
          requestAnimationFrame(sample);
        }
        """
    )


async def _end_cold_paint_probe(page: Page) -> list[dict]:
    await page.wait_for_timeout(80)
    frames = await page.evaluate("() => window.__sbBendingColdPaintProbe || []")
    for frame in frames:
        exposed = frame["host_visible"] and not frame["shell_visible"]
        complete = (
            frame["traces"] > 0
            and frame["shapes"] > 0
            and frame["annotations"] > 0
        )
        if exposed and not complete:
            raise AssertionError(
                f"partial Plotly host escaped the loading shell: {frame}"
            )
    return frames


async def _cold_scroll_probe(page: Page) -> dict:
    shell = page.locator("[data-bending-diagram-shell]")
    await shell.wait_for(state="visible", timeout=30_000)
    await _begin_cold_paint_probe(page)
    shell_box = await shell.bounding_box()
    passive = await shell.evaluate(
        """
        node => {
          const box = node.getBoundingClientRect();
          const centre = document.elementFromPoint(
            box.left + box.width / 2,
            Math.min(innerHeight - 2, Math.max(2, box.top + 20))
          );
          return {
            pointer_events: getComputedStyle(node).pointerEvents,
            centre_is_shell: centre === node || node.contains(centre),
          };
        }
        """
    )
    await page.mouse.move(300, 400)
    samples = [await _scroll_top(page)]
    for delta in (300, 300, -200):
        if await page.locator("[data-bending-diagram-ready]").count():
            raise AssertionError("diagram became ready before cold-shell scroll probe finished")
        await page.mouse.wheel(0, delta)
        await page.wait_for_timeout(60)
        samples.append(await _scroll_top(page))
    await page.wait_for_timeout(1_000)
    settled = await _scroll_top(page)
    samples.append(settled)
    if not (samples[1] > samples[0] and samples[2] > samples[1]):
        raise AssertionError(f"cold shell blocked downward scrolling: {samples}")
    if not samples[3] < samples[2]:
        raise AssertionError(f"cold shell blocked upward scrolling: {samples}")
    if abs(samples[4] - samples[3]) > 4:
        raise AssertionError(f"scroll position was forced after user input: {samples}")
    return {"shell": shell_box, "passive": passive, "scroll_samples": samples}


async def _loaded_region_height(page: Page) -> float:
    return float(
        await page.evaluate(
            """
            () => {
              const frame = document.querySelector(
                '.st-key-bending_diagram_frame'
              );
              return frame?.getBoundingClientRect().height || -1;
            }
            """
        )
    )


async def _exercise_states(page: Page) -> tuple[list[dict], list[dict]]:
    results = []
    frame_results = []
    for label in ("SLS (cracked)", "Uncracked", "ULS"):
        await _begin_frame_probe(page)
        started = time.perf_counter()
        await page.get_by_text(label, exact=True).click(no_wait_after=True)
        state = await _assert_state(page, STATE_KEYS[label])
        latency_ms = (time.perf_counter() - started) * 1_000
        frames = await _end_frame_probe(page)
        results.append({"label": label, "latency_ms": latency_ms, **state})
        frame_results.append({"label": label, "frames": frames})
    return results, frame_results


async def _stress_states(page: Page) -> dict:
    sequence = ["ULS", "SLS (cracked)", "Uncracked"] * 7
    expected_counts: dict[str, tuple[int, int, int]] = {}
    latencies = []
    host_switch_latencies = []
    for index, label in enumerate(sequence[:20]):
        started = time.perf_counter()
        await page.get_by_text(label, exact=True).click(no_wait_after=True)
        state = await _assert_state(page, STATE_KEYS[label])
        latencies.append((time.perf_counter() - started) * 1_000)
        await page.wait_for_timeout(40)
        state = await _visible_state(page)
        host_switch_latencies.append(float(state["host_switch_ms"]))
        host = state["visible_hosts"][0]
        counts = (host["traces"], host["shapes"], host["annotations"])
        if label in expected_counts and counts != expected_counts[label]:
            raise AssertionError(f"Plotly nodes accumulated for {label}: {counts}")
        expected_counts[label] = counts
        await page.wait_for_timeout(20 if index % 3 else 70)
    return {
        "switches": 20,
        "median_ms": statistics.median(latencies),
        "worst_ms": max(latencies),
        "host_switch_median_ms": statistics.median(host_switch_latencies),
        "host_switch_worst_ms": max(host_switch_latencies),
        "node_counts": {key: list(value) for key, value in expected_counts.items()},
    }


async def _exercise_tabs(page: Page) -> list[dict]:
    results = []
    for _cycle in range(5):
        for label in (
            "Side view",
            "Bending moment",
            "Section & stress-strain models",
        ):
            started = time.perf_counter()
            await page.get_by_role("tab", name=label).click()
            panel = page.locator('[role="tabpanel"]:visible')
            plot = panel.locator(".js-plotly-plot:visible").first
            await plot.wait_for(state="visible", timeout=5_000)
            box = await plot.bounding_box()
            if not box or box["height"] <= 100:
                raise AssertionError(f"{label} did not mount a visible Plotly diagram")
            results.append(
                {
                    "label": label,
                    "latency_ms": (time.perf_counter() - started) * 1_000,
                    "height": box["height"],
                }
            )
    return results


async def _material_lesson(page: Page) -> dict:
    await page.get_by_text("From strain to stress to internal force", exact=False).click()
    lesson = page.locator('[data-testid="stExpanderDetails"]:visible').filter(
        has=page.locator(".sb-material-major-one")
    )
    await lesson.wait_for(state="visible", timeout=10_000)
    material_plot = lesson.locator(".js-plotly-plot:visible").first
    await material_plot.wait_for(state="visible", timeout=10_000)
    box = await material_plot.bounding_box()
    traces = await material_plot.locator(".scatterlayer .trace").count()
    if not box or box["height"] <= 100 or traces <= 0:
        raise AssertionError("Material lesson live Plotly chart did not mount")
    return {"box": box, "traces": traces}


async def _capture_viewport(base_url: str, output: Path, name: str, viewport: dict) -> dict:
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
        except Exception:
            browser = await playwright.chromium.launch(headless=True, channel="msedge")
        context = await browser.new_context(viewport=viewport)
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        url = f"{base_url.rstrip('/')}?page=bending&cid=bending-regression-{uuid4()}"
        opened = time.perf_counter()
        await page.goto(url, wait_until="domcontentloaded")
        cold = await _cold_scroll_probe(page)
        loading_inputs_y = await _document_y(
            page.get_by_text("Inputs used for this check", exact=True)
        )
        await page.screenshot(path=output / f"{name}-loading.png", full_page=True)

        await page.locator("[data-bending-diagram-ready]").wait_for(
            state="attached", timeout=45_000
        )
        await _assert_state(page, "uls")
        await page.locator("[data-bending-diagram-shell]").wait_for(
            state="hidden", timeout=5_000
        )
        cold_paint_frames = await _end_cold_paint_probe(page)
        diagram_ready_ms = (time.perf_counter() - opened) * 1_000
        loaded_inputs_y = await _document_y(
            page.get_by_text("Inputs used for this check", exact=True)
        )
        live_height = await _loaded_region_height(page)
        shell_height = float(cold["shell"]["height"])
        geometry_delta = live_height - shell_height
        if abs(geometry_delta) > 2:
            raise AssertionError(
                f"shell/live region height movement was {geometry_delta:.3f}px"
            )
        inputs_delta = loaded_inputs_y - loading_inputs_y
        if abs(inputs_delta) > 2:
            raise AssertionError(
                f"loading-to-live downstream movement was {inputs_delta:.3f}px"
            )

        state_results, frame_results = await _exercise_states(page)
        stress_result = await _stress_states(page)
        tab_results = await _exercise_tabs(page)
        await page.get_by_role("tab", name="Section & stress-strain models").click()
        material = await _material_lesson(page)
        await page.screenshot(path=output / f"{name}-loaded.png", full_page=True)
        if errors:
            raise AssertionError(f"browser exceptions: {errors}")

        result = {
            "viewport": viewport,
            "cold": cold,
            "cold_paint_frames": cold_paint_frames,
            "diagram_ready_ms": diagram_ready_ms,
            "shell_height": shell_height,
            "loaded_region_height": live_height,
            "geometry_delta_px": geometry_delta,
            "loading_inputs_y": loading_inputs_y,
            "loaded_inputs_y": loaded_inputs_y,
            "layout_delta_px": inputs_delta,
            "states": state_results,
            "transition_frames": frame_results,
            "stress": stress_result,
            "tabs": tab_results,
            "material_plot": material,
        }
        await context.close()
        await browser.close()
        return result


async def _performance_run(browser, base_url: str, index: int) -> dict:
    context = await browser.new_context(viewport=VIEWPORTS["desktop"])
    page = await context.new_page()
    url = f"{base_url.rstrip('/')}?page=bending&cid=bending-perf-{index}-{uuid4()}"
    started = time.perf_counter()
    await page.goto(url, wait_until="domcontentloaded")
    await page.get_by_role("heading", name="Bending capacity").wait_for(timeout=30_000)
    summary_ms = (time.perf_counter() - started) * 1_000
    await page.locator("[data-bending-diagram-ready]").wait_for(
        state="attached", timeout=45_000
    )
    await _assert_state(page, "uls")
    await page.wait_for_function(
        "() => Boolean(document.documentElement.getAttribute("
        "'data-sb-bending-browser-ready'))",
        timeout=5_000,
    )
    diagram_ms = (time.perf_counter() - started) * 1_000
    switch_started = time.perf_counter()
    await page.get_by_text("SLS (cracked)", exact=True).click(no_wait_after=True)
    await _assert_state(page, "sls-cracked")
    sls_ms = (time.perf_counter() - switch_started) * 1_000
    await page.wait_for_timeout(40)
    sls_host_ms = float(
        await page.evaluate(
            "() => Number(document.documentElement.getAttribute("
            "'data-sb-last-bending-host-switch-ms') || 0)"
        )
    )
    switch_started = time.perf_counter()
    await page.get_by_text("Uncracked", exact=True).click(no_wait_after=True)
    await _assert_state(page, "uncracked")
    uncracked_ms = (time.perf_counter() - switch_started) * 1_000
    await page.wait_for_timeout(40)
    uncracked_host_ms = float(
        await page.evaluate(
            "() => Number(document.documentElement.getAttribute("
            "'data-sb-last-bending-host-switch-ms') || 0)"
        )
    )
    await context.close()
    return {
        "summary_ms": summary_ms,
        "diagram_ms": diagram_ms,
        "uls_to_sls_ms": sls_ms,
        "sls_to_uncracked_ms": uncracked_ms,
        "uls_to_sls_host_ms": sls_host_ms,
        "sls_to_uncracked_host_ms": uncracked_host_ms,
    }


async def _performance(base_url: str, runs: int) -> dict:
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
        except Exception:
            browser = await playwright.chromium.launch(headless=True, channel="msedge")
        results = [await _performance_run(browser, base_url, index) for index in range(runs)]
        await browser.close()
    summary = {}
    for metric in results[0]:
        values = [result[metric] for result in results]
        summary[metric] = {
            "median": statistics.median(values),
            "worst": max(values),
        }
    return {"runs": results, "summary": summary}


async def capture(base_url: str, output: Path, performance_runs: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    result = {
        name: await _capture_viewport(base_url, output, name, viewport)
        for name, viewport in VIEWPORTS.items()
    }
    if performance_runs:
        result["performance"] = await _performance(base_url, performance_runs)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8506/")
    parser.add_argument(
        "--output", type=Path, default=Path("work/bending-diagram-regression")
    )
    parser.add_argument("--performance-runs", type=int, default=3)
    args = parser.parse_args()
    result = asyncio.run(capture(args.base_url, args.output, args.performance_runs))
    result_path = args.output / "result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result_path)


if __name__ == "__main__":
    main()
