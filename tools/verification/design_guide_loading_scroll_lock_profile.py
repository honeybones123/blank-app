"""Browser/live profile for scroll-up lock during Design Guide loading.

Measurement-only. The profile detects whether wheel scrolling upward is being
overridden while the Inputs / Design Guide transition shell is visible. It does
not change product code, session state, engineering logic, CTA/apply routing,
or visible wording.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "A_bending_under_only"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({key: value for key, value in params.items() if value is not None})}"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "passed": payload.get("status") == "PASS",
        "snapshot_hash": payload.get("snapshot_hash") or payload.get("profile_hash"),
    }


def _install_scroll_probe(context) -> None:
    context.add_init_script(
        r"""
        (() => {
          window.__dgScrollLockProbe = window.__dgScrollLockProbe || {
            installedAt: Date.now(),
            wheelEvents: [],
            scrollEvents: [],
            preventDefaultCalls: []
          };
          const probe = window.__dgScrollLockProbe;
          try {
            const original = Event.prototype.preventDefault;
            if (!Event.prototype.__dgScrollProbeWrapped) {
              Event.prototype.preventDefault = function() {
                try {
                  probe.preventDefaultCalls.push({
                    type: this.type,
                    time: Date.now(),
                    target: this.target ? String(this.target.tagName || "").toLowerCase() : null,
                    targetClass: this.target ? String(this.target.className || "").slice(0, 120) : null
                  });
                  if (probe.preventDefaultCalls.length > 80) {
                    probe.preventDefaultCalls = probe.preventDefaultCalls.slice(-80);
                  }
                } catch (_err) {}
                return original.apply(this, arguments);
              };
              Event.prototype.__dgScrollProbeWrapped = true;
            }
          } catch (_err) {}
          const bestScroller = () => {
            const candidates = [
              document.querySelector("section.stMain"),
              document.querySelector("section[data-testid='stMain']"),
              document.querySelector("[data-testid='stAppViewContainer'] section"),
              document.scrollingElement,
              document.documentElement
            ].filter(Boolean);
            let best = candidates[0] || document.documentElement;
            let bestRange = -1;
            for (const el of candidates) {
              const range = Number(el.scrollHeight || 0) - Number(el.clientHeight || 0);
              if (range > bestRange) {
                best = el;
                bestRange = range;
              }
            }
            return best;
          };
          const recordScroll = () => {
            const s = bestScroller();
            probe.scrollEvents.push({
              time: Date.now(),
              top: s ? Number(s.scrollTop || 0) : Number(window.scrollY || 0)
            });
            if (probe.scrollEvents.length > 120) probe.scrollEvents = probe.scrollEvents.slice(-120);
          };
          document.addEventListener("wheel", (ev) => {
            probe.wheelEvents.push({
              time: Date.now(),
              deltaY: Number(ev.deltaY || 0),
              defaultPrevented: !!ev.defaultPrevented,
              target: ev.target ? String(ev.target.tagName || "").toLowerCase() : null,
              targetClass: ev.target ? String(ev.target.className || "").slice(0, 120) : null
            });
            if (probe.wheelEvents.length > 120) probe.wheelEvents = probe.wheelEvents.slice(-120);
          }, {capture: true, passive: false});
          document.addEventListener("scroll", recordScroll, true);
        })();
        """
    )


def _snapshot_scroll(page, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const scroller = () => {
                const candidates = [
                  document.querySelector("section.stMain"),
                  document.querySelector("section[data-testid='stMain']"),
                  document.querySelector("[data-testid='stAppViewContainer'] section"),
                  document.scrollingElement,
                  document.documentElement
                ].filter(Boolean);
                let best = candidates[0] || document.documentElement;
                let bestRange = -1;
                for (const el of candidates) {
                  const range = Number(el.scrollHeight || 0) - Number(el.clientHeight || 0);
                  if (range > bestRange) {
                    best = el;
                    bestRange = range;
                  }
                }
                return best;
              };
              const s = scroller();
              const style = s ? window.getComputedStyle(s) : null;
              const bodyText = clean(document.body ? document.body.innerText : "");
              const transitionTexts = [
                "Checking design guidance",
                "Preparing current summary",
                "Applying one-click design"
              ].filter((text) => bodyText.indexOf(text) !== -1);
              const fixed = Array.from(document.querySelectorAll("body *")).filter((el) => {
                try {
                  const cs = window.getComputedStyle(el);
                  const rect = el.getBoundingClientRect();
                  return (cs.position === "fixed" || cs.position === "sticky")
                    && rect.width > 20
                    && rect.height > 20
                    && rect.bottom > 0
                    && rect.top < window.innerHeight;
                } catch (_err) {
                  return false;
                }
              }).slice(0, 12).map((el) => {
                const rect = el.getBoundingClientRect();
                const cs = window.getComputedStyle(el);
                return {
                  tag: String(el.tagName || "").toLowerCase(),
                  cls: String(el.className || "").slice(0, 120),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  position: cs.position,
                  pointerEvents: cs.pointerEvents,
                  overflow: cs.overflow,
                  top: Math.round(rect.top),
                  bottom: Math.round(rect.bottom),
                  height: Math.round(rect.height),
                  text: clean(el.innerText || el.textContent).slice(0, 120)
                };
              });
              const local = {};
              try {
                for (const key of [
                  "codex_dg_scroll_restore_v1",
                  "codex_inputs_scroll_restore_v1",
                  "codex_inputs_edit_scroll_anchor_v1"
                ]) {
                  local[key] = window.localStorage.getItem(key);
                }
              } catch (_err) {}
              const probe = window.__dgScrollLockProbe || {};
              return {
                label,
                captured_at_ms: Date.now(),
                performance_now_ms: Math.round(performance.now()),
                transition_texts: transitionTexts,
                top: s ? Math.round(Number(s.scrollTop || 0)) : Math.round(Number(window.scrollY || 0)),
                scroll_height: s ? Math.round(Number(s.scrollHeight || 0)) : 0,
                client_height: s ? Math.round(Number(s.clientHeight || 0)) : window.innerHeight,
                max_top: s ? Math.max(0, Math.round(Number(s.scrollHeight || 0) - Number(s.clientHeight || 0))) : 0,
                overflow_y: style ? style.overflowY : null,
                body_overflow_y: window.getComputedStyle(document.body).overflowY,
                html_overflow_y: window.getComputedStyle(document.documentElement).overflowY,
                fixed_or_sticky_visible: fixed,
                scroll_restore_storage: local,
                wheel_events_tail: Array.from(probe.wheelEvents || []).slice(-20),
                scroll_events_tail: Array.from(probe.scrollEvents || []).slice(-20),
                prevent_default_tail: Array.from(probe.preventDefaultCalls || []).slice(-20),
                body_text_sample: bodyText.slice(0, 220)
              };
            }
            """,
            label,
        )
        or {}
    )


