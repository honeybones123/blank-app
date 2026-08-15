"""Live Runtime interaction audit across every calculation page.

The runner exercises each visible control category in a real browser while
checking that the page remains exception-free and retains its route.  It is a
verification utility only; it is not imported by the Runtime application.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import Locator, Page, TimeoutError, sync_playwright


PAGES = (
    "inputs",
    "design",
    "bending",
    "shear",
    "creep",
    "shrinkage",
    "crack",
    "deflection",
)

PAGE_HEADINGS = {
    "inputs": "Beam Inputs",
    "design": "Load Analysis",
    "bending": "Bending capacity",
    "shear": "Shear & Torsion",
    "creep": "Creep",
    "shrinkage": "Shrinkage",
    # The visible title is method-specific (for example
    # ``Crack width – AS 3600:2018``).  Match its stable page identity.
    "crack": "Crack",
    "deflection": "Deflection",
}

IGNORED_CONTROL_NAMES = {
    "Debug session state",
    "Design Guide Debug",
    "keyboard_double_arrow_right",
    "Deploy",
    "Main menu",
    "Stop",
    "Rerun",
    "Always rerun",
    "Save",
    "PDF Report",
}

_COMPACT_INPUT_CARD_LABELS = ("Design actions", "Section & material", "Reinforcement")


def _stable(page: Page, timeout_ms: int = 8_000) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        running = page.locator("[data-testid='stStatusWidget'] img[alt='Running...']")
        try:
            if running.count() == 0 or not running.first.is_visible():
                page.wait_for_timeout(300)
                return
        except Exception:
            pass
        page.wait_for_timeout(80)
    raise TimeoutError("page did not settle")


def _wait_checked(page: Page, label: str, expected: bool, timeout_ms: int = 8_000) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.get_by_label(label, exact=True).first.is_checked() == expected:
                page.wait_for_timeout(250)
                return
        except Exception:
            pass
        page.wait_for_timeout(80)
    raise AssertionError(f"{label!r} did not settle to checked={expected}")


def _ready(page: Page, page_slug: str) -> None:
    heading = page.get_by_role(
        "heading", name=PAGE_HEADINGS[page_slug], exact=False
    ).last
    try:
        heading.wait_for(state="visible", timeout=20_000)
    except Exception as exc:
        headings = page.get_by_role("heading").all_inner_texts()
        exceptions = page.locator("[data-testid='stException']").all_inner_texts()
        raise AssertionError(
            f"expected heading {PAGE_HEADINGS[page_slug]!r}; "
            f"available={headings!r}; exceptions={exceptions!r}"
        ) from exc
    _stable(page, timeout_ms=20_000)
    # Fragment children may mount just after the route heading and status
    # indicator settle.  A short quiet window makes the control inventory
    # deterministic without contributing to the page-speed measurement.
    page.wait_for_timeout(500)


def _assert_healthy(page: Page, expected_page: str) -> None:
    if f"page={expected_page}" not in page.url:
        raise AssertionError(f"route changed unexpectedly: {page.url}")
    exceptions = page.locator("[data-testid='stException']")
    if exceptions.count():
        raise AssertionError(exceptions.first.inner_text())
    body = page.locator("body").inner_text()
    if "Traceback (most recent call last)" in body:
        raise AssertionError("traceback rendered")


def _name(locator: Locator) -> str:
    return str(locator.get_attribute("aria-label") or "").strip()


def _audit_details(page: Page, page_slug: str, evidence: list[dict[str, Any]]) -> None:
    count = page.locator("details > summary").count()
    for index in range(count):
        summaries = page.locator("details > summary")
        if index >= summaries.count():
            break
        summary = summaries.nth(index)
        label = summary.inner_text().strip()[:120]
        is_open = summary.evaluate("el => Boolean(el.parentElement && el.parentElement.open)")
        if not is_open:
            summary.evaluate("el => el.click()")
        _stable(page)
        _assert_healthy(page, page_slug)
        evidence.append({"kind": "expander", "label": label, "ok": True})
        # Calculation/detail cards are interaction-tested and returned to
        # their original state. Only the compact input categories stay open so
        # their widgets remain mounted for the subsequent control audit. This
        # mirrors a user opening one editing card instead of creating an
        # artificial page with every expensive diagram expanded at once.
        if not is_open and not any(token in label for token in _COMPACT_INPUT_CARD_LABELS):
            summary = page.locator("details > summary").nth(index)
            summary.evaluate("el => el.click()")
            _stable(page)
            _assert_healthy(page, page_slug)


def _ensure_compact_input_cards_open(page: Page, page_slug: str) -> None:
    """Remount calculation-page input widgets after a fragment commit."""

    summaries = page.locator("details > summary")
    for index in range(summaries.count()):
        summary = page.locator("details > summary").nth(index)
        label = summary.inner_text().strip()
        if not any(token in label for token in _COMPACT_INPUT_CARD_LABELS):
            continue
        is_open = summary.evaluate(
            "el => Boolean(el.parentElement && el.parentElement.open)"
        )
        if not is_open:
            summary.evaluate("el => el.click()")
            _stable(page)
            _assert_healthy(page, page_slug)


def _close_details(page: Page, page_slug: str) -> None:
    count = page.locator("details > summary").count()
    for index in reversed(range(count)):
        summaries = page.locator("details > summary")
        if index >= summaries.count():
            continue
        summary = summaries.nth(index)
        is_open = summary.evaluate("el => Boolean(el.parentElement && el.parentElement.open)")
        if is_open:
            summary.evaluate("el => el.click()")
            _stable(page)
            _assert_healthy(page, page_slug)


def _audit_switches(page: Page, page_slug: str, evidence: list[dict[str, Any]]) -> None:
    names = page.locator("input[type='checkbox']").evaluate_all(
        "els => els.map(e => e.getAttribute('aria-label') || '').filter(Boolean)"
    )
    for label in dict.fromkeys(names):
        if label in IGNORED_CONTROL_NAMES:
            continue
        control = page.get_by_label(label, exact=True).first
        if not control.is_enabled() or not control.is_visible():
            continue
        original = control.is_checked()
        # Click the semantic checkbox itself. Current Streamlit renders a
        # decorative parent around the input; clicking that parent can leave
        # the browser glyph changed without dispatching the widget value to
        # the server. The input click is the same state transition a keyboard
        # or label activation ultimately performs.
        control.click(force=True, timeout=5_000)
        _wait_checked(page, label, not original)
        _stable(page)
        _assert_healthy(page, page_slug)
        restored_control = page.get_by_label(label, exact=True).first
        if restored_control.is_checked() != original:
            restored_control.click(force=True, timeout=5_000)
        _wait_checked(page, label, original)
        _stable(page)
        _assert_healthy(page, page_slug)
        evidence.append({"kind": "switch", "label": label, "ok": True})


def _audit_radio_groups(page: Page, page_slug: str, evidence: list[dict[str, Any]]) -> None:
    groups = page.get_by_role("radiogroup")
    group_names = groups.evaluate_all(
        "els => els.map(e => e.getAttribute('aria-label') || '').filter(Boolean)"
    )
    for group_name in dict.fromkeys(group_names):
        if group_name == "Navigation":
            continue
        group = page.get_by_role("radiogroup", name=group_name).first
        radios = group.get_by_role("radio")
        if radios.count() < 2:
            continue
        original_index = next(
            (index for index in range(radios.count()) if radios.nth(index).is_checked()),
            0,
        )
        alternate_index = next(
            (index for index in range(radios.count()) if index != original_index),
            None,
        )
        if alternate_index is None:
            continue
        radios.nth(alternate_index).locator("xpath=..").click(force=True)
        _stable(page)
        _assert_healthy(page, page_slug)
        restored_group = page.get_by_role("radiogroup", name=group_name).first
        restored_group.get_by_role("radio").nth(original_index).locator("xpath=..").click(force=True)
        _stable(page)
        _assert_healthy(page, page_slug)
        evidence.append({"kind": "radio", "label": group_name, "ok": True})


def _audit_selectboxes(page: Page, page_slug: str, evidence: list[dict[str, Any]]) -> None:
    controls = page.get_by_role("combobox")
    initial_labels = controls.evaluate_all(
        "els => els.map(el => el.getAttribute('aria-label'))"
    )
    label_counts: dict[str, int] = {}
    specs: list[tuple[int, str | None, int]] = []
    for index, initial_label in enumerate(initial_labels):
        occurrence = 0
        if initial_label:
            occurrence = label_counts.get(str(initial_label), 0)
            label_counts[str(initial_label)] = occurrence + 1
        specs.append((index, initial_label, occurrence))

    # Audit only the controls present in the original state. Switching a row
    # from Count to Spacing creates a different conditional widget; treating
    # that newly mounted widget as another original control corrupts the
    # restore walk and can leave the page in the alternate state.
    # Walk from leaf selectors back to their parent selectors.  Several pages
    # conditionally mount ``Bars``/``Spacing`` from a preceding ``Layout``
    # selector.  Auditing the child first proves both controls without asking
    # the verifier to address a node that its own parent mutation temporarily
    # removed.
    for index, aria_label, label_occurrence in reversed(specs):
        _ensure_compact_input_cards_open(page, page_slug)
        if aria_label:
            current_controls = page.get_by_role(
                "combobox", name=aria_label, exact=True
            )
            if label_occurrence >= current_controls.count():
                raise AssertionError(f"{aria_label!r} missing before audit")
            control = current_controls.nth(label_occurrence)
        else:
            current_controls = page.get_by_role("combobox")
            if index >= current_controls.count():
                raise AssertionError(f"combobox[{index}] missing before audit")
            control = current_controls.nth(index)
        if not control.is_visible() or not control.is_enabled():
            continue
        label = str(aria_label or f"combobox[{index}]")
        original_value = str(control.input_value() or control.inner_text()).strip()
        control.click(force=True)
        # React Aria retains hidden option trees for previously opened
        # selects. Audit only the currently visible popup so an identically
        # named stale option cannot be addressed ahead of the live one.
        options = page.locator('[role="option"]:visible')
        if options.count() < 2:
            page.keyboard.press("Escape")
            continue
        option_records = options.evaluate_all(
            "els => els.map(el => ({"
            "text: (el.innerText || '').trim(), "
            "selected: (el.getAttribute('aria-selected') || '').toLowerCase()"
            "}))"
        )
        option_texts = [str(record.get("text") or "") for record in option_records]
        selected_index = next(
            (
                i
                for i, record in enumerate(option_records)
                if str(record.get("selected") or "") == "true"
            ),
            next((i for i, text in enumerate(option_texts) if text == original_value), 0),
        )
        original = option_texts[selected_index]
        alternate_index = next(
            (i for i, text in enumerate(option_texts) if text and i != selected_index),
            None,
        )
        if alternate_index is None:
            page.keyboard.press("Escape")
            continue
        alternate = option_texts[alternate_index]
        alternate_option = page.locator('[role="option"]:visible').filter(
            has_text=re.compile(rf"^\s*{re.escape(alternate)}\s*$")
        )
        if alternate_option.count() == 0:
            raise AssertionError(f"{label!r} lost alternate option {alternate!r}")
        alternate_option.first.click(force=True)
        _stable(page)
        try:
            _assert_healthy(page, page_slug)
        except AssertionError as exc:
            raise AssertionError(
                f"selectbox {label!r} failed after choosing "
                f"{alternate!r}: {exc}"
            ) from exc
        # Re-enter the same session before restoring.  This proves the
        # committed selection survives a page render and gives conditional
        # compact-card widgets (Layout -> Bars/Spacing) a deterministic mount
        # boundary instead of addressing a subtree while Streamlit replaces
        # it.
        page.reload(wait_until="domcontentloaded")
        _ready(page, page_slug)
        _assert_healthy(page, page_slug)
        _ensure_compact_input_cards_open(page, page_slug)
        if aria_label:
            restored_controls = page.get_by_role("combobox", name=aria_label, exact=True)
            try:
                restored_controls.nth(label_occurrence).wait_for(
                    state="visible", timeout=30_000
                )
            except Exception:
                pass
            if label_occurrence >= restored_controls.count():
                available_labels = page.get_by_role("combobox").evaluate_all(
                    "els => els.map(el => el.getAttribute('aria-label'))"
                )
                raise AssertionError(
                    f"{label!r} disappeared after selection; available={available_labels!r}"
                )
            restored_control = restored_controls.nth(label_occurrence)
        else:
            restored_controls = page.get_by_role("combobox")
            try:
                restored_controls.first.wait_for(state="visible", timeout=30_000)
            except Exception:
                pass
            restored_control = None
            for candidate_index in range(restored_controls.count()):
                candidate = restored_controls.nth(candidate_index)
                if not candidate.is_visible() or not candidate.is_enabled():
                    continue
                candidate.click(force=True)
                candidate_original = page.locator('[role="option"]:visible').filter(
                    has_text=re.compile(rf"^\s*{re.escape(original)}\s*$")
                )
                if candidate_original.count():
                    restored_control = candidate
                    break
                page.keyboard.press("Escape")
            if restored_control is None:
                raise AssertionError(
                    f"{label!r} disappeared after selection; "
                    f"original={original!r}, alternate={alternate!r}"
                )
        if aria_label:
            page.keyboard.press("Escape")
            restored_control.click(force=True)
        original_option = page.locator('[role="option"]:visible').filter(
            has_text=re.compile(rf"^\s*{re.escape(original)}\s*$")
        )
        try:
            original_option.first.wait_for(state="visible", timeout=10_000)
        except Exception:
            # BaseWeb occasionally remounts a combobox between pointer-down
            # and popup creation.  Keyboard opening targets the newly mounted
            # semantic control and is equivalent to a user pressing Down.
            restored_control.focus()
            restored_control.press("ArrowDown")
            try:
                original_option.first.wait_for(state="visible", timeout=10_000)
            except Exception:
                pass
        if original_option.count() == 0:
            available_options = page.locator('[role="option"]:visible').evaluate_all(
                "els => els.map(el => (el.innerText || '').trim())"
            )
            raise AssertionError(
                f"{label!r} cannot restore option {original!r}; "
                f"available={available_options!r}"
            )
        original_option.first.click(force=True)
        _stable(page)
        _assert_healthy(page, page_slug)
        evidence.append({"kind": "select", "label": label, "ok": True})


def _audit_number_inputs(page: Page, page_slug: str, evidence: list[dict[str, Any]]) -> None:
    names = page.locator("input[type='number']").evaluate_all(
        "els => els.map(e => e.getAttribute('aria-label') || '').filter(Boolean)"
    )
    for label in dict.fromkeys(names):
        _ensure_compact_input_cards_open(page, page_slug)
        control = page.get_by_label(label, exact=True).first
        if not control.is_visible() or not control.is_enabled():
            continue
        original = control.input_value()
        control.press("ArrowUp")
        _stable(page)
        _assert_healthy(page, page_slug)
        _ensure_compact_input_cards_open(page, page_slug)
        restored = page.get_by_label(label, exact=True).first
        restored.fill(original)
        restored.press("Enter")
        _stable(page)
        _assert_healthy(page, page_slug)
        evidence.append({"kind": "number", "label": label, "ok": True})


def _audit_info_buttons(page: Page, page_slug: str, evidence: list[dict[str, Any]]) -> None:
    buttons = page.get_by_role("button")
    names = buttons.evaluate_all(
        "els => els.map(e => (e.getAttribute('aria-label') || e.innerText || '').trim())"
    )
    for label in dict.fromkeys(names):
        if not label or label in IGNORED_CONTROL_NAMES:
            continue
        if label not in {"i", "ℹ️ INFO"} and not label.startswith("Help for "):
            continue
        button = page.get_by_role("button", name=label, exact=True).first
        if not button.is_visible() or not button.is_enabled():
            continue
        button.click()
        page.wait_for_timeout(80)
        page.keyboard.press("Escape")
        _stable(page)
        _assert_healthy(page, page_slug)
        evidence.append({"kind": "info", "label": label, "ok": True})


def _audit_tabs(page: Page, page_slug: str, evidence: list[dict[str, Any]]) -> None:
    """Visit every mounted page-local tab and restore its initial selection."""

    tablists = page.get_by_role("tablist")
    for list_index in range(tablists.count()):
        tablist = page.get_by_role("tablist").nth(list_index)
        tabs = tablist.get_by_role("tab")
        labels = tabs.evaluate_all(
            "els => els.map(el => (el.innerText || el.getAttribute('aria-label') || '').trim())"
        )
        if len(labels) < 2:
            continue
        original_index = next(
            (
                index
                for index in range(tabs.count())
                if str(tabs.nth(index).get_attribute("aria-selected") or "").lower()
                == "true"
            ),
            0,
        )
        for target_index, label in enumerate(labels):
            if target_index == original_index or not label:
                continue
            current_tabs = page.get_by_role("tablist").nth(list_index).get_by_role("tab")
            current_tabs.nth(target_index).click(force=True)
            _stable(page)
            _assert_healthy(page, page_slug)
            evidence.append({"kind": "tab", "label": str(label), "ok": True})
        restored_tabs = page.get_by_role("tablist").nth(list_index).get_by_role("tab")
        restored_tabs.nth(original_index).click(force=True)
        _stable(page)
        _assert_healthy(page, page_slug)


def run(base_url: str, cid: str, pages: tuple[str, ...] = PAGES) -> dict[str, Any]:
    report: dict[str, Any] = {"base_url": base_url, "cid": cid, "pages": {}}
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception:
            # The Runtime verification machines already provide Edge even
            # when Playwright's optional bundled Chromium is not installed.
            browser = playwright.chromium.launch(headless=True, channel="msedge")
        for slug in pages:
            # Cold-control evidence must not inherit conditional widget state
            # from the preceding route. Cross-page persistence is exercised by
            # the dedicated navigation/state fuzz harness instead.
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            try:
                query = urlencode({"page": slug, "fresh": "1", "cid": cid})
                page.goto(f"{base_url.rstrip('/')}/?{query}", wait_until="domcontentloaded")
                _ready(page, slug)
                _assert_healthy(page, slug)
                evidence: list[dict[str, Any]] = []
                started = time.perf_counter()
                _audit_details(page, slug, evidence)
                _audit_info_buttons(page, slug, evidence)
                _audit_tabs(page, slug, evidence)
                _audit_switches(page, slug, evidence)
                _audit_radio_groups(page, slug, evidence)
                _audit_selectboxes(page, slug, evidence)
                _audit_number_inputs(page, slug, evidence)
                _close_details(page, slug)
                _assert_healthy(page, slug)
                report["pages"][slug] = {
                    "ok": True,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                    "controls": evidence,
                    "control_count": len(evidence),
                }
            except Exception as exc:
                raise AssertionError(f"page {slug!r}: {exc}") from exc
            finally:
                context.close()
        browser.close()
    report["ok"] = all(item["ok"] for item in report["pages"].values())
    report["control_count"] = sum(item["control_count"] for item in report["pages"].values())
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8522")
    parser.add_argument("--cid", default="full-live-interaction-audit")
    parser.add_argument("--output")
    parser.add_argument("--pages", nargs="*", choices=PAGES, default=list(PAGES))
    args = parser.parse_args()
    try:
        report = run(args.base_url, args.cid, tuple(args.pages))
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    # Keep console output portable on the Windows cp1252 shell used by the
    # local Runtime verifier. Escapes do not change the JSON evidence.
    payload = json.dumps(report, indent=2, ensure_ascii=True)
    print(payload)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
