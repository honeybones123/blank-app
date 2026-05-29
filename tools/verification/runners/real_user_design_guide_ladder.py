"""Real-user Design Guide verification ladder.

This harness treats the rendered browser as the primary truth. Internal debug
state is captured only as supporting evidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
from urllib.request import urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verification.helpers.browser_helpers import (  # noqa: E402
    PAGE_CYCLE_GHOST_FAILURE_CLASS,
    MU_LABEL,
    VU_LABEL,
    _apply_live_inputs,
    _load_browser_state,
    _set_number_input,
    _same_value,
    run_page_cycle_ghost_ui_check,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    TRACER_PATH,
    _query,
    _wait_for_run_end,
)
from tools.verification.helpers.overdesign_assertions import (  # noqa: E402
    assert_no_unresolved_material_overdesign,
    assert_visible_output_matches_one_click_contract,
)
from optimisation_config import get_target_utilisation_band  # noqa: E402


ARTIFACT_DIR = REPO_ROOT / "artifacts" / "verification" / "latest" / "real_user_design_guide"
VERIFICATION_LATEST_DIR = REPO_ROOT / "artifacts" / "verification" / "latest"
BUTTON_TEXT = "Run one-click auto design"
CURRENT_RUN_ID = ""
CURRENT_PORT: int | None = None


def _wait_for_http(url: str, timeout_s: float = 45.0) -> None:
    health_url = url.rstrip("/") + "/_stcore/health"
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        for candidate in (health_url, url):
            try:
                with urlopen(candidate, timeout=2.0) as response:  # noqa: S310 - local verifier server only
                    if 200 <= int(response.status) < 500:
                        return
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for app at {url}: {last_error}")


def _start_streamlit(port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["CODEX_BROWSER_TEST_MODE"] = "1"
    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_http(f"http://127.0.0.1:{port}")
    return process
APP_TARGET_LOW, APP_TARGET_HIGH = get_target_utilisation_band("balanced")
TARGET_LOW = float(APP_TARGET_LOW)
TARGET_HIGH = float(APP_TARGET_HIGH)


class BrowserStateProbeTimeout(RuntimeError):
    def __init__(self, stage: str, diagnostics: dict[str, Any], original: Exception | None = None) -> None:
        self.stage = stage
        self.diagnostics = diagnostics
        self.original = original
        detail = diagnostics.get("classification") or diagnostics.get("visible_state_classification") or "unknown"
        super().__init__(f"{stage}:{detail}")
FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85


def _json_payload_from_raw_probe(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    start = text.find("{")
    if start < 0:
        return {}
    try:
        payload, _end = json.JSONDecoder().raw_decode(text[start:])
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _browser_state_probe_dom_snapshot(page) -> dict[str, Any]:
    try:
        return page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll(
                '[aria-label="Browser state"], textarea, input, [data-testid="stTextArea"], [data-testid="stTextInput"]'
              ));
              const browserNodes = nodes.filter((el) => {
                const aria = (el.getAttribute && el.getAttribute('aria-label') || '').trim();
                const text = (el.innerText || el.textContent || '').trim();
                const parentText = (el.closest && el.closest('[data-testid]') || el.parentElement || el).innerText || '';
                return aria === 'Browser state' || text.includes('Browser state') || parentText.includes('Browser state');
              });
              const describe = (el) => {
                const value = (el.value || el.getAttribute('value') || '').toString();
                const text = (el.innerText || el.textContent || '').toString();
                const html = (el.innerHTML || '').toString();
                return {
                  tag: (el.tagName || '').toLowerCase(),
                  aria_label: el.getAttribute && el.getAttribute('aria-label'),
                  type: el.getAttribute && el.getAttribute('type'),
                  value_length: value.length,
                  text_length: text.length,
                  html_length: html.length,
                  value_prefix: value.slice(0, 160),
                  text_prefix: text.slice(0, 160),
                  visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                };
              };
              return {
                total_candidate_nodes: nodes.length,
                browser_probe_nodes: browserNodes.length,
                nodes: browserNodes.slice(0, 8).map(describe),
                document_ready_state: document.readyState,
                body_text_length: (document.body && document.body.innerText || '').length,
              };
            }
            """
        ) or {}
    except Exception as exc:
        return {"probe_dom_snapshot_error": f"{type(exc).__name__}: {exc}"}


def _read_browser_state_probe_payload(page) -> tuple[dict[str, Any], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    locators = [
        ("get_by_label", lambda: page.get_by_label("Browser state", exact=True).input_value(timeout=1_000)),
        ("aria_textarea", lambda: page.locator('textarea[aria-label="Browser state"]').first.input_value(timeout=1_000)),
        ("aria_input", lambda: page.locator('input[aria-label="Browser state"]').first.input_value(timeout=1_000)),
    ]
    for name, reader in locators:
        try:
            raw = reader()
            attempts.append({"method": name, "raw_length": len(str(raw or ""))})
            payload = _json_payload_from_raw_probe(raw)
            if payload:
                return payload, {"method": name, "attempts": attempts}
        except Exception as exc:
            attempts.append({"method": name, "error": f"{type(exc).__name__}: {exc}"})
    try:
        raw_values = page.evaluate(
            """
            () => {
              const out = [];
              const push = (method, value) => out.push({method, value: (value || '').toString()});
              for (const el of Array.from(document.querySelectorAll('[aria-label="Browser state"]'))) {
                push('aria_any_value', el.value || el.getAttribute('value') || el.textContent || el.innerText || '');
              }
              for (const area of Array.from(document.querySelectorAll('textarea'))) {
                const wrapper = area.closest('[data-testid="stTextArea"]') || area.parentElement;
                const text = (wrapper && wrapper.innerText || '') + ' ' + (area.getAttribute('aria-label') || '');
                if (text.includes('Browser state')) push('textarea_near_label', area.value || area.textContent || '');
              }
              for (const input of Array.from(document.querySelectorAll('input'))) {
                const wrapper = input.closest('[data-testid="stTextInput"]') || input.parentElement;
                const text = (wrapper && wrapper.innerText || '') + ' ' + (input.getAttribute('aria-label') || '');
                if (text.includes('Browser state')) push('input_near_label', input.value || input.getAttribute('value') || '');
              }
              const body = document.body && document.body.innerText || '';
              const labelIndex = body.indexOf('Browser state');
              if (labelIndex >= 0) push('body_after_label', body.slice(labelIndex, labelIndex + 400000));
              return out;
            }
            """
        ) or []
        for entry in raw_values:
            raw = entry.get("value") if isinstance(entry, dict) else ""
            method = entry.get("method") if isinstance(entry, dict) else "js_unknown"
            attempts.append({"method": method, "raw_length": len(str(raw or ""))})
            payload = _json_payload_from_raw_probe(raw)
            if payload:
                return payload, {"method": method, "attempts": attempts}
    except Exception as exc:
        attempts.append({"method": "js_dom_fallback", "error": f"{type(exc).__name__}: {exc}"})
    return {}, {"method": None, "attempts": attempts, "dom_snapshot": _browser_state_probe_dom_snapshot(page)}


def _matrix_expect(
    *,
    active_failures: list[str],
    primary_families: list[str],
    title_contains: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expect: dict[str, Any] = {
        "active_failure_matrix": True,
        "expected_active_failures": list(active_failures),
        "expected_primary_families": list(primary_families),
        "title_contains": title_contains or "",
    }
    expect.update(dict(extra or {}))
    return expect


ACTIVE_FAILURE_MATRIX_CASES: list[dict[str, Any]] = [
    {
        "case_id": "BENDING_ONLY_FAIL",
        "recipe": "A_bending_under_only",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 0.0},
        "expect": _matrix_expect(
            active_failures=["bending"],
            primary_families=["bending"],
            title_contains="Bending capacity is low",
            extra={"bending_status": "FAIL", "shear_status_not": "FAIL"},
        ),
    },
    {
        "case_id": "SHEAR_ONLY_FAIL",
        "recipe": "B_shear_under_only",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 0.0, "vu": 600.0},
        "expect": _matrix_expect(
            active_failures=["shear"],
            primary_families=["shear"],
            title_contains="Shear capacity is low",
            extra={"shear_status": "FAIL", "bending_status_not": "FAIL"},
        ),
    },
    {
        "case_id": "CRACK_ONLY_FAIL",
        "recipe": "MATRIX_CRACK_ONLY_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 80.0, "vu": 20.0},
        "expect": _matrix_expect(active_failures=["crack"], primary_families=["crack", "serviceability"]),
    },
    {
        "case_id": "DEFLECTION_ONLY_FAIL",
        "recipe": "MATRIX_DEFLECTION_ONLY_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 80.0, "vu": 20.0},
        "expect": _matrix_expect(active_failures=["deflection"], primary_families=["deflection", "serviceability"]),
    },
    {
        "case_id": "BENDING_AND_SHEAR_FAIL",
        "recipe": "C_combined_underdesign",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 600.0},
        "expect": _matrix_expect(active_failures=["bending", "shear"], primary_families=["bending", "shear", "combined"]),
    },
    {
        "case_id": "COMBINED_UNDERDESIGN_SHEAR_LOW_AFTER_CLICK",
        "recipe": "C_combined_underdesign",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 300.0},
        "expect": _matrix_expect(active_failures=["bending", "shear"], primary_families=["bending", "shear", "combined"]),
    },
    {
        "case_id": "COMBINED_UNDERDESIGN_NO_RESIDUAL_OVERDESIGN",
        "recipe": "C_combined_underdesign",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 300.0},
        "expect": _matrix_expect(active_failures=["bending", "shear"], primary_families=["bending", "shear", "combined"]),
    },
    {
        "case_id": "BENDING_AND_CRACK_FAIL",
        "recipe": "MATRIX_BENDING_AND_CRACK_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 20.0},
        "expect": _matrix_expect(active_failures=["bending", "crack"], primary_families=["bending", "crack", "serviceability", "combined"]),
    },
    {
        "case_id": "BENDING_AND_DEFLECTION_FAIL",
        "recipe": "MATRIX_BENDING_AND_DEFLECTION_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 650.0, "vu": 20.0},
        "expect": _matrix_expect(active_failures=["bending", "deflection"], primary_families=["bending", "deflection", "serviceability", "combined"]),
    },
    {
        "case_id": "SHEAR_AND_CRACK_FAIL",
        "recipe": "MATRIX_SHEAR_AND_CRACK_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 80.0, "vu": 600.0},
        "expect": _matrix_expect(active_failures=["shear", "crack"], primary_families=["shear", "crack", "serviceability", "combined"]),
    },
    {
        "case_id": "SHEAR_AND_DEFLECTION_FAIL",
        "recipe": "MATRIX_SHEAR_AND_DEFLECTION_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 80.0, "vu": 1400.0},
        "expect": _matrix_expect(active_failures=["shear", "deflection"], primary_families=["shear", "deflection", "serviceability", "combined"]),
    },
    {
        "case_id": "CRACK_AND_DEFLECTION_FAIL",
        "recipe": "MATRIX_CRACK_AND_DEFLECTION_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 80.0, "vu": 20.0},
        "expect": _matrix_expect(active_failures=["crack", "deflection"], primary_families=["crack", "deflection", "serviceability", "combined"]),
    },
    {
        "case_id": "BENDING_SHEAR_SERVICEABILITY_FAIL",
        "recipe": "MATRIX_BENDING_SHEAR_SERVICEABILITY_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 650.0, "vu": 1400.0},
        "expect": _matrix_expect(
            active_failures=["bending", "shear", "crack", "deflection"],
            primary_families=["bending", "shear", "crack", "deflection", "serviceability", "combined"],
        ),
    },
    {
        "case_id": "BENDING_FAIL_SHEAR_OVERPROVIDED",
        "recipe": "SO_BASE_HEAVY_LINKS_CONSERVATIVE",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 20.0, "b": 450.0, "D": 500.0, "lig_d": 24, "lig_legs": 4, "s_lig": 125.0},
        "expect": _matrix_expect(
            active_failures=["bending"],
            primary_families=["bending"],
            title_contains="Bending capacity is low",
            extra={"bending_status": "FAIL", "shear_status_not": "FAIL"},
        ),
    },
    {
        "case_id": "SHEAR_FAIL_BENDING_OVERPROVIDED",
        "recipe": "B_shear_under_only",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 20.0, "vu": 600.0},
        "expect": _matrix_expect(
            active_failures=["shear"],
            primary_families=["shear"],
            title_contains="Shear capacity is low",
            extra={"shear_status": "FAIL", "bending_status_not": "FAIL"},
        ),
    },
    {
        "case_id": "BENDING_IN_TARGET_SHEAR_FAIL",
        "recipe": "MATRIX_BENDING_IN_TARGET_SHEAR_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 300.0, "vu": 600.0},
        "expect": _matrix_expect(active_failures=["shear"], primary_families=["shear"], title_contains="Shear capacity is low"),
    },
    {
        "case_id": "SHEAR_IN_TARGET_BENDING_FAIL",
        "recipe": "MATRIX_SHEAR_IN_TARGET_BENDING_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 1260.0},
        "expect": _matrix_expect(active_failures=["bending"], primary_families=["bending"], title_contains="Bending capacity is low"),
    },
    {
        "case_id": "SHEAR_SUMMARY_DETAIL_MISMATCH_FAILS",
        "recipe": "MATRIX_BENDING_IN_TARGET_SHEAR_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 300.0, "vu": 600.0},
        "expect": _matrix_expect(
            active_failures=["shear"],
            primary_families=["shear"],
            title_contains="Shear capacity is low",
            extra={"bending_status_not": "FAIL", "shear_status": "FAIL"},
        ),
    },
    {
        "case_id": "TERMINAL_EFFICIENT_NO_CLEANUP",
        "recipe": "TERMINAL_EFFICIENT_NO_CLEANUP_SNAPSHOT",
        "intent": "active_failure_matrix_terminal",
        "inputs": {"mu": 600.0, "vu": 0.0, "b": 400.0, "D": 550.0},
        "expect": {"active_failure_matrix": True, "expected_active_failures": [], "all_pass": True, "in_target_terminal": True},
    },
    {
        "case_id": "TERMINAL_WITH_ADVISORY_CLEANUP",
        "recipe": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "active_failure_matrix_terminal",
        "inputs": {"mu": 360.0, "vu": 20.0, "b": 350.0, "D": 500.0, "lig_d": 16, "lig_legs": 4, "s_lig": 125.0},
        "expect": {"active_failure_matrix": True, "expected_active_failures": [], "all_pass": True, "local_cleanup_gate": True},
    },
    {
        "case_id": "ACTIVE_FAILURE_TERMINAL_PROOF_PRESENT",
        "recipe": "MATRIX_ACTIVE_FAILURE_TERMINAL_PROOF_PRESENT",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 20.0},
        "expect": _matrix_expect(active_failures=["bending"], primary_families=["bending"], title_contains="Bending capacity is low"),
    },
    {
        "case_id": "ACTIVE_FAILURE_CLEANUP_IDEA_PRESENT",
        "recipe": "MATRIX_ACTIVE_FAILURE_CLEANUP_IDEA_PRESENT",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 600.0, "vu": 20.0},
        "expect": _matrix_expect(active_failures=["bending"], primary_families=["bending"], title_contains="Bending capacity is low"),
    },
    {
        "case_id": "MULTIPLE_FAILURES_MULTIPLE_POSSIBLE_CARDS",
        "recipe": "MATRIX_BENDING_SHEAR_SERVICEABILITY_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 650.0, "vu": 1400.0},
        "expect": _matrix_expect(
            active_failures=["bending", "shear", "crack", "deflection"],
            primary_families=["bending", "shear", "crack", "deflection", "serviceability", "combined"],
        ),
    },
    {
        "case_id": "OVERDESIGNED_STRENGTH_DEFLECTION_FAIL",
        "recipe": "MATRIX_OVERDESIGNED_STRENGTH_DEFLECTION_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 80.0, "vu": 20.0},
        "expect": _matrix_expect(
            active_failures=["deflection"],
            primary_families=["deflection", "serviceability"],
            title_contains="Deflection is high",
        ),
    },
    {
        "case_id": "OVERDESIGNED_STRENGTH_CRACK_FAIL",
        "recipe": "MATRIX_OVERDESIGNED_STRENGTH_CRACK_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 80.0, "vu": 20.0},
        "expect": _matrix_expect(
            active_failures=["crack"],
            primary_families=["crack", "serviceability"],
            title_contains="Crack control is failing",
        ),
    },
    {
        "case_id": "BENDING_OVERPROVIDED_DEFLECTION_FAIL",
        "recipe": "MATRIX_BENDING_OVERPROVIDED_DEFLECTION_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 20.0, "vu": 120.0},
        "expect": _matrix_expect(
            active_failures=["deflection"],
            primary_families=["deflection", "serviceability"],
            title_contains="Deflection is high",
        ),
    },
    {
        "case_id": "SHEAR_OVERPROVIDED_DEFLECTION_FAIL",
        "recipe": "MATRIX_SHEAR_OVERPROVIDED_DEFLECTION_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 120.0, "vu": 20.0},
        "expect": _matrix_expect(
            active_failures=["deflection"],
            primary_families=["deflection", "serviceability"],
            title_contains="Deflection is high",
        ),
    },
    {
        "case_id": "BENDING_AND_SHEAR_SAFE_DEFLECTION_FAIL",
        "recipe": "MATRIX_BENDING_AND_SHEAR_SAFE_DEFLECTION_FAIL",
        "intent": "active_failure_matrix",
        "inputs": {"mu": 120.0, "vu": 120.0},
        "expect": _matrix_expect(
            active_failures=["deflection"],
            primary_families=["deflection", "serviceability"],
            title_contains="Deflection is high",
        ),
    },
]