def _scroll_to(page, top: int) -> None:
    page.evaluate(
        r"""
        (top) => {
          const candidates = [
            document.querySelector("section.stMain"),
            document.querySelector("section[data-testid='stMain']"),
            document.querySelector("[data-testid='stAppViewContainer'] section"),
            document.scrollingElement,
            document.documentElement
          ].filter(Boolean);
          let s = candidates[0] || document.documentElement;
          let bestRange = -1;
          for (const el of candidates) {
            const range = Number(el.scrollHeight || 0) - Number(el.clientHeight || 0);
            if (range > bestRange) {
              s = el;
              bestRange = range;
            }
          }
          if (s) s.scrollTop = Number(top || 0);
        }
        """,
        top,
    )


def _programmatic_scroll_by(page, delta: int) -> None:
    page.evaluate(
        r"""
        (delta) => {
          const candidates = [
            document.querySelector("section.stMain"),
            document.querySelector("section[data-testid='stMain']"),
            document.querySelector("[data-testid='stAppViewContainer'] section"),
            document.scrollingElement,
            document.documentElement
          ].filter(Boolean);
          let s = candidates[0] || document.documentElement;
          let bestRange = -1;
          for (const el of candidates) {
            const range = Number(el.scrollHeight || 0) - Number(el.clientHeight || 0);
            if (range > bestRange) {
              s = el;
              bestRange = range;
            }
          }
          if (s) s.scrollTop = Number(s.scrollTop || 0) + Number(delta || 0);
        }
        """,
        delta,
    )


