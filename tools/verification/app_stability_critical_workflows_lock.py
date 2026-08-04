"""Repeat-lock critical non-Apply workflows for app stability.

This verifier broadens the stability goal beyond the Design Guide Apply path.
It drives real browser interactions and checks that normal edits, mode toggles,
panel toggles, and page navigation settle without blanking, crashes, duplicate
key errors, or unexpected scroll jumps.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
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
CHECKPOINT_PATH = ARTIFACT_DIR / "app_stability_critical_workflows_checkpoint.json"

MU_LABEL = "Positive design moment Mu*+ (kNm)"
WIDTH_LABEL = "Width b (mm)"
LINK_SPACING_LABEL = "Link spacing (mm)"
APPLY_EDITS_LABEL = "Apply Beam/Reo/Load Edits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _source_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _checkpoint_path(*, recipe: dict[str, Any]) -> Path:
    """Keep canonical and focused checkpoints from overwriting each other."""
    recipe_hash = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    run_id = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID") or "").strip()
    run_suffix = (
        run_id.replace("/", "_").replace("\\", "_")[:48]
        if run_id
        else f"standalone-{os.getpid()}"
    )
    return ARTIFACT_DIR / f"app_stability_critical_workflows_checkpoint_{run_suffix}_{recipe_hash}.json"


def _load_checkpoint(*, recipe: dict[str, Any]) -> dict[str, Any]:
    checkpoint_path = _checkpoint_path(recipe=recipe)
    try:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict) or payload.get("status") != "RUNNING":
        return {}
    if payload.get("source_hash") != _source_hash() or payload.get("recipe") != recipe:
        return {}
    return payload


def _write_checkpoint(
    *,
    recipe: dict[str, Any],
    workflows: list[dict[str, Any]],
    in_progress: dict[str, Any] | None = None,
) -> None:
    checkpoint_path = _checkpoint_path(recipe=recipe)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "schema": "app_stability_critical_workflows_checkpoint.v1",
                "status": "RUNNING",
                "source_hash": _source_hash(),
                "recipe": recipe,
                "checkpoint_path": str(checkpoint_path),
                "completed_workflows": workflows,
                "in_progress": in_progress,
                "updated_at": _stamp(),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


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
              const errorMatch = bodyText.match(/(?:StreamlitDuplicateElementKey|Traceback|RuntimeError|Exception:)[\s\S]{0,420}/i);
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
                errorExcerpt: errorMatch ? errorMatch[0] : null,
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
        _query(
            base_url,
            {
                "page": "inputs",
                "browser_recipe": recipe,
                "browser_test_mode": "1",
                "stability_workflow": "1",
                "cid": f"critical-workflow-{recipe}",
            },
        ),
        wait_until="domcontentloaded",
        timeout=90_000,
    )
    ready = _page_cycle_wait_for_inputs_ready_gate(page, timeout_s=45.0)
    dom, stable = _wait_for_stable_dom(page, timeout_s=20.0)
    return {"ready_gate": ready, "dom": dom, "stable": stable}


def _workflow_action_input_edit(
    page,
    iteration: int,
    stage_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    before = _dom_probe(page)
    target = 180.0 + float(iteration % 5) * 10.0
    if stage_callback:
        stage_callback({"workflow": "normal_action_input_edit", "stage": "set_widget_started", "iteration": iteration})
    print(f"normal_action_input_edit stage=set_widget iteration={iteration}", flush=True)
    _set_number_input(page, MU_LABEL, target)
    if stage_callback:
        stage_callback({"workflow": "normal_action_input_edit", "stage": "set_widget_completed", "iteration": iteration})
    print(f"normal_action_input_edit stage=commit_widget iteration={iteration}", flush=True)
    state, ok, commit_method, commit_meta = _commit_number_input_like_user(
        page,
        active_label=MU_LABEL,
        other_label=WIDTH_LABEL,
        mu=target,
        vu=None,
        reconcile_timeout_s=25.0,
        stage_callback=(
            (lambda event: stage_callback({
                "workflow": "normal_action_input_edit",
                "iteration": iteration,
                **event,
            }))
            if stage_callback
            else None
        ),
    )
    if stage_callback:
        stage_callback({"workflow": "normal_action_input_edit", "stage": "commit_completed", "iteration": iteration})
    print(f"normal_action_input_edit stage=commit_return iteration={iteration}", flush=True)
    print(f"normal_action_input_edit stage=dom_settle iteration={iteration}", flush=True)
    if stage_callback:
        stage_callback({"workflow": "normal_action_input_edit", "stage": "dom_settle_started", "iteration": iteration})
    after, stable = _wait_for_stable_dom(page, timeout_s=20.0)
    if stage_callback:
        stage_callback({"workflow": "normal_action_input_edit", "stage": "dom_settle_completed", "iteration": iteration})
    print(f"normal_action_input_edit stage=dom_settle_return iteration={iteration}", flush=True)
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
    commit_state, commit_ok, commit_method, commit_meta = _commit_number_input_like_user(
        page,
        active_label=MU_LABEL,
        other_label=WIDTH_LABEL,
        mu=target,
        vu=None,
        reconcile_timeout_s=25.0,
    )
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
    if not ok:
        failures.append("explicit_design_calculation_state_did_not_settle")
    if not stable:
        failures.append("dom_did_not_stabilize_after_explicit_design_calculation")
    return {
        "target_mu": target,
        "commit_method": commit_method,
        "commit_meta": commit_meta,
        "commit_ok": commit_ok,
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
        # Navigation has its own slug/readiness probe. A 20-second DOM settle
        # window for every page multiplied the eight-page cycle by ten into a
        # release-gate timeout, even when the page had already settled. Keep a
        # bounded margin while allowing the probe to fail explicitly if the
        # app genuinely does not settle.
        click = _page_cycle_click_page(page, slug, label, timeout_s=12.0)
        # Inputs is the only page in the cycle that performs the full
        # engineering/publication bootstrap. Its existing readiness evidence
        # shows a bounded ~15 s settle in a cold navigation. Give that page a
        # measured margin so a slow transition is not misclassified as a blank
        # render; other pages retain the shorter interaction budget.
        settle_timeout_s = 20.0 if slug == "inputs" else 8.0
        dom, stable = _wait_for_stable_dom(page, timeout_s=settle_timeout_s)
        visit_failures = []
        if not (click.get("clicked") or click.get("already_active")):
            visit_failures.append(f"navigation_not_confirmed:{slug}")
        if not stable:
            visit_failures.append(f"dom_did_not_stabilize:{slug}")
        if dom.get("streamlitErrorVisible"):
            visit_failures.append(f"streamlit_error_visible:{slug}")
        if dom.get("blankLike"):
            visit_failures.append(f"blank_like_render:{slug}")
        visits.append({"slug": slug, "label": label, "click": click, "dom": dom, "stable": stable, "settle_timeout_s": settle_timeout_s, "failures": visit_failures})
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
    setup_each_iteration: bool = False,
    checkpoint_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    iterations: list[dict[str, Any]] = []
    # Page bootstrap is normally outside the repetition loop. The gate is
    # measuring repeated interaction/rerun stability; reloading the whole
    # Inputs page before every sample mostly measured startup cost. Stateful
    # workflows may opt into a reset per iteration when the prior action
    # intentionally removes or changes the next control under test.
    if checkpoint_callback is not None:
        checkpoint_callback({
            "workflow": name,
            "stage": "setup_started",
            "repetitions": repetitions,
            "completed_iterations": 0,
        })
    setup_meta = setup()
    if checkpoint_callback is not None:
        checkpoint_callback({
            "workflow": name,
            "stage": "setup_completed",
            "repetitions": repetitions,
            "completed_iterations": 0,
            "setup": setup_meta,
        })
    for index in range(1, repetitions + 1):
        print(f"{name} iteration {index}/{repetitions}", flush=True)
        if setup_each_iteration and index > 1:
            if checkpoint_callback is not None:
                checkpoint_callback({
                    "workflow": name,
                    "stage": "iteration_setup_started",
                    "iteration": index,
                    "repetitions": repetitions,
                    "completed_iterations": index - 1,
                })
            setup_meta = setup()
            if checkpoint_callback is not None:
                checkpoint_callback({
                    "workflow": name,
                    "stage": "iteration_setup_completed",
                    "iteration": index,
                    "repetitions": repetitions,
                    "completed_iterations": index - 1,
                    "setup": setup_meta,
                })
        if checkpoint_callback is not None:
            checkpoint_callback({
                "workflow": name,
                "stage": "iteration_started",
                "iteration": index,
                "repetitions": repetitions,
                "completed_iterations": index - 1,
            })
        result = workflow(index)
        failures = list(result.get("failures") or [])
        iterations.append(
            {
                "iteration": index,
                "status": "PASS" if not failures else "FAIL",
                "setup": dict(setup_meta, reused_for_repetition=index > 1),
                "result": result,
                "failures": failures,
            }
        )
        if checkpoint_callback is not None:
            checkpoint_callback(
                {
                    "workflow": name,
                    "repetitions": repetitions,
                    "passed": sum(1 for item in iterations if item.get("status") == "PASS"),
                    "failed": sum(1 for item in iterations if item.get("status") != "PASS"),
                    "iterations": list(iterations),
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

            selected_workflows = list(args.workflow or [
                "normal_action_input_edit",
                "geometry_width_edit",
                "reinforcement_edit",
                "explicit_design_calculation",
                "design_mode_toggle",
                "design_guide_expand_collapse",
                "calculation_panel_expand_collapse",
                "page_navigation_cycle",
            ])
            recipe = {
                "browser_recipe": args.browser_recipe,
                "repetitions": int(args.repetitions),
                "workflows": selected_workflows,
            }

            def checkpoint_progress(row: dict[str, Any]) -> None:
                _write_checkpoint(
                    recipe=recipe,
                    workflows=list(workflows),
                    in_progress=row,
                )

            available_workflows: dict[str, Callable[[], dict[str, Any]]] = {
                "normal_action_input_edit": lambda: _run_workflow_repeated(
                    page,
                    name="normal_action_input_edit",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_action_input_edit(page, index, checkpoint_progress),
                    checkpoint_callback=checkpoint_progress,
                ),
                "geometry_width_edit": lambda: _run_workflow_repeated(
                    page,
                    name="geometry_width_edit",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_geometry_edit(page, index),
                    checkpoint_callback=checkpoint_progress,
                ),
                "reinforcement_edit": lambda: _run_workflow_repeated(
                    page,
                    name="reinforcement_edit",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_reinforcement_edit(page, index),
                    checkpoint_callback=checkpoint_progress,
                ),
                "explicit_design_calculation": lambda: _run_workflow_repeated(
                    page,
                    name="explicit_design_calculation",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_explicit_design_calculation(page, index),
                    setup_each_iteration=True,
                    checkpoint_callback=checkpoint_progress,
                ),
                "design_mode_toggle": lambda: _run_workflow_repeated(
                    page,
                    name="design_mode_toggle",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_design_mode_toggle(page, index),
                    checkpoint_callback=checkpoint_progress,
                ),
                "design_guide_expand_collapse": lambda: _run_workflow_repeated(
                    page,
                    name="design_guide_expand_collapse",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_design_guide_expand_collapse(page, index),
                    checkpoint_callback=checkpoint_progress,
                ),
                "calculation_panel_expand_collapse": lambda: _run_workflow_repeated(
                    page,
                    name="calculation_panel_expand_collapse",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda index: _workflow_calculation_panel_expand_collapse(page, index),
                    checkpoint_callback=checkpoint_progress,
                ),
                "page_navigation_cycle": lambda: _run_workflow_repeated(
                    page,
                    name="page_navigation_cycle",
                    repetitions=int(args.repetitions),
                    setup=setup_inputs,
                    workflow=lambda _index: _workflow_page_cycle(page),
                    setup_each_iteration=True,
                    checkpoint_callback=checkpoint_progress,
                ),
            }
            if not args.workflow:
                selected_workflows = list(available_workflows.keys())
                recipe["workflows"] = selected_workflows
            unknown_workflows = [name for name in selected_workflows if name not in available_workflows]
            if unknown_workflows:
                raise SystemExit(f"Unknown workflow(s): {unknown_workflows}")
            checkpoint = _load_checkpoint(recipe=recipe)
            completed_by_name = {
                str(row.get("workflow") or ""): row
                for row in list(checkpoint.get("completed_workflows") or [])
                if isinstance(row, dict)
            }
            for workflow_name in selected_workflows:
                checkpointed = completed_by_name.get(workflow_name)
                # A checkpoint is reusable only when the workflow completed
                # cleanly. Failed or partial rows must be replayed; otherwise
                # a resumable run can silently preserve a previous live failure.
                if checkpointed and not checkpointed.get("failed") and checkpointed.get("passed"):
                    print(f"{workflow_name} reused from checkpoint", flush=True)
                    workflows.append(checkpointed)
                    continue
                try:
                    workflows.append(available_workflows[workflow_name]())
                except Exception as exc:
                    checkpoint = _load_checkpoint(recipe=recipe)
                    in_progress = dict(checkpoint.get("in_progress") or {})
                    workflows.append(
                        {
                            "workflow": workflow_name,
                            "repetitions": int(args.repetitions),
                            "passed": 0,
                            "failed": 1,
                            "iterations": [],
                            "failures": [
                                f"workflow_exception:{type(exc).__name__}: {exc}",
                            ],
                            "root_cause_candidate": {
                                "exception_type": type(exc).__name__,
                                "exception_message": str(exc),
                                "traceback": traceback.format_exc(),
                                "last_checkpoint": in_progress,
                            },
                        }
                    )
                _write_checkpoint(recipe=recipe, workflows=workflows, in_progress=None)
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
        "checkpoint_path": str(_checkpoint_path(recipe=recipe)),
    }
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"app_stability_critical_workflows_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"app_stability_critical_workflows_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, md_path)
    try:
        CHECKPOINT_PATH.unlink()
    except FileNotFoundError:
        pass
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