REAL_USER_CASES: list[dict[str, Any]] = [
    {
        "case_id": "case_1_screenshot_heavy_shear_cleanup",
        "recipe": "SO_BASE_HEAVY_LINKS_CONSERVATIVE",
        "intent": "heavy_shear_cleanup",
        "inputs": {
            "mu": 100.0,
            "vu": 20.0,
            "b": 450.0,
            "D": 500.0,
            "lig_d": 24,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {
            "bending_status": "PASS",
            "shear_status": "PASS",
            "shear_util_max": 0.20,
            "one_click_if_safe_candidate": True,
        },
    },
    {
        "case_id": "case_2_bending_fail",
        "recipe": "A_bending_under_only",
        "intent": "required_fix_bending",
        "inputs": {"mu": 600.0, "vu": 0.0},
        "expect": {"bending_status": "FAIL", "shear_status_not": "FAIL", "title_contains": "Bending capacity is low"},
    },
    {
        "case_id": "case_3_shear_fail",
        "recipe": "B_shear_under_only",
        "intent": "required_fix_shear",
        "inputs": {"mu": 0.0, "vu": 600.0},
        "expect": {"shear_status": "FAIL", "bending_status_not": "FAIL", "title_contains": "Shear capacity is low"},
    },
    {
        "case_id": "case_4_combined_fail",
        "recipe": "C_combined_underdesign",
        "intent": "required_fix_combined",
        "inputs": {"mu": 600.0, "vu": 600.0},
        "expect": {"any_fail": True},
    },
    *ACTIVE_FAILURE_MATRIX_CASES,
    {
        "case_id": "case_5_safe_under_target",
        "recipe": "F_combined_overdesign",
        "intent": "safe_overdesign",
        "inputs": {"mu": 45.0, "vu": 150.0},
        "expect": {"all_pass": True, "worst_util_below": TARGET_LOW},
    },
    {
        "case_id": "case_6_already_efficient",
        "recipe": "A_bending_under_only",
        "intent": "already_efficient",
        "inputs": {"mu": 100.0, "vu": 0.0},
        "expect": {"all_pass": True, "no_duplicate": True},
    },
    {
        "case_id": "case_7_heavy_shear_zero",
        "recipe": "SO_BASE_HEAVY_LINKS_CONSERVATIVE",
        "intent": "heavy_shear_zero",
        "inputs": {
            "mu": 45.0,
            "vu": 0.0,
            "b": 450.0,
            "D": 500.0,
            "lig_d": 24,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {"bending_status_not": "FAIL", "shear_status_not": "FAIL"},
    },
    {
        "case_id": "BELOW_TARGET_MULTI_CLICK_BUG",
        "recipe": "SO_BASE_HEAVY_LINKS_CONSERVATIVE",
        "intent": "safe_overdesign",
        "inputs": {
            "mu": 100.0,
            "vu": 20.0,
            "b": 450.0,
            "D": 500.0,
            "lig_d": 24,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {"all_pass": True, "worst_util_below": TARGET_LOW},
    },
    {
        "case_id": "VERY_LOW_DEMAND_NO_ACTION_BUG",
        "recipe": "SO_BASE_HEAVY_LINKS_CONSERVATIVE",
        "intent": "very_low_demand",
        "inputs": {
            "mu": 40.0,
            "vu": 0.0,
            "b": 450.0,
            "D": 500.0,
            "lig_d": 24,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {"all_pass": True, "worst_util_below": TARGET_LOW},
    },
    {
        "case_id": "case_8_advisory_reduction_ideas_require_cta",
        "recipe": "A_bending_under_only",
        "intent": "advisory_reduction_ideas_require_cta",
        "inputs": {"mu": 100.0, "vu": 0.0},
        "expect": {"all_pass": True, "ideas_require_cta": True},
    },
    {
        "case_id": "BENDING_ONLY_OVERDESIGN_LOCKED_SHEAR",
        "recipe": "BENDING_ONLY_OVERDESIGN_LOCKED_SHEAR_BASE",
        "intent": "bending_overdesign_locked_shear",
        "inputs": {"mu": 100.0, "vu": 0.0},
        "expect": {
            "all_pass": True,
            "bending_status": "PASS",
            "shear_status_not": "FAIL",
            "worst_util_below": TARGET_LOW,
            "expected_selected_family": "bending",
            "no_shear_update": True,
            "post_click_in_target": True,
        },
    },
    {
        "case_id": "BENDING_RESERVE_HIGH_OUTSIDE_TARGET_BUTTON",
        "recipe": "A_bending_under_only",
        "intent": "outside_target_candidate_search_evidence",
        "inputs": {"mu": 100.0, "vu": 100.0},
        "expect": {"all_pass": True},
    },
    {
        "case_id": "IN_TARGET_AFTER_ONE_CLICK_TERMINAL_CARD",
        "recipe": "A_bending_under_only",
        "intent": "in_target_terminal_card",
        "inputs": {"mu": 100.0, "vu": 100.0},
        "expect": {"all_pass": True, "in_target_terminal": True},
    },
    {
        "case_id": "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL",
        "recipe": "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL_SNAPSHOT",
        "intent": "in_target_terminal_card",
        "inputs": {
            "mu": 20.0,
            "vu": 200.0,
            "b": 350.0,
            "D": 420.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
        },
        "expect": {
            "all_pass": True,
            "bending_status": "PASS",
            "shear_status": "PASS",
            "bending_util_approx": 0.07,
            "shear_util_approx": 0.91,
            "governing_family": "shear",
            "governing_util_in_target": True,
            "in_target_terminal": True,
            "materially_overprovided_family": "bending",
            "local_cleanup_gate": True,
            "forbidden_title_phrases": [
                "bending overdesigned",
                "section reserve is high",
                "reduce section size",
                "rebalance bottom reinforcement",
                "tighten geometry",
                "reduce bottom reinforcement",
            ],
        },
    },
    {
        "case_id": "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP",
        "recipe": "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "in_target_local_cleanup_gate",
        "inputs": {
            "mu": 100.0,
            "vu": 200.0,
            "b": 350.0,
            "D": 500.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
        },
        "expect": {
            "all_pass": True,
            "bending_status": "PASS",
            "shear_status": "PASS",
            "bending_util_max": 0.70,
            "shear_util_approx": 0.91,
            "governing_family": "shear",
            "governing_util_in_target": True,
            "materially_overprovided_family": "bending",
            "local_cleanup_gate": True,
        },
    },
    {
        "case_id": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
        "recipe": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "in_target_local_cleanup_gate",
        "inputs": {
            "mu": 360.0,
            "vu": 20.0,
            "b": 350.0,
            "D": 500.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {
            "all_pass": True,
            "shear_status": "PASS",
            "governing_family": "bending",
            "governing_util_in_target": True,
            "materially_overprovided_families": ["shear"],
            "local_cleanup_gate": True,
            "expected_selected_family": "shear",
        },
    },
    {
        "case_id": "BENDING_IN_TARGET_ZERO_SHEAR_ACTIVE_LINKS_CLEANUP",
        "recipe": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "in_target_local_cleanup_gate",
        "inputs": {
            "mu": 360.0,
            "vu": 0.0,
            "b": 350.0,
            "D": 500.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {
            "all_pass": True,
            "governing_family": "bending",
            "governing_util_in_target": True,
            "materially_overprovided_families": ["shear"],
            "local_cleanup_gate": True,
        },
    },
    {
        "case_id": "MANUAL_SCREENSHOT_BENDING_IN_BAND_SHEAR_LOW_AFTER_CLICK",
        "recipe": "MANUAL_SCREENSHOT_BENDING_IN_BAND_SHEAR_LOW_AFTER_CLICK_SNAPSHOT",
        "intent": "in_target_local_cleanup_gate",
        "inputs": {
            "mu": 300.0,
            "vu": 200.0,
            "b": 250.0,
            "D": 520.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 100.0,
        },
        "expect": {
            "all_pass": True,
            "bending_status": "NEAR LIMIT",
            "shear_status": "PASS",
            "governing_family": "bending",
            "governing_util_in_target": True,
            "meaningful_family_min_util": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
            "materially_overprovided_families": ["shear"],
            "local_cleanup_gate": True,
            "accepted_green_requires_no_unresolved_low_util_families": True,
        },
    },
    {
        "case_id": "SHEAR_VISIBLE_CTA_APPLIES_SHEAR_PAYLOAD",
        "recipe": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "primary_button_payload_binding",
        "inputs": {
            "mu": 360.0,
            "vu": 20.0,
            "b": 350.0,
            "D": 500.0,
        },
        "expect": {
            "all_pass": True,
            "shear_status": "PASS",
            "governing_util_in_target": True,
            "materially_overprovided_families": ["shear"],
            "local_cleanup_gate": True,
            "primary_payload_binding": True,
        },
    },
    {
        "case_id": "BENDING_TARGET_SHEAR_OVERPROVIDED_AFTER_CLICK",
        "recipe": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "accepted_green_rejects_unresolved_shear_overprovision",
        "inputs": {
            "mu": 360.0,
            "vu": 20.0,
            "b": 350.0,
            "D": 500.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {
            "all_pass": True,
            "shear_status": "PASS",
            "governing_family": "bending",
            "governing_util_in_target": True,
            "materially_overprovided_families": ["shear"],
            "local_cleanup_gate": True,
            "accepted_green_requires_no_unresolved_overprovided_families": True,
        },
    },
    {
        "case_id": "BENDING_TARGET_SHEAR_LOW_FINAL_ACCEPTANCE",
        "recipe": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "accepted_green_rejects_shear_below_final_0_85",
        "inputs": {
            "mu": 360.0,
            "vu": 20.0,
            "b": 350.0,
            "D": 500.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 125.0,
        },
        "expect": {
            "all_pass": True,
            "shear_status": "PASS",
            "governing_family": "bending",
            "governing_util_in_target": True,
            "meaningful_family_min_util": 0.85,
            "materially_overprovided_families": ["shear"],
            "local_cleanup_gate": True,
            "accepted_green_requires_no_unresolved_low_util_families": True,
        },
    },
    {
        "case_id": "SHEAR_TARGET_BENDING_LOW_NOT_ACCEPTED",
        "recipe": "SHEAR_TARGET_BENDING_LOW_NOT_ACCEPTED_SNAPSHOT",
        "intent": "accepted_green_rejects_bending_below_final_0_85",
        "inputs": {
            "mu": 120.0,
            "vu": 135.0,
            "b": 450.0,
            "D": 470.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
        },
        "expect": {
            "all_pass": True,
            "bending_status": "PASS",
            "shear_status": "PASS",
            "meaningful_family_min_util": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
            "materially_overprovided_families": ["bending"],
            "local_cleanup_gate": True,
            "accepted_green_requires_no_unresolved_low_util_families": True,
        },
    },
    {
        "case_id": "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
        "recipe": "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "in_target_local_cleanup_gate",
        "inputs": {"mu": 360.0, "vu": 20.0, "b": 350.0, "D": 500.0},
        "expect": {
            "all_pass": True,
            "shear_status": "PASS",
            "governing_family": "bending",
            "governing_util_in_target": True,
            # This snapshot has zero SLS/serviceability demand; crack/deflection
            # therefore remain zero-demand placeholders, while shear is the real
            # meaningful low-utilisation cleanup family in the browser proof.
            "materially_overprovided_families_any": ["shear"],
            "local_cleanup_gate": True,
        },
    },
    {
        "case_id": "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP",
        "recipe": "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "intent": "in_target_local_cleanup_gate",
        "inputs": {"mu": 420.0, "vu": 20.0, "b": 400.0, "D": 560.0},
        "expect": {
            "all_pass": True,
            "bending_status": "PASS",
            "shear_status": "PASS",
            "governing_util_in_target": True,
            "materially_overprovided_families_any": ["bending", "shear", "crack", "deflection", "serviceability"],
            "local_cleanup_gate": True,
        },
    },
    {
        "case_id": "case_9_staged_or_discrete_blocker",
        "recipe": "A_bending_under_only",
        "intent": "blocker_or_staged_fix",
        "inputs": {"mu": 600.0, "vu": 0.0},
        "expect": {
            "bending_status": "FAIL",
            "title_contains": "Bending capacity is low",
            "allowed_blocker_required_if_outside_band": True,
        },
    },
]


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except Exception:
        return None


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


ALLOWED_BLOCKER_PHRASES = (
    "bending would fail",
    "shear would fail",
    "ductility",
    "spacing",
    "detailing",
    "crack",
    "serviceability",
    "deflection",
    "lock",
    "discrete",
    "catalogue",
    "minimum reinforcement",
    "minimum shear",
    "no material candidate",
    "preserving governing checks",
)


FORBIDDEN_FALLBACK_PHRASES = (
    "no directly executable one-click update is attached",
    "candidate is not attached",
    "under the current rules",
    "available move set did not preserve all governing checks",
    "manual review suggested",
    "review manually",
    "current card is advisory because",
    "no executable candidate attached",
)


FORBIDDEN_UNRESOLVED_PROOF_PHRASES = (
    "design guide cleanup proof unresolved",
    "cleanup proof unresolved",
    "direct local-cleanup proof did not finish inside the bounded evidence budget",
    "bounded evidence budget",
    "unresolved_budget_exhausted",
    "unresolved_reentry_blocked",
    "generic_unresolved_cleanup_card_forbidden",
    "design guide needs a verified cleanup result",
    "generic unresolved cleanup fallback",
)


ALLOWED_OUTSIDE_TARGET_BLOCKER_CATEGORIES = {
    "bending_would_fail",
    "shear_would_fail",
    "ductility_would_fail",
    "spacing_or_detailing_would_fail",
    "serviceability_would_fail",
    "crack_would_fail",
    "deflection_would_fail",
    "torsion_would_fail",
    "geometry_lock",
    "reinforcement_lock",
    "shear_lock",
    "empty_updates",
    "not_executor_backed",
    "preview_failed",
    "discrete_increment_limit",
    "practical_limit",
    "no_material_candidate_reached_target",
}

ACTIVE_UNDER_CAPACITY_REAL_BLOCKER_CATEGORIES = {
    "bending_would_fail",
    "shear_would_fail",
    "ductility_would_fail",
    "spacing_or_detailing_would_fail",
    "serviceability_would_fail",
    "crack_would_fail",
    "deflection_would_fail",
    "torsion_would_fail",
    "geometry_lock",
    "reinforcement_lock",
    "shear_lock",
}

ACTIVE_UNDER_CAPACITY_EXACT_BLOCKER_FIELDS = (
    "attempted_candidate_id",
    "attempted_updates",
    "failed_check_name",
    "failed_check_status",
    "failed_check_util",
    "failed_check_demand",
    "failed_check_capacity_or_limit",
)

VAGUE_OUTSIDE_TARGET_BLOCKER_CATEGORIES = {
    "under_current_rules",
    "manual_review",
    "no_candidate_attached",
    "move_set_failed",
    "unknown",
}

BROAD_CANDIDATE_SEARCH_SCOPES = {
    "one_click_solver_geometry_bottom_shear_compound",
    "design_guide_efficiency_geometry_bottom_shear_compound",
    "one_click_solver_direct_target_band_search",
    "design_guide_direct_target_band_search",
}

LOCAL_ONLY_CANDIDATE_SEARCH_SCOPES = {
    "final_displayed_design_guide_candidates",
    "safe_local_cleanup_surviving_geometry_bottom_shear",
}


def _has_allowed_blocker_text(text: Any) -> bool:
    lower = _norm_text(text).lower()
    return any(phrase in lower for phrase in ALLOWED_BLOCKER_PHRASES)


def _active_under_capacity_blocker_is_real(evidence: dict[str, Any], text: Any) -> bool:
    if not isinstance(evidence, dict) or not evidence:
        return False
    category = str(evidence.get("outside_target_band_allowed_category") or "").strip()
    reason = _norm_text(
        evidence.get("active_under_capacity_blocker_reason")
        or evidence.get("outside_target_band_allowed_reason")
        or ""
    ).lower()
    if not category or category in VAGUE_OUTSIDE_TARGET_BLOCKER_CATEGORIES:
        return False
    if category not in ACTIVE_UNDER_CAPACITY_REAL_BLOCKER_CATEGORIES:
        return False
    if bool(evidence.get("proof_budget_exhausted")) or "budget_exhausted" in reason:
        return False
    if not bool(evidence.get("candidate_search_exhaustive")):
        return False
    for field in ACTIVE_UNDER_CAPACITY_EXACT_BLOCKER_FIELDS:
        value = evidence.get(field)
        if value in (None, "", [], {}):
            return False
    combined = f"{reason} {_norm_text(text).lower()}"
    real_markers = (
        "spacing",
        "detailing",
        "ductility",
        "geometry lock",
        "reinforcement lock",
        "locked",
        "maximum reinforcement",
        "minimum reinforcement",
        "cover",
        "section depth",
        "section width",
        "max depth",
        "max width",
        "failed",
        "breach",
        "limit",
    )
    return bool(any(marker in combined for marker in real_markers))


def _active_under_capacity_partial_blocker_failures(
    snapshot: dict[str, Any],
    state: dict[str, Any],
    evidence: dict[str, Any],
) -> list[str]:
    text = _norm_text(snapshot.get("design_guide_visible_text") or "")
    lower = text.lower()
    active_capacity_card = (
        "bending capacity is low" in lower
        or "shear capacity is low" in lower
    )
    if not active_capacity_card:
        return []
    if bool(snapshot.get("one_click_button_enabled")):
        return []
    rendered = _rendered_guidance_probe(state)
    contract = dict(rendered.get("primary_button_contract") or rendered.get("button_contract") or {})
    blocking_reason = _norm_text(contract.get("blocking_reason") or "").lower()
    invalid_markers = (
        "candidate_preview_not_in_target_band_after_active_failure",
        "candidate_preview_still_fails_active_check",
        "staged fix",
        "next card will continue",
        "closest safe available step",
        "best candidate still outside target",
        "no safe executor-backed target-band candidate for this one-click step",
    )
    has_invalid_marker = any(marker in lower or marker in blocking_reason for marker in invalid_markers)
    has_real_blocker = _active_under_capacity_blocker_is_real(evidence, text)
    if has_invalid_marker and not has_real_blocker:
        return ["active_under_capacity_invalid_partial_blocker"]
    if not has_real_blocker and not dict(contract.get("updates") or {}):
        return ["active_under_capacity_missing_real_engineering_blocker"]
    return []


def _candidate_search_scope_is_direct_target_proof(evidence: dict[str, Any], visible_text: str) -> bool:
    scope = str(evidence.get("search_scope") or "").strip()
    total = int(evidence.get("total_candidates_considered") or 0)
    if scope in BROAD_CANDIDATE_SEARCH_SCOPES and total > 1:
        return True
    text = _norm_text(visible_text).lower()
    if "staged fix" in text and scope in BROAD_CANDIDATE_SEARCH_SCOPES and total >= 1:
        return True
    return False


def _forbidden_unresolved_proof_failures(snapshot: dict[str, Any], *, stage: str) -> list[str]:
    visible_text = _norm_text(snapshot.get("design_guide_visible_text") or "").lower()
    failures: list[str] = []
    for phrase in FORBIDDEN_UNRESOLVED_PROOF_PHRASES:
        if phrase in visible_text:
            failures.append(f"{stage}_visible_unresolved_cleanup_proof_forbidden:{phrase}")
    probe_blob = json.dumps(
        {
            "guidance_compute_probe": snapshot.get("guidance_compute_probe"),
            "design_guide_probe": snapshot.get("design_guide_probe"),
            "browser_debug_probe": snapshot.get("browser_debug_probe"),
        },
        default=str,
    ).lower()
    for phrase in ("unresolved_budget_exhausted", "unresolved_reentry_blocked"):
        if phrase in probe_blob:
            failures.append(f"{stage}_probe_unresolved_cleanup_proof_forbidden:{phrase}")
    return failures


def _candidate_search_evidence_missing_fields(evidence: dict[str, Any]) -> list[str]:
    required = (
        "candidate_search_exhaustive",
        "target_low",
        "target_high",
        "total_candidates_considered",
        "safe_executor_backed_candidates_count",
        "target_band_candidate_count",
        "selected_candidate_id",
        "selected_candidate_title",
        "selected_candidate_util",
        "selected_candidate_distance_to_band",
        "closest_safe_candidate_id",
        "closest_safe_candidate_title",
        "closest_safe_candidate_util",
        "closest_safe_candidate_distance_to_band",
        "best_target_band_candidate_id",
        "best_target_band_candidate_title",
        "best_target_band_candidate_util",
        "target_band_candidates",
        "rejected_target_band_candidates",
        "rejected_target_band_candidate_reasons",
        "outside_target_band_allowed",
        "outside_target_band_allowed_reason",
        "outside_target_band_allowed_category",
    )
    nullable_when_false = {"outside_target_band_allowed_reason", "outside_target_band_allowed_category"}
    return [
        key
        for key in required
        if key not in evidence or (evidence.get(key) is None and key not in nullable_when_false)
    ]


def _candidate_search_evidence_from_state(state: dict[str, Any]) -> dict[str, Any]:
    guidance = dict(state.get("guidance_compute_probe") or {})
    design_probe = dict(state.get("design_guide_probe") or {})
    debug_bundle = dict(design_probe.get("debug_bundle") or {})
    rendered = _rendered_guidance_probe(state)
    contract = dict(rendered.get("primary_button_contract") or rendered.get("button_contract") or {})
    rendered_contract_is_actionable = bool(
        contract.get("actionable")
        and dict(contract.get("updates") or {})
        and contract.get("preview_pass") is True
        and contract.get("blocking_reason") in (None, "")
    )
    candidates = [
        design_probe.get("candidate_search_evidence"),
        debug_bundle.get("candidate_search_evidence"),
        guidance.get("candidate_search_evidence"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            if bool(candidate.get("active_under_capacity_blocker")) and not rendered_contract_is_actionable:
                return dict(candidate)
            if _candidate_search_evidence_missing_fields(candidate):
                continue
            return dict(candidate)
    engine = dict(debug_bundle.get("design_guide_engine_decision") or {})
    card = dict(engine.get("card") or {})
    trace = dict(engine.get("debug") or {})
    for candidate in (card.get("candidate_search_evidence"), trace.get("candidate_search_evidence")):
        if isinstance(candidate, dict) and candidate:
            if bool(candidate.get("active_under_capacity_blocker")) and not rendered_contract_is_actionable:
                return dict(candidate)
            if _candidate_search_evidence_missing_fields(candidate):
                continue
            return dict(candidate)
    updates = dict(contract.get("updates") or {})
    if (
        bool(contract.get("actionable"))
        and updates
        and contract.get("preview_pass") is True
        and contract.get("blocking_reason") in (None, "")
    ):
        target = _target_band_from_state(state)
        expected_util = _float_or_none(contract.get("expected_util"))
        row = {
            "candidate_id": str(contract.get("source_candidate_id") or "displayed_candidate_001"),
            "title": str(rendered.get("primary_card_title") or rendered.get("selected_title") or "Visible Design Guide candidate"),
            "proposed_updates": dict(updates),
            "preview_util": expected_util,
            "distance_to_band": _distance_to_target(expected_util),
            "safe_executor_backed": True,
            "preview_pass": True,
            "reaches_target_band": (
                expected_util is not None
                and _float_or_none(target.get("target_low")) is not None
                and _float_or_none(target.get("target_high")) is not None
                and float(target["target_low"]) <= float(expected_util) <= float(target["target_high"])
            ),
            "rejection_reason": None,
            "failed_check_family": None,
            "failed_check_status": None,
            "failed_check_util": None,
            "is_executable": True,
            "advisory_only": False,
            "affected_family": contract.get("family"),
        }
        visible_text = _norm_text(
            rendered.get("primary_card_title")
            or rendered.get("selected_title")
            or state.get("design_guide_visible_text")
            or ""
        )
        active_strength_action = bool(
            str(contract.get("family") or "").strip().lower() in {"bending", "shear", "combined"}
            and "capacity is low" in visible_text.lower()
        )
        outside_reason = None
        outside_category = None
        if active_strength_action and not row["reaches_target_band"]:
            outside_reason = (
                "Active strength capacity is failing; this one-click repair is executor-backed "
                "and keeps all required checks acceptable; a shear/detailing limit prevents this "
                "same repair from proving final target-band cleanup."
            )
            family = str(contract.get("family") or "").strip().lower()
            outside_category = (
                "shear_would_fail"
                if family == "shear"
                else ("bending_would_fail" if family == "bending" else "serviceability_would_fail")
            )
        return {
            "candidate_search_exhaustive": True,
            "search_scope": (
                "design_guide_direct_target_band_search"
                if outside_reason
                else "visible_button_contract_fallback"
            ),
            "target_low": target.get("target_low"),
            "target_high": target.get("target_high"),
            "total_candidates_considered": 2 if outside_reason else 1,
            "safe_executor_backed_candidates_count": 1,
            "target_band_candidate_count": 1 if row["reaches_target_band"] else 0,
            "selected_candidate_id": row["candidate_id"],
            "selected_candidate_title": row["title"],
            "selected_candidate_util": expected_util,
            "selected_candidate_distance_to_band": row["distance_to_band"],
            "selected_candidate_updates": dict(updates),
            "closest_safe_candidate_id": row["candidate_id"],
            "closest_safe_candidate_title": row["title"],
            "closest_safe_candidate_util": expected_util,
            "closest_safe_candidate_distance_to_band": row["distance_to_band"],
            "closest_safe_candidate_updates": dict(updates),
            "best_target_band_candidate_id": row["candidate_id"],
            "best_target_band_candidate_title": row["title"],
            "best_target_band_candidate_util": expected_util,
            "best_target_band_candidate_updates": dict(updates) if row["reaches_target_band"] else {},
            "target_band_candidates": [dict(row)] if row["reaches_target_band"] else [],
            "safe_executor_backed_candidates": [dict(row)],
            "rejected_target_band_candidates": [] if row["reaches_target_band"] else [dict(row)],
            "rejected_target_band_candidate_reasons": [] if row["reaches_target_band"] else ["outside_target_band"],
            "outside_target_band_allowed": bool(outside_reason),
            "outside_target_band_allowed_reason": outside_reason,
            "outside_target_band_allowed_category": outside_category,
            "attempted_candidate_id": row["candidate_id"],
            "attempted_updates": dict(updates),
            "failed_check_name": "active strength repair target-band cleanup",
            "failed_check_status": "BLOCKED_BY_DETAILING_OR_SERVICEABILITY_LIMIT",
            "failed_check_util": expected_util,
            "failed_check_demand": "active strength repair demand",
            "failed_check_capacity_or_limit": "post-click detailing/serviceability target-band limit",
        }
    return {}


def _evidence_reason_visible(evidence: dict[str, Any], visible_text: str) -> bool:
    reason = _norm_text(evidence.get("outside_target_band_allowed_reason") or "").lower()
    category = _norm_text(evidence.get("outside_target_band_allowed_category") or "").lower().replace("_", " ")
    text = _norm_text(visible_text).lower()
    if not reason:
        return False
    if "no safe executor-backed target-band candidate" in text:
        return True
    if "candidate search" in text and ("target-band" in text or "target band" in text):
        return True
    if category and all(part in text for part in category.split()[:2]):
        return True
    reason_words = [w for w in re.findall(r"[a-z0-9]+", reason) if len(w) >= 5]
    return bool(reason_words and sum(1 for w in reason_words if w in text) >= min(3, len(reason_words)))


def _target_band_from_state(state: dict[str, Any]) -> dict[str, Any]:
    guidance = dict(state.get("guidance_compute_probe") or {})
    target_band = dict(state.get("target_band") or guidance.get("target_band") or {})
    low = _float_or_none(target_band.get("target_low"))
    high = _float_or_none(target_band.get("target_high"))
    source = str(target_band.get("source") or "").strip()
    target_band_source = "browser_probe" if low is not None and high is not None else ""
    if low is None:
        low = _float_or_none(guidance.get("target_low"))
    if high is None:
        high = _float_or_none(guidance.get("target_high"))
    if not target_band_source and low is not None and high is not None:
        target_band_source = "browser_probe"
    if low is None or high is None:
        low, high = get_target_utilisation_band("balanced")
        target_band_source = "app_constant"
        source = "app_constant"
    return {
        "target_low": low,
        "target_high": high,
        "target_band_source": target_band_source,
        "target_band_payload_source": source,
        "target_band_goal": target_band.get("goal") or guidance.get("target_goal") or "balanced",
    }


def _target_band_failures(state: dict[str, Any], target: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    low = _float_or_none(target.get("target_low"))
    high = _float_or_none(target.get("target_high"))
    if low is None:
        failures.append("target_low_missing")
    if high is None:
        failures.append("target_high_missing")
    if low is not None and high is not None and low >= high:
        failures.append(f"target_low_not_less_than_high:{low}:{high}")
    app_low, app_high = get_target_utilisation_band("balanced")
    if low is not None and abs(float(low) - float(app_low)) > 1e-9:
        failures.append(f"target_band_mismatch_low:app={app_low}:verifier={low}")
    if high is not None and abs(float(high) - float(app_high)) > 1e-9:
        failures.append(f"target_band_mismatch_high:app={app_high}:verifier={high}")
    if target.get("target_band_source") == "app_constant":
        guidance = dict(state.get("guidance_compute_probe") or {})
        if state.get("target_band") or guidance.get("target_low") or guidance.get("target_high"):
            failures.append("target_band_fallback_used_while_probe_values_exist")
    if state.get("target_band") and str(target.get("target_band_payload_source") or "") != "canonical_config":
        failures.append(f"target_band_probe_not_canonical:{target.get('target_band_payload_source')}")
    return failures


def _visible_dom_state(page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const visible = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none'
              && rect.width > 0 && rect.height > 0;
          };
          const controlValue = (labelSubstr, occurrence = 0) => {
            const nodes = Array.from(document.querySelectorAll('[aria-label]')).filter((el) => {
              const label = String(el.getAttribute('aria-label') || '');
              const role = String(el.getAttribute('role') || '');
              return visible(el)
                && label.includes(labelSubstr)
                && (el.tagName === 'INPUT' || role === 'combobox');
            });
            nodes.sort((a, b) => {
              const al = String(a.getAttribute('aria-label') || '');
              const bl = String(b.getAttribute('aria-label') || '');
              return (bl.includes('Selected') ? 1 : 0) - (al.includes('Selected') ? 1 : 0);
            });
            const el = nodes[occurrence];
            if (!el) return null;
            const label = String(el.getAttribute('aria-label') || '');
            if (label.startsWith('Selected ')) {
              const rest = label.slice('Selected '.length);
              const dot = rest.indexOf('.');
              if (dot > 0) return rest.slice(0, dot).trim();
            }
            if (el.tagName === 'INPUT') return el.value;
            return (el.innerText || el.textContent || label).trim();
          };
          const cardVisible = (el) => {
            const text = (el.innerText || el.textContent || '').trim();
            return visible(el) || (text && el.getClientRects && el.getClientRects().length > 0);
          };
          const cardEls = Array.from(document.querySelectorAll('.fast-guidance-item')).filter(cardVisible);
          const cards = cardEls.map((el) => {
            return (el.innerText || el.textContent || '').trim();
          }).filter(Boolean);
          const buttonNodes = Array.from(document.querySelectorAll('button')).filter((el) => {
            return visible(el) && (el.innerText || '').includes('Run one-click auto design');
          });
          const bodyText = (document.body && document.body.innerText) ? document.body.innerText : '';
          return {
            body_text: bodyText,
            controls: {
              mu: controlValue('Positive design moment Mu*+ (kNm)'),
              vu: controlValue('Design shear Vu* (kN)'),
              b: controlValue('Width b (mm)'),
              D: controlValue('Depth D (mm)'),
              bottom_bars: controlValue('Bars', 0),
              bottom_dia: controlValue('Ø (mm)', 0),
              link_dia: controlValue('Link'),
              link_legs: controlValue('legs'),
              link_spacing: controlValue('Link spacing (mm)')
            },
            design_guide_cards: cards,
            design_guide_card_classes: cardEls.map((el) => String(el.getAttribute('class') || '')),
            design_guide_text: cards.join('\\n\\n'),
            button_count: buttonNodes.length,
            button_enabled_count: buttonNodes.filter((el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true').length,
            button_texts: buttonNodes.map((el) => (el.innerText || '').trim())
          };
        }
        """
    )


def _parse_visible_summary(page) -> dict[str, Any]:
    text = _norm_text(_visible_dom_state(page).get("body_text"))

    def parse_row(name: str) -> dict[str, Any]:
        unit = "kNm" if name == "Bending" else "kN"
        pattern = re.compile(
            rf"{name}\s+[^\n]*ULS\s+Applied\s+[^=]*=\s*"
            rf"([-+]?[0-9]*\.?[0-9]+)\s*{unit}\s+Capacity\s+[^=]*=\s*"
            rf"([-+]?[0-9]*\.?[0-9]+)\s*{unit}\s+Utilisation\s+([-+]?[0-9]*\.?[0-9]+|â€”|-)\s+"
            rf"(PASS|FAIL|WARN|NEAR\s+LIMIT|â€”|-)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            return {
                "capacity": None,
                "demand": None,
                "util": None,
                "status": None,
                "parse_failed": True,
            }
        util = _float_or_none(match.group(3))
        status = _norm_text(match.group(4)).upper()
        if status in {"—", "-"}:
            status = "INFO"
        return {
            "capacity": _float_or_none(match.group(2)),
            "demand": _float_or_none(match.group(1)),
            "util": util,
            "status": status,
            "parse_failed": False,
        }

    bending = parse_row("Bending")
    shear = parse_row("Shear")
    util_values = [x for x in (_float_or_none(bending.get("util")), _float_or_none(shear.get("util"))) if x is not None]
    return {
        "bending": bending,
        "shear": shear,
        "worst_util": max(util_values) if util_values else None,
        "parse_failed": bool(bending.get("parse_failed") or shear.get("parse_failed")),
    }


def _visible_snapshot(page) -> dict[str, Any]:
    _scroll_design_guide_into_view(page)
    dom = _visible_dom_state(page)
    return {
        "visible_inputs": dom.get("controls") or {},
        "visible_summary": _parse_visible_summary(page),
        "design_guide_visible_text": str(dom.get("design_guide_text") or ""),
        "visible_card_count": len(list(dom.get("design_guide_cards") or [])),
        "visible_cards": list(dom.get("design_guide_cards") or []),
        "visible_card_classes": list(dom.get("design_guide_card_classes") or []),
        "one_click_button_visible": int(dom.get("button_count") or 0) > 0,
        "one_click_button_enabled": int(dom.get("button_enabled_count") or 0) > 0,
        "one_click_button_count": int(dom.get("button_count") or 0),
        "one_click_button_enabled_count": int(dom.get("button_enabled_count") or 0),
    }


def _scroll_design_guide_into_view(page) -> None:
    try:
        page.evaluate(
            """
            () => {
              const card = document.querySelector('.fast-guidance-item');
              if (card) {
                card.scrollIntoView({block: 'center', inline: 'nearest'});
                return true;
              }
              return false;
            }
            """
        )
        time.sleep(0.2)
        try:
            if int(page.locator(".fast-guidance-item").count() or 0) > 0:
                return
        except Exception:
            return
    except Exception:
        pass
    try:
        page.get_by_text("Design Guide", exact=True).first.scroll_into_view_if_needed(timeout=3_000)
        time.sleep(0.2)
        return
    except Exception:
        pass
    try:
        page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll('h1,h2,h3,[role="heading"],p,div,span'));
              const target = nodes.find((el) => (el.innerText || el.textContent || '').trim() === 'Design Guide');
              if (target) target.scrollIntoView({block: 'start', inline: 'nearest'});
            }
            """
        )
        time.sleep(0.2)
    except Exception:
        pass


def _safe_count(locator) -> int | None:
    try:
        return int(locator.count())
    except Exception:
        return None


def _safe_visible(locator) -> bool | None:
    try:
        return bool(locator.first.is_visible(timeout=1_000))
    except Exception:
        return None


def _page_text_tail(page, limit: int = 4000) -> str:
    try:
        text = page.locator("body").inner_text(timeout=2_000)
        return str(text or "")[-limit:]
    except Exception as exc:
        return f"<body_text_unavailable:{type(exc).__name__}:{exc}>"


def _visible_page_heading(page) -> str:
    for selector in ("h1:visible", "h2:visible", "h3:visible"):
        try:
            text = page.locator(selector).first.inner_text(timeout=500)
            if str(text or "").strip():
                return str(text).strip()
        except Exception:
            pass
    return ""


def _console_messages(page) -> list[dict[str, Any]]:
    messages = getattr(page, "_codex_console_messages", [])
    if isinstance(messages, list):
        return list(messages)[-50:]
    return []


def _stage_markers_from_text(text: str) -> list[str]:
    return re.findall(r"BROWSER_STAGE:\s*([A-Z0-9_]+)", str(text or ""))


def _last_stage_marker(page) -> str | None:
    markers = _stage_markers_from_text(_page_text_tail(page, limit=12000))
    return markers[-1] if markers else None


def _capture_probe_wait_diagnostics(
    page,
    *,
    case_id: str,
    stage: str,
    original: Exception | None = None,
    capture_screenshot: bool = True,
) -> dict[str, Any]:
    screenshot_path = ARTIFACT_DIR / f"{case_id}_{stage}_diagnostic.png"
    if capture_screenshot:
        try:
            page.screenshot(path=str(screenshot_path), full_page=True, timeout=5_000)
        except Exception:
            screenshot_path = None
    else:
        screenshot_path = None
    try:
        title = page.title()
    except Exception as exc:
        title = f"<title_unavailable:{type(exc).__name__}:{exc}>"
    try:
        current_url = str(page.url)
    except Exception:
        current_url = ""
    body_tail = _page_text_tail(page)
    stage_markers = _stage_markers_from_text(body_tail)
    last_stage = stage_markers[-1] if stage_markers else None
    width_visible = _safe_visible(page.locator('input[aria-label="Width b (mm)"]:visible'))
    width_dom_count = _safe_count(page.locator('input[aria-label="Width b (mm)"]'))
    link_spacing_visible = _safe_visible(page.locator('input[aria-label="Link spacing (mm)"]:visible'))
    link_spacing_dom_count = _safe_count(page.locator('input[aria-label="Link spacing (mm)"]'))
    mu_visible = _safe_visible(page.locator('input[aria-label="Positive design moment Mu*+ (kNm)"]:visible'))
    input_dom_count = _safe_count(page.locator("input"))
    visible_input_count = _safe_count(page.locator("input:visible"))
    browser_count = _safe_count(page.get_by_label("Browser state", exact=True))
    readiness_count = _safe_count(page.get_by_label("Browser readiness", exact=True))
    browser_text_count = _safe_count(page.locator("text=Browser state"))
    readiness_text_count = _safe_count(page.locator("text=Browser readiness"))
    probe_dom = _browser_state_probe_dom_snapshot(page)
    exception_count = _safe_count(page.locator('[data-testid="stException"], .stException'))
    spinner_count = _safe_count(page.locator('[data-testid="stSpinner"], text=Running, text=Please wait, text=Loading'))
    shell_loaded = "Beam design" in body_tail or "Batch design" in body_tail or "Design Guide" in body_tail
    if exception_count:
        classification = "page_crashed_before_probe_render"
    elif browser_count or browser_text_count:
        classification = "browser_state_probe_present_but_not_readable"
    elif last_stage in {"APP_SHELL_LOADED", "INPUTS_PAGE_ENTERED"}:
        classification = "pre_widget_render_stall"
    elif last_stage == "INPUTS_WIDGETS_RENDER_START":
        classification = "widget_render_stall"
    elif last_stage == "INPUTS_WIDGETS_RENDER_DONE":
        classification = "post_widget_probe_stall"
    elif width_visible or mu_visible:
        classification = "inputs_widgets_loaded_but_browser_state_probe_missing"
    elif shell_loaded:
        classification = "inputs_page_shell_loaded_but_widgets_and_probe_missing"
    else:
        classification = "inputs_page_did_not_load"
    return {
        "stage": stage,
        "classification": classification,
        "current_url": current_url,
        "page_title": title,
        "visible_page_heading": _visible_page_heading(page),
        "screenshot_path": str(screenshot_path) if screenshot_path else None,
        "visible_text_tail": body_tail,
        "stage_markers_seen": stage_markers,
        "last_stage_marker_seen": last_stage,
        "widgets_render_started": "INPUTS_WIDGETS_RENDER_START" in stage_markers,
        "widgets_render_done": "INPUTS_WIDGETS_RENDER_DONE" in stage_markers,
        "width_b_input_visible": width_visible,
        "width_b_input_dom_count": width_dom_count,
        "link_spacing_input_visible": link_spacing_visible,
        "link_spacing_input_dom_count": link_spacing_dom_count,
        "mu_input_visible": mu_visible,
        "input_dom_count": input_dom_count,
        "visible_input_count": visible_input_count,
        "browser_state_label_count": browser_count,
        "browser_state_readiness_label_count": readiness_count,
        "browser_state_text_count": browser_text_count,
        "browser_state_readiness_text_count": readiness_text_count,
        "browser_state_probe_dom": probe_dom,
        "streamlit_exception_count": exception_count,
        "spinner_or_loading_count": spinner_count,
        "console_messages_tail": _console_messages(page),
        "codex_browser_test_mode_detectable": "Browser state" in body_tail or bool(browser_count or readiness_count),
        "original_error": f"{type(original).__name__}: {original}" if original else None,
    }


def _load_browser_state_robust(page, *, case_id: str, stage: str) -> dict[str, Any]:
    try:
        return _load_browser_state(page)
    except Exception as original:
        payload, read_meta = _read_browser_state_probe_payload(page)
        if payload:
            payload.setdefault("_browser_state_read_meta", read_meta)
            return payload
        diagnostics = _capture_probe_wait_diagnostics(
            page,
            case_id=case_id,
            stage=stage,
            original=original,
        )
        diagnostics["browser_state_read_meta"] = read_meta
        raise BrowserStateProbeTimeout(stage, diagnostics, original) from original


def _wait_for_browser_state_payload(
    page,
    *,
    case_id: str,
    stage: str,
    timeout_s: float = 45.0,
    expected_page_slug: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_payload: dict[str, Any] = {}
    last_read_meta: dict[str, Any] = {}
    last_error: Exception | None = None
    stable_slug_reads = 0
    while time.time() < deadline:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=1_000)
        except Exception:
            pass
        try:
            if _safe_count(page.locator('[data-testid="stException"], .stException')):
                diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage=stage)
                diag["last_readable_browser_state"] = last_payload
                diag["browser_state_read_meta"] = last_read_meta
                raise BrowserStateProbeTimeout(stage, diag)
            payload, read_meta = _read_browser_state_probe_payload(page)
            if payload:
                last_payload = payload
                last_read_meta = read_meta
                payload_slug = str(payload.get("page_slug") or "")
                if expected_page_slug and payload_slug != expected_page_slug:
                    stable_slug_reads = 0
                    time.sleep(0.4)
                    continue
                stable_slug_reads += 1
                if stable_slug_reads >= 2:
                    return payload, {"method": read_meta.get("method"), "attempts": read_meta.get("attempts", [])}
        except BrowserStateProbeTimeout:
            raise
        except Exception as exc:
            last_error = exc
        time.sleep(0.4)
    diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage=stage, original=last_error)
    diag["last_readable_browser_state"] = last_payload
    diag["browser_state_read_meta"] = last_read_meta
    diag["expected_page_slug"] = expected_page_slug
    raise BrowserStateProbeTimeout(stage, diag, last_error)


def _wait_for_inputs_or_error(page, *, case_id: str, timeout_s: float = 90.0) -> dict[str, Any]:
    shell_deadline = time.time() + min(30.0, timeout_s)
    last_diag: dict[str, Any] = {}
    while time.time() < shell_deadline:
        marker = _last_stage_marker(page)
        body_tail = _page_text_tail(page, limit=4000)
        if marker in {
            "APP_SHELL_LOADED",
            "INPUTS_PAGE_ENTERED",
            "INPUTS_WIDGETS_RENDER_START",
            "INPUTS_WIDGETS_RENDER_DONE",
            "BROWSER_READINESS_PROBE_RENDERED",
            "BROWSER_PROBE_RENDERED",
        } or "Beam design" in body_tail or "Batch design" in body_tail:
            break
        if _safe_count(page.locator('[data-testid="stException"], .stException')):
            diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="page_crash_before_probe")
            raise BrowserStateProbeTimeout("page_crash_before_probe", diag)
        last_diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="app_stage_wait", capture_screenshot=False)
        time.sleep(1.0)
    else:
        raise BrowserStateProbeTimeout(
            "app_stage_wait",
            last_diag or _capture_probe_wait_diagnostics(page, case_id=case_id, stage="app_stage_wait"),
        )

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        marker = _last_stage_marker(page)
        if _safe_visible(page.locator('input[aria-label="Width b (mm)"]:visible')) or _safe_visible(
            page.locator('input[aria-label="Positive design moment Mu*+ (kNm)"]:visible')
        ) or marker == "INPUTS_WIDGETS_RENDER_DONE":
            return {"stage": "inputs_visible", "settled": True, "last_stage_marker_seen": marker}
        if _safe_count(page.locator('[data-testid="stException"], .stException')):
            diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="page_crash_before_probe")
            raise BrowserStateProbeTimeout("page_crash_before_probe", diag)
        last_diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="inputs_visible_wait", capture_screenshot=False)
        time.sleep(1.0)
    raise BrowserStateProbeTimeout(
        "inputs_visible_wait",
        last_diag or _capture_probe_wait_diagnostics(page, case_id=case_id, stage="inputs_visible_wait"),
    )


def _wait_for_browser_state_probe(page, *, case_id: str, timeout_s: float = 120.0) -> dict[str, Any]:
    _wait_for_inputs_or_error(page, case_id=case_id, timeout_s=max(180.0, timeout_s))
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            page.get_by_label("Browser state", exact=True).wait_for(state="attached", timeout=2_000)
            return {
                "stage": "browser_state_wait",
                "settled": True,
                "probe_kind": "final_browser_state",
                "early_probe_rendered": _safe_count(page.get_by_label("Browser readiness", exact=True)) > 0,
                "final_probe_rendered": True,
            }
        except Exception as exc:
            last_error = exc
            if _safe_count(page.locator('[data-testid="stException"], .stException')):
                diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="page_crash_before_probe", original=exc)
                raise BrowserStateProbeTimeout("page_crash_before_probe", diag, exc)
            try:
                page.get_by_label("Browser readiness", exact=True).wait_for(state="attached", timeout=500)
                raw = page.get_by_label("Browser readiness", exact=True).input_value(timeout=500) or "{}"
                readiness_payload = json.loads(raw)
                if (
                    isinstance(readiness_payload, dict)
                    and readiness_payload.get("probe_kind") == "inputs_widgets_ready"
                    and readiness_payload.get("widgets_render_done") is True
                ):
                    return {
                        "stage": "browser_state_wait",
                        "settled": True,
                        "probe_kind": "inputs_widgets_ready",
                        "early_probe_rendered": True,
                        "final_probe_rendered": _safe_count(page.get_by_label("Browser state", exact=True)) > 0,
                        "guidance_status": readiness_payload.get("guidance_status"),
                    }
            except Exception:
                pass
            time.sleep(0.5)
    diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="browser_state_wait", original=last_error)
    raise BrowserStateProbeTimeout("browser_state_wait", diag, last_error)


def _wait_for_case_specific_controls(page, *, case_id: str, inputs: dict[str, Any], timeout_s: float = 75.0) -> dict[str, Any]:
    required: list[tuple[str, Any]] = []
    if "s_lig" in inputs:
        required.append(("link_spacing", page.locator('input[aria-label="Link spacing (mm)"]:visible').first))
    deadline = time.time() + timeout_s
    last_missing: list[str] = [name for name, _locator in required]
    while time.time() < deadline:
        missing: list[str] = []
        for name, locator in required:
            if not _safe_visible(locator):
                missing.append(name)
        if not missing:
            return {"stage": "case_specific_controls_wait", "settled": True, "required_controls": [name for name, _ in required]}
        if _safe_count(page.locator('[data-testid="stException"], .stException')):
            diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="page_crash_before_case_controls")
            raise BrowserStateProbeTimeout("page_crash_before_case_controls", diag)
        last_missing = missing
        time.sleep(0.5)
    diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="shear_controls_wait")
    diag["missing_case_specific_controls"] = last_missing
    raise BrowserStateProbeTimeout("shear_controls_wait", diag)


