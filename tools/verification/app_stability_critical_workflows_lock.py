"""Repeat-lock critical non-Apply workflows for app stability.

This verifier broadens the stability goal beyond the Design Guide Apply path.
It drives real browser interactions and checks that normal edits, mode toggles,
panel toggles, and page navigation settle without blanking, crashes, duplicate
key errors, or unexpected scroll jumps.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import (  # noqa: E402
    _commit_live_edit,
    _commit_number_input_like_user,
    _input_dom_matches,
    _load_browser_state,
    _page_cycle_click_page,
    _page_cycle_wait_for_inputs_ready_gate,
    _same_value,
    _set_number_input,
    _wait_for_partial_state,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

MU_LABEL = "Positive design moment Mu*+ (kNm)"
WIDTH_LABEL = "Width b (mm)"
LINK_SPACING_LABEL = "Link spacing (mm)"
APPLY_EDITS_LABEL = "Apply Beam/Reo/Load Edits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _dom_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const bodyText = clean(document.body ? document.body.innerText : "");
              const visible = (el) => {
                if (!el) return false;
                if (el.hasAttribute("inert") || el.closest("[inert]")) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && rect.width > 2
                  && rect.height > 2;
              };
              const count = (selector) => {
                try { return Array.from(document.querySelectorAll(selector)).filter(visible).length; }
                catch (_err) { return 0; }
              };
              let hash = 2166136261;
              for (let i = 0; i < bodyText.length; i += 1) {
                hash ^= bodyText.charCodeAt(i);
                hash = Math.imul(hash, 16777619);
              }
              return {
                scrollY: Math.round(window.scrollY || 0),
                bodyTextLength: bodyText.length,
                bodyTextHash: (hash >>> 0).toString(16),
                hasInputsHeading: /\bInputs\b/.test(bodyText),
                hasDesignGuide: /Design Guide/i.test(bodyText),
                hasSummaryCards: /Bending\s+[\u2014-]\s+ULS|Shear\s+[\u2014-]\s+ULS/i.test(bodyText),
                loadingVisible: count('[data-testid="stSpinner"], [data-testid="stSkeleton"], [aria-busy="true"], [role="progressbar"]') > 0,
                designGuideCardCount: count('[data-testid="design-guide-card"], .fast-guidance-item'),
                inputCount: count('input, textarea, select'),
                streamlitErrorVisible: /StreamlitDuplicateElementKey|Traceback|RuntimeError|Exception:/i.test(bodyText),
                blankLike: bodyText.length < 900 || !/Inputs|Design|Bending|Shear|Creep|Shrinkage|Crack Control|Deflection|Design Guide/i.test(bodyText)
              };
            }
            """
        )
    )


def _wait_for_stable_dom(page, *, timeout_s: float = 20.0) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + max(2.0, timeout_s)
    last: dict[str, Any] = {}
    stable = 0
    last_hash: tuple[Any, ...] | None = None
    while time.time() < deadline:
        try:
            last = _dom_probe(page)
        except Exception as exc:
            last = {"probe_error": f"{type(exc).__name__}: {exc}"}
        current_hash = (
            last.get("bodyTextHash"),
            last.get("loadingVisible"),
            last.get("streamlitErrorVisible"),
            last.get("blankLike"),
        )
        if current_hash == last_hash:
            stable += 1
        else:
            stable = 1
            last_hash = current_hash
        if (
            stable >= 2
            and not last.get("loadingVisible")
            and not last.get("blankLike")
            and not last.get("streamlitErrorVisible")
        ):
            return last, True
        time.sleep(0.35)
    return last, False


