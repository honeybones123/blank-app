"""App-wide stability baseline inventory.

Phase 1 proof for the stability goal. This script does not change product
behaviour. It inventories router pages, source-level instability risks, and
browser-visible first-load stability for the main Streamlit pages.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

WIDGET_CALL_RE = re.compile(
    r"\bst\.(button|download_button|form_submit_button|text_input|number_input|"
    r"selectbox|multiselect|radio|checkbox|toggle|slider|tabs|expander|"
    r"data_editor|file_uploader|text_area)\s*\(",
)
KEY_RE = re.compile(r"\bkey\s*=\s*([\"'])(?P<key>.+?)\1")
SESSION_WRITE_RE = re.compile(r"st\.session_state\s*(?:\[|\.)")
SESSION_ASSIGN_RE = re.compile(r"st\.session_state\s*(?:\[[^\]]+\]|\.[A-Za-z_][A-Za-z0-9_]*)\s*=")
PLACEHOLDER_CLEAR_RE = re.compile(r"\.(?:empty|clear)\s*\(")
CONTAINER_RECREATE_RE = re.compile(r"\bst\.(?:empty|container|columns|tabs|expander)\s*\(")
RERUN_RE = re.compile(r"\bst\.rerun\s*\(")
CALLBACK_RE = re.compile(r"\bon_(?:click|change)\s*=")
CALC_ENTRY_RE = re.compile(
    r"\b(?:run_|evaluate_|calc_|calculate_|classify_|publish_|family_strategy_for|"
    r"run_design|run_bending|run_shear|run_deflection)[A-Za-z0-9_]*\s*\(",
)

PAGE_FILE_HINTS: dict[str, tuple[str, ...]] = {
    "inputs": ("inputs_page.py", "design_guide_page.py", "ui/summary_cards.py", "batch_design/ui/page.py"),
    "design": ("sfd_bmd_page.py", "beam_analysis.py"),
    "bending": ("bending_page.py", "bending_core.py", "bending_diagrams.py"),
    "shear": ("shear_page.py", "shear_core.py", "shear_diagrams.py"),
    "creep": ("creep.py",),
    "shrinkage": ("shrinkage.py",),
    "crack": ("crack_page.py", "crack_core.py"),
    "deflection": ("deflection.py", "deflection_core.py"),
}
SHARED_FILES = (
    "app.py",
    "state_and_helpers.py",
    "design_guide_page.py",
    "ui/final_design_guide_card.py",
    "ui/summary_cards.py",
    "ui/summary_sections.py",
    "batch_design/ui/page.py",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({k: v for k, v in params.items() if v is not None})}"


def _wait_for_http(url: str, timeout_s: float = 20.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2.0) as response:  # noqa: S310 - localhost verifier
                return 200 <= int(response.status) < 500
        except Exception:
            time.sleep(0.3)
    return False


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return ""


def _file_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _extract_pages() -> list[dict[str, Any]]:
    source = _safe_read(ROOT / "app.py")
    marker = "PAGES = {"
    start = source.find(marker)
    if start < 0:
        return []
    end = source.find("\n}\n\nSLUGS", start)
    block = source[start : end + 3] if end > start else source[start : start + 2000]
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r"[\"'](?P<slug>[a-z_]+)[\"']\s*:\s*\(\s*[\"'](?P<label>[^\"']+)[\"']", block):
        slug = match.group("slug")
        rows.append(
            {
                "slug": slug,
                "label": match.group("label"),
                "source_files": list(PAGE_FILE_HINTS.get(slug, ())),
                "route_declared_in": "app.py",
            }
        )
    return rows


def _function_names_for_file(path: Path) -> list[str]:
    source = _safe_read(path)
    if not source:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _source_inventory_for_file(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    source = _safe_read(path)
    if not source:
        return {
            "file": relative,
            "exists": False,
        }
    widget_calls = WIDGET_CALL_RE.findall(source)
    widget_keys = KEY_RE.findall(source)
    keys = [match[1] if isinstance(match, tuple) else str(match) for match in widget_keys]
    duplicate_keys = sorted({key for key in keys if keys.count(key) > 1})
    session_mentions = len(SESSION_WRITE_RE.findall(source))
    session_writes = len(SESSION_ASSIGN_RE.findall(source))
    return {
        "file": relative,
        "exists": True,
        "line_count": source.count("\n") + 1,
        "source_hash": _file_hash(source),
        "render_functions": [name for name in _function_names_for_file(path) if name.startswith("render") or name.startswith("_render")][:60],
        "widget_count": len(widget_calls),
        "widget_types": dict(sorted({name: widget_calls.count(name) for name in set(widget_calls)}.items())),
        "widget_key_count": len(keys),
        "duplicate_literal_widget_keys": duplicate_keys[:40],
        "session_state_mentions": session_mentions,
        "approx_session_state_writes": session_writes,
        "explicit_st_rerun_calls": len(RERUN_RE.findall(source)),
        "callback_bindings": len(CALLBACK_RE.findall(source)),
        "placeholder_clear_calls": len(PLACEHOLDER_CLEAR_RE.findall(source)),
        "container_or_placeholder_calls": len(CONTAINER_RECREATE_RE.findall(source)),
        "approx_engineering_entry_calls": len(CALC_ENTRY_RE.findall(source)),
    }


def _source_inventory(pages: list[dict[str, Any]]) -> dict[str, Any]:
    files = set(SHARED_FILES)
    for page in pages:
        files.update(page.get("source_files") or [])
    rows = [_source_inventory_for_file(relative) for relative in sorted(files)]
    return {
        "files": rows,
        "shared_files": list(SHARED_FILES),
    }


def _install_layout_probe(context) -> None:
    context.add_init_script(
        """
        (() => {
          window.__appStabilityProbe = {
            startedAt: Date.now(),
            layoutShiftTotal: 0,
            layoutShiftEntries: [],
            paints: []
          };
          try {
            new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                if (entry.hadRecentInput) continue;
                window.__appStabilityProbe.layoutShiftTotal += Number(entry.value || 0);
                window.__appStabilityProbe.layoutShiftEntries.push({
                  value: Number(entry.value || 0),
                  startTime: Number(entry.startTime || 0)
                });
              }
            }).observe({type: "layout-shift", buffered: true});
          } catch (_err) {}
          try {
            new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                window.__appStabilityProbe.paints.push({
                  name: entry.name,
                  startTime: Number(entry.startTime || 0)
                });
              }
            }).observe({type: "paint", buffered: true});
          } catch (_err) {}
        })();
        """
    )


def _browser_probe_script() -> str:
    return """
    () => {
      const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
      const visible = (el) => {
        if (!el || !el.getBoundingClientRect) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 2 && rect.height > 2;
      };
      const hash = (value) => {
        const text = String(value || "");
        let h = 2166136261;
        for (let i = 0; i < text.length; i += 1) {
          h ^= text.charCodeAt(i);
          h = Math.imul(h, 16777619);
        }
        return (h >>> 0).toString(16);
      };
      const bodyText = clean(document.body ? document.body.innerText : "");
      const headings = Array.from(document.querySelectorAll("h1,h2,h3,[role='heading']"))
        .filter(visible)
        .slice(0, 20)
        .map((el) => {
          const rect = el.getBoundingClientRect();
          return {text: clean(el.innerText || el.textContent).slice(0, 120), top: Math.round(rect.top), height: Math.round(rect.height)};
        });
      const widgets = Array.from(document.querySelectorAll("button,input,select,textarea,[role='button'],[role='tab']"))
        .filter(visible)
        .slice(0, 250)
        .map((el) => ({
          tag: String(el.tagName || "").toLowerCase(),
          role: el.getAttribute("role"),
          type: el.getAttribute("type"),
          text: clean(el.innerText || el.getAttribute("aria-label") || el.value || el.textContent).slice(0, 80),
          keyHint: el.getAttribute("data-testid") || el.getAttribute("aria-label") || el.getAttribute("id")
        }));
      const browserStateEls = Array.from(document.querySelectorAll("textarea[aria-label='Browser state'], [aria-label='Browser state']"));
      let browserState = null;
      for (const el of browserStateEls) {
        const raw = "value" in el ? el.value : el.textContent;
        if (raw && raw.trim()) {
          try { browserState = JSON.parse(raw); break; } catch (_err) {}
        }
      }
      const probe = window.__appStabilityProbe || {};
      return {
        url: location.href,
        scrollY: Math.round(window.scrollY || 0),
        viewport: {width: window.innerWidth, height: window.innerHeight},
        bodyTextLength: bodyText.length,
        bodyTextHash: hash(bodyText),
        blankLike: bodyText.length < 80,
        headings,
        widgetCount: widgets.length,
        widgetsSample: widgets.slice(0, 30),
        designGuidePresent: /Design Guide/i.test(bodyText),
        summaryPresent: /(Bending|Shear).*?(PASS|FAIL|CAPACITY|NEAR LIMIT)/i.test(bodyText),
        loadingShellPresent: /Checking design guidance|Reviewing strength, detailing, serviceability/i.test(bodyText),
        layoutShiftTotal: Number(probe.layoutShiftTotal || 0),
        layoutShiftCount: Array.isArray(probe.layoutShiftEntries) ? probe.layoutShiftEntries.length : 0,
        paintEntries: Array.isArray(probe.paints) ? probe.paints : [],
        browserState: browserState
      };
    }
    """


def _probe_page(page, slug: str, label: str, base_url: str, settle_ms: int) -> dict[str, Any]:
    url = _query(base_url, {"page": slug, "stability_baseline": "1"})
    started = time.perf_counter()
    errors: list[str] = []
    first_snapshot: dict[str, Any] | None = None
    final_snapshot: dict[str, Any] | None = None
    domcontentloaded_ms: float | None = None
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        domcontentloaded_ms = round((time.perf_counter() - started) * 1000.0, 3)
        if response is not None and getattr(response, "status", None) and int(response.status) >= 500:
            errors.append(f"http_status_{response.status}")
    except Exception as exc:
        errors.append(f"goto_failed:{type(exc).__name__}:{exc}")
    try:
        first_snapshot = dict(page.evaluate(_browser_probe_script()))
    except Exception as exc:
        errors.append(f"first_snapshot_failed:{type(exc).__name__}:{exc}")
    try:
        page.wait_for_timeout(max(100, int(settle_ms)))
        final_snapshot = dict(page.evaluate(_browser_probe_script()))
    except Exception as exc:
        errors.append(f"final_snapshot_failed:{type(exc).__name__}:{exc}")

    browser_state = dict((final_snapshot or {}).get("browserState") or {})
    timing = dict(browser_state.get("render_timing") or browser_state.get("timing") or {})
    timing_events = list(timing.get("recent_events") or browser_state.get("render_timing_events") or [])
    counts = dict(timing.get("counts") or {})
    source_probe = dict(browser_state.get("browser_shared_probe") or {})
    result = {
        "slug": slug,
        "label": label,
        "url": url,
        "domcontentloaded_ms": domcontentloaded_ms,
        "total_probe_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "errors": errors,
        "first": first_snapshot,
        "final": final_snapshot,
        "blanking_detected": bool((first_snapshot or {}).get("blankLike")) or bool((final_snapshot or {}).get("blankLike")),
        "loading_shell_visible_after_settle": bool((final_snapshot or {}).get("loadingShellPresent")),
        "layout_shift_total": float((final_snapshot or {}).get("layoutShiftTotal") or 0.0),
        "layout_shift_count": int((final_snapshot or {}).get("layoutShiftCount") or 0),
        "scroll_y_after_settle": int((final_snapshot or {}).get("scrollY") or 0),
        "browser_state_available": bool(browser_state),
        "render_timing_rerun_seq": timing.get("rerun_seq") or browser_state.get("rerun_seq"),
        "render_timing_count_names": sorted(counts.keys())[:80],
        "render_timing_recent_events_count": len(timing_events),
        "browser_shared_probe_keys": sorted(source_probe.keys())[:80],
    }
    return result


def _live_inventory(base_url: str, pages: list[dict[str, Any]], *, settle_ms: int, headless: bool) -> dict[str, Any]:
    if not _wait_for_http(base_url):
        return {
            "executed": False,
            "reason": f"base_url_unavailable:{base_url}",
            "pages": [],
        }
    rows: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        _install_layout_probe(context)
        page = context.new_page()
        for row in pages:
            rows.append(_probe_page(page, str(row["slug"]), str(row["label"]), base_url, settle_ms))
        browser.close()
    return {
        "executed": True,
        "base_url": base_url,
        "settle_ms": settle_ms,
        "pages": rows,
    }


def _risk_score(page: dict[str, Any], source_rows: list[dict[str, Any]]) -> int:
    score = 0
    if page.get("blanking_detected"):
        score += 4
    if page.get("loading_shell_visible_after_settle"):
        score += 3
    if float(page.get("layout_shift_total") or 0.0) > 0.02:
        score += 2
    if page.get("errors"):
        score += 5
    for source in source_rows:
        score += min(4, int(source.get("explicit_st_rerun_calls") or 0))
        score += min(4, int(source.get("placeholder_clear_calls") or 0) // 3)
        score += min(4, int(source.get("approx_engineering_entry_calls") or 0) // 80)
        if source.get("duplicate_literal_widget_keys"):
            score += 2
    return score


def _classify_risks(pages: list[dict[str, Any]], source: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    source_by_file = {row["file"]: row for row in source.get("files") or [] if row.get("exists")}
    live_by_slug = {row["slug"]: row for row in live.get("pages") or []}
    rows = []
    for page in pages:
        source_rows = [source_by_file[file] for file in page.get("source_files") or [] if file in source_by_file]
        live_row = live_by_slug.get(page["slug"], {})
        score = _risk_score(live_row, source_rows)
        causes: list[str] = []
        if live_row.get("blanking_detected"):
            causes.append("browser blank-like render sample")
        if live_row.get("loading_shell_visible_after_settle"):
            causes.append("loading shell visible after settle")
        if live_row.get("layout_shift_total", 0) and float(live_row.get("layout_shift_total") or 0) > 0.02:
            causes.append("layout shift observed")
        reruns = sum(int(item.get("explicit_st_rerun_calls") or 0) for item in source_rows)
        if reruns:
            causes.append(f"{reruns} explicit st.rerun call(s) in page/source files")
        clears = sum(int(item.get("placeholder_clear_calls") or 0) for item in source_rows)
        if clears:
            causes.append(f"{clears} placeholder clear/empty call(s)")
        entry_calls = sum(int(item.get("approx_engineering_entry_calls") or 0) for item in source_rows)
        if entry_calls > 100:
            causes.append(f"{entry_calls} approximate engineering/publication entry calls")
        rows.append(
            {
                "slug": page["slug"],
                "label": page["label"],
                "risk_score": score,
                "likely_causes": causes,
                "live": live_row,
                "source_files": source_rows,
            }
        )
    shared_rows = [source_by_file[file] for file in source.get("shared_files") or [] if file in source_by_file]
    shared_causes = []
    for item in shared_rows:
        if int(item.get("explicit_st_rerun_calls") or 0):
            shared_causes.append({"file": item["file"], "cause": "explicit_st_rerun", "count": item["explicit_st_rerun_calls"]})
        if int(item.get("placeholder_clear_calls") or 0):
            shared_causes.append({"file": item["file"], "cause": "placeholder_clear", "count": item["placeholder_clear_calls"]})
        if int(item.get("approx_engineering_entry_calls") or 0) > 100:
            shared_causes.append({"file": item["file"], "cause": "many_engineering_entry_calls", "count": item["approx_engineering_entry_calls"]})
    return {
        "page_risks": sorted(rows, key=lambda row: row["risk_score"], reverse=True),
        "shared_infrastructure_risks": shared_causes,
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    risks = payload.get("risk_classification") or {}
    lines = [
        "# App Stability Baseline Inventory",
        "",
        f"Status: `{payload.get('status')}`",
        f"Generated: `{payload.get('timestamp')}`",
        "",
        "## Scope",
        "",
        "This is a proof-only Phase 1 baseline. It does not change product behaviour.",
        "",
        "## Pages",
        "",
        "| Page | Risk | Live blanking | Loading shell after settle | Layout shift | Browser state | Main causes |",
        "| --- | ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in risks.get("page_risks") or []:
        live = row.get("live") or {}
        causes = "; ".join(row.get("likely_causes") or []) or "none recorded"
        lines.append(
            "| {label} (`{slug}`) | {risk} | {blank} | {loading} | {shift:.4f} | {state} | {causes} |".format(
                label=row.get("label"),
                slug=row.get("slug"),
                risk=row.get("risk_score"),
                blank=bool(live.get("blanking_detected")),
                loading=bool(live.get("loading_shell_visible_after_settle")),
                shift=float(live.get("layout_shift_total") or 0.0),
                state=bool(live.get("browser_state_available")),
                causes=causes.replace("|", "/"),
            )
        )
    lines.extend(["", "## Shared Root-Cause Candidates", ""])
    shared = risks.get("shared_infrastructure_risks") or []
    if not shared:
        lines.append("- None detected by this baseline.")
    else:
        for item in shared:
            lines.append(f"- `{item.get('file')}`: `{item.get('cause')}` count `{item.get('count')}`")
    lines.extend(
        [
            "",
            "## Highest-Risk Next Slice",
            "",
            str(payload.get("recommended_next_slice") or "No recommendation produced."),
            "",
            "## Notes",
            "",
            "- Live browser metrics are baseline measurements, not pass/fail stability locks yet.",
            "- Source counts are approximate static signals used to prioritize deeper workflow tracing.",
            "- The next phase should trace one high-value workflow end-to-end before changing behaviour.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8504")
    parser.add_argument("--settle-ms", type=int, default=2500)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    pages = _extract_pages()
    source = _source_inventory(pages)
    live = _live_inventory(args.base_url, pages, settle_ms=args.settle_ms, headless=not args.headed)
    risks = _classify_risks(pages, source, live)
    top = (risks.get("page_risks") or [{}])[0]
    top_causes = top.get("likely_causes") or []
    recommended = (
        f"Trace `{top.get('label')}` (`{top.get('slug')}`) first because it has the highest baseline risk "
        f"score `{top.get('risk_score')}`. Focus on: {', '.join(top_causes[:3]) or 'workflow-level rerun/layout evidence'}."
    )
    payload = {
        "schema": "app_stability_baseline_inventory.v1",
        "status": "PASS",
        "timestamp": _stamp(),
        "base_url": args.base_url,
        "pages": pages,
        "source_inventory": source,
        "live_inventory": live,
        "risk_classification": risks,
        "recommended_next_slice": recommended,
        "product_behaviour_changed": False,
    }
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"app_stability_baseline_inventory_{stamp}.json"
    md_path = AUDIT_DIR / f"app_stability_baseline_inventory_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_markdown(payload, md_path)
    print("app_stability_baseline_inventory PASS")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