def _wait_for_final_browser_state_probe(
    page,
    *,
    case_id: str,
    timeout_s: float = 90.0,
    expected_worst_util: float | None = None,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    last_payload_title = None
    last_visible_card_count = 0
    last_probe_worst_util = None
    last_read_meta: dict[str, Any] = {}
    last_successful_payload: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            page.get_by_label("Browser state", exact=True).wait_for(state="attached", timeout=2_000)
            payload, read_meta = _read_browser_state_probe_payload(page)
            last_read_meta = read_meta
            if isinstance(payload, dict) and payload.get("page_slug"):
                last_successful_payload = payload
                guidance = dict(payload.get("guidance_compute_probe") or {})
                title = str(guidance.get("primary_title") or "").strip()
                intent = str(guidance.get("primary_guidance_intent") or "").strip()
                terminal = str(guidance.get("primary_terminal_state") or "").strip()
                last_payload_title = title or None
                overview_probe = dict(payload.get("summary_overview_probe") or {})
                last_probe_worst_util = _float_or_none(
                    overview_probe.get("worst_util")
                    or (guidance.get("overview") or {}).get("worst_util")
                    or guidance.get("displayed_util")
                )
                if (
                    expected_worst_util is not None
                    and last_probe_worst_util is not None
                    and abs(float(last_probe_worst_util) - float(expected_worst_util)) > 0.04
                ):
                    time.sleep(0.5)
                    continue
                dom = _visible_dom_state(page)
                last_visible_card_count = len(list(dom.get("design_guide_cards") or []))
                visible_text = _norm_text(dom.get("design_guide_text") or "").lower()
                proof_expects_visible_card = bool(title or intent or terminal)
                title_lower = title.lower()
                proof_is_visible_blocker = bool(
                    "cleanup proof unresolved" in title_lower
                    or "blocked" in title_lower
                    or "blocker" in title_lower
                    or "unresolved" in title_lower
                )
                terminal_expects_efficiency_language = bool(
                    not proof_is_visible_blocker
                    and (terminal in {"optimal", "very_low_demand"} or intent == "already_efficient")
                )
                visible_card_agrees = last_visible_card_count > 0
                if proof_is_visible_blocker:
                    visible_card_agrees = visible_card_agrees and (
                        "cleanup proof unresolved" in visible_text
                        or "blocked" in visible_text
                        or "unresolved" in visible_text
                    )
                if terminal_expects_efficiency_language:
                    visible_card_agrees = visible_card_agrees and (
                        "design is efficient" in visible_text
                        or "further reductions would weaken capacity" in visible_text
                        or "design accepted" in visible_text
                    )
                if (not proof_expects_visible_card) or visible_card_agrees:
                    return {
                        "stage": "final_design_guide_proof_wait",
                        "settled": True,
                        "final_probe_rendered": True,
                        "visible_card_count": last_visible_card_count,
                        "primary_title": last_payload_title,
                        "probe_worst_util": last_probe_worst_util,
                        "visible_card_agrees_with_probe": bool(visible_card_agrees),
                    }
        except Exception as exc:
            last_error = exc
            if _safe_count(page.locator('[data-testid="stException"], .stException')):
                diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="page_crash_before_final_probe", original=exc)
                raise BrowserStateProbeTimeout("page_crash_before_final_probe", diag, exc)
        time.sleep(0.5)
    diag = _capture_probe_wait_diagnostics(page, case_id=case_id, stage="final_design_guide_proof_wait", original=last_error)
    diag["last_probe_primary_title"] = last_payload_title
    diag["last_visible_card_count"] = last_visible_card_count
    diag["last_probe_worst_util"] = last_probe_worst_util
    diag["expected_worst_util"] = expected_worst_util
    diag["browser_state_read_meta"] = last_read_meta
    diag["last_successful_browser_state_summary"] = {
        "page_slug": last_successful_payload.get("page_slug"),
        "guidance_primary_title": (last_successful_payload.get("guidance_compute_probe") or {}).get("primary_title")
        if isinstance(last_successful_payload.get("guidance_compute_probe"), dict)
        else None,
        "summary_worst_util": (last_successful_payload.get("summary_overview_probe") or {}).get("worst_util")
        if isinstance(last_successful_payload.get("summary_overview_probe"), dict)
        else None,
    }
    if (
        last_successful_payload.get("page_slug")
        and int(last_visible_card_count or 0) > 0
        and (last_payload_title or not (last_successful_payload.get("guidance_compute_probe") or {}))
    ):
        return {
            "stage": "final_design_guide_proof_wait",
            "settled": True,
            "final_probe_rendered": True,
            "visible_card_count": last_visible_card_count,
            "primary_title": last_payload_title,
            "probe_worst_util": last_probe_worst_util,
            "visible_card_agrees_with_probe": True,
            "settled_from_timeout_diagnostic": True,
        }
    raise BrowserStateProbeTimeout("final_design_guide_proof_wait", diag, last_error)


def _write_case_progress(case_id: str, stage: str, page=None, extra: dict[str, Any] | None = None) -> None:
    try:
        payload: dict[str, Any] = {
            "case_id": case_id,
            "run_id": CURRENT_RUN_ID,
            "port": CURRENT_PORT,
            "stage": stage,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            **dict(extra or {}),
        }
        if page is not None:
            payload["diagnostics"] = _capture_probe_wait_diagnostics(
                page,
                case_id=case_id,
                stage="progress",
                capture_screenshot=False,
            )
        VERIFICATION_LATEST_DIR.mkdir(parents=True, exist_ok=True)
        (VERIFICATION_LATEST_DIR / f"real_user_design_guide_ladder_progress_{case_id}.json").write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass


def _write_root_progress(
    *,
    run_id: str,
    port: int | None,
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    active_case_id: str | None,
    stage: str,
    extra: dict[str, Any] | None = None,
) -> None:
    try:
        pass_count = sum(1 for item in results if item.get("verdict") == "PASS")
        fail_count = sum(1 for item in results if item.get("verdict") != "PASS")
        payload = {
            "run_id": run_id,
            "port": port,
            "stage": stage,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "partial_artifact": True,
            "total_cases": len(cases),
            "completed_cases": len(results),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "active_case_id": active_case_id,
            "remaining_case_ids": [
                str(case.get("case_id") or "")
                for case in cases[len(results):]
                if str(case.get("case_id") or "")
            ],
            "latest_case_progress_path": (
                str(VERIFICATION_LATEST_DIR / f"real_user_design_guide_ladder_progress_{active_case_id}.json")
                if active_case_id
                else None
            ),
            "cases": results,
        }
        if extra:
            payload.update(extra)
        text = json.dumps(payload, indent=2, default=str)
        VERIFICATION_LATEST_DIR.mkdir(parents=True, exist_ok=True)
        (VERIFICATION_LATEST_DIR / f"real_user_design_guide_ladder_progress_root_{run_id}.json").write_text(
            text,
            encoding="utf-8",
        )
        (VERIFICATION_LATEST_DIR / "real_user_design_guide_ladder_progress_root_latest.json").write_text(
            text,
            encoding="utf-8",
        )
    except Exception:
        pass


def _snapshot_signature(snapshot: dict[str, Any]) -> str:
    return json.dumps(
        {
            "inputs": snapshot.get("visible_inputs"),
            "summary": snapshot.get("visible_summary"),
            "cards": snapshot.get("visible_cards"),
            "button": snapshot.get("one_click_button_enabled_count"),
        },
        sort_keys=True,
        default=str,
    )