def _classify_dom(before: dict[str, Any], after: dict[str, Any], *, allow_scroll_change: bool = False) -> list[str]:
    failures: list[str] = []
    if after.get("streamlitErrorVisible"):
        failures.append("streamlit_error_visible")
    if after.get("blankLike"):
        failures.append("blank_like_render")
    if after.get("loadingVisible"):
        failures.append("loading_shell_still_visible")
    if not after.get("hasSummaryCards") and not after.get("hasInputsHeading"):
        failures.append("core_inputs_content_missing")
    if not allow_scroll_change:
        before_scroll = int(before.get("scrollY") or 0)
        after_scroll = int(after.get("scrollY") or 0)
        if abs(after_scroll - before_scroll) > 30:
            failures.append("unexpected_scroll_movement")
    return failures


def _open_inputs(page, base_url: str, recipe: str) -> dict[str, Any]:
    page.goto(
        _query(base_url, {"page": "inputs", "browser_recipe": recipe, "stability_workflow": "1"}),
        wait_until="domcontentloaded",
        timeout=90_000,
    )
    ready = _page_cycle_wait_for_inputs_ready_gate(page, timeout_s=45.0)
    dom, stable = _wait_for_stable_dom(page, timeout_s=20.0)
    return {"ready_gate": ready, "dom": dom, "stable": stable}


def _workflow_action_input_edit(page, iteration: int) -> dict[str, Any]:
    before = _dom_probe(page)
    target = 180.0 + float(iteration % 5) * 10.0
    _set_number_input(page, MU_LABEL, target)
    state, ok, commit_method, commit_meta = _commit_number_input_like_user(
        page,
        active_label=MU_LABEL,
        other_label=WIDTH_LABEL,
        mu=target,
        vu=None,
        reconcile_timeout_s=25.0,
    )
    after, stable = _wait_for_stable_dom(page, timeout_s=20.0)
    failures = _classify_dom(before, after)
    dom_committed = _input_dom_matches(page, MU_LABEL, target, timeout_s=2.0)
    if not ok and not dom_committed:
        failures.append("mu_state_did_not_settle")
    probe = dict(state.get("summary_state_probe") or {})
    shared = dict(state.get("browser_shared_probe") or {})
    if not (
        _same_value(probe.get("uls_Mstar"), target)
        or _same_value(shared.get("uls_Mstar"), target)
        or _same_value(shared.get("load_Mstar_proxy"), target)
        or dom_committed
    ):
        failures.append("mu_state_value_mismatch")
    if not stable:
        failures.append("dom_did_not_stabilize_after_mu_edit")
    return {
        "target_mu": target,
        "state_settled": ok,
        "dom_committed": dom_committed,
        "commit_method": commit_method,
        "commit_meta": commit_meta,
        "state_probe": probe,
        "shared_probe": shared,
        "dom_before": before,
        "dom_after": after,
        "failures": failures,
    }


def _workflow_geometry_edit(page, iteration: int) -> dict[str, Any]:
    before = _dom_probe(page)
    target = 300.0 + float(iteration % 4) * 25.0
    _set_number_input(page, WIDTH_LABEL, target)
    _commit_live_edit(page)
    deadline = time.time() + 25.0
    state: dict[str, Any] = {}
    ok = False
    while time.time() < deadline:
        try:
            state = _load_browser_state(page, timeout_s=2.0)
        except Exception:
            time.sleep(0.3)
            continue
        shared = dict(state.get("browser_shared_probe") or {})
        if _same_value(shared.get("b"), target):
            ok = True
            break
        time.sleep(0.3)
    after, stable = _wait_for_stable_dom(page, timeout_s=20.0)
    failures = _classify_dom(before, after)
    dom_committed = _input_dom_matches(page, WIDTH_LABEL, target, timeout_s=2.0)
    if not ok and not dom_committed:
        failures.append("width_state_did_not_settle")
    if not stable:
        failures.append("dom_did_not_stabilize_after_width_edit")
    return {
        "target_width": target,
        "state_settled": ok,
        "dom_committed": dom_committed,
        "shared_probe": dict(state.get("browser_shared_probe") or {}),
        "dom_before": before,
        "dom_after": after,
        "failures": failures,
    }


