"""Browser/live stable rerun shell visibility snapshot.

This proof checks whether the Inputs stable rerun shell is actually layout
visible, or only present as hidden DOM text. It is proof-only and does not
change page rendering, publication, CTA/apply, family runtimes, or wording.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _snapshot(page, *, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const shell = document.querySelector('[data-testid="inputs-root-dispatch-stable-shell"]');
              const stylePayload = (el) => {
                if (!el || !el.getBoundingClientRect) {
                  return {exists: false};
                }
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return {
                  exists: true,
                  text: clean(el.innerText || el.textContent),
                  rect: {
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom),
                    left: Math.round(rect.left),
                    right: Math.round(rect.right),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                  },
                  computed: {
                    display: style.display,
                    visibility: style.visibility,
                    opacity: style.opacity,
                    overflow: style.overflow,
                    pointerEvents: style.pointerEvents,
                    userSelect: style.userSelect,
                    height: style.height,
                    minHeight: style.minHeight,
                    marginTop: style.marginTop,
                    marginBottom: style.marginBottom,
                    paddingTop: style.paddingTop,
                    paddingBottom: style.paddingBottom
                  },
                  layout_visible: style.display !== "none"
                    && style.visibility !== "hidden"
                    && Number(style.opacity || "1") > 0.02
                    && rect.width > 1
                    && rect.height > 1
                };
              };
              const bodyText = clean(document.body ? document.body.innerText : "");
              return {
                label,
                timestamp_ms: Date.now(),
                performance_now_ms: Math.round(performance.now()),
                shell: stylePayload(shell),
                body_text_has_shell: /Inputs page stable rerun shell/i.test(bodyText),
                body_text_length: bodyText.length,
                scroll: {
                  y: Math.round(window.scrollY || 0),
                  bodyHeight: Math.round(document.body ? document.body.scrollHeight : 0),
                  viewportHeight: Math.round(window.innerHeight || 0)
                }
              };
            }
            """,
            label,
        )
        or {}
    )


def _capture(base_url: str, *, recipe: str, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        snapshots: list[dict[str, Any]] = []
        for label, wait_ms in (
            ("initial", 500),
            ("settled", 3000),
            ("stable_rerun_triggered", 0),
            ("after_stable_rerun", 2500),
        ):
            if label == "stable_rerun_triggered":
                page.reload(wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(500)
            else:
                page.wait_for_timeout(wait_ms)
            snapshots.append(_snapshot(page, label=label))
        browser.close()
        return {"url": url, "recipe": recipe, "snapshots": snapshots}


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    snapshots = list(capture.get("snapshots") or [])
    shell_seen = any(((snap.get("shell") or {}).get("exists")) for snap in snapshots)
    shell_text_seen = any(bool(snap.get("body_text_has_shell")) for snap in snapshots)
    layout_visible = any(bool((snap.get("shell") or {}).get("layout_visible")) for snap in snapshots)
    nonzero_height = max(
        [
            int((((snap.get("shell") or {}).get("rect") or {}).get("height")) or 0)
            for snap in snapshots
        ],
        default=0,
    )
    if layout_visible or nonzero_height > 1:
        diagnosis = "STABLE_RERUN_SHELL_LAYOUT_VISIBLE"
        next_slice = "Make the stable rerun shell zero-layout or bypass it on stable publication/display hashes."
    elif shell_text_seen or shell_seen:
        diagnosis = "STABLE_RERUN_SHELL_HIDDEN_DOM_TEXT_ONLY"
        next_slice = "Update rerun-cause profiling to ignore hidden stable-shell text and profile the next visible layout shift source."
    else:
        diagnosis = "STABLE_RERUN_SHELL_NOT_OBSERVED"
        next_slice = "Profile page-content-slot clearing and summary placeholder height directly."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "shell_seen": shell_seen,
        "shell_text_seen": shell_text_seen,
        "layout_visible": layout_visible,
        "max_shell_height_px": nonzero_height,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Stable Rerun Shell Visibility Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Shell seen: `{cls.get('shell_seen')}`",
        f"- Shell text seen: `{cls.get('shell_text_seen')}`",
        f"- Layout visible: `{cls.get('layout_visible')}`",
        f"- Max shell height: `{cls.get('max_shell_height_px')}` px",
        "",
        "## Recommendation",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
        "## Samples",
        "",
    ]
    for snap in payload.get("snapshots") or []:
        shell = dict(snap.get("shell") or {})
        computed = dict(shell.get("computed") or {})
        rect = dict(shell.get("rect") or {})
        lines.append(
            f"- `{snap.get('label')}` exists `{shell.get('exists')}`, "
            f"layout `{shell.get('layout_visible')}`, height `{rect.get('height')}`, "
            f"opacity `{computed.get('opacity')}`, overflow `{computed.get('overflow')}`"
        )
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_stable_rerun_shell_visibility_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_stable_rerun_shell_visibility_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8606)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_STABLE_SHELL_URL"))
    parser.add_argument("--recipe", default="PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=60.0)
        capture = _capture(base_url, recipe=str(args.recipe), headed=bool(args.headed))
        classification = _classify(capture)
        payload = {
            "created_at": created_at,
            "status": classification.get("status"),
            "product_behaviour_changed": False,
            "base_url": base_url,
            "recipe": args.recipe,
            "classification": classification,
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], "diagnosis": classification.get("diagnosis")}, indent=2))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
