"""Browser/live profile for Design Guide loading-shell completion.

Proof-only. This does not change product behavior. It samples a live Inputs
page while the Design Guide is loading and classifies whether the final card,
Browser-state proof, and summary cards settle together.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import _query, _start_streamlit  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

BENIGN_CONSOLE_WARNING_PATTERNS = (
    "Unrecognized feature:",
    "allow-scripts and allow-same-origin",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _snapshot(page) -> dict[str, Any]:
    payload = page.evaluate(
        r"""
        () => {
          const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
          const visible = (el) => {
            if (!el || !el.getBoundingClientRect) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== "none"
              && style.visibility !== "hidden"
              && Number(style.opacity || "1") > 0.02
              && rect.width > 2
              && rect.height > 2;
          };
          const rectPayload = (el) => {
            if (!el || !el.getBoundingClientRect || !visible(el)) return null;
            const rect = el.getBoundingClientRect();
            return {
              top: Math.round(rect.top),
              bottom: Math.round(rect.bottom),
              width: Math.round(rect.width),
              height: Math.round(rect.height)
            };
          };
          const bodyText = clean(document.body ? document.body.innerText : "");
          const cards = Array.from(document.querySelectorAll(
            "[data-testid='design-guide-card'], .fast-guidance-item, [data-testid*='design-guide' i], section, div"
          )).filter(visible).map((el) => {
            const text = clean(el.innerText || el.textContent);
            if (!/Design is|Strengthening required|Design Guide blocker|repair proof incomplete|cleanup proof incomplete|Why action is required|Why repair is blocked|Preview after proposed change/i.test(text)) return null;
            const rect = rectPayload(el);
            if (!rect || rect.height > window.innerHeight * 0.82 || text.length > 4500) return null;
            return { text: text.slice(0, 1200), cls: String(el.className || ""), rect };
          }).filter(Boolean);
          const buttons = Array.from(document.querySelectorAll("button")).filter(visible).map((el) => ({
            text: clean(el.innerText || el.textContent),
            disabled: !!el.disabled || el.getAttribute("aria-disabled") === "true",
            rect: rectPayload(el)
          }));
          const bodyWindow = (() => {
            const match = bodyText.match(/Design Guide\s+(?:PASS|ACTION|BLOCKED|ERROR|WARN|NEXT)\s+[\s\S]*?(?=\s+Design mode|\s+Design Actions|\s+Positive design moment|\s+Geometry & Materials|$)/i);
            return match ? clean(match[0]) : "";
          })();
          const finalCardText = cards.length ? cards[0].text : bodyWindow;
          return {
            url: window.location.href,
            body_text_sample: bodyText.slice(0, 2500),
            landing_start_your_design_present: /Start Your Design/i.test(bodyText),
            summary_cards_count: Array.from(document.querySelectorAll(".summary-check-card")).filter(visible).length,
            loading_shell_present: /Design Guide\s+Checking design guidance/i.test(bodyText),
            stable_rerun_shell_present: /Inputs page stable rerun shell/i.test(bodyText),
            final_card_present: !!finalCardText,
            final_card_text: finalCardText,
            final_card_class: cards.length ? cards[0].cls : (finalCardText ? "body-window-design-guide-card" : ""),
            visible_apply_like_button_count: buttons.filter((item) => /Apply|Run one-click|Strengthen|Repair|Improve/i.test(item.text || "")).length,
            visible_enabled_apply_like_button_count: buttons.filter((item) => /Apply|Run one-click|Strengthen|Repair|Improve/i.test(item.text || "") && !item.disabled).length,
            inputs_render_ms: (() => {
              const match = bodyText.match(/Inputs render:\s*([0-9.]+)\s*ms/i);
              return match ? Number(match[1]) : null;
            })(),
          };
        }
        """
    )
    return dict(payload or {})


def _try_state(page, timeout_s: float = 0.8) -> tuple[bool, str | None, dict[str, Any]]:
    try:
        state = dict(_load_browser_state(page, timeout_s=timeout_s) or {})
        return bool(state), None, {
            "design_guide_probe_keys": sorted((state.get("design_guide_probe") or {}).keys())[:30],
            "summary_overview_probe_keys": sorted((state.get("summary_overview_probe") or {}).keys())[:30],
            "has_debug_bundle": bool(((state.get("design_guide_probe") or {}).get("debug_bundle") or {})),
        }
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", {}


def _is_benign_console_warning(message: str) -> bool:
    text = str(message or "")
    return any(pattern in text for pattern in BENIGN_CONSOLE_WARNING_PATTERNS)


def _classify(samples: list[dict[str, Any]], console_errors: list[str], page_errors: list[str]) -> dict[str, Any]:
    final_seen = any(bool(s.get("final_card_present")) for s in samples)
    state_seen = any(bool(s.get("browser_state_available")) for s in samples)
    loading_seen = any(bool(s.get("loading_shell_present")) for s in samples)
    loading_last = bool(samples[-1].get("loading_shell_present")) if samples else False
    summary_seen = any(int(s.get("summary_cards_count") or 0) > 0 for s in samples)
    stable_shell_seen = any(bool(s.get("stable_rerun_shell_present")) for s in samples)
    landing_seen = any(bool(s.get("landing_start_your_design_present")) for s in samples)
    landing_last = bool(samples[-1].get("landing_start_your_design_present")) if samples else False
    likely_source = "completed"
    if not final_seen and landing_last and not loading_last and not stable_shell_seen:
        likely_source = "completed_landing_start_state"
    elif not final_seen and loading_last and not state_seen:
        likely_source = "loading_shell_timeout_with_empty_browser_state"
    elif not final_seen and loading_last:
        likely_source = "loading_shell_timeout_after_browser_state"
    elif not final_seen and stable_shell_seen:
        likely_source = "stable_shell_or_placeholder_not_replaced"
    elif final_seen and not state_seen:
        likely_source = "final_card_visible_but_browser_state_missing"
    if console_errors or page_errors:
        likely_source = f"{likely_source}_with_browser_errors"
    return {
        "final_card_seen": final_seen,
        "browser_state_seen": state_seen,
        "loading_shell_seen": loading_seen,
        "loading_shell_last": loading_last,
        "summary_cards_seen": summary_seen,
        "stable_rerun_shell_seen": stable_shell_seen,
        "landing_start_your_design_seen": landing_seen,
        "landing_start_your_design_last": landing_last,
        "console_error_count": len(console_errors),
        "page_error_count": len(page_errors),
        "likely_source": likely_source,
        "requires_fix": bool(
            (not final_seen and not landing_last)
            or loading_last
            or console_errors
            or page_errors
        ),
        "recommended_next_step": (
            "Trace the Design Guide compute/publication completion path: summary cards render, but final card and Browser-state proof never settle."
            if not final_seen and loading_last and not state_seen
            else "Use the card state/CTA consistency audit on the settled final card."
            if final_seen
            else "Landing state completed; no Design Guide card is expected until actions/loads or publication eligibility exist."
            if landing_last
            else "Inspect stable-shell replacement and Browser-state probe attachment."
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    classification = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Loading Shell Completion Profile",
        "",
        f"Status: `{payload['status']}`",
        f"Target URL: `{payload['target_url']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Executive Summary",
        "",
        f"- Likely source: `{classification.get('likely_source')}`",
        f"- Requires fix: `{classification.get('requires_fix')}`",
        f"- Final card seen: `{classification.get('final_card_seen')}`",
        f"- Browser-state seen: `{classification.get('browser_state_seen')}`",
        f"- Loading shell last: `{classification.get('loading_shell_last')}`",
        f"- Summary cards seen: `{classification.get('summary_cards_seen')}`",
        f"- Landing Start Your Design seen: `{classification.get('landing_start_your_design_seen')}`",
        f"- Landing Start Your Design last: `{classification.get('landing_start_your_design_last')}`",
        f"- Stable rerun shell seen: `{classification.get('stable_rerun_shell_seen')}`",
        f"- Console errors: `{classification.get('console_error_count')}`",
        f"- Page errors: `{classification.get('page_error_count')}`",
        "",
        "## Sample Tail",
        "",
    ]
    for sample in list(payload.get("samples") or [])[-8:]:
        lines.append(
            "- "
            f"t=`{sample.get('elapsed_ms')}`ms "
            f"summary=`{sample.get('summary_cards_count')}` "
            f"loading=`{sample.get('loading_shell_present')}` "
            f"final=`{sample.get('final_card_present')}` "
            f"state=`{sample.get('browser_state_available')}` "
            f"state_error=`{sample.get('browser_state_error')}` "
            f"inputs_render_ms=`{sample.get('inputs_render_ms')}`"
        )
    lines.extend(["", "## Recommendation", "", str(classification.get("recommended_next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8672)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_LOADING_SHELL_PROFILE_BASE_URL"))
    parser.add_argument(
        "--url",
        default=(
            os.environ.get("DESIGN_GUIDE_LOADING_SHELL_PROFILE_URL")
            or os.environ.get("DESIGN_GUIDE_CARD_STATE_AUDIT_URL")
        ),
    )
    parser.add_argument("--recipe", default=os.environ.get("DESIGN_GUIDE_LOADING_SHELL_PROFILE_RECIPE") or "A_bending_under_only")
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=float(os.environ.get("DESIGN_GUIDE_LOADING_SHELL_PROFILE_SECONDS") or "60"),
    )
    parser.add_argument(
        "--interval-s",
        type=float,
        default=float(os.environ.get("DESIGN_GUIDE_LOADING_SHELL_PROFILE_INTERVAL") or "1.5"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    process: subprocess.Popen | None = None
    base_url = args.base_url
    if not args.url and not base_url:
        process = _start_streamlit(int(args.port))
        base_url = f"http://127.0.0.1:{int(args.port)}"
    target_url = args.url or _query(str(base_url or "http://127.0.0.1:8504"), {"page": "inputs", "browser_recipe": args.recipe})
    duration_s = float(args.timeout_s)
    interval_s = float(args.interval_s)
    samples: list[dict[str, Any]] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    errors: list[str] = []
    started = time.perf_counter()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in {"error", "warning"} else None)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
            while time.perf_counter() - started <= duration_s:
                sample = _snapshot(page)
                state_available, state_error, state_digest = _try_state(page)
                sample.update(
                    {
                        "elapsed_ms": round((time.perf_counter() - started) * 1000),
                        "browser_state_available": state_available,
                        "browser_state_error": state_error,
                        "browser_state_digest": state_digest,
                    }
                )
                samples.append(sample)
                if sample.get("final_card_present") and state_available:
                    break
                time.sleep(interval_s)
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
    actionable_console_errors = [
        message for message in console_errors if not _is_benign_console_warning(message)
    ]
    ignored_console_warnings = [
        message for message in console_errors if _is_benign_console_warning(message)
    ]
    classification = _classify(samples, actionable_console_errors, page_errors)
    failures: list[str] = []
    if classification.get("requires_fix"):
        failures.append(str(classification.get("likely_source") or "loading_shell_completion_profile_requires_fix"))
    failures.extend(f"browser_error::{error}" for error in errors)
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_loading_shell_completion_profile.v1",
        "status": status,
        "created_at": stamp,
        "target_url": target_url,
        "requested_recipe": args.recipe,
        "started_streamlit_port": int(args.port) if process is not None else None,
        "duration_s": duration_s,
        "interval_s": interval_s,
        "product_behaviour_changed": False,
        "code_changed": False,
        "classification": classification,
        "samples": samples,
        "console_errors": actionable_console_errors[-30:],
        "ignored_console_warnings": ignored_console_warnings[-30:],
        "page_errors": page_errors[-30:],
        "errors": errors,
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"design_guide_loading_shell_completion_profile_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_loading_shell_completion_profile_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "likely_source": classification.get("likely_source"),
                "requires_fix": classification.get("requires_fix"),
            },
            indent=2,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