def _workflow_reinforcement_edit(page, iteration: int) -> dict[str, Any]:
    before = _dom_probe(page)
    target = 125.0 + float(iteration % 4) * 25.0
    page.get_by_label(LINK_SPACING_LABEL).scroll_into_view_if_needed(timeout=10_000)
    _set_number_input(page, LINK_SPACING_LABEL, target)
    _commit_live_edit(page)
    deadline = time.time() + 25.0
    state: dict[str, Any] = {}
    ok = False
    while time.time() < deadline:
        try:
            state = _load_browser_state(page, timeout_s=2.0)
        except Exception:
            time.sleep(0.3)
            continue
        shared = dict(state.get("browser_shared_probe") or {})
        if (
            _same_value(shared.get("s_lig"), target)
            or _same_value(shared.get("lig_spacing"), target)
            or _same_value(shared.get("link_spacing"), target)
        ):
            ok = True
            break
        if _input_dom_matches(page, LINK_SPACING_LABEL, target, timeout_s=0.5):
            ok = True
            break
        time.sleep(0.3)
    after, stable = _wait_for_stable_dom(page, timeout_s=20.0)
    failures = _classify_dom(before, after, allow_scroll_change=True)
    dom_committed = _input_dom_matches(page, LINK_SPACING_LABEL, target, timeout_s=2.0)
    if not ok and not dom_committed:
        failures.append("reinforcement_spacing_state_did_not_settle")
    if not stable:
        failures.append("dom_did_not_stabilize_after_reinforcement_edit")
    return {
        "target_link_spacing": target,
        "state_settled": ok,
        "dom_committed": dom_committed,
        "shared_probe": dict(state.get("browser_shared_probe") or {}),
        "dom_before": before,
        "dom_after": after,
        "failures": failures,
    }


def _workflow_explicit_design_calculation(page, iteration: int) -> dict[str, Any]:
    before = _dom_probe(page)
    target = 220.0 + float(iteration % 4) * 5.0
    _set_number_input(page, MU_LABEL, target)
    clicked = False
    click_error = None
    try:
        clicked = bool(
            page.evaluate(
                r"""
                (label) => {
                  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
                  const visible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4;
                  };
                  const clickVisibleApply = () => {
                    const buttons = Array.from(document.querySelectorAll("button, [role='button']"));
                    const target = buttons.find((el) => visible(el) && clean(el.innerText || el.textContent).includes(label));
                    if (!target) return false;
                    target.scrollIntoView({block: "center", inline: "center"});
                    target.click();
                    return true;
                  };
                  if (clickVisibleApply()) return true;
                  const toggles = Array.from(document.querySelectorAll("button, [role='button'], div[aria-label]"));
                  const batchToggle = toggles.find((el) => visible(el) && /Toggle Batch design workspace/i.test(el.getAttribute("aria-label") || ""));
                  if (batchToggle) batchToggle.click();
                  return clickVisibleApply();
                }
                """,
                APPLY_EDITS_LABEL,
            )
        )
        if not clicked:
            page.wait_for_timeout(500)
            clicked = bool(
                page.evaluate(
                    r"""
                    (label) => {
                      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
                      const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4;
                      };
                      const target = Array.from(document.querySelectorAll("button, [role='button']"))
                        .find((el) => visible(el) && clean(el.innerText || el.textContent).includes(label));
                      if (!target) return false;
                      target.scrollIntoView({block: "center", inline: "center"});
                      target.click();
                      return true;
                    }
                    """,
                    APPLY_EDITS_LABEL,
                )
            )
    except Exception as exc:
        click_error = f"{type(exc).__name__}: {exc}"
        _commit_live_edit(page)
    deadline = time.time() + 30.0
    state: dict[str, Any] = {}
    ok = False
    while time.time() < deadline:
        try:
            state = _load_browser_state(page, timeout_s=2.0)
        except Exception:
            time.sleep(0.3)
            continue
        probe = dict(state.get("summary_state_probe") or {})
        shared = dict(state.get("browser_shared_probe") or {})
        if (
            _same_value(probe.get("uls_Mstar"), target)
            or _same_value(shared.get("uls_Mstar"), target)
            or _same_value(shared.get("load_Mstar_proxy"), target)
            or _input_dom_matches(page, MU_LABEL, target, timeout_s=0.5)
        ):
            ok = True
            break
        time.sleep(0.3)
    after, stable = _wait_for_stable_dom(page, timeout_s=25.0)
    failures = _classify_dom(before, after, allow_scroll_change=True)
    if not clicked:
        failures.append("explicit_apply_edits_button_not_clicked")
    if not ok:
        failures.append("explicit_design_calculation_state_did_not_settle")
    if not stable:
        failures.append("dom_did_not_stabilize_after_explicit_design_calculation")
    return {
        "target_mu": target,
        "clicked_apply_edits": clicked,
        "click_error": click_error,
        "state_settled": ok,
        "state_probe": dict(state.get("summary_state_probe") or {}),
        "shared_probe": dict(state.get("browser_shared_probe") or {}),
        "dom_before": before,
        "dom_after": after,
        "failures": failures,
    }


