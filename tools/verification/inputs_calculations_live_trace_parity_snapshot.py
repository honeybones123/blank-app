"""Browser/live trace proof for Inputs calculation/explainer view-model parity.

This verifier starts a temporary Streamlit server with PERF_TRACE_INPUTS=1,
opens the Inputs page, and reads the emitted pre-widget JSONL trace. It does
not change product behaviour, visible wording, engineering calculations, or
the live renderer.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time
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
PERF_DIR = ROOT / "artifacts" / "performance"
TRACE_BLOCK = "inputs_calculation_explainer_view_model_trace"
EXPECTED_ORDER = ("bending", "shear", "crack", "deflection")


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _trace_files() -> set[Path]:
    if not PERF_DIR.exists():
        return set()
    return set(PERF_DIR.glob("inputs_pre_widget_trace_*.jsonl"))


def _load_trace_rows(paths: set[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.stat().st_mtime):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            row["_trace_path"] = str(path)
            rows.append(row)
    return rows


def _wait_for_trace(paths_before: set[Path], *, timeout_s: float) -> dict[str, Any] | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        paths_now = _trace_files()
        candidate_paths = paths_now - paths_before
        if not candidate_paths:
            candidate_paths = paths_now
        rows = [
            row for row in _load_trace_rows(candidate_paths)
            if row.get("block") == TRACE_BLOCK
        ]
        if rows:
            return rows[-1]
        time.sleep(0.5)
    return None


def _classify(trace: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(trace, dict):
        return {
            "status": "FAIL",
            "decision": "LIVE_CALCULATION_TRACE_MISSING",
            "failures": ["trace_missing"],
        }
    source_counts = dict(trace.get("live_calculation_explainer_source_row_counts") or {})
    extracted_counts = dict(trace.get("extracted_calculation_explainer_row_counts") or {})
    order = tuple(str(value) for value in list(trace.get("extracted_calculation_explainer_card_order") or []))
    checks = {
        "trace_built": bool(trace.get("calculation_explainer_view_model_trace_built")),
        "trace_only": bool(trace.get("calculation_explainer_view_model_trace_only")),
        "renderer_not_cut_over": trace.get("live_calculation_explainer_renderer_cutover") is False,
        "source_hash_present": bool(str(trace.get("calculation_explainer_source_hash") or "").strip()),
        "view_model_hash_present": bool(str(trace.get("extracted_calculation_explainer_view_model_hash") or "").strip()),
        "card_count_four": int(trace.get("extracted_calculation_explainer_card_count") or 0) == 4,
        "card_order_fixed": order == EXPECTED_ORDER,
        "row_counts_match": source_counts == extracted_counts,
        "row_count_keys_fixed": tuple(source_counts.keys()) == EXPECTED_ORDER,
    }
    failures = [key for key, value in checks.items() if not value]
    return {
        "status": "PASS" if not failures else "FAIL",
        "decision": "READY_FOR_CALCULATION_STATE_EXTRACTION" if not failures else "LIVE_CALCULATION_PARITY_GAPS_REMAIN",
        "checks": checks,
        "failures": failures,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"inputs_calculations_live_trace_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"inputs_calculations_live_trace_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Inputs Calculations Live Trace Parity Snapshot",
        "",
        f"## Executive Summary: {payload['classification']['decision']}",
        "",
        f"- Status: `{payload['classification']['status']}`",
        f"- Trace found: `{payload['trace_found']}`",
        f"- Product behavior changed: `{payload['product_behavior_changed']}`",
        f"- Live renderer switched: `{payload['live_renderer_switched']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(payload["classification"].get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["classification"].get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["classification"]["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8617)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--recipe", default="R1A_M300_V0")
    parser.add_argument("--timeout-s", type=float, default=75.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    created_at = _stamp()
    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    paths_before = _trace_files()
    env_before = dict(os.environ)
    try:
        if not args.base_url:
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["PERF_TRACE_INPUTS"] = "1"
            process = _start_streamlit(int(args.port))
            _wait_for_http(base_url, timeout_s=60.0)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not bool(args.headed))
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1100})
                url = _query(
                    base_url,
                    {
                        "page": "inputs",
                        "browser_recipe": str(args.recipe),
                        "batch_design_open": "0",
                    },
                )
                page.goto(url, wait_until="domcontentloaded", timeout=int(args.timeout_s * 1000))
                page.wait_for_timeout(3500)
            finally:
                browser.close()
        trace = _wait_for_trace(paths_before, timeout_s=float(args.timeout_s))
        classification = _classify(trace)
        payload = {
            "created_at": created_at,
            "base_url": base_url,
            "recipe": args.recipe,
            "trace_found": isinstance(trace, dict),
            "trace": trace,
            "classification": classification,
            "product_behavior_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "live_renderer_switched": False,
        }
        json_path, report_path = _write(payload)
        print("inputs_calculations_live_trace_parity_snapshot", classification["status"])
        print(f"decision={classification['decision']}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 0 if classification["status"] == "PASS" else 1
    finally:
        os.environ.clear()
        os.environ.update(env_before)
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