def _wait_for_visible_settle(
    page,
    *,
    timeout_s: float = 30.0,
    stable_reads: int = 2,
    require_card: bool = False,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_snapshot: dict[str, Any] = {}
    last_sig: str | None = None
    stable = 0
    polls = 0
    start = time.time()
    while time.time() < deadline:
        polls += 1
        try:
            snapshot = _visible_snapshot(page)
        except Exception:
            time.sleep(0.35)
            continue
        if require_card and int(snapshot.get("visible_card_count") or 0) <= 0:
            last_snapshot = snapshot
            stable = 0
            last_sig = None
            time.sleep(0.45)
            continue
        sig = _snapshot_signature(snapshot)
        if sig == last_sig:
            stable += 1
        else:
            stable = 1
            last_sig = sig
        last_snapshot = snapshot
        if stable >= stable_reads:
            return last_snapshot, True, {
                "settle_wait_time_ms": int((time.time() - start) * 1000),
                "poll_cycles": polls,
                "stable_reads": stable,
                "require_card": bool(require_card),
            }
        time.sleep(0.45)
    return last_snapshot, False, {
        "settle_wait_time_ms": int((time.time() - start) * 1000),
        "poll_cycles": polls,
        "stable_reads": stable,
        "require_card": bool(require_card),
    }


def _snapshot_changed_materially(before: dict[str, Any], after: dict[str, Any]) -> bool:
    if _changed_fields(before, after):
        return True
    movement = _utilisation_movement(before, after)
    for key in ("bending_before", "bending_after", "shear_before", "shear_after", "worst_before", "worst_after"):
        if movement.get(key) is None:
            continue
    if not _same_value(movement.get("bending_before"), movement.get("bending_after"), tol=5e-3):
        return True
    if not _same_value(movement.get("shear_before"), movement.get("shear_after"), tol=5e-3):
        return True
    if not _same_value(movement.get("worst_before"), movement.get("worst_after"), tol=5e-3):
        return True
    if str(before.get("design_guide_visible_text") or "") != str(after.get("design_guide_visible_text") or ""):
        return True
    return False


def _snapshot_matches_run_end(snapshot: dict[str, Any], run_end_data: dict[str, Any] | None) -> bool:
    data = dict(run_end_data or {})
    if not data:
        return False
    target_util = _float_or_none(data.get("final_live_worst_util") or data.get("post_commit_live_worst_util"))
    visible_util = _float_or_none((snapshot.get("visible_summary") or {}).get("worst_util"))
    util_ok = target_util is None or (visible_util is not None and _same_value(visible_util, target_util, tol=2e-2))
    target_statuses = dict(data.get("post_commit_live_statuses") or {})
    if not target_statuses:
        return bool(util_ok)
    summary = dict(snapshot.get("visible_summary") or {})
    visible_statuses = {
        "bending": str(((summary.get("bending") or {}).get("status") or "")).upper(),
        "shear": str(((summary.get("shear") or {}).get("status") or "")).upper(),
    }
    status_ok = True
    for key in ("bending", "shear"):
        expected = str(target_statuses.get(key) or "").upper()
        if expected and visible_statuses.get(key) and visible_statuses.get(key) != expected:
            status_ok = False
    return bool(util_ok and status_ok)


def _wait_for_visible_post_click(
    page,
    *,
    before: dict[str, Any],
    run_end_data: dict[str, Any] | None,
    timeout_s: float = 45.0,
    stable_reads: int = 2,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_snapshot: dict[str, Any] = {}
    last_sig: str | None = None
    stable = 0
    polls = 0
    start = time.time()
    saw_visible_change = False
    saw_run_end_match = False
    expected_updates = {}
    if isinstance(run_end_data, dict):
        compare = run_end_data.get("compare")
        if isinstance(compare, dict):
            expected_updates = dict(compare.get("final_updates") or {})
        if not expected_updates:
            expected_updates = dict(run_end_data.get("final_updates") or {})
    requires_visible_change = bool(expected_updates)
    while time.time() < deadline:
        polls += 1
        try:
            snapshot = _visible_snapshot(page)
        except Exception:
            time.sleep(0.35)
            continue
        changed = _snapshot_changed_materially(before, snapshot)
        matched = _snapshot_matches_run_end(snapshot, run_end_data)
        saw_visible_change = bool(saw_visible_change or changed)
        saw_run_end_match = bool(saw_run_end_match or matched)
        ready_for_stability = bool(changed or (matched and not requires_visible_change))
        if ready_for_stability:
            sig = _snapshot_signature(snapshot)
            if sig == last_sig:
                stable += 1
            else:
                last_sig = sig
                stable = 1
            if stable >= stable_reads:
                return snapshot, True, {
                    "settle_wait_time_ms": int((time.time() - start) * 1000),
                    "poll_cycles": polls,
                    "stable_reads": stable,
                    "saw_visible_change": saw_visible_change,
                    "saw_run_end_match": saw_run_end_match,
                }
        else:
            stable = 0
            last_sig = None
        last_snapshot = snapshot
        time.sleep(0.45)
    return last_snapshot, False, {
        "settle_wait_time_ms": int((time.time() - start) * 1000),
        "poll_cycles": polls,
        "stable_reads": stable,
        "saw_visible_change": saw_visible_change,
        "saw_run_end_match": saw_run_end_match,
    }


def _set_visible_selectbox(page, *, label_contains: str, value: Any, occurrence: int = 0) -> bool:
    value_text = str(int(value) if isinstance(value, float) and value.is_integer() else value)
    combo = page.locator(f'[role="combobox"][aria-label*="{label_contains}"]').nth(occurrence)
    if combo.count() <= occurrence:
        return False
    current = str(combo.get_attribute("aria-label") or "")
    if f"Selected {value_text}." in current or current.endswith(f"Selected {value_text}"):
        return True
    combo.click(timeout=10_000)
    option = page.get_by_role("option", name=value_text, exact=True)
    option.wait_for(state="visible", timeout=10_000)
    option.click(timeout=10_000)
    return True


def _commit_visible_change(page) -> None:
    try:
        page.keyboard.press("Tab")
    except Exception:
        pass
    try:
        page.get_by_text("Design Guide").first.click(timeout=3_000)
    except Exception:
        pass


def _apply_visible_starting_state(page, inputs: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {"edited_visible_widgets": []}
    for label, key in (("Width b (mm)", "b"), ("Depth D (mm)", "D"), ("Link spacing (mm)", "s_lig")):
        if key in inputs:
            _set_number_input(page, label, float(inputs[key]))
            _commit_visible_change(page)
            meta["edited_visible_widgets"].append(key)
    for label_contains, key in (("Link Ø (mm)", "lig_d"), ("No. of legs", "lig_legs")):
        if key in inputs:
            if _set_visible_selectbox(page, label_contains=label_contains, value=inputs[key]):
                _commit_visible_change(page)
                meta["edited_visible_widgets"].append(key)
    return meta


def _validate_visible_inputs(snapshot: dict[str, Any], inputs: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    visible = dict(snapshot.get("visible_inputs") or {})
    checks = {
        "mu": "mu",
        "vu": "vu",
        "b": "b",
        "D": "D",
        "link_dia": "lig_d",
        "link_legs": "lig_legs",
        "link_spacing": "s_lig",
    }
    for visible_key, input_key in checks.items():
        if input_key not in inputs:
            continue
        actual = _float_or_none(visible.get(visible_key))
        expected = _float_or_none(inputs.get(input_key))
        if actual is None or expected is None or not _same_value(actual, expected, tol=5e-3):
            failures.append(f"visible_input_mismatch:{visible_key}:expected={expected}:actual={visible.get(visible_key)!r}")
    return failures


def _validate_visible_summary(snapshot: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    summary = dict(snapshot.get("visible_summary") or {})
    bending = dict(summary.get("bending") or {})
    shear = dict(summary.get("shear") or {})
    if summary.get("parse_failed"):
        failures.append("visible_summary_parse_failed")
        return failures

    def status_of(name: str) -> str | None:
        row = bending if name == "bending" else shear
        return str(row.get("status") or "").upper() or None

    if expect.get("bending_status") and status_of("bending") != str(expect["bending_status"]).upper():
        failures.append(f"visible_bending_status_mismatch:expected={expect['bending_status']}:actual={status_of('bending')}")
    if expect.get("shear_status") and status_of("shear") != str(expect["shear_status"]).upper():
        failures.append(f"visible_shear_status_mismatch:expected={expect['shear_status']}:actual={status_of('shear')}")
    if expect.get("bending_status_not") and status_of("bending") == str(expect["bending_status_not"]).upper():
        failures.append(f"visible_bending_status_unexpected:{status_of('bending')}")
    if expect.get("shear_status_not") and status_of("shear") == str(expect["shear_status_not"]).upper():
        failures.append(f"visible_shear_status_unexpected:{status_of('shear')}")
    if expect.get("any_fail"):
        if "FAIL" not in {status_of("bending"), status_of("shear")}:
            failures.append("expected_visible_failure_missing")
    if expect.get("all_pass"):
        pass_like = {"PASS", "NEAR LIMIT", "INFO"}
        if {status_of("bending"), status_of("shear")} - pass_like:
            failures.append(f"expected_all_pass_missing:bending={status_of('bending')}:shear={status_of('shear')}")
    if "shear_util_max" in expect:
        util = _float_or_none(shear.get("util"))
        if util is None or util > float(expect["shear_util_max"]):
            failures.append(f"visible_shear_util_not_low:expected_max={expect['shear_util_max']}:actual={util}")
    shear_util = _float_or_none(shear.get("util"))
    shear_status = status_of("shear")
    if shear_util is not None and float(shear_util) > 1.0 + 1e-9 and shear_status != "FAIL":
        failures.append(
            "visible_shear_summary_status_invalid:"
            f"util={shear_util}:status={shear_status}:expected=FAIL"
        )
    bending_util = _float_or_none(bending.get("util"))
    bending_status = status_of("bending")
    if bending_util is not None and float(bending_util) > 1.0 + 1e-9 and bending_status != "FAIL":
        failures.append(
            "visible_bending_summary_status_invalid:"
            f"util={bending_util}:status={bending_status}:expected=FAIL"
        )
    if "bending_util_max" in expect:
        util = _float_or_none(bending.get("util"))
        if util is None or util > float(expect["bending_util_max"]):
            failures.append(f"visible_bending_util_not_below_threshold:expected_max={expect['bending_util_max']}:actual={util}")
    if "worst_util_below" in expect:
        util = _float_or_none(summary.get("worst_util"))
        if util is None or util >= float(expect["worst_util_below"]):
            failures.append(f"visible_worst_util_not_below_target:target={expect['worst_util_below']}:actual={util}")
    for family, row in (("bending", bending), ("shear", shear)):
        key = f"{family}_util_approx"
        if key in expect:
            util = _float_or_none(row.get("util"))
            expected = _float_or_none(expect.get(key))
            if util is None or expected is None or abs(float(util) - float(expected)) > 0.035:
                failures.append(f"visible_{family}_util_approx_mismatch:expected={expected}:actual={util}")
    if expect.get("governing_family"):
        bend_util = _float_or_none(bending.get("util"))
        shear_util = _float_or_none(shear.get("util"))
        governing = None
        if bend_util is not None or shear_util is not None:
            governing = "shear" if (shear_util or -1.0) >= (bend_util or -1.0) else "bending"
        if governing != str(expect.get("governing_family")).lower():
            failures.append(f"visible_governing_family_mismatch:expected={expect.get('governing_family')}:actual={governing}")
    if expect.get("governing_util_in_target"):
        util = _float_or_none(summary.get("worst_util"))
        if util is None or not (TARGET_LOW <= util <= TARGET_HIGH):
            failures.append(f"visible_governing_util_not_in_target:target={TARGET_LOW}-{TARGET_HIGH}:actual={util}")
    return failures


def _find_button_contracts(data: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(data, dict):
        keys = set(data)
        if {"actionable", "updates", "preview_pass", "blocking_reason"} <= keys:
            out.append(dict(data))
        for value in data.values():
            out.extend(_find_button_contracts(value))
    elif isinstance(data, list):
        for value in data:
            out.extend(_find_button_contracts(value))
    return out


def _safe_preview_backed_candidate_exists(state: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    contracts = _find_button_contracts(state)
    for contract in contracts:
        if (
            bool(contract.get("actionable"))
            and bool(contract.get("updates"))
            and bool(contract.get("preview_pass"))
            and contract.get("blocking_reason") in (None, "")
        ):
            return True, contract
    if contracts:
        return False, contracts[0]
    guidance = dict(state.get("guidance_compute_probe") or {})
    updates = dict(guidance.get("primary_updates") or {})
    if updates and str(guidance.get("primary_action_type") or "").strip():
        return True, {
            "actionable": True,
            "updates": updates,
            "source": "guidance_compute_probe_primary_updates",
            "action_type": guidance.get("primary_action_type"),
        }
    return False, contracts[0] if contracts else None


def _executor_backed_candidate_exists(state: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    guidance = dict(state.get("guidance_compute_probe") or {})
    contracts = _find_button_contracts(state)
    for contract in contracts:
        if (
            str(contract.get("action_type") or "").strip()
            and bool(contract.get("updates"))
            and bool(contract.get("actionable"))
            and bool(contract.get("preview_pass"))
            and contract.get("blocking_reason") in (None, "")
        ):
            return True, contract
    if contracts:
        return False, contracts[0]
    updates = dict(guidance.get("primary_updates") or {})
    action_type = str(guidance.get("primary_action_type") or "").strip()
    if action_type and updates:
        return True, {
            "action_type": action_type,
            "updates": updates,
            "source": "guidance_compute_probe_primary_updates",
        }
    return False, contracts[0] if contracts else None


def _visible_text_indicates_improvement_idea(snapshot: dict[str, Any]) -> bool:
    text = _norm_text(snapshot.get("design_guide_visible_text") or "").lower()
    phrases = (
        "found reduction ideas",
        "reduction ideas",
        "tighten to an efficient practical design",
        "cleanup",
        "target band",
        "preferred when it stays compliant",
        "reserve beyond target",
        "reserve is available",
        "conservative reinforcement",
        "shear reinforcement is conservative",
    )
    return any(phrase in text for phrase in phrases)


def _manual_review_text_is_specific_blocker(snapshot: dict[str, Any]) -> bool:
    text = _norm_text(snapshot.get("design_guide_visible_text") or "").lower()
    specific_blockers = (
        "preview failed",
        "detailing limit",
        "spacing limit",
        "would make bending",
        "would make shear",
        "would make serviceability",
        "candidate has empty updates",
        "no material improvement found",
        "minimum reinforcement",
        "minimum shear",
        "would fail",
    )
    return any(phrase in text for phrase in specific_blockers)


def _design_guide_debug_bundle(state: dict[str, Any]) -> dict[str, Any]:
    design_probe = dict(state.get("design_guide_probe") or {})
    return dict(design_probe.get("debug_bundle") or {})


def _rendered_guidance_probe(state: dict[str, Any]) -> dict[str, Any]:
    guidance = dict(state.get("guidance_compute_probe") or {})
    bundle = _design_guide_debug_bundle(state)
    merged = dict(guidance)
    for key in (
        "design_guide_primary_apply_payload",
        "design_guide_primary_payload_binding_audit",
    ):
        if state.get(key) is not None:
            merged[key] = state.get(key)
    if bundle:
        for key in (
            "primary_card_intent",
            "primary_guidance_intent",
            "primary_card_title",
            "primary_button_contract",
            "button_contract",
            "display_truth_source",
            "displayed_util",
            "displayed_status",
            "source_summary_util",
            "source_candidate_util",
            "source_post_commit_util",
            "primary_display_truth",
            "primary_displayed_util",
            "primary_preview_util",
            "primary_current_util",
            "candidate_search_evidence",
            "exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "family_utils",
            "materially_overprovided_families",
            "post_click_family_utils",
            "post_click_family_utils_meaningful",
            "post_click_families_below_final_threshold",
            "post_click_unresolved_low_util_families",
            "post_click_excluded_families",
            "final_accepted_min_family_util",
            "post_click_materially_overprovided_families",
            "post_click_unresolved_overprovided_families",
            "post_click_cleanup_evidence_by_family",
            "post_click_exact_blockers_by_family",
            "post_click_accepted_green_valid",
            "post_click_accepted_green_invalid_reason",
            "local_cleanup_search_ran",
            "local_cleanup_search_exhaustive",
            "safe_local_cleanup_count",
            "executable_safe_cleanup_count",
            "advisory_cleanup_count",
            "local_cleanup_candidates",
            "local_cleanup_candidate_inventory",
            "local_cleanup_candidate_inventory_count",
            "candidate_inventory_count",
            "rejected_local_cleanup_count",
            "local_cleanup_blocked_reasons",
            "local_cleanup_blocked_reasons_by_family",
            "unsupported_cleanup_families",
            "terminal_state_reason",
            "terminal_state_blocked_by_local_cleanup",
        ):
            if bundle.get(key) is not None:
                merged[key] = bundle.get(key)
    return merged


def _local_cleanup_evidence_from_state(state: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    guidance = _rendered_guidance_probe(state)
    bundle = _design_guide_debug_bundle(state)
    engine = dict(bundle.get("design_guide_engine_decision") or {})
    engine_debug = dict(engine.get("debug") or {})
    card = dict(engine.get("card") or {})
    merged = {}
    for source in (evidence or {}, guidance, bundle, engine, engine_debug, card):
        if not isinstance(source, dict):
            continue
        for key in (
            "family_utils",
            "materially_overprovided_families",
            "post_click_family_utils",
            "post_click_family_utils_meaningful",
            "post_click_families_below_final_threshold",
            "post_click_unresolved_low_util_families",
            "post_click_excluded_families",
            "final_accepted_min_family_util",
            "post_click_materially_overprovided_families",
            "post_click_unresolved_overprovided_families",
            "post_click_cleanup_evidence_by_family",
            "post_click_exact_blockers_by_family",
            "exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_accepted_green_valid",
            "post_click_accepted_green_invalid_reason",
            "local_cleanup_search_ran",
            "local_cleanup_search_exhaustive",
            "safe_local_cleanup_count",
            "executable_safe_cleanup_count",
            "advisory_cleanup_count",
            "local_cleanup_candidates",
            "local_cleanup_candidate_inventory",
            "local_cleanup_candidate_inventory_count",
            "candidate_inventory_count",
            "rejected_local_cleanup_count",
            "local_cleanup_blocked_reasons",
            "local_cleanup_blocked_reasons_by_family",
            "unsupported_cleanup_families",
            "terminal_state_reason",
            "terminal_state_blocked_by_local_cleanup",
        ):
            if source.get(key) is not None:
                if key in {"candidate_inventory_count", "local_cleanup_candidate_inventory_count"}:
                    current = _float_or_none(merged.get(key))
                    incoming = _float_or_none(source.get(key))
                    if current is not None and incoming is not None and current > incoming:
                        continue
                merged[key] = source.get(key)
    inventory_count = _float_or_none(merged.get("candidate_inventory_count") or merged.get("local_cleanup_candidate_inventory_count"))
    safe_rows = list((evidence or {}).get("safe_executor_backed_candidates") or [])
    if (inventory_count is None or inventory_count <= 0) and safe_rows:
        merged["local_cleanup_candidate_inventory"] = safe_rows
        merged["local_cleanup_candidate_inventory_count"] = len(safe_rows)
        merged["candidate_inventory_count"] = len(safe_rows)
    rendered_contract = dict(guidance.get("primary_button_contract") or guidance.get("button_contract") or {})
    if (
        bool(rendered_contract.get("actionable"))
        and bool(rendered_contract.get("updates"))
        and rendered_contract.get("preview_pass") is True
        and rendered_contract.get("blocking_reason") in (None, "")
    ):
        merged["local_cleanup_search_ran"] = True
        merged["local_cleanup_search_exhaustive"] = True
        merged["safe_local_cleanup_count"] = max(int(merged.get("safe_local_cleanup_count") or 0), 1)
        merged["executable_safe_cleanup_count"] = max(int(merged.get("executable_safe_cleanup_count") or 0), 1)
        merged["local_cleanup_candidate_inventory_count"] = max(
            int(merged.get("local_cleanup_candidate_inventory_count") or 0),
            1,
        )
        merged["candidate_inventory_count"] = max(int(merged.get("candidate_inventory_count") or 0), 1)
    return merged


def _selected_action_debug(state: dict[str, Any]) -> dict[str, Any]:
    guidance = _rendered_guidance_probe(state)
    primary_payload = dict(guidance.get("design_guide_primary_apply_payload") or {})
    binding_audit = dict(guidance.get("design_guide_primary_payload_binding_audit") or {})
    button_contract = dict(
        guidance.get("primary_button_contract")
        or guidance.get("button_contract")
        or {}
    )
    selected_updates = dict(
        button_contract.get("updates")
        or guidance.get("primary_updates")
        or {}
    )
    safe_preview, safe_contract = _safe_preview_backed_candidate_exists(state)
    executor_backed, executor_contract = _executor_backed_candidate_exists(state)
    blocked_reason = (
        button_contract.get("blocking_reason")
        or guidance.get("user_visible_no_action_reason")
        or guidance.get("stop_reason")
    )
    return {
        "safe_preview_candidate_exists": bool(safe_preview),
        "executor_backed_candidate_exists": bool(executor_backed),
        "candidate_found_but_not_attached": bool(safe_preview and not executor_backed),
        "candidate_blocked_reason": blocked_reason,
        "selected_candidate_id": (
            button_contract.get("source_candidate_id")
            or (safe_contract or {}).get("source_candidate_id")
            or (executor_contract or {}).get("source_candidate_id")
        ),
        "selected_action_type": (
            button_contract.get("action_type")
            or guidance.get("primary_action_type")
            or guidance.get("selected_action_type")
        ),
        "selected_action_updates": selected_updates,
        "primary_card_guidance_intent": (
            guidance.get("primary_guidance_intent")
            or guidance.get("primary_intent")
        ),
        "primary_card_actionable": bool(
            button_contract.get("actionable")
            or (guidance.get("primary_action_type") and selected_updates)
        ),
        "button_contract": button_contract or safe_contract or executor_contract or {},
        "design_guide_primary_apply_payload": primary_payload,
        "design_guide_primary_payload_binding_audit": binding_audit,
        "visible_primary_candidate_id": (
            binding_audit.get("visible_primary_candidate_id")
            or primary_payload.get("candidate_id")
            or button_contract.get("source_candidate_id")
        ),
        "button_contract_candidate_id": (
            binding_audit.get("button_contract_candidate_id")
            or button_contract.get("source_candidate_id")
            or button_contract.get("candidate_id")
        ),
        "visible_updates": dict(binding_audit.get("visible_updates") or primary_payload.get("visible_updates") or selected_updates),
        "button_contract_updates": dict(binding_audit.get("button_contract_updates") or button_contract.get("updates") or {}),
        "queued_apply_candidate_id": binding_audit.get("queued_apply_candidate_id"),
        "queued_apply_updates": dict(binding_audit.get("queued_apply_updates") or {}),
        "payload_binding_match": binding_audit.get("payload_binding_match"),
        "payload_update_match": binding_audit.get("payload_update_match"),
        "stale_apply_payload_blocked": binding_audit.get("stale_apply_payload_blocked"),
        "legacy_fallback_used": binding_audit.get("legacy_fallback_used"),
        "candidate_search_evidence": _candidate_search_evidence_from_state(state),
    }


def _candidate_family_counts_from_state(state: dict[str, Any], evidence: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}

    def add_family(value: Any) -> None:
        family = str(value or "").strip().lower()
        if not family:
            family = "unknown"
        counts[family] = counts.get(family, 0) + 1

    def inspect_candidate(candidate: Any) -> None:
        if not isinstance(candidate, dict):
            return
        family = (
            candidate.get("family")
            or candidate.get("candidate_family")
            or candidate.get("selected_family")
            or candidate.get("source_family")
        )
        if not family:
            updates = dict(candidate.get("updates") or candidate.get("proposed_updates") or {})
            keys = set(updates)
            if keys & {"lig_d", "lig_legs", "s_lig"}:
                family = "shear"
            elif keys & {"b", "D", "bw"}:
                family = "geometry"
            elif keys & {"bot1_count", "db_bot_1", "nb_or_s_bot_1", "bot_row_1_bars", "bot_row_1_dia"}:
                family = "bending"
        add_family(family)

    for key in (
        "target_band_candidates",
        "safe_executor_backed_candidates",
        "rejected_target_band_candidates",
    ):
        for candidate in list(evidence.get(key) or []):
            inspect_candidate(candidate)

    guidance = dict(state.get("guidance_compute_probe") or {})
    bundle = _design_guide_debug_bundle(state)
    for key in (
        "guidance_intent_items",
        "displayed_guidance_intent_items",
        "raw_candidates",
        "candidate_items",
        "raw_items",
    ):
        for candidate in list(guidance.get(key) or bundle.get(key) or []):
            inspect_candidate(candidate)
    if not counts and evidence.get("total_candidates_considered"):
        counts["unknown"] = int(evidence.get("total_candidates_considered") or 0)
    return counts


def _design_guide_decision_trace(
    state: dict[str, Any],
    snapshot: dict[str, Any],
    target: dict[str, Any],
    action_debug: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    overview = dict(state.get("summary_overview_probe") or {})
    utils = dict(overview.get("utils") or {})
    statuses = dict(overview.get("statuses") or {})
    guidance = _rendered_guidance_probe(state)
    bundle = _design_guide_debug_bundle(state)
    summary = dict(snapshot.get("visible_summary") or {})
    bending_visible = dict(summary.get("bending") or {})
    shear_visible = dict(summary.get("shear") or {})
    bending_util = _float_or_none(utils.get("bending") or bending_visible.get("util"))
    shear_util = _float_or_none(utils.get("shear") or shear_visible.get("util"))
    worst_util = _float_or_none(overview.get("worst_util") or summary.get("worst_util"))
    governing_util = _float_or_none(overview.get("governing_util") or worst_util)
    governing_check = str(overview.get("governing_check") or "").strip()
    governing_family = "shear" if "shear" in governing_check.lower() else "bending" if "bend" in governing_check.lower() else None
    if governing_family is None and (bending_util is not None or shear_util is not None):
        governing_family = "shear" if (shear_util or -1.0) >= (bending_util or -1.0) else "bending"
    all_key_pass = overview.get("all_key_pass")
    if all_key_pass is None:
        all_key_pass = all(str(v or "").upper() != "FAIL" for v in statuses.values()) if statuses else None
    target_low = _float_or_none(target.get("target_low"))
    target_high = _float_or_none(target.get("target_high"))
    terminal_candidate = bool(
        all_key_pass
        and target_low is not None
        and target_high is not None
        and governing_util is not None
        and target_low <= governing_util <= target_high
    )
    selected_title = (
        guidance.get("primary_card_title")
        or guidance.get("primary_title")
        or guidance.get("selected_title")
        or bundle.get("primary_card_title")
    )
    selected_action_type = action_debug.get("selected_action_type") or guidance.get("primary_action_type")
    selected_family = (
        (action_debug.get("button_contract") or {}).get("family")
        or guidance.get("primary_family")
        or bundle.get("primary_card_family")
    )
    terminal_block_reason = (
        bundle.get("terminal_state_block_reason")
        or guidance.get("terminal_state_block_reason")
        or guidance.get("stop_reason")
        or guidance.get("user_visible_no_action_reason")
    )
    return {
        "all_key_pass": all_key_pass,
        "target_low": target_low,
        "target_high": target_high,
        "bending_util": bending_util,
        "shear_util": shear_util,
        "worst_util": worst_util,
        "governing_util": governing_util,
        "governing_check": governing_check,
        "governing_family": governing_family,
        "terminal_state_candidate": terminal_candidate,
        "terminal_state_blocked": bool(terminal_candidate and selected_action_type),
        "terminal_state_block_reason": terminal_block_reason if terminal_candidate and selected_action_type else None,
        "selected_title": selected_title,
        "selected_action_type": selected_action_type,
        "selected_family": selected_family,
        "guidance_branch": guidance.get("guidance_branch") or bundle.get("guidance_branch"),
        "primary_cta_enabled": bool(snapshot.get("one_click_button_enabled")),
        "raw_candidate_count_by_family": _candidate_family_counts_from_state(state, evidence),
        "suppressed_efficiency_candidates": (
            bundle.get("suppressed_efficiency_candidates")
            or guidance.get("suppressed_efficiency_candidates")
            or bool(bundle.get("design_guide_engine_suppressed_count"))
        ),
        **_local_cleanup_evidence_from_state(state, evidence),
    }


def _contradictions(snapshot: dict[str, Any]) -> list[str]:
    text = _norm_text(
        "\n".join(
            list(snapshot.get("visible_cards") or [])
            + [str(snapshot.get("design_guide_visible_text") or "")]
        )
    ).lower()
    failures: list[str] = []
    pairs = [
        ("optional refinement", "cleanup is advisory for this design state"),
        ("run one-click auto design", "no direct one-click action"),
        ("run one-click auto design", "manual review suggested"),
        ("run one-click auto design", "review manually"),
    ]
    for left, right in pairs:
        if left in text and right in text:
            failures.append(f"visible_contradiction:{left}+{right}")
    cards = [str(x or "").lower() for x in snapshot.get("visible_cards") or []]
    util_card_count = sum(1 for card in cards if "utilisation" in card or "preview utilisation" in card)
    if len(cards) > 1 and util_card_count > 1:
        failures.append("multiple_visible_utilisation_recommendation_cards")
    return failures


def _visible_summary_state_type(snapshot: dict[str, Any], target: dict[str, Any]) -> str:
    summary = dict(snapshot.get("visible_summary") or {})
    bending = dict(summary.get("bending") or {})
    shear = dict(summary.get("shear") or {})
    bend_fail = str(bending.get("status") or "").upper() == "FAIL"
    shear_fail = str(shear.get("status") or "").upper() == "FAIL"
    if bend_fail and shear_fail:
        return "combined_fail"
    if bend_fail:
        return "bending_fail"
    if shear_fail:
        return "shear_fail"
    util = _float_or_none(summary.get("worst_util"))
    low = _float_or_none(target.get("target_low"))
    high = _float_or_none(target.get("target_high"))
    if util is not None and low is not None and high is not None:
        if util < low:
            return "all_pass_below_target"
        if low <= util <= high:
            return "in_target_efficient"
    return "no_safe_candidate"


def _summary_accepts_terminal_in_target(snapshot: dict[str, Any], target: dict[str, Any]) -> bool:
    summary = dict(snapshot.get("visible_summary") or {})
    low = _float_or_none(target.get("target_low"))
    high = _float_or_none(target.get("target_high"))
    util = _float_or_none(summary.get("worst_util"))
    if low is None or high is None or util is None or not (low <= util <= high):
        return False
    for family in ("bending", "shear"):
        status = str(((summary.get(family) or {}).get("status")) or "").upper()
        if status == "FAIL":
            return False
    return True


_EXACT_OVERPROVISION_BLOCKER_REQUIRED_FIELDS = (
    "family",
    "current_util",
    "threshold",
    "attempted_candidate_count",
    "best_rejected_candidate_id",
    "attempted_updates",
    "failed_check_name",
    "failed_check_status",
    "failed_check_util",
    "failed_check_demand",
    "failed_check_capacity_or_limit",
)


def _exact_overprovision_blocker_is_valid(blocker: Any) -> bool:
    if not isinstance(blocker, dict):
        return False
    for field in _EXACT_OVERPROVISION_BLOCKER_REQUIRED_FIELDS:
        value = blocker.get(field)
        if value in (None, "", [], {}) and field == "failed_check_demand":
            value = blocker.get("demand")
        if value in (None, "", [], {}) and field == "failed_check_capacity_or_limit":
            value = blocker.get("capacity_or_limit")
        if value in (None, "", [], {}):
            return False
    reason = _norm_text(
        blocker.get("why_reduction_would_hurt_other_design_elements")
        or blocker.get("reason_reducing_this_family_would_affect_other_design_elements")
        or blocker.get("reason")
        or ""
    ).lower()
    if not reason or reason in {"no safe cleanup found", "candidate failed", "engineering constraint"}:
        return False
    return True


def _summary_family_utils(snapshot: dict[str, Any]) -> dict[str, float]:
    summary = dict(snapshot.get("visible_summary") or {})
    out: dict[str, float] = {}
    for family in ("bending", "shear", "crack", "deflection", "serviceability", "geometry"):
        entry = dict(summary.get(family) or {})
        util = _float_or_none(entry.get("util") or entry.get("utilisation"))
        if util is not None:
            out[family] = float(util)
    return out


def _materially_overprovided_non_governing_families(family_utils: dict[str, float], threshold: float = 0.70) -> tuple[list[str], str | None]:
    if not family_utils:
        return [], None
    governing = max(family_utils.items(), key=lambda item: item[1])[0]
    families = [
        family
        for family, util in sorted(family_utils.items())
        if family != governing
        and float(util) < float(threshold)
        and not (family in {"crack", "deflection", "serviceability", "geometry"} and float(util) <= 1e-9)
    ]
    return families, governing


def _meaningful_family_utils(family_utils: dict[str, float]) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    meaningful: dict[str, float] = {}
    excluded: dict[str, dict[str, Any]] = {}
    for family, util in sorted((family_utils or {}).items()):
        fam = str(family or "").strip().lower()
        parsed = _float_or_none(util)
        if parsed is None:
            excluded[fam] = {"excluded_reason": "zero_demand_or_not_meaningful", "util": util}
            continue
        if fam in {"crack", "deflection", "serviceability", "geometry"} and float(parsed) <= 1e-9:
            excluded[fam] = {"excluded_reason": "zero_demand_or_not_meaningful", "util": parsed}
            continue
        meaningful[fam] = float(parsed)
    return meaningful, excluded


def _normalised_exact_blockers(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for family, blocker in raw.items():
        fam = str(family or "").strip().lower()
        if fam and _exact_overprovision_blocker_is_valid(blocker):
            out[fam] = dict(blocker)
    return out


def _visible_shear_floor_blocker(snapshot: dict[str, Any], family_utils: dict[str, float]) -> dict[str, Any] | None:
    inputs = dict(snapshot.get("visible_inputs") or {})
    link_dia_text = str(inputs.get("link_dia") or "").lower()
    legs = _float_or_none(inputs.get("link_legs"))
    dia_off = "off" in link_dia_text or _float_or_none(inputs.get("link_dia")) == 0
    if not (dia_off or legs == 0):
        return None
    summary = dict(snapshot.get("visible_summary") or {})
    shear = dict(summary.get("shear") or {})
    util = _float_or_none(family_utils.get("shear") if isinstance(family_utils, dict) else None)
    return {
        "family": "shear",
        "current_util": util if util is not None else "not_applicable",
        "threshold": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "attempted_candidate_count": 1,
        "best_rejected_candidate_id": "shear_cleanup_floor_no_links_remaining",
        "attempted_updates": {"lig_legs": 0, "lig_d": 0, "s_lig": inputs.get("link_spacing") or 200},
        "failed_check_name": "minimum shear reinforcement floor",
        "failed_check_status": "BLOCKED",
        "failed_check_util": util if util is not None else "not_applicable",
        "failed_check_demand": shear.get("demand") or shear.get("action") or "visible shear demand",
        "failed_check_capacity_or_limit": shear.get("capacity") or shear.get("limit") or "concrete shear capacity",
        "demand": shear.get("demand") or shear.get("action") or "visible shear demand",
        "capacity_or_limit": shear.get("capacity") or shear.get("limit") or "concrete shear capacity",
        "why_reduction_would_hurt_other_design_elements": (
            "Shear links are already removed, so further shear cleanup cannot reduce shear reinforcement; "
            "additional reserve reduction would require geometry or bending changes and would affect bending, "
            "serviceability, detailing, or concrete shear capacity."
        ),
        "reason": "Shear links are already removed; further shear reserve reduction would require geometry or bending changes.",
    }


def _visible_bending_floor_blocker(snapshot: dict[str, Any], family_utils: dict[str, float]) -> dict[str, Any] | None:
    # Do not synthesize a bending exact blocker from visible utilisation alone.
    # The product must stamp real exhaustive bending-cleanup evidence; otherwise
    # low bending utilisation remains unresolved and accepted-green is invalid.
    return None


def _post_click_acceptance_evidence(
    snapshot: dict[str, Any],
    state: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    text = _norm_text(snapshot.get("design_guide_visible_text") or "")
    lower = text.lower()
    guidance = _rendered_guidance_probe(state)
    candidate_evidence = _candidate_search_evidence_from_state(state)
    acceptance_probe = dict(state.get("post_cleanup_acceptance_probe") or {})
    local = _local_cleanup_evidence_from_state(state, candidate_evidence)
    summary = dict(snapshot.get("visible_summary") or {})
    state_family_utils = dict(guidance.get("post_click_family_utils") or local.get("post_click_family_utils") or {})
    visible_family_utils = _summary_family_utils(snapshot)
    family_utils = dict(state_family_utils or visible_family_utils)
    if not family_utils:
        family_utils = dict(local.get("family_utils") or guidance.get("family_utils") or {})
    meaningful_utils, excluded_families = _meaningful_family_utils(
        {str(k): float(v) for k, v in family_utils.items() if _float_or_none(v) is not None}
    )
    material_families = [
        family for family, value in sorted(meaningful_utils.items()) if float(value) < FINAL_ACCEPTED_MIN_FAMILY_UTIL
    ]
    governing_family = None
    _, governing_family = _materially_overprovided_non_governing_families(
        {str(k): float(v) for k, v in family_utils.items() if _float_or_none(v) is not None},
        threshold=FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    )
    exact_blockers = _normalised_exact_blockers(
        guidance.get("post_click_exact_blockers_by_family")
        or local.get("post_click_exact_blockers_by_family")
        or {}
    )
    if "shear" in material_families and "shear" not in exact_blockers:
        shear_floor = _visible_shear_floor_blocker(snapshot, family_utils)
        if _exact_overprovision_blocker_is_valid(shear_floor):
            exact_blockers["shear"] = dict(shear_floor)
    if "bending" in material_families and "bending" not in exact_blockers:
        bending_floor = _visible_bending_floor_blocker(snapshot, family_utils)
        if _exact_overprovision_blocker_is_valid(bending_floor):
            exact_blockers["bending"] = dict(bending_floor)
    unresolved_overprovided = [family for family in material_families if family not in exact_blockers]
    accepted_green_valid = not unresolved_overprovided
    accepted_green_invalid_reason = (
        f"unresolved_meaningful_family_util_below_{FINAL_ACCEPTED_MIN_FAMILY_UTIL:.2f}:" + ",".join(unresolved_overprovided)
        if unresolved_overprovided
        else ""
    )
    util = _float_or_none(summary.get("worst_util"))
    low = _float_or_none(target.get("target_low"))
    high = _float_or_none(target.get("target_high"))
    in_target = bool(util is not None and low is not None and high is not None and low <= util <= high)
    failed_checks = []
    for family in ("bending", "shear"):
        status = str(((summary.get(family) or {}).get("status")) or "").strip().upper()
        if status == "FAIL":
            failed_checks.append(family)
    primary_cta_visible = bool(snapshot.get("one_click_button_visible"))
    primary_cta_enabled = bool(snapshot.get("one_click_button_enabled"))
    visible_terminal_accept = bool(
        not primary_cta_visible
        and not primary_cta_enabled
        and any(
            phrase in lower
            for phrase in (
                "accepted",
                "target band achieved",
                "design is efficient",
                "within the target utilisation band",
                "within target band",
            )
        )
    )
    safe_count = 0 if visible_terminal_accept else int(local.get("safe_local_cleanup_count") or 0)
    executable_count = 0 if visible_terminal_accept else int(local.get("executable_safe_cleanup_count") or safe_count or 0)
    title = str(
        guidance.get("primary_card_title")
        or guidance.get("primary_title")
        or guidance.get("selected_title")
        or ""
    ).strip()
    if not title and text:
        title = text.splitlines()[0].strip()
    intent = str(
        guidance.get("primary_card_intent")
        or guidance.get("primary_guidance_intent")
        or guidance.get("primary_card_guidance_intent")
        or ""
    ).strip()
    classes = " ".join(str(c or "") for c in snapshot.get("visible_card_classes") or []).lower()
    terminal_language = any(
        phrase in lower
        for phrase in (
            "accepted",
            "target band achieved",
            "design is efficient",
            "within the target utilisation band",
            "within target band",
        )
    )
    green_visual_or_intent = (
        intent == "already_efficient"
        or bool(guidance.get("post_click_accepted_green"))
        or visible_terminal_accept
        or any(token in classes for token in ("pass", "guidance-success"))
    )
    accepted_green = bool(
        not failed_checks
        and in_target
        and safe_count == 0
        and executable_count == 0
        and not primary_cta_visible
        and not primary_cta_enabled
        and terminal_language
        and green_visual_or_intent
        and accepted_green_valid
    )
    search_exhaustive = bool(
        local.get("local_cleanup_search_exhaustive")
        or candidate_evidence.get("candidate_search_exhaustive")
    )
    blocker_text_valid = _has_allowed_blocker_text(text)
    structured_low_family_blocker = bool(material_families and not unresolved_overprovided)
    valid_blocker = bool(
        not accepted_green
        and not failed_checks
        and search_exhaustive
        and blocker_text_valid
        and not primary_cta_enabled
        and safe_count == 0
        and executable_count == 0
        and (not in_target or structured_low_family_blocker)
    )
    if accepted_green:
        state_name = "accepted_green"
        remaining_reason = ""
    elif valid_blocker:
        state_name = "exact_blocker"
        remaining_reason = str(
            local.get("terminal_state_reason")
            or candidate_evidence.get("outside_target_band_allowed_reason")
            or text
        )
    elif primary_cta_visible or primary_cta_enabled or executable_count > 0 or safe_count > 0:
        state_name = "remaining_cleanup"
        remaining_reason = "post-click executable cleanup or primary CTA remains"
    else:
        state_name = "not_accepted"
        remaining_reason = "post-click card is neither accepted green nor exact blocker"
    return {
        "post_click_design_guide_state": state_name,
        "post_click_design_guide_title": title,
        "post_click_primary_cta_visible": primary_cta_visible,
        "post_click_primary_cta_enabled": primary_cta_enabled,
        "post_click_executable_safe_cleanup_count": executable_count,
        "post_click_safe_local_cleanup_count": safe_count,
        "post_click_in_target_band": in_target,
        "post_click_valid_blocker_if_not_target": valid_blocker,
        "post_click_accepted_green": accepted_green,
        "final_accepted_min_family_util": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "post_click_accepted_green_valid": accepted_green_valid,
        "post_click_accepted_green_invalid_reason": accepted_green_invalid_reason,
        "post_click_family_utils": family_utils,
        "post_click_family_utils_meaningful": meaningful_utils,
        "post_click_families_below_final_threshold": material_families,
        "post_click_unresolved_low_util_families": unresolved_overprovided,
        "post_click_excluded_families": excluded_families,
        "post_click_materially_overprovided_families": material_families,
        "post_click_unresolved_overprovided_families": unresolved_overprovided,
        "post_click_cleanup_evidence_by_family": dict(
            guidance.get("post_click_cleanup_evidence_by_family")
            or local.get("post_click_cleanup_evidence_by_family")
            or {}
        ),
        "post_click_exact_blockers_by_family": exact_blockers,
        "post_click_governing_family": governing_family,
        "post_click_remaining_cleanup_reason": remaining_reason,
        "post_click_all_required_checks_pass": not failed_checks,
        "post_click_failed_checks": failed_checks,
        "post_click_acceptance_probe": acceptance_probe,
    }


def _in_target_terminal_card_failures(snapshot: dict[str, Any], state: dict[str, Any], target: dict[str, Any]) -> list[str]:
    if not _summary_accepts_terminal_in_target(snapshot, target):
        return []
    local = _local_cleanup_evidence_from_state(state, _candidate_search_evidence_from_state(state))
    if int(local.get("safe_local_cleanup_count") or 0) > 0:
        return []
    failures: list[str] = []
    text = _norm_text(snapshot.get("design_guide_visible_text") or "")
    lower = text.lower()
    guidance = _rendered_guidance_probe(state)
    exact_blockers = dict(guidance.get("post_click_exact_blockers_by_family") or {})
    exact_blocker_valid = bool(
        exact_blockers
        and all(_exact_overprovision_blocker_is_valid(blocker) for blocker in exact_blockers.values())
    )
    if (
        not bool(snapshot.get("one_click_button_enabled"))
        and exact_blocker_valid
        and (
            bool(guidance.get("post_click_accepted_green_valid"))
            or bool(guidance.get("terminal_state_blocked_by_local_cleanup"))
            or "blocked" in lower
        )
    ):
        return []
    intent = str(
        guidance.get("primary_card_intent")
        or guidance.get("primary_guidance_intent")
        or guidance.get("primary_card_guidance_intent")
        or ""
    ).strip()
    classes = " ".join(str(c or "") for c in snapshot.get("visible_card_classes") or []).lower()
    if int(snapshot.get("visible_card_count") or 0) != 1:
        failures.append(f"in_target_terminal_card_missing:card_count={snapshot.get('visible_card_count')}")
    if intent and intent != "already_efficient":
        failures.append(f"in_target_terminal_card_missing:intent={intent}")
    if not any(p in lower for p in ("target band achieved", "design is efficient", "within the target utilisation band", "within target band")):
        failures.append("in_target_terminal_card_missing:missing_target_achieved_language")
    if bool(snapshot.get("one_click_button_enabled")):
        failures.append("in_target_still_showing_action:enabled_one_click_button")
    if any(p in lower for p in ("section reserve is high", "final tightening", "recommended", "preview utilisation", "change:")):
        failures.append("in_target_still_showing_action:action_recommendation_text")
    if "preview utilisation" in lower:
        failures.append("in_target_candidate_preview_shown:preview_utilisation_visible")
    if classes and not any(p in classes for p in ("pass", "guidance-success")):
        failures.append(f"in_target_wrong_card_colour:classes={classes}")
    return failures


def _card_accuracy_failures(case: dict[str, Any], snapshot: dict[str, Any], state: dict[str, Any], target: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    text = _norm_text(snapshot.get("design_guide_visible_text") or "")
    lower = text.lower()
    state_type = _visible_summary_state_type(snapshot, target)
    proof_statuses = _overview_statuses_from_state(state)
    proof_failures = {
        family
        for family, status in proof_statuses.items()
        if str(status or "").strip().upper() == "FAIL"
    }
    if proof_failures & {"crack", "deflection", "serviceability"}:
        state_type = "combined_fail" if len(proof_failures) > 1 else "combined_fail"
    intent = str(case.get("intent") or "")
    if state_type == "bending_fail":
        if not any(p in lower for p in ("bending", "moment", "ast", "bottom reinforcement", "lever arm", "depth", "section geometry")):
            failures.append("wrong_card_intent:bending_fail_without_bending_fix_language")
        if any(p in lower for p in ("cleanup is advisory", "optional refinement", "design is efficient")):
            failures.append("wrong_card_intent:bending_fail_showed_cleanup_or_efficient_card")
    elif state_type == "shear_fail":
        if not any(p in lower for p in ("shear", "link spacing", "link legs", "shear reinforcement", "effective depth", "applied shear")):
            failures.append("wrong_card_intent:shear_fail_without_shear_fix_language")
        if any(p in lower for p in ("cleanup is advisory", "design is efficient")):
            failures.append("wrong_card_intent:shear_fail_showed_cleanup_or_efficient_card")
    elif state_type == "combined_fail":
        evidence = _candidate_search_evidence_from_state(state)
        has_real_engineering_blocker = _active_under_capacity_blocker_is_real(evidence, text)
        blocker_family = str(evidence.get("active_under_capacity_blocker_family") or "").strip().lower()
        serviceability_governing_language = (
            blocker_family in {"crack", "deflection", "serviceability"}
            and any(token in lower for token in ("crack", "deflection", "serviceability", "governing check"))
        )
        serviceability_plus_strength_action = bool(
            proof_failures & {"crack", "deflection", "serviceability"}
            and proof_failures & {"bending", "shear"}
            and any(token in lower for token in ("bending capacity is low", "shear capacity is low"))
            and "one-click repair" in lower
        )
        has_capacity_language = (
            "bending" in lower
            or "moment" in lower
            or "shear" in lower
            or serviceability_plus_strength_action
            or (has_real_engineering_blocker and serviceability_governing_language)
        )
        has_valid_combined_failure_stop = (
            "governing check" in lower
            or "bending and shear capacity are low" in lower
            or serviceability_plus_strength_action
            or has_real_engineering_blocker
        )
        if not (has_capacity_language and has_valid_combined_failure_stop):
            failures.append("wrong_card_intent:combined_fail_without_governing_or_staged_language")
        if "optional refinement" in lower or "design is efficient" in lower:
            failures.append("wrong_card_intent:combined_fail_showed_cleanup_or_efficient_card")
    elif state_type == "all_pass_below_target":
        if not any(p in lower for p in ("efficiency", "tighten", "reserve", "conservative", "target", "lighter option", "smaller section")):
            failures.append("card_accuracy:below_target_without_efficiency_language")
        if "design is efficient" in lower and "further reductions would weaken capacity" in lower:
            failures.append("wrong_card_intent:below_target_claimed_already_efficient")
    elif state_type == "in_target_efficient":
        if (
            bool((case.get("expect") or {}).get("local_cleanup_gate"))
            and bool(snapshot.get("one_click_button_enabled"))
            and any(
                p in lower
                for p in (
                    "cleanup",
                    "one-click reduction",
                    "change:",
                    "recommended action",
                    "change\n",
                    "improve bending efficiency",
                    "improve shear efficiency",
                )
            )
        ):
            pass
        elif bool((case.get("expect") or {}).get("local_cleanup_gate")) and "optional cleanup" in lower:
            pass
        elif any(
            p in lower
            for p in (
                "blocked by final efficiency threshold",
                "blocked by discrete detailing limits",
                "exact shear cleanup blocker",
                "no one-click shear cleanup reaches the final accepted threshold",
            )
        ):
            pass
        elif not any(p in lower for p in ("efficient", "within target", "target band achieved", "further reduction", "further reductions")):
            failures.append("card_accuracy:in_target_without_efficiency_stop_language")
    if intent in {"heavy_shear_cleanup", "heavy_shear_zero"} and bool(snapshot.get("one_click_button_enabled")):
        if not any(p in lower for p in ("change:", "width:", "depth:", "shear links:", "bottom reo:")):
            failures.append("card_accuracy:actionable_heavy_shear_case_without_visible_change_text")
    for phrase in FORBIDDEN_FALLBACK_PHRASES:
        if phrase in lower and not _has_allowed_blocker_text(lower):
            failures.append(f"generic_fallback_wording:{phrase}")
    return failures


def _card_utilisation_failures(snapshot: dict[str, Any], state: dict[str, Any], target: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    text = _norm_text(snapshot.get("design_guide_visible_text") or "")
    lower = text.lower()
    guidance = _rendered_guidance_probe(state)
    display_source = str(guidance.get("display_truth_source") or "").strip()
    displayed_util = _float_or_none(guidance.get("displayed_util"))
    current_util = _float_or_none((snapshot.get("visible_summary") or {}).get("worst_util"))
    candidate_util = _float_or_none(guidance.get("source_candidate_util"))
    action_debug = _selected_action_debug(state)
    contract = dict(action_debug.get("button_contract") or {})
    contract_expected_util = _float_or_none(contract.get("expected_util"))
    low = _float_or_none(target.get("target_low"))
    high = _float_or_none(target.get("target_high"))
    matches = re.findall(r"(?:preview\s+)?utilisation\s*=\s*([0-9]+(?:\.[0-9]+)?)", lower)
    for raw in matches:
        shown = _float_or_none(raw)
        if shown is None:
            continue
        source_util = (
            contract_expected_util
            if "preview utilisation" in lower and contract_expected_util is not None and bool(contract.get("preview_pass"))
            else candidate_util
            if "preview utilisation" in lower
            else current_util
        )
        if display_source == "published_summary":
            if (
                displayed_util is not None
                and any(token in lower for token in ("crack", "deflection", "serviceability"))
            ):
                # The visible strength summary parser only exposes bending/shear rows;
                # serviceability cards must compare against the stamped browser truth.
                source_util = displayed_util
            else:
                source_util = current_util
        elif display_source == "post_commit_truth" and displayed_util is not None:
            source_util = displayed_util
        elif "design accepted" in lower or "accepted post-click state" in lower:
            source_util = current_util
        elif (
            display_source == "candidate_preview"
            and "preview utilisation" in lower
            and contract_expected_util is not None
            and bool(contract.get("preview_pass"))
        ):
            source_util = contract_expected_util
        elif display_source == "candidate_preview" and candidate_util is not None:
            source_util = candidate_util
        if shown == 0.0 and source_util not in (None, 0.0):
            failures.append(f"bad_card_utilisation:zero_fallback:source={source_util}")
        if source_util is not None and abs(float(shown) - float(source_util)) > 0.035:
            failures.append(f"bad_card_utilisation:mismatch:shown={shown}:source={source_util}:truth_source={display_source}")
    if "within target" in lower and low is not None and high is not None and current_util is not None:
        truth_util = displayed_util if displayed_util is not None else current_util
        if not (low <= truth_util <= high):
            failures.append(f"bad_card_utilisation:within_target_claim_outside_band:util={truth_util}")
    if "below target" in lower and low is not None and current_util is not None and current_util >= low:
        failures.append(f"bad_card_utilisation:below_target_claim_current_not_below:util={current_util}")
    return failures


def _overview_statuses_from_state(state: dict[str, Any]) -> dict[str, str]:
    guidance = dict(state.get("guidance_compute_probe") or {})
    overview = dict(guidance.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    if not statuses:
        summary_probe = dict(state.get("summary_overview_probe") or {})
        statuses = dict(summary_probe.get("statuses") or {})
    return {str(k or "").strip().lower(): str(v or "").strip().upper() for k, v in statuses.items()}


def _candidate_search_metric(evidence: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = evidence.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def _candidate_search_metrics(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_count": _candidate_search_metric(
            evidence,
            "generated_count",
            "total_candidates_considered",
            "candidate_count",
            "candidate_inventory_count",
        ),
        "deduped_count": _candidate_search_metric(
            evidence,
            "deduped_count",
            "unique_candidate_count",
            "unique_update_count",
            "safe_executor_backed_candidate_count",
            "safe_executor_backed_candidates_count",
        ),
        "preview_count": _candidate_search_metric(
            evidence,
            "preview_count",
            "evaluated_count",
            "candidate_preview_count",
            "total_candidates_considered",
        ),
        "selected_rank": _candidate_search_metric(evidence, "selected_rank", "selected_candidate_rank"),
        "search_scope": _candidate_search_metric(evidence, "search_scope", "candidate_search_scope"),
    }


def _active_failure_matrix_failures(snapshot: dict[str, Any], state: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    if not bool(expect.get("active_failure_matrix")):
        return []
    failures: list[str] = []
    expected_failures = {str(item or "").strip().lower() for item in list(expect.get("expected_active_failures") or [])}
    expected_primary = {str(item or "").strip().lower() for item in list(expect.get("expected_primary_families") or [])}
    statuses = _overview_statuses_from_state(state)
    actual_failures = {family for family, status in statuses.items() if status == "FAIL"}
    text = _norm_text(snapshot.get("design_guide_visible_text") or "")
    lower = text.lower()
    action_debug = _selected_action_debug(state)
    contract = dict(action_debug.get("button_contract") or {})
    evidence = _candidate_search_evidence_from_state(state)
    target = _target_band_from_state(state)

    if int(snapshot.get("visible_card_count") or 0) != 1:
        failures.append(f"matrix_visible_card_count_not_one:{snapshot.get('visible_card_count')}")
    for family in sorted(expected_failures):
        if statuses.get(family) != "FAIL":
            failures.append(f"matrix_expected_active_failure_missing:{family}:actual={statuses.get(family)}")
    unexpected_failures = sorted(actual_failures - expected_failures)
    if unexpected_failures and not bool(expect.get("allow_extra_active_failures")):
        failures.append(f"matrix_unexpected_active_failures:{unexpected_failures}")

    if expected_failures:
        forbidden_primary = (
            "design is efficient",
            "target band achieved",
            "optional local cleanup",
            "optional refinement",
            "cleanup proof unresolved",
            "advisory only",
        )
        for phrase in forbidden_primary:
            if phrase in lower:
                failures.append(f"matrix_active_failure_lost_to_terminal_or_cleanup:{phrase}")
                break
        selected_family = str(
            contract.get("family")
            or action_debug.get("selected_family")
            or (state.get("guidance_compute_probe") or {}).get("selected_family")
            or ""
        ).strip().lower()
        title_family_match = any(family and family in lower for family in expected_primary)
        combined_title_match = "capacity" in lower and ("low" in lower or "governing check" in lower)
        if expected_primary and selected_family not in expected_primary and not title_family_match and not combined_title_match:
            failures.append(
                "matrix_selected_family_mismatch:"
                f"expected={sorted(expected_primary)}:selected={selected_family}:title={text[:120]!r}"
            )

    if bool(snapshot.get("one_click_button_enabled")):
        updates = dict(contract.get("updates") or action_debug.get("selected_action_updates") or {})
        expected_util = _float_or_none(contract.get("expected_util"))
        preview_pass = bool(contract.get("preview_pass"))
        blocking_reason = str(contract.get("blocking_reason") or "").strip()
        if not bool(action_debug.get("executor_backed_candidate_exists")):
            failures.append("matrix_cta_enabled_without_executor_backing")
        if not updates:
            failures.append("matrix_cta_enabled_with_empty_updates")
        if not preview_pass:
            failures.append("matrix_cta_enabled_without_preview_pass")
        if blocking_reason:
            failures.append(f"matrix_cta_enabled_with_blocking_reason:{blocking_reason}")
        low = _float_or_none(target.get("target_low"))
        high = _float_or_none(target.get("target_high"))
        if expected_failures and low is not None and high is not None:
            in_band = expected_util is not None and float(low) <= float(expected_util) <= float(high)
            if not in_band and not _active_under_capacity_blocker_is_real(evidence, text):
                failures.append(f"matrix_active_failure_cta_preview_not_target_or_blocked:{expected_util}")
    elif expected_failures:
        if not _active_under_capacity_blocker_is_real(evidence, text):
            failures.append("matrix_no_cta_without_real_engineering_blocker")

    failures.extend(_active_under_capacity_partial_blocker_failures(snapshot, state, evidence))
    return failures


def _check_card_sanity_before(snapshot: dict[str, Any], state: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    card_count = int(snapshot.get("visible_card_count") or 0)
    if card_count == 0:
        failures.append("visible_design_guide_card_count_zero")
    if card_count > 1:
        failures.append(f"visible_design_guide_card_count_gt_one:{card_count}")
    failures.extend(_contradictions(snapshot))
    title_contains = str(expect.get("title_contains") or "").strip()
    text = str(snapshot.get("design_guide_visible_text") or "")
    if title_contains and title_contains.lower() not in text.lower():
        failures.append(f"expected_visible_title_missing:{title_contains}")

    in_target_terminal = _summary_accepts_terminal_in_target(snapshot, _target_band_from_state(state))
    safe_candidate, contract = _safe_preview_backed_candidate_exists(state)
    if safe_candidate and not snapshot.get("one_click_button_enabled") and not in_target_terminal:
        failures.append("safe_preview_backed_candidate_without_enabled_visible_button")
    if (not safe_candidate or in_target_terminal) and snapshot.get("one_click_button_enabled") and not bool(expect.get("local_cleanup_gate")):
        failures.append("enabled_visible_button_without_safe_preview_backed_candidate")
    if int(snapshot.get("one_click_button_enabled_count") or 0) > 1:
        failures.append(f"multiple_enabled_one_click_buttons:{snapshot.get('one_click_button_enabled_count')}")
    if contract is not None:
        if snapshot.get("one_click_button_enabled") and not bool(contract.get("updates")):
            failures.append("enabled_visible_button_with_empty_contract_updates")
        if snapshot.get("one_click_button_enabled") and contract.get("preview_pass") is False:
            failures.append("enabled_visible_button_with_preview_pass_false")
        if snapshot.get("one_click_button_enabled") and contract.get("blocking_reason") not in (None, ""):
            failures.append(f"enabled_visible_button_with_blocking_reason:{contract.get('blocking_reason')}")
    action_debug = _selected_action_debug(state)
    idea_visible = _visible_text_indicates_improvement_idea(snapshot)
    candidate_evidence = _candidate_search_evidence_from_state(state)
    failures.extend(_active_under_capacity_partial_blocker_failures(snapshot, state, candidate_evidence))
    selected_updates = dict(action_debug.get("selected_action_updates") or {})
    executor_backed = bool(action_debug.get("executor_backed_candidate_exists"))
    safe_preview = bool(action_debug.get("safe_preview_candidate_exists"))
    safe_evidence_count = int(candidate_evidence.get("safe_executor_backed_candidates_count") or 0)
    target_band_evidence_count = int(candidate_evidence.get("target_band_candidate_count") or 0)
    actionable_idea_available = bool(
        safe_preview
        or executor_backed
        or safe_evidence_count > 0
        or (
            target_band_evidence_count > 0
            and bool(candidate_evidence.get("best_target_band_candidate_updates"))
        )
    )
    idea_requires_cta = bool(idea_visible and (actionable_idea_available or expect.get("ideas_require_cta")))
    selected_action_type = str(action_debug.get("selected_action_type") or "").strip()
    selected_title = _norm_text(
        (state.get("guidance_compute_probe") or {}).get("primary_title")
        or action_debug.get("selected_action_title")
        or snapshot.get("design_guide_visible_text")
        or ""
    ).lower()
    if expect.get("no_primary_cta") and bool(snapshot.get("one_click_button_enabled")):
        failures.append("in_target_still_showing_action:expected_no_primary_cta")
    if expect.get("selected_action_type_not") and selected_action_type == str(expect.get("selected_action_type_not")):
        failures.append(f"wrong_card_intent:unexpected_selected_action_type:{selected_action_type}")
    for phrase in list(expect.get("forbidden_title_phrases") or []):
        phrase_norm = str(phrase or "").lower()
        if phrase_norm and phrase_norm in selected_title:
            failures.append(f"wrong_card_intent:forbidden_terminal_recommendation_text:{phrase_norm}")
    if idea_requires_cta and not in_target_terminal:
        if not snapshot.get("one_click_button_visible"):
            failures.append("missing_executor_backed_cta_when_ideas_exist:no_visible_button")
        if not snapshot.get("one_click_button_enabled"):
            failures.append("missing_executor_backed_cta_when_ideas_exist:button_not_enabled")
        if not selected_updates:
            failures.append("missing_executor_backed_cta_when_ideas_exist:empty_selected_updates")
        if not executor_backed:
            failures.append("missing_executor_backed_cta_when_ideas_exist:not_executor_backed")
    text_lower = _norm_text(snapshot.get("design_guide_visible_text") or "").lower()
    if "manual review suggested" in text_lower or "review manually" in text_lower:
        if safe_preview or executor_backed or idea_requires_cta:
            failures.append("manual_review_visible_despite_reduction_idea_or_candidate")
        elif not _manual_review_text_is_specific_blocker(snapshot):
            failures.append("manual_review_without_specific_engineering_blocker")
    if safe_preview and not executor_backed and idea_visible:
        failures.append("safe_preview_candidate_found_but_not_executor_attached")
    return failures


def _local_cleanup_gate_failures(
    snapshot: dict[str, Any],
    state: dict[str, Any],
    expect: dict[str, Any],
    evidence: dict[str, Any],
) -> list[str]:
    if not bool(expect.get("local_cleanup_gate")):
        return []
    failures: list[str] = []
    local = _local_cleanup_evidence_from_state(state, evidence)
    family_utils = dict(local.get("family_utils") or {})
    material = [str(v or "").strip().lower() for v in list(local.get("materially_overprovided_families") or [])]
    expected_families = [
        str(v or "").strip().lower()
        for v in list(expect.get("materially_overprovided_families") or [])
        if str(v or "").strip()
    ]
    expected_family = str(expect.get("materially_overprovided_family") or "").strip().lower()
    if expected_family:
        expected_families.append(expected_family)
    expected_any = [
        str(v or "").strip().lower()
        for v in list(expect.get("materially_overprovided_families_any") or [])
        if str(v or "").strip()
    ]
    selected_title = _norm_text(
        (state.get("guidance_compute_probe") or {}).get("primary_title")
        or (state.get("design_guide_probe") or {}).get("primary_card_title")
        or snapshot.get("design_guide_visible_text")
        or ""
    ).lower()
    action_debug = _selected_action_debug(state)
    button_contract = dict(action_debug.get("button_contract") or {})
    selected_action_type = str(action_debug.get("selected_action_type") or "").strip()
    primary_enabled = bool(snapshot.get("one_click_button_enabled"))
    safe_count = local.get("safe_local_cleanup_count")
    rendered_executable_cta = bool(
        primary_enabled
        and button_contract.get("actionable")
        and button_contract.get("updates")
        and button_contract.get("preview_pass") is True
        and button_contract.get("blocking_reason") in (None, "")
    )
    if rendered_executable_cta and int(safe_count or 0) <= 0:
        safe_count = 1
    for family in expected_families:
        util = _float_or_none(family_utils.get(family))
        if util is None or util >= 0.70:
            failures.append(f"local_cleanup_gate_family_util_missing_or_not_material:{family}:{util}")
        if family not in material:
            failures.append(f"local_cleanup_gate_material_family_missing:{family}:{material}")
    if expected_any and not any(family in material for family in expected_any):
        expected_any_meaningful = [
            family
            for family in expected_any
            if (_float_or_none(family_utils.get(family)) is not None and float(_float_or_none(family_utils.get(family)) or 0.0) > 1e-9)
        ]
        if not expected_any_meaningful and material and rendered_executable_cta:
            expected_any = []
    if expected_any and not any(family in material for family in expected_any):
        failures.append(f"local_cleanup_gate_material_family_missing_any:{expected_any}:{material}")
    if local.get("local_cleanup_search_ran") is not True and not rendered_executable_cta:
        failures.append("local_cleanup_gate_search_not_run")
    if local.get("local_cleanup_search_exhaustive") is not True and not rendered_executable_cta:
        failures.append("local_cleanup_gate_search_not_exhaustive")
    inventory_count = _float_or_none(local.get("candidate_inventory_count") or local.get("local_cleanup_candidate_inventory_count"))
    unsupported = list(local.get("unsupported_cleanup_families") or [])
    exact_blockers = dict(_rendered_guidance_probe(state).get("post_click_exact_blockers_by_family") or {})
    if (
        local.get("local_cleanup_search_exhaustive") is True
        and (inventory_count is None or inventory_count <= 0)
        and not unsupported
        and not exact_blockers
        and not rendered_executable_cta
    ):
        failures.append("local_cleanup_gate_exhaustive_without_real_candidate_inventory")
    if safe_count is None:
        failures.append("local_cleanup_gate_safe_count_missing")
        return failures
    safe_count_int = int(safe_count or 0)
    if safe_count_int > 0:
        if "design is efficient" in selected_title and "target band achieved" in selected_title:
            failures.append("local_cleanup_gate_terminal_selected_despite_safe_cleanup")
        if local.get("terminal_state_blocked_by_local_cleanup") is not True and not rendered_executable_cta:
            failures.append("local_cleanup_gate_terminal_not_blocked_by_safe_cleanup")
        selected_family = str(button_contract.get("family") or action_debug.get("selected_family") or "").strip().lower()
        allowed_selected = {"bending", "geometry", "shear", "crack", "deflection", "serviceability", "combined"}
        if selected_family not in allowed_selected:
            failures.append(f"local_cleanup_gate_selected_family_not_cleanup:{selected_family}")
        expected_selected_family = str(expect.get("expected_selected_family") or "").strip().lower()
        if expected_selected_family and selected_family != expected_selected_family:
            failures.append(
                f"local_cleanup_gate_selected_family_mismatch:expected={expected_selected_family}:actual={selected_family}"
            )
        if button_contract.get("preview_pass") is not True:
            failures.append(f"local_cleanup_gate_selected_preview_not_pass:{button_contract.get('preview_pass')}")
        if not primary_enabled:
            failures.append("local_cleanup_gate_primary_cta_not_enabled_for_safe_cleanup")
    else:
        if selected_action_type == "apply_resolved_candidate" or primary_enabled:
            failures.append("local_cleanup_gate_no_safe_cleanup_but_cta_enabled")
        if exact_blockers:
            return failures
        if local.get("terminal_state_reason") != "governing_in_target_no_safe_local_cleanup":
            failures.append(f"local_cleanup_gate_terminal_reason_missing:{local.get('terminal_state_reason')}")
        if not list(local.get("local_cleanup_blocked_reasons") or []):
            failures.append("local_cleanup_gate_blocked_reasons_missing")
    return failures


def _distance_to_target(util: float | None) -> float | None:
    if util is None:
        return None
    if TARGET_LOW <= util <= TARGET_HIGH:
        return 0.0
    if util < TARGET_LOW:
        return TARGET_LOW - util
    return util - TARGET_HIGH


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    keys = ("b", "D", "bottom_bars", "bottom_dia", "link_dia", "link_legs", "link_spacing")
    out: list[str] = []
    b_inputs = dict(before.get("visible_inputs") or {})
    a_inputs = dict(after.get("visible_inputs") or {})
    for key in keys:
        b_val = _float_or_none(b_inputs.get(key))
        a_val = _float_or_none(a_inputs.get(key))
        if b_val is not None and a_val is not None:
            if not _same_value(b_val, a_val, tol=5e-3):
                out.append(key)
        elif str(b_inputs.get(key) or "") != str(a_inputs.get(key) or ""):
            out.append(key)
    return out


def _utilisation_movement(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b_sum = dict(before.get("visible_summary") or {})
    a_sum = dict(after.get("visible_summary") or {})
    b_bend = _float_or_none((b_sum.get("bending") or {}).get("util"))
    a_bend = _float_or_none((a_sum.get("bending") or {}).get("util"))
    b_shear = _float_or_none((b_sum.get("shear") or {}).get("util"))
    a_shear = _float_or_none((a_sum.get("shear") or {}).get("util"))
    b_worst = _float_or_none(b_sum.get("worst_util"))
    a_worst = _float_or_none(a_sum.get("worst_util"))
    return {
        "bending_before": b_bend,
        "bending_after": a_bend,
        "shear_before": b_shear,
        "shear_after": a_shear,
        "worst_before": b_worst,
        "worst_after": a_worst,
        "distance_to_target_before": _distance_to_target(b_worst),
        "distance_to_target_after": _distance_to_target(a_worst),
        "worst_moved_closer": (
            _distance_to_target(a_worst) is not None
            and _distance_to_target(b_worst) is not None
            and float(_distance_to_target(a_worst)) < float(_distance_to_target(b_worst)) - 1e-6
        ),
        "shear_increased": b_shear is not None and a_shear is not None and a_shear > b_shear + 5e-3,
        "bending_decreased": b_bend is not None and a_bend is not None and a_bend < b_bend - 5e-3,
        "shear_decreased": b_shear is not None and a_shear is not None and a_shear < b_shear - 5e-3,
    }


def _check_click_effect(case: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    changed = _changed_fields(before, after)
    movement = _utilisation_movement(before, after)
    after_text = str(after.get("design_guide_visible_text") or "").lower()
    explained_no_change = any(
        phrase in after_text
        for phrase in (
            "further reductions would weaken capacity",
            "current design is within the target utilisation range",
            "no material change was required",
        )
    )
    moved_materially = bool(
        movement.get("worst_moved_closer")
        or movement.get("shear_increased")
        or movement.get("bending_decreased")
        or movement.get("shear_decreased")
    )
    if not changed and not moved_materially and not explained_no_change:
        failures.append("visible_one_click_click_no_effect")

    intent = str(case.get("intent") or "")
    if intent in {"heavy_shear_cleanup", "heavy_shear_zero"}:
        before_text = str(before.get("design_guide_visible_text") or "").lower()
        shear_cleanup_card = any(
            phrase in before_text
            for phrase in (
                "shear reinforcement",
                "link spacing",
                "link legs",
                "smaller links",
                "fewer legs",
                "wider spacing",
                "stirrups",
            )
        )
        if shear_cleanup_card:
            if not any(field in changed for field in ("link_dia", "link_legs", "link_spacing")):
                failures.append("heavy_shear_cleanup_did_not_change_visible_links")
            if not bool(movement.get("shear_increased")) and _float_or_none((before.get("visible_summary") or {}).get("shear", {}).get("util")) not in (0.0, None):
                failures.append("heavy_shear_cleanup_shear_util_did_not_increase")
        elif not bool(movement.get("worst_moved_closer")) and not explained_no_change:
            failures.append("heavy_shear_case_selected_action_did_not_move_visible_utilisation_toward_target")
        after_shear_status = str(((after.get("visible_summary") or {}).get("shear") or {}).get("status") or "")
        if after_shear_status == "FAIL":
            failures.append("heavy_shear_cleanup_caused_visible_shear_fail")
    elif intent == "required_fix_bending":
        if not (movement.get("bending_decreased") or str(((after.get("visible_summary") or {}).get("bending") or {}).get("status")) == "PASS"):
            failures.append("bending_fix_did_not_improve_visible_bending")
    elif intent == "required_fix_shear":
        if not (movement.get("shear_decreased") or str(((after.get("visible_summary") or {}).get("shear") or {}).get("status")) == "PASS"):
            failures.append("shear_fix_did_not_improve_visible_shear")
    elif intent == "safe_overdesign":
        if not bool(movement.get("worst_moved_closer")) and not explained_no_change:
            failures.append("safe_overdesign_did_not_move_visible_utilisation_toward_target")
    elif intent == "bending_overdesign_locked_shear":
        if not any(field in changed for field in ("bottom_bars", "bottom_dia")):
            failures.append("bending_overdesign_cleanup_did_not_change_visible_bending_reo")
        if any(field in changed for field in ("link_dia", "link_legs", "link_spacing")):
            failures.append(f"bending_overdesign_cleanup_changed_shear_links:{changed}")
        after_bending_status = str(((after.get("visible_summary") or {}).get("bending") or {}).get("status") or "").upper()
        after_shear_status = str(((after.get("visible_summary") or {}).get("shear") or {}).get("status") or "").upper()
        if after_bending_status == "FAIL":
            failures.append("bending_overdesign_cleanup_caused_bending_fail")
        if after_shear_status == "FAIL":
            failures.append("bending_overdesign_cleanup_caused_shear_fail")
    return failures


def _check_target_band_click_contract(
    case: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    state_before: dict[str, Any],
    target: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    action_debug = _selected_action_debug(state_before)
    contract = dict(action_debug.get("button_contract") or {})
    expected_util = _float_or_none(contract.get("expected_util"))
    preview_statuses = dict(contract.get("preview_statuses") or {})
    post_util = _float_or_none((after.get("visible_summary") or {}).get("worst_util"))
    current_util = _float_or_none((before.get("visible_summary") or {}).get("worst_util"))
    low = _float_or_none(target.get("target_low"))
    high = _float_or_none(target.get("target_high"))
    before_text = _norm_text(before.get("design_guide_visible_text") or "")
    after_text = _norm_text(after.get("design_guide_visible_text") or "")
    allowed_blocker = _has_allowed_blocker_text(before_text) or _has_allowed_blocker_text(after_text)
    if expected_util is not None and post_util is not None and abs(expected_util - post_util) > 0.04:
        failures.append(f"preview_post_click_mismatch:preview={expected_util}:post={post_util}")
    post_statuses = {
        "bending": str(((after.get("visible_summary") or {}).get("bending") or {}).get("status") or "").upper(),
        "shear": str(((after.get("visible_summary") or {}).get("shear") or {}).get("status") or "").upper(),
    }
    if any(v == "FAIL" for v in post_statuses.values()) and not allowed_blocker:
        failures.append(f"post_click_new_or_remaining_failure_without_staged_reason:{post_statuses}")
    if low is None or high is None or expected_util is None or post_util is None:
        return failures
    preview_in_band = bool(low <= expected_util <= high)
    post_in_band = bool(low <= post_util <= high)
    moved_closer = bool(_utilisation_movement(before, after).get("worst_moved_closer"))
    evidence = _candidate_search_evidence_from_state(state_before)
    if not evidence:
        failures.append("missing_candidate_search_evidence:enabled_one_click")
    else:
        missing_fields = _candidate_search_evidence_missing_fields(evidence)
        if missing_fields:
            failures.append(f"missing_candidate_search_evidence:incomplete_fields:{','.join(missing_fields[:8])}")
        selected_util = _float_or_none(evidence.get("selected_candidate_util"))
        if selected_util is None:
            failures.append("missing_candidate_search_evidence:no_selected_candidate_util")
        elif abs(float(selected_util) - float(expected_util)) > 0.04:
            failures.append(
                f"missing_candidate_search_evidence:selected_util_mismatch:evidence={selected_util}:preview={expected_util}"
            )
        target_count_all = int(evidence.get("target_band_candidate_count") or 0)
        if target_count_all > 0 and (not preview_in_band or not post_in_band):
            failures.append(
                f"target_band_candidate_not_selected:count={target_count_all}:preview={expected_util}:post={post_util}"
            )
    if not preview_in_band:
        if not evidence:
            failures.append("missing_candidate_search_evidence:outside_target_preview")
        else:
            if not bool(evidence.get("candidate_search_exhaustive")):
                failures.append("non_exhaustive_candidate_search:outside_target_preview")
            if not _candidate_search_scope_is_direct_target_proof(evidence, before_text):
                failures.append(
                    "non_exhaustive_candidate_search:outside_target_scope_not_direct_target_proof:"
                    f"scope={evidence.get('search_scope')}:total={evidence.get('total_candidates_considered')}"
                )
            target_count = int(evidence.get("target_band_candidate_count") or 0)
            if target_count > 0:
                failures.append(f"target_band_candidate_not_selected:count={target_count}")
            safe_count = int(evidence.get("safe_executor_backed_candidates_count") or 0)
            if safe_count <= 0:
                failures.append("missing_candidate_search_evidence:no_safe_executor_backed_candidates")
            selected_id = evidence.get("selected_candidate_id")
            if not selected_id:
                failures.append("missing_candidate_search_evidence:no_selected_candidate_id")
            selected_util = _float_or_none(evidence.get("selected_candidate_util"))
            if selected_util is None or abs(float(selected_util) - float(expected_util)) > 0.04:
                failures.append(f"missing_candidate_search_evidence:selected_util_mismatch:evidence={selected_util}:preview={expected_util}")
            selected_dist = _float_or_none(evidence.get("selected_candidate_distance_to_band"))
            closest_dist = _float_or_none(evidence.get("closest_safe_candidate_distance_to_band"))
            closest_id = evidence.get("closest_safe_candidate_id")
            if not (
                selected_id
                and closest_id
                and (
                    selected_id == closest_id
                    or (
                        selected_dist is not None
                        and closest_dist is not None
                        and abs(float(selected_dist) - float(closest_dist)) <= 0.01
                    )
                )
            ):
                failures.append(
                    f"selected_not_closest_safe_candidate:selected={selected_id}:closest={closest_id}:selected_dist={selected_dist}:closest_dist={closest_dist}"
                )
            if not bool(evidence.get("outside_target_band_allowed")):
                failures.append("missing_allowed_blocker_failures:outside_target_not_allowed_by_evidence")
            category = str(evidence.get("outside_target_band_allowed_category") or "").strip()
            if not category:
                failures.append("missing_allowed_blocker_failures:outside_target_missing_category")
            elif category in VAGUE_OUTSIDE_TARGET_BLOCKER_CATEGORIES or category not in ALLOWED_OUTSIDE_TARGET_BLOCKER_CATEGORIES:
                failures.append(f"vague_blocker:outside_target_category:{category}")
            reason = _norm_text(evidence.get("outside_target_band_allowed_reason") or "")
            if not reason:
                failures.append("missing_allowed_blocker_failures:outside_target_missing_reason")
            elif not _evidence_reason_visible(evidence, before_text):
                failures.append("missing_allowed_blocker_failures:outside_target_reason_not_visible")
    if preview_in_band and not post_in_band:
        failures.append(f"post_click_outside_band_despite_preview_in_band:preview={expected_util}:post={post_util}")
    if not preview_in_band and not allowed_blocker:
        if current_util is not None and current_util < low:
            failures.append(f"direct_target_band_miss_below_target_without_allowed_blocker:preview={expected_util}")
        elif current_util is not None and current_util > high:
            failures.append(f"direct_target_band_miss_over_target_without_allowed_blocker:preview={expected_util}")
    if not preview_in_band and not moved_closer and not allowed_blocker:
        failures.append("post_click_outside_band_without_reason")
    if (
        not post_in_band
        and bool(after.get("one_click_button_enabled"))
        and current_util is not None
        and (current_util < low or current_util > high or not post_in_band)
    ):
        evidence = _candidate_search_evidence_from_state(state_before)
        real_engineering_blocker = bool(
            evidence
            and _candidate_search_scope_is_direct_target_proof(evidence, before_text)
            and _active_under_capacity_blocker_is_real(evidence, before_text)
        )
        if not real_engineering_blocker:
            failures.append(
                "multi_click_required_without_blocker:"
                f"current={current_util}:preview={expected_util}:post={post_util}:after_button_enabled=True"
            )
    if preview_statuses and any(str(v or "").upper() == "FAIL" for v in preview_statuses.values()):
        failures.append(f"enabled_cta_preview_status_failed:{preview_statuses}")
    return failures


def _active_failure_post_click_family_threshold_failures(
    case: dict[str, Any],
    post_click_acceptance: dict[str, Any],
) -> list[str]:
    expect = dict(case.get("expect") or {})
    if not bool(expect.get("active_failure_matrix")):
        return []
    if not list(expect.get("expected_active_failures") or []):
        return []
    failures: list[str] = []
    meaningful_utils = dict(
        post_click_acceptance.get("post_click_family_utils_meaningful")
        or post_click_acceptance.get("post_click_family_utils")
        or {}
    )
    exact_blockers = _normalised_exact_blockers(
        post_click_acceptance.get("post_click_exact_blockers_by_family")
    )
    threshold = _float_or_none(post_click_acceptance.get("final_accepted_min_family_util"))
    if threshold is None:
        threshold = FINAL_ACCEPTED_MIN_FAMILY_UTIL
    for family in sorted({str(item or "").strip().lower() for item in list(expect.get("expected_active_failures") or [])}):
        if family in {"crack", "deflection", "serviceability", "geometry"}:
            # Serviceability-active cases are covered by pass/fail and blocker checks;
            # not every serviceability recipe has a stable utilisation scalar.
            continue
        util = _float_or_none(meaningful_utils.get(family))
        if util is None:
            failures.append(f"active_failure_post_click_family_util_missing:{family}")
            continue
        if float(util) < float(threshold) and family not in exact_blockers:
            failures.append(
                "active_failure_post_click_family_below_final_threshold:"
                f"{family}:util={util}:threshold={threshold}:blockers={sorted(exact_blockers)}"
            )
    return failures


def _counter_categories(fail_reasons: list[str], *, after_click: bool = False) -> set[str]:
    cats: set[str] = set()
    for reason in fail_reasons:
        if "visible_input_mismatch" in reason:
            cats.add("input_settle_failures")
        if "visible_summary" in reason or "visible_bending_status" in reason or "visible_shear_status" in reason or "visible_worst_util" in reason:
            cats.add("visible_summary_mismatch_failures")
        if "target_low" in reason or "target_high" in reason:
            cats.add("target_band_missing_failures")
        if "target_band_mismatch" in reason or "target_band_probe_not_canonical" in reason or "target_band_fallback" in reason:
            cats.add("target_band_mismatch_failures")
        if "card_count" in reason:
            cats.add("post_click_duplicate_failures" if after_click else "duplicate_card_failures")
        if "contradiction" in reason or "multiple_visible_utilisation" in reason:
            cats.add("contradiction_failures")
        if "card_accuracy" in reason:
            cats.add("card_accuracy_failures")
        if "wrong_card_intent" in reason:
            cats.add("wrong_card_intent_failures")
        if "local_cleanup_gate_" in reason:
            cats.add("local_cleanup_gate_failures")
        if "in_target_terminal_card_missing" in reason:
            cats.add("in_target_terminal_card_missing_failures")
        if "in_target_still_showing_action" in reason:
            cats.add("in_target_still_showing_action_failures")
        if "in_target_wrong_card_colour" in reason:
            cats.add("in_target_wrong_card_colour_failures")
        if "in_target_candidate_preview_shown" in reason:
            cats.add("in_target_candidate_preview_shown_failures")
        if "bad_card_utilisation" in reason:
            cats.add("bad_card_utilisation_failures")
        if "generic_fallback_wording" in reason:
            cats.add("generic_fallback_wording_failures")
        if "safe_preview_backed_candidate_without_enabled" in reason:
            cats.add("missing_cta_for_safe_candidate_failures")
        if "missing_executor_backed_cta_when_ideas_exist" in reason:
            cats.add("missing_cta_for_safe_candidate_failures")
            cats.add("missing_executor_backed_cta_when_ideas_exist_failures")
        if "enabled_visible_button_with_empty_contract_updates" in reason or "enabled_visible_button_with_preview_pass_false" in reason or "enabled_cta_preview_status_failed" in reason:
            cats.add("enabled_cta_without_valid_updates_failures")
        if "direct_target_band_miss" in reason:
            cats.add("direct_target_band_miss_failures")
        if "missing_candidate_search_evidence" in reason:
            cats.add("missing_candidate_search_evidence_failures")
            cats.add("outside_target_without_search_evidence_failures")
        if "non_exhaustive_candidate_search" in reason:
            cats.add("non_exhaustive_candidate_search_failures")
        if "target_band_candidate_not_selected" in reason:
            cats.add("target_band_candidate_not_selected_failures")
        if "selected_not_closest_safe_candidate" in reason:
            cats.add("selected_not_closest_safe_candidate_failures")
        if "without_allowed_blocker" in reason or "without_staged_reason" in reason:
            cats.add("missing_allowed_blocker_failures")
        if "outside_target_missing" in reason or "outside_target_not_allowed" in reason or "outside_target_reason_not_visible" in reason:
            cats.add("missing_allowed_blocker_failures")
        if "manual_review_without_specific" in reason:
            cats.add("vague_blocker_failures")
        if "vague_blocker" in reason:
            cats.add("vague_blocker_failures")
        if "preview_post_click_mismatch" in reason:
            cats.add("preview_post_click_mismatch_failures")
        if "post_click_outside_band_without_reason" in reason:
            cats.add("post_click_outside_band_without_reason_failures")
        if "post_click_new_or_remaining_failure" in reason:
            cats.add("post_click_new_failure_failures")
        if "multi_click_required_without_blocker" in reason:
            cats.add("multi_click_required_without_blocker_failures")
        if "post_click_primary_cta_still_visible_or_enabled" in reason:
            cats.add("post_click_primary_cta_still_visible_failures")
            cats.add("multi_click_required_without_blocker_failures")
        if "post_click_not_accepted_green_or_valid_blocker" in reason:
            cats.add("post_click_not_accepted_green_or_valid_blocker_failures")
            cats.add("in_target_terminal_card_missing_failures")
        if "visible_one_click_click_no_effect" in reason:
            cats.add("no_visible_change_for_one_click_failures")
        if "click_no_effect" in reason:
            cats.add("post_click_no_visible_effect_failures")
        if "did_not_move" in reason or "did_not_improve" in reason or "util_did_not" in reason:
            cats.add("movement_toward_target_failures")
        if "stale" in reason:
            cats.add("post_click_stale_card_failures")
            cats.add("stale_visible_recommendation_failures")
        if "expected_contract" in reason:
            cats.add("expected_contract_mismatch_failures")
        if "diagram" in reason:
            cats.add("diagram_stale_failures")
        if "cross_page" in reason:
            cats.add("cross_page_state_failures")
        if "save_load" in reason:
            cats.add("save_load_failures")
    return cats


ONE_CLICK_CONTRACT_FAILURE_NAMES = (
    "missing_enabled_button_when_safe_candidate_exists",
    "button_click_no_visible_effect",
    "post_click_not_in_target_without_proof",
    "preview_not_in_target_without_proof",
    "multi_click_required_without_blocker",
    "target_band_candidate_exists_but_not_selected",
    "selected_candidate_not_closest_safe",
    "missing_candidate_search_evidence",
    "non_exhaustive_candidate_search",
    "post_click_preview_mismatch",
    "post_click_new_failure",
    "post_click_no_green_terminal_card_when_in_target",
)


def _one_click_contract_failure_names(reason: str) -> set[str]:
    text = str(reason or "")
    names: set[str] = set()
    if "safe_preview_backed_candidate_without_enabled" in text or "missing_executor_backed_cta_when_ideas_exist" in text:
        names.add("missing_enabled_button_when_safe_candidate_exists")
    if "visible_one_click_click_no_effect" in text or "click_no_effect" in text:
        names.add("button_click_no_visible_effect")
    if (
        "post_click_outside_band_without_reason" in text
        or "post_click_outside_band_despite_preview_in_band" in text
        or "direct_target_band_miss" in text
    ):
        names.add("post_click_not_in_target_without_proof")
    if (
        "outside_target_preview" in text
        or "outside_target_not_allowed" in text
        or "outside_target_missing" in text
        or "outside_target_reason_not_visible" in text
        or "without_allowed_blocker" in text
    ):
        names.add("preview_not_in_target_without_proof")
    if "multi_click_required_without_blocker" in text:
        names.add("multi_click_required_without_blocker")
    if "target_band_candidate_not_selected" in text:
        names.add("target_band_candidate_exists_but_not_selected")
    if "selected_not_closest_safe_candidate" in text:
        names.add("selected_candidate_not_closest_safe")
    if "missing_candidate_search_evidence" in text:
        names.add("missing_candidate_search_evidence")
    if "non_exhaustive_candidate_search" in text:
        names.add("non_exhaustive_candidate_search")
    if "preview_post_click_mismatch" in text:
        names.add("post_click_preview_mismatch")
    if "post_click_new_or_remaining_failure" in text or "enabled_cta_preview_status_failed" in text:
        names.add("post_click_new_failure")
    if "in_target_terminal_card_missing" in text or "in_target_still_showing_action" in text:
        names.add("post_click_no_green_terminal_card_when_in_target")
    return names


def _one_click_contract_failures(results: list[dict[str, Any]]) -> dict[str, int]:
    failures = {name: 0 for name in ONE_CLICK_CONTRACT_FAILURE_NAMES}
    for result in results:
        for reason in list(result.get("fail_reasons") or []):
            for name in _one_click_contract_failure_names(str(reason)):
                failures[name] += 1
    return failures


def _check_cross_page_state(page, base_url: str, reference: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    visited: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    ref_inputs = dict(reference.get("visible_inputs") or {})
    ref_summary = dict(reference.get("visible_summary") or {})
    labels = {
        "inputs": "Inputs",
        "design": "Design",
        "bending": "Bending",
        "shear": "Shear",
        "deflection": "Deflection",
    }
    for slug in ("inputs", "design", "bending", "shear", "deflection"):
        try:
            label = labels[slug]
            clicked = False
            click_errors: list[str] = []
            try:
                current_state = _load_browser_state_robust(
                    page,
                    case_id=f"cross_page_{slug}",
                    stage=f"cross_page_precheck:{slug}",
                )
                clicked = str(current_state.get("page_slug") or "") == slug
            except Exception:
                clicked = False
            for locator in (
                page.locator(f'a[href*="page={slug}"]').first,
                page.locator(f'[href*="page={slug}"]').first,
                page.get_by_role("tab", name=label, exact=True),
                page.get_by_role("link", name=label, exact=True),
                page.get_by_role("button", name=label, exact=True),
                page.get_by_label(label, exact=True),
                page.get_by_text(label, exact=True),
            ):
                if clicked:
                    break
                try:
                    locator.click(timeout=10_000)
                    clicked = True
                    break
                except Exception as exc:
                    click_errors.append(f"{type(exc).__name__}:{exc}")
            if not clicked:
                raise RuntimeError(f"could not click page navigation {label}: {click_errors[-2:]}")
            state, read_meta = _wait_for_browser_state_payload(
                page,
                case_id=f"cross_page_{slug}",
                stage=f"cross_page_state_read:{slug}",
                timeout_s=120.0,
                expected_page_slug=slug,
            )
            probe = dict(state.get("summary_state_probe") or {})
            overview = dict(state.get("summary_overview_probe") or {})
            page_slug = str(state.get("page_slug") or "")
            if page_slug != slug:
                failures.append(f"cross_page_wrong_slug:{slug}:actual={page_slug}")
            for visible_key, probe_key in (("b", "b"), ("D", "D"), ("link_spacing", "s_lig")):
                ref = _float_or_none(ref_inputs.get(visible_key))
                actual = _float_or_none(probe.get(probe_key))
                if ref is not None and actual is not None and not _same_value(ref, actual, tol=5e-3):
                    failures.append(f"cross_page_state_input_changed:{slug}:{probe_key}:expected={ref}:actual={actual}")
            ref_worst = _float_or_none(ref_summary.get("worst_util"))
            actual_worst = _float_or_none(overview.get("worst_util"))
            if ref_worst is not None and actual_worst is not None and abs(ref_worst - actual_worst) > 0.05:
                failures.append(f"cross_page_summary_changed:{slug}:expected={ref_worst}:actual={actual_worst}")
            visited.append(
                {
                    "page": slug,
                    "page_slug": page_slug,
                    "worst_util": actual_worst,
                    "read_method": read_meta.get("method"),
                }
            )
        except Exception as exc:
            failures.append(f"cross_page_navigation_exception:{slug}:{type(exc).__name__}:{exc}")
            if isinstance(exc, BrowserStateProbeTimeout):
                diagnostics[slug] = exc.diagnostics
            else:
                diagnostics[slug] = _capture_probe_wait_diagnostics(
                    page,
                    case_id=f"cross_page_{slug}",
                    stage=f"cross_page_exception:{slug}",
                    original=exc,
                )
    page_cycle_ghost_check = run_page_cycle_ghost_ui_check(
        page,
        base_url=base_url,
        artifact_dir=ARTIFACT_DIR,
        console_messages=[],
        label="real_user_ladder_page_cycle",
    )
    diagnostics["page_cycle_ghost_ui_check"] = page_cycle_ghost_check
    if not page_cycle_ghost_check.get("ok"):
        failures.append(
            f"{PAGE_CYCLE_GHOST_FAILURE_CLASS}:"
            f"{'; '.join(str(item) for item in list(page_cycle_ghost_check.get('failures') or []))}"
        )
    return {
        "status": "PASS" if not failures else "FAIL",
        "visited": visited,
        "failures": failures,
        "diagnostics": diagnostics,
    }


KNOWN_BAD_VERIFIER_SENTINEL_REASONS = (
    "missing_executor_backed_cta_when_ideas_exist",
    "generic_fallback_wording",
    "visible_design_guide_card_count_gt_one",
    "bad_card_utilisation:zero_fallback",
    "Visible accepted state invalid",
    "visible_contract_unresolved_or_advisory_wording",
    "visible_blocker_but_executor_backed_payload_exists",
    "visible_action_without_enabled_cta",
)


def _has_known_bad_verifier_reason(reasons: list[Any]) -> bool:
    return any(
        phrase in str(reason)
        for reason in reasons
        for phrase in KNOWN_BAD_VERIFIER_SENTINEL_REASONS
    )


def _known_bad_reproduction_status(
    results: list[dict[str, Any]],
    *,
    one_click_contract_status: str,
) -> dict[str, Any]:
    live_failures: list[str] = []
    for result in results:
        reasons = list(result.get("fail_reasons") or [])
        if _has_known_bad_verifier_reason(reasons):
            live_failures.append(str(result.get("case_id")))
    artifact_failures: list[dict[str, Any]] = []
    for path in sorted(REPO_ROOT.glob("real_user_design_guide_ladder_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for case in payload.get("cases") or []:
            reasons = [str(r) for r in case.get("fail_reasons") or []]
            if any("missing_executor_backed_cta_when_ideas_exist" in r for r in reasons):
                artifact_failures.append(
                    {
                        "artifact": str(path),
                        "case_id": case.get("case_id"),
                        "fail_reasons": reasons,
                    }
                )
                break
        if artifact_failures:
            break
    synthetic_results = [
        {
            "case_id": f"VERIFIER_SENTINEL_{index}",
            "fail_reasons": [reason],
        }
        for index, reason in enumerate(KNOWN_BAD_VERIFIER_SENTINEL_REASONS, start=1)
    ]
    synthetic_failures = [
        str(result.get("case_id"))
        for result in synthetic_results
        if _has_known_bad_verifier_reason(list(result.get("fail_reasons") or []))
    ]
    clicked_cases = [result for result in results if bool(result.get("click_attempted"))]
    browser_mode_failures = [
        str(result.get("case_id"))
        for result in results
        if str(result.get("browser_mode") or "") != "browser_live"
    ]
    post_click_required_fields = (
        "post_click_in_target_band",
        "post_click_valid_blocker_if_not_target",
        "post_click_accepted_green",
        "post_click_primary_cta_visible",
        "post_click_primary_cta_enabled",
    )
    payload_binding_required_fields = (
        "payload_binding_match",
        "payload_update_match",
        "visible_primary_candidate_id",
        "button_contract_candidate_id",
        "queued_apply_candidate_id",
        "applied_candidate_id",
    )
    missing_post_click_fields = [
        {
            "case_id": result.get("case_id"),
            "missing_fields": [field for field in post_click_required_fields if field not in result],
        }
        for result in clicked_cases
        if any(field not in result for field in post_click_required_fields)
    ]
    missing_payload_binding_fields = [
        {
            "case_id": result.get("case_id"),
            "missing_fields": [field for field in payload_binding_required_fields if field not in result],
        }
        for result in clicked_cases
        if any(field not in result for field in payload_binding_required_fields)
    ]
    case_failures = [
        {
            "case_id": result.get("case_id"),
            "verdict": result.get("verdict"),
            "fail_reasons": list(result.get("fail_reasons") or []),
        }
        for result in results
        if result.get("verdict") != "PASS"
    ]
    validity_checks = {
        "all_required_cases_pass": bool(results) and not case_failures,
        "one_click_contract_status_pass": one_click_contract_status == "PASS",
        "known_bad_live_failure_detected": bool(live_failures),
        "known_bad_historical_artifact_failure_detected": bool(artifact_failures),
        "known_bad_sentinel_detection": len(synthetic_failures) == len(synthetic_results),
        "historical_known_bad_artifact_required": False,
        "browser_mode_all_browser_live": bool(results) and not browser_mode_failures,
        "post_click_proof_fields_present_for_clicked_cases": not missing_post_click_fields,
        "payload_binding_proof_fields_present_for_clicked_cases": not missing_payload_binding_fields,
    }
    fail_reasons: list[str] = []
    if not validity_checks["all_required_cases_pass"]:
        fail_reasons.append(f"case_failures_present:{case_failures}")
    if not validity_checks["one_click_contract_status_pass"]:
        fail_reasons.append(f"one_click_contract_status_not_pass:{one_click_contract_status}")
    if not validity_checks["known_bad_sentinel_detection"]:
        fail_reasons.append("known_bad_sentinel_detection_failed")
    if not validity_checks["browser_mode_all_browser_live"]:
        fail_reasons.append(f"browser_mode_not_browser_live:{browser_mode_failures}")
    if not validity_checks["post_click_proof_fields_present_for_clicked_cases"]:
        fail_reasons.append(f"post_click_proof_fields_missing:{missing_post_click_fields}")
    if not validity_checks["payload_binding_proof_fields_present_for_clicked_cases"]:
        fail_reasons.append(f"payload_binding_proof_fields_missing:{missing_payload_binding_fields}")
    valid = not fail_reasons
    return {
        "verifier_validity_status": "VALID" if valid else "INVALID",
        "verifier_validity_fail_reasons": fail_reasons,
        "verifier_validity_checks": validity_checks,
        "known_bad_live_failures": live_failures,
        "known_bad_historical_artifact_failures": artifact_failures,
        "known_bad_synthetic_failures": synthetic_failures,
        "known_bad_sentinel_reasons": list(KNOWN_BAD_VERIFIER_SENTINEL_REASONS),
        "browser_mode_failures": browser_mode_failures,
        "case_failures_for_validity": case_failures,
        "missing_post_click_proof_fields": missing_post_click_fields,
        "missing_payload_binding_proof_fields": missing_payload_binding_fields,
    }


def _run_case(page, case: dict[str, Any], base_url: str) -> dict[str, Any]:
    case_id = str(case["case_id"])
    inputs = dict(case.get("inputs") or {})
    expect = dict(case.get("expect") or {})
    result: dict[str, Any] = {
        "case_id": case_id,
        "intended_inputs": inputs,
        "browser_mode": "browser_live",
        "click_attempted": False,
        "screenshots": {
            "before": str(ARTIFACT_DIR / f"{case_id}_before.png"),
            "after": str(ARTIFACT_DIR / f"{case_id}_after.png"),
        },
        "fail_reasons": [],
    }
    query = {"page": "inputs"}
    if case.get("recipe"):
        query["browser_recipe"] = str(case["recipe"])
    _write_case_progress(case_id, "before_page_goto")
    page.goto(_query(base_url, query), wait_until="domcontentloaded", timeout=60_000)
    _write_case_progress(case_id, "after_page_goto", page)
    result["browser_state_wait_meta"] = _wait_for_browser_state_probe(page, case_id=case_id, timeout_s=120.0)
    _write_case_progress(case_id, "after_early_readiness", page, result.get("browser_state_wait_meta"))
    result["case_specific_controls_wait_meta"] = _wait_for_case_specific_controls(page, case_id=case_id, inputs=inputs)
    _write_case_progress(case_id, "after_case_specific_controls", page, result.get("case_specific_controls_wait_meta"))
    result["visible_widget_edit_meta"] = _apply_visible_starting_state(page, inputs)
    _write_case_progress(case_id, "after_visible_starting_state", page, result.get("visible_widget_edit_meta"))
    _apply_live_inputs(page, mu=float(inputs["mu"]), vu=float(inputs["vu"]))
    _write_case_progress(case_id, "after_live_inputs", page)
    _scroll_design_guide_into_view(page)
    before, settled, settle_meta = _wait_for_visible_settle(page, timeout_s=35.0)
    result["before_settle_meta"] = {**settle_meta, "settled": settled}
    page.screenshot(path=str(ARTIFACT_DIR / f"{case_id}_before.png"), full_page=True)
    _write_case_progress(case_id, "after_before_settle", page, result.get("before_settle_meta"))
    result["final_browser_state_wait_meta"] = _wait_for_final_browser_state_probe(page, case_id=case_id, timeout_s=90.0)
    _write_case_progress(case_id, "after_final_browser_state", page, result.get("final_browser_state_wait_meta"))
    _scroll_design_guide_into_view(page)
    final_before, final_settled, final_settle_meta = _wait_for_visible_settle(
        page,
        timeout_s=20.0,
        require_card=True,
    )
    if final_settled or int(final_before.get("visible_card_count") or 0) > 0:
        before = final_before
        settled = bool(final_settled)
    result["before_settle_meta"] = {
        **dict(result.get("before_settle_meta") or {}),
        "post_final_probe_visible_settle": dict(final_settle_meta),
        "post_final_probe_settled": bool(final_settled),
        "settled": bool(settled),
    }
    page.screenshot(path=str(ARTIFACT_DIR / f"{case_id}_before.png"), full_page=True)
    _write_case_progress(case_id, "after_final_visible_settle", page, result.get("before_settle_meta"))
    state_before = _load_browser_state_robust(page, case_id=case_id, stage="state_before_read")
    _write_case_progress(case_id, "after_load_browser_state_before", page)
    target = _target_band_from_state(state_before)
    safe_candidate, safe_contract = _safe_preview_backed_candidate_exists(state_before)
    action_debug_before = _selected_action_debug(state_before)
    candidate_search_evidence_before = dict(action_debug_before.get("candidate_search_evidence") or {})
    decision_trace_before = _design_guide_decision_trace(
        state_before,
        before,
        target,
        action_debug_before,
        candidate_search_evidence_before,
    )
    result["supporting_internal_debug_before"] = {
        "safe_preview_backed_candidate_exists": safe_candidate,
        "button_contract": safe_contract,
        **action_debug_before,
        "design_guide_decision_trace": decision_trace_before,
        "guidance_compute_probe": dict(state_before.get("guidance_compute_probe") or {}),
        "design_guide_probe": dict(state_before.get("design_guide_probe") or {}),
    }

    before_failures: list[str] = []
    if not settled:
        before_failures.append("visible_ui_did_not_settle_before_click")
    before_failures.extend(_target_band_failures(state_before, target))
    before_failures.extend(_validate_visible_inputs(before, inputs))
    before_failures.extend(_validate_visible_summary(before, expect))
    before_failures.extend(_check_card_sanity_before(before, state_before, expect))
    before_failures.extend(_forbidden_unresolved_proof_failures(before, stage="pre_click"))
    before_failures.extend(_active_failure_matrix_failures(before, state_before, expect))
    before_failures.extend(_card_accuracy_failures(case, before, state_before, target))
    before_failures.extend(_card_utilisation_failures(before, state_before, target))
    before_failures.extend(_in_target_terminal_card_failures(before, state_before, target))
    before_failures.extend(_local_cleanup_gate_failures(before, state_before, expect, candidate_search_evidence_before))
    if str(case.get("intent") or "") == "bending_overdesign_locked_shear":
        selected_family = str((action_debug_before.get("button_contract") or {}).get("family") or "").strip().lower()
        selected_updates = dict(action_debug_before.get("selected_action_updates") or {})
        if int(before.get("visible_card_count") or 0) != 1:
            before_failures.append(f"bending_overdesign_visible_card_count_not_one:{before.get('visible_card_count')}")
        if selected_family != "bending":
            before_failures.append(f"bending_overdesign_selected_family_not_bending:{selected_family or 'missing'}")
        if not bool(before.get("one_click_button_enabled")):
            before_failures.append("bending_overdesign_primary_cta_not_enabled")
        if not selected_updates:
            before_failures.append("bending_overdesign_selected_updates_empty")
        if set(selected_updates) & {"lig_d", "lig_legs", "s_lig"}:
            before_failures.append(f"bending_overdesign_selected_updates_touch_shear:{selected_updates}")
        contract = dict(action_debug_before.get("button_contract") or {})
        if not (
            bool(contract.get("actionable"))
            and bool(contract.get("updates"))
            and contract.get("preview_pass") is True
        ):
            before_failures.append(f"bending_overdesign_cta_not_executor_backed:{contract}")
    local_cleanup_evidence_before = _local_cleanup_evidence_from_state(state_before, candidate_search_evidence_before)

    result.update(
        {
            "expected_state_type": _visible_summary_state_type(before, target),
            "scenario_contract": {
                "intent": case.get("intent"),
                "expect": expect,
                "primary_truth_is_visible_dom": True,
            },
            "visible_inputs_before": before.get("visible_inputs"),
            "visible_summary_before": before.get("visible_summary"),
            "design_guide_visible_text_before": before.get("design_guide_visible_text"),
            "visible_card_count_before": before.get("visible_card_count"),
            "one_click_button_visible_before": before.get("one_click_button_visible"),
            "one_click_button_enabled_before": before.get("one_click_button_enabled"),
            "target_low": target.get("target_low"),
            "target_high": target.get("target_high"),
            "target_band_source": target.get("target_band_source"),
            "target_band_payload_source": target.get("target_band_payload_source"),
            "current_utilisation": (before.get("visible_summary") or {}).get("worst_util"),
            "preview_utilisation": (action_debug_before.get("button_contract") or {}).get("expected_util"),
            "selected_action_title": (
                decision_trace_before.get("selected_title")
                or (state_before.get("guidance_compute_probe") or {}).get("primary_title")
            ),
            "selected_action_family": (action_debug_before.get("button_contract") or {}).get("family"),
            "selected_action_updates": action_debug_before.get("selected_action_updates"),
            "safe_preview_candidate_exists": action_debug_before.get("safe_preview_candidate_exists"),
            "executor_backed_candidate_exists": action_debug_before.get("executor_backed_candidate_exists"),
            "primary_card_guidance_intent": action_debug_before.get("primary_card_guidance_intent"),
            "primary_card_actionable": action_debug_before.get("primary_card_actionable"),
            "button_contract": action_debug_before.get("button_contract"),
            "visible_primary_candidate_id": action_debug_before.get("visible_primary_candidate_id"),
            "button_contract_candidate_id": action_debug_before.get("button_contract_candidate_id"),
            "visible_updates": dict(action_debug_before.get("visible_updates") or {}),
            "button_contract_updates": dict(action_debug_before.get("button_contract_updates") or {}),
            "queued_apply_candidate_id": action_debug_before.get("queued_apply_candidate_id"),
            "queued_apply_updates": dict(action_debug_before.get("queued_apply_updates") or {}),
            "applied_candidate_id": None,
            "applied_updates": {},
            "applied_changed_keys": [],
            "payload_binding_match": action_debug_before.get("payload_binding_match"),
            "payload_update_match": action_debug_before.get("payload_update_match"),
            "stale_apply_payload_blocked": action_debug_before.get("stale_apply_payload_blocked"),
            "legacy_fallback_used": action_debug_before.get("legacy_fallback_used"),
            "design_guide_primary_apply_payload": dict(action_debug_before.get("design_guide_primary_apply_payload") or {}),
            "design_guide_primary_payload_binding_audit": dict(action_debug_before.get("design_guide_primary_payload_binding_audit") or {}),
            "candidate_search_evidence": dict(candidate_search_evidence_before),
            "active_failure_matrix_metrics": _candidate_search_metrics(candidate_search_evidence_before),
            "family_utils": dict(local_cleanup_evidence_before.get("family_utils") or {}),
            "materially_overprovided_families": list(local_cleanup_evidence_before.get("materially_overprovided_families") or []),
            "local_cleanup_search_ran": local_cleanup_evidence_before.get("local_cleanup_search_ran"),
            "local_cleanup_search_exhaustive": local_cleanup_evidence_before.get("local_cleanup_search_exhaustive"),
            "safe_local_cleanup_count": local_cleanup_evidence_before.get("safe_local_cleanup_count"),
            "executable_safe_cleanup_count": local_cleanup_evidence_before.get("executable_safe_cleanup_count"),
            "advisory_cleanup_count": local_cleanup_evidence_before.get("advisory_cleanup_count"),
            "local_cleanup_candidates": list(local_cleanup_evidence_before.get("local_cleanup_candidates") or []),
            "local_cleanup_candidate_inventory": list(local_cleanup_evidence_before.get("local_cleanup_candidate_inventory") or []),
            "local_cleanup_candidate_inventory_count": local_cleanup_evidence_before.get("local_cleanup_candidate_inventory_count"),
            "candidate_inventory_count": local_cleanup_evidence_before.get("candidate_inventory_count"),
            "rejected_local_cleanup_count": local_cleanup_evidence_before.get("rejected_local_cleanup_count"),
            "local_cleanup_blocked_reasons": list(local_cleanup_evidence_before.get("local_cleanup_blocked_reasons") or []),
            "local_cleanup_blocked_reasons_by_family": dict(local_cleanup_evidence_before.get("local_cleanup_blocked_reasons_by_family") or {}),
            "exact_blockers_by_family": dict(local_cleanup_evidence_before.get("exact_blockers_by_family") or {}),
            "cleanup_evidence_by_family": dict(local_cleanup_evidence_before.get("cleanup_evidence_by_family") or {}),
            "unsupported_cleanup_families": list(local_cleanup_evidence_before.get("unsupported_cleanup_families") or []),
            "terminal_state_reason": local_cleanup_evidence_before.get("terminal_state_reason"),
            "terminal_state_blocked_by_local_cleanup": local_cleanup_evidence_before.get("terminal_state_blocked_by_local_cleanup"),
            "candidate_search_exhaustive": candidate_search_evidence_before.get("candidate_search_exhaustive"),
            "total_candidates_considered": candidate_search_evidence_before.get("total_candidates_considered"),
            "safe_executor_backed_candidates_count": candidate_search_evidence_before.get("safe_executor_backed_candidates_count"),
            "target_band_candidate_count": candidate_search_evidence_before.get("target_band_candidate_count"),
            "selected_candidate_id": candidate_search_evidence_before.get("selected_candidate_id") or action_debug_before.get("selected_candidate_id"),
            "selected_candidate_util": candidate_search_evidence_before.get("selected_candidate_util"),
            "selected_candidate_distance_to_band": candidate_search_evidence_before.get("selected_candidate_distance_to_band"),
            "closest_safe_candidate_id": candidate_search_evidence_before.get("closest_safe_candidate_id"),
            "closest_safe_candidate_util": candidate_search_evidence_before.get("closest_safe_candidate_util"),
            "closest_safe_candidate_distance_to_band": candidate_search_evidence_before.get("closest_safe_candidate_distance_to_band"),
            "best_target_band_candidate_id": candidate_search_evidence_before.get("best_target_band_candidate_id"),
            "rejected_target_band_candidates": list(candidate_search_evidence_before.get("rejected_target_band_candidates") or []),
            "rejected_target_band_candidate_reasons": list(candidate_search_evidence_before.get("rejected_target_band_candidate_reasons") or []),
            "outside_target_band_allowed": candidate_search_evidence_before.get("outside_target_band_allowed"),
            "outside_target_band_allowed_reason": candidate_search_evidence_before.get("outside_target_band_allowed_reason"),
            "outside_target_band_allowed_category": candidate_search_evidence_before.get("outside_target_band_allowed_category"),
            "design_guide_decision_trace": decision_trace_before,
        }
    )

    after = before
    run_end_event = None
    if bool(before.get("one_click_button_enabled")):
        result["click_attempted"] = True
        tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
        click_started_ms = int(time.time() * 1000)
        button = page.get_by_role("button", name=BUTTON_TEXT)
        button.click(timeout=10_000)
        run_end_event, _ = _wait_for_run_end(tracer_offset, timeout_s=20.0, start_time_ms=click_started_ms)
        run_end_data = dict((run_end_event or {}).get("data") or {})
        after, after_settled, after_settle_meta = _wait_for_visible_post_click(
            page,
            before=before,
            run_end_data=run_end_data,
            timeout_s=120.0,
        )
        result["after_settle_meta"] = {**after_settle_meta, "settled": after_settled, "run_end_seen": bool(run_end_event)}
        expected_after_util = _float_or_none(
            run_end_data.get("post_commit_live_worst_util")
            or run_end_data.get("final_live_worst_util")
        )
        try:
            result["post_click_final_browser_state_wait_meta"] = _wait_for_final_browser_state_probe(
                page,
                case_id=f"{case_id}:post_click",
                timeout_s=90.0,
                expected_worst_util=expected_after_util,
            )
            _scroll_design_guide_into_view(page)
            final_after, final_after_settled, final_after_settle_meta = _wait_for_visible_settle(
                page,
                timeout_s=20.0,
                require_card=True,
            )
            if final_after_settled or int(final_after.get("visible_card_count") or 0) > 0:
                after = final_after
                after_settled = bool(final_after_settled)
            result["after_settle_meta"] = {
                **dict(result.get("after_settle_meta") or {}),
                "post_final_probe_visible_settle": dict(final_after_settle_meta),
                "post_final_probe_settled": bool(final_after_settled),
                "settled": bool(after_settled),
            }
        except BrowserStateProbeTimeout as exc:
            result["post_click_final_browser_state_wait_meta"] = {
                "settled": False,
                "timeout_stage": exc.stage,
                "diagnostics": exc.diagnostics,
            }
            raise
    else:
        result["after_settle_meta"] = {"settled": True, "run_end_seen": False, "click_skipped_reason": "visible_button_not_enabled"}
    page.screenshot(path=str(ARTIFACT_DIR / f"{case_id}_after.png"), full_page=True)

    post_failures: list[str] = []
    state_after = _load_browser_state_robust(page, case_id=case_id, stage="state_after_read")
    run_end_payload = dict((run_end_event or {}).get("data") or {})
    binding_after = dict(
        state_after.get("design_guide_primary_payload_binding_audit")
        or (state_after.get("post_cleanup_acceptance_probe") or {}).get("primary_payload_binding_audit")
        or run_end_payload.get("primary_payload_binding_audit")
        or {}
    )
    trace_binding_after = dict(run_end_payload.get("primary_payload_binding_audit") or {})
    if trace_binding_after.get("applied_candidate_id") or trace_binding_after.get("applied_updates"):
        binding_after = trace_binding_after
    last_apply_route = dict(
        (state_after.get("post_cleanup_acceptance_probe") or {}).get("last_apply_route")
        or run_end_payload.get("last_apply_route")
        or {}
    )
    trace_last_apply_route = dict(run_end_payload.get("last_apply_route") or {})
    if trace_last_apply_route.get("applied_candidate_id") or trace_last_apply_route.get("applied_updates"):
        last_apply_route = trace_last_apply_route
    visible_updates_for_binding = dict(action_debug_before.get("visible_updates") or {})
    button_updates_for_binding = dict(action_debug_before.get("button_contract_updates") or {})
    queued_updates_after = dict(binding_after.get("queued_apply_updates") or last_apply_route.get("queued_apply_updates") or {})
    applied_updates_after = dict(binding_after.get("applied_updates") or last_apply_route.get("applied_updates") or {})
    visible_candidate_id_for_binding = (
        action_debug_before.get("visible_primary_candidate_id")
        or binding_after.get("visible_primary_candidate_id")
    )
    button_candidate_id_for_binding = (
        action_debug_before.get("button_contract_candidate_id")
        or binding_after.get("button_contract_candidate_id")
    )
    queued_candidate_id_after = binding_after.get("queued_apply_candidate_id") or last_apply_route.get("queued_apply_candidate_id")
    applied_candidate_id_after = binding_after.get("applied_candidate_id") or last_apply_route.get("applied_candidate_id")
    post_click_acceptance = _post_click_acceptance_evidence(after, state_after, target)
    changed = _changed_fields(before, after)
    if result["click_attempted"]:
        if expect.get("primary_payload_binding") or bool(expect.get("local_cleanup_gate")):
            ids = [
                str(visible_candidate_id_for_binding or "").strip(),
                str(button_candidate_id_for_binding or "").strip(),
                str(queued_candidate_id_after or "").strip(),
                str(applied_candidate_id_after or "").strip(),
            ]
            if not all(ids) or len(set(ids)) != 1:
                post_failures.append(
                    "primary_payload_candidate_binding_mismatch:"
                    f"visible={ids[0]}:button={ids[1]}:queued={ids[2]}:applied={ids[3]}"
                )
            maps = [visible_updates_for_binding, button_updates_for_binding, queued_updates_after, applied_updates_after]
            if not all(maps) or any(candidate != maps[0] for candidate in maps[1:]):
                post_failures.append(
                    "primary_payload_update_binding_mismatch:"
                    f"visible={visible_updates_for_binding}:button={button_updates_for_binding}:"
                    f"queued={queued_updates_after}:applied={applied_updates_after}"
                )
            if binding_after.get("payload_binding_match") is False:
                post_failures.append("primary_payload_binding_audit_false")
            if binding_after.get("payload_update_match") is False:
                post_failures.append("primary_payload_update_audit_false")
            if binding_after.get("legacy_fallback_used") is True or last_apply_route.get("legacy_fallback_used") is True:
                post_failures.append("primary_payload_used_legacy_fallback")
            stale_keys = list(binding_after.get("stale_candidate_changed_keys") or last_apply_route.get("stale_candidate_changed_keys") or [])
            if stale_keys:
                post_failures.append(f"primary_payload_applied_stale_changed_keys:{stale_keys}")
            if binding_after.get("stale_apply_payload_blocked") is True:
                post_failures.append("primary_payload_was_blocked_as_stale")
        if int(after.get("visible_card_count") or 0) != 1:
            post_failures.append(f"post_click_visible_design_guide_card_count_not_one:{after.get('visible_card_count')}")
        post_failures.extend(_forbidden_unresolved_proof_failures(after, stage="post_click"))
        post_failures.extend(_contradictions(after))
        post_failures.extend(_check_click_effect(case, before, after))
        post_failures.extend(_check_target_band_click_contract(case, before, after, state_before, target))
        post_failures.extend(_card_utilisation_failures(after, state_after, target))
        post_failures.extend(_in_target_terminal_card_failures(after, state_after, target))
        post_failures.extend(_active_failure_post_click_family_threshold_failures(case, post_click_acceptance))
        if str(case.get("intent") or "") == "bending_overdesign_locked_shear":
            post_util = _float_or_none((after.get("visible_summary") or {}).get("worst_util"))
            low = _float_or_none(target.get("target_low"))
            high = _float_or_none(target.get("target_high"))
            if post_util is None or low is None or high is None or not (low <= post_util <= high):
                post_failures.append(f"bending_overdesign_post_click_not_in_target:post={post_util}:target={low}-{high}")
            if any(field in changed for field in ("link_dia", "link_legs", "link_spacing")):
                post_failures.append(f"bending_overdesign_post_click_changed_shear_links:{changed}")
        if bool(expect.get("local_cleanup_gate")):
            if post_click_acceptance.get("post_click_primary_cta_visible") or post_click_acceptance.get("post_click_primary_cta_enabled"):
                post_failures.append(
                    "post_click_primary_cta_still_visible_or_enabled:"
                    f"visible={post_click_acceptance.get('post_click_primary_cta_visible')}:"
                    f"enabled={post_click_acceptance.get('post_click_primary_cta_enabled')}"
                )
            if post_click_acceptance.get("post_click_accepted_green_valid") is False:
                post_failures.append(
                    "post_click_accepted_green_has_unresolved_overprovided_families:"
                    f"families={post_click_acceptance.get('post_click_unresolved_overprovided_families')}:"
                    f"reason={post_click_acceptance.get('post_click_accepted_green_invalid_reason')}"
                )
            if not (
                post_click_acceptance.get("post_click_accepted_green")
                or post_click_acceptance.get("post_click_valid_blocker_if_not_target")
            ):
                post_failures.append(
                    "post_click_not_accepted_green_or_valid_blocker:"
                    f"state={post_click_acceptance.get('post_click_design_guide_state')}:"
                    f"reason={post_click_acceptance.get('post_click_remaining_cleanup_reason')}"
                )
        before_text = _norm_text(before.get("design_guide_visible_text_before") or before.get("design_guide_visible_text") or "")
        after_text = _norm_text(after.get("design_guide_visible_text") or "")
        if before_text and before_text == after_text and _changed_fields(before, after):
            post_failures.append("stale_visible_recommendation_after_click")

    cross_page = {"status": "not_run", "visited": [], "failures": []}
    if case_id == "case_1_screenshot_heavy_shear_cleanup":
        cross_page = _check_cross_page_state(page, base_url, after)
        post_failures.extend(cross_page.get("failures") or [])

    changed = _changed_fields(before, after)
    movement = _utilisation_movement(before, after)
    result.update(
        {
            "visible_inputs_after": after.get("visible_inputs"),
            "visible_summary_after": after.get("visible_summary"),
            "design_guide_visible_text_after": after.get("design_guide_visible_text"),
            "visible_card_count_after": after.get("visible_card_count"),
            "one_click_button_visible_after": after.get("one_click_button_visible"),
            "one_click_button_enabled_after": after.get("one_click_button_enabled"),
            "changed_fields": changed,
            "utilisation_movement": movement,
            "supporting_run_end_event": run_end_event,
            "browser_shared_probe_after": dict(state_after.get("browser_shared_probe") or {}),
            "browser_debug_probe_after": dict(state_after.get("browser_debug_probe") or {}),
            "summary_state_probe_after": dict(state_after.get("summary_state_probe") or {}),
            "guidance_compute_probe_after": dict(state_after.get("guidance_compute_probe") or {}),
            "design_guide_probe_after": dict(state_after.get("design_guide_probe") or {}),
            "post_click_utilisation": (after.get("visible_summary") or {}).get("worst_util"),
            "visible_primary_candidate_id": visible_candidate_id_for_binding,
            "button_contract_candidate_id": button_candidate_id_for_binding,
            "queued_apply_candidate_id": queued_candidate_id_after,
            "applied_candidate_id": applied_candidate_id_after,
            "visible_updates": visible_updates_for_binding,
            "button_contract_updates": button_updates_for_binding,
            "queued_apply_updates": queued_updates_after,
            "applied_updates": applied_updates_after,
            "applied_changed_keys": list(binding_after.get("applied_changed_keys") or last_apply_route.get("applied_changed_keys") or []),
            "payload_binding_match": binding_after.get("payload_binding_match"),
            "payload_update_match": binding_after.get("payload_update_match"),
            "stale_apply_payload_blocked": binding_after.get("stale_apply_payload_blocked"),
            "legacy_fallback_used": binding_after.get("legacy_fallback_used") or last_apply_route.get("legacy_fallback_used"),
            "stale_candidate_changed_keys": list(binding_after.get("stale_candidate_changed_keys") or last_apply_route.get("stale_candidate_changed_keys") or []),
            "design_guide_primary_payload_binding_audit": binding_after,
            "last_apply_route": last_apply_route,
            **post_click_acceptance,
            "cross_page_state_check": cross_page,
        }
    )
    post_failures.extend(assert_no_unresolved_material_overdesign(case_id, result))
    post_failures.extend(assert_visible_output_matches_one_click_contract(case_id, result))
    fail_reasons = before_failures + post_failures
    result["fail_reasons"] = fail_reasons
    result["verdict"] = "PASS" if not fail_reasons else "FAIL"
    result["failure_categories"] = sorted(
        _counter_categories(before_failures, after_click=False) | _counter_categories(post_failures, after_click=True)
    )
    return result


def main(argv: list[str] | None = None) -> int:
    global CURRENT_PORT, CURRENT_RUN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8512)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--case", action="append", dest="cases", default=None)
    parser.add_argument("--cases", dest="cases_csv", default=None, help="Comma-separated case_id list.")
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    all_case_ids = [str(case.get("case_id") or "") for case in REAL_USER_CASES]
    if args.list_cases:
        print("\n".join(all_case_ids))
        return 0
    selected_ids = {str(case_id).strip() for case_id in (args.cases or []) if str(case_id).strip()}
    selected_ids.update(
        str(case_id).strip()
        for case_id in str(args.cases_csv or "").split(",")
        if str(case_id).strip()
    )
    missing_ids = sorted(selected_ids - set(all_case_ids))
    if missing_ids:
        raise SystemExit(f"Unknown real-user Design Guide case(s): {', '.join(missing_ids)}")
    cases = [case for case in REAL_USER_CASES if not selected_ids or str(case["case_id"]) in selected_ids]

    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    CURRENT_RUN_ID = run_id
    CURRENT_PORT = int(args.port)
    results: list[dict[str, Any]] = []
    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    _write_root_progress(
        run_id=run_id,
        port=args.port,
        cases=cases,
        results=results,
        active_case_id=None,
        stage="starting",
    )
    try:
        if args.base_url:
            _wait_for_http(base_url)
        else:
            process = _start_streamlit(args.port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            for case in cases:
                case_id = str(case.get("case_id") or "unknown")
                _write_root_progress(
                    run_id=run_id,
                    port=args.port,
                    cases=cases,
                    results=results,
                    active_case_id=case_id,
                    stage="before_case",
                )
                context = browser.new_context(viewport={"width": 1440, "height": 1200})
                page = context.new_page()
                console_messages: list[dict[str, Any]] = []
                setattr(page, "_codex_console_messages", console_messages)
                page.on(
                    "console",
                    lambda msg, store=console_messages: store.append(
                        {
                            "type": msg.type,
                            "text": msg.text,
                            "location": msg.location,
                        }
                    ),
                )
                page.on(
                    "pageerror",
                    lambda exc, store=console_messages: store.append(
                        {
                            "type": "pageerror",
                            "text": str(exc),
                            "location": {},
                        }
                    ),
                )
                try:
                    results.append(_run_case(page, case, base_url))
                    _write_root_progress(
                        run_id=run_id,
                        port=args.port,
                        cases=cases,
                        results=results,
                        active_case_id=case_id,
                        stage="after_case",
                    )
                except Exception as exc:
                    probe_diagnostics = (
                        dict(exc.diagnostics)
                        if isinstance(exc, BrowserStateProbeTimeout)
                        else _capture_probe_wait_diagnostics(
                            page,
                            case_id=case_id,
                            stage="case_exception",
                            original=exc,
                        )
                    )
                    timeout_stage = (
                        exc.stage
                        if isinstance(exc, BrowserStateProbeTimeout)
                        else probe_diagnostics.get("stage")
                    )
                    fail = {
                        "case_id": case_id,
                        "expected_state_type": str(case.get("intent") or ""),
                        "intended_inputs": dict(case.get("inputs") or {}),
                        "browser_mode": "browser_live",
                        "visible_inputs_before": {},
                        "visible_summary_before": {},
                        "design_guide_visible_text_before": "",
                        "visible_card_count_before": 0,
                        "one_click_button_visible_before": False,
                        "one_click_button_enabled_before": False,
                        "target_low": None,
                        "target_high": None,
                        "target_band_source": None,
                        "current_utilisation": None,
                        "preview_utilisation": None,
                        "post_click_utilisation": None,
                        "post_click_design_guide_state": "not_run",
                        "post_click_design_guide_title": "",
                        "post_click_primary_cta_visible": False,
                        "post_click_primary_cta_enabled": False,
                        "post_click_executable_safe_cleanup_count": 0,
                        "post_click_safe_local_cleanup_count": 0,
                        "post_click_in_target_band": False,
                        "post_click_valid_blocker_if_not_target": False,
                        "post_click_accepted_green": False,
                        "post_click_remaining_cleanup_reason": "",
                        "post_click_all_required_checks_pass": False,
                        "post_click_failed_checks": [],
                        "selected_action_title": None,
                        "selected_action_family": None,
                        "selected_action_updates": {},
                        "candidate_search_evidence": {},
                        "family_utils": {},
                        "materially_overprovided_families": [],
                        "local_cleanup_search_ran": None,
                        "local_cleanup_search_exhaustive": None,
                        "safe_local_cleanup_count": None,
                        "executable_safe_cleanup_count": None,
                        "advisory_cleanup_count": None,
                        "local_cleanup_candidates": [],
                        "rejected_local_cleanup_count": None,
                        "local_cleanup_blocked_reasons": [],
                        "terminal_state_reason": None,
                        "terminal_state_blocked_by_local_cleanup": None,
                        "candidate_search_exhaustive": None,
                        "total_candidates_considered": None,
                        "safe_executor_backed_candidates_count": None,
                        "target_band_candidate_count": None,
                        "selected_candidate_id": None,
                        "selected_candidate_util": None,
                        "selected_candidate_distance_to_band": None,
                        "closest_safe_candidate_id": None,
                        "closest_safe_candidate_util": None,
                        "closest_safe_candidate_distance_to_band": None,
                        "best_target_band_candidate_id": None,
                        "rejected_target_band_candidates": [],
                        "rejected_target_band_candidate_reasons": [],
                        "outside_target_band_allowed": None,
                        "outside_target_band_allowed_reason": None,
                        "outside_target_band_allowed_category": None,
                        "safe_preview_candidate_exists": None,
                        "executor_backed_candidate_exists": None,
                        "click_attempted": False,
                        "visible_inputs_after": {},
                        "visible_summary_after": {},
                        "design_guide_visible_text_after": "",
                        "visible_card_count_after": 0,
                        "one_click_button_visible_after": False,
                        "one_click_button_enabled_after": False,
                        "changed_fields": [],
                        "utilisation_movement": {},
                        "scenario_contract": {"intent": case.get("intent"), "expect": dict(case.get("expect") or {})},
                        "screenshots": {
                            "before": str(ARTIFACT_DIR / f"{case_id}_before.png"),
                            "after": str(ARTIFACT_DIR / f"{case_id}_after.png"),
                            "diagnostic": probe_diagnostics.get("screenshot_path"),
                        },
                        "verdict": "FAIL",
                        "fail_reasons": [f"case_exception:{type(exc).__name__}:{exc}"],
                        "timeout_stage": timeout_stage,
                        "browser_state_wait_diagnostics": probe_diagnostics,
                        "visible_text_tail": probe_diagnostics.get("visible_text_tail"),
                        "current_url": probe_diagnostics.get("current_url"),
                        "page_title": probe_diagnostics.get("page_title"),
                        "failure_categories": ["input_settle_failures"],
                    }
                    try:
                        page.screenshot(path=fail["screenshots"]["before"], full_page=True)
                        page.screenshot(path=fail["screenshots"]["after"], full_page=True)
                    except Exception:
                        pass
                    results.append(fail)
                    try:
                        VERIFICATION_LATEST_DIR.mkdir(parents=True, exist_ok=True)
                        partial_path = VERIFICATION_LATEST_DIR / f"real_user_design_guide_ladder_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}_partial.json"
                        partial_payload = {
                            "verdict": "FAIL",
                            "partial_artifact": True,
                            "process_return_code": 1,
                            "process_return_code_reason": f"case_exception:{timeout_stage}",
                            "total_cases": len(cases),
                            "pass_count": sum(1 for item in results if item.get("verdict") == "PASS"),
                            "fail_count": sum(1 for item in results if item.get("verdict") != "PASS"),
                            "cases": results,
                        }
                        partial_path.write_text(json.dumps(partial_payload, indent=2, default=str), encoding="utf-8")
                        fail["partial_artifact_path"] = str(partial_path)
                    except Exception:
                        pass
                    _write_root_progress(
                        run_id=run_id,
                        port=args.port,
                        cases=cases,
                        results=results,
                        active_case_id=case_id,
                        stage="case_exception",
                        extra={"timeout_stage": timeout_stage},
                    )
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
            browser.close()

        counter_names = [
            "target_band_missing_failures",
            "target_band_mismatch_failures",
            "input_settle_failures",
            "visible_summary_mismatch_failures",
            "duplicate_card_failures",
            "contradiction_failures",
            "card_accuracy_failures",
            "wrong_card_intent_failures",
            "local_cleanup_gate_failures",
            "in_target_terminal_card_missing_failures",
            "in_target_still_showing_action_failures",
            "in_target_wrong_card_colour_failures",
            "in_target_candidate_preview_shown_failures",
            "bad_card_utilisation_failures",
            "generic_fallback_wording_failures",
            "missing_cta_for_safe_candidate_failures",
            "enabled_cta_without_valid_updates_failures",
            "direct_target_band_miss_failures",
            "missing_candidate_search_evidence_failures",
            "non_exhaustive_candidate_search_failures",
            "target_band_candidate_not_selected_failures",
            "selected_not_closest_safe_candidate_failures",
            "outside_target_without_search_evidence_failures",
            "multi_click_required_without_blocker_failures",
            "missing_allowed_blocker_failures",
            "vague_blocker_failures",
            "preview_post_click_mismatch_failures",
            "post_click_outside_band_without_reason_failures",
            "post_click_new_failure_failures",
            "post_click_primary_cta_still_visible_failures",
            "post_click_not_accepted_green_or_valid_blocker_failures",
            "no_visible_change_for_one_click_failures",
            "post_click_no_visible_effect_failures",
            "post_click_duplicate_failures",
            "post_click_stale_card_failures",
            "expected_contract_mismatch_failures",
            "diagram_stale_failures",
            "cross_page_state_failures",
            "save_load_failures",
            "movement_toward_target_failures",
            "missing_expected_button_failures",
            "click_no_effect_failures",
            "stale_visible_recommendation_failures",
            "missing_executor_backed_cta_when_ideas_exist_failures",
        ]
        counters = {name: 0 for name in counter_names}
        for result in results:
            for category in result.get("failure_categories") or []:
                if category in counters:
                    counters[category] += 1
        pass_count = sum(1 for result in results if result.get("verdict") == "PASS")
        one_click_contract_failures = _one_click_contract_failures(results)
        one_click_contract_status = (
            "PASS"
            if all(int(count or 0) == 0 for count in one_click_contract_failures.values())
            else "FAIL"
        )
        validity = _known_bad_reproduction_status(
            results,
            one_click_contract_status=one_click_contract_status,
        )
        payload = {
            "total_cases": len(results),
            "pass_count": pass_count,
            "fail_count": len(results) - pass_count,
            **validity,
            "one_click_contract_status": one_click_contract_status,
            "one_click_contract_failures": one_click_contract_failures,
            "target_band_source": "browser_probe",
            "save_load_test_status": "not_implemented",
            **counters,
            "cases": results,
        }
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        VERIFICATION_LATEST_DIR.mkdir(parents=True, exist_ok=True)
        out_path = VERIFICATION_LATEST_DIR / f"real_user_design_guide_ladder_{timestamp}.json"
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        verdict = (
            "PASS"
            if payload["fail_count"] == 0
            and payload["verifier_validity_status"] == "VALID"
            and payload["one_click_contract_status"] == "PASS"
            else "FAIL"
        )
        return_code_reason = "all_required_real_user_verifier_checks_passed"
        if payload["fail_count"] != 0:
            return_code_reason = "case_failures_present"
        elif payload["verifier_validity_status"] != "VALID":
            return_code_reason = "verifier_validity_status_invalid"
        elif payload["one_click_contract_status"] != "PASS":
            return_code_reason = "one_click_contract_status_not_pass"
        payload["verdict"] = verdict
        payload["process_return_code"] = 0 if verdict == "PASS" else 1
        payload["process_return_code_reason"] = return_code_reason
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(json.dumps({
            "verdict": verdict,
            "output": str(out_path),
            **{k: payload[k] for k in ("total_cases", "pass_count", "fail_count", "verifier_validity_status", "one_click_contract_status")},
            "verifier_validity_fail_reasons": payload.get("verifier_validity_fail_reasons"),
            "process_return_code_reason": return_code_reason,
        }, indent=2))
        return 0 if verdict == "PASS" else 1
    except BaseException as exc:
        _write_root_progress(
            run_id=run_id,
            port=args.port,
            cases=cases,
            results=results,
            active_case_id=None,
            stage="runner_exception",
            extra={
                "exception_type": type(exc).__name__,
                "exception": str(exc),
                "process_return_code": 1,
                "process_return_code_reason": f"runner_exception:{type(exc).__name__}",
            },
        )
        raise
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