def _click_text(page, text: str) -> dict[str, Any]:
    try:
        locator = page.get_by_text(text, exact=True).first
        locator.click(timeout=5_000)
        return {"clicked": True, "method": "get_by_text_exact"}
    except Exception as exc:
        return {"clicked": False, "error": f"{type(exc).__name__}: {exc}"}


def _workflow_design_mode_toggle(page, iteration: int) -> dict[str, Any]:
    before = _dom_probe(page)
    target = "Detailed" if iteration % 2 else "Fast"
    click = _click_text(page, target)
    after, stable = _wait_for_stable_dom(page, timeout_s=15.0)
    failures = _classify_dom(before, after)
    if not click.get("clicked"):
        failures.append("design_mode_toggle_not_clicked")
    if not stable:
        failures.append("dom_did_not_stabilize_after_design_mode_toggle")
    return {
        "target_mode": target,
        "click": click,
        "dom_before": before,
        "dom_after": after,
        "failures": failures,
    }


def _workflow_design_guide_expand_collapse(page, iteration: int) -> dict[str, Any]:
    before = _dom_probe(page)
    click_meta = dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4;
              };
              const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,div,span,p"))
                .filter((el) => visible(el) && /^Design Guide$/i.test(clean(el.innerText || el.textContent)));
              const heading = headings[headings.length - 1] || null;
              if (!heading) return {clicked: false, reason: "heading_not_found"};
              const card = heading.closest("section, article, [data-testid='stVerticalBlock'], div") || heading.parentElement;
              const root = card && card.parentElement ? card.parentElement : document.body;
              const buttons = Array.from(root.querySelectorAll("button, [role='button'], summary"))
                .filter((el) => visible(el));
              const target = buttons.find((el) => /Design Guide|expand|collapse|chevron|v|⌄|⌃|›|〉|˅/i.test(clean(el.getAttribute("aria-label") || el.innerText || el.textContent)));
              if (target) {
                target.click();
                return {clicked: true, method: "near_design_guide_button", label: clean(target.getAttribute("aria-label") || target.innerText || target.textContent)};
              }
              const fallback = root.querySelector("[data-testid='design-guide-card'], .fast-guidance-item") || heading;
              if (fallback && visible(fallback)) {
                fallback.click();
                return {clicked: true, method: "design_guide_card_or_heading"};
              }
              return {clicked: false, reason: "target_not_found"};
            }
            """
        )
    )
    after, stable = _wait_for_stable_dom(page, timeout_s=15.0)
    failures = _classify_dom(before, after)
    if not click_meta.get("clicked"):
        failures.append("design_guide_expand_collapse_target_not_found")
    if not stable:
        failures.append("dom_did_not_stabilize_after_design_guide_expand_collapse")
    return {
        "iteration": iteration,
        "click": click_meta,
        "dom_before": before,
        "dom_after": after,
        "failures": failures,
    }


def _workflow_calculation_panel_expand_collapse(page, iteration: int) -> dict[str, Any]:
    before = _dom_probe(page)
    clicked = bool(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4;
              };
              const candidates = Array.from(document.querySelectorAll('button, [role="button"], summary, [data-testid="stExpander"]'));
              const target = candidates.find((el) => visible(el) && /Bending\s+[\u2014-]\s+ULS/i.test(clean(el.innerText || el.textContent)));
              if (target) {
                target.click();
                return true;
              }
              const textNode = Array.from(document.querySelectorAll('*')).find((el) => visible(el) && /^Bending\s+[\u2014-]\s+ULS$/i.test(clean(el.innerText || el.textContent)));
              if (textNode) {
                textNode.click();
                return true;
              }
              return false;
            }
            """
        )
    )
    after, stable = _wait_for_stable_dom(page, timeout_s=15.0)
    failures = _classify_dom(before, after)
    if not clicked:
        failures.append("calculation_panel_toggle_target_not_found")
    if not stable:
        failures.append("dom_did_not_stabilize_after_calculation_panel_toggle")
    return {
        "iteration": iteration,
        "clicked": clicked,
        "dom_before": before,
        "dom_after": after,
        "failures": failures,
    }