def _seed_restore_payload(page, target_top: int) -> None:
    page.evaluate(
        r"""
        (targetTop) => {
          const payload = JSON.stringify({
            scrollTop: Number(targetTop || 0),
            scrollHeight: 4000,
            clientHeight: 900,
            routeKey: "inputs",
            label: "Active beam",
            rectTop: 240,
            reason: "scroll_lock_profile_seed",
            until: Date.now() + 12000
          });
          try {
            window.localStorage.setItem("codex_inputs_edit_scroll_anchor_v1", payload);
            window.localStorage.setItem("codex_inputs_scroll_restore_v1", JSON.stringify({
              scrollTop: Number(targetTop || 0),
              until: Date.now() + 12000,
              reason: "scroll_lock_profile_seed"
            }));
          } catch (_err) {}
        }
        """,
        target_top,
    )


def _classify(snapshots: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    by_label = {str(row.get("label")): dict(row or {}) for row in snapshots}
    before = by_label.get(f"{mode}_before_wheel_up") or {}
    after_wheel = by_label.get(f"{mode}_after_wheel_up") or {}
    after_programmatic = by_label.get(f"{mode}_after_programmatic_up") or {}
    before_top = int(before.get("top") or 0)
    wheel_top = int(after_wheel.get("top") or 0)
    programmatic_top = int(after_programmatic.get("top") or 0)
    wheel_moved_up_px = before_top - wheel_top
    programmatic_moved_up_px = wheel_top - programmatic_top
    wheel_up_locked = before_top > 120 and wheel_moved_up_px < 60
    programmatic_up_works = programmatic_moved_up_px >= 120
    storage_active = any(
        bool((row.get("scroll_restore_storage") or {}).get(key))
        for row in snapshots
        for key in (
            "codex_dg_scroll_restore_v1",
            "codex_inputs_scroll_restore_v1",
            "codex_inputs_edit_scroll_anchor_v1",
        )
    )
    transition_active = any(row.get("transition_texts") for row in snapshots)
    prevented = sum(len(row.get("prevent_default_tail") or []) for row in snapshots)
    return {
        "mode": mode,
        "before_top": before_top,
        "after_wheel_top": wheel_top,
        "after_programmatic_top": programmatic_top,
        "wheel_moved_up_px": wheel_moved_up_px,
        "programmatic_moved_up_px": programmatic_moved_up_px,
        "wheel_up_locked": wheel_up_locked,
        "programmatic_up_works": programmatic_up_works,
        "scroll_restore_storage_active": storage_active,
        "transition_text_active": transition_active,
        "prevent_default_call_count_tail_sum": prevented,
        "likely_cause": (
            "scroll restoration loop overriding upward wheel movement"
            if wheel_up_locked and storage_active
            else (
                "event interception or overlay preventing wheel scroll"
                if wheel_up_locked and programmatic_up_works
                else (
                    "scroll container not scrollable during sampled loading window"
                    if wheel_up_locked
                    else "wheel scroll-up was not locked in this sampled window"
                )
            )
        ),
    }


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Loading Scroll-Lock Profile",
        "",
        f"Status: `{payload['status']}`",
        f"Target URL: `{payload['target_url']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Classification",
        "",
        "| Mode | Before | After wheel | After programmatic | Wheel moved up | Programmatic moved up | Locked | Likely cause |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload.get("classifications") or []:
        row = dict(row or {})
        lines.append(
            f"| `{row.get('mode')}` | `{row.get('before_top')}` | `{row.get('after_wheel_top')}` | `{row.get('after_programmatic_top')}` | `{row.get('wheel_moved_up_px')}` | `{row.get('programmatic_moved_up_px')}` | `{row.get('wheel_up_locked')}` | {_escape_md(str(row.get('likely_cause') or ''))} |"
        )
    lines.extend(["", "## Snapshot Labels", ""])
    for row in payload.get("snapshots") or []:
        row = dict(row or {})
        lines.append(
            f"- `{row.get('label')}`: top=`{row.get('top')}`, max=`{row.get('max_top')}`, transitions=`{row.get('transition_texts')}`"
        )
    lines.extend(["", "## Recommendation", "", str(payload.get("recommended_next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_profile(page, target_url: str, *, seed_restore: bool) -> list[dict[str, Any]]:
    mode = "seeded_restore" if seed_restore else "plain_load"
    page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
    if seed_restore:
        _seed_restore_payload(page, 900)
        page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
    snapshots = [_snapshot_scroll(page, f"{mode}_after_domcontentloaded")]
    wait_started = time.perf_counter()
    while time.perf_counter() - wait_started <= 8.0:
        sample = _snapshot_scroll(page, f"{mode}_scrollability_probe")
        snapshots.append(sample)
        if int(sample.get("max_top") or 0) >= 240:
            break
        page.wait_for_timeout(250)
    max_top = int(snapshots[-1].get("max_top") or 0)
    target_top = min(max(700, int(max_top * 0.55)), max_top)
    if target_top > 120:
        _scroll_to(page, target_top)
    page.wait_for_timeout(120)
    snapshots.append(_snapshot_scroll(page, f"{mode}_before_wheel_up"))
    page.mouse.move(960, 760)
    page.wait_for_timeout(40)
    page.mouse.wheel(0, -650)
    page.wait_for_timeout(300)
    snapshots.append(_snapshot_scroll(page, f"{mode}_after_wheel_up"))
    _programmatic_scroll_by(page, -650)
    page.wait_for_timeout(160)
    snapshots.append(_snapshot_scroll(page, f"{mode}_after_programmatic_up"))
    return snapshots


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    recipe = os.environ.get("DESIGN_GUIDE_SCROLL_PROFILE_RECIPE") or DEFAULT_RECIPE
    explicit_url = (os.environ.get("DESIGN_GUIDE_SCROLL_PROFILE_URL") or "").strip()
    port = int(os.environ.get("DESIGN_GUIDE_SCROLL_PROFILE_PORT") or "8542")
    base_url = f"http://127.0.0.1:{port}"
    target_url = explicit_url or _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    process: subprocess.Popen | None = None
    snapshots: list[dict[str, Any]] = []
    errors: list[str] = []
    started_own_server = False

    try:
        if not explicit_url:
            started_own_server = True
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["CODEX_RENDER_TIMING_TRACE"] = "1"
            os.environ["AUTO_DESIGN_SPEED_PROFILE"] = "1"
            try:
                process = _start_streamlit(port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            _install_scroll_probe(context)
            page = context.new_page()
            page.set_default_timeout(30_000)
            snapshots.extend(_run_profile(page, target_url, seed_restore=False))
            snapshots.extend(_run_profile(page, target_url, seed_restore=True))
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

    classifications = [
        _classify([row for row in snapshots if str(row.get("label") or "").startswith("plain_load_")], "plain_load"),
        _classify([row for row in snapshots if str(row.get("label") or "").startswith("seeded_restore_")], "seeded_restore"),
    ]
    supporting_artifacts = {
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "design_guide_independence_lock": _latest("design_guide_independence_lock"),
    }
    failures: list[str] = []
    if not snapshots:
        failures.append("no_scroll_snapshots")
    for name, artifact in supporting_artifacts.items():
        if artifact.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    if errors:
        failures.extend(f"browser_error::{error}" for error in errors)
    status = "PASS" if not failures else "FAIL"
    locked_modes = [row for row in classifications if row.get("wheel_up_locked")]
    recommended = (
        "Gate scroll restoration so it pauses or clears when the user wheels upward during loading."
        if any(row.get("scroll_restore_storage_active") for row in locked_modes)
        else (
            "Inspect overlay/event interception before changing restoration logic."
            if locked_modes
            else "No scroll-up lock reproduced in this profile; rerun against the live tab URL if the symptom persists."
        )
    )
    payload: dict[str, Any] = {
        "schema": "design_guide_loading_scroll_lock_profile.v1",
        "status": status,
        "created_at": stamp,
        "recipe": recipe,
        "target_url": target_url,
        "started_own_server": started_own_server,
        "product_behaviour_changed": False,
        "scroll_logic_changed": False,
        "snapshots": snapshots,
        "classifications": classifications,
        "supporting_artifacts": supporting_artifacts,
        "recommended_next_step": recommended,
        "errors": errors,
        "failures": failures,
    }
    payload["profile_hash"] = _stable_hash(
        {
            "target_url": target_url,
            "snapshots": snapshots,
            "classifications": classifications,
            "errors": errors,
        }
    )
    artifact_path = ARTIFACT_DIR / f"design_guide_loading_scroll_lock_profile_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_loading_scroll_lock_profile_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(json.dumps({"status": status, "artifact": str(artifact_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