def _workflow_page_cycle(page) -> dict[str, Any]:
    before = _dom_probe(page)
    visits: list[dict[str, Any]] = []
    failures: list[str] = []
    for slug, label in (
        ("design", "Design"),
        ("bending", "Bending"),
        ("shear", "Shear"),
        ("creep", "Creep"),
        ("shrinkage", "Shrinkage"),
        ("crack", "Crack Control"),
        ("deflection", "Deflection"),
        ("inputs", "Inputs"),
    ):
        click = _page_cycle_click_page(page, slug, label, timeout_s=20.0)
        dom, stable = _wait_for_stable_dom(page, timeout_s=20.0)
        visit_failures = []
        if not (click.get("clicked") or click.get("already_active")):
            visit_failures.append(f"navigation_not_confirmed:{slug}")
        if not stable:
            visit_failures.append(f"dom_did_not_stabilize:{slug}")
        if dom.get("streamlitErrorVisible"):
            visit_failures.append(f"streamlit_error_visible:{slug}")
        if dom.get("blankLike"):
            visit_failures.append(f"blank_like_render:{slug}")
        visits.append({"slug": slug, "label": label, "click": click, "dom": dom, "stable": stable, "failures": visit_failures})
        failures.extend(visit_failures)
    after = visits[-1]["dom"] if visits else _dom_probe(page)
    failures.extend(_classify_dom(before, after, allow_scroll_change=True))
    return {"visits": visits, "dom_before": before, "dom_after": after, "failures": failures}


def _run_workflow_repeated(
    page,
    *,
    name: str,
    repetitions: int,
    setup: Callable[[], dict[str, Any]],
    workflow: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    iterations: list[dict[str, Any]] = []
    for index in range(1, repetitions + 1):
        print(f"{name} iteration {index}/{repetitions}", flush=True)
        setup_meta = setup()
        result = workflow(index)
        failures = list(result.get("failures") or [])
        iterations.append(
            {
                "iteration": index,
                "status": "PASS" if not failures else "FAIL",
                "setup": setup_meta,
                "result": result,
                "failures": failures,
            }
        )
    return {
        "workflow": name,
        "repetitions": repetitions,
        "passed": sum(1 for item in iterations if item.get("status") == "PASS"),
        "failed": sum(1 for item in iterations if item.get("status") != "PASS"),
        "iterations": iterations,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# App Stability Critical Workflows Lock",
        "",
        f"Status: `{payload.get('status')}`",
        f"Generated: `{payload.get('timestamp')}`",
        f"Recipe: `{payload.get('browser_recipe')}`",
        f"Repetitions per workflow: `{payload.get('repetitions')}`",
        "",
        "## Summary",
        "",
    ]
    for workflow in payload.get("workflows") or []:
        lines.extend(
            [
                f"- `{workflow.get('workflow')}`: `{workflow.get('passed')}` passed / `{workflow.get('failed')}` failed",
            ]
        )
    lines.extend(["", "## Failures", ""])
    failures = payload.get("failures") or []
    lines.extend([f"- `{failure}`" for failure in failures] or ["None."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8504")
    parser.add_argument("--start-streamlit", action="store_true")
    parser.add_argument("--port", type=int, default=8521)
    parser.add_argument("--browser-recipe", default="R3A_M300_V400")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument(
        "--workflow",
        action="append",
        default=[],
        help="Run only the named workflow. May be supplied multiple times.",
    )
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    process = None
    base_url = args.base_url
    workflows: list[dict[str, Any]] = []
    try:
        if args.start_streamlit:
            base_url = f"http://127.0.0.1:{int(args.port)}"
            process = _start_streamlit(int(args.port))
        else:
            _wait_for_http(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            def setup_inputs() -> dict[str, Any]:
                return _open_inputs(page, base_url, args.browser_recipe)

            available_workflows: dict[str, Callable[[], dict[str, Any]]] = {
                "normal_action_input_edit": lambda: _run_workflow_repeated(
                    page,
                    name="normal_action_input_edit",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_action_input_edit(page, index),
                ),
                "geometry_width_edit": lambda: _run_workflow_repeated(
                    page,
                    name="geometry_width_edit",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_geometry_edit(page, index),
                ),
                "reinforcement_edit": lambda: _run_workflow_repeated(
                    page,
                    name="reinforcement_edit",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_reinforcement_edit(page, index),
                ),
                "explicit_design_calculation": lambda: _run_workflow_repeated(
                    page,
                    name="explicit_design_calculation",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_explicit_design_calculation(page, index),
                ),
                "design_mode_toggle": lambda: _run_workflow_repeated(
                    page,
                    name="design_mode_toggle",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_design_mode_toggle(page, index),
                ),
                "design_guide_expand_collapse": lambda: _run_workflow_repeated(
                    page,
                    name="design_guide_expand_collapse",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_design_guide_expand_collapse(page, index),
                ),
                "calculation_panel_expand_collapse": lambda: _run_workflow_repeated(
                    page,
                    name="calculation_panel_expand_collapse",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_calculation_panel_expand_collapse(page, index),
                ),
                "page_navigation_cycle": lambda: _run_workflow_repeated(
                    page,
                    name="page_navigation_cycle",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda _index: _workflow_page_cycle(page),
                ),
            }
            selected_workflows = list(args.workflow or available_workflows.keys())
            unknown_workflows = [name for name in selected_workflows if name not in available_workflows]
            if unknown_workflows:
                raise SystemExit(f"Unknown workflow(s): {unknown_workflows}")
            for workflow_name in selected_workflows:
                workflows.append(available_workflows[workflow_name]())
            browser.close()
    finally:
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    failures: list[str] = []
    for workflow in workflows:
        for iteration in workflow.get("iterations") or []:
            for failure in iteration.get("failures") or []:
                failures.append(f"{workflow.get('workflow')}#{iteration.get('iteration')}:{failure}")

    payload = {
        "schema": "app_stability_critical_workflows_lock.v1",
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "base_url": base_url,
        "started_isolated_streamlit": bool(args.start_streamlit),
        "browser_recipe": args.browser_recipe,
        "repetitions": int(args.repetitions),
        "workflows": workflows,
        "failures": failures,
        "product_behaviour_changed": False,
    }
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"app_stability_critical_workflows_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"app_stability_critical_workflows_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"app_stability_critical_workflows_lock {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:")
        for failure in failures[:30]:
            print(f"- {failure}")
        if len(failures) > 30:
            print(f"... {len(failures) - 30} more")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
